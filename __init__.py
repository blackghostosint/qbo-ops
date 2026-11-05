"""qbo-ops: QuickBooks Online operations plugin for Hermes.

Registers agent tools (health, P&L, close audit, deposit trace) and exposes
a Python backend for the desktop pane (dashboard/plugin_api.py).
"""
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

__version__ = "0.1.0"


def register(ctx):
    from pathlib import Path

    from qbo_ops.tools import register as register_tools

    register_tools(ctx)
    skill_md = Path(__file__).resolve().parent / "skills" / "qbo-ops-reconciliation" / "SKILL.md"
    try:
        ctx.register_skill(
            "qbo-ops-reconciliation", skill_md,
            description="QBO reconciliation tradecraft: close audits, deposit-wash detection, backdated-entry forensics.",
        )
    except Exception:
        pass  # skill registration is best-effort; tools are the core surface
