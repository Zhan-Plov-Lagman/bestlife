# Verification report — 2026-10-22

## Scope

User story: local UI → session-protected API → persisted paper ledger → pushed state and explainable journal. Verified implementation is a working initial vertical slice. It does **not** meet every Initial Release v1.0 requirement in PROJECT_SPEC.md.

| Boundary / check | Result and evidence |
|---|---|
| Python runtime | Python 3.14.3, dependencies installed in project `.venv` |
| Backend launch | Uvicorn startup complete, loopback port 8000, one worker |
| SQLite migrations | Upgrade → downgrade → upgrade test passes; current revision 0001 |
| Backend tests | 27 passed (money, pipeline, kill, stop-loss, fees, stale-data/marks, risk, liquidity decline at fill, idempotency, recovery, rollback, provider failures/cache, API origin/session/WS, offline validation, migrations, initial-balance setting isolation) |
| Ruff | All checks passed; formatted sources |
| mypy | No issues in 10 source files; `check_untyped_defs`, not full strict Python typing |
| Frontend build | Next.js 16.4.2 production build with Webpack succeeds; static route `/` |
| TypeScript | `tsc --noEmit` succeeds with strict mode |
| Vitest | 1 formatting/absence-of-data test passes |
| Playwright / Edge | Start → pause → kill → journal expansion → clear halt, 1 test passes |
| Browser visuals | Desktop screenshot `terminal-desktop.png`; narrow in-app browser inspected, responsive navigation and panels visible |
| Real WebSocket transport | Accepted `/ws`; pushed state reaches browser. Initial missing driver found by E2E and fixed by adding websockets |
| Actual Demo provider integration | 3 positions opened and 3 closed on paced observations; cash/P&L invariant and restart recovery verified; raw `demo-scenario.json` |
| DexScreener read-only request | Public wrapped-SOL query returned one normalized snapshot; trading remains disabled; `provider-check.json` |
| Solana RPC read-only request | `getHealth` returned `ok`; `provider-check.json` |
| Python dependency audit | Locked application/test dependencies scanned with pip-audit 2.10.1; no known vulnerabilities; `python-audit.json` |
| npm audit | 0 known vulnerabilities after updating Vitest; package-lock retained |
| Core load test | 1000 events, 0 dropped, about 218/s; target 1000/s **not met**; see PERFORMANCE.md |
| PostgreSQL / Compose | Configuration provided; runtime **not tested**, Docker unavailable |
| Python 3.12 | Docker target configured, not executed here; local compatibility verified only on 3.14.3 |

Synthetic scenario cash/returns are engineering evidence of arithmetic and lifecycle only; they are not actual market returns and are not displayed as live performance.

## Fixes discovered during verification

1. Decimal residual digits broke an exact conservation assertion; monetary settlements now use deterministic 8-decimal USD rounding.
2. Allocation originally reserved cash fees but not exposure-limit fees; both now reserve fees and have a regression test.
3. Pending entries could encounter liquidity withdrawal at execution; Guardian is rerun before fill and tested.
4. Stale marks on other portfolio tokens now independently block new entries.
5. Pausing/killing entries originally cancelled exit requests; existing exits are now preserved, tested.
6. Uvicorn minimal install omitted a WebSocket implementation. In-process API tests passed but the real browser failed; added `websockets` and confirmed the browser flow.
7. The installed Turbopack could not connect to its stylesheet worker even outside the sandbox; the supported Webpack build completes successfully.
8. Initial Vitest 3 dependency tree contained known vulnerabilities; upgraded to Vitest 5.0.5 and reran its test and npm audit.

## Verification limits

Short test runs do not establish long-running availability, expected profit, complete scam detection or safety of live capital. No live execution exists. No historical ML data, trained model or calibrated probability exists. No sustained 1000/s, full-application idle benchmark, real provider stream reconnect, PostgreSQL crash recovery, disk exhaustion soak or browser network-interruption stress test was completed. A Starlette test-client deprecation warning remains; functionality passed. Windows sometimes emits a connection-reset diagnostic on abrupt browser disconnect without halting the service.

## Documentation consulted

- [Next.js installation](https://nextjs.org/docs/app/getting-started/installation) and [v16 runtime requirements](https://nextjs.org/docs/app/guides/upgrading/version-16).
- [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/) for Python/Pydantic compatibility.
- [DexScreener public API reference](https://docs.dexscreener.com/api/reference) for documented batch token endpoints.

Remaining work with acceptance criteria: [ROADMAP.md](ROADMAP.md).
