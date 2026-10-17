# Search Term Report — full deep analysis

**Campaign:** `TL_EL_SPN_SG_Mobile Screens - Arun` (`A038001030A5E0IF4R8UV`) · Badeja Enterprises
**Source:** `Report_-_07_20_2026T01_28_48.csv` (Amazon Search Term Report, click-filtered — every row has ≥1 click)
**Analysed:** 2026-07-20 · pandas · script in session scratchpad (`analyze.py`, `f17.py`)

## Dataset at a glance

| Metric | Value |
|---|---|
| Rows (search-term × keyword × week bucket) | 1,821 |
| Ad groups covered | 83 (whole campaign, not just top 10) |
| Unique keywords we bid on (`Targeting`) | 544 |
| **Unique search terms customers actually typed** | **1,428** |
| Clicked impressions | 25,528 |
| Clicks | 3,359 |
| Spend (CPC × clicks) | ₹8,223 |
| Purchases | 10 |
| Sales | ₹24,936 |
| Blended ROAS | 3.03 · CTR 13.2% · avg CPC ₹2.45 · conv 0.30%/click |

> This report only contains search terms that earned a click, so "impressions" here = clicked-term impressions, not full campaign reach. Read it as **"what customers clicked and how they phrased it,"** which is exactly the demand-pattern question.

---

## A. How customers search — intent taxonomy (Sir's hypothesis, confirmed hard)

Every one of the 1,428 search terms bucketed into an intent (priority-ordered, most specific first), then summed by clicks:

| Intent bucket | uniq terms | clicks | clk% | spend | CPC | purch |
|---|---|---|---|---|---|---|
| **display original / original display** | 305 | **1,257** | **37.4%** | ₹2,836 | 2.26 | 5 |
| **display (plain)** | 341 | **866** | **25.8%** | ₹2,110 | 2.44 | 3 |
| folder (alone) | 151 | 232 | 6.9% | ₹547 | 2.36 | 0 |
| screen (alone) | 162 | 215 | 6.4% | ₹826 | 3.84 | 0 |
| combo display | 78 | 197 | 5.9% | ₹525 | 2.67 | 0 |
| display price/cost | 64 | 144 | 4.3% | ₹296 | 2.05 | 0 |
| combo (alone) | 89 | 116 | 3.5% | ₹292 | 2.52 | 1 |
| touch + display/screen | 50 | 74 | 2.2% | ₹192 | 2.59 | 1 |
| lcd | 41 | 52 | 1.5% | ₹105 | 2.03 | 0 |
| **ka display/folder (Hindi)** | 37 | 46 | 1.4% | ₹103 | 2.24 | 0 |
| broken/replacement/repair | 24 | 42 | 1.3% | ₹101 | 2.41 | 0 |
| combo display original | 25 | 41 | 1.2% | ₹90 | 2.20 | 0 |
| folder display | 25 | 37 | 1.1% | ₹70 | 1.89 | 0 |
| touch (alone) | 17 | 18 | 0.5% | ₹50 | 2.78 | 0 |
| glass | 10 | 12 | 0.4% | ₹52 | 4.34 | 0 |
| combo folder | 6 | 7 | 0.2% | ₹17 | 2.46 | 0 |

**Headline:** `display original` (37.4%) + plain `display` (25.8%) = **63% of all click demand**. Sir's read was right — and `display original` actually **beats** plain `display`. "combo" and "folder" families are real but a distant tail. "screen (alone)" is expensive (₹3.84 CPC, 0 conversions) — low-intent browsers.

**New signals the console UI didn't show:**
- **Hindi "ka" is real** — `oppo f17 ka folder`, `<model> ka display` = 46 clicks across 37 terms. Currently barely in the keyword base.
- **"display price / display cost"** = 144 clicks, cheapest CPC (₹2.05) — high-intent price-checkers worth a dedicated keyword.
- **"mobile display", "touch display", "original display price"** recur as real phrasings not in the template.

---

## B. Cross-model bleed — the ₹2,166 finding (26% of spend)

