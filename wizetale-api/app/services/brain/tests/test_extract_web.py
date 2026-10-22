"""Offline tests for the web extractor: SSRF guard, redirects, size/time caps, HTML sections, PDF delegation."""
import socket

import pytest
import requests
from requests.structures import CaseInsensitiveDict
from urllib3.connection import HTTPConnection
from urllib3.exceptions import NewConnectionError

from app.domain.brain.pipeline import ExtractInput, ExtractionError
from app.services.brain.extract import web
from app.services.brain.tests.test_extract_files import FakeAI, PAGE_ONE, PAGE_TWO, make_pdf

HOSTS = {"public.example": "93.184.216.34", "other.example": "151.101.1.69", "internal.example": "10.0.0.5",
         "v6.example": "2606:4700::6810:84e5", "nat64.example": "64:ff9b::a9fe:a9fe"}


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    """Resolve test hostnames from a table (real DNS would be network access)."""
    def getaddrinfo(host, port, *args, **kwargs):
        address = HOSTS.get(host, host)
        try:
            family = socket.AF_INET6 if ":" in address else socket.AF_INET
            socket.inet_pton(family, address)
        except OSError:
            raise socket.gaierror(socket.EAI_NONAME, "not found")
        return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))]

    monkeypatch.setattr(web.socket, "getaddrinfo", getaddrinfo)


class FakeResponse:
    def __init__(self, status=200, headers=None, body=b"", chunks=None, error=None):
        self.status_code = status
        self.headers = CaseInsensitiveDict(headers or {})
        self.chunks = chunks if chunks is not None else [body[i:i + 65536] for i in range(0, len(body), 65536)]
        self.error, self.closed = error, False

    @property
    def is_redirect(self):
        return "location" in self.headers and self.status_code in (301, 302, 303, 307, 308)

    def iter_content(self, size):
        yield from self.chunks
        if self.error:
            raise self.error

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls, self.closed = dict(responses), [], False

    def get(self, url, **kwargs):
        assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
        self.calls.append(url)
        return self.responses[url]

    def close(self):
        self.closed = True


def page(*sections, title="Variance explained | Stats 101"):
    paragraph = "Variance measures how far a set of numbers is spread out from their average value. " * 4
    body = "".join(f"<h2>{name}</h2><p>{paragraph}</p>" for name in sections)
    return (f"<html><head><title>{title}</title></head><body><nav>Home</nav><article><h1>Variance explained</h1>"
            f"<p>{paragraph}</p>{body}</article><footer>(c) 2026</footer></body></html>")


