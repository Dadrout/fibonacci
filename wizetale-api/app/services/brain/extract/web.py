"""Web page → readable text with section anchors. Fetches are SSRF-guarded."""
from __future__ import annotations

import codecs
import ipaddress
import logging
import re
import socket
import time
from typing import Optional, Union
from urllib.parse import urljoin, urlsplit

import requests
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import NewConnectionError

from app.domain.brain.pipeline import Anchor, Extraction, ExtractInput, ExtractionError
from app.services.brain.ai.client import BrainAI
from app.services.brain.extract.chunking import anchored, paragraphs

logger = logging.getLogger(__name__)
MAX_BYTES = 5 * 1024 * 1024
#: Wall-clock cap for one fetch (all redirects + body). `timeout=10` alone is per socket read,
#: so a server trickling bytes could otherwise hold the worker indefinitely.
FETCH_SECONDS = 30
ALLOWED_PORTS = {80, 443, 8080, 8443}
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/128.0 Safari/537.36 FibonacciBrain/1.0")
#: IPv6 ranges that carry an IPv4 address in their low 32 bits (NAT64 well-known prefix,
#: deprecated IPv4-compatible). Python reports e.g. 64:ff9b::7f00:1 as global.
EMBEDS_IPV4 = (ipaddress.ip_network("64:ff9b::/96"), ipaddress.ip_network("::/96"))
HEADING = re.compile(r"#{1,6}\s+(.*)")

Address = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


def _is_public(address: Address) -> bool:
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            return _is_public(address.ipv4_mapped)
        if any(address in network for network in EMBEDS_IPV4):
            if not _is_public(ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)):
                return False
    return address.is_global and not address.is_multicast and not address.is_reserved


