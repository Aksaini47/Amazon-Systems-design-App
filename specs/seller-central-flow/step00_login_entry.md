# Step 0 — Seller Central Login Entry

**Date:** 2026-05-20  
**Tool:** Cursor inbuilt browser (discovery lane)  
**URL:** https://sellercentral.amazon.in/ap/signin

## Page elements (EXTRACTED)

| Element | Label / role | Selector hint (Playwright later) |
|---------|--------------|----------------------------------|
| Email input | "Enter mobile number or email" | `#ap_email` or `input[name=email]` |
| Continue button | "Continue" | `input#continue` |
| Register | "Register now" | link |
| Cookie warning | "Please Enable Cookies to Continue" | heading (may be a11y-only) |

## Flow edge

```
SellerCentralSignIn --requires--> EmailOrMobile
EmailOrMobile --action_continue--> PasswordOrOTP
```

## Notes

- Amazon redirects signin URL → `/ap/signin` with OpenID params
- Locale: en_IN
- assoc_handle: sc_in_amazon_v2

## Next step

Sir teaches after login home — SAFE-T claim wizard steps 1–6.
