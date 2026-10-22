"""Offline tests for the YouTube extractor: captions, recorded replay, clip transcription, title-only fallback."""
import json
import threading

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from app.domain.brain.pipeline import ExtractInput, ExtractionError
from app.services.brain.ai.client import AIUnavailable
from app.services.brain.extract import youtube
from app.services.brain.extract.segments import Segment, Transcript

VIDEO = "2xcUup_-K6c"
META = {"title": "Lecture 5: Heteroskedasticity", "author_name": "Prof. Econ"}


class FakeCache:
    def __init__(self):
        self.data = {}

    @staticmethod
    def key(*parts):
        return json.dumps(parts, default=str)

    def get(self, op, key):
        return self.data.get((op, key))

    def put(self, op, key, value):
        self.data[(op, key)] = value


class ClipAI:
    """Fake BrainAI for clip transcription: `clips` maps clip start → Transcript or exception."""

    def __init__(self, clips=None):
        self.cache, self.clips, self.starts = FakeCache(), clips or {}, []
        self.lock = threading.Lock()

    def generate(self, **kwargs):
        start, end = kwargs["parts"][0].clip
        assert end - start == youtube.CLIP_SECONDS
        with self.lock:
            self.starts.append(start)
        result = self.clips.get(start, Transcript())
        if isinstance(result, BaseException):
            raise result
        return result


def lines(start, count, step=4.0, prefix="line"):
    return [Segment(start_sec=start + i * step, end_sec=start + i * step + step, text=f"{prefix} {i}.") for i in range(count)]


def speech(*starts, language="ru-RU"):
    return Transcript(language=language, segments=[Segment(start_sec=s, end_sec=s + 30, text=f"said at {s}.") for s in starts])


@pytest.fixture
def offline(monkeypatch):
    """No captions, no oEmbed, no thumbnail fetch unless a test overrides them."""
    monkeypatch.setattr(youtube, "_captions", lambda video_id: None)
    monkeypatch.setattr(youtube, "_oembed", lambda video_id: {})
    monkeypatch.setattr(youtube, "_thumbnail", lambda video_id: b"\xff\xd8\xffthumb")


def run(ai):
    return youtube.extract(ExtractInput(kind="youtube", url=f"https://youtu.be/{VIDEO}", youtube_id=VIDEO), ai)


def test_captions_become_minute_windows_and_are_recorded(offline, monkeypatch):
    monkeypatch.setattr(youtube, "_captions", lambda video_id: lines(0, 60))
    monkeypatch.setattr(youtube, "_oembed", lambda video_id: META)
    ai = ClipAI()
    result = run(ai)
    assert ai.starts == []
    assert 3 <= len(result.chunks) <= 6
    assert all(c.anchor.kind == "timestamp" and c.anchor.end_sec >= c.anchor.start_sec for c in result.chunks)
    assert all(45 <= c.anchor.end_sec - c.anchor.start_sec <= 75 for c in result.chunks[:-1])
    assert result.chunks[0].anchor.start_sec == 0 and result.duration_sec == pytest.approx(240)
    assert result.title == META["title"] and result.thumbnail.startswith(b"\xff\xd8\xff")
    assert result.metadata == {"transcript": "captions", "channel": "Prof. Econ"}
    recorded = ai.cache.get("youtube_captions", ai.cache.key("youtube_captions", "v1", VIDEO))
    assert recorded["meta"] == META and len(recorded["segments"]) == 60


def test_recorded_captions_replay_without_fetching(offline, monkeypatch):
    ai = ClipAI()
    ai.cache.put("youtube_captions", ai.cache.key("youtube_captions", "v1", VIDEO),
                 {"meta": META, "segments": [s.model_dump() for s in lines(0, 30)]})

    def boom(video_id):
        raise AssertionError("must not fetch when a recording exists")

    monkeypatch.setattr(youtube, "_captions", boom)
    monkeypatch.setattr(youtube, "_oembed", boom)
    result = run(ai)
    assert result.metadata["transcript"] == "captions" and result.title == META["title"]
    assert result.chunks[-1].anchor.end_sec == pytest.approx(120) and ai.starts == []


