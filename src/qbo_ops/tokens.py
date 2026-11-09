#!/usr/bin/env python3
"""QBO API access via Hermes's credential routes only (catalog rule 11).

The plugin NEVER holds, refreshes, or stores OAuth tokens. All calls ride
credentialed_provider_request with the plugin's declared oauth: entry —
Hermes owns the grant, the token, and the refresh cycle.
"""
import urllib.parse

API_BASE = "https://quickbooks.api.intuit.com/v3/company"
PROVIDER_ID = "quickbooks"


class QboError(Exception):
    """User-presentable QBO error (health tool turns this into guidance)."""


def _secret(name):
    try:
        from agent.secret_scope import get_secret
        return get_secret(name)
    except Exception:
        return None


def realm():
    return _secret("QBO_OPS_REALM_ID")


def qbo_get(path, query=None):
    """Authenticated GET against the QBO v3 API via Hermes's credential
    route. Returns parsed JSON; raises QboError with plain-English guidance."""
    r = realm()
    if not r:
        raise QboError("QBO_OPS_REALM_ID is not set (your QBO company ID) — "
                       "set it in the plugin config, then restart Hermes")
    url = f"{API_BASE}/{r}/{path}"
    if query:
        url += "?" + urllib.parse.urlencode({"query": query})
    try:
        from hermes_cli.plugin_provider_requests import (
            ProviderNotSignedIn, credentialed_provider_request)
    except ImportError:
        raise QboError("Hermes plugin runtime not available (standalone use "
                       "is not supported; run inside Hermes)") from None
    try:
        resp = credentialed_provider_request(PROVIDER_ID, "GET", url, timeout=60)
    except ProviderNotSignedIn as exc:
        raise QboError(
            f"QuickBooks not signed in: {exc}. Run "
            "`hermes auth add qbo-ops:quickbooks` to connect.") from None
    except Exception as exc:
        raise QboError(f"QuickBooks auth error: {exc}") from None
    if resp.status >= 300:
        body = getattr(resp, "text", "")[:300]
        raise QboError(f"QBO API HTTP {resp.status} on {path}: {body}")
    return resp.json()
