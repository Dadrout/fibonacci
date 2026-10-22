"""Telegram bot, offline: linking, capture shapes, replies, notify, webhook secret, poller offsets.

The real TelegramClient runs against FakeSession (records Bot API calls, serves file bytes), so
payload field names and file URLs are exercised too. Capture and store are fakes.
"""
import functools
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.services.brain import events
from app.services.brain.capture import CaptureRejected, sniff_file
from app.services.brain.telegram import bot, linking, notify, poller, webhook
from app.services.brain.telegram.client import TelegramClient, TelegramError
from app.services.brain.telegram.texts import TEXTS

TOKEN = "123456:SECRET-TOKEN-abc"
CHAT = 5550001
UID = "00000000-0000-4000-8000-0000000000b1"
API = f"https://api.telegram.org/bot{TOKEN}/"
FILES = f"https://api.telegram.org/file/bot{TOKEN}/"


# ---------------------------------------------------------------- fakes

class FakeResponse:
    def __init__(self, status=200, data=None, content=b""):
        self.status_code, self._data, self.content = status, data, content

    def json(self):
        if self._data is None:
            raise ValueError("not json")
        return self._data

    def iter_content(self, size):
        for start in range(0, len(self.content), size):
            yield self.content[start:start + size]

    def close(self):
        pass


def ok(result):
    return FakeResponse(200, {"ok": True, "result": result})


class FakeSession:
    """Stands in for requests.Session: records Bot API calls and serves uploaded files."""

    def __init__(self):
        self.posts, self.gets, self.files, self.queued = [], [], {}, {}

    def queue(self, method, *responses):
        self.queued.setdefault(method, []).extend(responses)

    def post(self, url, json=None, timeout=None):
        assert url.startswith(API), url
        method = url[len(API):]
        self.posts.append((method, json, timeout))
        if self.queued.get(method):
            response = self.queued[method].pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        if method == "getFile":
            data = self.files[json["file_id"]]
            return ok({"file_id": json["file_id"], "file_path": f"documents/{json['file_id']}", "file_size": len(data)})
        if method == "getMe":
            return ok({"id": 1, "is_bot": True, "username": "FibonacciTestBot"})
        return ok(True)

    def get(self, url, timeout=None, stream=False):
        assert url.startswith(FILES), url
        self.gets.append(url)
        return FakeResponse(200, content=self.files[url[len(FILES):].split("/", 1)[1]])

    def calls(self, method):
        return [payload for name, payload, _timeout in self.posts if name == method]

    def texts(self):
        return [payload["text"] for payload in self.calls("sendMessage")]


class FakeStore:
    """Mirrors brain_redeem_telegram_code: unused, unexpired codes link one chat to one account."""

    def __init__(self):
        self.codes, self.links, self.redeem_calls = {}, {}, 0

    def save_telegram_code(self, uid, code_hash, expires_at):
        self.codes[code_hash] = {"uid": uid, "expires_at": expires_at, "used": False}

    def redeem_telegram_code(self, code_hash, chat_id, telegram_user_id, username):
        self.redeem_calls += 1
        entry = self.codes.get(code_hash)
        if not entry or entry["used"] or entry["expires_at"] <= datetime.now(timezone.utc):
            return None
        entry["used"] = True
        self.links = {c: l for c, l in self.links.items() if l["user_id"] != entry["uid"]}
        self.links[chat_id] = {"user_id": entry["uid"], "chat_id": chat_id, "telegram_user_id": telegram_user_id,
                               "telegram_username": username, "linked_at": "2026-10-22T00:00:00+00:00"}
        return entry["uid"]

    def telegram_link(self, uid):
        return next((l for l in self.links.values() if l["user_id"] == uid), None)

    def telegram_link_for_chat(self, chat_id):
        return self.links.get(chat_id)


