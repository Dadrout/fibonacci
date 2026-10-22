"""Core Brain logic, offline: gaps, citations, schemas, sniffing, media links, SSRF, linker, plans."""
import json
import time
from datetime import date

import pytest

from app.core.config import settings
from app.domain.brain.pipeline import ExtractionError, LinkVerdict, LinkVerdicts
from app.services.brain import blobs, capture, link, plans, views
from app.services.brain.ai.client import AIUnavailable, gemini_schema
from app.services.brain.extract import web
from app.services.brain.extract.segments import Segment, windows

UID = "00000000-0000-4000-8000-0000000000a1"


# ---------------------------------------------------------------- gaps

def graph_with(sequences, kind="week"):
    course = {"id": "c1", "title": "Econometrics"}
    topics = [{"id": f"t{n}", "course_id": "c1", "title": f"T{n}", "sequence": n, "sequence_kind": kind, "item_count": 1}
              for n in sequences]
    return {"courses": [course], "topics": topics, "concepts": [], "links": []}


def test_gap_alerts_find_missing_weeks_between_first_and_last():
    gaps = views.gap_alerts(graph_with([1, 2, 3, 4, 5, 8]))
    assert [g["missing"] for g in gaps] == [6, 7]
    assert gaps[0]["id"] == "c1:week:6" and gaps[0]["present"] == [1, 2, 3, 4, 5, 8]


def test_gap_alerts_ignore_empty_topics_and_single_numbers():
    graph = graph_with([1, 3])
    graph["topics"][1]["item_count"] = 0
    assert views.gap_alerts(graph) == []


# ---------------------------------------------------------------- AI plumbing

def test_gemini_schema_drops_large_array_limits_but_keeps_small_ones():
    schema = {"type": "object", "properties": {"a": {"type": "array", "maxItems": 40, "default": []},
                                               "b": {"type": "array", "maxItems": 3}}}
    cleaned = gemini_schema(schema)
    assert "maxItems" not in cleaned["properties"]["a"] and "default" not in cleaned["properties"]["a"]
    assert cleaned["properties"]["b"]["maxItems"] == 3


def test_plan_text_never_leaks_passage_ids():
    assert plans.clean("Watch the video (P3, P4) at 14:32") == "Watch the video at 14:32"
    assert "P12" not in plans.clean("See P12 for the definition")


# ---------------------------------------------------------------- capture

@pytest.mark.parametrize("head,name,kind", [
    (b"%PDF-1.7", "x.bin", "pdf"),
    (b"\xff\xd8\xff\xe0", "IMG_1.HEIC", "photo"),
    (b"\x89PNG\r\n\x1a\n", "slide.png", "photo"),
    (b"OggS\x00\x02", "voice.oga", "audio"),
])
def test_sniff_trusts_magic_bytes_over_names(head, name, kind):
    assert capture.sniff_file(head + b"\x00" * 32, name, None).kind == kind


def test_sniff_rejects_unknown_binaries():
    with pytest.raises(capture.CaptureRejected) as error:
        capture.sniff_file(b"MZ\x90\x00binary", "tool.exe", "application/octet-stream")
    assert error.value.code == "unsupported_type"


def test_youtube_ids_from_common_link_shapes():
    for url in ("https://youtu.be/2xcUup_-K6c", "https://www.youtube.com/watch?v=2xcUup_-K6c&t=10",
                "https://youtube.com/shorts/2xcUup_-K6c", "https://m.youtube.com/watch?feature=share&v=2xcUup_-K6c"):
        assert capture.youtube_id(url) == "2xcUup_-K6c"
    assert capture.youtube_id("https://example.com/watch?v=nope") is None


# ---------------------------------------------------------------- media links

def test_media_tokens_are_owner_scoped_signed_and_expire(monkeypatch):
    url = blobs.sign_media(UID, f"{UID}/item/thumbnail.jpg", "image/jpeg", ttl=60)
    token = url.rsplit("/", 1)[1]
    claims = blobs.verify_media(token)
    assert claims["p"] == f"{UID}/item/thumbnail.jpg" and claims["m"] == "image/jpeg"
    assert blobs.verify_media(token[:-2] + ("A" if token[-1] != "A" else "B") + token[-1]) is None
    with pytest.raises(blobs.BlobError):
        blobs.sign_media(UID, "someone-else/item/x.jpg", "image/jpeg")
    monkeypatch.setattr(time, "time", lambda: 10**12)
    assert blobs.verify_media(token) is None


def test_local_blob_store_refuses_path_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BRAIN_MEDIA_DIR", str(tmp_path))
    store = blobs.BlobStore()
    store.put(f"{UID}/i1/original.txt", b"hi", "text/plain")
    assert store.get(f"{UID}/i1/original.txt") == b"hi"
    with pytest.raises(blobs.BlobError):
        store.get("../../etc/passwd")


