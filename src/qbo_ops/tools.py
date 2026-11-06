"""QBO operations: the four core tools.

Each handler returns a plain dict; failures raise QboError which the
registration wrapper converts to a structured, user-presentable error
(never a raw 401 stack trace).
"""
import datetime
import json

from .tokens import QboCredentials, QboError, TokenLock, qbo_get


class OAuthTransport:
    """Rule-11 primary path: calls ride Hermes's credentialed_provider_request
    with the plugin's declared oauth: entry — Hermes owns the grant, the
    token and the refresh. The plugin never touches tokens."""

    def __init__(self, provider_id="quickbooks"):
        self.provider_id = provider_id

    def realm(self):
        return _secret("QBO_OPS_REALM_ID")

    def get(self, path, query=None):
        from hermes_cli.plugin_provider_requests import (
            ProviderNotSignedIn, credentialed_provider_request)

        realm = self.realm()
        if not realm:
            raise QboError("QBO_OPS_REALM_ID is not set (your QBO company ID)")
        url = f"{API_BASE_HOST}/{realm}/{path}"
        if query:
            import urllib.parse
            url += "?" + urllib.parse.urlencode({"query": query})
        try:
            resp = credentialed_provider_request(self.provider_id, "GET", url, timeout=60)
        except ProviderNotSignedIn as exc:
            raise QboError(
                f"QuickBooks not signed in: {exc}. Run "
                "`hermes auth add qbo-ops:quickbooks` to connect.") from None
        except Exception as exc:  # AuthError and friends
            raise QboError(f"QuickBooks auth error: {exc}") from None
        if resp.status >= 300:
            raise QboError(f"QBO API HTTP {resp.status} on {path}: {resp.text[:300]}")
        return resp.json()


API_BASE_HOST = "https://quickbooks.api.intuit.com/v3/company"


def _secret(name):
    try:
        from agent.secret_scope import get_secret
        return get_secret(name)
    except Exception:
        return None


class EnvTransport:
    """Fallback path (catalog-legal, precedented): BYO refresh token via
    requires_env secrets; the ported flock-guarded refresher handles rotation."""

    def __init__(self, creds):
        self.creds = creds

    def realm(self):
        return self.creds._get("QBO_OPS_REALM_ID")

    def get(self, path, query=None):
        return qbo_get(self.creds, path, query=query)


def _transport():
    """OAuth-first, env-fallback. A signed-out OAuth grant falls through to
    env creds when present, else surfaces the setup wizard."""
    realm = _secret("QBO_OPS_REALM_ID")
    try:
        from hermes_cli.plugin_provider_requests import (
            ProviderNotSignedIn, credentialed_provider_request)
        # Probe signed-in-ness cheaply: an unsigned grant raises before any HTTP.
        try:
            credentialed_provider_request(
                "quickbooks", "GET",
                f"{API_BASE_HOST}/(probe)/companyinfo/0", timeout=10)
        except (ProviderNotSignedIn, PermissionError):
            # Signed out — or not called from a plugin frame (probe context
            # can't grant provider access). Either way: fall through to env.
            pass
        except QboError:
            return OAuthTransport()  # signed in; the 404-ish probe error is fine
        except Exception:
            pass  # unknown probe failure: never trust the oauth path on a guess
        else:
            return OAuthTransport()
    except ImportError:
        pass
    try:
        creds = QboCredentials.from_secret_scope()
    except ImportError:
        raise QboError(
            "QBO is not configured yet. Setup takes ~10 minutes: "
            "(1) create an app at developer.intuit.com — I'll walk you "
            "through each field; (2) run `hermes auth add "
            "qbo-ops:quickbooks` (once upstream redirect-port support "
            "lands) or set these Hermes secrets: QBO_OPS_CLIENT_ID, "
            "QBO_OPS_CLIENT_SECRET, QBO_OPS_REFRESH_TOKEN, "
            "QBO_OPS_REALM_ID. Say 'set up QuickBooks' to start.") from None
    missing = creds.missing()
    if missing:
        raise QboError(
            "QBO is not configured yet. Setup takes ~10 minutes: "
            "(1) create a free app at https://developer.intuit.com "
            "(Dashboard → Create an app → QuickBooks Online Accounting); "
            "(2) under Development → Keys, copy the Client ID and Secret, "
            "and register this exact redirect URI: "
            "http://localhost:1990/callback; "
            "(3) either run `hermes auth add qbo-ops:quickbooks` (once "
            "upstream redirect-port support lands) or set these Hermes "
            "secrets: "
            + ", ".join(k for k in missing if k != "QBO_OPS_REFRESH_TOKEN")
            + " plus QBO_OPS_REFRESH_TOKEN — the consent URL and a full "
              "copy-paste walkthrough are at "
              "https://github.com/blackghostosint/qbo-ops/blob/main/docs/SETUP.md; "
            "(4) set QBO_OPS_REALM_ID. "
            "Or just say 'set up QuickBooks' and I'll walk you through "
            "every step.")
    return EnvTransport(creds)


