# Listing Manager — Price, Inventory/Stock, Bulk Upload — Scripted Flow

**Goal of this doc:** standalone, copy-paste-ready reference for updating live Seller Central listings — price, quantity/stock, and full bulk uploads. When referenced, execute fast and error-free — every gotcha below already cost a failed batch once.

**Tags:** `listing-update`, `price`, `inventory`, `stock`, `bulk-upload`, `seller-central`, `mahika`

**Account:** Badeja Enterprises → India (see `seller-central-login` skill for the login flow — Browser pane only, Sir watches, never headless).

---

## Decision: which method?

| Situation | Method |
|---|---|
| ≤2 SKUs, quantity or price only | **A. Inline edit** (Manage All Inventory) |
| >2 SKUs, or any field beyond price/qty (title, quality, images, etc.) | **B. Bulk upload flat-file** |
| Brand-new SKU, full listing creation | **C. New Listing Creation** (below) — see also `bulk-listing-create/FLOW.md` for the 237-col template map |

---

## A. Inline edit — Manage All Inventory (≤2 SKUs)

Fast path for a couple of qty/price tweaks. Steps, in exact order — skipping the "click outside" step is the #1 way this silently fails:

1. Navigate: `https://sellercentral.amazon.in/myinventory/inventory`
2. Search box → type SKU/ASIN/title → **click the magnifying-glass icon** (pressing Enter alone does not search).
3. Scroll the results table **right** until you see:
   - **"Available (FBM)"** — quantity field
   - **"Price"** — price field (INR)
4. Triple-click the field to select existing value, type the new value.
5. **Click somewhere clearly outside the table** (e.g. the page `<h1>` heading area). A **"N SKU(s) edited · Cancel · Save all"** bar appears fixed at the bottom.
   - Tab / Enter from inside the field does **not** reliably surface this bar — must be an outside click.
6. Click **Save all**.
7. Verify: the new value persists after `F5` refresh. **The status label ("Out of stock" ↔ "Active") can lag behind the actual qty change** — treat the field value as ground truth, not the label, when deciding if the save worked.

Can edit multiple fields (qty + price) on multiple visible rows before the single "Save all" — the edited-count bar accumulates.

---

## B. Bulk upload flat-file (>2 SKUs, or Edit/Partial-Update in general)

### B1 — Build the file

Base template: newest blank `PHONE_ACCESSORY (N).xlsm` in `C:\Users\DELL\Downloads\`. **It is not actually blank** — ships with ~47 stale leftover data rows from old batches. Always delete rows 7+ first.

```python
import shutil, zipfile
import openpyxl

SRC = r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (6).xlsm"   # newest blank template
OUT = r"C:\Projects\Amazon Systems Design\catalog-builder\amazon-reports\PHONE_ACCESSORY_<label>_<date>.xlsm"

shutil.copyfile(SRC, OUT)
wb = openpyxl.load_workbook(OUT, keep_vba=False)
ws = wb["Template"]
ws.delete_rows(7, ws.max_row - 6)          # ALWAYS — kills the 47 stale rows

# Confirmed column map (verify against row 4 before trusting — Amazon reorders on template updates):
COL_SKU              = 1    # SKU
COL_PRODUCT_TYPE      = 2    # Product Type  — NOT column 4! (col 4 is "Parentage Level")
COL_LISTING_ACTION    = 3    # Listing Action: "Edit (Partial Update)" or "Create or Replace (Full Update)"
COL_FULFILLMENT       = 102  # Fulfillment Channel Code (IN) — must be literal "DEFAULT"
COL_QTY               = 103  # Quantity (IN)
COL_PRICE             = 107  # Your Price INR
COL_MRP               = 108  # Maximum Retail Price

for i, row in enumerate(ROWS):            # ROWS = [{"sku":..., "qty":..., "price":...}, ...]
    r = 7 + i
    ws.cell(row=r, column=COL_SKU, value=row["sku"])
    ws.cell(row=r, column=COL_PRODUCT_TYPE, value="PHONE_ACCESSORY")
    ws.cell(row=r, column=COL_LISTING_ACTION, value="Edit (Partial Update)")
    ws.cell(row=r, column=COL_FULFILLMENT, value="DEFAULT")
    if "qty" in row:
        ws.cell(row=r, column=COL_QTY, value=row["qty"])
    if "price" in row:
        ws.cell(row=r, column=COL_PRICE, value=row["price"])