def serve(monkeypatch, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(web, "_public_session", lambda: session)
    return session


def expect_error(code, fn, *args):
    with pytest.raises(ExtractionError) as error:
        fn(*args)
    assert error.value.code == code


# ---------------------------------------------------------------- SSRF guard

@pytest.mark.parametrize("url", [
    "http://internal.example/", "http://127.0.0.1/admin", "http://[::1]/", "http://[::ffff:10.0.0.1]/",
    "http://[::ffff:169.254.169.254]/", "http://nat64.example/", "http://[::127.0.0.1]/", "http://100.64.0.1/",
    "http://[fe80::1%25eth0]/", "http://224.0.0.1/", "http://public.example:22/", "http://public.example:0/",
    "http://public.example:99999/", "http://public.example:abc/", "http://[::1/", "file:///etc/passwd",
    "gopher://public.example/", "http:///nohost", "http://no-such-host.invalid/", "",
])
def test_check_public_url_refuses_private_odd_and_malformed_targets(url):
    expect_error("fetch_failed", web.check_public_url, url)


@pytest.mark.parametrize("url", ["https://public.example/a", "http://public.example:8080/", "https://v6.example/",
                                 "http://[::ffff:93.184.216.34]/"])
def test_check_public_url_allows_public_targets(url):
    web.check_public_url(url)


def test_redirect_to_a_private_address_is_blocked(monkeypatch):
    session = serve(monkeypatch, {
        "https://public.example/go": FakeResponse(302, {"Location": "http://internal.example/secret"}),
        "http://internal.example/secret": FakeResponse(200, {"Content-Type": "text/html"}, b"secret"),
    })
    expect_error("fetch_failed", web.fetch, "https://public.example/go")
    assert session.calls == ["https://public.example/go"] and session.closed


def test_relative_redirects_are_followed_and_capped(monkeypatch):
    session = FakeSession({
        "https://public.example/a": FakeResponse(301, {"Location": "/b"}),
        "https://public.example/b": FakeResponse(200, {"Content-Type": "text/plain"}, b"ok"),
    })
    assert web.fetch("https://public.example/a", session) == (b"ok", "text/plain", "https://public.example/b")
    loop = FakeSession({"https://public.example/loop": FakeResponse(302, {"Location": "/loop"})})
    expect_error("fetch_failed", web.fetch, "https://public.example/loop", loop)
    assert len(loop.calls) == 6
    expect_error("fetch_failed", web.fetch, "https://public.example/x",
                 FakeSession({"https://public.example/x": FakeResponse(302)}))


def test_http_errors_and_transport_errors_are_fetch_failed(monkeypatch):
    expect_error("fetch_failed", web.fetch, "https://public.example/",
                 FakeSession({"https://public.example/": FakeResponse(404)}))
    broken = FakeResponse(200, {"Content-Type": "text/html"}, chunks=[b"<html>"],
                          error=requests.exceptions.ChunkedEncodingError("reset"))
    expect_error("fetch_failed", web.fetch, "https://public.example/", FakeSession({"https://public.example/": broken}))
    assert broken.closed


def test_body_over_5_mb_is_too_large():
    big = FakeResponse(200, {"Content-Type": "text/html"}, chunks=[b"x" * 65536] * 90)
    expect_error("too_large", web.fetch, "https://public.example/", FakeSession({"https://public.example/": big}))
    assert big.closed
    declared = FakeResponse(200, {"Content-Type": "text/html", "Content-Length": str(6 * 1024 * 1024)}, body=b"x")
    expect_error("too_large", web.fetch, "https://public.example/", FakeSession({"https://public.example/": declared}))


def test_a_trickling_server_hits_the_wall_clock_cap(monkeypatch):
    clock = iter(range(0, 10_000, 20))
    monkeypatch.setattr(web.time, "monotonic", lambda: next(clock))
    slow = FakeResponse(200, {"Content-Type": "text/html"}, chunks=[b"a"] * 100)
    expect_error("fetch_failed", web.fetch, "https://public.example/", FakeSession({"https://public.example/": slow}))
    assert slow.closed


def test_connect_time_recheck_blocks_dns_rebinding(monkeypatch):
    class Sock:
        def __init__(self, peer):
            self.peer, self.closed = peer, False

        def getpeername(self):
            return (self.peer, 80)

        def close(self):
            self.closed = True

    rebound = Sock("127.0.0.1")
    monkeypatch.setattr(HTTPConnection, "_new_conn", lambda self: rebound)
    with pytest.raises(NewConnectionError):
        web._PublicHTTPConnection("public.example", 80)._new_conn()
    assert rebound.closed
    fine = Sock("93.184.216.34")
    monkeypatch.setattr(HTTPConnection, "_new_conn", lambda self: fine)
    assert web._PublicHTTPConnection("public.example", 80)._new_conn() is fine

    session = web._public_session()
    pool = session.get_adapter("https://public.example/").poolmanager.connection_from_url("https://public.example/")
    assert pool.ConnectionCls is web._PublicHTTPSConnection
    session.close()


# ---------------------------------------------------------------- extraction

def test_html_page_becomes_section_anchored_passages(monkeypatch):
    serve(monkeypatch, {"https://public.example/variance": FakeResponse(
        200, {"Content-Type": "text/html; charset=utf-8"}, page("Definition", "Sample variance").encode())})
    result = web.extract(ExtractInput(kind="web", url="https://public.example/variance"), FakeAI())
    headings = [c.anchor.heading for c in result.chunks]
    assert all(c.anchor.kind == "section" for c in result.chunks)
    assert headings == ["Variance explained", "Definition", "Sample variance"]
    assert result.title and result.metadata == {"final_host": "public.example"}


def test_windows_1251_page_is_decoded_by_its_charset(monkeypatch):
    html = page("Дисперсия", title="Лекция 5").replace("Variance measures", "Дисперсия показывает")
    serve(monkeypatch, {"https://public.example/ru": FakeResponse(
        200, {"Content-Type": "text/html; charset=windows-1251"}, html.encode("cp1251"))})
    result = web.extract(ExtractInput(kind="web", url="https://public.example/ru"), FakeAI())
    assert "Дисперсия показывает" in " ".join(c.text for c in result.chunks)
    assert "Дисперсия" in [c.anchor.heading for c in result.chunks]


def test_pdf_link_delegates_to_the_pdf_extractor(monkeypatch):
    serve(monkeypatch, {"https://public.example/w3.pdf": FakeResponse(
        200, {"Content-Type": "application/pdf"}, make_pdf([PAGE_ONE, PAGE_TWO]))})
    result = web.extract(ExtractInput(kind="web", url="https://public.example/w3.pdf"), FakeAI())
    assert [c.anchor.page for c in result.chunks] == [1, 2] and result.page_count == 2


def test_media_links_are_unsupported_and_thin_pages_unreadable(monkeypatch):
    serve(monkeypatch, {"https://public.example/cat.png": FakeResponse(200, {"Content-Type": "image/png"}, b"\x89PNG")})
    expect_error("unsupported_type", web.extract, ExtractInput(kind="web", url="https://public.example/cat.png"), FakeAI())
    serve(monkeypatch, {"https://public.example/thin": FakeResponse(
        200, {"Content-Type": "text/html"}, b"<html><body><p>Hello</p></body></html>")})
    expect_error("unreadable", web.extract, ExtractInput(kind="web", url="https://public.example/thin"), FakeAI())


def test_plain_text_links_are_read(monkeypatch):
    body = ("Covariance measures how two variables move together. " * 6 + "\n\n") * 2
    serve(monkeypatch, {"https://public.example/notes.txt": FakeResponse(
        200, {"Content-Type": "text/plain; charset=utf-8"}, body.encode())})
    result = web.extract(ExtractInput(kind="web", url="https://public.example/notes.txt"), FakeAI())
    assert result.chunks[0].anchor.heading == "public.example" and "Covariance" in result.chunks[0].text
