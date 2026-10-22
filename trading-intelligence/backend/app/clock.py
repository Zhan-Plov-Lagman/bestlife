"""Market logic uses an injected clock; scheduling/telemetry use monotonic time."""

from datetime import datetime
from typing import Protocol

from .domain import now


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return now()


class ReplayClock:
    def __init__(self, at: datetime):
        if at.tzinfo is None:
            raise ValueError("Timezone required")
        self.at = at

    def now(self) -> datetime:
        return self.at

    def advance(self, at: datetime) -> None:
        if at < self.at:
            raise ValueError("REPLAY_TIME_REVERSED")
        self.at = at
