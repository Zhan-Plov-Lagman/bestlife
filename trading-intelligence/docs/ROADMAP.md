# Remaining work after v1.1 P0/P1

1. Long-run reliability: process-kill/disk-full fault campaigns, property-based Decimal invariants, tested backup/restore, immutable audit export, retention preserving recovery/dedup history.
2. Performance: sustainable 1000 events/s is not accepted; investigate commit/checkpoint tail latency and deployment storage, benchmark active fills separately, 24-hour soak. Keep FULL durability and report overloaded queue latency.
3. Testing Gateway: persistent test sessions and asynchronous lifecycle, Demo/Historical adapters, import/export validation and API/UI. Current offline replay is a working prerequisite, not this gateway.
4. Shadow: separate portfolios over identical immutable events, paired-decision and cost attribution, confidence/coverage analysis and comparison UI; optional/off in ECO.
5. Data: verified historical market timestamps and depth, provenance, token safety, survivorship/leakage controls. Dex remains observation-only until required data exists.
6. ML: versioned dataset contracts and compatibility, persisted registry, reproducible OOS evaluation, explicit approval/audit for promotion, separate CPU models for momentum/scalping/regime. No runtime training or automatic risk expansion.
7. Deployment: verify PostgreSQL recovery/locking, Linux systemd and Python 3.12. Public remote access requires a full TLS/auth/proxy design; current native terminal is loopback only.
8. UI: Testing Lab, Shadow, deeper per-strategy/per-regime reports and explicit execution provenance columns. Existing screens remain; recovery banner and stage metrics are available now.

Real wallets, transactions and automated risk increases remain outside scope.
