from app.api.v1.generate import _user_facing_error_message


def test_generation_failure_message_hides_provider_details():
    message = _user_facing_error_message("429 Quota exceeded for private-provider-account")
    assert "quota" in message.lower()
    assert "private-provider-account" not in message


def test_celery_redelivers_generation_when_a_worker_process_is_lost():
    from app.celery_utils import celery_app

    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True


def test_worker_registers_teacher_presentation_renderer():
    from worker import celery_app

    assert "app.services.teacher_presentation_video" in celery_app.conf.include
    assert "app.services.teacher_video_render" in celery_app.conf.include
    assert "app.services.presentation_visuals" in celery_app.conf.include


def test_persisted_generation_stops_reporting_progress_after_deletion_cancellation(monkeypatch):
    from types import SimpleNamespace
    from app.api.v1 import generate

    task = SimpleNamespace(request=SimpleNamespace(id="job-1"), update_state=lambda **_kwargs: None)
    progress = generate.PersistedTaskProgress(task, "job-1", "draft-1")
    monkeypatch.setattr(generate.story_repository, "update_story_progress_if_active", lambda *_args: False)

    try:
        progress.update_state(state="PROGRESS", meta={"progress": 50, "step": "audio"})
    except generate.GenerationCancelled:
        pass
    else:
        raise AssertionError("A cancelled render must stop before continuing generation")


def test_generation_guard_stops_if_account_is_deleting_or_story_is_terminal(monkeypatch):
    from app.api.v1 import generate

    monkeypatch.setattr(generate.story_repository, "is_user_deleting", lambda _user_id: True)
    monkeypatch.setattr(generate.story_repository, "get_story_job", lambda *_args: None)

    try:
        generate._assert_generation_is_active("job-1", "learner-1")
    except generate.GenerationCancelled:
        pass
    else:
        raise AssertionError("A deletion lock must prevent the worker from generating")

    monkeypatch.setattr(generate.story_repository, "is_user_deleting", lambda _user_id: False)

    try:
        generate._assert_generation_is_active("job-1", "learner-1")
    except generate.GenerationCancelled:
        pass
    else:
        raise AssertionError("A missing/terminal story row must stop the worker before upload")


def test_worker_removes_assets_if_account_deletion_wins_during_upload(monkeypatch):
    from app.api.v1 import generate

    deleted = []
    monkeypatch.setattr(
        generate,
        "_assert_generation_is_active",
        lambda *_args: (_ for _ in ()).throw(generate.GenerationCancelled("deleting")),
    )
    monkeypatch.setattr(
        generate.story_repository,
        "delete_job_assets",
        lambda user_id, job_id: deleted.append((user_id, job_id)),
    )

    try:
        generate._assert_generation_active_or_cleanup("job-1", "learner-1")
    except generate.GenerationCancelled:
        pass
    else:
        raise AssertionError("A worker must stop when deletion wins during the upload")

    assert deleted == [("learner-1", "job-1")]


def _teacher_video_orchestrator(tmp_path):
    from pathlib import Path
    from app.domain.models import (
        GenerationRequest, ImageArtifact, LearningOutcomes, NarrationAudio,
        Scene, SceneImageSpec, ValidatedTopic, VideoScript,
    )
    from app.services.pipeline.job_orchestrator import JobOrchestrator

    events = []
    quiz = [
        {
            'question': f'Question {index}?',
            'options': [
                {'id': 'a', 'text': 'One'}, {'id': 'b', 'text': 'Two'},
                {'id': 'c', 'text': 'Three'},
            ],
            'correct_option': 'a', 'explanation': 'The narration says so.',
        }
        for index in range(1, 4)
    ]

    class ScriptService:
        text_service = type('TextService', (), {'healthcheck': lambda _self: {}})()

        def validate_topic(self, _request):
            events.append('validate')
            return ValidatedTopic(
                subject='science', original_topic='Rain', normalized_topic='Rain',
                language='en-US', pedagogical_framing='Water cycle',
            )

        def generate_script(self, **_kwargs):
            events.append('script')
            return VideoScript(
                title='Rain', hook='Rain moves through the water cycle.',
                full_narration='Rain falls, collects, and returns to the sky. ' * 100,
                estimated_duration_sec=180,
            )

        def generate_learning_outcomes(self, **_kwargs):
            events.append('outcomes')
            return LearningOutcomes(recap='Rain cycles through nature.', quiz=quiz)

    class SceneService:
        def build_render_plan(self, *_args, **_kwargs):
            events.append('scenes')
            return ([Scene(
                scene_index=1, start_hint_sec=0, end_hint_sec=180,
                narration_text='Rain falls.', visual_goal='Clouds over a field.',
                on_screen_subtitle_text='Rain falls',
            )], [SceneImageSpec(scene_index=1, prompt='Clouds over a field.')])

    class ImageService:
        def generate_images(self, **_kwargs):
            events.append('images')
            return ([ImageArtifact(
                scene_index=1, image_path=str(tmp_path / 'image.png'),
                source='test', prompt='Clouds over a field.',
            )], [])

    class TTS:
        def synthesize(self, **kwargs):
            events.append('narration')
            return NarrationAudio(
                audio_path=kwargs['output_path'], duration_sec=180,
                provider='test', voice='female', language='en-US',
            )

    class SubtitleService:
        def build_cues(self, *_args):
            return []

        def write_srt(self, _cues, path):
            Path(path).write_text('', encoding='utf-8')

    class FfmpegService:
        def render(self, *, output_path, **_kwargs):
            events.append('video')
            Path(output_path).write_bytes(b'mp4')

    orchestrator = JobOrchestrator(
        script_service=ScriptService(), scene_service_instance=SceneService(),
        image_service=ImageService(), tts_provider=TTS(),
        subtitle_service_instance=SubtitleService(), ffmpeg_service_instance=FfmpegService(),
    )
    paths = type('Paths', (), {})()
    paths.temp_dir = tmp_path / 'temp'
    paths.output_dir = tmp_path / 'output'
    paths.video_path = paths.output_dir / 'video.mp4'
    paths.audio_path = paths.output_dir / 'audio.mp3'
    paths.subtitles_path = paths.output_dir / 'subtitles.srt'
    paths.manifest_path = paths.output_dir / 'manifest.json'
    paths.temp_dir.mkdir()
    paths.output_dir.mkdir()
    orchestrator.build_paths = lambda **_kwargs: paths
    request = GenerationRequest(
        subject='science', topic='Rain', user_id='teacher-1', school_grade='4',
    )
    return orchestrator, request, events


def test_orchestrator_skips_learning_outcomes_for_teacher_video(tmp_path):
    import json

    orchestrator, request, events = _teacher_video_orchestrator(tmp_path)

    result = orchestrator.run(
        request=request, job_id='render-1', generate_learning_outcomes=False,
    )

    assert 'outcomes' not in events
    assert all(stage in events for stage in ('scenes', 'narration', 'images', 'video'))
    assert result.recap == ''
    assert result.quiz == []
    manifest = json.loads((tmp_path / 'output' / 'manifest.json').read_text())
    assert manifest['recap'] == ''
    assert manifest['quiz'] == []


def test_orchestrator_generates_learning_outcomes_by_default(tmp_path):
    orchestrator, request, events = _teacher_video_orchestrator(tmp_path)

    result = orchestrator.run(request=request, job_id='student-1')

    assert 'outcomes' in events
    assert result.recap == 'Rain cycles through nature.'
    assert len(result.quiz) == 3