class FakeCapture:
    """Records captures; uploads are sniffed and size-checked like the real service."""

    def __init__(self):
        self.calls, self.reject, self.status = [], None, "queued"

    def _row(self, kind, **call):
        self.calls.append({"kind": kind, **call})
        if self.reject:
            raise CaptureRejected(self.reject, "rejected")
        return {"id": f"item-{len(self.calls)}", "status": self.status}

    def from_upload(self, uid, email, data, filename, mime, *, channel, request_id=None, metadata=None):
        if len(data) > settings.BRAIN_MAX_UPLOAD_BYTES:
            raise CaptureRejected("too_large", "Choose a file up to 20 MB.")
        sniffed = sniff_file(data, filename, mime).kind
        return self._row("upload", uid=uid, data=data, filename=filename, mime=mime, sniffed=sniffed, channel=channel,
                         request_id=request_id, metadata=metadata)

    def from_link(self, uid, email, url, *, channel, request_id=None, metadata=None):
        return self._row("link", uid=uid, url=url, channel=channel, request_id=request_id, metadata=metadata)

    def from_text(self, uid, email, text, *, title=None, channel, request_id=None, metadata=None):
        return self._row("text", uid=uid, text=text, channel=channel, request_id=request_id, metadata=metadata)


@pytest.fixture
def env(monkeypatch):
    published = []
    monkeypatch.setattr(events, "publish", lambda uid, event_type, **payload: published.append((uid, event_type, payload)))
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", None)
    bot._code_failures.clear()
    bot._acked_albums.clear()
    session = FakeSession()

    class Env:
        pass

    e = Env()
    e.session, e.store, e.capture, e.published = session, FakeStore(), FakeCapture(), published
    e.client = TelegramClient(token=TOKEN, session=session, sleep=lambda _s: None)
    e.run = lambda upd: bot.handle_update(upd, client=e.client, capture=e.capture, store=e.store)
    e.link = lambda: e.store.links.__setitem__(CHAT, {"user_id": UID, "chat_id": CHAT})
    return e


def message(text=None, *, chat_type="private", language="en", message_id=10, update_id=1, **fields):
    msg = {"message_id": message_id, "date": 1761091200, "chat": {"id": CHAT, "type": chat_type},
           "from": {"id": 777, "is_bot": False, "first_name": "Aru", "username": "aru", "language_code": language}}
    if text is not None:
        msg["text"] = text
    msg.update(fields)
    return {"update_id": update_id, "message": msg}


def en(key, **values):
    return TEXTS["en"][key].format(**values)


# ---------------------------------------------------------------- linking

@pytest.mark.parametrize("form", ["/start {code}", "{code}", " {code} ", "/start@FibonacciTestBot {code}"])
def test_link_code_links_chat_and_tells_the_web_app(env, form):
    code = linking.create_link_code(UID, store=env.store, client=env.client)
    assert code["deep_link"] == f"https://t.me/FibonacciTestBot?start={code['code']}"

    env.run(message(form.format(code=code["code"]), message_id=42))

    assert env.store.links[CHAT]["user_id"] == UID and env.store.links[CHAT]["telegram_username"] == "aru"
    sent = env.session.calls("sendMessage")[-1]
    assert sent["chat_id"] == CHAT and sent["text"] == en("linked")
    assert sent["reply_parameters"] == {"message_id": 42, "allow_sending_without_reply": True}
    assert sent["link_preview_options"] == {"is_disabled": True}
    assert env.published[0][:2] == (UID, "telegram.linked") and env.published[0][2]["telegram"]["linked"] is True


@pytest.mark.parametrize("case", ["expired", "used", "unknown"])
def test_bad_link_code_gets_a_failure_reply(env, case):
    if case == "expired":
        env.store.save_telegram_code(UID, linking.code_hash("123456"), datetime.now(timezone.utc) - timedelta(seconds=1))
    elif case == "used":
        env.store.save_telegram_code(UID, linking.code_hash("123456"), datetime.now(timezone.utc) + timedelta(minutes=5))
        env.run(message("123456"))
        env.store.links.clear()
    env.run(message("/start 123456"))
    assert env.session.texts()[-1] == en("link_failed")
    assert CHAT not in env.store.links and env.capture.calls == []


def test_link_code_guessing_is_throttled_per_chat(env):
    for guess in range(bot.MAX_CODE_FAILURES):
        env.run(message(f"{guess:06d}"))
    code = linking.create_link_code(UID, store=env.store, client=env.client)["code"]
    env.run(message(code))
    assert env.store.redeem_calls == bot.MAX_CODE_FAILURES and CHAT not in env.store.links
    assert env.session.texts()[-1] == en("link_failed")


def test_unlinked_chat_gets_instructions_and_nothing_is_captured(env):
    env.run(message("https://youtu.be/dQw4w9WgXcQ"))
    assert env.session.texts() == [en("how_to_link")] and env.capture.calls == []


