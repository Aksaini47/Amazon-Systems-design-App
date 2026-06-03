# Step 1 — Email submitted → Password screen

**URL:** https://sellercentral.amazon.in/ap/signin  
**Previous:** step00_login_entry.md

## Elements (EXTRACTED)

| Element | Label | Playwright selector |
|---------|-------|---------------------|
| Email display | arunsaini416@gmail.com + Change link | `#ap_email` (hidden) |
| Password input | Password | `#ap_password` |
| Sign in button | Sign in | `#signInSubmit` or `input#signInSubmit` |
| Forgot password | link | `#auth-fpp-link-bottom` |

## Flow edge

```
EmailOrMobile --submit_continue--> PasswordEntry
PasswordEntry --requires--> AmazonSellerPassword
PasswordEntry --action_sign_in--> OTPOrHome
```

## Cursor browser quirk (INFERRED)

- `Continue` button is exposed as `role: button` but DOM is `SPAN#continue` — `browser_click` fails with stale ref
- **Workaround:** `form.submit()` via CDP Runtime.evaluate

## Next

Password fill → Sign in → OTP (phone ending 711)
