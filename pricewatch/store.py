"""Preisverlauf (CSV) und Zustand (JSON)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

FIELDS = ["timestamp", "item_id", "source", "price", "status", "error"]


@dataclass
class Observation:
    timestamp: str
    item_id: str
    source: str
    price: float | None
    status: str  # ok | blocked | error
    error: str = ""


class Store:
    def __init__(self, data_dir: str | Path):
        self.dir = Path(data_dir)
        self.csv_path = self.dir / "prices.csv"
        self.state_path = self.dir / "state.json"
        self._history: list[dict] | None = None

    # -- Verlauf --
    def history(self) -> list[dict]:
        if self._history is None:
            if self.csv_path.exists():
                with self.csv_path.open(newline="", encoding="utf-8") as fh:
                    self._history = list(csv.DictReader(fh))
            else:
                self._history = []
        return self._history

    def ok_prices(self, item_id: str) -> list[tuple[datetime, float, str]]:
        out = []
        for row in self.history():
            if row["item_id"] == item_id and row["status"] == "ok" and row["price"]:
                out.append((datetime.fromisoformat(row["timestamp"]), float(row["price"]), row["source"]))
        return out

    def append(self, observations: list[Observation]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        new_file = not self.csv_path.exists()
        with self.csv_path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS)
            if new_file:
                writer.writeheader()
            for o in observations:
                row = {
                    "timestamp": o.timestamp,
                    "item_id": o.item_id,
                    "source": o.source,
                    "price": f"{o.price:.2f}" if o.price is not None else "",
                    "status": o.status,
                    "error": o.error[:200],
                }
                writer.writerow(row)
                self.history().append(row)

    # -- Zustand --
    def load_state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"items": {}}

    def save_state(self, state: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
