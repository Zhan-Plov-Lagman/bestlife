# Native deployment (no containers)

## Windows

Use setup.ps1, dev.ps1, stop.ps1, test.ps1 and benchmark.ps1. BackendOnly permits a Python-only installation/run. Scripts resolve application root from their own path. OS byte locks prevent concurrent managed launchers and concurrent backend writers. Stop verifies PID creation time and script path then sends a random owner-specific local shutdown request; it never uses process-name-wide killing. Backend drains admitted queued work before saving stopped state. Logs and ownership metadata live in .run (ignored).

Frontend is the existing production Next.js build. Rebuild after UI changes. Default ports are 8000 and 3000 on loopback. A port conflict must be resolved by the owner; scripts do not kill an unknown service.

## Linux VPS preparation (NOT deployed or verified here)

Create an unprivileged meridian user and `/opt/meridian` app directory owned by it. Install Python 3.12+ and Node 20.9+, create .venv, install backend/requirements.lock.txt, run Alembic from backend, then npm ci and npm run build in frontend. Keep configuration/secrets in a root-readable protected environment file as appropriate for the service account. Use one worker. Example unit `/etc/systemd/system/meridian-backend.service`:

```ini
[Unit]
Description=Meridian paper research backend
After=network.target

[Service]
User=meridian
Group=meridian
WorkingDirectory=/opt/meridian/backend
Environment=DATABASE_URL=sqlite:////opt/meridian/backend/trading.db
Environment=MERIDIAN_REMOTE_MODE=false
ExecStart=/opt/meridian/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --ws-max-size 4096 --limit-concurrency 64 --timeout-graceful-shutdown 35
Restart=on-failure
RestartSec=5
TimeoutStopSec=45
UMask=0077
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Separate frontend unit uses the same user, WorkingDirectory=/opt/meridian/frontend and ExecStart=/usr/bin/node /opt/meridian/frontend/node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000. Verify the actual Node path before installation. Add Restart=on-failure, TimeoutStopSec=30 and the same hardening basics. Apply migrations deliberately before service start, not concurrently with a running writer.

Access through SSH local port forwarding for 3000 and 8000; neither public firewall port needs opening. Do not bind 0.0.0.0 or publish an unauthenticated reverse proxy. Public remote access requires the additional security work described in SECURITY.md. Do not enable multiple workers or multiple VPS writers.

Before upgrades: stop services gracefully, take a SQLite-consistent backup with the SQLite backup API (never copy only the main DB while WAL writes are active), verify integrity and recovery in an isolated copy, preserve all ledger and audit records. Automated backup/restore acceptance tests remain pending. PostgreSQL via DATABASE_URL needs separate operational testing and distributed ownership before scaling.
