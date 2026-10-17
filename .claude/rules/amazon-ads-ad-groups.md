# Amazon Ads - verified compatible-part families

Hard rule (2026-07-19). Cursor rule: `.cursor/rules/amazon-ads-ad-groups.mdc`.

## Ad group structure

- One ad group = one **verified compatible-part family**, not necessarily one printed model name.
- Multiple model names may share one ad group only when the listing title/details and bullet points explicitly confirm the same part is compatible across every named model.
- Include model-specific keywords for every explicitly confirmed compatible model.
- Similar names, successor relationships, and assumptions are not compatibility evidence.
- Oppo F17 and Oppo F17 Pro remain separate unless title/details and bullets explicitly confirm shared compatibility.
- **OnePlus 10 Pro / OnePlus 11 confirmed same part (Sir, 2026-08-22).** Sell OnePlus 11 stock under the existing "OnePlus 10 Pro" ad-group/listing — do not create a separate OnePlus 11 ad-group. Sir's own physical-parts confirmation, not an assumption from naming.
- Screens-only campaigns contain screens only; never mix batteries or other categories.
- Before creation, verify compatibility from listing title/details and listing bullet points where available.
- If evidence conflicts or is missing, keep products separate or stop for review.
- Before creation, check the campaign for duplicates by ASIN, verified family, and ad-group name.
- **Model is the grouping key — color/quality/frame are not.** One ad group per model; every listing for that model (any screen quality, any color, with-frame or non-frame) goes in as an ad inside that same ad group, not a separate one. Confirmed by Sir 2026-08-09 (Honor 7X case: physical stock is Black, and even though the account currently has two ad-groups — "Honor 7X (Black)" and "Honor 7X (White)" — new/matched listings should route by model into the single applicable ad-group, not get split further by color/quality when creating going forward).
- **Archive is PROHIBITED for ad groups, ads/products, and (positive) keywords.** Allowed: **Enable** / **Pause** only. Wrong ASINs → Pause them; do not Archive.
- **Negative keywords are the one exception — Archive them freely.** Confirmed via live UI recon (2026-08-15): the Negative targeting tab's Bulk actions menu offers only "Archive" for a negative-keyword row — there is no separate Remove/Delete control and no Enable/Pause state for negatives at all. The original blanket rule (2026-07-19) was written before this was confirmed, out of caution; Sir removed the negatives clause once the mechanism was verified live. Revisit/tighten this note later per Sir.

## Negative keywords

### Campaign-level negatives

- Already set by Sir — **do NOT change** unless new search-term data appears.
- Current: `battery`, `housing`, `body`, `screenguard`, `screen protector` (Negative phrase) — leave as-is.
- Logic: block off-category terms that look similar to our keywords but mean different products (junk traffic).
  - Example: "iphone 11 combo screen battery" → customer wants battery too; our product is screen-only.
  - Example: "iphone 11 screen protector" → "screen" word overlap but protector ≠ display replacement.
- Only add new campaign negatives later if new off-category bleed appears in data.

### Ad-group-level negatives = model-centric

- Based on **verified compatible models** from listing title + bullet points (not assumptions).
- **Negative phrase blocks searches containing that phrase.** NEVER negative-phrase a term that is a substring of the group's own positive model phrase (e.g. `f17` in F17 Pro or `note 8` in Note 8 Pro), because it can block own traffic.
- A base-model group may phrase-negate unsupported qualifiers such as `pro`, `max`, or `pro max` when they are absent from every supported model name.
- A Pro/Max group should block base-only intent with carefully scoped **Negative Exact** terms, then monitor Search Terms.
- Model-code negatives require proof that the code belongs exclusively to the unsupported sibling.
- Examples of logic:
  - iPhone 11 Pro does NOT support iPhone 11 Pro Max → `max` / `11 pro max` may be Negative phrase because `max` is absent from the own model
  - In an iPhone 11 (non-Pro) group: `pro`, `max`, `pro max` style combinations go as Negative phrase
- Always verify from listing compatible-model data / bullets first, THEN set negatives accordingly.
- Shared compatible family (e.g. Oppo F19/F19 Pro confirmed on same listing): do NOT negate each other; include both in positive keywords.
- Regression test: Oppo F17 Pro must not have `oppo f17` or `f17` Negative phrase; use specific Negative Exact base queries if verified and needed.

## Redmi Note 8 research example

- Screen/combo differences and model codes are user-provided research inputs; verify against current listing/manufacturer data before live use.
- If incompatibility is verified, Note 8 base may phrase-negate `pro`, `note 8 pro`, and `note 8pro`.
- Note 8 Pro must not phrase-negate `note 8`; scoped Negative Exact candidates are `redmi note 8` and `note 8`.
- Verify before use: possible Pro code `m1906g7i`; possible base codes `m1908c3jg`, `m1908c3jh`, `m1908c3ji`.
- Monitor Search Terms for Note 8T and Note 8 2021.

## Reference campaign

`TL_EL_SPN_SG_Mobile Screens - Arun` — Sponsored Products, manual keywords, screens category only.

## Canonical entry URLs (Sir 2026-07-22)

- **Ads homepage ONLY:** `https://advertising.amazon.in/campaign-manager/all-campaigns?entityId=ENTITY37NJTG1VOHVTB`
- **Normal SC home ONLY:** `https://sellercentral-europe.amazon.com/`
- Ads work: `advertising.amazon.in` only — **never** retail `www.amazon.in` / `amazon.in`
- Prefer GRAPHIFY deep links after landing; login stuck → `specs/seller-central-flow/login-flow.md` (never ask Sir to login)

## Canonical workflow

`agent/Graphs & workflows/mahika-ads-flow/FLOW.md`
