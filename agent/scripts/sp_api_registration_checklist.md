# Amazon SP-API — Registration Checklist (Badeja / Mahika)

Last verified: 2026-05-20 via Solution Provider Portal (admin: Trendylifestyle46@gmail.com)

## Current status

| Item | Value / status |
|------|----------------|
| Developer profile ID | `A8C5XXFI7YLLM` |
| SPP email | Trendylifestyle46@gmail.com |
| Sandbox app | **Mahika v1** (exists) |
| Production app | **Not created** — requires Developer Profile approval |
| India marketplace ID | `A21TJRUUN4KGV` |
| India paid account ID | `amzn1.pa.d.AB5ZXZYCP3XOLA6T5BVNPV2EXP6A` |
| SP-API region (India) | `eu-west-1` |
| SPP onboarding Step 2 | **Done** (profile consolidated) |
| SPP migration | **In progress** — up to 2 hours; credentials UI temporarily empty |

## Env vars (root `.env` → `scripts/sync_env.ps1`)

```env
MAHIKA_SP_API_LWA_CLIENT_ID=          # from SPP → Developer Central → app → LWA credentials
MAHIKA_SP_API_LWA_CLIENT_SECRET=      # same
MAHIKA_SP_API_REFRESH_TOKEN=          # Authorize app on Seller Central (India account)
MAHIKA_SP_API_ROLE_ARN=               # leave empty for private self-authorized seller apps
MAHIKA_SP_API_REGION=eu-west-1
MAHIKA_SP_API_MARKETPLACE_ID=A21TJRUUN4KGV
MAHIKA_SP_API_SANDBOX=true          # false after production refresh token

# Legacy backend (same LWA values, different names)
BACKEND_AMAZON_CLIENT_ID=
BACKEND_AMAZON_CLIENT_SECRET=
BACKEND_AMAZON_REFRESH_TOKEN=
BACKEND_AMAZON_MARKETPLACE_ID=A21TJRUUN4KGV
```

## Portal paths (use onboarding India context — not bare `/` URL)

1. **Onboarding (India):**  
   `https://solutionproviderportal.amazon.com/account/program?enrollmentApplicationId=hC8h11s1&mons_sel_dir_paid=amzn1.pa.d.AB5ZXZYCP3XOLA6T5BVNPV2EXP6A`

2. **Developer Central (after migration):**  
   `https://solutionproviderportal.amazon.com/sellingpartner/developerconsole`

3. **Switch account:** pick profile **A8C5XXFI7YLLM - United States** (developer profile; not seller marketplace)

> **Note:** SPP account switcher shows US for developer profile IDs. India seller data uses `A21TJRUUN4KGV` in API calls regardless.

## Do NOT use Edit App

The **Edit App** page (App name + API Type + Save/Delete only) does **not** show
roles, OAuth, LWA credentials, or refresh tokens. Opening it repeatedly wastes time.

| Need | Where to go instead |
|------|---------------------|
| LWA Client ID + Secret | Developer Central **list view** → **Mahika V1** card → **View LWA credentials** |
| Sandbox refresh token | Same card → **▼ dropdown** (next to Edit App) → **Create Token** → **Sandbox Testing** |
| Production refresh token | After profile approval: Authorize flow on Seller Central (India), not Edit App |
| Roles (Orders, Finances, Reports) | Production app setup / authorization flow — not on sandbox Edit App page |

## Steps when migration completes

### A. Get LWA Client ID + Secret

1. SPP → **Developer Central** (list view) → **Mahika V1** card.
2. **View LWA credentials** → copy Client Identifier + Client Secret into `.env`.
3. Do **not** open Edit App for this.

### B. Get Refresh Token

**Sandbox (API wiring tests only):**

1. Developer Central → **Mahika V1** → **▼** → **Create Token** → **Sandbox Testing** → **Create Token**.
2. Copy token (starts with `Atzr|`) into `.env`.

**Production (live Badeja India data — after profile approval):**

1. Create/authorize **Production** app with required roles.
2. Seller Central → authorize for **Badeja Enterprises | India**.
3. Copy production refresh token into `.env`.

### C. Sync and verify

```powershell
powershell -File scripts\sync_env.ps1
cd agent
.\.venv\Scripts\python.exe -m mahika.cli doctor
```

Expect: `[8/10] SP-API credentials` → all PASS when refresh + LWA filled.

## Code fix (sandbox token → wrong endpoint)

Mahika now sets `AWS_ENV=SANDBOX` when `MAHIKA_SP_API_SANDBOX=true` (default).
Without this, `python-amazon-sp-api` hits **production** URLs and returns 403
even though the sandbox token is valid.

Verify:

```powershell
powershell -File scripts\sync_env.ps1
cd agent
.\.venv\Scripts\python.exe scripts\sp_api_probe.py
.\.venv\Scripts\python.exe -m mahika.cli doctor
```

Expect: `mahika_ping` / `SP-API reachable` → **sandbox OK — 2 mock order(s)**.

When production is ready: set `MAHIKA_SP_API_SANDBOX=false`, replace refresh
token with production authorize token, re-run probe.

## What works today (no portal action needed)

Credentials already in `.env` (synced via `scripts/sync_env.ps1`):

- LWA token exchange: **works** (refresh → access token)
- SP-API sandbox orders (mock): **works** with `MAHIKA_SP_API_SANDBOX=true`
- SP-API live Badeja data: **blocked** until production app + profile approval
- Mahika reports lane: **works** via Seller Central CSV download + `mahika.cli reports analyze`

## Blockers today

- **Migration in progress:** app list may show “no application clients”; Save on new app may not persist.
- **Production disabled:** complete Developer Profile vetting in SPP for live India order/refund data.
- **Mahika V1 is sandbox only:** fine for API wiring tests; not for live SAFE-T polling.
- **Edit App is a dead end:** only app name/API type — never send anyone there for credentials.

## Telegram / OTP

OTP for SPP sign-in goes to phone ending **503**. Forward Amazon SMS to `@mahika_arun_bot` before automated login.
