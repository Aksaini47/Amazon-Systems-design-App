# Explore PDF filename patterns

- **Subtitle:** Invoice PDF filename analysis
- **Project:** `c:\Projects\Amazon Systems Design`
- **Created:** 2026-07-09 17:42
- **Updated:** 
- **Status:** completed
- **Model:** default
- **Messages:** 4
- **Composer ID:** `f9b34cf5-1105-4b2e-acab-7e91d5143a96`

---
### User — 2026-07-09 17:42

Read-only exploration. In c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices\, analyze PDF filenames only (not temp _* files). Return: (1) filename pattern with examples, (2) unique invoice types from filenames, (3) year-month distribution counts if parseable from YYYY-MM-DD prefix, (4) any duplicate invoice IDs, (5) sample of 5 filenames. Use shell/python readonly only.

### Assistant — 2026-07-09 17:42

Analyzing PDF filenames in the seller-invoices directory — listing files and parsing patterns.

### Assistant — 2026-07-09 17:42

> **Tool:** `update_current_step` completed
```
{"currentStep":"Analyzing invoice PDF filenames"}
```

### Assistant — 2026-07-09 17:42

> **Tool:** `glob_file_search` completed
```
{"directories":[{"absPath":"c:\\Projects\\Amazon Systems Design\\data\\mahika\\amazon-seller-invoices"}]}
```

### Assistant — 2026-07-09 17:42

> **Tool:** `run_terminal_command_v2` completed
```
{"output":"TOTAL_PDFS 445\r\n---SAMPLE_FIRST_10---\r\n2020-01-31_Fulfillment_by_Amazon_Tax_Invoice_HR-1920-33307.pdf\r\n2020-01-31_Merchant_VAT_Invoice_KA-1920-909720.pdf\r\n2020-01-31_Product_Ads_VAT_Invoice_ADS-1920-326986.pdf\r\n2020-02-29_Fulfillment_by_Amazon_Tax_Invoice_HR-1920-38011.pdf\r\n2020-02-29_Merchant_VAT_Invoice_KA-1920-1025884.pdf\r\n2020-02-29_Product_Ads_VAT_Invoice_ADS-1920-372186.pdf\r\n2020-03-31_Fulfillment_by_Amazon_Tax_Invoice_HR-1920-43243.pdf\r\n2020-03-31_Merchant_VAT_Invoice_KA-1920-1184835.pdf\r\n2020-03-31_Product_Ads_VAT_Invoice_ADS-1920-412695.pdf\r\n2020-04-30_Fulfillment_by_Amazon_Tax_Invoice_HR-2021-511.pdf\r\n---SAMPLE_LAST_5---\r\n2025-11-30_Merchant_VAT_Invoice_KA-2526-2529169.pdf\r\n2025-12-31_Merchant_VAT_Credit_Note_KA-C-26-1422864.pdf\r\n2025-12-31_Merchant_VAT_Invoice_KA-2526-2813358.pdf\r\n2026-01-31_Merchant_VAT_Credit_Note_KA-C-26-1700981.pdf\r\n2026-01-31_Merchant_VAT_Invoice_KA-2526-3284310.pdf\r\n---UNIQUE_TYPES---\r\n268\tMerchant\r\n105\tFulfillment\r\n72\tProduct\r\n---YM_DISTRIBUTION---\r\n3\t2020-01\r\n3\t2020-02\r\n3\t2020-03\r\n3\t2020-04\r\n3\t2020-05\r\n3\t2020-06\r\n3\t2020-07\r\n3\t2020-08\r\n3\t2020-09\r\n8\t2020-10\r\n4\t2020-11\r\n5\t2020-12\r\n4\t2021-01\r\n5\t2021-02\r\n4\t2021-03\r\n4\t2021-04\r\n3\t2021-05\r\n3\t2021-06\r\n3\t2021-07\r\n3\t2021-08\r\n3\t2021-09\r\n3\t2021-10\r\n4\t2021-11\r\n4\t2021-12\r\n4\t2022-01\r\n4\t2022-02\r\n4\t2022-03\r\n5\t2022-04\r\n5\t2022-05\r\n8\t2022-06\r\n10\t2022-07\r\n8\t2022-08\r\n8\t2022-09\r\n8\t2022-10\r\n8\t2022-11\r\n8\t2022-12\r\n11\t2023-01\r\n9\t2023-02\r\n9\t2023-03\r\n9\t2023-04\r\n8\t2023-05\r\n8\t2023-06\r\n8\t2023-07\r\n8\t2023-08\r\n8\t2023-09\r\n8\t2023-10\r\n7\t2023-11\r\n8\t2023-12\r\n8\t2024-01\r\n8\t2024-02\r\n8\t2024-03\r\n8\t2024-04\r\n8\t2024-05\r\n8\t2024-06\r\n8\t2024-07\r\n8\t2024-08\r\n8\t2024-09\r\n8\t2024-10\r\n8\t2024-11\r\n8\t2024-12\r\n7\t2025-01\r\n6\t2025-02\r\n8\t2025-03\r\n8\t2025-04\r\n8\t2025-05\r\n8\t2025-06\r\n8\t2025-07\r\n8
… [truncated 684 chars]
```

