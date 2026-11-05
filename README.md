# qbo-ops — QuickBooks Online operations for Hermes Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Plugin](https://img.shields.io/badge/Hermes-plugin-blueviolet)](https://hermes-agent.nousresearch.com)
![Status](https://img.shields.io/badge/status-hackathon%20v0.1.0-orange)

**Ask your agent about your books — and get real answers from real data.**

qbo-ops connects your Hermes agent to QuickBooks Online with the
reconciliation tradecraft of a working bookkeeper built in: connection
health, P&L reports, close audits, deposit tracing, and a guarded read-only
SQL query tool that can answer any transaction-level question. Plus a live
desktop pane so you can see your books are healthy without asking.

## Why

QuickBooks Online is the default books of millions of small businesses —
and the Hermes plugin catalog had **zero** bookkeeping entries. Every
competent dev can wrap the QBO REST API; what nobody ships is the judgment
layer: how a deposit wash presents, which backdated entries are benign and
which silently change a reconciled balance, what to check and in what order
at month-end. That knowledge here is earned from closing real books for a
real store, and it ships both as executable tools and as a bundled agent
skill.

## What you get

**Desktop surface:** a status chip (connection health at a glance) and a
QuickBooks pane (company, this month's income/net, close-audit flags) in
the Hermes desktop app.

**5 agent tools** (all read-only):

| Tool | What it answers |
|---|---|
| `qbo_health` | "Is my QuickBooks connection healthy?" — doubles as the setup wizard |
| `qbo_pnl` | "How did October look?" — real P&L, correct date handling |
| `qbo_udf_audit` | "Anything weird since Friday's close?" — backdated-entry flags |
| `qbo_deposit_trace` | "This $412 deposit shows twice" — duplicate/wash detection |
| `qbo_query` | "What did I spend on shipping last quarter?" — guarded read-only SQL against any QBO entity |

**Bundled skill** (`qbo-ops-reconciliation`): the interpretation layer —
close-audit reading, deposit-wash analysis, the month-end sanity chain, and
failure diagnosis — so the agent doesn't just fetch data, it reasons like
a bookkeeper.

## Setup (~10 minutes)

1. **Create an Intuit app** at [developer.intuit.com](https://developer.intuit.com)
   (accounting scope). This one step no plugin can automate — Intuit
   requires the app to be yours. Redirect URI: `http://localhost:1990/callback`.
2. **Provide credentials through Hermes secrets.** The installer prompts for
   each by name (you can skip and set later): `QBO_OPS_CLIENT_ID`,
   `QBO_OPS_CLIENT_SECRET`, `QBO_OPS_REFRESH_TOKEN`, `QBO_OPS_REALM_ID`.
3. **Verify:** ask your agent *"is my QuickBooks connection healthy?"* —
   you'll get your company name and a verified connection, or a plain-English
   diagnosis of exactly what's missing.

No secrets ever touch plugin code or config files — credentials flow
through Hermes's secret scope (catalog rule 11), and the plugin never reads
`.env` files or token stores.

## Where's the write support?

The plugin is **read-only by design**. A write mode exists as a per-user
config switch (`allow_writes`, default **off** — an individual decision,
not ours) and ships in v0.2 only after write paths are verified against a
QBO sandbox. Flipping the switch opts you into Hermes's normal approval
flow per write; it never bypasses it.

## Known limitation

The pure `hermes auth add` OAuth path needs upstream `redirect_port`
support for Intuit's exact-match redirect URIs — tracked in
[NousResearch/hermes-agent#149642](https://github.com/NousResearch/hermes-agent/issues/149642).
Until then, use the BYO-refresh-token setup above: fully supported, and the
plugin's flock-guarded refresher handles rotation safely (no token-family
revocation races).

## Roadmap

- [ ] v0.2: write mode (`allow_writes` switch → sandbox-verified mutation tool)
- [ ] Cash-flow and Balance Sheet reports alongside P&L
- [ ] Scheduled close audits (cron: Monday morning flag report)
- [ ] `oauth:` primary path once upstream #149642 lands

## Status

v0.1.0 — hackathon build: production-hardened token layer, 5 tools,
desktop pane, bundled skill, 17 offline tests. Not yet in the plugin
catalog (submission PR in progress).

## License

MIT
