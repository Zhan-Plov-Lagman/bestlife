"""Strict contracts. Money never travels through binary floats in the ledger."""

from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

D = Decimal


def usd(value: Decimal) -> Decimal:
    """Ledger precision: 10^-8 USD, deterministic bankers rounding."""
    return value.quantize(D("0.00000001"), rounding=ROUND_HALF_EVEN)


def now() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Settings(StrictModel):
    initial_balance: Decimal = Field(default=D("70"), ge=10, le=100000)
    max_position: Decimal = Field(default=D("7"), gt=0, le=1000)
    max_exposure: Decimal = Field(default=D("21"), gt=0, le=10000)
    max_positions: int = Field(default=3, ge=1, le=20)
    max_drawdown: Decimal = Field(default=D("0.1"), gt=0, le=D("0.5"))
    daily_loss_limit: Decimal = Field(default=D("3.5"), gt=0, le=1000)
    min_liquidity: Decimal = Field(default=D("25000"), gt=0)
    max_cost_fraction: Decimal = Field(default=D("0.025"), gt=0, le=D("0.1"))
    fee_rate: Decimal = Field(default=D("0.003"), ge=0, le=D("0.05"))
    network_fee: Decimal = Field(default=D("0.005"), ge=0, le=10)
    slippage: Decimal = Field(default=D("0.002"), ge=0, le=D("0.1"))
    uncertainty_margin: Decimal = Field(default=D("0.005"), ge=0, le=D("0.1"))
    stop_loss: Decimal = Field(default=D("0.04"), gt=0, le=D("0.5"))
    take_profit: Decimal = Field(default=D("0.06"), gt=0, le=1)
    freshness_seconds: int = Field(default=30, ge=5, le=120)
    signal_ttl_seconds: int = Field(default=20, ge=3, le=120)
    execution_delay_seconds: int = Field(default=1, ge=1, le=10)
    performance: Literal["ECO", "BALANCED", "PERFORMANCE"] = "BALANCED"
    provider: Literal["DEMO", "DEXSCREENER"] = "DEMO"
    token_mints: list[str] = Field(default_factory=list, max_length=30)
    aggressor_enabled: bool = True
    scalping_enabled: bool = True
    retention_days: int = Field(default=7, ge=1, le=90)
    strategy_version: Literal["baseline-v1", "baseline-v1.1"] = "baseline-v1.1"

    @field_validator("token_mints")
    @classmethod
    def valid_mints(cls, values: list[str]) -> list[str]:
        import re

        if any(not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", v) for v in values):
            raise ValueError("Expected Solana base58 mint addresses")
        return list(dict.fromkeys(values))


class MarketSnapshot(StrictModel):
    event_id: str = Field(min_length=1, max_length=200)
    event_time: datetime
    received_time: datetime = Field(default_factory=now)
    processing_time: datetime | None = None
    provider: Literal["DEMO", "DEXSCREENER"]
    chain: Literal["solana"] = "solana"
    token_mint: str = Field(min_length=1, max_length=64)
    symbol: str = Field(min_length=1, max_length=30)
    pool_address: str = Field(min_length=1, max_length=100)
    price: Decimal = Field(gt=0)
    liquidity: Decimal = Field(ge=0)
    volume: Decimal = Field(ge=0)
    buys: int | None = Field(default=None, ge=0)
    sells: int | None = Field(default=None, ge=0)
    data_quality_status: Literal["VALID", "UNAVAILABLE", "STALE", "INVALID"] = "VALID"
    # Only deterministic synthetic scenarios supply these in v1.
    token_safety_known: bool = False
    suspicious: bool | None = None
    execution_model: Literal["SYNTHETIC_CONSERVATIVE", "UNAVAILABLE"] = "UNAVAILABLE"

    @field_validator("event_time", "received_time")
    @classmethod
    def timezone_required(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Timezone required")
        return v.astimezone(UTC)


class FeatureVector(StrictModel):
    version: str = "features-v1.1"
    latest_return: float | None = None
    pressure_consistency: float | None = None
    sample_interval_seconds: float | None = None
    return_window: float | None = None
    acceleration: float | None = None
    consistency: float | None = None
    volatility: float | None = None
    liquidity_change: float | None = None
    volume_change: float | None = None
    imbalance: float | None = None
    observations: int = 0
    wallet_concentration: float | None = None


class Assessment(StrictModel):
    regime: str
    score: float = Field(ge=0, le=1)
    model_version: str = "baseline-v1"
    reason_codes: list[str]


class StrategySignal(StrictModel):
    strategy: str
    action: Literal["WAIT", "PROPOSE_ENTRY", "PROPOSE_EXIT", "REJECT"]
    score: float = Field(ge=0, le=1)
    reason_codes: list[str]


class RiskAssessment(StrictModel):
    status: Literal["APPROVED", "REJECTED", "SYSTEM_HALTED"]
    reason_codes: list[str]
    checks: dict[str, bool]
