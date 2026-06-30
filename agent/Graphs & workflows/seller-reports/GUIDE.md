# Seller reports — manual download + analyze

**Goal:** Download reports from Seller Central, drop in inbox, run `mahika.cli reports analyze`.  
**Login:** [../seller-central-login/FLOW.md](../seller-central-login/FLOW.md)  
**SP-API:** deferred — browser lane first.

---

## Folders

```
data/mahika/reports/
├── inbox/      ← fresh downloads
├── archive/    ← after analyze
└── analysis/   ← summary-{date}.txt
```

Historical (May 2026): `catalog-builder/amazon-reports/`

---

## Report types

| P | Report | Path in SC | Pattern |
|---|--------|------------|---------|
| P0 | All orders | Reports → Order → All orders | `*Order*` TSV |
| P0 | Business report | Reports → Business Reports | `BusinessReport*.csv` |
| P0 | Payments unified | Reports → Payments → Transaction view | `*CustomUnifiedTransaction*.csv` |
| P1 | All listings | Inventory → All listings | `All+Listings+Report*.txt` |
| P1 | Sales dashboard | Home → Sales dashboard | `SalesDashboard*.csv` |
| P2 | Returns | Reports → Fulfillment → Returns | `*Returns*` |
| P2 | Settlement | Reports → Payments → Settlement | `*Settlement*` |

---

## Commands

```powershell
cd agent
.\.venv\Scripts\python.exe -m mahika.cli reports init
.\.venv\Scripts\python.exe -m mahika.cli reports scan
.\.venv\Scripts\python.exe -m mahika.cli reports analyze
```

---

## Download steps (India, Badeja)

Base: https://sellercentral.amazon.in

### 1. Business report
Reports → Business Reports → Detail Page Sales and Traffic → date range → Download CSV → `BusinessReport-YYYY-MM-DD.csv`

### 2. Payment / unified transaction
Reports → Payments → Transaction View → Custom Unified Transaction CSV

### 3. All orders
Reports → Order → All orders → Request CSV → wait for link (1–15 min)

### 4. All listings
Inventory → Manage All Inventory → All listings report → `.txt`

### 5. Sales dashboard
Home → Sales dashboard → Download CSV

### 6. Returns
Reports → Fulfillment → Returns → date range → Download

### 7. Settlement
Reports → Payments → Settlement → pick period → Download

---

## Weekly bundle (Monday)

| # | Report | Range |
|---|--------|-------|
| 1 | Business (by date) | Last 7 days |
| 2 | Custom unified transaction | Last 7 days |
| 3 | All orders | Last 7 days |
| 4 | All listings | Today snapshot |

Then: `mahika.cli reports analyze` → archive to `reports/archive/YYYY-MM-DD/`

---

## Roadmap

1. Playwright auto-download to `inbox/`
2. SP-API Reports API
3. Cockpit `/reports` + Telegram weekly digest
