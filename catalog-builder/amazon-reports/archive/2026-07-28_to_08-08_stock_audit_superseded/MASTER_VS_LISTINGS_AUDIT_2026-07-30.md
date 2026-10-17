# Master inventory vs Excel `(6).xlsm` vs All Listings — 2026-07-30

Sources:
- Sir master inventory (this chat)
- `C:\Users\DELL\Downloads\PHONE_ACCESSORY (6).xlsm` (47 rows after IP13PMGX dedupe)
- `All+Listings+Report_05-12-2026.txt`
- Prior classify: `stock_vs_all_listings_report_2026-07-28.csv` (OK 30 / OOS 48 / QUALITY_GAP 20 / MISSING 2)

Quality rules: Incell≈LCD≈TFT · OLED≈AMOLED · CareOG≈Original · WF=With Frame · no OLED↔LCD cross.

---

## Excel file — what is actually in it

All 47 rows: `PHONE_ACCESSORY` + `Edit (Partial Update)` + Quantity(IN) col **103** only. Every SKU exists in All Listings.

| # | SKU | File qty | Amz qty | Listing (truth) | Fits master? |
|---|-----|--------:|--------:|-----------------|--------------|
| 1 | RM7i | 1 | 0 | Realme 7i LCD | Yes — 7i Incell |
| 2 | RMEC33OG | 1 | 0 | Realme C33 LCD | Yes — C33 Incell |
| 3 | RLM11ProOG | 1 | 0 | Realme 11 Pro CareOG | Yes |
| 4 | Y33S | 1 | 0 | Vivo Y33s LCD | Yes |
| 5 | Y22 | 1 | 0 | Vivo Y22/Y22s LCD | Yes (covers Y22 Incell; Y22 CareOG is different SKU if exists) |
| 6 | T12021CARE | 1 | 0 | Vivo T1 (2021) CareOG | Yes (label T1) |
| 7 | T2XCARE | 1 | 0 | Vivo T2x CareOG | Yes |
| 8 | VVX70Pro+OG | 1 | 0 | Vivo X70 Pro+ CareOG | Yes |
| 9 | V11PROLED | 1 | 0 | Vivo V11 Pro CareOG | Yes |
| 10 | V17CARE | 1 | 0 | Vivo V17 CareOG | Yes |
| 11 | V15CARE | 1 | 0 | Vivo V15 CareOG | Yes |
| 12 | VVX80OG | 1 | 0 | Vivo X80 CareOG | Yes |
| 13 | RNO10Pro+OG | 2 | 0 | Reno 10 Pro+ CareOG | Yes (qty 2) |
| 14 | F5B | 1 | 0 | Oppo F5 Black LCD | Yes for **F5 Incell**; not Frame |
| 15 | 1+8CARE | 2 | 0 | OnePlus 8 CareOG | Yes (qty 2) |
| 16 | 1+10PROCARE | 1 | 0 | OnePlus 10 Pro CareOG | Yes |
| 17 | 1+7CARE | 1 | 0 | OnePlus 7 CareOG | Yes |
| 18 | 1+8ProLCD | 1 | 0 | OnePlus 8 Pro LCD | Yes — 8 Pro Incell |
| 19 | 1+11RCARE | 1 | 0 | OnePlus 11R CareOG | Yes |
| 20 | CE2LYTCARE | 1 | 0 | **Nord CE 2 Lite** CareOG | **NO** — master is OnePlus **Nord** CareOG |
| 21 | 1+9CARE | 1 | 0 | OnePlus 9 CareOG | Yes |
| 22 | IP13MiniLCD | 1 | 0 | **iPhone 13 Mini** LCD | **NO** — master is iPhone **13** Incell |
| 23 | IP13PMGX | 1 | 1 | iPhone **13 Pro Max** GX OLED | Yes for **13 Pro Max OLED** only (not 13 Pro) |
| 24 | IP13PMLCD | 1 | 0 | iPhone 13 Pro Max LCD | Yes — 13 Pro Max Incell |
| 25 | 11PMAXOLED | 1 | 0 | iPhone 11 Pro Max GX OLED | Yes |
| 26 | 11PMAXLCD | 1 | 0 | iPhone **11 Pro Max** LCD | **NO** — master is iPhone **11** Incell |
| 27 | IP8+WCARE | 1 | 0 | iPhone **8+** White CareOG | **NO** — master iPhone **8** CareOG / 8 Plus **Incell** |
| 28 | IPXSLCD | 1 | 0 | iPhone Xs LCD | Yes — XS Incell |
| 29 | IP14PMLCD | 1 | 0 | iPhone 14 Pro Max LCD | Yes |
| 30 | GLXS20FeWFLED | 1 | 0 | S20 FE WF Amoled | Yes |
| 31 | J7PRIME16G | 1 | 0 | J7 Prime 2016 Gold LCD | Yes — J7 2016 Incell |
| 32 | MINOTE5BWFCARE | 1 | 0 | Note 5 **Black** WF CareOG | **Color** — master wants **White** WF |
| 33 | Mi11i/11XOLED | 1 | 0 | Mi 11i/11X OLED | Yes — Mi 11X OLED |
| 34 | XMI11X | 1 | 0 | Mi 11X LCD | Yes — Mi 11X Incell |
| 35 | XMIA3TFT | 1 | 0 | Mi A3 LCD | Yes — Mi A3 Incell |
| 36 | MIK20 | 1 | 1 | K20/K20 Pro LCD | Yes (already amz qty 1) |
| 37 | VL-KE1B-VAIP | 1 | 0 | Note 7/7s/7 Pro LCD | Yes — Note 7 Incell |
| 38 | NTG1OG | 1 | 0 | Nothing Phone 1 CareOG | Yes |
| 39 | INN11S | 1 | 0 | Infinix Note 11S LCD | Yes |
| 40 | HNR8C | 1 | 0 | Honor 8C LCD | Yes |
| 41 | HNR8X | 1 | 0 | Honor 8X LCD | Yes |
| 42 | HNRX9B(5G)LCD | 1 | 0 | Honor X9B LCD | Yes |
| 43 | NKG21 | 1 | 0 | Nokia G21 LCD | Yes |
| 44 | NKC3 | 1 | 0 | Nokia C3 LCD | Yes |
| 45 | EDGE50FusionLCD | 1 | 0 | Edge 50 Fusion LCD | Yes |
| 46 | MOTOG34WFOG | 1 | 0 | Moto G34 WF CareOG | Yes — G34 Frame |
| 47 | ZFMXM2TFT | 1 | 0 | Zenfone Max M2 LCD | Yes |