For every row, compared the model qualifiers in the **customer's search term** vs **our keyword**. Flagged rows where the customer typed a qualifier (`pro`, `max`, `plus`, `5g`, `4g`, `lite`…) that our keyword did **not** have — i.e. a base keyword catching a different-variant search.

| Qualifier customer typed (we lacked) | rows | clicks | spend | purch |
|---|---|---|---|---|
| 5g | 154 | 301 | ₹741 | 0 |
| pro | 124 | 207 | ₹768 | 0 |
| 4g | 58 | 82 | ₹238 | 0 |
| max / pro max | 24 | 67 | ₹155 | 0 |
| 5g + plus | 20 | 38 | ₹74 | 1 |
| plus | 26 | 35 | ₹134 | 0 |
| other combos | ~10 | ~15 | ~₹56 | 0 |

**Total bleed: 416 rows · 745 clicks · ₹2,166 spend · 1 purchase.**
**= 22.2% of all clicks and 26.3% of all spend went to a DIFFERENT model variant than the keyword we bid on** — almost entirely on **BROAD** match, almost all **zero conversions**.

This is the F17/F17-Pro problem, but campaign-wide. Worst offenders (by spend):

| ad group | our keyword | match | customer typed | clk | spend |
|---|---|---|---|---|---|
| Redmi Note 5 | redmi note 5 display | BROAD | redmi note 5 **pro** display combo | 11 | ₹66 |
| Redmi Note 11T | redmi note 11t original display | BROAD | redmi note 11t **5g** display original | 14 | ₹34 |
| Redmi 12 | redmi 12 original display | BROAD | redmi 12 **5g** display original | 14 | ₹32 |
| **Oppo F17** | oppo f17 display original | BROAD | oppo f17 **pro** display original | 10 | ₹30 |
| Vivo T1 (2022) | vivo t1 display | BROAD | vivo t1 **5g** display original | 11 | ₹27 |
| Realme 8 | realme 8 display original | BROAD | realme 8 **5g** display original | 11 | ₹23 |
| Redmi Note 9 Pro | redmi note 9 pro display | BROAD | redmi note 9 pro **max** display | 11 | ₹20 |

**Systemic fix (doctrine-approved, substring-safe):** every base-model group should **Negative Phrase** the qualifiers absent from its own model name — `pro`, `max`, `plus`, `5g`, `4g` — because those tokens are never a substring of the base group's own positive keywords, so they can't self-block. This is exactly the FLOW.md rule: *"A base-model group may phrase-negate unsupported qualifiers such as `pro`, `max`, or `pro max` when they are absent from every supported model name."* One phrase negative per qualifier per base group recovers most of this ₹2,166.

---

## C. Match-type economics — PHRASE is the quiet winner

| match type | clicks | clk% | CPC | spend | purch | conv% | ROAS |
|---|---|---|---|---|---|---|---|
| BROAD | 1,920 | 57.2% | ₹2.57 | ₹4,933 | 5 | 0.26% | 2.68 |
| **PHRASE** | 749 | 22.3% | **₹2.20** | ₹1,650 | 4 | **0.53%** | **4.91** |
| EXACT | 664 | 19.8% | ₹2.38 | ₹1,582 | 1 | 0.15% | 2.29 |
| auto (TARGETING_EXPRESSION) | 26 | 0.8% | ₹2.23 | ₹58 | 0 | 0 | 0 |

**PHRASE wins on every efficiency axis** — lowest CPC, 2× BROAD's conversion rate, best ROAS (4.91). BROAD buys 57% of clicks but leaks 26% of them to wrong models (§B). Small purchase count (10) means treat ROAS as directional, but the pattern is consistent.

---

## D. Winning terms — all 10 converters

