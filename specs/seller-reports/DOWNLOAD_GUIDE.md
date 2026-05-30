# Seller Central — Report download guide (India, Badeja Enterprises)

**Account:** Owner/admin for full Reports menu. Sub-user may lack some report types.

Login flow: [../seller-central-flow/FLOW.md](../seller-central-flow/FLOW.md)

Base URL: https://sellercentral.amazon.in

---

## 1. Business report (sales + traffic + refunds)

1. ☰ **Menu** → **Reports** → **Business Reports**
2. **Detail Page Sales and Traffic By Child Item** (or **By Date** for daily CSV)
3. Date range: last 30 days / custom (max ~2 years in UI)
4. **Download** → CSV
5. Save as: `BusinessReport-YYYY-MM-DD.csv` → `data/mahika/reports/inbox/`

**Use:** Conversion rate, sessions, units ordered, refund rate, A-to-z claims column.

---

## 2. Payment / transaction report (unified)

1. ☰ **Menu** → **Reports** → **Payments** → **Transaction View**
2. Date range: e.g. last month or custom (Sep 2025 – today for full recon)
3. **Download** → **Custom Unified Transaction** CSV
4. Save as: `YYYYMonDD-YYYYMonDDCustomUnifiedTransaction.csv`

**Use:** Net settlement, referral fees, Easy Ship charges, ad spend (`Cost of Advertising`), transfers to bank.

**Note:** Header has 13 metadata lines — Mahika parser skips them automatically.

---

## 3. All orders report

1. ☰ **Menu** → **Reports** → **Order** → **All orders**
2. Date range + **Request CSV download**
3. Wait for **Download** link (can take 1–15 min)
4. Save TSV/CSV to inbox

**Use:** Order IDs for SAFE-T cross-check, ship dates, statuses.

---

## 4. All listings (inventory on Amazon)

1. ☰ **Menu** → **Inventory** → **Manage All Inventory**
2. **Inventory Reports** or **Download** → **All listings report**
3. Tab-separated `.txt` file
4. Save as: `All+Listings+Report_DD-MM-YYYY.txt`

**Use:** SKU count, quantity, status (Active/Inactive), price vs MRP.

**Also used by:** `catalog-builder/amazon-reports/stock_*.py` for physical stock match.

---

## 5. Sales dashboard (intraday)

1. **Home** → **Sales dashboard** (or Reports → Sales dashboard)
2. Top-right **Download** icon
3. CSV with hourly + today/yesterday compare

**Use:** Intraday pulse; not a substitute for business report.

---

## 6. Returns report

1. ☰ **Menu** → **Reports** → **Fulfillment** → **Returns**
2. Date range → Download

**Use:** Return reasons, SAFE-T evidence timing, refund watcher validation (later).

---

## 7. Settlement reports

1. ☰ **Menu** → **Reports** → **Payments** → **Settlement**
2. Pick settlement period → Download

**Use:** Reconcile bank transfer vs transaction report totals.

---

## Recommended weekly bundle (Sir)

Every **Monday**, download and drop in `inbox/`:

| # | Report | Range |
|---|--------|-------|
| 1 | Business report (by date) | Last 7 days |
| 2 | Custom unified transaction | Last 7 days |
| 3 | All orders | Last 7 days |
| 4 | All listings | Snapshot (today) |

Then:

```powershell
cd agent
.\.venv\Scripts\python.exe -m mahika.cli reports analyze
```

Archive processed files to `reports/archive/YYYY-MM-DD/` manually or via future automation.

---

## Filename tips

Mahika auto-detects by **content**, not only filename. Good names help humans:

```
BusinessReport-2026-05-20.csv
2026May13-2026May20CustomUnifiedTransaction.csv
All+Listings+Report_20-05-2026.txt
SalesDashboard-20-05-26.csv
```
