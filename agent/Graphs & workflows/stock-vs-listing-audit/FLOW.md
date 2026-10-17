# Stock vs Live Listing Audit + Restock — Flow

**Goal of this doc:** when this file is referenced, execute the full audit-and-restock pipeline fast and error-free — no rediscovering the gotchas below.

**Matcher script:** `catalog-builder/amazon-reports/stock_vs_all_listings_YYYY-MM-DD.py` (copy the newest dated one — see [[Known-good scripts]])
**Master stock file:** `catalog-builder/amazon-reports/_master_inventory_YYYY-MM-DD_reconciled.txt` (use the newest dated one)
**Tags:** `stock-audit`, `inventory-report`, `restock`, `bulk-upload`, `seller-central`, `mahika`

---

## When to use

Sir asks "stock vs listing status dikhao", "kya OOS hai", "fresh report nikaalo aur check karo", or wants Inactive/OOS listings reactivated with a qty.

---

## Step 1 — Pull a fresh All Listings Report (JS-fetch method — fast, no download-button flakiness)

The UI "Download" button on Inventory Reports is a shadow-DOM `kat-button`; clicking it (real click or synthetic) is unreliable and often produces zero visible result. **Skip the button. Use the API directly:**

1. Login via `seller-central-login` skill (Browser pane, Sir watches — never headless).
2. Navigate: hamburger menu → **Reports → Inventory Reports** (confirmed URL: `https://sellercentral.amazon.in/listing/reports/ref=xx_invreport_dnav_xx`).
3. Select **"All Listings Report"** from the dropdown → click **Request Report**. Wait ~30–60s.
4. Get the batch's download link via `javascript_tool`:
   ```js
   fetch('https://sellercentral.amazon.in/listing/api/status/inventory-reports', {credentials:'include'})
     .then(r=>r.text()).then(t=>t.slice(0,900))
   ```
   Find the newest batch (top of `statuses[]`), grab its `actions[0].link` (a `/listing/downloadfile?documentId=...` URL).
5. Fetch the report content directly and stash it on `window`:
   ```js
   fetch('https://sellercentral.amazon.in' + LINK, {credentials:'include'})
     .then(r=>r.text()).then(t => { window.__reportText = t; return {length:t.length}; })
   ```
6. Return `window.__reportText` — it will exceed the tool's inline limit and get saved to a `tool-results/*.txt` file automatically. Extract with Python:
   ```python
   import json
   data = json.load(open(TOOL_RESULT_PATH, encoding='utf-8'))
   json_str = data[0]['text'].split('\n\n(captured')[0]
   actual = json.loads(json_str)   # the real TSV text
   open(f'all_listings_{DATE}.tsv', 'w', encoding='utf-8', newline='').write(actual)
   ```

This whole step takes ~1–2 min and needs zero UI-download troubleshooting.

---

## Step 2 — Run the matcher

```bash
python3 stock_vs_all_listings_YYYY-MM-DD.py
```
(Copy the script, point `STOCK_FILE`/`LISTINGS_FILE`/`OUT_CSV` at today's files. **Never copy a pre-2026-08-03 version** — see [[Known-good scripts]] below, older ones have the false-positive matching bug.)

Prints OK / OUT_OF_STOCK / QUALITY_GAP / MISSING counts + writes `stock_vs_all_listings_report_YYYY-MM-DD.csv`.

**Before trusting the output**, run the two cheap verification passes (catches real bugs — has twice already):
```python
# invariant: every OK/QUALITY_GAP/OUT_OF_STOCK row's picked listing must satisfy is_clean_match
for item in stock:
    status, best, hits = m.classify_stock_item(item, listings)
    if best:
        tokens = m.search_tokens(item['name'], m.actual_brand(item['brand'], item['name']))
        assert m.is_clean_match(tokens, best['title_raw']), item['name']
```
Plus the qualifier-word re-scan (pro/pro+/max/plus/note/lite/etc. in title but not model — see script history / `project_matcher_false_positive_fix` memory).

---

## Step 3 — Build the status Excel

`python3 build_status_excel.py` (in scratchpad, or recreate from `catalog-builder/amazon-reports/STOCK_VS_LISTINGS_STATUS_*.xlsx` history) — reads the CSV from Step 2, writes a colour-coded workbook (Brand / SKU / ASIN / Actual Stock Availability / Classification / Available Stock Model / Listed Model / Physical Qty / Amazon Qty / Notes) + a Summary tab. Send to Sir via `SendUserFile`.

**If Sir has the file open in Excel, the save will `PermissionError` — ask him to close it first, don't force.**

---

## Step 4 — Restock the OUT_OF_STOCK SKUs

Dedupe by SKU (one SKU can satisfy two stock lines, e.g. `MI125G` covers both "Redmi 12" and "Redmi 12 5G"). **All mechanics (inline edit, bulk flat-file, upload/validate/submit, verify) live in `../listing-manager/LISTING_MANAGER.md` — follow that doc, don't duplicate steps here.**

---

## Known gotchas (audit/matcher-specific — do not re-discover)

| Symptom | Cause | Fix |
|---|---|---|
| "Total SKUs 47" on a 5-row upload | Blank template ships with 47 stale rows | see LISTING_MANAGER.md |
| A stock model wrongly shows "OK" against a Pro/Pro Max/Note-prefixed sibling listing | Old matcher used loose substring containment | Only use scripts ≥ `stock_vs_all_listings_2026-08-03.py` (`is_clean_match` fix) — `project_matcher_false_positive_fix` memory |
| Active Listings Report shows a long-OOS SKU as "active" | That report type is unreliable | Always pull **All Listings Report**, not Active — `feedback_active_listings_report_unreliable` memory |
| PermissionError saving the status Excel | Sir has it open in Excel | Ask him to close it, don't force |
| Browser pane screenshot fails "not displayed" | Pane lost focus/visibility | Ask Sir to bring it into view, don't spin-wait indefinitely |

Upload/bulk-file gotchas (Error 99022, Error 90041, Product Type column, native dialog steps) → **`listing-manager/LISTING_MANAGER.md`**.

---

## Known-good scripts (copy from these, not older ones)

- `stock_vs_all_listings_2026-08-07.py` — has the clean-match fix, TFT≈Incell≈LCD equivalence, "+"/"plus" canonicalization, and the "mi" sub-brand carry-forward fix (all four bugs found via Sir's spot-checks, 2026-08-03 → 2026-08-07).
- `_master_inventory_2026-08-07_reconciled.txt` — reconciled GPT-vs-Gemini master list with Sir's soldout/quality corrections applied.

---

## Sir checklist

- [ ] Fresh All Listings Report pulled today (not reusing a stale one for a restock decision)
- [ ] Matcher run against the newest reconciled master + newest report
- [ ] Invariant check + qualifier re-scan both clean before trusting "OK" rows
- [ ] Restock done per `listing-manager/LISTING_MANAGER.md`, result verified there
