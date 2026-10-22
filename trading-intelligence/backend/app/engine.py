import copy
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from .analytics import FeatureEngine, council, dispatch, guardian, regime
from .clock import Clock, SystemClock
from .database import Store, events, records, seen, write_record
from .domain import D, MarketSnapshot, Settings, now, usd
from .execution import PaperExecutionAdapter
from .reconciliation import reconcile
from .risk import allocate, assess, round_trip_cost


def fresh_state(cfg: Settings, at: datetime | None = None) -> dict[str, Any]:
    return {
        "session_id": str(uuid4()),
        "settings": cfg.model_dump(mode="json"),
        "running": False,
        "killed": False,
        "fault": None,
        "provider_healthy": False,
        "cash": str(cfg.initial_balance),
        "starting_balance": str(cfg.initial_balance),
        "equity": str(cfg.initial_balance),
        "peak_equity": str(cfg.initial_balance),
        "day_start_equity": str(cfg.initial_balance),
        "day": (at or now()).date().isoformat(),
        "realized": "0",
        "fees": "0",
        "slippage_cost": "0",
        "gross_pnl": "0",
        "max_drawdown": "0",
        "positions": {},
        "pending": {},
        "suspended": [],
        "closed": 0,
        "wins": 0,
        "loss_streak": 0,
        "decision_count": 0,
        "skipped": 0,
        "last_decision": None,
    }


