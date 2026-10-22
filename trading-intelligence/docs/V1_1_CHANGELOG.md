# v1.1 engineering report — 2026-10-22

Starting commit: 6dbdd6e5126a365c03aaca85498f10e3c213d19c; working tree was clean. Existing implementation retained. Scope delivered: P0 recovery/accounting/access hardening and substantial P1 work. Full Testing Gateway/Shadow/ML requirements are deferred, as permitted by the task's priority rule.

## Findings and fixes

- Restart discarded pending exits. BUY now cancels; SELL retains intent and identity, requires new observations, rechecks exit feasibility and renews expired intent only on valid data. Kill/pause preserve exits.
- No accounting reconstruction existed. Reconciliation now rebuilds cash, fees, realized P&L and positions from fills, checks equity and exact last-decision snapshot, and blocks clear-halt on mismatch. Duplicate settlement and negative cash have explicit guards.
- Entry constraints could obstruct protective actions. Independent exit checks cover freshness, provenance, liquidity and fee funding without applying entry-only loss/strategy/kill limits.
- Local CSRF was insufficient for future remote exposure. Added expiring sessions, actual-body limit, WS handshake/connection limits and separate remote read/control credentials; remote remains disabled.
- Profiling identified deepcopy, SQL construction and commits. Added cached settings, selective rollback copies, bounded ordered batches and grouped telemetry in the same durable transaction. Failed reset also restores feature/UI state.
- Added virtual-clock isolated replay, deterministic economic hashes, explicit synthetic stress assumptions and distinct momentum/scalping baselines. No trained models or observed fills claimed.
- Native Windows setup/start/test/benchmark/stop scripts and OS writer lease replace Docker as primary workflow. Existing Docker files retained as optional compatibility examples. Linux systemd guidance only; no deployment.

## Changed files

Backend: engine.py, analytics.py, domain.py, risk.py, database.py, main.py; new clock.py, reconciliation.py, security.py, strategies.py, instance.py, replay.py. Tests: conftest.py, test_recovery.py, test_security.py, test_batch.py, test_replay.py. Frontend: lib/api.ts session renewal/contracts; components/terminal.tsx recovery banner/version and accurate metric labels. Scripts: common/setup/dev/test/benchmark/stop.ps1, native_service.py, replay.py and compatibility start.ps1. Benchmarks: run.py, profile_pipeline.py, raw JSON and profiles. Documentation: README, ARCHITECTURE, SECURITY, PERFORMANCE, ROADMAP, VERIFICATION, this report, TESTING_GATEWAY, SHADOW_MODE, NATIVE_DEPLOYMENT, KNOWN_LIMITATIONS. Browser screenshot regenerated.

## Verification

Final backend: 53 pytest passed in 6.25 s, Ruff passed, mypy passed across 16 source files. TypeScript passed; production Next build passed; Vitest 1 passed; Playwright/Edge 1 passed. Native launch, second-instance rejection and owned graceful stop passed. setup -BackendOnly passed against existing environment; clean-machine setup and full reinstall not repeated. Migrations covered by existing regression tests. Test warnings: Starlette/httpx deprecation and Vitest config/shutdown notice. Initial import/type-check failures were corrected; no final functional test failure remains.

Short 1000-event baseline: 262.71 → 968.87 events/s, end-to-end p95 2637.78 → 27.98 ms, zero drops. 30-second offers at 100/500/1000 events/s achieved 99.99/499.74/792.33, zero drops; overloaded 1000/s E2E p95 7342.80 ms. Sustainable 1000/s is NOT met. Processing metric definition changed; see PERFORMANCE.md before comparing it. Long-run timestamp generation defect found and corrected before final suite. No active-fill throughput or 24-hour soak claim.

## Unfinished and next phase

Testing Gateway API/UI, online Shadow and paired reports, verified historical/forward execution adapters, partial fills with real depth, durable research-session lifecycle, dataset/model registry and manual promotion remain unimplemented. Backup/restore, safe retention, PostgreSQL recovery, Linux runtime and full remote security require tests. Replay currently accepts synthetic data only. Future ML first needs verified provenance, leakage-controlled historical labels and reproducible out-of-sample evaluation; no training performed.

No fresh external integration checks in this stage. Earlier DexScreener and Solana read-only evidence remains in docs/provider-check.json. No real wallets, transactions, cloud deployment, commit or push. Test servers stopped gracefully after verification.
