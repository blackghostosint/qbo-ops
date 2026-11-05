"""QBO operations: the four core tools.

Each handler returns a plain dict; failures raise QboError which the
registration wrapper converts to a structured, user-presentable error
(never a raw 401 stack trace).
"""
import datetime
import json

from .tokens import QboCredentials, QboError, TokenLock, qbo_get


def _creds():
    creds = QboCredentials.from_secret_scope()
    missing = creds.missing()
    if missing:
        raise QboError(
            "QBO is not configured yet. Setup takes ~10 minutes: "
            "(1) create an app at developer.intuit.com — I'll walk you "
            "through each field; (2) set these Hermes secrets: "
            + ", ".join(missing)
            + "; (3) I'll run the OAuth consent flow and verify the "
              "connection. Say 'set up QuickBooks' to start.")
    return creds


def health(args=None):
    """Connection health: validates credentials, refreshes the token if
    needed, and confirms the realm answers a real API call."""
    creds = _creds()
    try:
        with TokenLock(creds):
            token = creds.refresh()
        realm = creds._get("QBO_OPS_REALM_ID")
        info = qbo_get(creds, f"companyinfo/{realm}")
        company = info.get("CompanyInfo", {}).get("CompanyName", "(unnamed)")
        return {
            "status": "connected",
            "company": company,
            "realm_id": realm,
            "token_valid": bool(token),
        }
    except QboError as e:
        msg = str(e)
        if "invalid_grant" in msg.lower() or "HTTP 400" in msg:
            return {
                "status": "reauth_required",
                "message": ("Refresh token revoked — Intuit does this after "
                            "100+ days idle or a password change. Re-run the "
                            "OAuth consent flow to reconnect."),
            }
        return {"status": "error", "message": msg}


def pnl(args):
    """Profit & Loss report for a date range. args: start_date, end_date."""
    start = args.get("start_date") or (datetime.date.today().replace(day=1).isoformat())
    end = args.get("end_date") or datetime.date.today().isoformat()
    creds = _creds()
    query = (f"select * from ProfitAndLoss "
             f"where StartDate = '{start}' and EndDate = '{end}'")
    resp = qbo_get(creds, "query", query=query)
    report = resp.get("QueryResponse", {}).get("ProfitAndLoss", [{}])[0]
    rows = report.get("Rows", {}).get("Row", [])
    income = expense = 0.0
    for row in rows:
        header = row.get("Header", {}).get("ColData", [])
        if header and header[0].get("value") == "Income":
            income = _col_value(header)
        elif header and header[0].get("value") in ("Expenses", "Cost of Goods Sold"):
            expense += _col_value(header)
    return {
        "start_date": start,
        "end_date": end,
        "income": income,
        "expenses": expense,
        "net_income": round(income - expense, 2),
        "currency": report.get("Currency", "USD"),
    }


def _col_value(coldate):
    if len(coldate) > 1:
        try:
            return float(coldate[1].get("value", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def udf_audit(args):
    """Close audit: list deposits/journal entries created or modified since a
    cutoff, flagging entries dated before their creation date (backdating)."""
    cutoff = args.get("since") or (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    creds = _creds()
    flags = []
    for entity in ("Deposit", "JournalEntry"):
        query = (f"select * from {entity} where MetaData.CreateTime >= '{cutoff}' "
                 f"maxresults 100")
        resp = qbo_get(creds, "query", query=query)
        for obj in resp.get("QueryResponse", {}).get(entity, []):
            created = obj.get("MetaData", {}).get("CreateTime", "")
            txn_date = obj.get("TxnDate", "")
            if created[:10] and txn_date and created[:10] > txn_date:
                flags.append({
                    "type": entity,
                    "id": obj.get("Id"),
                    "txn_date": txn_date,
                    "created": created[:10],
                    "flag": "backdated (created after its transaction date)",
                })
    return {"since": cutoff, "entries_checked_entities": ["Deposit", "JournalEntry"],
            "flagged": flags, "flag_count": len(flags)}


def deposit_trace(args):
    """Trace deposits: find payments/deposits matching an amount in a window,
    surfacing possible duplicate deposits (washes) or credit balances."""
    amount = args.get("amount")
    if amount is None:
        raise QboError("deposit_trace needs an 'amount' (e.g. 412.00)")
    days = int(args.get("days", 30))
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    creds = _creds()
    query = (f"select * from Deposit where TxnDate >= '{since}' maxresults 200")
    resp = qbo_get(creds, "query", query=query)
    hits = []
    for dep in resp.get("QueryResponse", {}).get("Deposit", []):
        for line in dep.get("Line", []):
            led = line.get("DepositLineDetail", {}) if "DepositLineDetail" in line else {}
            amt = line.get("Amount")
            try:
                amt = float(amt)
            except (TypeError, ValueError):
                continue
            if abs(amt - float(amount)) < 0.005:
                hits.append({
                    "deposit_id": dep.get("Id"),
                    "txn_date": dep.get("TxnDate"),
                    "amount": amt,
                    "account": led.get("AccountRef", {}).get("name"),
                    "total_deposit": dep.get("TotalAmt"),
                })
    dupes = len(hits) > 1
    return {
        "amount": float(amount),
        "window_days": days,
        "matches": hits,
        "match_count": len(hits),
        "possible_duplicate_deposit": dupes,
        "note": ("More than one deposit line matches this exact amount in the "
                 "window — verify this is not a deposit wash (recorded twice)."
                 if dupes else ""),
    }


TOOLS = {
    "qbo_health": (health, "Check QuickBooks connection health; doubles as the setup wizard"),
    "qbo_pnl": (pnl, "Pull a QuickBooks Profit & Loss report for a date range"),
    "qbo_udf_audit": (udf_audit, "Audit recent close activity for backdated entries"),
    "qbo_deposit_trace": (deposit_trace, "Trace a deposit amount to detect duplicates/washes"),
}

SCHEMAS = {
    "qbo_health": {"name": "qbo_health", "description": TOOLS["qbo_health"][1],
                   "inputSchema": {"type": "object", "properties": {}, "additionalProperties": True}},
    "qbo_pnl": {"name": "qbo_pnl", "description": TOOLS["qbo_pnl"][1],
                "inputSchema": {"type": "object", "properties": {
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                }}},
    "qbo_udf_audit": {"name": "qbo_udf_audit", "description": TOOLS["qbo_udf_audit"][1],
                      "inputSchema": {"type": "object", "properties": {
                          "since": {"type": "string", "description": "YYYY-MM-DD cutoff"},
                      }}},
    "qbo_deposit_trace": {"name": "qbo_deposit_trace", "description": TOOLS["qbo_deposit_trace"][1],
                          "inputSchema": {"type": "object", "properties": {
                              "amount": {"type": "number"},
                              "days": {"type": "integer"},
                          }, "required": ["amount"]}},
}


def register(ctx):
    for name, (handler, _desc) in TOOLS.items():
        def wrapped(args, _h=handler, **kwargs):
            try:
                return _h(args if isinstance(args, dict) else {})
            except QboError as e:
                return {"status": "error", "message": str(e)}
        ctx.register_tool(name=name, toolset="qbo-ops",
                          schema=SCHEMAS[name], handler=wrapped, emoji="📒")
