# Step 3 — Account Switcher (post-login)

**URL:** https://sellercentral.amazon.in/account-switcher/default/merchantMarketplace?returnTo=%2Fhome

## Elements (EXTRACTED)

| Element | Label | Action |
|---------|-------|--------|
| Account row | Badeja Enterprises | click to select |
| Account row | A3D7O1R9RYOLF6 | alternate seller ID |
| Select account | button (disabled until pick) | confirm |
| Search | Search for an account | filter |

## Sir instruction (Telegram)

> Click badeja enterprises > select india > select continue

## Flow edge

```
MFA_OTP --valid_otp--> AccountSwitcher
AccountSwitcher --select--> BadejaEnterprises
BadejaEnterprises --marketplace--> India
India --continue--> SellerCentralHome
```

## OTP fix applied

Plain 6-digit Telegram messages (e.g. `234182`) now parse in `otp_watcher.py`.
