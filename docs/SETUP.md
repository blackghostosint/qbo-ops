# Complete Setup Walkthrough — qbo-ops from zero

This guide assumes you have **never** touched a developer portal. Every
click is listed. Time: ~10 minutes, one time only.

**One rule throughout: your Client Secret and any token are YOURS — they
never need to be pasted into a chat with your agent.** They go only into
Hermes's install-time prompt or your own `~/.hermes/.env`, and the grant
is created by `hermes auth add` in your own terminal. Your agent can
verify things exist; it never needs to see their values.

---

## Part 1 — Create your Intuit app (5 min)

1. Go to **https://developer.intuit.com** and click **Sign up** (top right).
   - Use your normal email; create a password. Verify the email if asked.
   - Already have Intuit/TurboTax/QuickBooks login? That works — **Sign in**.
2. Once signed in, open **https://developer.intuit.com/app/developer/dashboard**.
3. Click **Create an app**.
4. Choose **QuickBooks Online and Payments**, then select
   **QuickBooks Online Accounting** only.
5. Name the app anything you like — e.g. `my-hermes-qbo` — accept the
   license terms, click **Create app**.

## Part 2 — Register the redirect URI (1 min, the step that breaks for everyone)

6. In your app's left sidebar click **Keys** under the **Development** heading.
7. Find the **Redirect URIs** section and paste EXACTLY this, character for
   character:
    ```
    http://localhost:1990/callback
    ```
8. Click **Save**. No trailing slash; `http://` not `https://` — **a
   mismatch here is the #1 setup failure**.

## Part 3 — Enter your Client ID and Secret yourself (2 min)

9. Still under **Development → Keys**, copy the **Client ID** and
   **Client Secret** (click **Generate Client Secret** if not shown).
   - Use the **Development** keys first — free and safe. Production keys
     come later (see "Going live" below).
10. Enter them YOURSELF, in one of these two ways — never in a chat:
    - **Install-time prompt:** if `hermes plugins install
      blackghostosint/qbo-ops` prompted for these values, answer it in
      your terminal.
    - **By hand:** open `~/.hermes/.env` in an editor and add:
      ```
      QBO_OPS_CLIENT_ID=paste_your_client_id
      QBO_OPS_CLIENT_SECRET=paste_your_client_secret
      ```
      (One `NAME=value` per line, no quotes. Restart Hermes after.)

## Part 4 — Connect the grant (1 click + 1 command)

11. In YOUR terminal (not a chat window) run:
    ```
    hermes auth add qbo-ops:quickbooks
    ```
12. A browser opens Intuit's consent page — sign in to **the QuickBooks
    company you want to connect** and click **Connect**. Hermes catches
    the callback, stores the grant, and refreshes the token automatically
    from then on. The plugin never holds or refreshes tokens itself.
    - Requires a Hermes build with plugin oauth redirect-port support for
      Intuit (upstream: NousResearch/hermes-agent#149642). If your build
      predates it, this command fails with a redirect-URI error — the
      entry lists and activates for users once that change ships.

## Part 5 — Your company (Realm) ID

13. The realm ID is a **company number, not a secret**. Find it: sign in
    at **https://app.qbo.intuit.com** — the number after `/app/` in the
    address bar is your realm ID.
14. You may paste it to your agent to store, or add it yourself:
    ```
    QBO_OPS_REALM_ID=paste_the_number
    ```

## Part 6 — Verify (30 seconds)

Restart Hermes so the new secrets are picked up:

```bash
hermes gateway restart
```

Then ask your agent:

> **"is my QuickBooks connection healthy?"**

You should hear your company's name and **connected**. If anything is off,
the health tool tells you exactly which piece is missing or expired — it
never dumps a raw error.

---

## Going live with your real company (when ready)

Development keys work with a **sandbox** company by default. To connect
your real books:

1. Go to **https://developer.intuit.com/app/developer/dashboard**, open
   your app → **Production settings** (left sidebar), complete the short
   questionnaire (automatic for standard accounting scope).
2. Under **Production → Keys**, copy the production **Client ID/Secret**
   and update your two `QBO_OPS_CLIENT_*` lines in `~/.hermes/.env`
   yourself.
3. Re-consent with production keys: run `hermes auth add
   qbo-ops:quickbooks` again.
4. Re-verify with the health question. Same redirect URI throughout.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Consent page: `redirect_uri` mismatch | URI not registered verbatim (Part 2) | Re-check exactly `http://localhost:1990/callback` |
| `hermes auth add` fails with redirect-URI error | Hermes build predates redirect-port support (#149642) | Update Hermes; the change is tracked upstream |
| `invalid_grant` at sign-in | Consent code single-use/expired (5 min) | Re-run `hermes auth add` |
| `qbo_health`: "reauth_required" | Grant revoked (100+ days idle, password change) | Re-run `hermes auth add` |
| `qbo_health`: names a missing secret | Skipped at install | Add the named value yourself (Part 3 route) |
| Everything set but still error | Hermes hasn't re-read secrets | `hermes gateway restart` |

### Deeper failure catalog (for agent diagnosis)

| Error signature | Root cause | Remediation |
|---|---|---|
| HTTP 400 `invalid_client` | Client ID/Secret pair wrong for the environment (prod keys vs dev consent or vice versa) | Confirm which keypair is stored; keys and consent must come from the same tab (Development or Production) |
| HTTP 400 `unauthorized_client` | App lacks the accounting scope / app type wrong | Recreate app with **QuickBooks Online Accounting** selected; re-consent |
| HTTP 403 on API calls | Company not authorized to the app, or scope lost | Re-consent (Part 4) — the company must be the one you signed into |
| `invalid_grant` at refresh (was working) | Grant revoked: 100+ days idle, password change | Re-consent (Part 4); Hermes owns the refresh, no data is lost |
| HTTP 429 | Intuit rate limit (500 req/min typical) | Back off 60s; the plugin surfaces it as an error state, not a hang |
| `qbo_query` returns empty but data exists | Query entity/field misspelled, or date format wrong | QBO SQL wants `YYYY-MM-DD` quoted dates; entity names are case-sensitive (`Purchase`, not `purchases`) |
| Realm ID mismatch / "company not found" | realmId from sandbox used with production keys (or vice versa) | Re-consent against the same environment as the stored keys |
| Dashboard shows plugin but tools missing in session | Plugin installed after session start | New session (tools load at session start), or restart the backend |
