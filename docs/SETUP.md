# Complete Setup Walkthrough — qbo-ops from zero

This guide assumes you have **never** touched a developer portal. Every
click is listed. Time: ~10 minutes, one time only.

You will create: an Intuit developer app (free), copy two codes into
Hermes, paste one more from a one-time consent page, and paste your
company ID. After that, the plugin refreshes everything itself.

---

## Part 1 — Create your Intuit app (5 min)

1. Go to **https://developer.intuit.com** and click **Sign up** (top right).
   - Use your normal email; create a password. Verify the email if asked.
   - Already have Intuit/TurboTax/QuickBooks login? That works — **Sign in**.
2. Once signed in, open **https://developer.intuit.com/app/developer/dashboard**
   (this is the "Dashboard" — it's linked in the left sidebar as
   **Dashboard**).
3. Click **Create an app** (blue button, top right area).
4. When asked what the app does, choose **QuickBooks Online and Payments** —
   then on the next screen select **QuickBooks Online Accounting** only.
5. Name the app anything you like — e.g. `my-hermes-qbo` — and accept the
   license terms. Click **Create app**.

## Part 2 — Get your Client ID and Client Secret (2 min)

6. In your new app's page, find the left sidebar and click **Keys** under
   the "Development" heading.
7. You will see two long strings:
   - **Client ID** — looks like `ABcd1234EfGh5678IjKl90MnOpQrStUv12`
   - **Client Secret** — looks like a longer random string
   - (If the secret isn't shown, click **Generate Client Secret**.)
8. Leave this browser tab open — you'll copy these in Part 4.
   - Use the **Development** keys first — they are free and safe. Production
     keys require an Intuit review and are only needed when you connect your
     real company file later (Part 6 covers that switch).

## Part 3 — Register the redirect URI (1 min, the step that breaks for everyone)

9. Still under **Development → Keys**, find the section **Redirect URIs**.
10. Paste EXACTLY this, character for character:
    ```
    http://localhost:1990/callback
    ```
11. Click **Save**. Double-check there is no trailing slash and the scheme
    is `http://` not `https://` — **a mismatch here is the #1 setup
    failure** (the consent page will say `redirect_uri` error later).

## Part 4 — Put the credentials into Hermes (2 min)

In a terminal, run the installer prompt flow:

```bash
hermes plugins install blackghostosint/qbo-ops
```

- When prompted, paste the **Client ID**, then the **Client Secret** from
  Part 2.
- When prompted for the **refresh token** (Part 5 gives you this), you can
  press Enter to skip — you'll add it in a moment.
- When prompted for the **Realm ID** (Part 6), skip for now too.

Already installed and skipped? Two ways to add them:

- **Let your agent do it:** say *"set up QuickBooks"* — it will ask for the
  two values one at a time and store them in your profile's
  `~/.hermes/.env` for you (this is what happened on every install: the
  installer itself prompts for each secret by name, and skipping is fine).
- **Do it by hand:** append to `~/.hermes/.env`:
  ```
  QBO_OPS_CLIENT_ID=paste_client_id_here
  QBO_OPS_CLIENT_SECRET=paste_client_secret_here
  ```
  (One `NAME=value` per line, no quotes needed. Restart Hermes after.)

## Part 5 — Authorize and get the refresh token (2 min)

12. Build your consent URL in a browser address bar — replace
    `YOUR_CLIENT_ID` with your Client ID from Part 2:
    ```
    https://appcenter.intuit.com/connect/oauth2?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:1990/callback&response_type=code&scope=com.intuit.quickbooks.accounting&state=hermes123
    ```
13. Open it, sign in to **the QuickBooks company you want to connect**, and
    click **Connect** on the consent screen.
14. The browser will land on `localhost:1990/callback` — the page will
    **fail to load** (nothing is listening) — **that is expected and fine**.
15. Copy the FULL URL from the address bar. It looks like:
    ```
    http://localhost:1990/callback?code=AB1234567890...&realmId=1234567890123456
    ```
16. Exchange the code for a refresh token — one terminal command. Replace
    `CLIENT_ID`, `CLIENT_SECRET`, and the `code=` value from your URL:
    ```bash
    curl -s -X POST https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer \
      -u "CLIENT_ID:CLIENT_SECRET" \
      -d "grant_type=authorization_code&code=PASTE_CODE_HERE&redirect_uri=http://localhost:1990/callback"
    ```
    (Your agent can run this for you — paste it the whole address-bar URL
    and say *"exchange this"*.)
17. The reply is JSON. Find the long `"refresh_token": "..."` value (it
    starts `RT1-...` or similar) and save it — same two routes as Part 4:
    tell your agent *"set QBO_OPS_REFRESH_TOKEN to ..."* (it stores it for
    you), or append `QBO_OPS_REFRESH_TOKEN=paste_it_here` to
    `~/.hermes/.env` yourself.

## Part 6 — Your company (Realm) ID

18. Look again at the address-bar URL from step 15 — the `realmId=` number
    **is your company ID**. Save it the same way:
    *"set QBO_OPS_REALM_ID to ..."* to your agent, or append
    `QBO_OPS_REALM_ID=paste_the_number` to `~/.hermes/.env`.

## Part 7 — Verify (30 seconds)

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
your real books, go back to
**https://developer.intuit.com/app/developer/dashboard**, open your app →
left sidebar → **Production settings** (under "Production"), complete the
short questionnaire (it's automatic for standard accounting scope), then
repeat Parts 3–6 using the **Production** keys tab. Same redirect URI.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Consent page: `redirect_uri` mismatch | URI not registered verbatim (Part 3) | Re-check exactly `http://localhost:1990/callback` |
| `invalid_grant` on token exchange | Code single-use/expired (5 min) | Redo Part 5 with a fresh consent |
| `qbo_health`: "reauth_required" | Refresh token revoked (100+ days idle, password change) | Redo Part 5 |
| `qbo_health`: names a missing secret | Skipped at install | Re-add the secret (Part 4 routes) |
| Everything set but still error | Hermes hasn't re-read secrets | `hermes gateway restart` |

### Deeper failure catalog (for agent diagnosis)

| Error signature | Root cause | Remediation |
|---|---|---|
| HTTP 400 `invalid_client` | Client ID/Secret pair wrong for the token endpoint (prod keys vs dev consent or vice versa) | Confirm which keypair is stored; consent and keys must come from the same tab (Development or Production) |
| HTTP 400 `unauthorized_client` | App lacks the accounting scope / app type wrong | Recreate app with **QuickBooks Online Accounting** selected; re-consent |
| HTTP 403 on API calls | Company not authorized to the app, or scope lost | Re-run consent (Part 5) — the company must be the one you signed into |
| `invalid_grant` at refresh (was working) | Token family revoked: 100+ days idle, password change, or another integration rotated the token out from under us | Re-consent (Part 5). Prevention: only one integration should own the refresh token |
| Two integrations, tokens keep dying | Refresh-token rotation: each integration refreshing invalidates the other's copy | Give each integration its own Intuit app; don't share a client pair |
| HTTP 429 | Intuit rate limit (500 req/min typical) | Back off 60s; the plugin surfaces it as an error state, not a hang |
| `qbo_query` returns empty but data exists | Query entity/field misspelled, or date format wrong | QBO SQL wants `YYYY-MM-DD` quoted dates; entity names are case-sensitive (`Purchase`, not `purchases`) |
| Realm ID mismatch / "company not found" | realmId from sandbox consent used with production keys (or vice versa) | Re-consent against the same environment as the stored keys; the realmId rides the callback URL |
| Dashboard shows plugin but tools missing in session | Plugin installed after session start | New session (tools load at session start), or restart the backend |
