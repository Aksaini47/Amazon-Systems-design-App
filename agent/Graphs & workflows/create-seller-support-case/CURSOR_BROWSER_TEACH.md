# Cursor browser — login + Case Log (Sir sikhata hai)

**Lane:** Cursor built-in browser only (Playwright Chromium alag session — cookies share nahi).  
**OTP helper:** Telegram → `cursor_otp.txt` (terminal mein `otp-watch`)

---

## Pehle (ek baar)

1. **`Ctrl+Shift+B`** — Browser tab side panel kholo (black panel ho to batao agent ko).
2. Terminal (alag window):

```powershell
cd "C:\Projects\Amazon Systems Design\agent"
.\.venv\Scripts\python.exe -m mahika.cli otp-watch --round-label caselog-teach
```

3. OTP aaye → sirf **6 digit** `@mahika_arun_bot` par.

---

## Step-by-step (Sir + agent)

| Step | Kya | Sir / Agent |
|------|-----|-------------|
| **0** | Sign-in URL side panel | Agent `browser_navigate` + `position: side` |
| **S1** | Email → Continue | Sir type (ya agent fill) |
| **S2** | Password → Sign in | Sir |
| **S3** | OTP picker — **Send OTP** (WhatsApp mat dabana agar Call chahiye) | Sir — default Send |
| **R8** | Amazon **60s** cooldown — wait | Sir wait |
| **S4** | Trust device ✓ → OTP box | Sir paste OTP from Telegram / `cursor_otp.txt` |
| **S7** | **Badeja Enterprises** → **India** → **Select account** | Sir click (shadow DOM — agent help limited) |
| **H1** | Home → **? Help** → dropdown | Agent / Sir |
| **2a** | **Get help and resources** → `/help/center` | Help Hub + issue picker |
| **2b** | **Manage support cases** → `/cu/case-lobby` | Case list + **Create new issue** |
| **3** | Create new issue → `IP1` (Store India, Service Selling on Amazon) | Do **not** click preset cards |
| **4** | **My issue is not listed** only | Unlocks `IP2` — click `#issueNotListedButton` (or inner `kat-button`), then human-type fields |
| **5** | `IP2` — fill 3 fields → Continue | SP-API case text |
| **CL3** | Subject + body (Mahika V1 SP-API) | Sir review — copy from [MASTER_FLOW_TREE.md](MASTER_FLOW_TREE.md) |

---

## URLs (Cursor browser address bar / agent navigate)

```
Sign-in:
https://sellercentral.amazon.in/signin?ref_=INscwp_signin_n&mons_sel_locale=en_IN&ld=SCINWPDirect

Home (Badeja India paid):
https://sellercentral.amazon.in/home?mons_sel_dir_paid=amzn1.pa.d.AB5ZXZYCP3XOLA6T5BVNPV2EXP6A

Develop Apps:
https://sellercentral.amazon.in/apps/manage?mons_sel_dir_paid=amzn1.pa.d.AB5ZXZYCP3XOLA6T5BVNPV2EXP6A

SPP Case Log (fallback):
https://solutionproviderportal.amazon.com/support/cases

Developer support:
https://developer.amazonservices.com/support
```

---

## Case text (copy-paste)

**Subject:** `Request production SP-API access — Mahika V1 private app (Badeja Enterprises India)`

**Body:** see `agent/scripts/raise_sp_api_production_case.py` or automation defaults in `support_case_flow.py`.

**IDs:** Developer `A8C5XXFI7YLLM` · App `amzn1.sp.solution.8fd7d23a-72d4-4152-a8aa-40654de8c215` · Marketplace **India**

---

## Login rules (same as Playwright)

- OTP wait: **3 × 60s** Telegram (`otp-watch`)
- Picker pe dubara **Send OTP** mat — agar OTP box (`#auth-mfa-otpcode`) dikhe
- Call **711**: Scenario 2 — 120s → resubmit → 300s ×2

Full tree: [../seller-central-login/MASTER_FLOW_TREE.md](../seller-central-login/MASTER_FLOW_TREE.md)

---

## Agent commands (is session)

```
browser_navigate → sign-in (side, newTab)
browser_snapshot → screen dekho
browser_fill / browser_click → jahan refs mile
otp-watch background → OTP file
```

**Automation lane baad mein:** `python -m mahika.cli support-case` (Playwright + saved cookies)

---

## Notes

- Cursor browser cookies **alag** hain — ek baar yahan login karna padega caselog sikhne ke liye.
- Playwright `seller-login` cookies is tab mein **auto nahi** aate.
- Black panel: `specs/cursor-browser-troubleshooting.md`