### Remove / replace before upload (Sir audit)

1. **IP13MiniLCD** — wrong model (13 Mini ≠ 13)
2. **11PMAXLCD** — wrong model (11 Pro Max ≠ 11)
3. **IP8+WCARE** — wrong model (8+ ≠ 8 CareOG)
4. **CE2LYTCARE** — wrong model (CE 2 Lite ≠ Nord) unless Sir accepts CE2 Lite as Nord stock line
5. **MINOTE5BWFCARE** — Black vs White
6. Optional drop **IP13PMGX** / **MIK20** — Amazon qty already ≥1

### Excel does NOT cover (still in master, need correct SKU or Create)

From Jul-28 + master (high confidence gaps):

| Master | Issue |
|--------|--------|
| Realme C67 Incell | QUALITY_GAP (only WF CareOG listing) |
| Realme C30 / C53 Incell | QUALITY_GAP (CareOG/WF listings, not plain Incell) |
| Realme 13 Pro CareOG | MISSING |
| Realme 3 Pro Frame | QUALITY_GAP |
| F17/F19/F27 OLED | QUALITY_GAP (Active LCD listings only) |
| F5 Frame | QUALITY_GAP |
| OnePlus 7 Incell, 10R Incell, 9RT Incell | check / may be OK elsewhere |
| iPhone 13 Incell, 13 Pro OLED, 11 Incell, 8 Plus Incell, 8 CareOG | wrong/missing SKUs in excel |
| Galaxy A73 OLED, S21 FE OLED, J7 Next/Max Incell | gap / AMOLED mismatch |
| Redmi 4A WF, Note 10T WF, 12 WF, 12 5G WF, 13 Pro+ WF, Poco X3/M4 | gap |
| Honor 7X / 7X White, Nokia G10/G20, Moto G9, G40, Asus ROG 2 | not in this excel |
| Infinix Note 10, Hot 9 | not in this excel |

Jul-28 rollup for older stock file (~100 lines): **OK 30 · OUT_OF_STOCK 48 · QUALITY_GAP 20 · MISSING 2**.

---

## Recommendation for audit

**Safe to keep in Partial Update upload (~40 rows):** all Yes rows above (LCD≈Incell OK).

**Fix or delete first:** IP13MiniLCD, 11PMAXLCD, IP8+WCARE, CE2LYTCARE, MINOTE5BWFCARE.

**Do not Full Update** — qty-only Partial Update is correct for the Yes rows.

After Sir edits the file, say **upload**.
