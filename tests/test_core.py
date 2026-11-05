"""Tests for qbo-ops core logic — offline (no network, no credentials)."""
import importlib
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


# ---------- QboCredentials ----------

def test_missing_reports_all_keys():
    creds = tokens.QboCredentials.from_mapping({})
    assert set(creds.missing()) == {
        "QBO_OPS_CLIENT_ID", "QBO_OPS_CLIENT_SECRET",
        "QBO_OPS_REFRESH_TOKEN", "QBO_OPS_REALM_ID"}


def test_missing_reports_subset():
    creds = tokens.QboCredentials.from_mapping({"QBO_OPS_CLIENT_ID": "x"})
    assert creds.missing() == [
        "QBO_OPS_CLIENT_SECRET", "QBO_OPS_REFRESH_TOKEN", "QBO_OPS_REALM_ID"]


def test_refresh_raises_clean_when_unconfigured():
    creds = tokens.QboCredentials.from_mapping({})
    with pytest.raises(tokens.QboError) as ei:
        creds.refresh()
    assert "incomplete" in str(ei.value)


def test_cached_access_token_reused():
    creds = tokens.QboCredentials.from_mapping({
        "QBO_OPS_CLIENT_ID": "x", "QBO_OPS_CLIENT_SECRET": "y",
        "QBO_OPS_REFRESH_TOKEN": "z"})
    creds._access_token, creds._access_exp = "cached", 9_999_999_999.0
    assert creds.refresh() == "cached"  # no network call


# ---------- TokenLock ----------

def test_lock_acquire_and_release(tmp_path):
    creds = tokens.QboCredentials.from_mapping({})
    lp = str(tmp_path / "t.lock")
    with tokens.TokenLock(creds, lock_path=lp, wait_s=1):
        pass  # acquired + released
    # second acquire must succeed immediately
    with tokens.TokenLock(creds, lock_path=lp, wait_s=1):
        pass


def test_lock_contention_fails_loudly(tmp_path):
    import multiprocessing as mp

    lp = str(tmp_path / "t.lock")

    def _holder_block():
        import time
        import fcntl
        f = open(lp, "w")
        fcntl.flock(f, fcntl.LOCK_EX)
        time.sleep(5)

    p = mp.get_context("fork").Process(target=_holder_block)
    p.start()
    import time
    time.sleep(0.5)  # let the holder grab the lock
    creds = tokens.QboCredentials.from_mapping({})
    with pytest.raises(tokens.QboError) as ei:
        tokens.TokenLock(creds, lock_path=lp, wait_s=1).__enter__()
    p.terminate()
    p.join()
    assert "refusing to deadlock" in str(ei.value)


# ---------- tools: error/wizard paths (offline) ----------

def test_health_unconfigured_returns_wizard(monkeypatch):
    import qbo_ops.tools as T

    def boom():
        raise tokens.QboError(
            "QBO is not configured yet. Setup takes ~10 minutes")
    monkeypatch.setattr(T, "_transport", boom)
    r = T.health({})
    assert r["status"] == "unconfigured"
    assert "not configured" in r["message"]


def test_health_reauth_path(monkeypatch):
    import qbo_ops.tools as T

    def boom():
        raise tokens.QboError(
            "Intuit refresh failed HTTP 400: invalid_grant")
    monkeypatch.setattr(T, "_transport", boom)
    r = T.health({})
    assert r["status"] == "reauth_required"


def test_deposit_trace_requires_amount():
    with pytest.raises(tokens.QboError) as ei:
        tools.deposit_trace({})
    assert "amount" in str(ei.value)


# ---------- qbo_query guardrails ----------

def test_query_rejects_non_select():
    with pytest.raises(tokens.QboError) as ei:
        tools.qbo_query({"query": "delete from Deposit where Id = '1'"})
    assert "READ-ONLY" in str(ei.value)


def test_query_rejects_statement_stacking():
    with pytest.raises(tokens.QboError) as ei:
        tools.qbo_query({"query": "select * from Deposit; drop table Deposit"})
    assert "semicolons" in str(ei.value)


def test_query_rejects_comment_markers():
    with pytest.raises(tokens.QboError):
        tools.qbo_query({"query": "select * from Deposit -- evil"})


def test_query_clamps_maxresults(monkeypatch):
    class FakeTransport:
        def realm(self):
            return "1"

        def get(self, path, query=None):
            assert query.endswith("maxresults 200"), query
            assert "maxresults 9999" not in query
            return {"QueryResponse": {"Deposit": [{"Id": "1"}]}}
    import qbo_ops.tools as T
    monkeypatch.setattr(T, "_transport", lambda: FakeTransport())
    r = tools.qbo_query({"query": "select * from Deposit maxresults 9999"})
    assert r["read_only"] is True and r["result_count"] == 1


def test_query_empty():
    with pytest.raises(tokens.QboError):
        tools.qbo_query({})


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
    import qbo_ops.tools as T

    class FakeTransport:
        def realm(self):
            return "1"

        def get(self, path, query=None):
            return _report()

    monkeypatch.setattr(T, "_transport", lambda: FakeTransport())
    r = T.pnl({"start_date": "2026-10-01", "end_date": "2026-10-31"})
    assert r["income"] == 14256.69
    assert r["expenses"] == 5139.01 + 1084.08
    assert r["net_income"] == round(14256.69 - 5139.01 - 1084.08, 2)


def test_tool_wrapper_returns_json_string():
    import json as _json

    import qbo_ops.tools as T

    class Ctx:
        def register_tool(self, name, toolset, schema, handler, emoji=None):
            Ctx.registered[name] = handler
    Ctx.registered = {}
    T.register(Ctx())
    for name, handler in Ctx.registered.items():
        out = handler({})
        assert isinstance(out, str), f"{name} handler must return a JSON string"
        _json.loads(out)  # and valid JSON


def test_col_value_tolerates_garbage():
    assert tools._col_value([{"value": "a"}, {"value": "not-a-number"}]) == 0.0
    assert tools._col_value([{"value": "a"}, {"value": "3.5"}]) == 3.5
    assert tools._col_value([{"value": "a"}]) == 0.0