def health(args=None):
    """Connection health: validates credentials, and confirms the realm
    answers a real API call. Never raises — returns a status dict (setup
    wizard message when unconfigured)."""
    try:
        transport = _transport()
        realm = transport.realm()
        if not realm:
            raise QboError("QBO_OPS_REALM_ID is not set (your QBO company ID)")
        info = transport.get(f"companyinfo/{realm}")
        company = info.get("CompanyInfo", {}).get("CompanyName", "(unnamed)")
        return {
            "status": "connected",
            "company": company,
            "realm_id": realm,
            "transport": type(transport).__name__,
        }
    except QboError as e:
        msg = str(e)
        if "not configured" in msg.lower():
            return {"status": "unconfigured", "message": msg}
        if "invalid_grant" in msg.lower() or "HTTP 400" in msg:
            return {
                "status": "reauth_required",
                "message": ("Refresh token revoked — Intuit does this after "
                            "100+ days idle or a password change. Re-run the "
                            "OAuth consent flow to reconnect."),
            }
        return {"status": "error", "message": msg}


def pnl(args):
    """Profit & Loss report for a date range. args: start_date, end_date.
    Uses the QBO reports endpoint (reports are not SQL-queryable)."""
    start = args.get("start_date") or (datetime.date.today().replace(day=1).isoformat())
    end = args.get("end_date") or datetime.date.today().isoformat()
    transport = _transport()
    report = transport.get(
        f"reports/ProfitAndLoss?start_date={start}&end_date={end}")
    totals = {}

    def walk(rs):
        for row in rs:
            if row.get("type") == "Section" and "Rows" in row:
                walk(row["Rows"].get("Row", []))
            elif row.get("type") == "Section" and "Summary" in row:
                sm = row["Summary"].get("ColData", [])
                if len(sm) > 1 and sm[0].get("value", "").startswith("Total"):
                    totals[sm[0]["value"]] = _col_value(sm)
            if "Summary" in row:  # nested section summaries
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
    """Close audit: list deposits/journal entries created or modified since a
    cutoff, flagging entries dated before their creation date (backdating)."""
    cutoff = args.get("since") or (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    transport = _transport()
    flags = []
    for entity in ("Deposit", "JournalEntry"):
        query = (f"select * from {entity} where MetaData.CreateTime >= '{cutoff}' "
                 f"maxresults 100")
        resp = transport.get("query", query=query)
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
    transport = _transport()
    query = (f"select * from Deposit where TxnDate >= '{since}' maxresults 200")
    resp = transport.get("query", query=query)
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
    """Guarded read-only pass-through to QBO's SQL endpoint. This is the
    'answer any question' tool: the agent composes a real SELECT against the
    user's books. Guardrails enforced here, not requested:
    - must start with SELECT (case-insensitive)
    - no semicolons (no statement stacking)
    - maxresults clamped to 200
    """
    query = (args.get("query") or "").strip()
    if not query:
        raise QboError("qbo_query needs a 'query' — a QBO SQL SELECT statement "
                       "(e.g. \"select * from Purchase where TxnDate >= '2026-10-01' maxresults 50\")")
    if not query.lower().startswith("select"):
        raise QboError("qbo_query is READ-ONLY: only SELECT statements are allowed")
    if ";" in query or "--" in query:
        raise QboError("qbo_query rejects semicolons and comment markers")
    import re as _re
    query = _re.sub(r"maxresults\s+\d+", "", query, flags=_re.IGNORECASE).strip()
    query += " maxresults 200"
    transport = _transport()
    resp = transport.get("query", query=query)
    out = {"read_only": True, "query": query}
    qr = resp.get("QueryResponse", {})
    # Single-entity responses: hoist rows under 'results'; keep totalCount if present
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
            # Handlers return JSON strings (see plugin dev guide, common mistakes)
            return json.dumps(result)
        ctx.register_tool(name=name, toolset="qbo-ops",
                          schema=SCHEMAS[name], handler=wrapped, emoji="📒")
