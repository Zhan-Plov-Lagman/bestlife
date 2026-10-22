# Testing Gateway — status and offline replay

The interactive Testing Gateway is NOT implemented in this stage. No placeholder session buttons or fabricated results were added. Demo runtime and the offline deterministic replay below work; persisted research-session API, Historical data adapter, Solana Forward Paper adapter and External Demo interface remain pending.

## Working replay

Run `.venv/Scripts/python scripts/replay.py dataset.jsonl --output research/run-001 --scenario BASE` from the application root. Input is JSONL of the existing strict MarketSnapshot contract. Output directory must not exist. Maximum input 64 MiB / 100000 events; chronological event time and unique event IDs required. Only DEMO is accepted because observed sources currently lack execution evidence.

Each run owns a new SQLite database, features, settings, virtual clock, $70 default account and journal. It does not access the runtime database or network. Dataset SHA-256, settings, strategy version, reason counts, normalized decisions, net equity/cash/realized/fees/drawdown and result SHA-256 are stored in report.json. Result digest excludes random audit IDs but includes ordered decisions and financial summary. Source snapshots are copied, not mutated. Replay ends with open positions explicitly marked; no fake end liquidation.

Scenarios are SYNTHETIC assumptions, never observed executions:

- BASE: configured fees/slippage, next-observation delay.
- ADVERSE: slippage at least 1%, fee at least 0.6%, network fee at least $0.01, delay at least 3 seconds; unchanged risk budgets, so costly opportunities may be rejected entirely.
- ILLIQUID: supplied liquidity multiplied by 0.001; hard safety rules can prevent entry or full exit.

Execution remains conservative all-or-none: no depth data means partial fills would be unsupported fabrication. Exits above 1% of supplied liquidity are blocked with intent retained; this cap is a synthetic feasibility rule, not real executable depth. Every fill carries SYNTHETIC provenance. UNAVAILABLE sources are blocked; ESTIMATED/OBSERVED fill sources are not implemented.

Use `--strategy baseline-v1` or `baseline-v1.1` to run separate configurations on the same input. This provides reproducible raw research artifacts, not a statistical comparison engine. Replay tests cover deterministic outcomes, isolation, input immutability, stress budget preservation, duplicate rejection and reverse-time rejection.
