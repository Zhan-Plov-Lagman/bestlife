"""Conservative all-or-none next-observation simulator; never signs transactions."""

from decimal import Decimal
from typing import Protocol

from .domain import D, MarketSnapshot, Settings


class ExecutionAdapter(Protocol):
    def quote(
        self, side: str, amount: Decimal, snapshot: MarketSnapshot, cfg: Settings
    ) -> tuple[Decimal, Decimal]: ...


class PaperExecutionAdapter:
    def quote(
        self, side: str, amount: Decimal, snapshot: MarketSnapshot, cfg: Settings
    ) -> tuple[Decimal, Decimal]:
        if snapshot.execution_model == "UNAVAILABLE" or snapshot.liquidity <= 0:
            raise ValueError("EXECUTION_UNAVAILABLE")
        impact = min(D("0.25"), amount / snapshot.liquidity)
        multiplier = 1 + cfg.slippage + impact if side == "BUY" else 1 - cfg.slippage - impact
        price = snapshot.price * multiplier
        return price, amount * cfg.fee_rate + cfg.network_fee
