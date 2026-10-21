from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest

from app.services import teacher_presentation_video as video
from app.services.video.ffmpeg_service import FFmpegService
from app.services.tts import edge_tts_service as speech


def test_edge_tts_applies_a_slower_rate_when_requested(monkeypatch, tmp_path):
    captured = {}

    class Communicate:
        def __init__(self, *, text, voice, rate):
            captured.update(text=text, voice=voice, rate=rate)

        async def save(self, path):
            Path(path).write_bytes(b"audio")

    monkeypatch.setattr(speech, "edge_tts", SimpleNamespace(Communicate=Communicate))

    import asyncio

    asyncio.run(
        speech.EdgeTTSProvider()._save_audio(
            text="A clear example.",
            voice_name="en-US-JennyNeural",
            output_path=tmp_path / "voice.mp3",
            rate="-8%",
        )
    )

    assert captured == {
        "text": "A clear example.",
        "voice": "en-US-JennyNeural",
        "rate": "-8%",
    }


def test_presentation_voice_uses_the_brighter_female_voice():
    provider = speech.EdgeTTSProvider()

    assert provider._voice_name("en-US", "female") == "en-US-AriaNeural"
    assert (
        provider._voice_name("en-US", "female", presentation=True)
        == "en-US-JennyNeural"
    )


def test_language_router_drops_edge_only_presentation_options_for_other_providers():
    calls = []

    class GoogleProvider:
        provider_name = "google_cloud_tts"

        def synthesize(self, **kwargs):
            calls.append(kwargs)

    router = video.get_tts_provider().__class__(GoogleProvider())
    router.synthesize(
        text="A note",
        language="en-US",
        voice="female",
        output_path="voice.mp3",
        rate="-8%",
        presentation=True,
    )

    assert calls == [
        {
            "text": "A note",
            "language": "en-US",
            "voice": "female",
            "output_path": "voice.mp3",
        }
    ]


@pytest.mark.parametrize(
    ("total", "expected"),
    [
        (1, ["cover"]),
        (4, ["cover", "spotlight", "cards", "recap"]),
        (6, ["cover", "spotlight", "cards", "spotlight", "cards", "recap"]),
    ],
)
def test_slide_layouts_vary_through_a_deck(total, expected):
    assert [video.slide_layout_for(index, total) for index in range(total)] == expected


def test_presentation_video_keeps_text_frames_steady_and_uses_soft_brand_fades():
    command = FFmpegService().build_command(
        image_paths=["slide-1.png", "slide-2.png"],
        scene_durations=[8.0, 9.0],
        audio_path="narration.mp3",
        subtitles_path="captions.srt",
        output_path="presentation.mp4",
        static_slides=True,
    )

    filters = command[command.index("-filter_complex") + 1]
    assert "zoompan" not in filters
    assert filters.count("fade=t=in") == 2
    assert filters.count("fade=t=out") == 2


def test_presentation_audio_join_places_a_short_silence_between_slide_voices():
    command = video.build_narration_join_command(
        ["voice-1.mp3", "voice-2.mp3", "voice-3.mp3"],
        "narration.mp3",
        pause_seconds=0.32,
    )

    assert command.count("anullsrc=r=24000:cl=mono") == 2
    assert "concat=n=5:v=0:a=1" in command[command.index("-filter_complex") + 1]


def test_captions_wait_for_the_slide_voice_pause(tmp_path):
    captions = tmp_path / "captions.srt"
    video.build_srt(
        ["First slide.", "Second slide."],
        [1.0, 1.0],
        captions,
        slide_pause_seconds=0.32,
    )

    assert "00:00:01,320 --> 00:00:02,320" in captions.read_text(encoding="utf-8")


def test_regular_video_preserves_the_whole_image_over_a_blurred_backdrop():
    command = FFmpegService().build_command(
        image_paths=["scene-1.png"],
        scene_durations=[8.0],
        audio_path="narration.mp3",
        subtitles_path="captions.srt",
        output_path="story.mp4",
    )

    filters = command[command.index("-filter_complex") + 1]
    # Story scenes preserve portrait and landscape artwork instead of cropping
    # it to fill the video. Only the separate, blurred backdrop is cropped.
    assert "split=2[bgsrc0][fgsrc0]" in filters
    assert "[fgsrc0]scale=1280:720:force_original_aspect_ratio=decrease" in filters
    assert "crop=1280:720,boxblur=" in filters
    assert "[bg0][fg0]overlay=(W-w)/2:(H-h)/2" in filters
    assert "fade=t=in" not in filters


def test_renderer_narrates_ordered_slides_and_builds_branded_video(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(video.settings, "WORKDIR_ROOT", str(tmp_path))
    calls = []
    updates = []

    class TTS:
        def synthesize(
            self, *, text, language, voice, output_path, rate=None, presentation=False
        ):
            calls.append((text, language, voice, rate, presentation))
            Path(output_path).write_bytes(b"audio")
            return SimpleNamespace(duration_sec=12.0)

    class FFmpeg:
        def render(self, **kwargs):
            self.kwargs = kwargs
            Path(kwargs["output_path"]).write_bytes(b"mp4")

    def join_audio(command, *, capture_output, text, check, cwd):
        assert command[:2] == ["ffmpeg", "-y"]
        assert "anullsrc=r=24000:cl=mono" in command
        assert "-filter_complex" in command
        Path(command[-1]).write_bytes(b"joined audio")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(video.subprocess, "run", join_audio)
    ffmpeg = FFmpeg()
    renderer = video.PresentationVideoRenderer(
        tts_provider=TTS(), video_renderer=ffmpeg
    )
    content = {
        "slides": [
            {
                "title": "Equal parts",
                "key_points": ["A fraction names equal parts."],
                "speaker_notes": "Show a simple example.",
            },
            {
                "title": "Compare",
                "key_points": ["Look at the denominator."],
                "speaker_notes": "Compare two equal wholes.",
            },
        ]
    }

    result = renderer.render(
        content=content,
        lesson={"topic": "Fractions", "language": "kk-KZ"},
        user_id="teacher",
        render_id="render-1",
        progress=lambda *args: updates.append(args),
    )

    assert calls == [
        ("Show a simple example.", "kk-KZ", "female", "-8%", True),
        ("Compare two equal wholes.", "kk-KZ", "female", "-8%", True),
    ]
    assert result["duration_sec"] == 24.32
    assert Path(result["video_path"]).read_bytes() == b"mp4"
    assert len(ffmpeg.kwargs["image_paths"]) == 2
    assert ffmpeg.kwargs["audio_duration"] == 24.32
    assert ffmpeg.kwargs["scene_durations"] == [12.32, 12.0]
    assert ffmpeg.kwargs["static_slides"] is True
    assert (
        Path(ffmpeg.kwargs["subtitles_path"]).read_text(encoding="utf-8").count("--> ")
        >= 2
    )
    with Image.open(ffmpeg.kwargs["image_paths"][0]) as slide:
        assert slide.size == (1280, 720)
    assert updates[0][0] == 5 and updates[-1][0] == 65
