# Changelog

## 0.1.0 — 2026-11-05

Initial hackathon build.

### Added
- 5 read-only agent tools: qbo_health (setup wizard), qbo_pnl,
  qbo_udf_audit (backdated-entry detection), qbo_deposit_trace
  (duplicate-deposit/wash detection), qbo_query (guarded read-only SQL).
- Desktop pane + status chip for the Hermes desktop app.
- Bundled skill: qbo-ops-reconciliation (close audits, deposit-wash
  analysis, month-end sanity chain).
- Production-hardened flock-guarded token refresher (BYO-refresh-token
  path; no token-family revocation races).
- Dual transport: Hermes oauth: route (primary) with env-secret fallback.
- allow_writes config switch (default off; write tool ships in v0.2).
- 17 offline tests; hermes plugins validate + doctor green.
