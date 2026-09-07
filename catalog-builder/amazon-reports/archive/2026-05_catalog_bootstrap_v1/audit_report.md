# Bulk Upload Audit — `bulk_upload_update_final_FIXED_v6.xlsx`

**Total SKUs:** 1283
**Listing action:** Edit (Partial Update)
**Columns:** 28 (SKU, product_type, listing_action, item_name, brand, main_image_url, other_image_url_1, other_image_url_2, other_image_url_3, other_image_url_4...)

## Column alignment

**Header ↔ data alignment:** ✅ canonical (data positions match header labels). All 28 columns line up correctly.

_Skip ahead to section A._


## A. Field population
| field | populated | % |
|---|---|---|
| title | 1283 | 100.0% |
| brand | 0 | 0.0% |
| description | 1283 | 100.0% |
| bullet1 | 1283 | 100.0% |
| bullet2 | 1283 | 100.0% |
| bullet3 | 1283 | 100.0% |
| bullet4 | 1283 | 100.0% |
| bullet5 | 1283 | 100.0% |
| keywords | 1283 | 100.0% |

> **Reading this:** Empty cells on Edit Partial Update mean "leave the existing Amazon listing field unchanged." If bullets 2-4 show 0% populated, that's by design — the bulk file only updates bullet1 + bullet5 + title + keywords + price + MRP.

## B. Hard compliance limits (Amazon India 2026)
| check | violations |
|---|---|
| title > 200 chars | 0 (0.0%) |
| bullet1 > 255 chars | 0 (0.0%) |
| bullet2 > 255 chars | 0 (0.0%) |
| bullet3 > 255 chars | 0 (0.0%) |
| bullet4 > 255 chars | 0 (0.0%) |
| bullet5 > 255 chars | 0 (0.0%) |
| bullets total > 1000 bytes (indexing cliff) | 0 (0.0%) |
| keywords > 200 bytes (India hard cap) | 0 (0.0%) |
| brand column populated on Edit Partial Update | 0 (0.0%) |

## C. Banned promotional terms
**SKUs with at least one banned term:** 0 (0.0%)

## D. Emoji + ALL CAPS
**SKUs with emojis:** 0 (0.0%)
**SKUs with non-allowlisted ALL CAPS words:** 2 (0.2%)

Top all-caps words flagged (allowlist excludes LCD/OLED/AMOLED/etc):
| word | SKU count | sample |
|---|---|---|
| `GLUOG` | 2 | PIXL6PCARE, PIXL6ProWFLED |

## E. Tier name leakage (memory: tiers internal-only)

**Hard tier-name leaks (Bronze/Silver/AAA in customer-facing fields):** 0 (0.0%)
**Gold appearing outside device-color parens:** 2 (0.2%) _(33 of 33 "gold" hits are inside `(Gold)` parens — legitimate device-color references like "Galaxy J7 Pro (Gold)", not tier leaks)_
**"Premium" marketing wording (borderline; not in explicit ban list):** 0 (0.0%)

## F. Title ↔ bullet1 consistency
| check | mismatches |
|---|---|
| brand mismatch | 0 (0.0%) |
| screen type mismatch | 0 (0.0%) |
| frame status mismatch | 0 (0.0%) |

## G. Hinglish keywords (user preference)
**SKUs with at least one Hinglish token in `keywords` (sceen/kharab/marammat/asali):** 1283 (100.0%)
**SKUs missing Hinglish:** 0 (0.0%)

## H. Warranty wording in bullet5
**SKUs with "7 days" or "seven days" in bullet5:** 1283 (100.0%)
**bullet5 populated but missing warranty wording:** 0 (0.0%)

## I. Support reference
**SKUs mentioning repairfully.com:** 1283 (100.0%)

## Summary
- Per-SKU findings written to `audit_findings.csv` (4 rows)
- High-severity violation incidents (length cliffs + banned + emoji + tier leak + title mismatch): 0

## How to use this report
1. Open `audit_findings.csv` in Excel, filter by `issue_type` to find specific SKUs
2. For Edit Partial Update mode, empty bullet2-4 cells are intentional (preserves existing Amazon content)
3. Bullet length cap is 255 chars per bullet AND 1000 bytes total across all 5 bullets (indexing cliff — anything past 1000 bytes is shown but not searchable)