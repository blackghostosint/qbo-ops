"""Guided setup script for the qbo-ops wizard (bundled skill companion).

The agent follows this turn-by-turn: one step per turn, copy-paste-ready
text the user can act on, and a check after EVERY step. Never dump the
whole script; never advance until the user confirms.

SECURITY RULE (catalog rule 11 + review ask 2): the user NEVER types
client secrets, refresh tokens, or any credential into this conversation.
Secrets move only through: the install-time secret prompt, `hermes
auth add qbo-ops:quickbooks` (the user types it in their own terminal),
or the user editing their profile .env themselves. The agent gives
pointers, never collects values. The only value that may transit chat is
the NON-secret QBO_OPS_REALM_ID (a company ID).
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
            "Step 1 of 5 — create the app (5 min).\n\n"
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
        part="Part 2+4",
        title="Register the redirect URI and enter your keys YOURSELF",
        say=(
            "Step 2 of 5 — the keys (never share them in this chat).\n\n"
            "A. In your app's left sidebar click **Keys** (under "
            "**Development**), find **Redirect URIs**, and paste EXACTLY:\n\n"
            "    http://localhost:1990/callback\n\n"
            "   (no trailing slash, http:// not https://) and **Save**.\n\n"
            "B. Enter your Client ID and Client Secret yourself — choose "
            "whichever is easier:\n"
            "   • If Hermes prompted for them during "
            "`hermes plugins install`, answer that prompt in your "
            "terminal; or\n"
            "   • Open ~/.hermes/.env in an editor and add two lines:\n"
            "       QBO_OPS_CLIENT_ID=<your client id>\n"
            "       QBO_OPS_CLIENT_SECRET=<your client secret>\n\n"
            "Do NOT paste either value here — I never need to see them.\n\n"
            "Say 'saved' when both lines are in (I'll only check that the "
            "keys EXIST, never their values)."
        ),
        expect="user says saved",
        check="Move to Part 3. If the user pastes a secret anyway: tell them "
              "to rotate it in the Intuit dashboard later and do not store "
              "or repeat it.",
    ),
    SetupStep(
        part="Part 5",
        title="Connect the grant (hermes auth add)",
        say=(
            "Step 3 of 5 — connect (1 click + 1 command).\n\n"
            "In YOUR terminal (not this chat) run:\n\n"
            "    hermes auth add qbo-ops:quickbooks\n\n"
            "A browser window opens Intuit's consent page — sign in to "
            "the QuickBooks company you want to connect and click "
            "**Connect**. Hermes catches the callback, stores the grant, "
            "and refreshes it automatically from then on.\n\n"
            "(Requires a Hermes version with plugin oauth redirect-port "
            "support for Intuit — tracked in NousResearch/hermes-agent#149642. "
            "If your build predates it, the command will fail with a "
            "redirect-URI error; see docs/SETUP.md for the manual fallback.)\n\n"
            "Say 'connected' when the command finishes."
        ),
        expect="user says connected",
        check="Verify with `hermes auth status qbo-ops:quickbooks` if "
              "available; else continue.",
    ),
    SetupStep(
        part="Part 6",
        title="Set your company (realm) ID",
        say=(
            "Step 4 of 5 — point me at your company (the one NON-secret "
            "value you may paste here).\n\n"
            "A realm ID is just a company number, not a credential. Find "
            "it: sign in at https://app.qbo.intuit.com — the number after "
            "/app/ in the address bar IS the realm ID (or see docs/SETUP.md "
            "Part 6).\n\n"
            "Either paste the number here and I'll store it, or add this "
            "line to ~/.hermes/.env yourself:\n"
            "    QBO_OPS_REALM_ID=<the number>"
        ),
        expect="user pastes the realm number or says stored",
        check="Store as QBO_OPS_REALM_ID (profile .env) if pasted; it is "
              "non-secret so echoing it back is fine.",
    ),
    SetupStep(
        part="Part 7",
        title="Restart and verify",
        say=(
            "Step 5 of 5 — restart + verify (30 sec).\n\n"
            "Hermes reads new secrets only at startup. From a terminal "
            "(not this chat):\n"
            "    hermes gateway restart\n"
            "(Desktop app users: also `systemctl --user restart "
            "hermes-dashboard` on the backend host if you use one.)\n\n"
            "Then ask me: \"is my QuickBooks connection healthy?\""
        ),
        expect="health returns company name + connected",
        check=(
            "Run qbo_health. On 'connected': celebrate briefly, then "
            "offer the sandbox/production fork below. On any error state: "
            "diagnose per the health message and the SETUP.md failure "
            "catalog (never a raw error), fix, re-run."
        ),
    ),
]


def sandbox_production_fork() -> str:
    """Offered after successful verification. No secrets transit chat."""
    return (
        "One decision left — which company do you want me to read?\n\n"
        "**Sandbox (safe practice):** your Development keys currently point "
        "at Intuit's fake demo company. Nothing you break matters. Leave "
        "everything as-is to practice with it.\n\n"
        "**Your real books (production):** done entirely in YOUR terminal "
        "and the Intuit dashboard — nothing here:\n"
        "  1. On https://developer.intuit.com/app/developer/dashboard, "
        "open your app → **Production settings** (left sidebar), complete "
        "the short questionnaire (automatic for accounting scope).\n"
        "  2. Under **Production → Keys**, copy the production Client "
        "ID/Secret and update the two QBO_OPS_CLIENT_* lines in "
        "~/.hermes/.env yourself (or re-run the installer prompt).\n"
        "  3. Re-consent with production keys: rerun `hermes auth add "
        "qbo-ops:quickbooks`.\n"
        "  4. Re-verify with the health question.\n\n"
        "You can switch between them any time by swapping which key pair "
        "is stored. Which would you like?"
    )


def next_step(steps_done: int) -> SetupStep | None:
    """Return the step the user should do next (None = all done)."""
    if steps_done >= len(STEPS):
        return None
    return STEPS[steps_done]
