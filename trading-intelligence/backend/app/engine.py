import copy
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from .analytics import FeatureEngine, council, dispatch, guardian, regime
from .database import Store, events, seen, write_record
from .domain import D, MarketSnapshot, Settings, now, usd
from .execution import PaperExecutionAdapter
from .risk import allocate, assess, round_trip_cost


def fresh_state(cfg: Settings) -> dict[str, Any]:
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
        "day": now().date().isoformat(),
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
    def __init__(self, store: Store):
        self.store = store
        self.lock = threading.RLock()
        self.state = store.load() or fresh_state(Settings())
        self.state.setdefault("starting_balance", self.state["settings"]["initial_balance"])
        self.features = FeatureEngine()
        self.execution = PaperExecutionAdapter()
        self.latest: dict[str, dict[str, Any]] = {}
        self.latencies: deque[float] = deque(maxlen=5000)
        self.state["running"] = False  # restart requires deliberate resume
        self.state["provider_healthy"] = False
        with self.store.engine.begin() as conn:
            for order in self.state["pending"].values():
                self.record(
                    conn,
                    "paper_orders",
                    str(uuid4()),
                    {**order, "status": "CANCELLED", "reason_codes": ["RESTART"]},
                )
            self.state["pending"] = {}  # never replay an unfilled entry after restart
            self.log(
                conn, "RECOVERY", {"message": "Recovered ledger; pending orders cancelled; stopped"}
            )
            self.store.save(conn, self.state)

    @property
    def cfg(self) -> Settings:
        return Settings.model_validate(self.state["settings"])

    def log(self, conn, kind: str, payload: dict[str, Any]) -> None:
        conn.execute(
            events.insert().values(
                id=str(uuid4()),
                kind=kind,
                at=now().isoformat(),
                payload={"session_id": self.state["session_id"], **payload},
            )
        )

    def record(self, conn, name: str, key: str, payload: dict[str, Any]) -> None:
        write_record(conn, name, key, self.state["session_id"], now().isoformat(), payload)

    def control(self, action: str, settings: Settings | None = None) -> None:
        with self.lock:
            old = copy.deepcopy(self.state)
            try:
                with self.store.engine.begin() as conn:
                    if action == "start":
                        if self.state["killed"] or self.state["fault"]:
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
                                    {**order, "status": "CANCELLED"},
                                )
                        self.state["pending"] = {
                            k: v for k, v in self.state["pending"].items() if v["side"] == "SELL"
                        }
                        if action == "kill":
                            self.state["killed"] = True
                    elif action == "clear-halt":
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
                        self.state = fresh_state(self.cfg)
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
                            self.state = fresh_state(settings)
                            self.latest.clear()
                            self.features = FeatureEngine()
                    elif action == "close-all":
                        # Exits still wait for a future valid observation, including when halted.
                        for mint, p in self.state["positions"].items():
                            self.queue_order(
                                conn, mint, "SELL", p["strategy"], "MANUAL_EXIT", now()
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
        elapsed = (s.event_time - datetime.fromisoformat(order["created_at"])).total_seconds()
        if elapsed < self.cfg.execution_delay_seconds:
            return
        status = "FILLED"
        reasons: list[str] = []
        if elapsed > self.cfg.signal_ttl_seconds:
            status, reasons = "EXPIRED", ["SIGNAL_EXPIRED"]
        elif (
            not (-2 <= (now() - s.event_time).total_seconds() <= self.cfg.freshness_seconds)
            or s.data_quality_status != "VALID"
            or s.execution_model == "UNAVAILABLE"
            or s.liquidity <= 0
        ):
            status, reasons = "FAILED", ["UNRELIABLE_EXECUTION_DATA"]
        elif order["side"] == "BUY":
            risk = assess(s, self.cfg, self.state, D(order["amount"]), order["strategy"])
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
        if status == "FILLED":
            self.fill(conn, s, order)
        self.record(
            conn, "paper_orders", str(uuid4()), {**order, "status": status, "reason_codes": reasons}
        )
        del self.state["pending"][s.token_mint]

    def fill(self, conn, s: MarketSnapshot, order: dict[str, Any]) -> None:
        cfg = self.cfg
        if order["side"] == "BUY":
            amount = usd(D(order["amount"]))
            price, fee = self.execution.quote("BUY", amount, s, cfg)
            fee = usd(fee)
            qty = amount / price
            cost = amount + fee
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
                "fee": str(fee),
                "slippage_cost": str(impact_cost),
                "event_time": s.event_time.isoformat(),
                "provider": s.provider,
                "model": s.execution_model,
            },
        )

    def process(self, s: MarketSnapshot) -> bool:
        started = time.perf_counter()
        with self.lock:
            if s.provider != self.cfg.provider:
                return False
            old = copy.deepcopy(self.state)
            old_history = copy.deepcopy(self.features.history.get(s.provider + s.pool_address))
            try:
                with self.store.engine.begin() as conn:
                    dedup_key = self.state["session_id"] + ":" + s.event_id
                    if conn.execute(select(seen.c.id).where(seen.c.id == dedup_key)).first():
                        return False
                    conn.execute(
                        seen.insert().values(
                            id=dedup_key, session_id=self.state["session_id"], at=now().isoformat()
                        )
                    )
                    s.processing_time = now()
                    self.state["provider_healthy"] = True
                    age = (now() - s.event_time).total_seconds()
                    if age < -2 or age > self.cfg.freshness_seconds:
                        s.data_quality_status = "STALE"
                    try:
                        f = self.features.compute(s) if s.data_quality_status == "VALID" else None
                    except ValueError:
                        s.data_quality_status = "INVALID"
                        f = None
                    from .domain import FeatureVector

                    f = f or FeatureVector()
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
                    self.mark()
                    if self.state["day"] != now().date().isoformat():
                        self.state["day"], self.state["day_start_equity"] = (
                            now().date().isoformat(),
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
                    r = regime(s, f)
                    amount = allocate(self.cfg, self.state)
                    signals = dispatch(
                        s, f, r, self.cfg, float(round_trip_cost(self.cfg, amount, s.liquidity))
                    )
                    strategy, reasons = council(signals)
                    decision_id = str(uuid4())
                    risk = assess(
                        s,
                        self.cfg,
                        self.state,
                        amount,
                        strategy,
                        s.token_mint in self.state["pending"],
                    )
                    action = "SKIP"
                    p = self.state["positions"].get(s.token_mint)
                    if p:
                        change = D(s.price) / D(p["entry_price"]) - 1
                        held = (
                            s.event_time - datetime.fromisoformat(p["opened_at"])
                        ).total_seconds()
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
                        self.queue_order(
                            conn, s.token_mint, "BUY", strategy, decision_id, s.event_time
                        )
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
                        "model_version": "baseline-v1",
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
                        {"time": s.event_time.isoformat(), "equity": self.state["equity"]},
                    )
                    self.store.save(conn, self.state)
                self.latest[s.token_mint] = {
                    **s.model_dump(mode="json"),
                    "features": f.model_dump(mode="json"),
                    "regime": r.model_dump(mode="json"),
                }
                self.latencies.append((time.perf_counter() - started) * 1000)
                return True
            except Exception as exc:
                self.state = old
                if old_history is None:
                    self.features.history.pop(s.provider + s.pool_address, None)
                else:
                    self.features.history[s.provider + s.pool_address] = old_history
                self.state["fault"] = type(exc).__name__
                self.state["running"] = False
                raise

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
