"""Ende-zu-Ende-Lauf mit simulierten Shopseiten."""

import json

import pricewatch.__main__ as main_mod

WATCHLIST = """
settings:
  min_drop_pct: 1
items:
  - name: Testartikel
    id: test
    sources:
      - url: https://shop-a.example/p
      - url: https://shop-b.example/p
"""


def make_page(price):
    return ('<html><body><script type="application/ld+json">'
            f'{{"@type":"Product","offers":{{"@type":"Offer","price":"{price}"}}}}'
            "</script></body></html>")


def test_end_to_end(tmp_path, monkeypatch, capsys):
    (tmp_path / "watchlist.yaml").write_text(WATCHLIST, encoding="utf-8")
    prices = {"https://shop-a.example/p": 229.0, "https://shop-b.example/p": 219.0}
    monkeypatch.setattr(main_mod, "fetch_html", lambda url: make_page(prices[url]))
    monkeypatch.setattr(main_mod.time, "sleep", lambda s: None)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)

    assert main_mod.main(["--root", str(tmp_path)]) == 0
    assert "Überwachung gestartet" in capsys.readouterr().out

    prices["https://shop-a.example/p"] = 199.0
    assert main_mod.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Preis gesunken" in out and "199,00 € statt 219,00 €" in out

    state = json.loads((tmp_path / "data/state.json").read_text())
    assert state["items"]["test"]["ref"] == 199.0
    csv_lines = (tmp_path / "data/prices.csv").read_text().strip().splitlines()
    assert len(csv_lines) == 1 + 4
    summary = (tmp_path / "data/summary.md").read_text()
    assert "Testartikel" in summary and "199,00 €" in summary


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    (tmp_path / "watchlist.yaml").write_text(WATCHLIST, encoding="utf-8")
    monkeypatch.setattr(main_mod, "fetch_html", lambda url: make_page(100))
    monkeypatch.setattr(main_mod.time, "sleep", lambda s: None)
    assert main_mod.main(["--root", str(tmp_path), "--dry-run"]) == 0
    assert not (tmp_path / "data").exists()


def test_broken_shop_does_not_stop_run(tmp_path, monkeypatch):
    (tmp_path / "watchlist.yaml").write_text(WATCHLIST, encoding="utf-8")

    def fake(url):
        if "shop-a" in url:
            raise RuntimeError("Timeout")
        return make_page(150)

    monkeypatch.setattr(main_mod, "fetch_html", fake)
    monkeypatch.setattr(main_mod.time, "sleep", lambda s: None)
    assert main_mod.main(["--root", str(tmp_path)]) == 0
    rows = (tmp_path / "data/prices.csv").read_text()
    assert "error" in rows and "150.00" in rows
