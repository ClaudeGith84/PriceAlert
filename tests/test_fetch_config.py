"""Abruf-Größenlimit und URL-Prüfung der Watchlist."""

import pytest

import pricewatch.fetch as fetch_mod
from pricewatch.config import load_watchlist


class FakeResponse:
    def __init__(self, body: bytes, status=200, headers=None, encoding="utf-8"):
        self.body, self.status_code = body, status
        self.headers = headers or {}
        self.encoding = encoding

    def iter_content(self, size):
        for i in range(0, len(self.body), size):
            yield self.body[i:i + size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch(monkeypatch, resp):
    monkeypatch.setattr(fetch_mod.requests, "get", lambda *a, **kw: resp)
    monkeypatch.setattr(fetch_mod.time, "sleep", lambda s: None)


def test_fetch_returns_decoded_text(monkeypatch):
    _patch(monkeypatch, FakeResponse("Preis: 199,– €".encode()))
    assert fetch_mod.fetch_html("https://shop.example/p") == "Preis: 199,– €"


def test_fetch_rejects_oversized_body(monkeypatch):
    _patch(monkeypatch, FakeResponse(b"x" * 100))
    monkeypatch.setattr(fetch_mod, "MAX_BYTES", 50)
    with pytest.raises(fetch_mod.FetchError, match="zu groß"):
        fetch_mod.fetch_html("https://shop.example/p", retries=0)


def test_fetch_rejects_oversized_content_length(monkeypatch):
    _patch(monkeypatch, FakeResponse(b"", headers={"Content-Length": str(10**10)}))
    with pytest.raises(fetch_mod.FetchError, match="zu groß"):
        fetch_mod.fetch_html("https://shop.example/p", retries=0)


def test_fetch_unknown_charset_falls_back_to_utf8(monkeypatch):
    _patch(monkeypatch, FakeResponse("ä".encode(), encoding="x-kaputt"))
    assert fetch_mod.fetch_html("https://shop.example/p") == "ä"


@pytest.mark.parametrize("url", ["httpfoo://x", "file:///etc/passwd", "https://", "ftp://shop.example/p"])
def test_watchlist_rejects_bad_urls(tmp_path, url):
    path = tmp_path / "w.yaml"
    path.write_text(f"items:\n  - name: X\n    sources:\n      - url: {url!r}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ungültige URL"):
        load_watchlist(path)
