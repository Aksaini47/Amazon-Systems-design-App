# Phase 2 outcomes — Galaxy + Redmi/Mi/Poco (amazon-ads-3 / p2fix)

**Session:** Sir Chrome Ads (Badeja) + `amazon-ads-3` · **Campaign:** `TL_EL_SPN_SG_Mobile Screens - Arun` · **2026-07-22**

## Leftover finish pass (this session — live verify)

| Item | Result |
|---|---|
| Galaxy A32 ASINs | **VERIFIED DONE** — LCD `B0FRSVSLH4` Enabled/Delivering; CareOG `B0FRSYNQ6H` **Paused**; OLED WF `B0FRSYGSMF` **Paused** (Archive never used) |
| Galaxy A32 keywords | **VERIFIED** — BPE @ ₹3 visible (`galaxy a32 display original` Broad+Phrase+Exact; `galaxy a32 display` Broad; + keyword group). Prior Total **43**. |
| Galaxy A32 negatives | **VERIFIED** — Total **6**: Phrase `pro`, `max`, `pro max`, `plus`, `5g` + Exact `4g` (no Phrase `4g` — in model name) |
| Galaxy S20 FE WF OLED | **failed_skip** — plan `B0F3JR7BQ9` Inactive; only quality match SKU `GLXS20FeWFLED` ASIN `B0GKGVNXNL` also **Inactive** (listings report). No Active OLED/AMOLED+WF ASIN. No LCD↔OLED force. |
| Galaxy J7 Prime (2016) | **exists_enabled** `A07077631NTH1V7TFJ6WV` — leave Enabled (LCD OK; no further action) |
| Mi 11X OLED / Incell | **failed_skip** — listings **Inactive** (`B0FLQHV7ZV` / `B0BZT5FTRQ`) |
| Mi A3 Incell / K20 Incell | **still_blocked** — listings Active but Ads browser returned to Sign-In after A32 verify; create needs live Ads session |

## Counts

| Bucket | Count |
|---|---:|
| created / created_fixed | 1 |
| exists_* (enabled/reused) | 7 |
| skipped_quality_conflict* | 11 |
| failed_skip / failed_create | 5 |
| still_blocked (need Ads login) | 2 |
| **create rows in scope** | **26** |

## IDs — created / fixed

| Ad group | ID | Stock | ASIN |
|---|---|---|---|
| Galaxy A32 | `A091776017XH8Q480GEKN` | Galaxy A32 4G Incell | `B0FRSVSLH4` |

## IDs — exists enabled / reused

| Ad group | ID | Stock | ASIN |
|---|---|---|---|
| Galaxy A31 | `A02810171EUNHAMIGCSCJ` | Galaxy A31 Incell | `B0CPTD4KL9` |
| Galaxy J7 Prime (2016) | `A07077631NTH1V7TFJ6WV` | Galaxy J7 2016 Incell | `B0CPTCXZRZ` |
| Galaxy A30s | `A088091616JUNTR4QH4A3` | Galaxy A30s Incell | `B0CPTBRX46` |
| Galaxy A10 | `A08727522R6N51EWF5W6Z` | Galaxy A10 Incell | `B0CPTFBQM4` |
| Redmi 10 Power | `A05907496B6DKCPQISY2` | Redmi 10 Power Incell | `B0BYVM95J3` |
| Redmi Note 6 Pro | `A04782503ALR6BPUN8J5O` | Redmi Note 6 Pro Incell | `B0CPTBK5J6` |
| Redmi Note 7/7s/7 Pro | `A02577102Z1S9V7SI2BNU` | Redmi Note 7 Incell | `B0BBZNNN7C` |

## Skipped / failed

| Stock | Outcome | Notes |
|---|---|---|
| Galaxy A73 OLED | skipped_quality_conflict | stock OLED vs listing LCD/TFT — no force |
| Galaxy S21 FE OLED | skipped_quality_conflict | stock OLED vs listing LCD/TFT — no force |
| Galaxy J7 Next Incell | skipped_quality_conflict_exists_name | stock Incell vs listing AMOLED; live AG name exists — do not recreate |
| Galaxy J7 2015 Incell | skipped_quality_conflict_exists_name | stock Incell vs listing AMOLED; live AG exists |
| Galaxy J7 Max Incell | skipped_quality_conflict_exists_name | stock Incell vs listing AMOLED; live AG exists |
| Redmi Note 5 With Frame White | skipped_quality_conflict | stock White vs listing Black CareOG WF — color conflict |
| Redmi 4A With Frame Incell Black | skipped_quality_conflict | stock Incell vs listing CareOG WF — no force |
| Redmi Note 10T With Frame | skipped_quality_conflict | stock WF vs listing non-WF LCD |
| Redmi 13 Pro Plus With Frame | skipped_quality_conflict | stock WF Redmi 13 Pro+ vs listing Note 13 Pro+ LCD non-WF |
| Poco X3 Incell | skipped_quality_conflict | stock Incell X3 vs listing CareOG Poco X3 GT |
| Poco M4 Incell | skipped_quality_conflict | stock Poco M4 vs listing Poco M4 Pro — wrong model |
| Galaxy S20 FE With Frame OLED | failed_skip | Inactive quality match only (`B0F3JR7BQ9` / `B0GKGVNXNL`); no Active OLED+WF |
| Redmi 12 With Frame | failed_skip | listing Inactive + title is Redmi 12 Pro (wrong model) ASIN B0F3JLHWNR |
| Redmi 12 5G With Frame | failed_skip | listing Inactive + title is Redmi 12 Pro (wrong model) ASIN B0F3JLHWNR |
| Mi 11X OLED | failed_skip | listing Inactive `B0FLQHV7ZV` |
| Mi 11X Incell | failed_skip | listing Inactive `B0BZT5FTRQ` |
| Mi A3 Incell | still_blocked | Active `B0BZT5V9T8` — need Ads login to create |
| Redmi K20 Incell | still_blocked | Active `B0BYVP2LWV` — need Ads login to create |

## Graphify deep links

- Galaxy A32: `/ad-groups/A091776017XH8Q480GEKN/{ads,targeting,negative-targeting}`
- Galaxy A30s: `/ad-groups/A088091616JUNTR4QH4A3/ads`
- Galaxy J7 Prime (2016): `/ad-groups/A07077631NTH1V7TFJ6WV/ads`
- Redmi 10 Power: `/ad-groups/A05907496B6DKCPQISY2/ads`
- Redmi Note 6 Pro: `/ad-groups/A04782503ALR6BPUN8J5O/ads`
- Redmi Note 7/7s/7 Pro: `/ad-groups/A02577102Z1S9V7SI2BNU/ads`

Archive: **never used**. Campaign negatives: **untouched**.
