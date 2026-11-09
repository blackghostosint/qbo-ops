"""QBO operations: the five read-only tools (catalog rule 11: oauth-only
credential path — the plugin never holds, refreshes, or stores tokens)."""
import datetime
import json
import re as _re

from .tokens import QboError, qbo_get, realm as _realm


def health(args=None):
    """Connection health. Never raises — returns a status dict (setup
    wizard message when unconfigured)."""
    try:
        r = _realm()
        if not r:
            raise QboError("QBO_OPS_REALM_ID is not set (your QBO company ID)")
        info = qbo_get(f"companyinfo/{r}")
        company = info.get("CompanyInfo", {}).get("CompanyName", "(unnamed)")
        return {
            "status": "connected",
            "company": company,
            "realm_id": r,
            "transport": "oauth (Hermes-managed)",
        }
    except QboError as e:
        msg = str(e)
        if "REALM_ID is not set" in msg or "not configured" in msg.lower():
            return {"status": "unconfigured", "message": (
                "QBO is not fully configured yet. Two steps: "
                "(1) sign in once with `hermes auth add qbo-ops:quickbooks` "
                "— Hermes stores and refreshes the grant; "
                "(2) set your QBO company ID (QBO_OPS_REALM_ID) in the "
                "plugin's config or your profile .env. "
                "Find the realm ID: sign in at "
                "https://app.qbo.intuit.com and read the number after "
                "/app/ in the address bar, or see the walkthrough at "
                "https://github.com/blackghostosint/qbo-ops/blob/main/docs/SETUP.md. "
                "Or just say 'set up QuickBooks' and I'll walk you through "
                "every step.")}
        if "not signed in" in msg.lower() or "invalid_grant" in msg.lower():
            return {"status": "reauth_required",
                    "message": ("QuickBooks grant missing or revoked. Run "
                                "`hermes auth add qbo-ops:quickbooks` to "
                                "reconnect — no data is lost.")}
        return {"status": "error", "message": msg}
    except Exception as e:  # never propagate — health must always answer
        return {"status": "error", "message": f"unexpected error: {e}"}


def pnl(args):
    """Profit & Loss report for a date range (QBO reports endpoint)."""
    start = args.get("start_date") or (datetime.date.today().replace(day=1).isoformat())
    end = args.get("end_date") or datetime.date.today().isoformat()
    report = qbo_get(f"reports/ProfitAndLoss?start_date={start}&end_date={end}")
    totals = {}

    def walk(rs):
        for row in rs:
            if row.get("type") == "Section" and "Rows" in row:
                walk(row["Rows"].get("Row", []))
            if "Summary" in row:
                sm = row["Summary"].get("ColData", [])
                if len(sm) > 1 and sm[0].get("value", "").startswith("Total"):
                    totals[sm[0]["value"]] = _col_value(sm)

    walk(report.get("Rows", {}).get("Row", []))
    income = totals.get("Total Income", 0.0)
    expense = (totals.get("Total Expenses", 0.0)
               + totals.get("Total Cost of Goods Sold", 0.0)
               + totals.get("Total Other Expenses", 0.0))
    net = totals.get("Net Income")
    return {
        "start_date": start,
        "end_date": end,
        "income": income,
        "expenses": expense,
        "net_income": net if net is not None else round(income - expense, 2),
        "totals": totals,
    }


def _col_value(coldate):
    if len(coldate) > 1:
        try:
            return float(coldate[1].get("value", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def udf_audit(args):
    """Close audit: deposits/journal entries created since a cutoff,
    flagging backdated entries (created after their transaction date)."""
    cutoff = args.get("since") or (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    flags = []
    for entity in ("Deposit", "JournalEntry"):
        query = (f"select * from {entity} where MetaData.CreateTime >= '{cutoff}' "
                 f"maxresults 100")
        resp = qbo_get("query", query=query)
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
    return {"since": cutoff, "entities_checked": ["Deposit", "JournalEntry"],
            "flagged": flags, "flag_count": len(flags)}


def deposit_trace(args):
    """Trace a deposit amount in a window; detect duplicates (washes)."""
    amount = args.get("amount")
    if amount is None:
        raise QboError("deposit_trace needs an 'amount' (e.g. 412.00)")
    days = int(args.get("days", 30))
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    query = f"select * from Deposit where TxnDate >= '{since}' maxresults 200"
    resp = qbo_get("query", query=query)
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


def qbo_query(args):
    """Guarded read-only pass-through to QBO's SQL endpoint: SELECT-only,
    no statement stacking, maxresults clamped to 200 (enforced, not asked)."""
    query = (args.get("query") or "").strip()
    if not query:
        raise QboError("qbo_query needs a 'query' — a QBO SQL SELECT statement "
                       "(e.g. \"select * from Purchase where TxnDate >= '2026-10-01' maxresults 50\")")
    if not query.lower().startswith("select"):
        raise QboError("qbo_query is READ-ONLY: only SELECT statements are allowed")
    if ";" in query or "--" in query:
        raise QboError("qbo_query rejects semicolons and comment markers")
    query = _re.sub(r"maxresults\s+\d+", "", query, flags=_re.IGNORECASE).strip()
    query += " maxresults 200"
    resp = qbo_get("query", query=query)
    out = {"read_only": True, "query": query}
    qr = resp.get("QueryResponse", {})
    for key, val in qr.items():
        if key == "totalCount":
            out["total_count"] = val
        elif isinstance(val, list):
            out["results"] = val
            out["result_count"] = len(val)
        else:
            out[key] = val
    out.setdefault("results", [])
    out.setdefault("result_count", 0)
    return out


TOOLS = {
    "qbo_health": (health, "Check QuickBooks connection health; doubles as the setup wizard"),
    "qbo_pnl": (pnl, "Pull a QuickBooks Profit & Loss report for a date range"),
    "qbo_udf_audit": (udf_audit, "Audit recent close activity for backdated entries"),
    "qbo_deposit_trace": (deposit_trace, "Trace a deposit amount to detect duplicates/washes"),
    "qbo_query": (qbo_query, "Run a READ-ONLY SQL query against the user's QuickBooks data. Use for any transaction-level financial question (spending by vendor, payment lists, invoice status, expense lookups). Only SELECT; write operations are not available."),
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
    "qbo_query": {"name": "qbo_query", "description": TOOLS["qbo_query"][1],
                  "inputSchema": {"type": "object", "properties": {
                      "query": {"type": "string",
                                "description": ("QBO SQL SELECT. Entities: Purchase, Payment, "
                                                "Invoice, Bill, Deposit, JournalEntry, Account, "
                                                "Vendor, Customer. Example: \"select * from Purchase "
                                                "where TxnDate >= '2026-10-01' maxresults 50\"")},
                  }, "required": ["query"]}},
}


def register(ctx):
    for name, (handler, _desc) in TOOLS.items():
        def wrapped(args, _h=handler, **kwargs):
            try:
                result = _h(args if isinstance(args, dict) else {})
            except QboError as e:
                result = {"status": "error", "message": str(e)}
            # Handlers return JSON strings (plugin dev guide: common mistakes)
            return json.dumps(result)
        ctx.register_tool(name=name, toolset="qbo-ops",
                          schema=SCHEMAS[name], handler=wrapped, emoji="📒")