@pytest.mark.parametrize("chat_type", ["group", "supergroup", "channel"])
def test_group_chats_are_ignored(env, chat_type):
    env.link()
    env.run(message("123456", chat_type=chat_type))
    env.run(message("https://example.com/notes", chat_type=chat_type))
    assert env.session.posts == [] and env.capture.calls == [] and env.store.redeem_calls == 0


@pytest.mark.parametrize("code,expected", [("ru", "ru"), ("ru-RU", "ru"), ("kk", "kk"), ("en", "en"), ("de", "en"), (None, "en")])
def test_reply_language_follows_sender_language_code(env, code, expected):
    env.run(message("hi", language=code))
    assert env.session.texts() == [TEXTS[expected]["how_to_link"]]


def test_commands_in_a_linked_chat(env):
    env.link()
    env.run(message("/start"))
    env.run(message("/settings"))
    assert env.session.texts() == [en("ready"), en("unsupported")] and env.capture.calls == []


# ---------------------------------------------------------------- capture shapes

def test_photo_downloads_the_largest_size(env):
    env.link()
    env.session.files.update({"small": b"\xff\xd8\xffsmall", "big": b"\xff\xd8\xff" + b"x" * 500, "mid": b"\xff\xd8\xffmid"})
    photo = [{"file_id": "small", "width": 90, "height": 67, "file_size": 1200},
             {"file_id": "big", "width": 1280, "height": 960},  # file_size is optional
             {"file_id": "mid", "width": 320, "height": 240, "file_size": 9000}]
    env.run(message(photo=photo, message_id=77))

    assert env.session.calls("getFile") == [{"file_id": "big"}]
    assert env.session.gets == [f"{FILES}documents/big"]
    [call] = env.capture.calls
    assert call["sniffed"] == "photo" and call["filename"] == "photo_77.jpg" and call["channel"] == "telegram"
    assert call["data"] == env.session.files["big"]
    assert call["metadata"] == {"telegram": {"chat_id": CHAT, "message_id": 77, "language": "en"}}
    assert env.session.calls("sendChatAction") == [{"chat_id": CHAT, "action": "typing"}]
    assert env.session.texts() == [en("got_it")]


