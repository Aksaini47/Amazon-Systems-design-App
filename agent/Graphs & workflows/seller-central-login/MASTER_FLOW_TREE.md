# Seller Central Login — Master Flow Tree (saral)

**Command:** `python -m mahika.cli seller-login`  
**Test reset:** `--fresh` (sirf debug)  
**Account:** Badeja Enterprises → India → Select account (S7)

**Tags (graphify):** `login-flow`, `seller-central`, `otp-telegram`, `account-switcher`, `call-711`, `mahika`

---

## Family tree (poora ped)

```mermaid
flowchart TD
  ROOT([Mahika seller-login START])

  ROOT --> OPEN[Open Seller Central]

  OPEN --> GATE{Pehle kya dikha?}

  GATE -->|Cookies OK / Home| HOME_A[S6 Home ✓]
  GATE -->|Account switcher| SW_A[S7 Badeja → India → Select]
  SW_A --> HOME_A

  GATE -->|Sirf email / account row| SHORT[Shortcut branch]
  SHORT --> TAP[Mail tap / Continue]
  TAP --> GATE2{Logged in?}
  GATE2 -->|Home| HOME_A
  GATE2 -->|Switcher| SW_A
  GATE2 -->|OTP phase| OTP_SHORT[Scenario 3]

  GATE -->|Email form| FULL[Full sign-in branch]
  FULL --> S1[S1 Email + Continue]
  S1 --> S2[S2 Password + Sign in]
  S2 --> GATE3{OTP screen?}

  GATE3 -->|Picker S3| PICK[Send OTP default 1× + R8 60s]
  PICK --> S4[S4 OTP entry]
  GATE3 -->|Seedha S4| S4

  S4 --> TRUST[Tick trust device]
  TRUST --> WAIT3[Telegram 3 × 60s — attempt 1/3, 2/3, 3/3]

  WAIT3 -->|OTP mila| SUB[OTP submit]
  SUB --> S7[S7 Badeja → India → Select]
  S7 --> HOME_B[S6 Home + cookies SAVE ✓]

  WAIT3 -->|3 min fail| CALL_TREE[Call 711 branch — Scenario 2]

  CALL_TREE --> R1{Round 1 or 2?}

  R1 --> C_SUB[Call 711 submit]
  C_SUB --> C120[Wait 120 seconds]
  C120 --> C_RES[Resubmit Call 711]
  C_RES --> C300[Wait 300s + Telegram poll]

  C300 -->|OTP| SUB
  C300 -->|fail round 1| R1
  C300 -->|fail round 2| FAIL[FAIL: screenshot + seller_login_failure.log]
  FAIL --> CLOSE[Script CLOSE]

  OTP_SHORT --> PICK3[Call 711 if picker else S4 wait 3×60s]
  PICK3 --> SUB

  HOME_A --> END([END OK])
  HOME_B --> END
```

---

## Teen bade branches (Sir recap)

### 1) Ideal

```
Open SC → Mail → Password → OTP (Send once) → 3×60s wait
→ OTP Telegram → Submit → S7 Badeja→India → Home ✓
```

### 2) Cold + Call

```
Open SC → Mail → Password → OTP Send → 3×60s (fail)
→ Call 711 submit → 120s → Resubmit 711 → 300s (+ Telegram)
→ (agar fail) Round 2 same
→ (agar phir fail) Log save + script CLOSE
```

### 3) Shortcut (cookies)

```
Open SC → (email/account dikha) → Continue
→ Home YA Switcher (S7) YA OTP screen (Scenario 3)
```

---

## Screen codes

| Code | Matlab |
|------|--------|
| S1 | Email |
| S2 | Password |
| S3 | OTP picker |
| S4 | OTP type box |
| S5 | Didn't receive list |
| S7 | Badeja → India → Select account |
| S6 | Home |
| R8 | Amazon 60s cooldown |
| RL | Rate limit — 1 min wait |

---

## Timers (code)

| Step | Seconds |
|------|---------|
| Telegram wait (Scenario 1) | 3 × 60 = **180s** |
| After Call 711 submit | **120s** |
| After Call 711 resubmit | **300s** |
| Call rounds max | **2** |
| R8 Amazon cooldown | 60s |

---

## Code map

| File | Kaam |
|------|------|
| `src/mahika/playwright/seller_login.py` | Scenarios, Call 711, fail close |
| `src/mahika/playwright/account_switcher.py` | S7 |
| `src/mahika/playwright/amazon_signin_flow.py` | Picker, R8 |
