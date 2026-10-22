"""Rebuild cash and open inventory from immutable fills; never silently repair."""

from decimal import InvalidOperation

from sqlalchemy import select

from .database import records
from .domain import D, usd


def reconcile(conn, state: dict) -> list[str]:
    table = records["paper_fills"]
    fills = conn.execute(
        select(table.c.payload)
        .where(table.c.session_id == state["session_id"])
        .order_by(table.c.at, table.c.id)
    ).scalars()
    cash, fees, realized = D(state["starting_balance"]), D(0), D(0)
    inventory: dict = {}
    reasons = []
    try:
        for f in fills:
            qty, price, fee = D(f["quantity"]), D(f["price"]), D(f["fee"])
            amount = D(f.get("notional", str(usd(qty * price))))
            mint = f["token_mint"]
            if qty <= 0 or price <= 0 or fee < 0 or amount < 0:
                return ["LEDGER_INVALID_FILL"]
            if f["side"] == "BUY":
                if mint in inventory:
                    return ["LEDGER_DUPLICATE_ENTRY"]
                inventory[mint] = {"quantity": qty, "cost_basis": amount + fee}
                cash -= amount + fee
            elif f["side"] == "SELL":
                if mint not in inventory or qty != inventory[mint]["quantity"]:
                    return ["LEDGER_UNMATCHED_EXIT"]
                realized += amount - fee - inventory.pop(mint)["cost_basis"]
                cash += amount - fee
            else:
                return ["LEDGER_INVALID_SIDE"]
            fees += fee
            if cash < 0:
                return ["LEDGER_NEGATIVE_CASH"]
        for key, actual in [("cash", cash), ("fees", fees), ("realized", realized)]:
            if usd(D(state[key])) != usd(actual):
                reasons.append("LEDGER_" + key.upper() + "_MISMATCH")
        if inventory.keys() != state["positions"].keys():
            reasons.append("LEDGER_POSITION_SET_MISMATCH")
        for mint in inventory.keys() & state["positions"].keys():
            p = state["positions"][mint]
            if D(p["quantity"]) != inventory[mint]["quantity"] or usd(D(p["cost_basis"])) != usd(
                inventory[mint]["cost_basis"]
            ):
                reasons.append("LEDGER_POSITION_MISMATCH")
        equity = D(state["cash"]) + sum(
            (D(p["net_liquidation_value"]) for p in state["positions"].values()), D(0)
        )
        if usd(equity) != usd(D(state["equity"])):
            reasons.append("LEDGER_EQUITY_MISMATCH")
        snapshots = records["portfolio_snapshots"]
        last_id = (state.get("last_decision") or {}).get("decision_id")
        latest = conn.execute(
            select(snapshots.c.payload)
            .where(snapshots.c.session_id == state["session_id"])
            .where(snapshots.c.id == last_id)
            .order_by(snapshots.c.at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if last_id and latest is None:
            reasons.append("LEDGER_SNAPSHOT_MISSING")
        if latest and usd(D(latest["equity"])) != usd(D(state["equity"])):
            reasons.append("LEDGER_SNAPSHOT_MISMATCH")
        if latest:
            for key in ("cash", "fees", "realized"):
                if key in latest and usd(D(latest[key])) != usd(D(state[key])):
                    reasons.append("LEDGER_SNAPSHOT_" + key.upper() + "_MISMATCH")
    except (KeyError, InvalidOperation, ValueError, TypeError):
        reasons.append("LEDGER_MALFORMED")
    return sorted(set(reasons))
