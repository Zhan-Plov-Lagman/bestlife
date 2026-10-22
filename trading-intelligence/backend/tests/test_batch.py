import copy

import pytest
from test_pipeline import sample

from app.engine import TradingEngine


def test_failed_reset_restores_feature_and_ui_state(engine, monkeypatch):
    engine.process(sample())
    history = engine.features
    latest = copy.deepcopy(engine.latest)

    def fail(*args):
        raise RuntimeError("save failed")

    monkeypatch.setattr(engine.store, "save", fail)
    with pytest.raises(RuntimeError):
        engine.control("reset")
    assert engine.features is history
    assert engine.latest == latest
    assert engine.state["decision_count"] == 1


def test_batch_rolls_back_every_event(engine, monkeypatch):
    original = engine.store.save

    def fail(*args):
        raise RuntimeError("commit interrupted")

    monkeypatch.setattr(engine.store, "save", fail)
    with pytest.raises(RuntimeError):
        engine.process_batch([sample(i, str(1 + i * 0.01)) for i in range(6)])
    assert engine.state["decision_count"] == 0 and not engine.features.history
    monkeypatch.setattr(engine.store, "save", original)
    recovered = TradingEngine(engine.store)
    assert recovered.state["decision_count"] == 0
    assert not recovered.state["reconciliation_errors"]


def test_batch_idempotency_and_order(engine):
    engine.control("start")
    snapshots = [sample(i, str(1 + i * 0.01)) for i in range(6)]
    assert all(engine.process_batch(snapshots))
    before = copy.deepcopy(engine.state)
    assert not any(engine.process_batch(snapshots))
    assert engine.state == before
    assert len(engine.store.recent("paper_fills", engine.state["session_id"])) == 1
