# Architecture and explicit tradeoffs

Single local FastAPI process + one worker thread for durable market event processing. Next.js App Router UI uses TanStack Query for finite history windows and a single authenticated WebSocket for state. No independent strategy processes; all rules share a FeatureVector.

## Modules

| Module | Responsibility |
|---|---|
| `domain.py` | Validated configuration, market and decision contracts, Decimal precision |
| `providers.py` | Synthetic market, documented DexScreener batch source, fixed read-only RPC |
| `analytics.py` | Bounded rolling features, regime, strategy dispatcher, Guardian, council |
| `risk.py` | Independent fourteen gates plus cash reserve, allocation, estimated cost |
| `execution.py` | Abstract adapter and only PaperExecutionAdapter |
| `engine.py` | Atomic state machine, fills, portfolio, event journal, recovery |
| `database.py` | SQLAlchemy Core schema and transaction store |
| `main.py` | Bounded async queue, APIs, origin/session protection, telemetry, WS fanout |
| `learning.py` | Pure offline validation helpers; no training in runtime |

The pipeline writes market snapshot, features, regime, signals, decision, risk, orders/fills, portfolio and ledger projection in one transaction. A failure rolls back both database changes and in-memory state/history, then stops entries. A decision ID correlates the pipeline stages; fills reference their order and decision. Unique event/session keys prevent duplicate processing, unique fill keys prevent duplicate settlement.

After process restart, open positions and financial state restore from the projection. Pending orders receive CANCELLED journal entries. Trading remains stopped and feature windows rewarm; protective exits still operate when usable data returns. SQLite uses WAL + FULL synchronization. PostgreSQL support uses SQLAlchemy + psycopg; no distributed lock or multi-worker support.

## Accounting and execution

Monetary ledger settlements round half-even at 8 USD decimal places. Quantity and pricing use Decimal without conversion through float. Statistical features explicitly convert price ratios to float. Buy: debit notional + entry fee, quantity = notional / adverse fill price. Sell: credit rounded quantity × adverse exit price minus exit fee. Realized P&L = net exit proceeds − entry cost basis. Gross realized P&L includes adverse fill prices but excludes explicit fees. Slippage cost is a diagnostic, **not** subtracted again from already adverse fill-price P&L.

Unrealized P&L uses estimated net exit proceeds, not last-price-only valuation. Equity = cash + net liquidation estimates. Exposure limits use entry cost basis including fees; absolute budgets never automatically grow. Daily loss uses UTC day-start net equity; daily boundary is documented and independent from browser display timezone. Rollovers need continuous observations to obtain a current mark. The current-day baseline starts at recovery's retained ledger until a new-day event.

Orders require a later market event, minimum 1-second delay and an unexpired signal. Entries rerun mandatory risk checks and Guardian before filling. Stop-loss/take-profit create exit requests that also wait for later usable data; no instantaneous guaranteed stop. Empty/invalid execution data produces FAILED, stale signals EXPIRED. V1 does not implement partial fills: CREATED/VALIDATED are logical synchronous stages, only PENDING and terminal states are persisted. There is no simulated random fill probability.

Performance modes change observation cadence / UI push cadence, not formulas or thresholds. Since sampling windows contain 12 observations, their wall-clock duration changes with cadence; this affects observed signals and is not claimed equivalent to a tick stream.

## Schema limitation

The initial schema is an indexed append-only JSON journal with a transactional JSON ledger projection, not the fully normalized target schema requested in section 20. Decimal values are serialized strings. Reserved entity tables exist for future sources but do not imply implemented wallet/model data. Migration 0001 freezes the schema independently of current application metadata; upgrade/downgrade/upgrade is tested on SQLite. No untrusted SQL or serialized executable models are used.

Runtime memory is bounded (12 observations per observed pool, 5000 latency samples, 256 queued market events, one pending UI state per client, 8 WS clients). Supported sources constrain token count. Journal retention is **not yet automated**; long-running deployment requires monitored disk usage and a tested archival policy. No retention UI control is exposed as if it worked.
