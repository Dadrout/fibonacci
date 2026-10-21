"""Web page → readable text with section anchors. Fetches are SSRF-guarded."""
from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Optional
from urllib.parse import urljoin, urlsplit

import requests

from app.domain.brain.pipeline import Anchor, Extraction, ExtractInput, ExtractionError
from app.services.brain.ai.client import BrainAI
from app.services.brain.extract.chunking import anchored

logger = logging.getLogger(__name__)
MAX_BYTES = 5 * 1024 * 1024
ALLOWED_PORTS = {80, 443, 8080, 8443}
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/128.0 Safari/537.36 FibonacciBrain/1.0")


def check_public_url(url: str) -> None:
    """Refuse URLs that resolve to non-public addresses (SSRF guard)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ExtractionError("fetch_failed", "Only http(s) links can be read")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if port not in ALLOWED_PORTS:
        raise ExtractionError("fetch_failed", "Port not allowed")
    try:
        infos = socket.getaddrinfo(parts.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as error:
        raise ExtractionError("fetch_failed", "Host not found") from error
    for info in infos:
        address = ipaddress.ip_address(info[4][0].split("%")[0])
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        if not address.is_global or address.is_multicast or address.is_reserved:
            raise ExtractionError("fetch_failed", "Link points to a private address")


def fetch(url: str, session: Optional[requests.Session] = None) -> tuple[bytes, str, str]:
    """GET with manual, re-checked redirects and a size cap. Returns (body, content_type, final_url)."""
    session = session or requests.Session()
    for _ in range(6):
        check_public_url(url)
        try:
            response = session.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ru,kk;q=0.9,en;q=0.8"},
                                   timeout=10, allow_redirects=False, stream=True)
        except requests.RequestException as error:
            raise ExtractionError("fetch_failed", "Page could not be fetched") from error
        if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            response.close()
            if not location:
                break
            url = urljoin(url, location)
            continue
        if response.status_code >= 400:
            response.close()
            raise ExtractionError("fetch_failed", f"HTTP {response.status_code}")
        body = bytearray()
        for piece in response.iter_content(65536):
            body.extend(piece)
            if len(body) > MAX_BYTES:
                response.close()
                raise ExtractionError("too_large", "Page is larger than 5 MB")
        return bytes(body), response.headers.get("Content-Type", ""), url
    raise ExtractionError("fetch_failed", "Too many redirects")


def extract(inp: ExtractInput, ai: BrainAI) -> Extraction:
    body, content_type, final_url = fetch(inp.url or "")
    if "pdf" in content_type.lower() or body[:4] == b"%PDF":
        from app.services.brain.extract import pdf

        return pdf.extract(ExtractInput(kind="pdf", data=body, mime_type="application/pdf", url=final_url), ai)
    import trafilatura

    html = body.decode("utf-8", errors="replace")
    text = trafilatura.extract(html, url=final_url, include_comments=False, include_tables=True,
                               output_format="markdown", favor_recall=True) or ""
    metadata = trafilatura.extract_metadata(html, default_url=final_url)
    title = (metadata.title if metadata and metadata.title else None)
    chunks, heading, buffer = [], (title or urlsplit(final_url).hostname or "Page")[:200], []
    for line in text.splitlines():
        if line.startswith("#"):
            if buffer:
                chunks.extend(anchored(Anchor(kind="section", heading=heading), "\n".join(buffer)))
            heading, buffer = line.lstrip("#").strip()[:200] or heading, []
        elif line.strip():
            buffer.append(line.strip())
    if buffer:
        chunks.extend(anchored(Anchor(kind="section", heading=heading), "\n".join(buffer)))
    if sum(len(c.text) for c in chunks) < 200:
        raise ExtractionError("unreadable", "Too little readable text on the page")
    return Extraction(title=title, chunks=chunks[:600], metadata={"final_host": urlsplit(final_url).hostname})
