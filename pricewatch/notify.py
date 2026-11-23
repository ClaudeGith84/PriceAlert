"""Benachrichtigung per ntfy (https://ntfy.sh)."""

from __future__ import annotations

import os

import requests

from .alerts import Alert


def send(alert: Alert, *, dry_run: bool = False) -> bool:
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    token = os.environ.get("NTFY_TOKEN", "").strip()

    if dry_run or not topic:
        reason = "dry-run" if dry_run else "NTFY_TOPIC nicht gesetzt"
        print(f"[notify:{reason}] {alert.title}\n  " + alert.message.replace("\n", "\n  "))
        return False

    payload = {
        "topic": topic,
        "title": alert.title,
        "message": alert.message,
        "priority": alert.priority,
        "tags": alert.tags,
    }
    if alert.click:
        payload["click"] = alert.click
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        resp = requests.post(server, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        print(f"[notify] Fehler beim Senden: {exc}")
        return False
