# Seller Central login — full flow (3 × 60s OTP wait)

Rules: `.cursor/rules/seller-central-login.mdc`

## Master flow (normal — cookies kept)

```mermaid
flowchart TD
  START([seller-login]) --> LOAD[Load cookies]
  LOAD --> NAV[Seller Central]
  NAV -->|session OK| HOME[S6 Home]
  NAV -->|need sign-in| FLOW[Account picker / S1 / S2]
  FLOW --> S3[S3 Picker optional]
  S3 --> S4[S4 OTP]
  S4 --> TG[3 x 60s Telegram]
  TG -->|OTP| S7[S7 Badeja → India → Select account]
  S7 --> HOME[S6 Home + cookies]
  TG -->|fail| S2[Scenario 2 Call 711]
  S2 --> TG2[3 x 60s]
  TG2 --> S7
```

## Test-only branch

```mermaid
flowchart LR
  T[seller-login --fresh] --> CLR[Clear cookies + profile]
  CLR --> FLOW[Clean sign-in URL]
```

Use `--fresh` only when debugging wrong screens — **not** every login.

## OTP wait (3 attempts)

See rules file R4. Constant: `OTP_TELEGRAM_ATTEMPTS = 3`.
