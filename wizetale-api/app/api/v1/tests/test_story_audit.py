import pytest
from pydantic import ValidationError
from app.domain.models import QuizQuestion
from app.services.pipeline.scene_service import SceneAssignment, SceneService

@pytest.mark.parametrize('ids,answer', [(['a', 'a', 'c'], 'a'), (['a', 'b', 'c'], 'd')])
def test_quiz_requires_distinct_options_and_present_answer(ids, answer):
    with pytest.raises(ValidationError):
        QuizQuestion(question='Q', options=[{'id': i, 'text': i} for i in ids], correct_option=answer, explanation='Why')

@pytest.mark.parametrize('ranges', [[(2, 3)], [(1, 1), (3, 5)], [(1, 3), (2, 4)]])
def test_scene_normalization_covers_every_narration_segment_once(ranges):
    service = object.__new__(SceneService)
    assignments = [SceneAssignment(scene_index=i, start_segment_index=start, end_segment_index=end, visual_goal='Scene', on_screen_subtitle_text='Caption') for i, (start, end) in enumerate(ranges, 1)]
    normalized = service._normalize_assignments(assignments=assignments, segment_count=5, target_scene_count=3)
    covered = [i for row in normalized for i in range(row.start_segment_index, row.end_segment_index+1)]
    assert covered == list(range(1, 6))

def test_completed_media_survives_a_draft_metadata_write_failure(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from app.api.v1 import generate
    updates = []
    result = SimpleNamespace(artifacts={'video': str(tmp_path/'video.mp4'), 'audio': str(tmp_path/'audio.mp3')}, scene_count=1)
    result.model_copy = lambda **_kwargs: result
    result.model_dump = lambda **_kwargs: {'video_url': 'signed-video'}
    monkeypatch.setattr(generate.job_orchestrator, 'run', lambda **_kwargs: result)
    monkeypatch.setattr(generate, '_assert_generation_is_active', lambda *_args: None)
    monkeypatch.setattr(generate.story_repository, 'upload_asset', lambda **_kwargs: None)
    monkeypatch.setattr(generate.story_repository, 'create_signed_asset_url', lambda *_args: 'signed')
    monkeypatch.setattr(generate.story_repository, 'update_story_by_task', lambda _id, data: updates.append(data))
    monkeypatch.setattr(generate.story_repository, 'update_story_progress_if_active', lambda _id, data: updates.append(data) or True)
    monkeypatch.setattr(generate.story_repository, 'update_draft', lambda *_args: (_ for _ in ()).throw(RuntimeError('metadata unavailable')))
    task = generate.generate_story_video_task
    task.push_request(id='audit-job')
    try:
        output = task.run({'subject':'geography','topic':'Rivers'}, 'fictional', story_row_id='story', draft_id='draft')
    finally:
        task.pop_request()
    assert output['video_url'] == 'signed-video'
    assert [row['status'] for row in updates] == ['SUCCESS']

def test_fallback_scene_limit_preserves_the_entire_narration(monkeypatch):
    from app.services.pipeline.job_orchestrator import job_orchestrator
    from app.core.config import settings
    monkeypatch.setattr(settings, 'GENERATION_MAX_SCENES', 2)
    narration = '\n\n'.join(['First paragraph.', 'Second paragraph.', 'Final paragraph.'])
    scenes = job_orchestrator._build_fallback_scenes(narration, 60)
    assert len(scenes) <= 2
    assert ' '.join(s.narration_text for s in scenes).split() == narration.split()