# ---------------------------------------------------------------- SSRF guard

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://169.254.169.254/latest/meta-data", "http://[::1]/", "http://10.1.2.3/",
    "http://192.168.0.10/", "http://[::ffff:127.0.0.1]/", "http://0.0.0.0/", "ftp://example.com/",
    "http://8.8.8.8:6379/",
])
def test_web_fetch_refuses_private_targets_and_odd_ports(url):
    with pytest.raises(ExtractionError) as error:
        web.check_public_url(url)
    assert error.value.code == "fetch_failed"


# ---------------------------------------------------------------- transcripts

def test_caption_lines_merge_into_minute_windows_with_anchors():
    lines = [Segment(start_sec=i * 4.0, end_sec=i * 4.0 + 4, text=f"line {i}.") for i in range(60)]
    chunks = windows(lines)
    assert 3 <= len(chunks) <= 6
    assert chunks[0].anchor.kind == "timestamp" and chunks[0].anchor.start_sec == 0
    assert all(c.anchor.end_sec >= c.anchor.start_sec for c in chunks)
    assert chunks[-1].anchor.end_sec == pytest.approx(240.0)


# ---------------------------------------------------------------- linker

class FakeCache:
    def __init__(self):
        self.data = {}

    @staticmethod
    def key(*parts):
        return json.dumps(parts)

    def get(self, op, key):
        return self.data.get((op, key))

    def put(self, op, key, value):
        self.data[(op, key)] = value


class FakeAI:
    def __init__(self, verdicts=None, fail=False):
        self.cache, self.verdicts, self.fail, self.calls = FakeCache(), verdicts or [], fail, 0

    def generate(self, **kwargs):
        self.calls += 1
        if self.fail:
            raise AIUnavailable("down")
        return LinkVerdicts(verdicts=self.verdicts)


COURSES = {"econ": {"title": "Econometrics"}, "prob": {"title": "Probability"}}


def pair(a, b, course_b="prob"):
    return {"a": {"id": a, "course_id": "econ", "name": a, "summary": ""},
            "b": {"id": b, "course_id": course_b, "name": b, "summary": ""}, "similarity": 0.8}


def test_linker_drops_weak_or_unrelated_verdicts(monkeypatch):
    monkeypatch.setattr(settings, "BRAIN_LINK_MIN_STRENGTH", 0.8)
    pairs = [pair("Heteroskedasticity", "Variance"), pair("Heteroskedasticity", "Mean"), pair("Heteroskedasticity", "Dice")]
    ai = FakeAI([LinkVerdict(pair=0, related=True, relation="builds_on", strength=0.88),
                 LinkVerdict(pair=1, related=True, relation="applies", strength=0.6),
                 LinkVerdict(pair=2, related=False, strength=0.9)])
    links = link.verify(pairs, COURSES, ai)
    assert [(l["source_concept_id"], l["target_concept_id"]) for l in links] == [("Heteroskedasticity", "Variance")]


def test_linker_caps_links_per_new_concept_preferring_cross_course(monkeypatch):
    monkeypatch.setattr(settings, "BRAIN_LINK_MIN_STRENGTH", 0.8)
    pairs = [pair("H", "Same course", course_b="econ"), pair("H", "Variance"), pair("H", "Standard error")]
    ai = FakeAI([LinkVerdict(pair=i, related=True, relation="builds_on", strength=0.95 - i * 0.01) for i in range(3)])
    links = link.verify(pairs, COURSES, ai)
    assert [l["target_concept_id"] for l in links] == ["Variance", "Standard error"]


def test_linker_replays_cached_pair_verdicts_when_offline(monkeypatch):
    monkeypatch.setattr(settings, "BRAIN_LINK_MIN_STRENGTH", 0.8)
    online = FakeAI([LinkVerdict(pair=0, related=True, relation="same_idea", strength=0.9)])
    link.verify([pair("Variance", "Variance")], COURSES, online)
    offline = FakeAI(fail=True)
    offline.cache = online.cache
    assert len(link.verify([pair("Variance", "Variance")], COURSES, offline)) == 1
    assert offline.calls == 0


# ---------------------------------------------------------------- plans

def chunk(cid, item, kind="page", **anchor):
    return {"id": cid, "item_id": item, "ordinal": 0, "anchor_kind": kind, "page": anchor.get("page"), "slide": anchor.get("slide"),
            "start_sec": anchor.get("start_sec"), "end_sec": anchor.get("end_sec"), "paragraph": None, "heading": None,
            "body": f"passage {cid}"}


class Cat:
    def __init__(self):
        self.topics = {"t6": {"id": "t6", "course_id": "econ"}}
        self.concepts = {"k1": {"id": "k1", "name": "Heteroskedasticity"}}


