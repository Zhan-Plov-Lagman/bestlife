from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.analytics import FeatureEngine, council, dispatch, regime
from app.database import Store, metadata
from app.domain import D, MarketSnapshot, Settings, now
from app.engine import TradingEngine
from app.risk import allocate, assess


@pytest.fixture
def engine(tmp_path):
    store = Store("sqlite:///" + str(tmp_path / "test.db"))
    metadata.create_all(store.engine)
    return TradingEngine(store)


def sample(i=0, price="1", **kwargs):
    return MarketSnapshot(
        event_id=f"test-{i}",
        event_time=now() - timedelta(seconds=25 - i),
        provider="DEMO",
        token_mint="DEMO-TEST",
        symbol="TEST",
        pool_address="POOL",
        price=D(price),
        liquidity=D("100000"),
        volume=D(10000 + i * 1000),
        buys=80,
        sells=20,
        token_safety_known=True,
        suspicious=False,
        execution_model="SYNTHETIC_CONSERVATIVE",
        **kwargs,
    )


def enter(engine):
    engine.control("start")
    for i in range(5):
        engine.process(sample(i, str(1 + i * 0.01)))
    assert len(engine.state["positions"]) == 1


def test_complete_cycle_money_and_restart(engine):
    enter(engine)
    p = next(iter(engine.state["positions"].values()))
    assert D(engine.state["cash"]) == D("70") - D(p["cost_basis"])
    assert D(p["entry_price"]) > D("1.04")
    engine.control("close-all")
    # Manual exits use wall clock; simulated next event must be later.
    s = sample(7, "1.15").model_copy(update={"event_time": now() + timedelta(seconds=1.1)})
    engine.control("stop")
    engine.control("close-all")
    engine.process(s)
    assert not engine.state["positions"]
    assert D(engine.state["realized"]) == D(engine.state["cash"]) - D("70")
    assert D(engine.state["fees"]) > 0
    restored = TradingEngine(engine.store)
    assert restored.state["cash"] == engine.state["cash"]
    assert not restored.state["running"]
    assert len(restored.store.recent("paper_fills", restored.state["session_id"])) == 2


def test_idempotency(engine):
    s = sample()
    assert engine.process(s)
    assert not engine.process(s)
    assert engine.state["decision_count"] == 1


def test_kill_cancels_pending_and_blocks(engine):
    engine.control("start")
    for i in range(4):
        engine.process(sample(i, str(1 + i * 0.01)))
    assert engine.state["pending"]
    engine.control("kill")
    engine.process(sample(4, "1.04"))
    assert not engine.state["positions"]
    assert not engine.state["pending"]
    with pytest.raises(ValueError):
        engine.control("start")


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("liquidity", D("1"), "MARKET_LIQUIDITY"),
        ("token_safety_known", False, "SUSPICIOUS_TOKEN"),
        ("suspicious", True, "SUSPICIOUS_TOKEN"),
        ("execution_model", "UNAVAILABLE", "EXECUTION_COST"),
        ("data_quality_status", "INVALID", "DATA_QUALITY"),
        ("event_time", now() - timedelta(minutes=10), "DATA_FRESHNESS"),
    ],
)
def test_risk_fails_closed(engine, field, value, reason):
    engine.control("start")
    engine.state["provider_healthy"] = True
    r = assess(
        sample().model_copy(update={field: value}), engine.cfg, engine.state, D(7), "AGGRESSOR"
    )
    assert reason in r.reason_codes


def test_drawdown_daily_loss_and_allocation(engine):
    engine.state.update(running=True, provider_healthy=True, equity="60")
    r = assess(sample(), engine.cfg, engine.state, D(7), "AGGRESSOR")
    assert {"DAILY_LOSS", "MAXIMUM_DRAWDOWN"} <= set(r.reason_codes)
    engine.state["cash"] = "1"
    assert allocate(engine.cfg, engine.state) < D(1)


