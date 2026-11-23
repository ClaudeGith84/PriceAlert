from pricewatch.alerts import eur, evaluate
from pricewatch.config import Settings


def run(results, state, *, target=None, all_time_min=None, settings=None):
    return evaluate(
        item_name="AirPods Pro 3",
        target_price=target,
        results=results,
        urls={k: f"https://{k}/x" for k in results},
        state=state,
        all_time_min=all_time_min,
        observed_days=2,
        settings=settings or Settings(),
        now_iso="2026-11-20T10:00:00+00:00",
    )


def test_eur_format():
    assert eur(1299.5) == "1.299,50 €"


def test_first_run_sets_reference():
    alerts, st = run({"a": 229.0, "b": 219.0}, {})
    assert [a.kind for a in alerts] == ["start"]
    assert st["ref"] == 219.0 and st["best_source"] == "b"


def test_drop_alert_and_new_reference():
    _, st = run({"a": 229.0}, {})
    alerts, st = run({"a": 209.0}, st, all_time_min=229.0)
    assert [a.kind for a in alerts] == ["drop"]
    assert "209,00 € statt 229,00 €" in alerts[0].message
    assert "Neuer Tiefstpreis" in alerts[0].message
    assert st["ref"] == 209.0


def test_small_drops_accumulate_until_threshold():
    _, st = run({"a": 200.0}, {})
    alerts, st = run({"a": 199.0}, st)  # 0,5 %
    assert alerts == [] and st["ref"] == 200.0
    alerts, st = run({"a": 197.9}, st)  # 1,05 % gegenüber Referenz
    assert [a.kind for a in alerts] == ["drop"]


def test_zero_threshold_alerts_every_drop():
    s = Settings(min_drop_pct=0)
    _, st = run({"a": 200.0}, {}, settings=s)
    alerts, _ = run({"a": 199.99}, st, settings=s)
    assert len(alerts) == 1


def test_rise_then_drop_alerts_again():
    _, st = run({"a": 200.0}, {})
    alerts, st = run({"a": 230.0}, st)
    assert alerts == [] and st["ref"] == 230.0
    alerts, st = run({"a": 215.0}, st)
    assert [a.kind for a in alerts] == ["drop"]


def test_failed_cheap_source_coming_back_is_no_false_alarm():
    _, st = run({"a": 229.0, "b": 209.0}, {})
    alerts, st = run({"a": 229.0, "b": None}, st)  # b fällt aus
    assert alerts == [] and st["ref"] == 209.0  # Referenz nicht angehoben
    alerts, st = run({"a": 229.0, "b": 209.0}, st)  # b wieder da
    assert alerts == []


def test_target_alert_only_once():
    _, st = run({"a": 230.0}, {}, target=200.0)
    alerts, st = run({"a": 199.0}, st, target=200.0)
    assert [a.kind for a in alerts] == ["target"]
    assert alerts[0].priority == 5
    alerts, st = run({"a": 199.0}, st, target=200.0)
    assert alerts == []


def test_failure_alert_once_after_n_runs():
    _, st = run({"a": 200.0}, {})
    kinds = []
    for _ in range(8):
        alerts, st = run({"a": None}, st)
        kinds += [a.kind for a in alerts]
    assert kinds == ["failure"]
    _, st = run({"a": 200.0}, st)
    assert st["failures"] == 0 and st["failure_alert_sent"] is False


def test_state_not_mutated():
    state = {"ref": 200.0, "sources": {"a": {"last_price": 200.0, "last_ok": "x"}}}
    run({"a": 150.0}, state)
    assert state["ref"] == 200.0 and state["sources"]["a"]["last_price"] == 200.0
