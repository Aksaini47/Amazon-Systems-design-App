# Seller Reports — Mahika Track (no SP-API)

**Goal:** Download Amazon Seller Central reports manually (filhal), drop in inbox, run analysis.

SP-API deferred — same data, browser download lane first; automation via Playwright later.

---

## Folder layout

```
data/mahika/reports/
├── inbox/      ← fresh downloads (Sir drops here)
├── archive/    ← dated copies after analyze
└── analysis/   ← summary JSON + text from `mahika.cli reports analyze`
```

Historical reports (May 2026): `catalog-builder/amazon-reports/` — catalog/stock scripts ke liye.

---

## Report types we care about

| Priority | Report | Seller Central path | File pattern |
|----------|--------|---------------------|--------------|
| P0 | **Orders — All orders** | Reports → Order → All orders | `*Order*`, flat file TSV |
| P0 | **Business report** | Reports → Business reports → Detail page sales/traffic | `BusinessReport*.csv` |
| P0 | **Payments — Custom unified** | Reports → Payments → Transaction view → Download | `*CustomUnifiedTransaction*.csv` |
| P1 | **All listings** | Inventory → Download → All listings | `All+Listings+Report*.txt` |
| P1 | **Sales dashboard** | Home → Sales dashboard → Download | `SalesDashboard*.csv` |
| P2 | **Returns** | Reports → Fulfillment → Returns | `*Returns*` |
| P2 | **Settlement** | Reports → Payments → Settlement | `*Settlement*` |
| P2 | **Inventory (FBA)** | Reports → Fulfillment → Inventory | FBA only |

Download steps: [DOWNLOAD_GUIDE.md](./DOWNLOAD_GUIDE.md)

---

## Commands

```powershell
cd agent

# Create report folders under MAHIKA_STORAGE_ROOT
.\.venv\Scripts\python.exe -m mahika.cli reports init

# Scan inbox (or any folder) — detect report types
.\.venv\Scripts\python.exe -m mahika.cli reports scan
.\.venv\Scripts\python.exe -m mahika.cli reports scan "C:\Projects\Amazon Systems Design\catalog-builder\amazon-reports"

# Analyze → prints summary + writes analysis/summary-{date}.txt
.\.venv\Scripts\python.exe -m mahika.cli reports analyze
.\.venv\Scripts\python.exe -m mahika.cli reports analyze "..\catalog-builder\amazon-reports"
```

---

## Analysis outputs

| Input | Metrics |
|-------|---------|
| Business report | Daily/monthly sales, units, sessions, conversion %, refund rate |
| Payment (unified) | Net credited, fees, ads spend, transfers, order-level totals |
| All listings | Active SKUs, total listed qty, zero-qty count, avg price |
| Sales dashboard | Today snapshot vs yesterday / last week |

Combined summary ties **orders + payments + inventory** for Sir's weekly review.

---

## Roadmap (after manual lane stable)

1. Playwright: Reports → Request report → poll → download to `inbox/` (reuse seller cookies)
2. SP-API Reports API (same report types, no browser)
3. Cockpit `/reports` page + Telegram weekly digest
