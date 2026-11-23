"""Einstiegspunkt:  python -m pricewatch [--dry-run] [--test-notify]"""

from __future__ import annotations

import argparse
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import notify
from .alerts import Alert, eur, evaluate
from .config import load_watchlist
from .fetch import fetch_html
from .parse import Blocked, extract_price
from .store import Observation, Store

BERLIN = ZoneInfo("Europe/Berlin")


def _unique_names(sources) -> list[str]:
    names, seen = [], {}
    for src in sources:
        n = src.name
        seen[n] = seen.get(n, 0) + 1
        names.append(n if seen[n] == 1 else f"{n}#{seen[n]}")
    return names


def check_source(url: str, selector: str | None) -> tuple[float | None, str, str]:
    try:
        html = fetch_html(url)
        return extract_price(html, url, selector), "ok", ""
    except Blocked as exc:
        return None, "blocked", str(exc)
    except Exception as exc:  # noqa: BLE001 – ein kaputter Shop soll den Lauf nicht stoppen
        return None, "error", f"{type(exc).__name__}: {exc}"


def write_summary(path: Path, watchlist, state: dict, store: Store, now: datetime) -> None:
    lines = [
        "# Preisübersicht",
        "",
        f"Stand: {now.astimezone(BERLIN):%d.%m.%Y %H:%M} Uhr",
        "",
        "| Artikel | Aktuell | Shop | Tiefster | Zielpreis |",
        "|---|---|---|---|---|",
    ]
    for item in watchlist.items:
        st = state["items"].get(item.id, {})
        prices = [p for _, p, _ in store.ok_prices(item.id)]
        best = st.get("best")
        lines.append(
            f"| {item.name} | {eur(best) if best else '–'} | {st.get('best_source', '–')} | "
            f"{eur(min(prices)) if prices else '–'} | "
            f"{eur(item.target_price) if item.target_price else '–'} |"
        )
    lines += ["", "Details je Shop:", ""]
    for item in watchlist.items:
        st = state["items"].get(item.id, {})
        lines.append(f"**{item.name}**")
        for name, info in sorted(st.get("sources", {}).items()):
            ts = datetime.fromisoformat(info["last_ok"]).astimezone(BERLIN)
            lines.append(f"- {name}: {eur(info['last_price'])} (zuletzt gelesen {ts:%d.%m. %H:%M})")
        if st.get("failures"):
            lines.append(f"- ⚠️ {st['failures']} Läufe in Folge ohne Preis")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args) -> int:
    root = Path(args.root)
    watchlist = load_watchlist(root / args.watchlist)
    store = Store(root / args.data)
    state = store.load_state()
    state.setdefault("items", {})
    now = datetime.now(timezone.utc).replace(microsecond=0)
    now_iso = now.isoformat()

    all_alerts: list[Alert] = []
    observations: list[Observation] = []

    for item in watchlist.items:
        if args.only and item.id != args.only:
            continue
        names = _unique_names(item.sources)
        results, urls = {}, {}
        for name, src in zip(names, item.sources):
            price, status, err = check_source(src.url, src.selector)
            results[name], urls[name] = price, src.url
            observations.append(Observation(now_iso, item.id, name, price, status, err))
            shown = eur(price) if price else f"{status}: {err}"
            print(f"{item.id:<24} {name:<28} {shown}")
            time.sleep(1 + random.random() * 2)

        history = store.ok_prices(item.id)
        all_time_min = min((p for _, p, _ in history), default=None)
        observed_days = (now - history[0][0]).days if history else 0

        alerts, state["items"][item.id] = evaluate(
            item_name=item.name,
            target_price=item.target_price,
            results=results,
            urls=urls,
            state=state["items"].get(item.id, {}),
            all_time_min=all_time_min,
            observed_days=observed_days,
            settings=watchlist.settings,
            now_iso=now_iso,
        )
        all_alerts.extend(alerts)

    if args.dry_run:
        for a in all_alerts:
            notify.send(a, dry_run=True)
        print("dry-run: nichts gespeichert")
        return 0

    store.append(observations)
    store.save_state(state)
    write_summary(root / args.data / "summary.md", watchlist, state, store, now)
    for a in all_alerts:
        notify.send(a)
    print(f"{len(observations)} Abrufe, {len(all_alerts)} Benachrichtigungen")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pricewatch", description="Black-Friday-Preisüberwachung")
    ap.add_argument("--root", default=".", help="Projektordner")
    ap.add_argument("--watchlist", default="watchlist.yaml")
    ap.add_argument("--data", default="data")
    ap.add_argument("--only", help="nur diesen Artikel (id) prüfen")
    ap.add_argument("--dry-run", action="store_true", help="nichts speichern, nichts senden")
    ap.add_argument("--test-notify", action="store_true", help="nur eine Testnachricht senden")
    ap.add_argument("--probe", metavar="URL", help="eine Seite testen: Preis lesen und HTML in probe.html sichern")
    ap.add_argument("--selector", help="CSS-Selektor für --probe")
    args = ap.parse_args(argv)

    if args.probe:
        try:
            html = fetch_html(args.probe)
        except Exception as exc:  # noqa: BLE001
            print(f"Abruf fehlgeschlagen: {type(exc).__name__}: {exc}")
            return 1
        Path("probe.html").write_text(html, encoding="utf-8")
        price, status, err = None, "ok", ""
        try:
            price = extract_price(html, args.probe, args.selector)
        except Exception as exc:  # noqa: BLE001
            status, err = type(exc).__name__, str(exc)
        print(f"Preis: {eur(price)}" if price else f"Kein Preis ({status}: {err}) – HTML liegt in probe.html")
        return 0 if price else 1

    if args.test_notify:
        ok = notify.send(Alert(title="✅ Preiswächter: Test",
                               message="Wenn du das liest, kommen Benachrichtigungen an.",
                               tags=["white_check_mark"]))
        return 0 if ok else 1
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