@pytest.mark.parametrize("data,name,mime,kind", [
    (b"%PDF-1.7\n...", "Lecture 7.pdf", "application/pdf", "pdf"),
    (b"PK\x03\x04docx", "notes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "document"),
    (b"\x89PNG\r\n\x1a\nslide", "slide.png", "image/png", "photo"),
    (b"\xff\xd8\xffslide", "IMG_2041.JPG", "image/jpeg", "photo"),
    (b"ID3\x04audio", "lecture.mp3", "audio/mpeg", "audio"),
    (b"\x00\x00\x00\x20ftypM4A rec", "recording.m4a", "audio/mp4", "audio"),
])
def test_documents_are_captured_by_content(env, data, name, mime, kind):
    env.link()
    env.session.files["doc"] = data
    env.run(message(document={"file_id": "doc", "file_name": name, "mime_type": mime, "file_size": len(data)},
                    forward_origin={"type": "channel", "chat": {"id": -100, "type": "channel"}, "date": 1}))
    [call] = env.capture.calls
    assert (call["sniffed"], call["filename"], call["mime"]) == (kind, name, mime)
    assert env.session.texts() == [en("got_it")]


def test_voice_note_and_audio(env):
    env.link()
    env.session.files.update({"v": b"OggS\x00\x02voice", "a": b"ID3\x03song"})
    env.run(message(voice={"file_id": "v", "duration": 4, "mime_type": "audio/ogg", "file_size": 14}, message_id=1))
    env.run(message(audio={"file_id": "a", "duration": 60, "file_size": 9}, message_id=2))
    assert [(c["filename"], c["mime"], c["sniffed"]) for c in env.capture.calls] == [
        ("voice.ogg", "audio/ogg", "audio"), ("audio.mp3", "audio/mpeg", "audio")]


def test_text_links_capture_at_most_five_unique_urls(env):
    env.link()
    urls = [f"https://example.com/lecture/{n}" for n in range(7)]
    text = f"Week 7: {urls[0]}, also ({urls[1]}). {urls[0]} " + " ".join(urls[2:]) + " https://en.wikipedia.org/wiki/Variance_(statistics)"
    env.run(message(text, language="ru"))
    links = [c["url"] for c in env.capture.calls]
    assert links == urls[:5]
    assert all(c["kind"] == "link" and c["metadata"]["telegram"]["language"] == "ru" for c in env.capture.calls)
    assert len({c["request_id"] for c in env.capture.calls}) == 5
    assert env.session.texts() == [TEXTS["ru"]["got_it"]]


def test_hidden_and_schemeless_links_from_entities(env):
    env.link()
    text = "Лекция 5 — слайды тут: youtu.be/dQw4w9WgXcQ"
    hidden = {"type": "text_link", "offset": 0, "length": 8, "url": "https://www.youtube.com/watch?v=abcdefghijk"}
    start = len(text.encode("utf-16-le")) // 2 - len("youtu.be/dQw4w9WgXcQ")
    visible = {"type": "url", "offset": start, "length": len("youtu.be/dQw4w9WgXcQ")}
    env.run(message(text, entities=[hidden, visible], forward_origin={"type": "hidden_user", "sender_user_name": "x", "date": 1}))
    assert [c["url"] for c in env.capture.calls] == ["https://www.youtube.com/watch?v=abcdefghijk", "https://youtu.be/dQw4w9WgXcQ"]


def test_entity_offsets_are_utf16(env):
    env.link()
    text = "😀😀 see example.org/page"
    env.run(message(text, entities=[{"type": "url", "offset": 9, "length": 16}]))
    assert [c["url"] for c in env.capture.calls] == ["https://example.org/page"]


def test_caption_links_are_captured_with_the_file_and_on_unsupported_media(env):
    env.link()
    env.session.files["p"] = b"\xff\xd8\xffslide"
    env.run(message(photo=[{"file_id": "p", "width": 10, "height": 10}], caption="Recording: https://youtu.be/dQw4w9WgXcQ",
                    message_id=1))
    env.run(message(video={"file_id": "vid", "duration": 3}, caption="https://youtu.be/abcdefghijk", message_id=2))
    assert [c["kind"] for c in env.capture.calls] == ["upload", "link", "link"]
    assert env.capture.calls[2]["url"] == "https://youtu.be/abcdefghijk"
    assert env.session.calls("getFile") == [{"file_id": "p"}]  # the video itself is never downloaded


def test_plain_text_is_captured_as_a_note(env):
    env.link()
    env.run(message("Variance measures spread around the mean.", language="kk", message_id=5))
    [call] = env.capture.calls
    assert call["kind"] == "text" and call["text"] == "Variance measures spread around the mean."
    assert call["metadata"] == {"telegram": {"chat_id": CHAT, "message_id": 5, "language": "kk"}}
    assert env.session.texts() == [TEXTS["kk"]["got_it"]]


def test_forwarded_digits_are_content_not_a_link_code(env):
    env.link()
    env.run(message("123456", forward_origin={"type": "user", "sender_user": {"id": 1}, "date": 1}))
    assert env.store.redeem_calls == 0 and env.capture.calls[0]["kind"] == "text"


def test_redelivered_update_reuses_request_ids(env):
    env.link()
    env.run(message("https://example.com/a https://example.com/b", message_id=9))
    env.run(message("https://example.com/a https://example.com/b", message_id=9))
    first, second = env.capture.calls[:2], env.capture.calls[2:]
    assert [c["request_id"] for c in first] == [c["request_id"] for c in second]
    assert first[0]["request_id"] != first[1]["request_id"]


def test_album_is_captured_photo_by_photo_and_acknowledged_once(env):
    env.link()
    env.session.files.update({"p1": b"\xff\xd8\xff1", "p2": b"\xff\xd8\xff2", "p3": b"\xff\xd8\xff3"})
    for n in (1, 2, 3):
        env.run(message(photo=[{"file_id": f"p{n}", "width": 10, "height": 10}], media_group_id="album-1", message_id=n,
                        update_id=n))
    assert [c["data"] for c in env.capture.calls] == [b"\xff\xd8\xff1", b"\xff\xd8\xff2", b"\xff\xd8\xff3"]
    assert env.session.texts() == [en("got_it")]


def test_oversize_file_gets_the_too_large_reply_without_downloading(env):
    env.link()
    env.run(message(document={"file_id": "huge", "file_name": "scan.pdf", "file_size": 25 * 1024 * 1024}))
    assert env.session.calls("getFile") == [] and env.capture.calls == []
    assert env.session.texts() == [en("too_large")]


def test_getfile_too_big_error_is_the_too_large_reply(env):
    env.link()
    env.session.queue("getFile", FakeResponse(400, {"ok": False, "error_code": 400, "description": "Bad Request: file is too big"}))
    env.run(message(document={"file_id": "nosize", "file_name": "scan.pdf"}))
    assert env.session.texts() == [en("too_large")] and env.session.gets == []


@pytest.mark.parametrize("code,key", [("unsupported_type", "unsupported"), ("too_large", "too_large"),
                                      ("invalid_input", "error"), ("conflict", "error")])
def test_capture_rejected_gets_a_friendly_reply(env, code, key):
    env.link()
    env.capture.reject = code
    env.run(message("some notes"))
    assert env.session.texts() == [en(key)]


def test_unsupported_document_is_rejected_by_sniffing(env):
    env.link()
    env.session.files["exe"] = b"MZ\x90\x00binary"
    env.run(message(document={"file_id": "exe", "file_name": "setup.exe", "mime_type": "application/x-msdownload", "file_size": 10}))
    assert env.session.texts() == [en("unsupported")]


def test_capture_that_could_not_be_queued_says_so(env):
    env.link()
    env.capture.status = "failed"
    env.run(message("notes"))
    assert env.session.texts() == [en("failed", reason=en("reason.internal"))]


def test_sticker_is_unsupported(env):
    env.link()
    env.run(message(sticker={"file_id": "s", "type": "regular"}))
    assert env.session.texts() == [en("unsupported")] and env.capture.calls == []


def test_store_outage_replies_error_and_never_raises(env):
    def broken(_chat):
        raise RuntimeError("supabase down")
    env.store.telegram_link_for_chat = broken
    env.run(message("hello"))
    assert env.session.texts() == [en("error")]


def test_reply_failure_never_raises(env):
    env.link()
    env.session.queue("sendMessage", *[FakeResponse(403, {"ok": False, "error_code": 403, "description": "Forbidden: bot was blocked"})] * 3)
    env.run(message("notes"))
    assert len(env.capture.calls) == 1


def test_non_message_updates_are_ignored(env):
    env.run({"update_id": 1, "edited_message": message("x")["message"]})
    env.run({"update_id": 2, "callback_query": {"id": "1"}})
    assert env.session.posts == []


# ---------------------------------------------------------------- notify

def item(language="en", **meta):
    return {"id": "i1", "channel": "telegram",
            "metadata": {"telegram": {"chat_id": CHAT, "message_id": 31, "language": language, **meta}}}


def test_notify_filed_replies_to_the_original_message(env):
    notify.notify_filed(item(), "Econometrics", "Week 7 · Variance", client=env.client)
    notify.notify_filed(item("ru"), "Эконометрика", "Дисперсия", "Variance ↔ Expected value", client=env.client)
    notify.notify_filed(item(), "Econometrics", None, client=env.client)
    first, second, third = env.session.calls("sendMessage")
    assert first["text"] == "Filed under Econometrics → Week 7 · Variance ✓"
    assert first["reply_parameters"]["message_id"] == 31 and first["chat_id"] == CHAT
    assert second["text"] == "Сохранено: Эконометрика → Дисперсия ✓\nНовая связь: Variance ↔ Expected value"
    assert third["text"] == "Filed under Econometrics ✓"


def test_notify_failed_explains_the_reason(env):
    notify.notify_failed(item(), "transcript_unavailable", client=env.client)
    notify.notify_failed(item("kk"), "something_new", client=env.client)
    assert env.session.texts() == [en("failed", reason=en("reason.transcript_unavailable")),
                                   TEXTS["kk"]["failed"].format(reason=TEXTS["kk"]["reason.internal"])]


def test_notify_is_a_no_op_without_telegram_metadata_or_bot(env):
    notify.notify_filed({"id": "i1", "metadata": {}}, "Course", "Topic", client=env.client)
    notify.notify_failed({"id": "i1", "metadata": None}, "internal", client=env.client)
    notify.notify_filed({"id": "i1", "metadata": {"telegram": {"chat_id": "not-a-number"}}}, "C", "T", client=env.client)
    unconfigured = TelegramClient(session=env.session)  # settings.TELEGRAM_BOT_TOKEN is None in tests
    assert unconfigured.configured is False
    notify.notify_filed(item(), "Course", "Topic", client=unconfigured)
    notify.notify_failed(item(), "internal", client=unconfigured)
    notify.notify_filed(item(), "Course", "Topic")  # shared client follows settings: not configured either
    assert env.session.posts == []


def test_notify_swallows_telegram_errors(env):
    env.session.queue("sendMessage", FakeResponse(400, {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}))
    notify.notify_filed(item(), "Course", "Topic", client=env.client)


# ---------------------------------------------------------------- webhook

@pytest.fixture
def handled(monkeypatch):
    seen = []
    monkeypatch.setattr(webhook, "handle_update", seen.append)
    return seen


@pytest.mark.parametrize("configured,header,accepted", [
    (None, "s3cret", False), ("s3cret", None, False), ("s3cret", "", False), ("s3cret", "wrong", False),
    ("s3cret", "s3créte", False), ("s3cret", "s3cret", True),
])
def test_webhook_secret(monkeypatch, handled, configured, header, accepted):
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", configured)
    body = {"update_id": 1, "message": {}}
    assert webhook.handle_webhook(body, header) is accepted
    assert handled == ([body] if accepted else [])


def test_webhook_accepts_even_when_handling_fails(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "s3cret")

    def boom(_update):
        raise RuntimeError("bug")
    monkeypatch.setattr(webhook, "handle_update", boom)
    assert webhook.handle_webhook({"update_id": 1}, "s3cret") is True
    assert webhook.handle_webhook(["not", "a", "dict"], "s3cret") is True


# ---------------------------------------------------------------- poller

class OffsetStore(dict):
    def get(self, key):
        return super().get(key)

    def set(self, key, value):
        self[key] = str(value).encode()


class BrokenOffsetStore:
    def get(self, key):
        raise ConnectionError("redis down")

    def set(self, key, value):
        raise ConnectionError("redis down")


class UpdatesClient:
    def __init__(self, *batches):
        self.batches, self.offsets = list(batches), []

    def updates(self, offset, timeout=25):
        self.offsets.append(offset)
        batch = self.batches.pop(0) if self.batches else []
        if isinstance(batch, Exception):
            raise batch
        return batch


def test_run_once_persists_offset_and_survives_a_failing_update():
    store, handled = OffsetStore(), []

    def handler(update):
        handled.append(update["update_id"])
        if update["update_id"] == 11:
            raise RuntimeError("bad update")

    client = UpdatesClient([{"update_id": 10}, {"update_id": 11}, {"update_id": 12}], [{"update_id": 13}])
    assert poller.run_once(client, store, handler=handler) == 13
    assert handled == [10, 11, 12] and store[poller.OFFSET_KEY] == b"13"
    assert poller.run_once(client, store, 13, handler=handler) == 14
    assert client.offsets == [None, 13] and store[poller.OFFSET_KEY] == b"14"


def test_run_once_resumes_from_the_stored_offset():
    store = OffsetStore({poller.OFFSET_KEY: b"42"})
    client = UpdatesClient([])
    assert poller.run_once(client, store, handler=lambda _u: None) == 42
    assert client.offsets == [42]


def test_run_once_keeps_going_when_redis_is_down():
    client, handled = UpdatesClient([{"update_id": 5}, {"no_id": True}, {"update_id": 6}]), []
    assert poller.run_once(client, BrokenOffsetStore(), handler=lambda u: handled.append(u["update_id"])) == 7
    assert handled == [5, 6]


def test_run_once_uses_the_real_bot_handler(env, monkeypatch):
    monkeypatch.setattr(poller, "handle_update", functools.partial(bot.handle_update, capture=env.capture, store=env.store))
    env.session.queue("getUpdates", ok([message("hello", update_id=70)]))
    store = OffsetStore()
    assert poller.run_once(env.client, store) == 71
    getupdates = env.session.calls("getUpdates")[0]
    assert getupdates == {"timeout": 25, "allowed_updates": ["message"]}
    assert env.session.texts() == [en("how_to_link")] and store[poller.OFFSET_KEY] == b"71"


def test_poll_backs_off_on_errors_and_resets_after_success():
    client = UpdatesClient(TelegramError("getUpdates failed: ConnectionError"), TelegramError("x"), [{"update_id": 1}],
                           TelegramError("y"))
    sleeps, loops = [], iter([True] * 4 + [False])
    poller.poll(client, OffsetStore(), keep_running=lambda: next(loops), sleep=sleeps.append, handler=lambda _u: None)
    assert sleeps == [1.0, 2.0, 1.0]
    assert client.offsets == [None, None, None, 2]
