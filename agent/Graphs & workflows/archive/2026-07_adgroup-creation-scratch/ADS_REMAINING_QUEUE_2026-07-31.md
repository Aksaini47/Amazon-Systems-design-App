# Ads remaining queue — 2026-07-31 (after K20 verify + Realme 7i)

**Campaign:** TL_EL_SPN_SG_Mobile Screens - Arun (A038001030A5E0IF4R8UV)
**Entity:** ENTITY37NJTG1VOHVTB
**Updated:** 2026-07-31 ~02:30 IST

## Done this pass

| Brand | Model | Outcome | ID |
|---|---|---|---|
| XIAOMI | Mi A3 | **created_ineligible_product** (prior) | `A0237552245ODQ3Z08K5O` ASIN `B0FRSX7288` |
| XIAOMI | K20 Incell | **verified_fixed** — LCD OK; +K20 Pro BPE; safe negs (no Phrase `pro`) | `A02851655NMF3GRW8X4R` ASIN `B0FRSYCY2W` Ineligible |
| REALME | Realme 7i | **created_ineligible_product** — BPE 42 + Phrase negs | `A05601153KWG4QDC0T7GU` ASIN `B0FRSVD92Q` |
| REALME | 7 Pro / 8 / 8i / 9 / 9i | **exists_enabled** — skip recreate | see progress |
| VIVO | T2x / Y22 / Y33s | **exists_enabled** — skip recreate | see progress |
| VIVO | T1 (2022) | **exists** — not same as T1 (2021) queue row | `A08623972SG26AMSUG7C5` |

## Blocker

Ads browser CDP timeout during **Vivo V15** create (`os error 10060`). Wizard had CareOG `B0FRSX29JG` + BPE staged; Create failed (Custom bid / Phrase plus-4g modal). Auth tip: `--state ads-from-sc.json`.

## Next (priority)

1. Finish **Vivo V15** CareOG create (Custom bid ₹3 first; Phrase negs after create; skip 4g/5g/plus in wizard)
2. Listing eligibility fixes (Mi A3, K20, Realme 7i, others Ineligible)
3. **Create Vivo T1 (2021)** if still needed vs T1 (2022)
4. Y22 CareOG+LCD mix review (Pause wrong grade if policy requires — never Archive)
5. Rest of brand queue (Apple/Oppo/OnePlus/Mix)

## Ads homepage

https://advertising.amazon.in/campaign-manager/all-campaigns?entityId=ENTITY37NJTG1VOHVTB

Progress note: `ADS_PROGRESS_2026-07-31.md`
