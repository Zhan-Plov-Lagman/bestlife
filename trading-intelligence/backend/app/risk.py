from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from typing import Any

from .domain import D, MarketSnapshot, RiskAssessment, Settings, now


def allocate(cfg: Settings, state: dict[str, Any]) -> Decimal:
    exposure = sum((D(p["cost_basis"]) for p in state["positions"].values()), D(0))
    # Equity growth never increases the absolute budget. Reserve fees before sizing.
    return max(
        D(0),
        min(
            cfg.max_position,
            (cfg.max_exposure - exposure - cfg.network_fee) / (1 + cfg.fee_rate),
            (D(state["cash"]) - cfg.network_fee) / (1 + cfg.fee_rate),
        ),
    ).quantize(D("0.00000001"), rounding=ROUND_DOWN)


def round_trip_cost(cfg: Settings, amount: Decimal, liquidity: Decimal) -> Decimal:
    if amount <= 0 or liquidity <= 0:
        return D(1)
    return 2 * (cfg.fee_rate + cfg.slippage + amount / liquidity + cfg.network_fee / amount)


def assess(
    s: MarketSnapshot,
    cfg: Settings,
    state: dict[str, Any],
    amount: Decimal,
    strategy: str,
    duplicate: bool = False,
) -> RiskAssessment:
    age = (now() - s.event_time).total_seconds()
    equity = D(state["equity"])
    peak = D(state["peak_equity"])
    exposure = sum((D(p["cost_basis"]) for p in state["positions"].values()), D(0))
    checks = {
        "DATA_FRESHNESS": -2 <= age <= cfg.freshness_seconds,
        "DATA_QUALITY": s.data_quality_status == "VALID",
        "MARKET_LIQUIDITY": s.liquidity >= cfg.min_liquidity,
        "EXECUTION_COST": s.execution_model != "UNAVAILABLE"
        and round_trip_cost(cfg, amount, s.liquidity) <= cfg.max_cost_fraction,
        "PORTFOLIO_EXPOSURE": amount > 0
        and exposure + amount * (1 + cfg.fee_rate) + cfg.network_fee <= cfg.max_exposure
        and len(state["positions"]) < cfg.max_positions,
        "MAXIMUM_DRAWDOWN": peak > 0 and (peak - equity) / peak < cfg.max_drawdown,
        "DAILY_LOSS": D(state["day_start_equity"]) - equity < cfg.daily_loss_limit,
        "STRATEGY_HEALTH": strategy not in state["suspended"]
        and (
            (strategy == "AGGRESSOR" and cfg.aggressor_enabled)
            or (strategy == "SCALPING" and cfg.scalping_enabled)
        ),
        "PROVIDER_HEALTH": state["provider_healthy"],
        "KILL_SWITCH": not state["killed"],
        "SUSPICIOUS_TOKEN": s.token_safety_known and s.suspicious is False,
        "POSITION_CONCENTRATION": amount <= cfg.max_position
        and s.token_mint not in state["positions"],
        "DUPLICATE_ORDER": not duplicate,
        "TRADING_SESSION": state["running"] and not state["fault"],
        "CASH_RESERVE": amount * (1 + cfg.fee_rate) + cfg.network_fee <= D(state["cash"]),
        "PORTFOLIO_MARK_FRESHNESS": all(
            -2
            <= (now() - datetime.fromisoformat(p["mark_time"])).total_seconds()
            <= cfg.freshness_seconds
            for p in state["positions"].values()
        ),
    }
    reasons = [k for k, passed in checks.items() if not passed]
    return RiskAssessment(
        status="SYSTEM_HALTED"
        if state["killed"] or state["fault"]
        else "REJECTED"
        if reasons
        else "APPROVED",
        reason_codes=reasons,
        checks=checks,
    )
