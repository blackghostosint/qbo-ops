# qbo-ops — QuickBooks Online operations for Hermes Agent

Hermes desktop plugin: QuickBooks connection health, P&L reports, close
audits and deposit tracing — reconciliation tradecraft built in, not just
API plumbing.

## What you get

- **Desktop pane + status chip**: live connection health in the Hermes
  desktop app, this month's income/net at a glance, close-audit flags.
- **4 agent tools**: `qbo_health` (doubles as the setup wizard),
  `qbo_pnl`, `qbo_udf_audit` (backdated-entry detection),
  `qbo_deposit_trace` (duplicate-deposit / wash detection).

## Setup (~10 minutes)

1. Create an app at [developer.intuit.com](https://developer.intuit.com)
   (accounting scope; redirect URI: `http://localhost:1990/callback`).
2. Provide credentials through Hermes secrets (the plugin asks for exactly
   these, by name): `QBO_OPS_CLIENT_ID`, `QBO_OPS_CLIENT_SECRET`,
   `QBO_OPS_REFRESH_TOKEN`, `QBO_OPS_REALM_ID`.
3. Ask your agent "is my QuickBooks connection healthy?" — `qbo_health`
   verifies the token and the company connection, or tells you exactly
   what's missing.

## Known limitation

The pure `hermes auth add` OAuth path needs upstream `redirect_port` support for
Intuit exact-match redirect URIs — tracked in
NousResearch/hermes-agent#149642. Until then, use the BYO-token setup above
(which is fully supported and what the plugin defaults to).

## Status

v0.1.0 — day-1 scaffold: token layer (production-hardened), 4 tools,
desktop pane. Not yet in the plugin catalog.

## License

MIT