def test_plan_assembly_drops_uncited_claims_and_keeps_answers_server_side():
    items = {"photo": {"id": "photo", "kind": "photo", "title": "Slide 7", "course_id": "econ", "captured_at": "2026-10-21T00:00:00Z"},
             "video": {"id": "video", "kind": "youtube", "title": "Lecture", "course_id": "econ", "youtube_id": "2xcUup_-K6c",
                       "captured_at": "2026-10-21T00:00:00Z"}}
    ids = {"P1": chunk("c1", "photo", "slide", slide=7), "P2": chunk("c2", "video", "timestamp", start_sec=872.0, end_sec=910.0)}
    draft = plans.PlanDraft(
        title="Econometrics (P1)",
        days=[plans.DraftDay(day=1, focus="Heteroskedasticity", tasks=[
            plans.DraftTask(kind="watch", title="Watch 14:32", minutes=15, topic_id="t6", passage_ids=["P2"]),
            plans.DraftTask(kind="read", title="Uncited", minutes=10, passage_ids=["P99"])])],
        notes=[plans.DraftNote(heading="Key", bullets=[plans.DraftBullet(text="OLS stays unbiased (P1).", passage_ids=["P1"])])],
        flashcards=[plans.DraftCard(front="Q", back="A", passage_ids=[])],
        quiz=[plans.DraftQuestion(prompt="What breaks?", options=["Bias", "Standard errors", "R²", "Nothing"], correct_index=1,
                                  explanation="Only the SEs.", passage_ids=["P1", "P2"], explain_passage="P2",
                                  explain_reason="At 14:32 the lecturer explains it.", concepts=["heteroskedasticity"])])
    content, key = plans.assemble(UID, draft, ids, items, Cat(), "econ", 1, date(2026, 10, 24))
    assert [t["title"] for t in content["days"][0]["tasks"]] == ["Watch 14:32"]
    assert content["flashcards"] == []
    assert content["title"] == "Econometrics" and content["notes"][0]["bullets"][0]["text"] == "OLS stays unbiased."
    question = content["quiz"][0]
    assert "correct" not in json.dumps(question) and question["concept_ids"] == ["k1"]
    assert key["q1"]["correct"] == "b"
    moment = key["q1"]["moment"]["source"]
    assert moment["anchor"] == {"kind": "timestamp", "start_sec": 872.0, "end_sec": 910.0}
    assert moment["open_url"].endswith("t=872s")


def test_event_stream_survives_read_timeouts_and_ends_cleanly_on_redis_errors():
    import asyncio

    import redis

    from app.services.brain import events

    class FakeRedis:
        def __init__(self):
            self.calls = 0

        async def xread(self, streams, block, count):
            self.calls += 1
            if self.calls == 1:
                raise redis.exceptions.TimeoutError("slow read")
            if self.calls == 2:
                return [("brain:events:u1", [("1700000000000-0", {"data": '{"type": "item.filed"}'})])]
            raise redis.exceptions.ConnectionError("redis went away")

    async def collect():
        return [frame async for frame in events.stream("u1", None, client=FakeRedis())]

    frames = asyncio.run(collect())
    assert frames[0] == "retry: 2000\n\n"
    assert frames[1].startswith(": heartbeat")
    assert frames[2].startswith("id: 1700000000000-0\n") and '"item.filed"' in frames[2]
    assert len(frames) == 3


# ---------------------------------------------------------------- demo tools

class RecordingCapture:
    def __init__(self):
        self.calls = []

    def from_upload(self, uid, email, data, filename, mime, *, channel, request_id=None):
        self.calls.append(("upload", filename, mime, channel, len(data)))
        return {"id": filename}

    def from_link(self, uid, email, url, *, channel, request_id=None):
        self.calls.append(("link", url, channel))
        return {"id": url}


def test_demo_hero_sends_photo_video_pdf_through_normal_capture(tmp_path):
    from app.services.brain.demo import hero

    (tmp_path / hero.HERO_PHOTO[0]).write_bytes(b"\xff\xd8\xff photo")
    (tmp_path / hero.HERO_PDF[0]).write_bytes(b"%PDF-1.4 pdf")
    capture = RecordingCapture()
    rows = hero.send(capture, UID, "demo@example.test", directory=tmp_path)
    assert [call[0] for call in capture.calls] == ["upload", "link", "upload"]
    assert capture.calls[0][1:4] == (hero.HERO_PHOTO[0], "image/jpeg", "web_drop")
    assert capture.calls[1] == ("link", hero.HERO_YOUTUBE_URL, "web_paste")
    assert capture.calls[2][1:4] == (hero.HERO_PDF[0], "application/pdf", "web_drop")
    assert len(rows) == 3


