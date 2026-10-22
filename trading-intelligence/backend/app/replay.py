"""Offline deterministic research. No network, shared account or automatic promotion."""

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Literal

from .clock import ReplayClock
from .database import Store, metadata
from .domain import D, MarketSnapshot, Settings
from .engine import TradingEngine
from .reconciliation import reconcile


def replay(
    snapshots: list[MarketSnapshot],
    database: Path,
    cfg: Settings | None = None,
    scenario: Literal["BASE", "ADVERSE", "ILLIQUID"] = "BASE",
) -> dict:
    if not snapshots or len(snapshots) > 100000:
        raise ValueError("REPLAY_EVENT_LIMIT")
    if database.exists():
        raise ValueError("REPLAY_REQUIRES_NEW_DATABASE")
    if scenario not in {"BASE", "ADVERSE", "ILLIQUID"}:
        raise ValueError("UNKNOWN_SCENARIO")
    cfg = cfg or Settings()
    if cfg.provider != "DEMO" or any(s.provider != "DEMO" for s in snapshots):
        raise ValueError("UNVERIFIED_EXECUTION_SOURCE")
    if any(b.event_time < a.event_time for a, b in zip(snapshots, snapshots[1:])):
        raise ValueError("REPLAY_TIME_REVERSED")
    if len({s.event_id for s in snapshots}) != len(snapshots):
        raise ValueError("REPLAY_DUPLICATE_EVENT")
    # Explicit synthetic stress assumptions, not estimates of actual pool execution.
    if scenario == "ADVERSE":
        cfg = Settings.model_validate(
            {
                **cfg.model_dump(),
                "slippage": max(cfg.slippage, D(".01")),
                "fee_rate": max(cfg.fee_rate, D(".006")),
                "network_fee": max(cfg.network_fee, D(".01")),
                "execution_delay_seconds": max(cfg.execution_delay_seconds, 3),
            }
        )
    fingerprint = hashlib.sha256(
        "\n".join(s.model_dump_json() for s in snapshots).encode()
    ).hexdigest()
    clock = ReplayClock(snapshots[0].event_time)
    store = Store("sqlite:///" + str(database.resolve()))
    try:
        metadata.create_all(store.engine)
        engine = TradingEngine(store, clock)
        engine.control("settings", cfg)
        engine.control("reset")
        engine.control("start")
        decisions = []
        reasons: Counter = Counter()
        for source in snapshots:
            clock.advance(source.event_time)
            event = source.model_copy(update={"received_time": source.event_time})
            if scenario == "ILLIQUID":
                event = event.model_copy(update={"liquidity": event.liquidity * D(".001")})
            if not engine.process(event):
                raise ValueError("REPLAY_EVENT_NOT_ACCEPTED")
            d = engine.state["last_decision"]
            decisions.append(
                {
                    k: d[k]
                    for k in (
                        "event_time",
                        "token_mint",
                        "action",
                        "strategy",
                        "reason_codes",
                        "features",
                        "risk",
                    )
                }
            )
            reasons.update(d["reason_codes"])
        with store.engine.begin() as conn:
            errors = reconcile(conn, engine.state)
        if errors:
            raise ValueError("REPLAY_RECONCILIATION_FAILED: " + ",".join(errors))
        # Never invent a final liquidation quote: remaining positions stay marked and visible.
        summary = {
            k: engine.state[k]
            for k in (
                "cash",
                "equity",
                "realized",
                "fees",
                "slippage_cost",
                "max_drawdown",
                "closed",
                "wins",
            )
        }
        summary.update(
            open_positions=len(engine.state["positions"]),
            pending_orders=len(engine.state["pending"]),
        )
        digest = hashlib.sha256(
            json.dumps({"decisions": decisions, "summary": summary}, sort_keys=True).encode()
        ).hexdigest()
        return {
            "schema": "replay-v1.1",
            "provenance": "SYNTHETIC",
            "scenario": scenario,
            "dataset_sha256": fingerprint,
            "result_sha256": digest,
            "settings": cfg.model_dump(mode="json"),
            "events": len(snapshots),
            "summary": summary,
            "reason_counts": dict(reasons),
            "decisions": decisions,
            "limitations": [
                "No observed fills or profitability claim",
                "No depth data: all-or-none, no partial fills",
                "End positions not forcibly liquidated",
                "UUID journal identities intentionally excluded from economic digest",
            ],
        }
    finally:
        store.engine.dispose()
