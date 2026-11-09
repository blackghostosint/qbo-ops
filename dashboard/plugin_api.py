"""Authenticated, profile-scoped Desktop API under /api/plugins/qbo-ops.

Hermes imports this as a flat module, independently of register(); we load
our sibling package by explicit path only — no global sys.path changes,
no Hermes internals.
"""
import asyncio
import datetime
import sys
import types
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"

# Register our own package by explicit path (tools.py uses relative imports).
_pkg = types.ModuleType("qbo_ops")
_pkg.__path__ = [str(_SRC / "qbo_ops")]
sys.modules.setdefault("qbo_ops", _pkg)
import importlib

_tools = importlib.import_module("qbo_ops.tools")

router = APIRouter()


@router.get("/health")
async def health():
    try:
        return await asyncio.to_thread(_tools.health, None)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=200)


@router.get("/pnl")
async def pnl():
    today = datetime.date.today()
    args = {"start_date": today.replace(day=1).isoformat(),
            "end_date": today.isoformat()}
    try:
        return await asyncio.to_thread(_tools.pnl, args)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=200)


@router.get("/audit")
async def audit():
    try:
        return await asyncio.to_thread(_tools.udf_audit, {})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=200)


@router.get("/trace")
async def trace():
    # The desktop pane links into conversation for interactive traces; the
    # qbo_deposit_trace agent tool is the interactive surface, not a GET route.
    return {"hint": "use the qbo_deposit_trace agent tool with an amount"}
