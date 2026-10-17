# Keyword & negative-keyword patterns (Mahika Ads)

**Relationship to [FLOW.md](FLOW.md):** FLOW.md is *process* doctrine — evidence gate, family verification, preview/approve, rollback. This file is *content* doctrine — which actual keywords and negatives to type once FLOW.md says a group is safe to build. Use both together: FLOW.md answers "is this group allowed to exist and in what shape," this file answers "what keywords go in it."

**Goal (Sir, 2026-07-20):** minimum leakage, maximum ROAS, maximum CTR, optimized clicks. Every rule below exists to serve one of those four.

**Source data:** `TL_EL_SPN_SG_Mobile Screens - Arun` (`A038001030A5E0IF4R8UV`), Search Term Report `Report_-_07_20_2026T01_28_48.csv` (1,821 rows, 83 ad groups, 1,428 unique customer search terms, 3,359 clicks, 10 purchases) + live top-10 ad-group keyword pull. Full workings in [SEARCH_TERM_ANALYSIS_2026-07-20.md](SEARCH_TERM_ANALYSIS_2026-07-20.md) and [TOP10_KEYWORD_ANALYSIS_2026-07-20.md](TOP10_KEYWORD_ANALYSIS_2026-07-20.md).

**Caveat:** only 10 purchases total in the sample — treat ROAS/conversion numbers as directional, not final. Click/impression demand-pattern and bleed findings are the solid part; re-verify against a bigger Search Term Report before treating any single number as gospel.

---

## 1. Positive keyword pattern — data-driven default for any new `<model>` group

Ranked by actual customer demand (% of clicks), highest first. Build every new ad group's keyword set in this order:

| Priority | Keyword suffix on `<model>` | % of demand | Match type | Why |
|---|---|---|---|---|
| 1 | `<model> display original` | 37.4% | **Phrase + Exact** | Single biggest demand bucket, best-converting phrasing |
| 2 | `<model> display` | 25.8% | **Phrase + Exact**, one **Broad** for discovery | 2nd biggest bucket; Broad only with qualifier negatives active (§2) |
| 3 | `<model> display price` / `<model> original display price` | 4.3% | Phrase | Cheapest CPC (₹2.05) — high-intent price-checkers |
| 4 | `<model> combo display`, `<model> combo` | 5.9% + 3.5% | Phrase | Real secondary demand |
| 5 | `<model> folder`, `<model> folder original`, `<model> folder display` | 6.9% + tail | Phrase | Real secondary demand, esp. Oppo-family listings |
| 6 | `<model> ka display`, `<model> ka folder` | 1.4% | Phrase | **Hindi vernacular — real and converts** (e.g. "iphone 8 ka combo" converted). Under-covered in most existing groups — add proactively. |
| 7 | `<model> mobile display`, `<model> touch display` | ~2.2% combined | Phrase | Observed real phrasings not in the old template |
| 8 | `<model> lcd` | 1.5% | Broad | Low volume but converted at least once (iPhone 13 Pro) |

**Do not bother / kill-list** (present in the old template, proven dead weight — 0 impressions or 0 conversions across every group checked):
- `<model> broken screen replacement`
- `display of <model> lite`
- Bare `<model> screen` alone — expensive (₹3.84 CPC), zero conversions in the sample; browsers, not buyers.

**Match-type allocation policy** (from §D of the search-term analysis — PHRASE wins on every axis):

| Match type | Share of clicks | CPC | Conversion rate | ROAS |
|---|---|---|---|---|
| **Phrase** | 22.3% | **₹2.20 (best)** | **0.53% (best)** | **4.91 (best)** |
| Broad | 57.2% | ₹2.57 | 0.26% | 2.68 |
| Exact | 19.8% | ₹2.38 | 0.15% | 2.29 |

**Rule of thumb:** lead with Phrase for every proven-demand suffix. Add Exact only on the top 1-2 highest-converting exact strings for control/bid isolation. Keep at most one Broad per group (on plain `<model> display`) purely for discovery, and only if the qualifier-negative guardrail (§2) is already in place — unguarded Broad is what causes the cross-model bleed below.

---

## 2. Negative keyword pattern — leakage prevention

### 2a. Broad-match mechanics (why leakage happens — know this before writing any negative)

A Broad-match keyword fires when the search term contains **every word** in the keyword, in any order, with extra words allowed anywhere. So:

- Keyword `oppo f17 display` (Broad) **matches** search `oppo f17 pro display` (all 3 words present, "pro" is just extra) → **base ad shown to a Pro searcher.**
- Keyword `oppo f17 pro display` (Broad) does **not** match search `oppo f17 display` ("pro" is missing from the search) → Pro ad is naturally NOT shown to a base searcher via Broad.

