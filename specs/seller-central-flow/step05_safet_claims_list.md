# Step 5 — Navigate to Manage SAFE-T Claims

**Sir instruction (Telegram):** Menu (☰) → Orders → Manage SAFE-T Claims  
**URL:** https://sellercentral.amazon.in/safet-claims/ref=xx_safet_dnav_xx  
**Page title:** Manage SAFE-T Claims

## Navigation path (EXTRACTED)

| Step | Action | Notes |
|------|--------|-------|
| 1 | Click hamburger menu (top-left) | ref `e0` / shadow DOM |
| 2 | Click **Orders** | sidebar item — CDP text match on SPAN |
| 3 | Click **Manage SAFE-T Claims** | link in Orders submenu |

**Direct URL (shortcut):** `/safet-claims/ref=xx_safet_dnav_xx`

## Page elements (EXTRACTED)

| Element | Label | Purpose |
|---------|-------|---------|
| File a new SAFE-T Claim | link | **Start new claim wizard** |
| Download the SAFE-T Report | link | export |
| Learn More | link | help |
| Tabs | All / Awaiting Seller Response / Granted / Denied / Under Investigation | filter claims |
| Search | Order ID, ASIN, SAFE-T ID | lookup |
| Filters | ALL, Claim date, Last 30 days, Fulfillment channel | table filters |

## Stats visible (session snapshot)

- Granted: 9 of 10 (90%)
- Claims value granted: ₹16,636.39
- Sample order IDs in table: 171-7816574-9085140, 402-5053795-7029953, etc.

## Flow edge

```
HomeDashboard --menu_orders--> OrdersSubmenu
OrdersSubmenu --manage_safet_claims--> SafetClaimsList
SafetClaimsList --file_new_claim--> SafetWizardStep1
```

## Playwright notes (INFERRED)

- Sidebar uses shadow DOM — pierce or text-based click like Cursor CDP
- Primary CTA for Mahika: **File a new SAFE-T Claim** link

## Next (Sir teaches)

Click **File a new SAFE-T Claim** → wizard steps 1–6