### Assistant — 2026-07-09 17:42

Refining analysis to extract full invoice types and proper invoice ID formats.

### Assistant — 2026-07-09 17:42

> **Tool:** `run_terminal_command_v2` completed
```
{"output":"=== FULL INVOICE TYPES ===\r\n155\tMerchant_VAT_Invoice\r\n111\tMerchant_VAT_Credit_Note\r\n103\tFulfillment_by_Amazon_Tax_Invoice\r\n70\tProduct_Ads_VAT_Invoice\r\n1\tFulfillment_by_Amazon_Tax_Invoice_HR-2021-26028-1\r\n1\tFulfillment_by_Amazon_Tax_Invoice_HR-CN-E-1100\r\n1\tMerchant_VAT_Credit_Note_KA-CN-E-7485\r\n1\tMerchant_VAT_Invoice_KA-2021-628512-1\r\n1\tProduct_Ads_VAT_Credit_Note_ADS-CN-E-15913\r\n1\tProduct_Ads_VAT_Invoice_ADS-21-183359-1\r\n=== FILES WITHOUT DATE PREFIX === 0\r\n=== FILES WITHOUT PARSED ID === 6\r\n  2020-10-31_Fulfillment_by_Amazon_Tax_Invoice_HR-2021-26028-1.pdf\r\n  2020-10-31_Fulfillment_by_Amazon_Tax_Invoice_HR-CN-E-1100.pdf\r\n  2020-10-31_Merchant_VAT_Credit_Note_KA-CN-E-7485.pdf\r\n  2020-10-31_Merchant_VAT_Invoice_KA-2021-628512-1.pdf\r\n  2020-10-31_Product_Ads_VAT_Credit_Note_ADS-CN-E-15913.pdf\r\n=== DUPLICATE INVOICE IDs === 0\r\nNone\r\n=== ID SERIES PREFIXES (top 15) ===\r\n37\tKA-2223\r\n35\tKA-2324\r\n34\tKA-2425\r\n27\tKA-C-23\r\n25\tKA-C-24\r\n23\tKA-C-25\r\n22\tKA-2526\r\n18\tKA-C-26\r\n13\tKA-2122\r\n13\tADS-2223\r\n12\tKA-C-22\r\n12\tADS-2122\r\n12\tHR-2324\r\n12\tHR-C-24\r\n12\tADS-2324\r\n=== SAMPLE 5 ===\r\n2020-01-31_Fulfillment_by_Amazon_Tax_Invoice_HR-1920-33307.pdf\r\n2022-06-30_Merchant_VAT_Credit_Note_KA-C-23-278925.pdf\r\n2023-07-31_Fulfillment_by_Amazon_Tax_Invoice_HR-C-24-11907.pdf\r\n2024-09-30_Fulfillment_by_Amazon_Tax_Invoice_HR-C-25-25208.pdf\r\n2026-01-31_Merchant_VAT_Invoice_KA-2526-3284310.pdf\r\n","rejected":false,"notInterrupted":true}
```

### Assistant — 2026-07-09 17:42

> **Tool:** `run_terminal_command_v2` completed
```
{"output":"Credit_Note total: 113\r\nProduct_Ads_VAT_Credit_Note: 1\r\nMonths covered: 2020-01 to 2026-01\r\nTotal months: 73\r\nTotal files: 445\r\nAvg per month: 6.1\r\n=== BY YEAR ===\r\n44\t2020\r\n43\t2021\r\n80\t2022\r\n101\t2023\r\n96\t2024\r\n79\t2025\r\n2\t2026\r\n","rejected":false,"notInterrupted":true}
```

### Assistant — 2026-07-09 17:42

> **Tool:** `update_current_step` completed
```
{"currentStep":"Compiling filename analysis report","finalSummary":"Analyzed **445** PDFs in `data\\mahika\\amazon-seller-invoices\\` (excluding `_*` temp files). All use `YYYY-MM-DD_<DocType>_<Series-ID>.pdf`. Five document types dominate; **no duplicate invoice IDs**; coverage spans **2020-01** through **2026-01**.","completedSubtitle":"Analyzed 445 invoice PDF filenames"}
```

### Assistant — 2026-07-09 17:42