def test_clip_transcription_stitches_clip_times_and_stops_after_an_empty_clip(offline):
    ai = ClipAI({0: speech(0, 120), 300: speech(10, 290), 600: speech(5), 900: speech(20),
                 1200: Transcript(), 1500: AIUnavailable("past the end")})
    result = run(ai)
    assert sorted(ai.starts) == [0, 300, 600, 900, 1200, 1500]  # second batch ends empty → no third batch
    text = " ".join(c.text for c in result.chunks)
    assert "said at 290." in text and "said at 20." in text
    assert result.metadata == {"transcript": "ai"} and result.language == "ru-RU"
    starts = [c.anchor.start_sec for c in result.chunks]
    assert starts == sorted(starts) and starts[0] == 0
    # Clip-relative 290 s in the clip starting at 300 s is absolute 590 s; clip 900's 20 s is 920 s.
    assert any(c.anchor.start_sec <= 590 <= c.anchor.end_sec for c in result.chunks)
    assert result.duration_sec == pytest.approx(950)


def test_clip_transcription_stops_when_a_whole_batch_is_empty(offline):
    ai = ClipAI({0: speech(0), 300: speech(0), 600: speech(0)})
    result = run(ai)
    assert sorted(ai.starts) == [0, 300, 600, 900, 1200, 1500]
    assert result.chunks[-1].anchor.start_sec == 600


def test_clip_segment_ends_are_clamped_to_their_clip(offline):
    clip = Transcript(segments=[Segment(start_sec=280, end_sec=900, text="runs long."),
                                Segment(start_sec=302, end_sec=301, text="slop.")])
    ai = ClipAI({0: clip})
    transcript = youtube._transcribe_clips(VIDEO, ai)
    assert [(s.start_sec, s.end_sec) for s in transcript.segments] == [(280, 300), (302, 302)]


def test_clip_budget_stops_starting_new_batches(offline, monkeypatch):
    monkeypatch.setattr(youtube, "CLIP_BUDGET_SECONDS", -1)
    ai = ClipAI({s: speech(0) for s in range(0, 7200, 300)})
    run(ai)
    assert sorted(ai.starts) == [0, 300, 600]


def test_soft_time_limit_is_not_swallowed_by_clip_errors(offline):
    ai = ClipAI({0: SoftTimeLimitExceeded()})
    with pytest.raises(SoftTimeLimitExceeded):
        run(ai)


def test_captions_without_words_fall_through_to_transcription(offline, monkeypatch):
    monkeypatch.setattr(youtube, "_captions", lambda video_id: [Segment(start_sec=0, end_sec=4, text=" \n ")])
    ai = ClipAI({0: speech(0, 40)})
    result = run(ai)
    assert result.metadata["transcript"] == "ai" and ai.starts


def test_nothing_transcribable_files_by_oembed_title(offline, monkeypatch):
    monkeypatch.setattr(youtube, "_oembed", lambda video_id: META)
    result = run(ClipAI({s: AIUnavailable("down") for s in (0, 300, 600)}))
    assert result.title == META["title"]
    assert [(c.anchor.kind, c.anchor.heading) for c in result.chunks] == [("section", "YouTube")]
    assert result.chunks[0].text == "Lecture 5: Heteroskedasticity — Prof. Econ"
    assert result.metadata == {"transcript": "title_only", "channel": "Prof. Econ"}


def test_nothing_transcribable_and_no_title_is_transcript_unavailable(offline):
    with pytest.raises(ExtractionError) as error:
        run(ClipAI())
    assert error.value.code == "transcript_unavailable"


def test_overlong_oembed_title_is_truncated(offline, monkeypatch):
    monkeypatch.setattr(youtube, "_oembed", lambda video_id: {"title": "T" * 500})
    result = run(ClipAI())
    assert result.title == "T" * 300


def test_missing_video_id_is_fetch_failed():
    with pytest.raises(ExtractionError) as error:
        youtube.extract(ExtractInput(kind="youtube", url="https://youtube.com/"), ClipAI())
    assert error.value.code == "fetch_failed"
