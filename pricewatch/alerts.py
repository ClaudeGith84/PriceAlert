"""Alarm-Logik – reine Funktionen, ohne Netzwerk/Dateien (gut testbar).

Referenzpreis-Prinzip:
- Beim ersten erfolgreichen Lauf wird der beste Preis zur Referenz.
- Fällt der beste Preis um mindestens die Schwelle unter die Referenz,
  gibt es einen Alarm und der neue Preis wird zur Referenz.
- Steigt der Preis, wird die Referenz nur angehoben, wenn alle Quellen
  erfolgreich abgefragt wurden. So erzeugt eine kurz ausgefallene,
  günstigere Quelle beim Wiederauftauchen keinen Fehlalarm.
- Kleine Senkungen summieren sich: die Referenz bleibt stehen, bis die
  Schwelle insgesamt erreicht ist.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Alert:
    title: str
    message: str
    priority: int = 3
    tags: list[str] = field(default_factory=list)
    click: str | None = None
    kind: str = "drop"  # drop | target | start | failure


def eur(value: float) -> str:
    s = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def _passes_threshold(ref: float, new: float, min_pct: float, min_eur: float) -> bool:
    drop = ref - new
    if drop <= 0:
        return False
    return drop + 1e-9 >= min_eur and (drop / ref * 100) + 1e-9 >= min_pct


def evaluate(
    *,
    item_name: str,
    target_price: float | None,
    results: dict[str, float | None],
    urls: dict[str, str],
    state: dict,
    all_time_min: float | None,
    observed_days: int,
    settings,
    now_iso: str,
) -> tuple[list[Alert], dict]:
    """Bewertet einen Lauf für einen Artikel.

    results: Quelle -> Preis (None = Abruf/Auslese fehlgeschlagen)
    state:   bisheriger Zustand dieses Artikels (wird nicht verändert)
    """
    st = {**state, "sources": dict(state.get("sources", {}))}
    alerts: list[Alert] = []
    ok = {s: p for s, p in results.items() if p is not None}

    # --- komplett fehlgeschlagen ---
    if not ok:
        st["failures"] = st.get("failures", 0) + 1
        if st["failures"] >= settings.failure_alert_after and not st.get("failure_alert_sent"):
            st["failure_alert_sent"] = True
            alerts.append(Alert(
                title=f"⚠️ {item_name}: keine Preise",
                message=(f"Seit {st['failures']} Läufen konnte kein Preis gelesen werden "
                         f"({', '.join(results)}). Vermutlich blockiert der Shop den Abruf "
                         f"oder die Seite hat sich geändert."),
                priority=3, tags=["warning"], kind="failure",
            ))
        return alerts, st

    st["failures"] = 0
    st["failure_alert_sent"] = False
    all_ok = len(ok) == len(results)

    for s, p in ok.items():
        st["sources"][s] = {"last_price": p, "last_ok": now_iso}

    best_src = min(ok, key=ok.get)
    best = ok[best_src]
    st["best"] = best
    st["best_source"] = best_src
    st["last_ok"] = now_iso
    click = urls.get(best_src)
    ref = st.get("ref")

    # --- erster Lauf: Referenz setzen ---
    if ref is None:
        st["ref"] = best
        st["started"] = now_iso
        st["target_hit"] = target_price is not None and best <= target_price
        alerts.append(Alert(
            title=f"👀 Überwachung gestartet: {item_name}",
            message=f"Aktuell bester Preis: {eur(best)} bei {best_src}.",
            priority=2, tags=["eyes"], click=click, kind="start",
        ))
        return alerts, st

    new_low = all_time_min is not None and best < all_time_min - 1e-9
    target_crossed = (target_price is not None and best <= target_price
                      and not st.get("target_hit"))
    dropped = _passes_threshold(ref, best, settings.min_drop_pct, settings.min_drop_eur)

    if dropped or target_crossed:
        lines = []
        if best < ref:
            pct = (ref - best) / ref * 100
            pct_txt = f"{pct:.1f}".replace(".", ",")
            lines.append(f"{eur(best)} statt {eur(ref)} (−{pct_txt} %) bei {best_src}")
        else:
            lines.append(f"{eur(best)} bei {best_src}")
        if target_price is not None:
            lines.append(f"Zielpreis: {eur(target_price)}" + (" ✅" if best <= target_price else ""))
        if new_low:
            lines.append(f"Neuer Tiefstpreis seit Beobachtungsbeginn ({observed_days} Tage).")
        elif all_time_min is not None:
            lines.append(f"Tiefster bisher: {eur(all_time_min)}")
        others = sorted((p, s) for s, p in ok.items() if s != best_src)
        if others:
            lines.append("Andere: " + ", ".join(f"{s} {eur(p)}" for p, s in others[:3]))

        if target_crossed:
            title = f"🎯 Zielpreis erreicht: {item_name}"
            prio, tags, kind = settings.ntfy_priority_target, ["dart"], "target"
        else:
            title = f"📉 Preis gesunken: {item_name}"
            prio, tags, kind = settings.ntfy_priority_drop, ["chart_with_downwards_trend"], "drop"
        alerts.append(Alert(title=title, message="\n".join(lines), priority=prio,
                            tags=tags, click=click, kind=kind))
        if dropped:
            st["ref"] = best

    if best > ref and all_ok:
        st["ref"] = best

    if target_price is not None:
        if best <= target_price:
            st["target_hit"] = True
        elif all_ok:
            st["target_hit"] = False

    return alerts, st