def test_demo_hero_creates_nothing_when_a_file_is_missing(tmp_path):
    from app.services.brain.demo import hero

    (tmp_path / hero.HERO_PHOTO[0]).write_bytes(b"\xff\xd8\xff photo")
    capture = RecordingCapture()
    with pytest.raises(hero.HeroInputsMissing):
        hero.send(capture, UID, None, directory=tmp_path)
    assert capture.calls == []


def test_demo_tools_are_off_outside_demo_mode_and_in_production(monkeypatch):
    import asyncio

    from app.api.brain import routes

    assert routes.demo_tools_allowed() is False  # tests run with DEMO_MODE off
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert routes.demo_tools_allowed() is False
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert routes.demo_tools_allowed() is True
    with pytest.raises(routes.BrainError) as refused:  # reset only ever touches the demo student
        asyncio.run(routes.demo_reset(uid=UID))
    assert refused.value.status == 404


# ---------------------------------------------------------------- presentations

def test_deck_keeps_only_cited_bullets_and_drops_empty_slides():
    from app.services.brain import decks

    items = {"photo": {"id": "photo", "kind": "photo", "title": "Slide 7", "course_id": "econ", "captured_at": "2026-10-21T00:00:00Z"}}
    ids = {"P1": chunk("c1", "photo", "slide", slide=7)}
    draft = decks.DeckDraft(title="Econometrics (P1)", slides=[
        decks.DraftSlide(title="Heteroskedasticity", topic_id="t6", notes="Say it plainly, see P1.", bullets=[
            plans.DraftBullet(text="Only the standard errors break (P1).", passage_ids=["P1"]),
            plans.DraftBullet(text="Invented claim", passage_ids=["P42"])]),
        decks.DraftSlide(title="Nothing cited", bullets=[plans.DraftBullet(text="No source", passage_ids=[])]),
        decks.DraftSlide(title="Unknown topic", topic_id="nope", bullets=[plans.DraftBullet(text="Cited", passage_ids=["p1"])]),
    ])
    slides = decks.assemble(UID, draft, ids, items, {"t6"})
    assert [s["title"] for s in slides] == ["Heteroskedasticity", "Unknown topic"]
    assert [b["text"] for b in slides[0]["bullets"]] == ["Only the standard errors break."]
    assert slides[0]["bullets"][0]["sources"][0]["anchor"] == {"kind": "slide", "slide": 7}
    assert "P1" not in slides[0]["notes"] and slides[0]["topic_id"] == "t6"
    assert slides[1]["id"] == "s2" and slides[1]["topic_id"] is None


def test_deck_slide_count_stays_between_five_and_twelve():
    from app.services.brain import decks

    assert decks.slide_count(0) == "5" and decks.slide_count(7) == "9" and decks.slide_count(40) == "12"


# ---------------------------------------------------------------- telegram text → tasks

def test_text_tasks_reply_lists_only_given_tasks_and_falls_back_quietly():
    from app.services.brain.telegram import tasks

    analysis = tasks.TextAnalysis(summary="Econometrics homework for Friday.", kind="tasks", tasks=[
        tasks.TaskItem(title="Solve problems 1–10 from chapter 8", due="Friday"), tasks.TaskItem(title="Read chapter 9")])
    reply = tasks.format_reply(analysis, "ru")
    assert reply.splitlines()[0] == "Econometrics homework for Friday."
    assert "Задачи:" in reply and "☐ Solve problems 1–10 from chapter 8 — срок: Friday" in reply and "☐ Read chapter 9" in reply
    assert reply.endswith("Сохранено в ваш Brain.")
    assert tasks.format_reply(tasks.TextAnalysis(summary="A note."), "en") == "A note.\n\nSaved to your Brain."

    class Down:
        def generate(self, **_):
            raise RuntimeError("down")
    assert tasks.analyze("Homework: read chapter 9 by Friday", "en", ai=Down()) is None
    assert tasks.analyze("hi", "en", ai=Down()) is None


def test_plan_focus_adapts_to_the_time_left():
    assert [plans.focus_for(d) for d in (1, 2, 4, 5, 30)] == ["essentials", "core", "core", "full", "full"]
    rules, quiz = plans.focus_rules("essentials", 1)
    assert "ONLY the most important topics" in rules and quiz == "5"
    assert plans.focus_rules("core", 3)[1] == "6" and plans.focus_rules("full", 6)[1] == "8" and plans.focus_rules("full", 20)[1] == "10"


def test_todos_reply_names_the_tasks_and_where_they_went():
    from app.services.brain.telegram import tasks

    analysis = tasks.TextAnalysis(summary="Homework.", kind="tasks", tasks=[tasks.TaskItem(title="Read chapter 9", due="Friday")])
    reply = tasks.format_todos_reply(analysis, "en", 1)
    assert "☐ Read chapter 9 — due: Friday" in reply and reply.endswith("Added 1 to your To do list in Fibonacci.")
    assert "Saved to your Brain." not in reply