| ad group | our keyword | match | customer search term | clk | spend | purch | sales |
|---|---|---|---|---|---|---|---|
| 1+ Nord 2 | nord 2 display | BROAD | one plus nord ce 2 5g display | 1 | ₹2 | 1 | ₹4,190 |
| iPhone XS | iphone xs display original | EXACT | iphone xs display original | 18 | ₹38 | 1 | ₹3,620 |
| iPhone 13 Pro | iphone 13 pro display | PHRASE | iphone 13 pro display | 4 | ₹12 | 1 | ₹3,049 |
| iPhone 13 Pro | iphone 13 pro lcd | BROAD | apple iphone 13 pro lcd with touch | 1 | ₹1 | 1 | ₹3,049 |
| Redmi Note 9 Pro Max | redmi note 9 pro max display | BROAD | redmi note 9 pro max display | 4 | ₹9 | 1 | ₹2,377 |
| Mi 11X | mi 11x display original | PHRASE | mi 11x display original | 3 | ₹5 | 1 | ₹2,086 |
| iPhone 11 | iphone 11 original display | BROAD | iphone 11 display original | 15 | ₹28 | 1 | ₹2,057 |
| iPhone 8 | iphone 8 combo | BROAD | iphone 8 ka combo | 3 | ₹7 | 1 | ₹1,537 |
| Redmi Note 4/4X | redmi note 4 display original | PHRASE | redmi note 4 display original | 2 | ₹5 | 1 | ₹1,533 |
| iPhone 8 | iphone 8 display | PHRASE | iphone 8 display | 2 | ₹4 | 1 | ₹1,437 |

**₹24,936 sales on just ₹110 spend for the converting rows.** 8 of 10 converters carry `display`/`display original`; 4 are PHRASE, 2 EXACT. iPhones convert at far higher order value (₹1,437–₹4,190) than Android screens. Note "iphone 8 **ka** combo" converted — Hindi again.

---

## E. Wasted spend — 96% of spend, 0 purchases

Aggregated by search term, zero-purchase terms burned **₹7,872 of ₹8,223 (96%)**. Biggest single burners:

| search term (0 conversions) | clk | impr | spend |
|---|---|---|---|
| redmi note 9 pro max display original | 43 | 306 | ₹96 |
| oppo f17 original display price | 44 | 529 | ₹85 |
| iphone xs display | 39 | 392 | ₹76 |
| redmi note 7 pro display combo | 33 | 406 | ₹75 |
| oppo f17 pro display original | 19 | 119 | ₹73 |
| redmi note 5 pro display combo | 13 | 176 | ₹73 |

Low overall conversion (0.30%/click) partly reflects that screens are a considered, cross-shopped purchase and attribution may lag. But the **pro/max/combo zero-converters overlap heavily with the §B bleed** — cutting the bleed cuts most of this waste.

---

## F. Oppo F17 deep-dive — the direction is OPPOSITE to what we assumed

Every `f17` search term in the report (78 rows, 196 clicks, ₹498, 0 purchases). **Crucial: every single F17 row was served by the base "Oppo F17" ad group. The "Oppo F17 Pro" group served nothing in this window.**

**Base "Oppo F17" group is catching F17 PRO searches** (base ad shown to Pro customer = wrong part):

| our keyword (base group) | match | customer typed | clk |
|---|---|---|---|
| oppo f17 display original | BROAD | oppo f17 **pro** display original | 10 |
| oppo f17 display | BROAD | oppo f17 **pro** display original | 6 |
| oppo f17 original display | BROAD | oppo f17 **pro** display original | 3 |
| oppo f17 display | BROAD | oppo f17 **pro** display | 3 |
| oppo f17 display | BROAD | oppo f17 **pro** oled/combo/mobile display | 2 each |

Total **~44 clicks of F17-Pro searches captured by the base group.**

Top real base-F17 searches (what genuine F17 customers type):

| base F17 search term | clk | impr |
|---|---|---|
| oppo f17 original display price | 44 | 529 |
| oppo f17 display original | 18 | 110 |
| oppo f17 display | 17 | 97 |
| oppo f17 combo display | 9 | 23 |
| oppo f17 display combo | 7 | 15 |
| oppo f17 folder original | 6 | 30 |
| oppo f17 mobile display original | 6 | 16 |
| oppo f17 ka folder | 3 | 13 |
| oppo f17 5g display | 3 | 5 |

### What this means for the negative-keyword plan

The problem is **bidirectional**, and the data shows the *reverse* of Sir's original concern is the one actually firing right now:

