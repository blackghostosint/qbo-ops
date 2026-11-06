"""Guided setup script for the qbo-ops wizard (bundled skill companion).

The agent follows this turn-by-turn: one step per turn, copy-paste-ready
text the user can act on, and a check after EVERY step. Never dump the
whole script; never advance until the user confirms (or pastes the proof
the step produces).

Steps are numbered like the docs/SETUP.md parts so the doc and the
conversation stay in sync.
"""
from dataclasses import dataclass


@dataclass
class SetupStep:
    part: str            # SETUP.md part reference
    title: str
    say: str             # exact copy-paste text the agent shows the user
    expect: str          # what completion looks like (proof to ask for)
    check: str           # what the agent does when the user confirms


STEPS = [
    SetupStep(
        part="Part 1",
        title="Create the Intuit app",
        say=(
            "Step 1 of 6 — create the app (5 min).\n\n"
            "1. Open https://developer.intuit.com and click **Sign up** "
            "(or Sign in if you have any Intuit/TurboTax/QuickBooks login).\n"
            "2. Go to https://developer.intuit.com/app/developer/dashboard\n"
            "3. Click **Create an app**.\n"
            "4. Pick **QuickBooks Online and Payments**, then "
            "**QuickBooks Online Accounting**.\n"
            "5. Name it anything (e.g. `my-hermes-qbo`) and click "
            "**Create app**.\n\n"
            "Tell me 'done' when you're on the app's page."
        ),
        expect="user says done / pastes the app name",
        check="Move to Part 2. If stuck: 'what do you see on screen?'",
    ),
    SetupStep(
        part="Part 2",
        title="Copy the Client ID and Secret",
        say=(
            "Step 2 of 6 — copy your two keys (2 min).\n\n"
            "In your app's left sidebar click **Keys** (under the "
            "**Development** heading).\n"
            "  • **Client ID** — long string like ABcd1234...\n"
            "  • **Client Secret** — click **Generate Client Secret** if "
            "not shown.\n\n"
            "Paste the Client ID here when you have it (the Secret comes "
            "next — keep both handy)."
        ),
        expect="user pastes the client ID",
        check=(
            "Store it: append QBO_OPS_CLIENT_ID=<value> to the profile "
            ".env (mask the value in any echo). Then ask for the Secret; "
            "store as QBO_OPS_CLIENT_SECRET the same way. NEVER repeat "
            "either value back in chat."
        ),
    ),
    SetupStep(
        part="Part 3",
        title="Register the redirect URI",
        say=(
            "Step 3 of 6 — register the redirect URI (1 min, the step "
            "that breaks for everyone).\n\n"
            "Still under **Development → Keys**, find **Redirect URIs** "
            "and paste EXACTLY, character for character:\n\n"
            "    http://localhost:1990/callback\n\n"
            "No trailing slash. `http://` not `https://`. Click **Save**.\n\n"
            "Say 'saved' when it's in."
        ),
        expect="user says saved",
        check="Move to Part 4.",
    ),
    SetupStep(
        part="Part 5",
        title="Consent and capture the callback URL",
        say=(
            "Step 4 of 6 — the one-time consent (2 min).\n\n"
            "Paste this into your browser's address bar, replacing only "
            "the part after client_id= with YOUR Client ID:\n\n"
            "    https://appcenter.intuit.com/connect/oauth2?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:1990/callback&response_type=code&scope=com.intuit.quickbooks.accounting&state=hermes123\n\n"
            "Sign in to the QuickBooks company you want to connect and "
            "click **Connect**.\n"
            "The browser will land on a localhost page that FAILS to load "
            "— that is expected and fine.\n\n"
            "Copy the FULL address-bar URL (it starts "
            "http://localhost:1990/callback?code=...) and paste the whole "
            "thing here."
        ),
        expect="user pastes the full callback URL (contains code= and realmId=)",
        check=(
            "Extract the code and realmId from the pasted URL. Exchange "
            "the code (curl -X POST "
            "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer "
            "-u \"CLIENT_ID:CLIENT_SECRET\" -d "
            "\"grant_type=authorization_code&code=<code>&redirect_uri="
            "http://localhost:1990/callback\"). Store the refresh_token as "
            "QBO_OPS_REFRESH_TOKEN and the realmId as QBO_OPS_REALM_ID. "
            "If invalid_grant: the code expired (5 min) — issue a fresh "
            "consent URL and retry."
        ),
    ),
    SetupStep(
        part="Part 7",
        title="Restart and verify",
        say=(
            "Step 5 of 6 — restart (30 sec).\n\n"
            "Hermes only reads new secrets at startup. From a terminal "
            "(not in this chat) run:\n\n"
            "    hermes gateway restart\n\n"
            "(If you're on the desktop app, also restart "
            "hermes-dashboard: `systemctl --user restart hermes-dashboard`.)\n\n"
            "Say 'restarted' when it's back."
        ),
        expect="user says restarted",
        check="Move to the verify step.",
    ),
    SetupStep(
        part="Part 7",
        title="Verify live",
        say=(
            "Step 6 of 6 — verify (10 sec).\n\n"
            "Ask me: \"is my QuickBooks connection healthy?\"\n\n"
            "(Type it as a normal message so the qbo_health tool runs.)"
        ),
        expect="health returns company name + connected",
        check=(
            "Run qbo_health. On 'connected': celebrate briefly, then "
            "offer the sandbox/production fork below. On any error state: "
            "diagnose per the health message (never a raw error), fix, "
            "re-run."
        ),
    ),
]


def sandbox_production_fork() -> str:
    """Offered after successful verification."""
    return (
        "One decision left — which company do you want me to read?\n\n"
        "**Sandbox (safe practice):** your Development keys currently point "
        "at Intuit's fake demo company. Nothing you break matters. Leave "
        "everything as-is to practice with it.\n\n"
        "**Your real books (production):** two extra moves —\n"
        "  1. On https://developer.intuit.com/app/developer/dashboard, "
        "open your app → **Production settings** (left sidebar), complete "
        "the short questionnaire (automatic for accounting scope).\n"
        "  2. Redo the consent (Step 4) using the **Production** keys tab "
        "— Client ID/Secret change, the redirect URI stays "
        "http://localhost:1990/callback.\n"
        "Then update QBO_OPS_CLIENT_ID/QBO_OPS_CLIENT_SECRET to the "
        "production pair and re-verify.\n\n"
        "You can switch between them any time by swapping which key pair "
        "is stored. Which would you like?"
    )


def next_step(steps_done: int) -> SetupStep | None:
    """Return the step the user should do next (None = all done)."""
    if steps_done >= len(STEPS):
        return None
    return STEPS[steps_done]