class TradingEngine:
    def __init__(self, store: Store, clock: Clock | None = None):
        self.store = store
        self.clock = clock or SystemClock()
        self.lock = threading.RLock()
        self.state = store.load() or fresh_state(Settings(), self.clock.now())
        self.state.setdefault("starting_balance", self.state["settings"]["initial_balance"])
        self._cfg_source = self.state["settings"]
        self._cfg = Settings.model_validate(self._cfg_source)
        self.features = FeatureEngine()
        self.execution = PaperExecutionAdapter()
        self.latest: dict[str, dict[str, Any]] = {}
        self.latencies: deque[float] = deque(maxlen=5000)
        self.stage_metrics: dict[str, deque[float]] = {
            k: deque(maxlen=5000)
            for k in (
                "features_ms",
                "strategies_ms",
                "risk_ms",
                "persistence_batch_ms",
                "batch_total_ms",
            )
        }
        self._telemetry_buffer: dict[str, list[dict[str, Any]]] | None = None
        self.state["running"] = False  # restart requires deliberate resume
        self.state["provider_healthy"] = False
        self.state["recovery_marks"] = list(self.state["positions"])
        self.state["recovery_started"] = self.clock.now().isoformat()
        with self.store.engine.begin() as conn:
            self.state["reconciliation_errors"] = reconcile(conn, self.state)
            if self.state["reconciliation_errors"]:
                self.state["fault"] = "LEDGER_RECONCILIATION_FAILED"
            for order in self.state["pending"].values():
                recover_exit = (
                    order["side"] == "SELL" and order["token_mint"] in self.state["positions"]
                )
                if recover_exit:
                    order["status"] = "RECOVERY_PENDING"
                    order["recovery_after"] = self.clock.now().isoformat()
                self.record(
                    conn,
                    "paper_orders",
                    str(uuid4()),
                    {
                        **order,
                        "status": "RECOVERY_PENDING" if recover_exit else "CANCELLED",
                        "reason_codes": [
                            "RESTART_EXIT_REQUIRES_FRESH_QUOTE"
                            if recover_exit
                            else "RESTART_CANCEL_ENTRY"
                        ],
                    },
                )
            self.state["pending"] = {
                k: v
                for k, v in self.state["pending"].items()
                if v["side"] == "SELL" and k in self.state["positions"]
            }
            self.log(
                conn,
                "RECOVERY",
                {
                    "message": "Entries cancelled; exit intents preserved; stopped",
                    "errors": self.state["reconciliation_errors"],
                },
            )
            self.store.save(conn, self.state)

    @property
    def cfg(self) -> Settings:
        if self._cfg_source is not self.state["settings"]:
            self._cfg_source = self.state["settings"]
            self._cfg = Settings.model_validate(self._cfg_source)
        return self._cfg

    def log(self, conn, kind: str, payload: dict[str, Any]) -> None:
        conn.execute(
            events.insert().values(
                id=str(uuid4()),
                kind=kind,
                at=self.clock.now().isoformat(),
                payload={"session_id": self.state["session_id"], **payload},
            )
        )

    def record(self, conn, name: str, key: str, payload: dict[str, Any]) -> None:
        if self._telemetry_buffer is not None and name not in {
            "paper_fills",
            "paper_orders",
            "paper_positions",
        }:
            self._telemetry_buffer.setdefault(name, []).append(
                {
                    "id": key,
                    "session_id": self.state["session_id"],
                    "at": self.clock.now().isoformat(),
                    "payload": payload,
                }
            )
        else:
            write_record(
                conn, name, key, self.state["session_id"], self.clock.now().isoformat(), payload
            )

    def control(self, action: str, settings: Settings | None = None) -> None:
        with self.lock:
            old = copy.deepcopy(self.state)
            old_features, old_latest = self.features, self.latest.copy()
            try:
                with self.store.engine.begin() as conn:
                    if action == "start":
                        if (
                            self.state["killed"]
                            or self.state["fault"]
                            or self.state.get("recovery_marks")
                        ):
                            raise ValueError("Clear the halt before starting")
                        self.state["running"] = True
                    elif action in ("stop", "kill"):
                        self.state["running"] = False
                        for order in self.state["pending"].values():
                            if order["side"] == "BUY":
                                self.record(
                                    conn,
                                    "paper_orders",
                                    str(uuid4()),
                                    {
                                        **order,
                                        "status": "CANCELLED",
                                        "reason_codes": ["CONTROL_" + action.upper()],
                                    },
                                )
                        self.state["pending"] = {
                            k: v for k, v in self.state["pending"].items() if v["side"] == "SELL"
                        }
                        if action == "kill":
                            self.state["killed"] = True
                    elif action == "clear-halt":
                        self.state["reconciliation_errors"] = reconcile(conn, self.state)
                        if self.state["reconciliation_errors"]:
                            raise ValueError("LEDGER_RECONCILIATION_FAILED")
                        self.state["killed"] = False
                        self.state["fault"] = None
                        self.state["running"] = False
                    elif action == "reset":
                        if (
                            self.state["running"]
                            or self.state["positions"]
                            or self.state["pending"]
                        ):
                            raise ValueError(
                                "Stop and close positions before resetting; prior session remains archived"
                            )
                        self.state = fresh_state(self.cfg, self.clock.now())
                        self.features = FeatureEngine()
                        self.latest.clear()
                    elif action == "settings" and settings:
                        if (
                            self.state["running"]
                            or self.state["positions"]
                            or self.state["pending"]
                        ):
                            raise ValueError("Settings require a stopped, flat portfolio")
                        provider_changed = self.cfg.provider != settings.provider
                        self.state["settings"] = settings.model_dump(mode="json")
                        if provider_changed:
                            self.state = fresh_state(settings, self.clock.now())
                            self.latest.clear()
                            self.features = FeatureEngine()
                    elif action == "close-all":
                        # Exits still wait for a future valid observation, including when halted.
                        for mint, p in self.state["positions"].items():
                            self.queue_order(
                                conn, mint, "SELL", p["strategy"], "MANUAL_EXIT", self.clock.now()
                            )
                    else:
                        raise ValueError("Unknown action")
                    self.log(
                        conn,
                        "CONTROL",
                        {
                            "action": action,
                            "settings": self.state["settings"] if action == "settings" else None,
                        },
                    )
                    self.store.save(conn, self.state)
            except Exception:
                self.state = old
                self.features, self.latest = old_features, old_latest
                raise

    def queue_order(
        self, conn, mint: str, side: str, strategy: str, decision_id: str, at: datetime
    ) -> None:
        if mint in self.state["pending"]:
            return
        order = {
            "id": str(uuid4()),
            "token_mint": mint,
            "side": side,
            "strategy": strategy,
            "decision_id": decision_id,
            "created_at": at.isoformat(),
            "status": "PENDING",
            "amount": str(allocate(self.cfg, self.state)) if side == "BUY" else "0",
        }
        self.state["pending"][mint] = order
        self.record(conn, "paper_orders", order["id"], order)

    def mark(self) -> None:
        equity = D(self.state["cash"])
        for p in self.state["positions"].values():
            equity += D(p["net_liquidation_value"])
        self.state["equity"] = str(equity)
        peak = max(D(self.state["peak_equity"]), equity)
        self.state["peak_equity"] = str(peak)
        dd = max(D(0), (peak - equity) / peak)
        self.state["max_drawdown"] = str(max(D(self.state["max_drawdown"]), dd))

    def process_pending(self, conn, s: MarketSnapshot) -> None:
        order = self.state["pending"].get(s.token_mint)
        if not order:
            return
        if self.state.get("reconciliation_errors"):
            return
        if order.get("recovery_after") and s.event_time <= datetime.fromisoformat(
            order["recovery_after"]
        ):
            return
        elapsed = (s.event_time - datetime.fromisoformat(order["created_at"])).total_seconds()
        if elapsed < self.cfg.execution_delay_seconds:
            return
        status = "FILLED"
        reasons: list[str] = []
        if elapsed > self.cfg.signal_ttl_seconds:
            status, reasons = "EXPIRED", ["SIGNAL_EXPIRED"]
        elif (
            not (
                -2
                <= (self.clock.now() - s.event_time).total_seconds()
                <= self.cfg.freshness_seconds
            )
            or s.data_quality_status != "VALID"
            or s.execution_model == "UNAVAILABLE"
            or s.liquidity <= 0
        ):
            status, reasons = "FAILED", ["UNRELIABLE_EXECUTION_DATA"]
        elif order["side"] == "BUY":
            risk = assess(
                s, self.cfg, self.state, D(order["amount"]), order["strategy"], at=self.clock.now()
            )
            self.record(
                conn,
                "risk_assessments",
                str(uuid4()),
                {
                    "decision_id": order["decision_id"],
                    "stage": "FILL_RECHECK",
                    **risk.model_dump(mode="json"),
                },
            )
            if risk.status != "APPROVED":
                status, reasons = "REJECTED", risk.reason_codes
        if order["side"] == "SELL":
            from .risk import assess_exit

            position = self.state["positions"].get(s.token_mint)
            if not position:
                status, reasons = "CANCELLED", ["POSITION_ALREADY_CLOSED"]
            elif status in {"EXPIRED", "FILLED"}:
                exit_reasons = assess_exit(s, self.cfg, self.state, position, self.clock.now())
                if exit_reasons:
                    status, reasons = "BLOCKED", exit_reasons
            if status == "EXPIRED":
                self.record(
                    conn,
                    "paper_orders",
                    str(uuid4()),
                    {**order, "status": "EXPIRED", "reason_codes": reasons},
                )
                del self.state["pending"][s.token_mint]
                self.queue_order(
                    conn,
                    s.token_mint,
                    "SELL",
                    order["strategy"],
                    order["decision_id"],
                    s.event_time,
                )
                return
            if status in {"FAILED", "BLOCKED"}:
                if order.get("reason_codes") != reasons or order["status"] != "BLOCKED":
                    order.update(status="BLOCKED", reason_codes=reasons)
                    self.record(conn, "paper_orders", str(uuid4()), order.copy())
                if s.token_mint not in self.state.setdefault("recovery_marks", []):
                    self.state["recovery_marks"].append(s.token_mint)
                return
        if status == "FILLED":
            self.fill(conn, s, order)
        self.record(
            conn, "paper_orders", str(uuid4()), {**order, "status": status, "reason_codes": reasons}
        )
        del self.state["pending"][s.token_mint]

    def fill(self, conn, s: MarketSnapshot, order: dict[str, Any]) -> None:
        cfg = self.cfg
        if conn.execute(
            select(records["paper_fills"].c.id).where(records["paper_fills"].c.id == order["id"])
        ).first():
            return
        if order["side"] == "BUY":
            amount = usd(D(order["amount"]))
            price, fee = self.execution.quote("BUY", amount, s, cfg)
            fee = usd(fee)
            qty = amount / price
            cost = amount + fee
            if (
                cost > D(self.state["cash"])
                or amount <= 0
                or s.token_mint in self.state["positions"]
            ):
                raise ValueError("SETTLEMENT_ENTRY_INVARIANT")
            self.state["cash"] = str(D(self.state["cash"]) - cost)
            exit_price, _ = self.execution.quote("SELL", qty * s.price, s, cfg)
            exit_fee = qty * exit_price * cfg.fee_rate + cfg.network_fee
            p = {
                "id": str(uuid4()),
                "token_mint": s.token_mint,
                "symbol": s.symbol,
                "strategy": order["strategy"],
                "quantity": str(qty),
                "entry_price": str(price),
                "cost_basis": str(cost),
                "entry_fee": str(fee),
                "opened_at": s.event_time.isoformat(),
                "mark_price": str(s.price),
                "mark_time": s.event_time.isoformat(),
                "net_liquidation_value": str(qty * exit_price - exit_fee),
            }
            self.state["positions"][s.token_mint] = p
            self.record(conn, "paper_positions", p["id"], p)
            gross = D(0)
        else:
            p = self.state["positions"][s.token_mint]
            qty = D(p["quantity"])
            price, _ = self.execution.quote("SELL", qty * s.price, s, cfg)
            amount = usd(qty * price)
            fee = usd(amount * cfg.fee_rate + cfg.network_fee)
            net = amount - fee
            if D(self.state["cash"]) + net < 0:
                raise ValueError("SETTLEMENT_NEGATIVE_CASH")
            pnl = net - D(p["cost_basis"])
            gross = amount - (D(p["cost_basis"]) - D(p["entry_fee"]))
            self.state["cash"] = str(D(self.state["cash"]) + net)
            self.state["realized"] = str(D(self.state["realized"]) + pnl)
            self.state["gross_pnl"] = str(D(self.state["gross_pnl"]) + gross)
            self.state["closed"] += 1
            self.state["wins"] += int(pnl > 0)
            self.state["loss_streak"] = self.state["loss_streak"] + 1 if pnl < 0 else 0
            if self.state["loss_streak"] >= 3:
                self.state["suspended"] = ["AGGRESSOR", "SCALPING"]
                self.log(conn, "GOVERNOR_SUSPEND", {"reason": "THREE_CONSECUTIVE_LOSSES"})
            self.record(
                conn,
                "paper_positions",
                str(uuid4()),
                {
                    **p,
                    "status": "CLOSED",
                    "realized_pnl": str(pnl),
                    "closed_at": s.event_time.isoformat(),
                },
            )
            del self.state["positions"][s.token_mint]
            self.state["recovery_marks"] = [
                m for m in self.state.get("recovery_marks", []) if m != s.token_mint
            ]
        self.state["fees"] = str(D(self.state["fees"]) + fee)
        impact_cost = usd(abs(price - s.price) * qty)
        self.state["slippage_cost"] = str(D(self.state["slippage_cost"]) + impact_cost)
        self.record(
            conn,
            "paper_fills",
            order["id"],
            {
                "id": order["id"],
                "decision_id": order["decision_id"],
                "side": order["side"],
                "symbol": s.symbol,
                "token_mint": s.token_mint,
                "price": str(price),
                "quantity": str(qty),
                "notional": str(amount),
                "provenance": "SYNTHETIC" if s.provider == "DEMO" else "UNAVAILABLE",
                "fee": str(fee),
                "slippage_cost": str(impact_cost),
                "event_time": s.event_time.isoformat(),
                "provider": s.provider,
                "model": s.execution_model,
            },
        )

    def process(self, s: MarketSnapshot) -> bool:
        return self.process_batch([s])[0]

    def process_batch(self, snapshots: list[MarketSnapshot]) -> list[bool]:
        if len(snapshots) > 32:
            raise ValueError("BATCH_LIMIT")
        started = time.perf_counter()
        with self.lock:
            old = {
                **self.state,
                "positions": {k: v.copy() for k, v in self.state["positions"].items()},
                "pending": {k: v.copy() for k, v in self.state["pending"].items()},
                "recovery_marks": list(self.state.get("recovery_marks", [])),
            }
            history = {k: v.copy() for k, v in self.features.history.items()}
            latest = self.latest.copy()
            results = []
            self._telemetry_buffer = {}
            try:
                with self.store.engine.begin() as conn:
                    for snapshot in snapshots:
                        event_start = time.perf_counter()
                        results.append(self._process_event(conn, snapshot))
                        self.latencies.append((time.perf_counter() - event_start) * 1000)
                    persistence_start = time.perf_counter()
                    for name, rows in self._telemetry_buffer.items():
                        conn.execute(records[name].insert(), rows)
                    if any(results):
                        self.store.save(conn, self.state)
                self.stage_metrics["persistence_batch_ms"].append(
                    (time.perf_counter() - persistence_start) * 1000
                )
                self.stage_metrics["batch_total_ms"].append((time.perf_counter() - started) * 1000)
                return results
            except Exception as exc:
                self.state, self.features.history, self.latest = old, history, latest
                self.state["fault"] = type(exc).__name__
                self.state["running"] = False
                raise
            finally:
                self._telemetry_buffer = None

    def _process_event(self, conn, s: MarketSnapshot) -> bool:
        if s.provider != self.cfg.provider:
            return False
        dedup_key = self.state["session_id"] + ":" + s.event_id
        if conn.execute(select(seen.c.id).where(seen.c.id == dedup_key)).first():
            return False
        conn.execute(
            seen.insert().values(
                id=dedup_key,
                session_id=self.state["session_id"],
                at=self.clock.now().isoformat(),
            )
        )
        s = s.model_copy(update={"processing_time": self.clock.now()})
        self.state["provider_healthy"] = True
        age = (self.clock.now() - s.event_time).total_seconds()
        if age < -2 or age > self.cfg.freshness_seconds:
            s.data_quality_status = "STALE"
        feature_started = time.perf_counter()
        try:
            f = self.features.compute(s) if s.data_quality_status == "VALID" else None
        except ValueError:
            s.data_quality_status = "INVALID"
            f = None
        from .domain import FeatureVector

        f = f or FeatureVector()
        self.stage_metrics["features_ms"].append((time.perf_counter() - feature_started) * 1000)
        p = self.state["positions"].get(s.token_mint)
        if (
            p
            and s.data_quality_status == "VALID"
            and s.execution_model != "UNAVAILABLE"
            and s.liquidity > 0
        ):
            qty = D(p["quantity"])
            exit_price, _ = self.execution.quote("SELL", qty * s.price, s, self.cfg)
            p["net_liquidation_value"] = str(
                qty * exit_price * (1 - self.cfg.fee_rate) - self.cfg.network_fee
            )
            p["mark_price"], p["mark_time"] = str(s.price), s.event_time.isoformat()
            if s.event_time > datetime.fromisoformat(
                self.state.get("recovery_started", s.event_time.isoformat())
            ):
                self.state["recovery_marks"] = [
                    m for m in self.state.get("recovery_marks", []) if m != s.token_mint
                ]
        self.mark()
        if self.state["day"] != self.clock.now().date().isoformat():
            self.state["day"], self.state["day_start_equity"] = (
                self.clock.now().date().isoformat(),
                self.state["equity"],
            )
        guard_status, guard_reasons = guardian(s, f)
        pending = self.state["pending"].get(s.token_mint)
        if pending and pending["side"] == "BUY" and guard_status == "BLOCK":
            self.record(
                conn,
                "paper_orders",
                str(uuid4()),
                {**pending, "status": "REJECTED", "reason_codes": guard_reasons},
            )
            del self.state["pending"][s.token_mint]
        self.process_pending(conn, s)
        self.mark()
        strategy_started = time.perf_counter()
        r = regime(s, f)
        amount = allocate(self.cfg, self.state)
        signals = dispatch(s, f, r, self.cfg, float(round_trip_cost(self.cfg, amount, s.liquidity)))
        strategy, reasons = council(signals)
        self.stage_metrics["strategies_ms"].append((time.perf_counter() - strategy_started) * 1000)
        decision_id = str(uuid4())
        risk_started = time.perf_counter()
        risk = assess(
            s,
            self.cfg,
            self.state,
            amount,
            strategy,
            s.token_mint in self.state["pending"],
            at=self.clock.now(),
        )
        self.stage_metrics["risk_ms"].append((time.perf_counter() - risk_started) * 1000)
        action = "SKIP"
        p = self.state["positions"].get(s.token_mint)
        if p:
            change = D(s.price) / D(p["entry_price"]) - 1
            held = (s.event_time - datetime.fromisoformat(p["opened_at"])).total_seconds()
            if (
                change <= -self.cfg.stop_loss
                or change >= self.cfg.take_profit
                or held >= 180
                or signals[-1].action == "REJECT"
            ):
                action, reasons = (
                    "PROPOSE_EXIT",
                    [
                        "STOP_LOSS"
                        if change <= -self.cfg.stop_loss
                        else "TAKE_PROFIT"
                        if change >= self.cfg.take_profit
                        else "TIME_OR_GUARDIAN_EXIT"
                    ],
                )
                self.queue_order(
                    conn, s.token_mint, "SELL", p["strategy"], decision_id, s.event_time
                )
        elif strategy != "SKIP" and risk.status == "APPROVED":
            action = "PROPOSE_ENTRY"
            self.queue_order(conn, s.token_mint, "BUY", strategy, decision_id, s.event_time)
        decision = {
            "decision_id": decision_id,
            "event_time": s.event_time.isoformat(),
            "symbol": s.symbol,
            "token_mint": s.token_mint,
            "provider": s.provider,
            "action": action,
            "strategy": strategy,
            "reason_codes": list(
                dict.fromkeys(reasons + (risk.reason_codes if action == "SKIP" else []))
            ),
            "risk": risk.model_dump(mode="json"),
            "regime": r.model_dump(mode="json"),
            "features": f.model_dump(mode="json"),
            "signals": [x.model_dump(mode="json") for x in signals],
            "model_version": self.cfg.strategy_version,
            "guardian": {"status": guard_status, "reason_codes": guard_reasons},
            "proposed_amount": str(amount),
            "expected_cost_fraction": str(round_trip_cost(self.cfg, amount, s.liquidity)),
            "provenance": "SYNTHETIC" if s.provider == "DEMO" else "UNAVAILABLE",
        }
        for name, payload in [
            ("market_snapshots", s.model_dump(mode="json")),
            ("feature_snapshots", f.model_dump(mode="json")),
            ("market_regimes", r.model_dump(mode="json")),
            ("strategy_signals", {"signals": decision["signals"]}),
            ("risk_assessments", risk.model_dump(mode="json")),
            ("decisions", decision),
        ]:
            self.record(conn, name, decision_id, payload)
        self.state["last_decision"] = decision
        self.state["decision_count"] += 1
        self.state["skipped"] += int(action == "SKIP")
        self.record(
            conn,
            "portfolio_snapshots",
            decision_id,
            {
                "time": s.event_time.isoformat(),
                "equity": self.state["equity"],
                "cash": self.state["cash"],
                "realized": self.state["realized"],
                "fees": self.state["fees"],
            },
        )
        self.latest[s.token_mint] = {
            **s.model_dump(mode="json"),
            "features": f.model_dump(mode="json"),
            "regime": r.model_dump(mode="json"),
        }
        return True

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            s = copy.deepcopy(self.state)
            s["unrealized"] = str(
                sum(
                    (
                        D(p["net_liquidation_value"]) - D(p["cost_basis"])
                        for p in s["positions"].values()
                    ),
                    D(0),
                )
            )
            s["net_pnl"] = str(D(s["equity"]) - D(s["starting_balance"]))
            s["win_rate"] = s["wins"] / s["closed"] if s["closed"] else None
            s["real_exposure"] = "0"
            s["paper_only"] = True
            s["tokens"] = list(self.latest.values())
            return s
