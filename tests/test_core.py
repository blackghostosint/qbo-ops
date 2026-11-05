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

def test_health_unconfigured_returns_wizard():
    import qbo_ops.tools as T
    orig = T._creds
    T._creds = lambda: (_ for _ in ()).throw(tokens.QboError(
        "QBO is not configured yet. Setup takes ~10 minutes"))
    try:
        r = T.health({})
    finally:
        T._creds = orig
    assert r["status"] == "unconfigured"
    assert "not configured" in r["message"]


def test_health_reauth_path():
    import qbo_ops.tools as T
    orig = T._creds
    T._creds = lambda: (_ for _ in ()).throw(tokens.QboError(
        "Intuit refresh failed HTTP 400: invalid_grant"))
    try:
        r = T.health({})
    finally:
        T._creds = orig
    assert r["status"] == "reauth_required"


def test_deposit_trace_requires_amount():
    with pytest.raises(tokens.QboError) as ei:
        tools.deposit_trace({})
    assert "amount" in str(ei.value)


# ---------- pnl report walking (fixture, offline) ----------

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
    fake_creds = tokens.QboCredentials.from_mapping({
        "QBO_OPS_CLIENT_ID": "x", "QBO_OPS_CLIENT_SECRET": "y",
        "QBO_OPS_REFRESH_TOKEN": "z", "QBO_OPS_REALM_ID": "1"})
    monkeypatch.setattr(T, "_creds", lambda: fake_creds)
    monkeypatch.setattr(T, "qbo_get", lambda c, p, query=None: _report())
    r = T.pnl({"start_date": "2026-10-01", "end_date": "2026-10-31"})
    assert r["income"] == 14256.69
    assert r["expenses"] == 5139.01 + 1084.08
    assert r["net_income"] == round(14256.69 - 5139.01 - 1084.08, 2)


def test_col_value_tolerates_garbage():
    assert tools._col_value([{"value": "a"}, {"value": "not-a-number"}]) == 0.0
    assert tools._col_value([{"value": "a"}, {"value": "3.5"}]) == 3.5
    assert tools._col_value([{"value": "a"}]) == 0.0
