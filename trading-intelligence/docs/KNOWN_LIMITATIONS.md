# Known limitations — v1.1

- This stage delivers P0 recovery/accounting/access fixes and substantial P1 profiling/batching/replay/strategy work. It is not the full v1.1 specification.
- Sustainable 1000 events/s, 24-hour soak and active-fill load capacity are unproven; see measured overload results in PERFORMANCE.md. Queue backpressure retains events in a live run but cannot make an overloaded consumer keep pace.
- SQLite journal is indexed JSON; no schema change was made, migration 0001 remains. Retention_days is not enforced. No automatic archive, Parquet export, size cap or verified backup/restore tool. Do not delete current-session ledger/dedup records.
- No complete Testing Gateway, forward-paper/external adapter, Shadow Mode, comparative statistics UI or ML registry/promotion system. Existing learning helpers remain offline evaluation utilities only.
- No verified historical dataset, calibrated probability, trained model, actual fill, real wallet or market profitability evidence.
- Replay accepts synthetic inputs only. Provenance cannot establish the truth of user-supplied data. UUIDs vary between runs; deterministic digest covers normalized decisions and finances.
- All-or-none execution, no partial fill model. Exit depth cap is an assumption. Fresh marks are valuation estimates, not guarantees that a full position can be sold.
- Recovery rewarms features and pauses entries. Interrupted uncommitted observations are not replayed from a durable queue. Tamper detection is accounting consistency, not cryptographic audit integrity.
- Local OS user is trusted. Remote credential policy is groundwork; remote UI/login, TLS, multi-user permissions and public deployment are not shipped.
- PostgreSQL runtime/recovery and Linux systemd were not executed. Local writer lease is not a distributed lock. Python 3.12 compatibility not run; tested on 3.14.3.
- Remaining test-tool warnings: Starlette/httpx deprecation; Vitest config-loader notice and shutdown timeout despite successful exit. Neither is reported as a passed long-run resource test.
