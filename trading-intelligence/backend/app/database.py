"""Transactional single-writer store. Decimal values encoded as strings in JSON."""

import os
from typing import Any

from sqlalchemy import JSON, Column, Integer, MetaData, String, Table, create_engine, event, select
from sqlalchemy.engine import Connection

metadata = MetaData()
state_table = Table(
    "app_settings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("payload", JSON, nullable=False),
)
events = Table(
    "system_events",
    metadata,
    Column("id", String(200), primary_key=True),
    Column("kind", String(40), index=True),
    Column("at", String(40), index=True),
    Column("payload", JSON, nullable=False),
)
records: dict[str, Table] = {}
for name in (
    "market_snapshots",
    "feature_snapshots",
    "market_regimes",
    "strategy_signals",
    "decisions",
    "risk_assessments",
    "paper_orders",
    "paper_fills",
    "paper_positions",
    "portfolio_snapshots",
    "model_versions",
    "model_evaluations",
    "backtest_runs",
    "provider_health",
    "tokens",
    "pools",
    "wallet_observations",
):
    records[name] = Table(
        name,
        metadata,
        Column("id", String(200), primary_key=True),
        Column("session_id", String(40), nullable=False, index=True),
        Column("at", String(40), nullable=False, index=True),
        Column("payload", JSON, nullable=False),
    )
seen = Table(
    "market_events",
    metadata,
    Column("id", String(200), primary_key=True),
    Column("session_id", String(40), nullable=False),
    Column("at", String(40), nullable=False, index=True),
)


def db_engine(url: str | None = None):
    url = url or os.environ.get("DATABASE_URL") or "sqlite:///./trading.db"
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 10}
        if url.startswith("sqlite")
        else {},
        pool_pre_ping=True,
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def setup(dbapi_connection, _):
            dbapi_connection.execute("PRAGMA journal_mode=WAL")
            dbapi_connection.execute("PRAGMA synchronous=FULL")

    return engine


def write_record(
    conn: Connection, name: str, key: str, session: str, at: str, payload: dict[str, Any]
) -> None:
    conn.execute(records[name].insert().values(id=key, session_id=session, at=at, payload=payload))


class Store:
    def __init__(self, url: str | None = None):
        self.engine = db_engine(url)

    def load(self) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            return conn.execute(
                select(state_table.c.payload).where(state_table.c.id == 1)
            ).scalar_one_or_none()

    def save(self, conn: Connection, payload: dict[str, Any]) -> None:
        if conn.execute(select(state_table.c.id).where(state_table.c.id == 1)).first():
            conn.execute(state_table.update().where(state_table.c.id == 1).values(payload=payload))
        else:
            conn.execute(state_table.insert().values(id=1, payload=payload))

    def recent(self, name: str, session: str, limit: int = 100) -> list[dict[str, Any]]:
        table = records[name]
        with self.engine.connect() as conn:
            return list(
                conn.execute(
                    select(table.c.payload)
                    .where(table.c.session_id == session)
                    .order_by(table.c.at.desc())
                    .limit(limit)
                ).scalars()
            )
