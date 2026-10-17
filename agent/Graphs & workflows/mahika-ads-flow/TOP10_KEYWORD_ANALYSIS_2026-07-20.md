# Top 10 ad groups by impressions — keyword pattern analysis

**Campaign:** `TL_EL_SPN_SG_Mobile Screens - Arun` (`A038001030A5E0IF4R8UV`) · **Entity:** `ENTITY37NJTG1VOHVTB` (Badeja Enterprises)
**Pulled:** 2026-07-20, live Ads console, DOM text (`get_page_text`), sorted by Impressions descending.
**Correction note:** an earlier pass misread "Realme 8" as "Redmi 8" and "iPhone 6s" as "iPhone 5s" off a screenshot. This file is DOM-verified — no "Redmi 8" or "iPhone 5s" ad group exists anywhere in this campaign's 159 groups.

## Ad group ranking (source of truth)

| # | Ad group | Ad group ID | Impressions | Cost | Purchases | Sales | ROAS |
|---|---|---|---|---|---|---|---|
| 1 | Realme 8 | `A07680621AJNOC1F9CHBW` | 6,867 | ₹851.89 | — | — | — |
| 2 | Redmi 12 | `A065011614KF9MKOG3Y5F` | 5,128 | ₹1,477.95 | — | — | — |
| 3 | iPhone XS | `A0388612130A9ULA40CJ3` | 3,944 | ₹655.40 | 1 | ₹3,620.34 | 5.52 |
| 4 | iPhone 11 | `A09027603BX4HMI7C02IG` | 3,631 | ₹577.89 | 1 | ₹2,056.78 | 3.56 |
| 5 | iPhone 6s | `A048178223ZZS7JDI1Q81` | 2,847 | ₹236.73 | — | — | — |
| 6 | 1+ Nord 2 | `A0750411NNIPX7IDE12A` | 2,813 | ₹409.41 | 1 | ₹4,189.83 | 10.23 |
| 7 | Redmi Note 7/7s/7 Pro | `A02577102Z1S9V7SI2BNU` | 2,768 | ₹458.43 | — | — | — |
| 8 | Oppo A54 | `A078902117NX4IWGM9XMP` | 2,598 | ₹343.31 | 1 | ₹1,270.34 | 3.70 |
| 9 | Redmi Note 9 Pro | `A05606651AYV76EVSFYIF` | 2,383 | ₹392.91 | — | — | — |
| 10 | Realme 5/5S/5i | `A00294891R80HM1GX8RZ8` | 2,184 | ₹392.36 | 1 | ₹1,598.31 | 4.07 |

Next tier (not deep-pulled): Redmi Note 5 (`A00135061SPDP3FATG1CP`, 2,168), Oppo A53 (`A030354537UFK8PVW5ARE`, 1,965), Galaxy F23 (`A01375041QA7TDNI1PWIA`, 1,958), Realme 7 Pro (`A022568729OX5U6B7H6A`, 1,920), Redmi 6 Pro (`A02277431GJT9187C25VT`, 1,824), Oppo F17 (`A093953938RPRE6IXGDV4`, 1,723).

## The universal template (7 of 10 groups run it verbatim)

Realme 8, Redmi 12, iPhone XS, iPhone 11, iPhone 6s, 1+ Nord 2, Redmi Note 9 Pro, Realme 5/5S/5i all carry the **identical 8-suffix keyword template** on `<model>`, each suffix in Exact/Phrase/Broad triples:

1. `<model> display` — **always the #1 or #2 traffic driver, every time**
2. `<model> display cost`
3. `<model> display original`
4. `<model> combo`
5. `<model> combo display original`
6. `<model> combo folder`
7. `<model> broken screen replacement` — **consistently 0 impressions**
8. `display of <model> lite` — **consistently 0 impressions**

### Per-group: `<model> display` (Broad) impressions — the dominant keyword everywhere

| Ad group | `display` Broad impr | 2nd highest keyword | impr |
|---|---|---|---|
| Realme 8 | 1,408 | `realme 8 display cost` (Broad) | 257 |
| Redmi 12 | 932 | `redmi 12 combo` (Broad) | 301 |
| iPhone XS | 1,249 | `iphone xs display cost` (Broad) | 221 |
| iPhone 11 | 647 | `iphone 11 display cost` (Broad) | 396 |
| iPhone 6s | 967 | `iphone 6s display cost` (Broad) | 427 |
| 1+ Nord 2 | 832 | `nord 2 combo folder` (Broad) | 42 |
| Redmi Note 9 Pro | 630 | `redmi note 9 pro display cost` (Broad) | 227 |
| Realme 5/5S/5i | 816 | `realme 5 display original` (Broad) | 282 |

### Exception 1 — Redmi Note 7/7s/7 Pro (multi-model group, keyword text uses "note 7 pro" only)

Here `display cost` (Phrase) **out-drives** plain `display` (Broad): 811 vs 314 impressions. `combo` (Broad) is close behind at 341. Worth checking Search Terms — could mean shoppers for this specific model type "cost" more often, or it's noise from a small sample.

### Exception 2 — Oppo A54 (138 keywords vs ~72-99 for everyone else)

This group has been **manually expanded past the template** — extra variants not seen anywhere else in the top 10:
- `oppo a54 folder`, `oppo a54 folder display`, `oppo a54 folder display original` (drops "combo", keeps "folder")
- `oppo a54 ka display`, `oppo a54 ka folder` — **Hindi possessive "ka"**, real vernacular search behavior
- `oppo a54 display price`, `oppo a54 display replacement`, `oppo a54 lcd`
- `crown oppo a54 display` — "Crown" is a specific screen-part brand/variant name, not a phone model

Only the first ~40 of 138 keywords were pulled (page 1-2 of 3 — table pagination wasn't fully exhausted this pass). Impressions seen so far: `oppo a54 combo` (Broad) 47, `oppo a54 combo display` (Broad) 44, `oppo a54 folder` (Broad) 43, `crown oppo a54 display` variants ~0. **The bulk of this group's 2,598 impressions live in the untraced ~98 remaining keywords** — flag for a follow-up pull before drawing conclusions on this group specifically.

## Synthesis (confirms Sir's hypothesis)

Buyers search `<model name>` + one of: **"display"**, **"display original"**, **"combo"** — exactly as suspected. Bare model name alone is rare. Ranked by real traffic weight across the sample:

1. `<model> display` (Broad) — by far the single biggest keyword in almost every group
2. `<model> display cost` — reliable #2, sometimes #1 (Redmi Note 7 Pro)
3. `<model> display original`
4. `<model> combo` / `combo folder` / `combo display original`
5. Dead weight, safe to leave paused/ignore: `broken screen replacement`, `display of <model> lite`

Oppo A54 suggests the template isn't the ceiling — vernacular ("ka"), part-brand names ("crown", "lcd"), and repair-intent phrasing ("display replacement", "display price") may be worth testing in other high-volume groups too.

## Open items for the next session

1. Finish pulling Oppo A54 pages 2-3 (98 keywords untraced).
2. Decide whether the "winning template" (display / display cost / display original / combo family) should be proactively added to ad groups below the top 10 that may be missing it.
3. Build the Oppo F17 Pro negative-exact keyword list using the base Oppo F17 group's own `display` / `display cost` / `display original` / `combo` Broad-match queries — confirmed approach, not yet built into a final preview.
4. iPhone 11 Pro Max and Oppo F19/F19 Pro negative-keyword decisions still open — need the equivalent base-model groups checked the same way F17 was.