wb.save(OUT)
wb.close()

# openpyxl keep_vba=False resets the workbook content-type to plain xlsx — Excel then refuses
# to open a .xlsm with that content-type. Patch it back to macroEnabled after every save:
XLSX_WB = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
XLSM_WB = "application/vnd.ms-excel.sheet.macroEnabled.main+xml"
TMP = OUT + ".tmp"
src = zipfile.ZipFile(OUT, "r")
names = src.namelist()
new_ct = src.read("[Content_Types].xml").decode("utf-8").replace(XLSX_WB, XLSM_WB)
out = zipfile.ZipFile(TMP, "w", zipfile.ZIP_DEFLATED)
for n in names:
    out.writestr(n, new_ct.encode("utf-8") if n == "[Content_Types].xml" else src.read(n))
out.close(); src.close()
shutil.move(TMP, OUT)
```

**Verify the column map before every run** — don't trust the hardcoded numbers blind, Amazon has reordered this template before:
```python
for c in [1, 2, 3, 4]:
    print(c, ws.cell(row=4, column=c).value)
# expect: SKU, Product Type, Listing Action, Parentage Level
```

**Never use Excel COM / `win32com`** to touch this file — Office 2013 on this machine is unlicensed, a modal "Product Activation Failed" dialog blocks every OLE call. `openpyxl` (per above) is the only reliable path.

### B2 — Which Listing Action?

| SKU state | Listing Action |
|---|---|
| Already has an ASIN (exists in catalogue) | `Edit (Partial Update)` |
| Never created before | `Create or Replace (Full Update)` — needs the full 237-col fill, see `bulk-listing-create/FLOW.md` |

Mixing both in one file is fine — set the column per-row.

### B3 — Upload via native file dialog

1. Browser pane (visible, Sir watching) → hamburger menu → **Catalogue → Add Products via Upload** → **Spreadsheet** tab.
   (Direct URL not yet confirmed reliable for this specific page — go via menu.)
2. Click **"Upload file"**.
3. `mcp__Windows-MCP__Snapshot` → find the **"File name:"** native dialog Edit field (its `id` in the snapshot).
4. `mcp__Windows-MCP__Type` with `label:"<id>", text:"<full path>", clear:true, press_enter:true`.
   - Do **not** pass `loc:[x,y]` as a coordinate array — it fails Pydantic validation as a string; always use `label`.
5. Confirm **"Try AI-generated content"** toggle is OFF (left position) — AI enhancement can inject hallucinated attributes.
6. Scroll down, click **"Validate your file"**.
7. Wait for **"Preview file and fix errors"**: confirm `Ready to submit == Total SKUs` and `Action required == 0` before proceeding. If errors, fix and re-upload — don't submit partial.
8. Click **Submit**.

**Note:** selecting the file sometimes auto-advances straight past Validate into "Check Upload Status" with the batch already `In Progress` — this is normal on this UI, not a bug. Just proceed to verify the result.

### B4 — Verify the result (JS-fetch — reliable; UI buttons are not)

The "Download Processing Summary" button and the report-page "Download" button are both shadow-DOM `kat-button` components; clicking them (real or synthetic) is unreliable and often produces zero visible result. **Use the API directly instead:**

```js
// Quick pass/fail:
fetch('https://sellercentral.amazon.in/listing/api/status/feeds/feed?merchantId=' + MERCHANT_ID + '&batchId=' + BATCH_ID + '&frpRegion=EU', {credentials:'include'})
  .then(r=>r.text()).then(t=>t.slice(0,3000))
```
Poll every ~30s until `processingState.name == "DONE"`. Read `processingStatistics.numRecordsSuccessful` vs `numRecordsSubmitted`.

If not 100% successful, pull the actual Processing Summary workbook as bytes (button download doesn't reliably land on disk either):
```js
fetch('https://sellercentral.amazon.in/listing/api/status/feeds/download?batchId=' + BATCH_ID + '&merchantId=' + MERCHANT_ID + '&frpRegion=EU', {credentials:'include'})
  .then(r => r.arrayBuffer())
  .then(buf => {
    const bytes = new Uint8Array(buf);
    let binary = '';
    for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode.apply(null, bytes.subarray(i, i+8192));
    window.__b64 = btoa(binary);
    return {b64len: window.__b64.length};
  })
