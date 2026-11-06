---
name: qbo-ops-reconciliation
description: QuickBooks Online reconciliation tradecraft — close audits, deposit-wash detection, backdated-entry forensics. Use with the qbo-ops plugin tools.
---

# QBO Operations: Reconciliation Tradecraft

Methodology for verifying a QuickBooks Online company's books with the
qbo-ops plugin tools. The tools provide the data; this skill is the judgment
layer — what to check, in what order, and what a finding means.

## When to use

- "How did last month look?" → `qbo_pnl`, then sanity-check against the
  user's expectation (a merchant-services deposit total, a POS report).
- "Audit the close" / daily bookkeeping verification → `qbo_udf_audit`.
- "This deposit looks wrong / shows twice" → `qbo_deposit_trace`.
- Anything feels off → start with `qbo_health` to rule out connection rot.
- "Set up QuickBooks" / any setup question → run the GUIDED setup, not a
  doc dump. The turn-by-turn script lives next to this file at
  `references/guided_setup.py` (same folder as this SKILL.md): one step per
  turn, copy-paste-ready text, ask for proof after EVERY step, never
  advance until the user confirms, store secrets the moment they arrive,
  never echo secret values back. After verification succeeds, offer the
  sandbox-vs-production fork (`sandbox_production_fork()` in the same
  file). If the script file is unavailable, fetch
  https://raw.githubusercontent.com/blackghostosint/qbo-ops/main/docs/SETUP.md
  and walk it part by part — a complete newbie needs the exact URLs
  (`developer.intuit.com`, redirect URI `http://localhost:1990/callback`,
  the consent URL template) and where each value gets pasted.

## The close audit (qbo_udf_audit)

Runs deposits and journal entries created since the cutoff and flags
**backdated entries** — created after their transaction date. Reading the
flags:

- **Benign pattern:** a bookkeeper enters Monday's weekend sales on Tuesday.
  Created-after-dated is normal for human entry cadence; the flag is a
  *review queue*, not an accusation.
- **Hostile pattern:** an entry dated before a bank-confirmed balance,
  created after the period closed. If the user is reconciling against a
  bank statement, backdated entries created AFTER the reconciliation date
  silently change the reconciled balance. Escalate: re-run the bank rec.
- **Compound flag:** a backdated *journal entry* touching cash and a
  *deposit* with the same amount within a few days = a manual reclass of a
  real transaction. Verify which one the bank actually shows.

## Deposit tracing (qbo_deposit_trace)

Trace a suspect amount across the deposit window:

- **match_count 0:** the amount never landed as a deposit line. It may be
  recorded as a Sales Receipt or Payment (undeposited funds), an expense
  refund, or *not at all*. Check undeposited funds before declaring loss.
- **match_count 1:** normal. Confirm the deposit's account is the bank the
  money actually landed in — a right-amount/wrong-account hit is a
  mispost, and it reconciles "cleanly" while hiding the true location.
- **match_count 2+ (wash):** two deposit lines with the identical amount.
  Classic causes: POS batch recorded twice (morning re-run), a duplicate
  merchant-services import, or an entry + its "correction" both kept.
  Determine which deposit the bank statement supports; the other is the
  duplicate to reverse — never delete the one the bank proves.

## Month-end sanity chain

1. `qbo_pnl` for the month → income and net.
2. Ask the user (or their POS/merchant report) the period's gross sales.
3. Material gap (POS sales ≠ P&L income) means one of: sales recorded as
   undeposited funds but never deposited; owner draws misbooked as income
   or expenses misbooked as draws; or a missing week of POS import.
4. `qbo_udf_audit` with since = last successful close.
5. Any flagged backdated entry that predates the bank rec → re-reconcile.

## Health and failure interpretation (qbo_health)

- `unconfigured` → run the guided setup (see `references/guided_setup.py`).
- `reauth_required` → Intuit revoked the refresh token (100+ days idle,
  password change, or app-side family revocation). Re-run consent; no data
  is lost.
- `error` with HTTP 403 → the user's Intuit app lacks the accounting scope
  or the company isn't authorized to the app (re-consent needed).
- **Before improvising any diagnosis, consult the failure catalog** in
  https://raw.githubusercontent.com/blackghostosint/qbo-ops/main/docs/SETUP.md
  (Troubleshooting section — "Deeper failure catalog"): every known error
  signature (invalid_client, unauthorized_client, 403, invalid_grant,
  429, empty-query results, realm mismatch, tools-missing-after-install)
  has a documented root cause and remediation. Only fall back to
  first-principles debugging for signatures not in the catalog — and add
  the new one to the catalog when solved.
- Token refreshes are handled by Hermes (oauth path) or the plugin's
  flock-guarded refresher (BYO path). If you ever see two refreshes race,
  report it as a bug — rotation races are how whole token families die.

## Anti-patterns (do not do these)

- Don't re-run a report for a "different number" without fixing the date
  range explicitly — QBO defaults are the #1 source of phantom discrepancies.
- Don't treat a matched amount as proof of the right transaction — amounts
  collide constantly in retail. Dates and accounts are the discriminators.
- Don't edit or suggest deleting transactions from the tool's findings
  alone; findings are leads, the bank statement is the referee.