> **Tool:** `run_terminal_command_v2` completed
```
{"output":"155\tMerchant_VAT_Invoice\r\n111\tMerchant_VAT_Credit_Note\r\n103\tFulfillment_by_Amazon_Tax_Invoice\r\n70\tProduct_Ads_VAT_Invoice\r\n1\t[nonstandard] Fulfillment_by_Amazon_Tax_Invoice_HR-2021-26028-1\r\n1\t[nonstandard] Fulfillment_by_Amazon_Tax_Invoice_HR-CN-E-1100\r\n1\t[nonstandard] Merchant_VAT_Credit_Note_KA-CN-E-7485\r\n1\t[nonstandard] Merchant_VAT_Invoice_KA-2021-628512-1\r\n1\t[nonstandard] Product_Ads_VAT_Credit_Note_ADS-CN-E-15913\r\n1\t[nonstandard] Product_Ads_VAT_Invoice_ADS-21-183359-1\r\n","rejected":false,"notInterrupted":true}
```

### Assistant — 2026-07-09 17:42

## Invoice PDF filename analysis

**Directory:** `c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices\`  
**Total PDFs (excluding `_*` temp):** **445** — sab mein `YYYY-MM-DD` prefix hai.

---

### 1) Filename pattern

```
YYYY-MM-DD_<DocumentType>_<SeriesPrefix>-<FY>-<InvoiceNumber>.pdf
```

| Part | Meaning | Examples |
|------|---------|----------|
| `YYYY-MM-DD` | Invoice / statement date (month-end mostly) | `2025-12-31`, `2023-07-31` |
| `<DocumentType>` | Amazon doc category (underscores) | `Merchant_VAT_Invoice`, `Fulfillment_by_Amazon_Tax_Invoice` |
| `<SeriesPrefix>` | State / product line | `KA` (Karnataka merchant), `HR` (FBA), `ADS` (Product Ads) |
| `-C-` | Credit note (optional) | `KA-C-26-1422864` |
| `<FY>` | Financial year code | `2526`, `1920`, `26` |
| `<InvoiceNumber>` | Sequential ID | `3284310`, `33307` |

**Examples:**
- `2020-01-31_Fulfillment_by_Amazon_Tax_Invoice_HR-1920-33307.pdf`
- `2025-12-31_Merchant_VAT_Credit_Note_KA-C-26-1422864.pdf`
- `2020-01-31_Product_Ads_VAT_Invoice_ADS-1920-326986.pdf`

**Edge cases (6 files, Oct 2020):** non-standard IDs — `-1` suffix, `CN-E-` format, ya ID type string ke andar merge ho gayi.

---

### 2) Unique invoice types (standard)

| Count | Document type |
|------:|---------------|
| 155 | `Merchant_VAT_Invoice` |
| 111 | `Merchant_VAT_Credit_Note` |
| 103 | `Fulfillment_by_Amazon_Tax_Invoice` |
| 70 | `Product_Ads_VAT_Invoice` |
| 6 | Non-standard (Oct 2020 anomalies) |

**4 main types** + 6 outliers. Credit notes sirf `Merchant_VAT_Credit_Note` dominate (111); `Product_Ads_VAT_Credit_Note` = 1 outlier.

---

### 3) Year–month distribution (`YYYY-MM` from prefix)

**Range:** `2020-01` → `2026-01` (73 months) · **avg ~6.1 files/month**

| Year | PDF count |
|------|----------:|
| 2020 | 44 |
| 2021 | 43 |
| 2022 | 80 |
| 2023 | 101 |
| 2024 | 96 |
| 2025 | 79 |
| 2026 | 2 |

**Monthly detail (selected):**

| YYYY-MM | Count | YYYY-MM | Count |
|---------|------:|---------|------:|
| 2020-01 | 3 | 2023-01 | 11 |
| 2020-10 | 8 | 2023-07 | 8 |
| 2022-06 | 8 | 2024-06 | 8 |
| 2022-07 | 10 | 2025-07 | 8 |
| 2022-12 | 8 | 2025-12 | 2 |
| | | 2026-01 | 2 |

Typical month: **3–4 files** (early 2020–2021) → **8 files** (2022+): ~3 invoice types + credit notes.

---

### 4) Duplicate invoice IDs

**None found.**  
439/445 files parsed clean ID (`KA-2526-3284310`, `HR-C-24-11907`, etc.) — har ID unique.

---

### 5) Sample filenames (5, spread across timeline)

1. `2020-01-31_Fulfillment_by_Amazon_Tax_Invoice_HR-1920-33307.pdf`
2. `2022-06-30_Merchant_VAT_Credit_Note_KA-C-23-278925.pdf`
3. `2023-07-31_Fulfillment_by_Amazon_Tax_Invoice_HR-C-24-11907.pdf`
4. `2024-09-30_Fulfillment_by_Amazon_Tax_Invoice_HR-C-25-25208.pdf`
5. `2026-01-31_Merchant_VAT_Invoice_KA-2526-3284310.pdf`

---

**Kaise parse karein:** date = first 10 chars; type = underscore block before last `_XX-####-####` segment; invoice ID = trailing `[A-Z]{2,4}(-C)?-\d{2,4}-\d+`.

Detail chahiye (e.g. Oct 2020 outliers, ya ID series breakdown `KA` vs `HR` vs `ADS`)?