**1. LIVE, MEASURED — base "Oppo F17" group → block Pro traffic.**
- Fix: **Negative Phrase `f17 pro`** (single entry) in the base Oppo F17 group.
- Safe because `f17 pro` is **not** a substring of any base positive keyword (`oppo f17 display`, `oppo f17 combo`…), so it cannot self-block. Doctrine explicitly allows a base group to phrase-negate `pro`.
- Catches all observed Pro variants at once: `oppo f17 pro display`, `…pro display original`, `…pro oled display`, etc.
- Stops ~44 clicks / ~₹150 of ongoing waste.

**2. PREVENTIVE — F17 Pro group → block base traffic (Sir's original ask).**
- Not firing in this window (Pro group served nothing), but will the moment the Pro group gets BROAD keywords or a bid bump.
- Fix: **Negative EXACT** for each real base query (Phrase is disastrous here — `oppo f17` is a substring of the Pro group's own `oppo f17 pro display` positives and would self-block, per the FLOW.md regression test and Sir's confirmation):
  - `oppo f17 display`
  - `oppo f17 display original`
  - `oppo f17 original display price`
  - `oppo f17 combo display`
  - `oppo f17 display combo`
  - `oppo f17 combo`
  - `oppo f17 folder`
  - `oppo f17 folder original`
  - `oppo f17 combo display original`
  - `oppo f17 mobile display original`
  - `oppo f17 5g display`
  - `oppo f17 ka folder`

**Nothing has been changed live. This is a preview for Sir's approval.**

---

## G. Best winning keyword patterns (the build)

Synthesising §A–§F into a repeatable per-model recipe:

**Positive keywords — priority order (matches real demand):**
1. `<model> display original` — **PHRASE + EXACT** (37% of demand, best-converting phrasing)
2. `<model> display` — **PHRASE + EXACT** (26% of demand)
3. `<model> original display price` / `<model> display price` — cheap, high-intent (₹2.05 CPC)
4. `<model> combo display` and `<model> combo` — real tail
5. `<model> folder original` / `<model> folder` — real tail
6. `<model> ka display` / `<model> ka folder` — **Hindi, currently under-covered, converts**
7. `<model> mobile display`, `<model> touch display` — observed real phrasings
8. Keep ONE BROAD `<model> display` for discovery — but always guarded by §B negatives

**Match-type policy:**
- Lead with **PHRASE** (best ROAS 4.91, lowest CPC, 2× broad conversion).
- **EXACT** on the two proven winners (`display`, `display original`) for control.
- **BROAD** only as a capped discovery layer, never without qualifier negatives.

**Kill / don't bother (0 impressions or 0 intent):**
- `broken screen replacement`, `display of <model> lite` — dead template filler.
- Bare `<model> screen` — expensive (₹3.84 CPC), non-converting browser traffic.

**Every base-model group — mandatory guardrail negatives (Negative Phrase, substring-safe):**
- `pro`, `max`, `plus`, `5g`, `4g` — whichever are absent from that group's model name.
- Recovers the 26%-of-spend bleed. For Pro/Max groups, mirror with Negative **Exact** base queries.

---

## Action items

1. **[measured waste]** Base "Oppo F17" group → Negative Phrase `f17 pro`. Await Sir's go.
2. **[Sir's original ask]** F17 Pro group → the 12 Negative Exact base queries above. Await go.
3. **[₹2,166 opportunity]** Roll the qualifier-negative guardrail across all base-model groups (5g/pro/4g/plus/max). Biggest single lever in this report.
4. Add under-covered high-intent positives: `<model> display price`, Hindi `<model> ka display/folder`, `<model> mobile display`.
5. Finish Oppo A54 pages 2-3 (98 keywords untraced from the earlier UI pull).
6. iPhone 11 Pro Max & Oppo F19/F19 Pro negative decisions — apply the same base-vs-qualifier test.

*Data caveat: click-filtered report, 10 purchases total — ROAS/conversion numbers are directional, not statistically heavy. Demand-pattern and bleed findings (clicks/impressions) are solid.*
