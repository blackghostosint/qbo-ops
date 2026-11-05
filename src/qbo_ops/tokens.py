#!/usr/bin/env python3
"""QBO OAuth token management — flock-guarded single-refresher.

Ported from the battle-tested qbo_token.py (Mailbox Plus production, Oct 2026).
Key invariants preserved from the original:
- The read-token -> refresh -> persist sequence happens inside ONE exclusive
  flock. Consumers that refresh outside the lock then persist later are what
  let two processes refresh with the same token; Intuit's reuse-detection then
  revokes the whole token family.
- The refresh token is ALWAYS re-read from the credential store inside the
  lock, so a sibling process's rotation is picked up instead of replayed-over.
- The access token is cached with its own expiry; consumers within its ~1h
  life reuse it and never rotate anything.

Plugin adaptation (catalog rule 11): credentials come from Hermes secret
scope (requires_env declarations in plugin.yaml), never from .env files.
"""
import base64
import errno
import fcntl
import json
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
API_BASE = "https://quickbooks.api.intuit.com/v3/company"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128 Safari/537.36")
MIN_REMAINING_S = 120


class QboError(Exception):
    """User-presentable QBO error (health tool turns this into guidance)."""


class QboCredentials:
    """Credential access + token cache, resolved via Hermes secret scope.

    Under the Hermes plugin runtime, secrets arrive through
    agent.secret_scope.get_secret(). For standalone/test use, an explicit
    dict can be injected via `from_env` (never touches .env files itself).
    """

    def __init__(self, getter):
        self._get = getter  # callable(name) -> str or None
        self._access_token = None
        self._access_exp = 0.0

    @classmethod
    def from_mapping(cls, mapping):
        return cls(lambda name: mapping.get(name))

    @classmethod
    def from_secret_scope(cls):
        from agent.secret_scope import get_secret  # Hermes runtime-injected

        return cls(get_secret)

    def missing(self):
        need = ["QBO_OPS_CLIENT_ID", "QBO_OPS_CLIENT_SECRET",
                "QBO_OPS_REFRESH_TOKEN", "QBO_OPS_REALM_ID"]
        return [k for k in need if not self._get(k)]

    def refresh(self, force=False):
        """Return a valid access token, refreshing if needed. Thread/process
        safety comes from the caller holding the flock (see locked()).
        """
        if (not force and self._access_token
                and self._access_exp - time.time() > MIN_REMAINING_S):
            return self._access_token
        cid, csec = self._get("QBO_OPS_CLIENT_ID"), self._get("QBO_OPS_CLIENT_SECRET")
        rtok = self._get("QBO_OPS_REFRESH_TOKEN")
        if not (cid and csec and rtok):
            raise QboError("QBO credentials incomplete: client ID, client secret "
                           "and refresh token are all required")
        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": rtok,
        }).encode()
        req = urllib.request.Request(TOKEN_URL, data=data)
        req.add_header("Authorization", "Basic " + base64.b64encode(
            f"{cid}:{csec}".encode()).decode())
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("User-Agent", UA)
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            raise QboError(
                f"Intuit refresh failed HTTP {e.code}: {body}. "
                "If this is invalid_grant, the refresh token was revoked "
                "(100+ days idle or a password change) — re-run the OAuth "
                "consent flow.") from None
        except Exception as e:
            raise QboError(f"Intuit refresh failed: {type(e).__name__}: {e}") from None
        if "access_token" not in resp:
            raise QboError(f"no access_token in Intuit response: {str(resp)[:300]}")
        self._access_token = resp["access_token"]
        self._access_exp = time.time() + int(resp.get("expires_in", 3600))
        return self._access_token


class TokenLock:
    """Context manager: with TokenLock(creds): creds.refresh() ..."""

    def __init__(self, credentials, lock_path="/tmp/qbo_ops_token.lock", wait_s=45):
        self.credentials = credentials
        self.lock_path = lock_path
        self.wait_s = wait_s
        self._lockf = None

    def __enter__(self):
        self._lockf = open(self.lock_path, "w")
        lockf = self._lockf
        assert lockf is not None
        deadline = time.time() + self.wait_s
        while True:
            try:
                fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self.credentials
            except OSError as e:
                if e.errno not in (errno.EAGAIN, errno.EACCES):
                    raise
                if time.time() >= deadline:
                    raise QboError(
                        f"token lock held by another process for {self.wait_s}s "
                        "— refusing to deadlock") from None
                time.sleep(2)

    def __exit__(self, *exc):
        lockf = self._lockf
        if lockf is not None:
            fcntl.flock(lockf, fcntl.LOCK_UN)
            lockf.close()
        return False


def qbo_get(credentials, path, query=None):
    """Authenticated GET against the QBO v3 API. Returns parsed JSON."""
    with TokenLock(credentials):
        token = credentials.refresh()
    realm = credentials._get("QBO_OPS_REALM_ID")
    url = f"{API_BASE}/{realm}/{path}"
    if query:
        url += "?" + urllib.parse.urlencode({"query": query})
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", UA)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        raise QboError(f"QBO API HTTP {e.code} on {path}: {body}") from None
