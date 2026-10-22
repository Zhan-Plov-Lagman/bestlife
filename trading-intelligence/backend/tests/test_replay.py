from datetime import UTC, datetime, timedelta

import pytest
from test_pipeline import sample

from app.clock import ReplayClock
from app.domain import Settings
from app.instance import InstanceLease
from app.replay import replay


def dataset():
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        sample(i, str(1 + i * 0.01)).model_copy(
            update={
                "event_time": start + timedelta(seconds=i),
                "received_time": start + timedelta(seconds=i),
            }
        )
        for i in range(20)
    ]


def test_replay_deterministic_economics_and_isolation(tmp_path):
    events = dataset()
    a = replay(events, tmp_path / "a.db")
    b = replay(events, tmp_path / "b.db")
    assert a["result_sha256"] == b["result_sha256"]
    assert a["summary"]["fees"] != "0"
    assert a["provenance"] == "SYNTHETIC"
    assert all(s.processing_time is None for s in events)
    with pytest.raises(ValueError, match="NEW_DATABASE"):
        replay(events, tmp_path / "a.db")


def test_stress_is_explicit_and_limits_unchanged(tmp_path):
    cfg = Settings()
    result = replay(dataset(), tmp_path / "stress.db", cfg, "ADVERSE")
    assert result["settings"]["max_exposure"] == str(cfg.max_exposure)
    assert result["scenario"] == "ADVERSE"
    illiquid = replay(dataset(), tmp_path / "illiquid.db", cfg, "ILLIQUID")
    assert illiquid["summary"]["fees"] == "0"
    assert "MARKET_LIQUIDITY" in illiquid["reason_counts"]


def test_replay_rejects_future_leakage_and_duplicates(tmp_path):
    events = dataset()
    with pytest.raises(ValueError, match="TIME_REVERSED"):
        replay(list(reversed(events)), tmp_path / "reversed.db")
    with pytest.raises(ValueError, match="DUPLICATE_EVENT"):
        replay([events[0], events[0]], tmp_path / "duplicate.db")
    clock = ReplayClock(events[1].event_time)
    with pytest.raises(ValueError, match="TIME_REVERSED"):
        clock.advance(events[0].event_time)


def test_instance_lock_excludes_second_writer_and_releases(tmp_path):
    url = "sqlite:///" + str(tmp_path / "lock.db")
    first = InstanceLease(url).acquire()
    try:
        with pytest.raises(RuntimeError, match="ANOTHER_BACKEND"):
            InstanceLease(url).acquire()
    finally:
        first.close()
    second = InstanceLease(url).acquire()
    second.close()
