# PHONE_ACCESSORY Bulk Listing — Template & Column Flow

**Template file:** `PHONE_ACCESSORY (4).xlsm` (Amazon India, 237 cols)  
**Category donor:** `Category+Listings+Report_05-12-2026.xlsm` (591 cols — **different layout**)  
**Generator script:** `catalog-builder/amazon-reports/create_bulk_new_listings.py`  
**Sample row:** Template sheet **row 7** (rows 1–6 = headers / dropdown presets — **never edit**)

**Tags:** `bulk-upload`, `phone-accessory`, `listing-create`, `seller-central`, `mahika`

---

## Template layout (rows)

| Row | Purpose | Edit? |
|-----|---------|-------|
| 1–3 | Amazon feed settings | **No** |
| 4 | Column labels (SKU, Product Type, …) | **No** |
| 5 | API field names (`contribution_sku#1.value`, …) | **No** |
| 6 | Example defaults (`(Default) Create or Replace`, `Diet Bars`) | **No** |
| **7+** | **Your listing data** | **Yes** |

Frozen pane: row 7 = first data row.

---

## Listing Action — Column C (SIR RULES — bas yahi)

**Rows 1–6 = Amazon default — KABHI MAT BADLO.** Agent/script bhi mat chheden.

Row 7 col C — **sirf dropdown se select**, type mat karo:

| Dropdown | Kab |
|----------|-----|
| **Create or Replace (Full Update)** | Nayi listing |
| **Edit (Partial Update)** | Existing listing update (price, qty, bullets…) |
| **Delete** | Listing delete |

Row 6 `C6 = (Default) Create or Replace` — official hint, **rehne do**.

---

## Product Type — Column B (dropdown first)

**B7 = `PHONE_ACCESSORY`** pehle select karo — browse node (L) aur kaafi dropdowns is pe depend karte hain.

---

## Browse Node — Column L (dropdown)

**Named range:** `PHONE_ACCESSORY` + `recommended_browse_nodes…` (depends on B7)

| Product | Dropdown pick |
|---------|----------------|
| Mobile screen / display combo | `Electronics > … > Replacement Parts > Mobile Displays (11180541031)` |

**Wrong:** `Mobile Screen Guards (1389425031)` — old category-report short format; new template mein full path chahiye.

Cols M–P = extra browse slots — usually blank.

---

## Key columns (237-col template)

| Col | Letter | Field | CREATE |
|-----|--------|-------|--------|
| 1 | A | SKU | Required — unique |
| 2 | B | Product Type | `PHONE_ACCESSORY` |
| 3 | C | Listing Action | Dropdown (see above) |
| 7 | G | Item Name | Title ≤200 chars |
| 9 | I | Brand Name | `Generic` (create) |
| 10 | J | Product Id Type | `GTIN Exempt` if no barcode |
| 12 | L | Browse Nodes #1 | Dropdown — Mobile Displays |
| 17 | Q | Model Number | Often = SKU |
| 18 | R | Manufacturer | `Generic` |
| 21–30 | U–AD | Image URLs | **Blank OK** for test / donor clone later |
| 31 | AE | Product Description | Required (Data Definitions) |
| 32–36 | AF–AJ | Bullets 1–5 | ≤255 each |
| 37 | AK | Generic Keyword | ≤200 bytes |
| 57–58 | BE–BF | HSN Entity + Code | `HSN Code` + `851770` |
| 77 | BY | Item Condition | `New` |
| 79 | CA | Product Tax Code | `A_GEN_STANDARD` |
| 101 | CW | Fulfillment Channel | `AMAZON_IN` or `Fulfillment by Merchant (Default)` |
| 102 | CX | Quantity | Stock qty |
| 106 | DB | Your Price INR | Sell price |
| 107 | DC | MRP | Max retail price |
| 140–147 | — | Package dims/weight | From donor listing |
| 149 | DL | Country of Origin | `China` |
| 153 | DP | Batteries required? | `No` |
| 176 | EM | Dangerous Goods | `Not Applicable` |

---

## Old vs new column map

Category Listings Report (591 cols) has **Status + Title** in cols A–B — new template **does not**.

| Field | Category Report col | PHONE_ACCESSORY (4) col |
|-------|--------------------|-------------------------|
| SKU | 3 | 1 |
| Product Type | 4 | 2 |
| Listing Action | 5 | 3 |
| Item Name | 9 | 7 |
| Brand | 10 | 9 |
| Browse Node | 13 | 12 |
| Main Image | 29 | 21 |
| Description | 39 | 31 |
| Bullets | 40–44 | 32–36 |
| Fulfillment | 419 | 101 |
| Quantity | 420 | 102 |
| Price | 424 | 106 |
| MRP | 425 | 107 |

**Scripts must use new map** — `create_bulk_new_listings.py` still uses 591-col indices; update before bulk 25 re-run.

---

## Sheets reference

| Sheet | Role |
|-------|------|
| Template | Data entry |
| Valid Values | Dropdown option lists |
| Dropdown Lists | Named-range source (`record_action`, etc.) |
| Browse Data | Node ID ↔ path |
| Data Definitions | Required / optional per field |
| Instructions | Amazon how-to |

---

## File safety

| Do | Don't |
|----|-------|
| Excel COM save (pywin32) | `openpyxl.save()` on `.xlsm` — **corrupts** macros/validation |
| Edit row 7+ only | Edit rows 1–6 or Dropdown Lists |
| Backup before bulk fill | Overwrite without `_backup.xlsm` |

**Restore official template (no row 7 touch):**
```powershell
Copy-Item "$env:USERPROFILE\Downloads\PHONE_ACCESSORY (4)_backup.xlsm" `
  "$env:USERPROFILE\Downloads\PHONE_ACCESSORY (4).xlsm" -Force
```

---

## Upload path (Seller Central)

1. Login → Badeja India (`seller-central-login` flow)
2. **Catalog → Add Products via Upload** — `sellercentral.amazon.in/product-search/bulk`
3. Upload `.xlsm` → Submit
4. Status: `sellercentral.amazon.in/listing/status`

---

## Related files

| Path | Role |
|------|------|
| `catalog-builder/amazon-reports/bulk_create_25_quality.xlsm` | 25 SKU batch |
| `catalog-builder/amazon-reports/bulk_create_25_review.csv` | Price/SKU review |
| `catalog-builder/amazon-reports/PHONE_ACCESSORY_fill_analysis.txt` | Mandatory vs optional analysis |
| `catalog-builder/amazon-reports/fill_sample_template_row_excel.py` | Sample row via Excel COM |
| `catalog-builder/amazon-reports/restore_template_from_backup.py` | Revert to official dropdowns |

---

## Sir checklist (sample row)

- [ ] B7 dropdown → `PHONE_ACCESSORY`
- [ ] C7 dropdown → `Create or Replace (Full Update)` (not typed)
- [ ] L7 dropdown → Mobile Displays path
- [ ] Images 21–30 blank (if policy)
- [ ] Mandatory cols OK — see `PHONE_ACCESSORY_fill_analysis.txt`