def check_public_url(url: str) -> None:
    """Refuse URLs that resolve to non-public addresses (SSRF guard)."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as error:  # bad IPv6 literal, non-numeric or out-of-range port
        raise ExtractionError("fetch_failed", "Malformed link") from error
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ExtractionError("fetch_failed", "Only http(s) links can be read")
    if port is None:
        port = 443 if parts.scheme == "https" else 80
    if port not in ALLOWED_PORTS:
        raise ExtractionError("fetch_failed", "Port not allowed")
    try:
        infos = socket.getaddrinfo(parts.hostname, port, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError) as error:  # gaierror, or a hostname IDNA cannot encode
        raise ExtractionError("fetch_failed", "Host not found") from error
    if not infos:
        raise ExtractionError("fetch_failed", "Host not found")
    for info in infos:
        try:
            address = ipaddress.ip_address(info[4][0].split("%")[0])
        except ValueError as error:
            raise ExtractionError("fetch_failed", "Host not found") from error
        if not _is_public(address):
            raise ExtractionError("fetch_failed", "Link points to a private address")


# ---------------------------------------------------------------- connect-time re-check (DNS rebinding)

class _PublicPeerMixin:
    """Re-check the address actually connected to: DNS may answer differently than in check_public_url."""

    def _new_conn(self):
        sock = super()._new_conn()  # type: ignore[misc]
        try:
            peer = ipaddress.ip_address(sock.getpeername()[0].split("%")[0])
        except (OSError, ValueError):
            peer = None
        if peer is None or not _is_public(peer):
            sock.close()
            raise NewConnectionError(self, "Link points to a private address")
        return sock


class _PublicHTTPConnection(_PublicPeerMixin, HTTPConnection):
    pass


class _PublicHTTPSConnection(_PublicPeerMixin, HTTPSConnection):
    pass


class _PublicHTTPPool(HTTPConnectionPool):
    ConnectionCls = _PublicHTTPConnection


class _PublicHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _PublicHTTPSConnection


class _PublicOnlyAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {"http": _PublicHTTPPool, "https": _PublicHTTPSPool}


def _public_session() -> requests.Session:
    session = requests.Session()
    adapter = _PublicOnlyAdapter()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# ---------------------------------------------------------------- fetch

def fetch(url: str, session: Optional[requests.Session] = None) -> tuple[bytes, str, str]:
    """GET with manual, re-checked redirects and a size cap. Returns (body, content_type, final_url)."""
    owned = session is None
    session = session or _public_session()
    deadline = time.monotonic() + FETCH_SECONDS
    try:
        for _ in range(6):
            check_public_url(url)
            if time.monotonic() > deadline:
                raise ExtractionError("fetch_failed", "Page took too long to load")
            try:
                response = session.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ru,kk;q=0.9,en;q=0.8"},
                                       timeout=10, allow_redirects=False, stream=True)
            except requests.RequestException as error:
                raise ExtractionError("fetch_failed", "Page could not be fetched") from error
            try:
                if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        raise ExtractionError("fetch_failed", "Redirect without a location")
                    url = urljoin(url, location)
                    continue
                if response.status_code >= 400:
                    raise ExtractionError("fetch_failed", f"HTTP {response.status_code}")
                declared = (response.headers.get("Content-Length") or "").strip()
                if declared.isdigit() and int(declared) > MAX_BYTES:
                    raise ExtractionError("too_large", "Page is larger than 5 MB")
                body = bytearray()
                try:
                    for piece in response.iter_content(65536):
                        body.extend(piece)
                        if len(body) > MAX_BYTES:
                            raise ExtractionError("too_large", "Page is larger than 5 MB")
                        if time.monotonic() > deadline:
                            raise ExtractionError("fetch_failed", "Page took too long to load")
                except requests.RequestException as error:  # reset, read timeout, bad chunking/encoding
                    raise ExtractionError("fetch_failed", "Page could not be fetched") from error
                return bytes(body), response.headers.get("Content-Type", ""), url
            finally:
                response.close()
        raise ExtractionError("fetch_failed", "Too many redirects")
    finally:
        if owned:
            session.close()


# ---------------------------------------------------------------- extract

def _charset(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    try:
        return codecs.lookup(name.strip().strip("\"'")).name
    except LookupError:
        return None


def _decode(body: bytes, content_type: str) -> str:
    """Decode with the declared charset (header, then <meta>), else UTF-8, else a detected one.

    Russian and Kazakh sites still serve windows-1251/KOI8-R; decoding those as UTF-8 garbles every word.
    """
    if body.startswith(codecs.BOM_UTF8):
        return body[len(codecs.BOM_UTF8):].decode("utf-8", errors="replace")
    declared = re.search(r"charset\s*=\s*[\"']?([\w.:-]+)", content_type, re.I)
    meta = re.search(rb"<meta[^>]+charset\s*=\s*[\"']?([\w.:-]+)", body[:4096], re.I)
    for name in (declared.group(1) if declared else None, meta.group(1).decode("ascii", "ignore") if meta else None, "utf-8"):
        charset = _charset(name)
        if charset:
            try:
                return body.decode(charset)
            except UnicodeDecodeError:
                continue
    try:
        from trafilatura.utils import detect_encoding

        for guess in detect_encoding(body):
            try:
                return body.decode(guess)
            except (LookupError, UnicodeDecodeError):
                continue
    except Exception:  # noqa: BLE001 — detection is best effort
        pass
    return body.decode("utf-8", errors="replace")


def extract(inp: ExtractInput, ai: BrainAI) -> Extraction:
    body, content_type, final_url = fetch(inp.url or "")
    mime = content_type.split(";")[0].strip().lower()
    if "pdf" in mime or body[:4] == b"%PDF":
        from app.services.brain.extract import pdf

        return pdf.extract(ExtractInput(kind="pdf", data=body, mime_type="application/pdf", url=final_url), ai)
    if mime.split("/")[0] in ("image", "audio", "video", "font"):
        raise ExtractionError("unsupported_type", f"Link is not a page ({mime})")
    host = urlsplit(final_url).hostname
    html = _decode(body, content_type)
    if mime == "text/plain":
        title, lines = None, paragraphs(html)
    else:
        import trafilatura

        text = trafilatura.extract(html, url=final_url, include_comments=False, include_tables=True,
                                   output_format="markdown", favor_recall=True) or ""
        metadata = trafilatura.extract_metadata(html, default_url=final_url)
        title = (metadata.title or "").strip()[:300] if metadata else ""
        title = title or None
        lines = text.splitlines()
    chunks, heading, buffer = [], (title or host or "Page")[:200], []
    for line in lines:
        match = HEADING.match(line)
        if match:
            if buffer:
                chunks.extend(anchored(Anchor(kind="section", heading=heading), "\n".join(buffer)))
            heading, buffer = match.group(1).strip(" #")[:200] or heading, []
        elif line.strip():
            buffer.append(line.strip())
    if buffer:
        chunks.extend(anchored(Anchor(kind="section", heading=heading), "\n".join(buffer)))
    if sum(len(c.text) for c in chunks) < 200:
        raise ExtractionError("unreadable", "Too little readable text on the page")
    return Extraction(title=title, chunks=chunks[:600], metadata={"final_host": host})
