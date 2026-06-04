# Create Seller Support Case (Case Log) — Master Flow Tree

**Prerequisite:** Login OK — `python -m mahika.cli seller-login` (cookies saved)  
**Command:** `python -m mahika.cli support-case`  
**Account context:** Badeja Enterprises → India  
**Tags (graphify):** `support-case`, `case-log`, `sp-api`, `seller-central`, `mahika`

---

## Family tree (poora ped)

```mermaid
flowchart TD
  ROOT([START support-case])

  ROOT --> PRE{Cookies saved?}
  PRE -->|No| LOGIN[Run seller-login first]
  PRE -->|Yes| OPEN[Playwright Chromium + load cookies]
  LOGIN --> OPEN

  OPEN --> AUTH{Still logged in?}
  AUTH -->|No| LOGIN2[ensure_seller_session + OTP 3×60s]
  AUTH -->|Yes| S7
  LOGIN2 --> S7[S7: Badeja → India → Select account]

  S7 --> ENTRY{Case Log entry path}

  ENTRY -->|D — Cursor discovery| D1[Home → ? Help]
  D1 --> D2{Dropdown}
  D2 -->|Get help and resources| D3[/help/center Help Hub]
  D2 -->|Manage support cases| D4[/cu/case-lobby Case Lobby]
  D3 --> D5[Create new issue tab]
  D4 --> D6[Create new issue button]
  D5 --> IP1
  D6 --> IP1[IP1 /help/center redirectSource=Hill]
  IP1 --> IP1A[Store India + Service Selling on Amazon]
  IP1A --> NIL[My issue is not listed — ALWAYS]
  NIL --> IP2[IP2 Troubleshoot — free-text form]
  IP2 --> F1[Fill production SP-API text — required]
  IP2 --> F2[Fill steps taken — required]
  IP2 --> SKIP[Skip reference + files]
  SKIP --> CONT[Continue]
  CONT --> IP3[IP3 Troubleshoot / contact — next screen]
  IP3 --> FORM[Submit case TBD]

  ENTRY -->|A| A1[Seller Central → Develop Apps]
  A1 --> A2{Redirect SPP?}
  A2 -->|Yes| A3[Click Case Log / Launch Case Log]
  A2 -->|No| B1

  ENTRY -->|B| B1[developer.amazonservices.com/support]
  B1 --> B2[Create a case / Case Log link]

  ENTRY -->|C| C1[Direct SPP /support/cases URL]

  A3 --> FORM[Case Log / Create case screen]
  B2 --> FORM
  C1 --> FORM

  FORM --> FILL[Fill subject + body + Developer ID + App ID + India]
  FILL --> SUB{--submit?}

  SUB -->|No| REVIEW[Browser open 120s — Sir review]
  SUB -->|Yes| SEND[Click Submit / Create case]
  REVIEW --> SAVE[Save cookies + screenshot]
  SEND --> CONFIRM{Case created?}
  CONFIRM -->|Yes| SAVE
  CONFIRM -->|Manual| REVIEW

  SAVE --> END([END OK])
```

---

## Sir recap (4 branches)

### D — Help menu (Cursor browser — **discovered May 2026**)

```
Home → ? Help
  → Get help and resources → /help/center?redirectSource=HelpHub
  → Manage support cases     → /cu/case-lobby
  → Create new issue → /help/center?redirectSource=Hill
     → IP1: set Store/Service only — **never** pick preset issue cards (bot path)
     → **My issue is not listed** only
     → IP2: troubleshoot form (help with / steps / reference #s)
```

Discovery log: [CASELOG_DISCOVERY_STEPS.md](CASELOG_DISCOVERY_STEPS.md)

### A — Ideal (login pehle ho chuka)

```
support-case
→ load cookies
→ Badeja India (agar switcher)
→ Develop Apps → Case Log
→ form fill
→ review / --submit
```

### B — Login zaroori

```
support-case
→ seller-login jaisa OTP flow (reuse ensure_seller_session)
→ Badeja India
→ Case Log paths A/B/C
→ form fill
```

### C — SPP direct (admin / developer portal)

```
Direct URL: solutionproviderportal.amazon.com/support/cases
→ Case Log list → Create case
→ same form fill
```

---

## Form fields (SP-API production case default)

| Field | Default |
|-------|---------|
| Subject | Production SP-API access — Mahika V1 |
| Body | Developer profile + sandbox OK + production 403 |
| Developer ID | A8C5XXFI7YLLM |
| App ID | amzn1.sp.solution.8fd7d23a-… |
| Marketplace | India |

Override via env: `AMAZON_SP_API_DEVELOPER_ID`, `AMAZON_SP_API_APP_ID`

---

## Screens

| Code | Matlab |
|------|--------|
| PRE | Cookies / login check |
| S7 | Account switcher (same as login flow) |
| CL | Case Log list |
| CF | Create case form |
| OK | Case submitted / saved |

---

## Outputs

| Artifact | Path |
|----------|------|
| Form screenshot | `data/mahika/logs/support_case_form.png` |
| Cookies | `seller_central_cookies.json` |
| Failure log | `seller_login_failure.log` (login fail only) |

---

## Related flows

| Flow | Link |
|------|------|
| Login (prerequisite) | [../seller-central-login/MASTER_FLOW_TREE.md](../seller-central-login/MASTER_FLOW_TREE.md) |
| SP-API checklist | `agent/scripts/sp_api_registration_checklist.md` |

---

## Code map

| File | Role |
|------|------|
| `src/mahika/playwright/support_case_flow.py` | Case Log navigation + form |
| `src/mahika/playwright/account_switcher.py` | S7 Badeja India |
| `src/mahika/playwright/seller_login.py` | Login if cookies expired |
| `scripts/raise_sp_api_production_case.py` | Legacy script (calls same flow) |