**Consequence:** the "base group leaks into qualified/Pro/Max searches" direction is the live, common leak. The reverse ("Pro group shows to base searchers") is naturally blocked by Broad's own matching logic — but treat it as an insurance gap, not a non-issue, because Amazon can loosen Broad matching over time and Phrase/Exact keywords on the Pro side don't get this protection at all.

### 2b. Universal base-group guardrail (the ₹2,166 / 26%-of-spend fix)

Every **base-model** ad group should carry **Negative Phrase** on every qualifier that is absent from its own model name:

- `pro`, `max`, `pro max`, `plus`, `5g`, `4g` — pick whichever ones the base model's name does NOT contain.

**Safety check (mandatory, from FLOW.md §5):** confirm the qualifier is not a substring of the group's own positive keywords before adding. `pro`/`max`/`5g`/`4g`/`plus` are safe for a true base model (e.g. plain "Oppo F17", "Redmi 12") because none of those tokens appear in the base group's own keyword text.

**Measured impact:** in the 2026-07-20 sample, qualifier bleed alone accounted for 416 rows / 745 clicks / ₹2,166 spend (26.3% of total campaign spend) with only 1 purchase attributed to it. This is the single biggest lever in the whole analysis — roll it out to every base-model group, not just the one under active discussion.

| Qualifier typed by customer, missing from our keyword | Clicks | Spend |
|---|---|---|
| `5g` | 301 | ₹741 |
| `pro` | 207 | ₹768 |
| `4g` | 82 | ₹238 |
| `max` / `pro max` | 67 | ₹155 |
| `plus` (incl. combos) | ~75 | ~₹210 |

### 2c. Pro/Max-group insurance (base-query blocking)

For a **Pro/Max/Plus** group that must not show to base-model searchers:

- **Never** Negative Phrase the base model name or number alone (e.g. `f17`, `note 8`) — it is a substring of the group's own positive phrase (`f17 pro`, `note 8 pro`) and will self-block the group's own traffic. This is the documented Oppo F17 Pro regression (FLOW.md §6).
- Instead, enumerate the base group's **actual observed high-traffic search strings** and add each as **Negative Exact**. Exact only blocks that literal full string, so it can never self-block a longer Pro phrase. Build the list from the base group's own Search Term Report — see the worked Oppo F17 example in [SEARCH_TERM_ANALYSIS_2026-07-20.md §F](SEARCH_TERM_ANALYSIS_2026-07-20.md#f-oppo-f17-deep-dive--the-direction-is-opposite-to-what-we-assumed) for the exact 12-query pattern.
- Treat this as **insurance**, not the primary leak — per §2a, Broad's own word-matching logic already mostes of this direction. Still worth doing because Phrase/Exact keywords on the Pro side get no such protection, and Amazon's Broad definition can loosen.

### 2d. Exact-vs-Phrase decision table (canonical — see also FLOW.md §5)

| Group type | Candidate negative | Type | Verdict |
|---|---|---|---|
| Base model | `pro`, `max`, `5g`, `4g`, `plus` (absent from own name) | Phrase | Safe, do it everywhere — §2b |
| Pro/Max model | bare base name/number (`f17`, `note 8`) | Phrase | **Unsafe — never.** Self-blocks own traffic. |
| Pro/Max model | full base search strings (`oppo f17 display`, `oppo f17 combo`…) | Exact | Safe alternative — §2c |
| Shared verified family (e.g. F19/F19 Pro) | either model name | any | **Never** — they're the same family, not siblings to exclude |

---

## 3. New ad group — keyword build checklist

Once FLOW.md's evidence gate + family verification has cleared a new ad group:

1. Add positives from §1, in priority order, using the match-type mix in the policy table.
2. Add Hindi "ka" variants (§1 row 6) — usually forgotten, real demand.
3. Skip the kill-list entirely — don't waste setup time on dead suffixes.
4. If this is a **base model**: add the §2b qualifier guardrail immediately, same session as creation — don't wait for bleed to show up in a report first.
5. If this is a **Pro/Max/Plus model** with a sibling base group already live: pull the base group's Search Term Report, build the §2c Negative Exact list from its real top queries, apply the substring safety check (§2d) before adding anything as Phrase.
6. Preview per FLOW.md before submitting live. Nothing in this file overrides FLOW.md's PREVIEW/APPROVE gate.

## 4. Maintenance

Refresh this file whenever a new Search Term Report is pulled and analyzed — update the demand percentages in §1 and the bleed numbers in §2b if they've shifted materially. Keep old dated analysis docs (like the 2026-07-20 ones) as provenance; this file should always reflect the **latest** consolidated pattern, not a point-in-time snapshot.

**Last updated:** 2026-07-20, from the first full Search Term Report pull for this campaign.
