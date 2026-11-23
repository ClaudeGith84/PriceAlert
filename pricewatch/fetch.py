"""HTTP-Abruf mit Browser-Headern und einfachem Retry."""

from __future__ import annotations

import random
import time

import requests

from .parse import Blocked

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/18.1 Safari/605.1.15",
]


class FetchError(Exception):
    pass


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
            resp = requests.get(url, headers=_headers(), timeout=timeout, allow_redirects=True)
            if resp.status_code in (403, 429, 503):
                raise Blocked(f"HTTP {resp.status_code}")
            if resp.status_code != 200:
                raise FetchError(f"HTTP {resp.status_code}")
            resp.encoding = resp.encoding or resp.apparent_encoding
            return resp.text
        except (Blocked, FetchError, requests.RequestException) as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(3 * (attempt + 1) + random.random() * 2)
    assert last_err is not None
    raise last_err
