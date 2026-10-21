from types import SimpleNamespace

from app.services.video.ffmpeg_service import FFmpegService


def test_ffmpeg_prefers_x264_and_falls_back_to_openh264(monkeypatch):
    responses = iter([
        SimpleNamespace(stdout=" V..... libopenh264 H.264 encoder", stderr=""),
        SimpleNamespace(stdout=" V..... libx264 H.264 encoder", stderr=""),
    ])
    monkeypatch.setattr("app.services.video.ffmpeg_service.subprocess.run", lambda *a, **k: next(responses))
    service = FFmpegService()

    assert service._select_video_encoder() == "libopenh264"
    assert service._select_video_encoder() == "libx264"


def test_openh264_uses_its_supported_constrained_baseline_profile():
    command = FFmpegService().build_command(
        image_paths=['scene.png'],
        scene_durations=[1.0],
        audio_path='voice.wav',
        subtitles_path='captions.srt',
        output_path='story.mp4',
        video_encoder='libopenh264',
    )

    assert command[command.index('-profile:v') + 1] == 'constrained_baseline'


def test_x264_keeps_its_existing_baseline_profile():
    command = FFmpegService().build_command(
        image_paths=['scene.png'],
        scene_durations=[1.0],
        audio_path='voice.wav',
        subtitles_path='captions.srt',
        output_path='story.mp4',
        video_encoder='libx264',
    )

    assert command[command.index('-profile:v') + 1] == 'baseline'
