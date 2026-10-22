# Performance measurements — v1.1, 2026-10-22

Windows 11 build 26200, AMD64 Family 25 Model 68, 16 logical CPUs, Python 3.14.3. SQLite WAL + synchronous FULL throughout. Disk model and competing OS activity were not measured. No claim about other machines or PostgreSQL.

## Profiling before optimization

Same-stage baseline commit: `6dbdd6e5126a365c03aaca85498f10e3c213d19c`. Raw: docs/v11-baseline.json. cProfile of 1000 synchronous single-event writes: 5.782 seconds, record/SQLAlchemy about 1.755 seconds, SQLite commit 1.129 seconds, deepcopy 0.901 seconds (nested totals are not additive). This established copying, statement construction and per-event durability costs as actual targets. Raw profiles: docs/v11-profile-before.txt and docs/v11-profile-after.txt.

Changes: identity-cached validated settings; selective rollback copies; reusable parameterized inserts; UPDATE-first projection save; bounded sequential batch; grouped secondary journal inserts in the same transaction. Order/fill/position writes remain synchronous and atomic. No dropped audit rows and no weaker SQLite synchronization. Final single-event cProfile: 3.105 seconds, commit still 1.019 seconds. Profiling overhead means these are not normal throughput measurements.

## Short comparable load: 1000 events offered at 1000/s

| Metric | Before | After |
|---|---:|---:|
| Achieved events/s | 262.71 | 968.87 |
| End-to-end p95, including producer delay/backpressure | 2637.78 ms | 27.98 ms |
| Events consumed / dropped | 1000 / 0 | 1000 / 0 |
| RSS growth | 2.96 MiB | 2.94 MiB |

After raw file: benchmarks/runs/v11-after.json. Before uses one transaction/event, after drains up to 16. The new harness advances event timestamps with offered time so long runs do not turn stale solely due to a timestamp generator defect. Features remain synthetic; this is not an exact byte-identical workload or a statistical performance guarantee. The earlier 218/s figure belongs to the previous development run, not this measured baseline.

Do NOT compare old processing p95 4.53 ms directly with new 0.80 ms: the former included commit, the latter measures event computation and immediate SQL, excluding final batch persistence. After batch-total p95 is 11.92 ms and persistence-batch p95 7.69 ms. End-to-end is the meaningful complete-path comparison here.

## Sustained offered load: 30 seconds at each rate

| Offered /s | Events | Achieved /s | E2E p95 ms | Queue wait p95 ms | Persistence batch p95 ms | Active CPU, one core | RSS growth MiB | Dropped |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 3000 | 99.99 | 15.48 | 3.71 | 2.67 | 29.63% | 3.43 | 0 |
| 500 | 15000 | 499.74 | 24.98 | 10.36 | 14.67 | 86.00% | 5.93 | 0 |
| 1000 | 30000 | 792.33 | 7342.80 | 377.21 | 41.90 | 84.56% | 8.10 | 0 |

1000/s sustained is **not achieved**: the 30-second offer takes 37.86 seconds to drain. Queue bounded at 256 applies backpressure; offered-time latency includes time before enqueue, explaining why it exceeds queue wait. The short 969/s result must not be substituted for sustained capacity. The measured persistence tail suggests durable I/O/checkpoint/serialization pressure; attributing it specifically to hardware or WAL checkpoints needs deeper tracing. These runs used an inactive-entry engine processing full decisions/journals, not active fills or a full browser/server. Signal-to-order/fill latency under active load remains unmeasured.

Raw suite: benchmarks/runs/v11-100.json, v11-500.json, v11-1000.json. Run `scripts/benchmark.ps1 -Seconds 30` (1..60 supported). Stage/event distributions keep the latest 5000 samples; end-to-end, ingestion, queue wait and loop lag cover all events. JSON contains feature, strategy, risk, persistence, batch, ingestion, queue and loop p50/p95/p99, CPU and RSS. CPU is process CPU-time delta / wall elapsed expressed as percent of one core. No full-app idle or long-run leak guarantee follows from a short idle sample or net RSS growth.

Limits preserved: 12 observations/pool, 256 queued events, 5000 samples/metric, one writer, batch <=16 runtime / <=32 engine, eight WS clients, one coalesced UI snapshot/client. UI coalescing never means ledger event dropping. Future work: active-fill workload, commit/checkpoint tracing, slower-disk tests, overload admission policy, and 24-hour soak. Disk journals still grow without automatic retention.
