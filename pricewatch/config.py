"""Watchlist laden und prüfen."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml


@dataclass
class Source:
    url: str
    selector: str | None = None
    label: str | None = None

    @property
    def name(self) -> str:
        if self.label:
            return self.label
        host = urlparse(self.url).netloc.lower()
        return host[4:] if host.startswith("www.") else host


@dataclass
class Item:
    id: str
    name: str
    sources: list[Source]
    target_price: float | None = None


@dataclass
class Settings:
    min_drop_pct: float = 1.0
    min_drop_eur: float = 0.0
    failure_alert_after: int = 6
    ntfy_priority_drop: int = 4
    ntfy_priority_target: int = 5


@dataclass
class Watchlist:
    settings: Settings
    items: list[Item] = field(default_factory=list)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def load_watchlist(path: str | Path) -> Watchlist:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    s = raw.get("settings") or {}
    settings = Settings(**{k: v for k, v in s.items() if k in Settings.__dataclass_fields__})

    items: list[Item] = []
    seen: set[str] = set()
    for entry in raw.get("items") or []:
        name = entry.get("name") or entry.get("id")
        if not name:
            raise ValueError("Jeder Artikel braucht 'name' oder 'id'")
        item_id = entry.get("id") or _slug(name)
        if item_id in seen:
            raise ValueError(f"Doppelte Artikel-ID: {item_id}")
        seen.add(item_id)
        sources = []
        for src in entry.get("sources") or []:
            if isinstance(src, str):
                src = {"url": src}
            parsed = urlparse(str(src.get("url", "")))
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(f"{item_id}: ungültige URL {src.get('url')!r}")
            sources.append(Source(url=src["url"], selector=src.get("selector"), label=src.get("label")))
        if not sources:
            raise ValueError(f"{item_id}: keine Quellen angegeben")
        target = entry.get("target_price")
        items.append(Item(id=item_id, name=name, sources=sources,
                          target_price=float(target) if target is not None else None))
    return Watchlist(settings=settings, items=items)
