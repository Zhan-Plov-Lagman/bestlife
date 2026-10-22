"""Distinct research baselines, with no probability or trained-model claims."""

from typing import Protocol

from .domain import Assessment, FeatureVector, MarketSnapshot, Settings, StrategySignal


class StrategyModel(Protocol):
    version: str

    def evaluate(
        self, s: MarketSnapshot, f: FeatureVector, r: Assessment, cfg: Settings, cost: float
    ) -> StrategySignal: ...


class RegimeModel(Protocol):
    version: str

    def classify(self, s: MarketSnapshot, f: FeatureVector) -> Assessment: ...


class AggressorBaseline:
    version = "aggressor-v1.1"

    def evaluate(self, s, f, r, cfg, cost):
        reasons = []
        if not cfg.aggressor_enabled:
            reasons.append("STRATEGY_SUSPENDED")
        if r.regime != "MOMENTUM_EXPANSION":
            reasons.append("REGIME_MISMATCH")
        if (f.return_window or 0) <= cost + float(cfg.uncertainty_margin):
            reasons.append("MOMENTUM_BELOW_COST_BUFFER")
        if (
            (f.consistency or 0) < 0.75
            or (f.pressure_consistency or 0) < 0.75
            or (f.imbalance or 0) < 0.15
        ):
            reasons.append("SUSTAINED_PRESSURE_UNCONFIRMED")
        if (f.volume_change or 0) <= 0 or f.liquidity_change is None or f.liquidity_change < -0.05:
            reasons.append("MOMENTUM_QUALITY_UNCONFIRMED")
        if (f.return_window or 0) > 0.15:
            reasons.append("LATE_ENTRY")
        if (f.latest_return or 0) <= 0 or (f.acceleration or 0) < -0.005:
            reasons.append("REVERSAL_WARNING")
        return StrategySignal(
            strategy="AGGRESSOR",
            action="WAIT" if reasons else "PROPOSE_ENTRY",
            score=r.score if not reasons else 0,
            reason_codes=reasons or ["SUSTAINED_MOMENTUM_HYPOTHESIS"],
        )


class ScalpingBaseline:
    version = "scalping-v1.1"

    def evaluate(self, s, f, r, cfg, cost):
        reasons = []
        if not cfg.scalping_enabled:
            reasons.append("STRATEGY_SUSPENDED")
        if r.regime != "SHORT_TERM_OPPORTUNITY":
            reasons.append("REGIME_MISMATCH")
        if (
            f.sample_interval_seconds is None
            or f.sample_interval_seconds > 3
            or cfg.execution_delay_seconds > 2
        ):
            reasons.append("SCALP_LATENCY_TOO_HIGH")
        if f.volatility is None or not 0.0001 <= f.volatility <= 0.01:
            reasons.append("SCALP_VOLATILITY_OUTSIDE_RANGE")
        if (f.latest_return or 0) <= cost + float(cfg.uncertainty_margin):
            reasons.append("MICRO_MOVE_BELOW_ROUND_TRIP_COST")
        if (f.imbalance or 0) < 0.25 or s.liquidity < cfg.min_liquidity * 2:
            reasons.append("FAST_EXIT_UNCONFIRMED")
        return StrategySignal(
            strategy="SCALPING",
            action="WAIT" if reasons else "PROPOSE_ENTRY",
            score=0.6 if not reasons else 0,
            reason_codes=reasons or ["MICRO_MOVE_TEST_HYPOTHESIS"],
        )