def test_features_no_lookahead_and_strategy():
    fengine = FeatureEngine()
    cfg = Settings()
    for i in range(4):
        s = sample(i, str(1 + i * 0.01))
        f = fengine.compute(s)
    assert f.return_window == pytest.approx(0.03)
    assert f.imbalance == pytest.approx(0.6)
    assert f.consistency == 1
    assert f.volume_change == pytest.approx(0.3)
    r = regime(s, f)
    assert r.regime == "MOMENTUM_EXPANSION"
    signals = dispatch(s, f, r, cfg, 0.01)
    assert council(signals)[0] == "AGGRESSOR"
    with pytest.raises(ValueError):
        fengine.compute(sample(0))


def test_stop_loss_is_delayed_and_includes_fees(engine):
    enter(engine)
    engine.process(sample(5, ".9"))
    assert engine.state["positions"]
    assert engine.state["pending"]["DEMO-TEST"]["side"] == "SELL"
    engine.process(sample(6, ".85"))
    assert not engine.state["positions"]
    assert D(engine.state["realized"]) < 0
    assert D(engine.state["gross_pnl"]) > D(engine.state["realized"])


def test_expired_order_never_fills(engine):
    engine.control("start")
    for i in range(4):
        engine.process(sample(i, str(1 + i * 0.01)))
    engine.process(sample(24, "1.04"))
    assert not engine.state["positions"]
    statuses = engine.store.recent("paper_orders", engine.state["session_id"])
    assert any(x["status"] == "EXPIRED" for x in statuses)


def test_invalid_decimal_and_settings():
    with pytest.raises(ValidationError):
        sample(price="NaN")
    with pytest.raises(ValidationError):
        Settings(token_mints=["../../evil"])
    with pytest.raises(ValidationError):
        Settings(live_trading=True)


def test_restart_preserves_position(engine):
    enter(engine)
    restored = TradingEngine(engine.store)
    assert restored.state["positions"] == engine.state["positions"]
    assert not restored.state["running"]


def test_rollback_halts_on_db_failure(engine, monkeypatch):
    def fail(*args):
        raise RuntimeError("disk failure")

    monkeypatch.setattr(engine.store, "save", fail)
    with pytest.raises(RuntimeError):
        engine.process(sample())
    assert engine.state["decision_count"] == 0
    assert engine.state["fault"]
    assert not engine.features.history


def test_fill_rechecks_liquidity_withdrawal(engine):
    engine.control("start")
    for i in range(4):
        engine.process(sample(i, str(1 + i * 0.01)))
    engine.process(sample(4, "1.04").model_copy(update={"liquidity": D("50000")}))
    assert not engine.state["positions"]
    assert any(
        "LIQUIDITY_WITHDRAWAL" in o.get("reason_codes", [])
        for o in engine.store.recent("paper_orders", engine.state["session_id"])
    )


def test_pause_keeps_exit_and_stale_marks_block_new_entries(engine):
    enter(engine)
    p = next(iter(engine.state["positions"].values()))
    p["mark_time"] = (now() - timedelta(minutes=2)).isoformat()
    risk = assess(sample(), engine.cfg, engine.state, D(1), "AGGRESSOR")
    assert "PORTFOLIO_MARK_FRESHNESS" in risk.reason_codes
    engine.control("close-all")
    engine.control("stop")
    assert engine.state["pending"]["DEMO-TEST"]["side"] == "SELL"


def test_allocation_reserves_fees_in_exposure(engine):
    cfg = engine.cfg.model_copy(update={"max_exposure": D("7")})
    amount = allocate(cfg, engine.state)
    assert amount * (1 + cfg.fee_rate) + cfg.network_fee <= D("7")


def test_balance_setting_does_not_rewrite_session_pnl(engine):
    engine.control("settings", engine.cfg.model_copy(update={"initial_balance": D("100")}))
    assert engine.snapshot()["net_pnl"] == "0"
    assert engine.snapshot()["cash"] == "70"
    engine.control("reset")
    assert engine.snapshot()["cash"] == "100"
    assert engine.snapshot()["net_pnl"] == "0"
