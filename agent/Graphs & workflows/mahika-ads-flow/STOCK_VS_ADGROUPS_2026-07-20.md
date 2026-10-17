# Stock vs ad-group reconciliation

**Source stock file:** `catalog-builder/actual stock.txt` (also duplicated at `catalog-builder/amazon-reports/actual stock.txt` — identical, 117 lines, 74 line-item SKUs across 8 brand categories).
**Source campaign:** `TL_EL_SPN_SG_Mobile Screens - Arun` (`A038001030A5E0IF4R8UV`), 159 ad groups total.
**Method:** searched the live Ads console "Find an ad group" box by brand/model term, read the DOM result list + `Total: N` count per search. Some brand searches only rendered part of their result set in the virtualized grid (noted below) — **Total counts are reliable, individual name lists may be missing 1-2 low-traffic entries per brand.**

## Ad groups per brand (confirmed via search)

| Brand searched | Total ad groups | Notes |
|---|---|---|
| Realme | 18 | full list captured |
| Vivo | 11 | 9 of 11 names captured |
| Oppo | 21 | 19 of 21 captured — confirms **Oppo F17**, **Oppo F17 Pro**, **Oppo F19 / F19 Pro** all exist as separate groups (F19 combined, matches shared-family doctrine) |
| OnePlus (`1+`) | 11 | 9 of 11 captured — "1+ Nord 2" (known real, top-10) not in this capture, virtualization gap |
| iPhone | 15 | 13 of 15 captured — confirms **IPhone 11 Pro Max** exists (exact spelling: capital "I") |
| Samsung (`Galaxy`) | 22 | 20 of 22 captured — "Galaxy F23" (known real) not in this capture |
| Redmi | 17 | 15 of 17 captured |
| Poco | 5 | 3 of 5 captured |
| Mi (standalone, not Redmi) | 3 confirmed | Mi 11X, Mi 11i, Mi Max 2 |
| Nothing | 1 | Nothing Phone 1 |
| Infinix | 10 | includes 4 **Archived** status entries + apparent name-casing duplicates ("Infinix Note 10" appears twice, "Infinix Note 11"/"Note 11s"/"Note 11S" all separate) |
| Honor | 5 | 3 of 5 captured |
| Nokia | 3 | 1 of 3 captured |
| Moto | ~5 | partial capture |
| **Asus** | **0** | **zero ad groups of any kind** |

**Running total across searched brands: ~152.** Campaign has 159 — remainder are likely brands not yet searched (Tecno, small counts) or duplicate-name variants across the above.

## Stock list (74 items, 8 categories) — full reference

**REALME (14):** C67, 8, 7i, 9, C33, 11 Pro, 9i, C21, C30, C53, 8i, 13 Pro, 3 Pro, 7 Pro
**VIVO (10):** Y33s, Y22 (×2 variants), T1, T2x, X70 Pro Plus, V11 Pro, V17, V15, X80
**OPPO (10):** F17 Pro, A53, A57 5G, F19, A54 5G, F27, F9, Reno 10 Pro Plus, F5 (×2 variants)
**ONEPLUS (11):** 8, 10 Pro, 7 (×2), 8 Pro, 10R, 11R, Nord, 9RT, 9, Nord CE 2 Lite
**APPLE (10):** 13, 13 Pro, 13 Pro Max (×2), 11 Pro Max, 11, 8 Plus, 8, XS, 14 Pro Max
**SAMSUNG (12):** A73, A32 (×2), A31, S21 FE, S20 FE, J7 Next, J7 2016, J7 2015, A30s, J7 Max, A10
**XIAOMI/REDMI/POCO (16):** Note 5, 11X (×2), Redmi 4A, A3, Note 10T, K20, Redmi 12, Redmi 12 5G, Redmi 13 Pro Plus, Redmi 10 Power, Note 6 Pro, Note 7, Poco X3, Poco M4
**MIX (18):** Nothing Phone 1, Infinix Note 10, Hot 9, Note 11S, Honor 7X (×2), 8C, 8X, X9B, Nokia G10, G20, G21, C3, Moto G9, Edge 50 Fusion, G34, Asus Zenfone Max M2, Asus ROG Phone 2

## Headline findings

### 1. Confirmed critical gap — Asus has stock but zero ads
`Asus Zenfone Max M2 Incell` and `Asus ROG Phone 2 Incell` are in stock; the campaign has **no Asus ad group at all**. These parts are getting zero paid discovery.

### 2. Stock items with no obvious matching ad group (need Sir's confirmation before creating anything — evidence gate applies per FLOW.md)
- Realme 7i, Realme C21, Realme 13 Pro, Realme 3 Pro
- Oppo F27 (not seen anywhere in the 19-of-21 Oppo capture)
- Vivo X70 Pro Plus, Vivo V15, Vivo X80 (not in the 9-of-11 Vivo capture — could be in the 2 uncaptured rows, needs re-check)
- Redmi Note 10T, Redmi K20 (ad group list has "Redmi K20/K20 Pro" — likely same, probably fine)
- Nokia C3, Nokia G21 (only Nokia G10 confirmed in the 1-of-3 capture)
- Honor 8C, Honor X9B (only 3 of 5 Honor names captured — may just be uncaptured, not necessarily missing)

**These are candidates, not confirmed gaps** — several fall in the un-rendered portion of a brand search and need a second pass (scroll fully or search the exact model name) before concluding they truly don't exist.

### 3. Ad groups running for models no longer in the stock list (dead weight, spending clicks on unsellable parts)
Realme alone: Realme 5/5S/5i, Realme 6/6s, Realme 7, Realme 9 Pro+, Realme C20, Realme 10, Realme C55 — none of these appear in current stock. Likely true across other brands too (not fully cross-checked yet). **These groups should probably be part of the "pause the other ~156" set regardless of the 3-ASIN task — they can't fulfill orders.**

### 4. Data-quality issue — duplicate/casing ad groups
Infinix has near-duplicate ad groups from casing/naming drift: "Infinix Note 10" (×2), "Infinix Note 11" / "Note 11s" / "Note 11S" (3 separate groups for what may be 1-2 real models). Worth a cleanup pass separately from the current task.

### 5. Relevance to the "pause 156, keep 3 active" task in progress
Oppo F17 Pro, iPhone 11 Pro Max (as "IPhone 11 Pro Max"), and Oppo F19 / F19 Pro all **confirmed to exist** as distinct ad groups — safe to search-and-enable by exact name. Their stock backing:
- Oppo F17 Pro OLED — in stock ✓
- iPhone 11 Pro Max OLED — in stock ✓
- Oppo F19 OLED — in stock ✓ (F19 Pro not separately listed in stock, but doctrine already treats F19/F19 Pro as one shared-family group)

All 3 target ad groups have real stock backing — good to proceed.

## Caveat

This is a first-pass reconciliation from live search, not a full row-by-row export. Before treating any "missing ad group" or "dead ad group" finding as final, re-verify with a direct search on the specific model name (as was done for Oppo A54, which looked missing from the brand-level list but was confirmed present via direct search) — the console's virtualized grid under-renders on brand searches returning more than ~15-19 results.
