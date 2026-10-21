# Measured performance

Reproduce from repository root: `.venv/Scripts/python benchmarks/run.py --events 1000`.

Initial measurement on 2026-10-22, Windows 11 build 26200, AMD64 Family 25 Model 68, 16 logical CPUs, Python 3.14.3. SQLite WAL, synchronous FULL, one transaction per event. Hardware model is reported exactly as supplied by the OS; disk hardware was not measured.

| Metric | Measured |
|---|---:|
| Synthetic events offered | 1000 at target 1000/s |
| Consumed / dropped | 1000 / 0 |
| Achieved throughput | 217.98 events/s |
| Processing p50 / p95 / p99 | 3.97 / 5.71 / 10.27 ms |
| End-to-end p95 including backpressure | 3385.89 ms |
| Event loop lag p50 / p95 / p99 | 1.74 / 5.01 / 8.84 ms |
| Idle core CPU, 2-second core-only sample | 0.0% |
| Core RSS before / after | 59.89 / 63.13 MB |
| Memory growth over 1000 events | 3.23 MB |

Raw output: `benchmarks/runs/latest.json`. This is a short core benchmark, **not** a full application idle/soak guarantee. The idle CPU sample excludes HTTP server and browser; server telemetry is separately exposed in System monitor. Data was generated for correctness/load testing only; no return claim follows from it.

The 1000 events/s target is **not achieved**. The producer blocks on a 256-item queue, preserving events but increasing latency. The likely bottleneck is per-event SQL serialization and FULL durable commits; exact CPU-vs-disk attribution requires a profiler beyond these timings. No claim of full optimization is made. Next work: transaction batching with preserved order and idempotency, cached validated configuration, structured typed ledger snapshots instead of deepcopy, separate bounded telemetry writes, PostgreSQL measurements and a 24-hour memory soak. Do not weaken ledger durability merely to improve a benchmark number.

Current limits: 4 HTTP pooled connections, provider interval ≥1 second, Dex observations ≥10 seconds and TTL 10 seconds, one market consumer, 12 samples/pool, up to 30 configured mints, 5000 latency samples. UI publishes at 3 / 1 / 0.5 seconds for ECO / BALANCED / PERFORMANCE; synthetic scanning at 5 / 2 / 1 seconds. A UI queue coalesces snapshots; the backend market queue never intentionally drops critical events.

No GPU framework or runtime ML dependencies are loaded. Training is offline only. NumPy/Polars/sklearn/LightGBM were not installed without a real training workload; offline helpers currently use Python's standard library.