```
Then return `window.__b64` — it will exceed the tool's inline limit and get saved to a `tool-results/*.txt` file. Extract and decode in Python:
```python
import json, base64
data = json.load(open(TOOL_RESULT_PATH, encoding='utf-8'))
b64 = json.loads(data[0]['text'].split('\n\n(captured')[0])
open('processing_summary.xlsx', 'wb').write(base64.b64decode(b64))
```
Open with `openpyxl`, read the **"Feed Processing Summary"** sheet — it has per-SKU error rows with exact codes/messages/affected columns.

### B5 — Getting a fresh All Listings Report (to verify live state after any change)

Same JS-fetch pattern, text not binary this time:
1. Navigate `https://sellercentral.amazon.in/listing/reports/ref=xx_invreport_dnav_xx` (confirmed working direct URL).
2. Dropdown → **"All Listings Report"** → **Request Report**. Wait ~30–60s.
3. ```js
   fetch('https://sellercentral.amazon.in/listing/api/status/inventory-reports', {credentials:'include'})
     .then(r=>r.text()).then(t=>t.slice(0,900))
   ```
   grab the newest batch's `actions[0].link`.
4. ```js
   fetch('https://sellercentral.amazon.in' + LINK, {credentials:'include'})
     .then(r=>r.text()).then(t => { window.__reportText = t; return {length:t.length}; })
   ```
5. Return `window.__reportText`, extract from the overflow tool-result file the same way as B4's base64 (it's plain JSON-string text here, not base64):
   ```python
   import json
   data = json.load(open(TOOL_RESULT_PATH, encoding='utf-8'))
   actual = json.loads(data[0]['text'].split('\n\n(captured')[0])
   open(f'all_listings_{DATE}.tsv', 'w', encoding='utf-8', newline='').write(actual)
   ```
Prefer **All Listings Report** over Active Listings Report for verification — the Active report type can wrongly mark long-OOS SKUs as active.

---

## C. New Listing Creation — mandatory fields & gotchas

Creating a genuinely new PHONE_ACCESSORY SKU (`Listing Action = Create or Replace (Full Update)`) fails the "N Attributes" preview check far more often than a qty/price Edit — real required fields and AI-hallucinated suggestions look identical in the preview screen unless you know which is which. Learned the hard way over a 5-SKU creation batch — every field below was a genuine blocker at least once.

### C1 — The full mandatory-field checklist (PHONE_ACCESSORY, no barcode)

This is the **complete, verified column map** — pulled directly from a batch that actually went 100% successful (`numRecordsSuccessful == numRecordsSubmitted`, not just "looked right in preview"). Fill every one of these before validating; the four marked **⚠️ easy to miss** were found only via the live "Preview file and fix errors" grid (column-group codes EC/ES/ET/FT), not via the print/console field lists — a batch of 10 new listings hit exactly these 4 gaps in one go (2026-08-07), so check them first.

| Field | Column | Value | Why it bites |
|---|---|---|---|
| SKU | 1 | unique | — |
| Product Type | 2 | `PHONE_ACCESSORY` | Wrong column here = error 90041, 0 successful |
| Listing Action | 3 | `Create or Replace (Full Update)` for genuinely new SKUs; `Edit (Partial Update)` if the SKU already got an ASIN from an earlier partial-success batch | Using Create on an already-created SKU, or Edit on a truly new one, both fail |
| Item Name (title) | 7 | `Compatible for {Model} {Quality} Display+Touch Screen Combo Folder`, ≤200 chars | No unverified "(Fingerprint Support)" claims — see C3 |
| Brand Name | 9 | `Generic` | — |
| Product Id Type | 10 | `GTIN Exempt` | Leaving this **and** Product Id both blank is a hard blocker — no barcode exists for these generic replacement parts |
| Product Id | 11 | leave blank | GTIN Exempt makes this optional |
| Recommended Browse Nodes #1 | 12 | `11180541031` (Mobile Displays path) — **not** the old "Mobile Screen Guards" short code | Wrong/stale browse node silently breaks category-dependent dropdowns downstream |
| Model Number | 17 | same as SKU | — |
| Manufacturer | 18 | `Generic` | — |
| Main Image URL | 21 | leave blank if images pending | Sir uploads separately later — fine to skip, not a blocker |
| Product Description | 31 | see boilerplate below | — |
| Bullet Point 1–5 | 32–36 | see quality-specific templates below | — |
| Generic Keyword | 37 | `{Compatible Model} {Quality} Display` | — |
| Style | 38 | `Replacement Part` | — |
| Number of Items | 39 | `1` | — |
| Item Type Name | 40 | `Mobile Screen Replacement Part` | — |
| Color | 41 | `Black` (or actual stock color) | — |
| Size | 42 | `Standard` | — |
| Part Number | 43 | same as SKU | — |
| Manufacturer Contact Information | 44 | `RepairFully.com, Import Hub E-Commerce 122503, Pataudi, Haryana` | — |
| Compatible Phone Models | 45 | bare model name, e.g. `OnePlus Nord` | — |
| Product Grade | 48 | `Replacement Parts` | — |
| Unit Count | 49 | `1` | Required for PHONE_ACCESSORY — see C2 for the reclassification trap |
| Unit Count Type | 50 | `Count` | Same |
| Included Components #1 / #2 | 52 / 53 | `Display` / `Touch Screen` | — |
| External Product Information Entity | 57 | `HSN Code` | — |
| External Product Information | 58 | `851770` | — |
| Importer Contact Information | 63 | same as Manufacturer Contact | — |
| Packer Contact Information | 68 | same as Manufacturer Contact | — |
| Item Weight | 74 | `100` | Must be **less than** package weight — equal values imply zero packaging and can itself flag as an error |
| Item Weight Unit | 75 | `Grams` | — |
| Item Condition | 77 | `New` | — |
| Product Tax Code | 79 | `A_GEN_STANDARD` | Valid values are all `A_GEN_*` — **`A_ELECTRONICS_GEN` does not exist**, using it silently blocks the row |
| Maximum Order Quantity | 81 | `1` | — |
| **Shipping Template (IN)** ⚠️ | **134** | **`Migrated Template`** — confirmed the *only* value in the Valid Values sheet, don't invent alternatives | **Missing = one of the 4 silent blockers found 2026-08-07** |
| Item Length / Width / Height | 135 / 137 / 139 | `15` / `7` / `0.5` | Units in 136/138/140 = `Centimetres` |
| Item Package Length / Width / Height | 141 / 143 / 145 | `26` / `13` / `3` | Units in 142/144/146 = `Centimetres` |
| Package Weight | 147 | `220` | Unit in 148 = `Grams` |
| **Country of Origin** ⚠️ | **150** | **`China`** (or actual sourcing country — full country-name list in Valid Values sheet row "Country of Origin - [ PHONE_ACCESSORY ]") | **Missing = one of the 4 silent blockers found 2026-08-07** |
| **Warranty Description** ⚠️ | **151** | **`7 Day Replacement Warranty - Manufacturing Defects Only`** (free text; 152/153 are extra optional slots, leave blank) | **Missing = one of the 4 silent blockers found 2026-08-07** |
| **Dangerous Goods Regulations** ⚠️ | **177** | **`Not Applicable`** — valid set is `GHS / Storage / Transportation / Waste / Other / Not Applicable / Unknown` | **Missing = one of the 4 silent blockers found 2026-08-07** |
| Fulfillment Channel Code (IN) | 102 | literal `DEFAULT` (not the display string `AMAZON_IN` or `Fulfillment by Merchant (Default)` shown in the Valid Values sheet) | Using the display string instead of the raw value causes silent rejection |
| Quantity (IN) | 103 | stock qty | — |
| Handling Time (IN) | 104 | `2` | — |
| Your Price INR | 107 | sell price — derive from a same-brand/similar-quality sibling SKU's live price if Sir hasn't given one, and flag the guess for correction | — |
| Maximum Retail Price | 108 | MRP — sibling ratio is usually ~1.7–2× sell price | — |

**Description boilerplate** (identical for every SKU except the bracketed part — insert `+ Frame` only for With-Frame items):
> NOTICE: If Any Customer Will Try To Do Any Type Of Fraud/cheating In Terms Of Refund Or Replacement Under The Amazon Guarantee Program Then On Prima Facia Evidence Our Company Will Take Legal Action Against Such Customers And Report Them Under The Indian Penal Code Section 415/420. Violation Of Indian Penal Code Section 415/420 Is Punishable By Imprisonment And A Monetary Fine Decided By The Court Of Law. Package Contents: 1. Replacement Screen [+ Frame] + Touchpad Digitizer Assembly. 2. Replace The Old, Broken, Cracked, Damaged One. We Strongly Recommend Servicing Under Expert Technical Supervision. Self-installation Without The Required Skills Can Be Dangerous To The Screen/device. Do Not Remove The Sticker Till The Complete Satisfaction, Sticker Removal Means Acceptance Of The Product. When You Are Certain That Everything Is Working Fine Then Your Technician Can Install It Permanently. It's Important To Keep The Item In Its Original Condition And Don't Remove The Sticker. We Do Offer Replacement For Manufacturing Defects But Not For Any Physical Damage Done By You Or Your Technician During Installation. Got A Broken Display In Your Phone? Buy The Complete Display With Touch Screen For Your Phone And Replace The Broken, Cracked, Or Scratched Screen In Your Handset. Fit With High Manufacturing Quality. With The Least Technical Know-how Required, It Is Easiest To Replace The Display For Your Handset. The Replacement Combo Display With Touch For Your Phone Comes With A Manufacturing Quality And The Shipping Is Done In Secure Packing To Make Sure You Get The Product In Shape.

**Bullet 1 (quality-specific — pick one):**
- LCD/Incell/TFT: *"📱 Premium Display Technology 🔹 Grade A LCD/TFT Display – A bright, energy-efficient, and cost-effective alternative with sharp clarity for everyday use."*
- CareOG/Original: *"📱 Premium Display Technology 🔹 100% Original Grade (OG) Quality – Factory-calibrated to match OEM standards, ensuring perfect color accuracy & touch response like your original screen!"*
- OLED/AMOLED: *"📱 Premium Display Technology 🔹 Grade A AMOLED Display – Experience vivid colors, true blacks, and ultra-high contrast for immersive viewing. Perfect for streaming, gaming, and vibrant visuals!"*

**Bullet 2 (always):** *"📲 Perfect Compatibility ✅ Designed for {Compatible Model} – Precise fit"*

**Bullet 3 (pick by priority — Frame beats OLED-fingerprint beats generic; never claim fingerprint support without verification, hence the hedged "(Where Applicable)" wording):**
- Has a physical frame: *"🖼️ Comes With Frame (Pre-Assembled or Separate) – Frame color varies (black, silver, etc.) depending on stock availability."*
- OLED/AMOLED, no frame: *"🔓 Under-Display Fingerprint Support (Where Applicable) – Fast, secure unlock with seamless integration (only on select models)."*
- Otherwise: *"🔬 Rigorously Tested for Performance – Each display undergoes strict quality checks for touch sensitivity, color uniformity, and brightness levels to ensure flawless performance right out of the box!"*

**Bullet 4 (always):** *"🔧 Professional Installation STRONGLY Recommended – Improper installation can cause touch issues, dead pixels, or adhesive failure. We are not liable for post-installation problems."*

**Bullet 5 (always):** *"⚠️ Important Warranty & Installation Info 🛡️ 7-Day Replacement Warranty – Covers manufacturing defects only (see full terms in description). No refunds – replacement only!"*

### C2 — Amazon can silently reclassify Product Type mid-processing

Error **90244** *"We can't accept the Count that you entered for Unit Count"* paired with warning **18367** means Amazon's backend auto-reclassified the SKU from `PHONE_ACCESSORY` to `CELLULAR_PHONE_CASE` based on title/keyword heuristics (e.g. the word "case" or "cover" appearing anywhere in title/bullets) — and `CELLULAR_PHONE_CASE` has **different valid Unit Count Type values** than `PHONE_ACCESSORY`. Fix: scrub the title/bullets for any case/cover-sounding words for a screen-replacement listing, don't just retry with a different Unit Count value.

### C3 — Turn "Try AI-generated content" OFF, always, before validating

With it ON, Amazon's AI suggests attribute values that show as filled-in but are **not actually accepted values** — they read as plausible in the preview but are wrong for a screen/display replacement part: seen `form_factor = "Basic Case"`, `special_feature = "360 Degree Protection"` / `"Built-in Screen Protector"` / `"Anti-Fingerprint"` — all attributes that describe a phone **case or screen protector**, not a display+touch combo. These are suggestions, not committed values, but they inflate the apparent "N Attributes" gap count and can get accidentally committed if you don't check the toggle first. Confirm the toggle is in the left/off position on every upload, not just the first one in a session.

To diagnose which attributes are genuinely required vs AI-suggested for SKUs already in a DRAFT state, query:
```
GET /spsx/ajax/v1/contributions/{merchantId}?contributionType=DRAFT&encodeSelectorsInAttributeName=true&sku=X&sku=Y...
```
— returns per-attribute `value` (committed) vs `suggestion` (AI-proposed, not committed) so you can tell a real gap from an AI hallucination before treating it as a required-field blocker.

### C4 — Error 13013 after submitting a batch that both creates a SKU and adds its offer

*"Your offer to the SKU cannot be added because the product is not in the catalogue"* on a **brand-new** SKU is a race condition, not a real data error — the SKU-creation half of the feed and the offer/price/qty half can process out of order within the same batch. **Resolves itself on resubmission** once the SKU genuinely exists in the catalogue (usually within minutes) — don't waste time re-diagnosing the data, just wait and resubmit the same rows with `Listing Action = Edit (Partial Update)` (they now have an ASIN, see C1's Listing Action row).

---

## Known gotchas (do not re-discover)

| Symptom | Cause | Fix |
|---|---|---|
| Excel COM `com_error(-2147418111)` / corrupts `.xlsm` | Office 2013 unlicensed, modal dialog blocks OLE | Use `openpyxl` only — never `win32com` on this machine |
| "unable to open file" after saving with openpyxl | `keep_vba=False` leaves xlsx content-type on a `.xlsm` filename | Patch `[Content_Types].xml` → macroEnabled, every save |
| "Total SKUs 47" on a 5-row upload | Blank template ships with 47 stale rows | `ws.delete_rows(7, ws.max_row-6)` before filling, always |
| Error 99022, whole batch rejected | Qty-only Edit rows missing Fulfillment Channel Code | Always set col 102 = literal `DEFAULT` |
| Error 90041, 0/N successful, "product_type#1.value is always required" | Product Type written to wrong column (4 instead of 2) | Product Type = **col 2** — verify against row 4 headers before every run |
| Inline-edit qty change looks lost after clicking away | Save bar needs an explicit outside-table click, not Tab/Enter | Click outside table → "N SKU(s) edited" bar appears → click Save all |
| Inline-edit status label still says "Out of stock" after a successful save | Status label lags the actual qty value | Trust the qty field (refresh-verified), not the label, for a few minutes |
| PermissionError saving any `.xlsx`/`.xlsm` | Sir has the file open in Excel | Ask him to close it, don't force |
| Browser pane screenshot fails "not displayed" | Pane lost focus/visibility on Sir's screen | Ask Sir to bring it into view; don't spin-wait indefinitely |
| Report/processing-summary "Download" button does nothing | Shadow-DOM `kat-button`, click doesn't reach the real handler | Use the JS-fetch API pattern (B4/B5), skip the button entirely |
| New-listing row blocked, blank Product Id Type/Product Id | No barcode for a generic replacement part | Set Product Id Type = `GTIN Exempt`, leave Product Id blank — see C1 |
| Product Tax Code rejected | Used `A_ELECTRONICS_GEN` — doesn't exist | Use `A_GEN_STANDARD` — valid values are all `A_GEN_*` |
| Error 90244 "can't accept Count for Unit Count" + warning 18367 | Amazon silently reclassified Product Type away from PHONE_ACCESSORY (title/bullets read like a case/cover) | Scrub case/cover-sounding words from title+bullets — see C2 |
| Preview shows more attribute gaps than expected on a new listing | "Try AI-generated content" toggle was ON, suggesting wrong attributes (form_factor, special_feature) | Toggle OFF before every validate, not just the first upload — see C3 |
| Error 13013 "product not in the catalogue" right after creating a new SKU | Race condition: SKU-creation and offer-attach processed out of order in the same feed | Resolves on resubmit once the SKU has an ASIN — resubmit as Edit (Partial Update), not a new data problem — see C4 |
| New listing: "4 Attributes" error on every row, not obvious which 4 | Shipping Template (IN, col 134), Country of Origin (150), Warranty Description (151), Dangerous Goods Regulations (177) left blank | Fill all 4 — see C1 for exact required values. Found via the preview grid's "Focus on errors" toggle + column-group codes (EC/ES/ET/FT), not visible in a plain column dump |

---

## Related docs

| Doc | Role |
|---|---|
| `bulk-listing-create/FLOW.md` | Full 237-column map for brand-new listing creation (Create or Replace) |
| `stock-vs-listing-audit/FLOW.md` | Physical-stock vs live-listing audit pipeline — calls into this doc for the actual restock mechanics |
| `seller-central-login/` | Login flow, OTP, account switcher |
