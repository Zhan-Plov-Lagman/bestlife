import copy
from datetime import timedelta

import pytest
from sqlalchemy import delete
from test_pipeline import enter, sample

from app.clock import ReplayClock
from app.database import records
from app.domain import D, now
from app.engine import TradingEngine


def recover(engine):
    clock = ReplayClock(now())
    return TradingEngine(engine.store, clock), clock


def observation(clock, i=100, seconds=2, **updates):
    clock.advance(clock.now() + timedelta(seconds=seconds))
    return sample(i, "1.04").model_copy(update={"event_time": clock.now(), **updates})


def test_restart_buy_cancelled(engine):
    engine.control("start")
    for i in range(4):
        engine.process(sample(i, str(1 + i * 0.01)))
    restored, clock = recover(engine)
    assert not restored.state["pending"]
    restored.process(observation(clock))
    assert not restored.state["positions"]


def test_restart_sell_and_kill_exit(engine):
    enter(engine)
    engine.control("close-all")
    order_id = next(iter(engine.state["pending"].values()))["id"]
    restored, clock = recover(engine)
    assert not restored.state["reconciliation_errors"]
    assert next(iter(restored.state["pending"].values()))["id"] == order_id
    restored.control("kill")
    restored.process(observation(clock))
    assert not restored.state["positions"]
    assert restored.state["closed"] == 1
    again = TradingEngine(engine.store, clock)
    assert again.state["closed"] == 1 and not again.state["reconciliation_errors"]


def test_expired_exit_renews_intent_after_fresh_observation(engine):
    enter(engine)
    engine.control("close-all")
    restored, clock = recover(engine)
    restored.process(observation(clock, seconds=60))
    assert restored.state["positions"] and restored.state["pending"]
    restored.process(observation(clock, i=101))
    assert not restored.state["positions"]


def test_restart_stale_quote_does_not_fill(engine):
    enter(engine)
    engine.control("close-all")
    restored, clock = recover(engine)
    stale = sample(99).model_copy(update={"event_time": clock.now() - timedelta(seconds=1)})
    restored.process(stale)
    assert restored.state["positions"] and restored.state["pending"]
    with pytest.raises(ValueError):
        restored.control("start")
    restored.process(observation(clock))
    assert not restored.state["positions"]


def test_duplicate_fill_no_second_settlement(engine):
    enter(engine)
    before = copy.deepcopy(engine.state)
    fill = engine.store.recent("paper_fills", engine.state["session_id"])[0]
    with engine.store.engine.begin() as conn:
        engine.fill(conn, sample(10), {"id": fill["id"], "side": "BUY"})
    assert engine.state == before


def test_incomplete_ledger_cannot_clear_halt(engine):
    enter(engine)
    with engine.store.engine.begin() as conn:
        conn.execute(delete(records["paper_fills"]))
    restored, _ = recover(engine)
    assert restored.state["fault"] == "LEDGER_RECONCILIATION_FAILED"
    with pytest.raises(ValueError, match="RECONCILIATION"):
        restored.control("clear-halt")


def test_interrupted_close_all_rolls_back(engine, monkeypatch):
    enter(engine)
    original = engine.store.save

    def fail(*args):
        raise RuntimeError("interrupted")

    monkeypatch.setattr(engine.store, "save", fail)
    with pytest.raises(RuntimeError):
        engine.control("close-all")
    monkeypatch.setattr(engine.store, "save", original)
    restored, _ = recover(engine)
    assert restored.state["positions"] and not restored.state["pending"]
    assert not restored.state["reconciliation_errors"]


def test_liquidity_blocks_exit_but_preserves_intent(engine):
    enter(engine)
    engine.control("close-all")
    restored, clock = recover(engine)
    restored.process(observation(clock, liquidity=D("1")))
    assert next(iter(restored.state["pending"].values()))["status"] == "BLOCKED"
    assert restored.state["positions"]
    restored.process(observation(clock, i=101))
    assert not restored.state["positions"]


def test_expired_exit_does_not_renew_on_invalid_data(engine):
    enter(engine)
    engine.control("close-all")
    restored, clock = recover(engine)
    original = restored.state["pending"]["DEMO-TEST"]["id"]
    restored.process(observation(clock, seconds=60, data_quality_status="INVALID"))
    assert restored.state["pending"]["DEMO-TEST"]["id"] == original
    assert restored.state["pending"]["DEMO-TEST"]["status"] == "BLOCKED"


def test_missing_latest_snapshot_halts_recovery(engine):
    enter(engine)
    with engine.store.engine.begin() as conn:
        conn.execute(delete(records["portfolio_snapshots"]))
    restored, _ = recover(engine)
    assert "LEDGER_SNAPSHOT_MISSING" in restored.state["reconciliation_errors"]


@pytest.mark.parametrize("unit", [D("1e-18"), D("1e18")])
def test_extreme_prices_preserve_decimal_ledger(engine, unit):
    engine.control("start")
    for i in range(5):
        engine.process(sample(i, str(unit * (1 + D(i) / 100))))
    assert len(engine.state["positions"]) == 1
    engine.control("close-all")
    restored, clock = recover(engine)
    restored.process(observation(clock, price=unit * D("1.04")))
    assert not restored.state["positions"]
    assert D(restored.state["cash"]) >= 0
    assert D(restored.state["cash"]) - D("70") == D(restored.state["realized"])
    assert not TradingEngine(engine.store, clock).state["reconciliation_errors"]
