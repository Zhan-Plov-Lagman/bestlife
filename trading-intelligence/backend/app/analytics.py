"""Pure, shared baseline analytics: no fitted model or calibrated probabilities."""

from collections import deque
from statistics import pstdev

from .domain import Assessment, FeatureVector, MarketSnapshot, Settings, StrategySignal

FEATURE_CATALOG = {
    "return_window": ("ratio", "last / first - 1", "price", "12 observations"),
    "acceleration": ("ratio", "last return - prior return", "price", "3 observations"),
    "consistency": ("fraction", "positive returns / returns", "price", "12 observations"),
    "volatility": ("ratio", "population stdev of simple returns", "price", "12 observations"),
    "liquidity_change": ("ratio", "last / first - 1", "liquidity", "12 observations"),
    "volume_change": ("ratio", "last / first - 1", "rolling provider volume", "12 observations"),
    "imbalance": ("ratio", "(buys-sells)/(buys+sells)", "provider counts", "provider window"),
    "wallet_concentration": (
        "fraction",
        "unavailable",
        "requires indexed wallet source",
        "unavailable",
    ),
}


class FeatureEngine:
    def __init__(self) -> None:
        self.history: dict[str, deque[MarketSnapshot]] = {}

    def compute(self, s: MarketSnapshot) -> FeatureVector:
        key = s.provider + s.pool_address
        history = self.history.setdefault(key, deque(maxlen=12))
        if history and s.event_time <= history[-1].event_time:
            raise ValueError("OUT_OF_ORDER")
        history.append(s)
        f = FeatureVector(observations=len(history))
        if len(history) < 4:
            return f
        prices = [float(x.price) for x in history]
        returns = [b / a - 1 for a, b in zip(prices, prices[1:])]
        f.return_window = prices[-1] / prices[0] - 1
        f.acceleration = returns[-1] - returns[-2]
        f.consistency = sum(r > 0 for r in returns) / len(returns)
        f.volatility = pstdev(returns)
        f.liquidity_change = (
            float(s.liquidity / history[0].liquidity - 1) if history[0].liquidity else None
        )
        f.volume_change = float(s.volume / history[0].volume - 1) if history[0].volume else None
        if s.buys is not None and s.sells is not None and s.buys + s.sells:
            f.imbalance = (s.buys - s.sells) / (s.buys + s.sells)
        return f


def guardian(s: MarketSnapshot, f: FeatureVector) -> tuple[str, list[str]]:
    reasons = []
    if s.data_quality_status != "VALID":
        reasons.append("DATA_QUALITY")
    if not s.token_safety_known or s.suspicious is None:
        reasons.append("TOKEN_SAFETY_UNAVAILABLE")
    if s.suspicious:
        reasons.append("SUSPICIOUS_TOKEN")
    if s.execution_model == "UNAVAILABLE":
        reasons.append("EXECUTION_UNAVAILABLE")
    if f.liquidity_change is not None and f.liquidity_change < -0.2:
        reasons.append("LIQUIDITY_WITHDRAWAL")
    if f.volatility is not None and f.volatility > 0.025:
        reasons.append("EXTREME_VOLATILITY")
    return ("BLOCK" if reasons else "NORMAL", reasons)


def regime(s: MarketSnapshot, f: FeatureVector) -> Assessment:
    guard, reasons = guardian(s, f)
    if guard == "BLOCK":
        return Assessment(regime="NO_TRADE", score=0, reason_codes=reasons)
    if f.return_window is None:
        return Assessment(regime="UNCLASSIFIED", score=0, reason_codes=["WARMUP"])
    if f.return_window < -0.02:
        return Assessment(regime="DEFENSIVE", score=0.8, reason_codes=["NEGATIVE_MOMENTUM"])
    if f.return_window > 0.02 and (f.consistency or 0) >= 0.75:
        return Assessment(
            regime="MOMENTUM_EXPANSION",
            score=min(1, f.consistency or 0),
            reason_codes=["CONSISTENT_MOMENTUM"],
        )
    return Assessment(regime="SHORT_TERM_OPPORTUNITY", score=0.5, reason_codes=["RANGE_BASELINE"])


def dispatch(
    s: MarketSnapshot, f: FeatureVector, r: Assessment, cfg: Settings, cost: float
) -> list[StrategySignal]:
    signals = []
    for name, enabled, selected in [
        ("AGGRESSOR", cfg.aggressor_enabled, r.regime == "MOMENTUM_EXPANSION"),
        ("SCALPING", cfg.scalping_enabled, r.regime == "SHORT_TERM_OPPORTUNITY"),
    ]:
        reasons = []
        if not enabled:
            reasons.append("STRATEGY_SUSPENDED")
        if not selected:
            reasons.append("REGIME_MISMATCH")
        if f.return_window is None or f.return_window <= cost + float(cfg.uncertainty_margin):
            reasons.append("EDGE_NOT_ESTABLISHED_AFTER_COSTS")
        if (f.return_window or 0) > 0.15:
            reasons.append("LATE_ENTRY")
        if f.imbalance is None or f.imbalance < 0.1:
            reasons.append("BUY_PRESSURE_UNCONFIRMED")
        if f.volume_change is None or f.volume_change <= 0:
            reasons.append("VOLUME_UNCONFIRMED")
        signals.append(
            StrategySignal(
                strategy=name,
                action="WAIT" if reasons else "PROPOSE_ENTRY",
                score=r.score if not reasons else 0,
                reason_codes=reasons or ["BASELINE_TEST_HYPOTHESIS"],
            )
        )
    g, reasons = guardian(s, f)
    signals.append(
        StrategySignal(
            strategy="GUARDIAN",
            action="REJECT" if g == "BLOCK" else "WAIT",
            score=1 if g == "BLOCK" else 0,
            reason_codes=reasons or ["NO_OBSERVED_BLOCKERS"],
        )
    )
    return signals


def council(signals: list[StrategySignal]) -> tuple[str, list[str]]:
    if signals[-1].action == "REJECT":
        return "SKIP", signals[-1].reason_codes
    for s in signals[:-1]:
        if s.action == "PROPOSE_ENTRY":
            return s.strategy, s.reason_codes
    return "SKIP", list(dict.fromkeys(r for s in signals[:-1] for r in s.reason_codes))
