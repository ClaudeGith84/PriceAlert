"""HTTP-Abruf mit Browser-Headern und einfachem Retry."""

from __future__ import annotations

import random
import time

import requests

from .parse import Blocked

USER_AGENTS = [
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/131.0.0.0 Safari/537.36"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) "
     "Version/18.1 Safari/605.1.15"),
]


MAX_BYTES = 8 * 1024 * 1024  # Produktseiten sind deutlich kleiner; schützt vor Endlos-Antworten


class FetchError(Exception):
    pass


def _read_limited(resp: requests.Response, limit: int | None = None) -> bytes:
    limit = limit or MAX_BYTES
    declared = resp.headers.get("Content-Length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise FetchError(f"Antwort zu groß ({declared} Bytes)")
    chunks, size = [], 0
    for chunk in resp.iter_content(64 * 1024):
        size += len(chunk)
        if size > limit:
            raise FetchError(f"Antwort zu groß (> {limit} Bytes)")
        chunks.append(chunk)
    return b"".join(chunks)


def _headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
        "Cache-Control": "no-cache",
    }


def fetch_html(url: str, timeout: int = 25, retries: int = 2) -> str:
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with requests.get(url, headers=_headers(), timeout=timeout,
                              allow_redirects=True, stream=True) as resp:
                if resp.status_code in (403, 429, 503):
                    raise Blocked(f"HTTP {resp.status_code}")
                if resp.status_code != 200:
                    raise FetchError(f"HTTP {resp.status_code}")
                raw = _read_limited(resp)
                try:
                    return raw.decode(resp.encoding or "utf-8", errors="replace")
                except LookupError:  # unbekannter Zeichensatz im Header
                    return raw.decode("utf-8", errors="replace")
        except (Blocked, FetchError, requests.RequestException) as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(3 * (attempt + 1) + random.random() * 2)
    assert last_err is not None
    raise last_err
