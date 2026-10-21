"""Frozen append-only schema, independent of application metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None
RECORDS = (
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
)


def upgrade():
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("payload", sa.JSON, nullable=False),
    )
    op.create_table(
        "system_events",
        sa.Column("id", sa.String(200), primary_key=True),
        sa.Column("kind", sa.String(40)),
        sa.Column("at", sa.String(40)),
        sa.Column("payload", sa.JSON, nullable=False),
    )
    for field in ("kind", "at"):
        op.create_index(f"ix_system_events_{field}", "system_events", [field])
    op.create_table(
        "market_events",
        sa.Column("id", sa.String(200), primary_key=True),
        sa.Column("session_id", sa.String(40), nullable=False),
        sa.Column("at", sa.String(40), nullable=False),
    )
    op.create_index("ix_market_events_at", "market_events", ["at"])
    for name in RECORDS:
        op.create_table(
            name,
            sa.Column("id", sa.String(200), primary_key=True),
            sa.Column("session_id", sa.String(40), nullable=False),
            sa.Column("at", sa.String(40), nullable=False),
            sa.Column("payload", sa.JSON, nullable=False),
        )
        for field in ("session_id", "at"):
            op.create_index(f"ix_{name}_{field}", name, [field])


def downgrade():
    for name in reversed(RECORDS):
        op.drop_table(name)
    for name in ("market_events", "system_events", "app_settings"):
        op.drop_table(name)
