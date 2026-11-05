"""Authenticated, profile-scoped Desktop API under /api/plugins/qbo-ops.

Mirrors jot's pattern: Hermes imports this as a flat module, independently
of register(); we load our own sibling modules by explicit path only — no
global sys.path changes, no Hermes internals.
"""
import asyncio
import datetime
import importlib.util
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"

# Register our own package by explicit path (no global sys.path changes):
# tools.py uses relative imports, so it must load as part of a package.
import sys
import types

_pkg = types.ModuleType("qbo_ops")
_pkg.__path__ = [str(_SRC / "qbo_ops")]
sys.modules["qbo_ops"] = _pkg
import importlib

_tokens = importlib.import_module("qbo_ops.tokens")
_tools = importlib.import_module("qbo_ops.tools")

QboError = _tokens.QboError
router = APIRouter()


def _creds():
    return _tools._creds()


@router.get("/health")
async def health():
    try:
        return await asyncio.to_thread(_tools.health, None)
    except QboError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=200)


@router.get("/pnl")
async def pnl():
    today = datetime.date.today()
    args = {"start_date": today.replace(day=1).isoformat(),
            "end_date": today.isoformat()}
    try:
        return await asyncio.to_thread(_tools.pnl, args)
    except QboError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=200)


@router.get("/audit")
async def audit():
    try:
        return await asyncio.to_thread(_tools.udf_audit, {})
    except QboError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=200)


@router.get("/trace")
async def trace():
    # Placeholder: the desktop pane links into conversation for interactive
    # traces; the tool is the interactive surface, not a GET route.
    return {"hint": "use the qbo_deposit_trace agent tool with an amount"}
