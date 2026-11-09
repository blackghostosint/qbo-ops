"""Tests for qbo-ops core logic — offline (no network, no credentials).

v0.2 (catalog review): oauth-only credential path. The plugin never holds,
refreshes or stores tokens — Hermes does via the declared oauth: entry and
credentialed_provider_request. All token-handling tests were removed with
the code (see git history for the BYO-path coverage).
"""
import importlib
import json
import sys
import types
from pathlib import Path

import pytest

_PKG_ROOT = Path(__file__).resolve().parent.parent / "src"
_pkg = types.ModuleType("qbo_ops")
_pkg.__path__ = [str(_PKG_ROOT / "qbo_ops")]
sys.modules.setdefault("qbo_ops", _pkg)
tokens = importlib.import_module("qbo_ops.tokens")
tools = importlib.import_module("qbo_ops.tools")


def _patch_qbo_get(monkeypatch, fn):
    monkeypatch.setattr(tokens, "qbo_get", fn)
    monkeypatch.setattr(tools, "qbo_get", fn)


def _patch_realm(monkeypatch, value):
    monkeypatch.setattr(tokens, "realm", lambda: value)
    monkeypatch.setattr(tools, "_realm", lambda: value)


# ---------- rule 11: no token handling exists in the plugin ----------

def test_no_token_refresh_or_storage_code():
    import inspect
    src = inspect.getsource(tokens) + inspect.getsource(tools)
    for banned in ("refresh_token", "client_secret", "TokenLock", "flock",
                   "grant_type", "QBO_OPS_CLIENT_SECRET"):
        assert banned not in src, f"rule-11 violation: {banned} in plugin code"


def test_tokens_module_uses_provider_request():
    import inspect
    assert "credentialed_provider_request" in inspect.getsource(tokens)


# ---------- health: wizard / reauth / connected ----------

def test_health_missing_realm_returns_wizard(monkeypatch):
    _patch_realm(monkeypatch, None)
    r = tools.health({})
    assert r["status"] == "unconfigured"
    assert "auth add qbo-ops:quickbooks" in r["message"]
    assert "developer.intuit.com" in r["message"] or "REALM_ID" in r["message"]
    # ask 2: no secret values requested in chat
    assert "QBO_OPS_CLIENT_SECRET" not in r["message"].split("walk")[0]


def test_health_not_signed_in(monkeypatch):
    _patch_realm(monkeypatch, "123")

    def boom(path, query=None):
        raise tokens.QboError("QuickBooks not signed in: run hermes auth add")
    _patch_qbo_get(monkeypatch, boom)
    r = tools.health({})
    assert r["status"] == "reauth_required"


def test_health_connected(monkeypatch):
    _patch_realm(monkeypatch, "123")
    _patch_qbo_get(monkeypatch,
                   lambda path, query=None: {"CompanyInfo": {"CompanyName": "Test Co"}})
    r = tools.health({})
    assert r["status"] == "connected" and r["company"] == "Test Co"


def test_health_never_raises(monkeypatch):
    _patch_realm(monkeypatch, "123")

    def boom(path, query=None):
        raise RuntimeError("unexpected")
    _patch_qbo_get(monkeypatch, boom)
    r = tools.health({})
    assert r["status"] == "error"


# ---------- deposit trace ----------

def test_deposit_trace_requires_amount():
    with pytest.raises(tokens.QboError) as ei:
        tools.deposit_trace({})
    assert "amount" in str(ei.value)


# ---------- pnl report walking (fixture) ----------

def _report():
    return {"Rows": {"Row": [
        {"type": "Section", "Header": {"ColData": [{"value": "Income"}]},
         "Rows": {"Row": [
             {"type": "Section",
              "Summary": {"ColData": [{"value": "Total 4000 Revenue"},
                                      {"value": "14256.69"}]}},
         ]},
         "Summary": {"ColData": [{"value": "Total Income"},
                                 {"value": "14256.69"}]}},
        {"type": "Section", "Header": {"ColData": [{"value": "Expenses"}]},
         "Rows": {"Row": []},
         "Summary": {"ColData": [{"value": "Total Expenses"},
                                 {"value": "5139.01"}]}},
        {"type": "Section",
         "Summary": {"ColData": [{"value": "Total Other Expenses"},
                                 {"value": "1084.08"}]}},
    ]}}


def test_pnl_walks_section_summaries(monkeypatch):
    _patch_realm(monkeypatch, "1")
    _patch_qbo_get(monkeypatch, lambda path, query=None: _report())
    r = tools.pnl({"start_date": "2026-10-01", "end_date": "2026-10-31"})
    assert r["income"] == 14256.69
    assert r["expenses"] == 5139.01 + 1084.08
    assert r["net_income"] == round(14256.69 - 5139.01 - 1084.08, 2)


# ---------- qbo_query guardrails ----------

def test_query_rejects_non_select():
    with pytest.raises(tokens.QboError) as ei:
        tools.qbo_query({"query": "delete from Deposit where Id = '1'"})
    assert "READ-ONLY" in str(ei.value)


def test_query_rejects_statement_stacking():
    with pytest.raises(tokens.QboError):
        tools.qbo_query({"query": "select * from Deposit; drop table Deposit"})


def test_query_rejects_comment_markers():
    with pytest.raises(tokens.QboError):
        tools.qbo_query({"query": "select * from Deposit -- evil"})


def test_query_clamps_maxresults(monkeypatch):
    seen = {}

    def fake(path, query=None):
        seen["query"] = query
        return {"QueryResponse": {"Deposit": [{"Id": "1"}]}}
    _patch_qbo_get(monkeypatch, fake)
    r = tools.qbo_query({"query": "select * from Deposit maxresults 9999"})
    assert seen["query"].endswith("maxresults 200")
    assert "9999" not in seen["query"]
    assert r["read_only"] is True and r["result_count"] == 1


def test_query_empty():
    with pytest.raises(tokens.QboError):
        tools.qbo_query({})


def test_col_value_tolerates_garbage():
    assert tools._col_value([{"value": "a"}, {"value": "not-a-number"}]) == 0.0
    assert tools._col_value([{"value": "a"}, {"value": "3.5"}]) == 3.5
    assert tools._col_value([{"value": "a"}]) == 0.0


# ---------- handler contract (plugin dev guide) ----------

def test_tool_wrapper_returns_json_string():
    class Ctx:
        registered = {}

        def register_tool(self, name, toolset, schema, handler, emoji=None):
            Ctx.registered[name] = handler
    Ctx.registered = {}
    tools.register(Ctx())
    assert len(Ctx.registered) == 5
    for name, handler in Ctx.registered.items():
        out = handler({})
        assert isinstance(out, str), f"{name} must return a JSON string"
        parsed = json.loads(out)  # and valid JSON
        assert isinstance(parsed, dict)


# ---------- guided setup: secrets never transit chat (review ask 2) ----------

def test_guided_setup_never_collects_secrets():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent
                           / "skills" / "qbo-ops-reconciliation" / "references"))
    import guided_setup as g
    for step in g.STEPS:
        text = step.say + " " + step.check
        assert "paste the Client Secret" not in text
        assert "paste the client secret" not in text
        assert "refresh_token" not in step.say  # no token handling at all
        assert "curl" not in step.say  # no manual token exchange
    # realm ID (non-secret) is the only storable-by-agent value
    assert any("QBO_OPS_REALM_ID" in s.say for s in g.STEPS)
