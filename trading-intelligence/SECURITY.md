# Security boundary

- Local-only startup commands and loopback Docker published ports. No live execution adapter, signing library, wallet permissions, private keys, seed phrases, Axiom session data or private APIs.
- HTTP Host allowlist and exact browser Origin allowlist. Mutations require a random per-process session token fetched from the local API; WS authenticates in its first message, not a logged URL. Cross-origin reads/mutations are rejected. Eight WS clients maximum, 240 HTTP requests/minute process-wide, bounded payload contracts.
- The local session token is a CSRF protection, not a multi-user authentication scheme. Other processes under the same OS user can call the local API. Do not expose the service publicly or use a reverse proxy without adding proper authentication/TLS, access controls and distributed locking.
- PostgreSQL password only through environment; `.env` ignored. Frontend public API URL contains no secret. No wallet secrets are accepted in settings. Fixed external provider URLs prevent arbitrary URL/SSRF configuration.
- Token symbols are text rendered by React. No `dangerouslySetInnerHTML`, eval, shell execution, model pickle/joblib loading or token-directed instructions.
- Validated Pydantic inputs reject unknown settings, NaN and invalid mint syntax; SQLAlchemy bound queries. Monetary settlements use Decimal.
- A database failure rolls back a market event and halts processing. Clear-halt is explicit and leaves trading paused. A crash restarts paused. Disk exhaustion handling relies on database errors and fail-closed, not proof of uninterrupted availability.
- Reset archives by changing session ID; it does not erase financial history. Provider changes require stopped/flat state and create a separate session.
- Dependencies are locked. npm audit was run; see verification report for measured results. Dependency scanners do not establish that software is vulnerability-free.

Stale portfolio marks block new entries, independently of the current token's freshness. Pending protective/manual exit orders survive a pause or kill command; restart cancels outstanding orders and requires fresh observations.

Known hardening work: body-size limits before parsing, per-client rate limiting, immutable audit export, disk-pressure alerts, cross-process writer lease, database reconciliation from immutable fills, backups and tested Postgres recovery. This is a personal local research application, not a reviewed custody or production trading service.
