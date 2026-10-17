# Graphify — Mahika Ads Flow

**Tags:** `amazon-ads`, `ad-groups`, `compatible-family`, `negative-keywords`, `exact-vs-phrase`, `search-terms`, `mahika`

**Canonical:** [FLOW.md](FLOW.md)

**URL lock verified:** 2026-07-22 evening (Sir locked entry URLs)

---

## Canonical entry URLs (Sir 2026-07-22 evening)

| Role | ONLY landing URL |
|---|---|
| **Ads homepage** | `https://advertising.amazon.in/campaign-manager/all-campaigns?entityId=ENTITY37NJTG1VOHVTB` |
| **Normal Seller Central** | `https://sellercentral-europe.amazon.com/` |

**Hard entry rules:**

- Ads work: stay on `advertising.amazon.in` only. **Never** open `www.amazon.in` / retail `amazon.in`.
- SC work: use `sellercentral-europe.amazon.com` as the normal home Sir gave (not retail amazon.in).
- Prefer deep links from this URL LOCK after landing; campaign AG primary remains the ad-groups URL below.
- Login stuck → `specs/seller-central-flow/login-flow.md`; **never ask Sir to login manually**.

---

## URL LOCK

| Name | Purpose | Exact URL | Notes |
|---|---|---|---|
| **Ads homepage** | ONLY Ads landing (Sir-locked) | `https://advertising.amazon.in/campaign-manager/all-campaigns?entityId=ENTITY37NJTG1VOHVTB` | **Homepage row** — not bare root; domain note: `advertising.amazon.in` only |
| Ads domain (note) | Domain only — not a landing | `https://advertising.amazon.in` | Bare root OK as domain reminder; **do not** use as homepage |
| All campaigns list | Same as Ads homepage | `https://advertising.amazon.in/campaign-manager/all-campaigns?entityId=ENTITY37NJTG1VOHVTB` | Filter by name after land |
| Seller Central home | ONLY SC landing (Sir-locked) | `https://sellercentral-europe.amazon.com/` | Normal SC home; never retail amazon.in |
| SP campaigns list (alt) | Legacy/script entry | `https://advertising.amazon.in/cm/campaigns?entityId=ENTITY37NJTG1VOHVTB` | Redirects or resolves to campaign manager |
| **Reference campaign — ad groups** | Campaign overview + ad-group table | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups?entityId=ENTITY37NJTG1VOHVTB` | **Primary deep link** — skip nav |
| Campaign negative targeting | Sir-set off-category negatives | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/negative-targeting?entityId=ENTITY37NJTG1VOHVTB` | Do **not** change unless new bleed |
| Campaign settings | Budget, schedule, type | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/settings?entityId=ENTITY37NJTG1VOHVTB` | Screens-only SP manual |
| **Ad group: Oppo F19 / F19 Pro — products** | ASINs / ads tab | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A084559912FCQ11YW6QKN/ads?entityId=ENTITY37NJTG1VOHVTB` | Shared verified family; B0H8FKMJWD |
| **Ad group: Oppo F19 / F19 Pro — keywords + negatives** | Targeting tab (positives + ad-group negatives) | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A084559912FCQ11YW6QKN/targeting?entityId=ENTITY37NJTG1VOHVTB` | No separate negative URL at ad-group level |
| **Ad group: Oppo F19 / F19 Pro — search terms** | Search Term Report | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A084559912FCQ11YW6QKN/search-terms?entityId=ENTITY37NJTG1VOHVTB` | Export / iterate from data |
| **Ad group: Oppo F17 Pro — products** | ASINs / ads tab | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A04445372C07526DZXA0I/ads?entityId=ENTITY37NJTG1VOHVTB` | Existing group; F17 phrase-negative regression guardrail |
| **Ad group: Oppo F17 Pro — keywords + negatives** | Targeting tab | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A04445372C07526DZXA0I/targeting?entityId=ENTITY37NJTG1VOHVTB` | **Never** phrase-negate `f17` / `oppo f17` here |
| **Ad group: Oppo F17 Pro — search terms** | Search Term Report | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A04445372C07526DZXA0I/search-terms?entityId=ENTITY37NJTG1VOHVTB` | Base F17 group catches Pro traffic — see SEARCH_TERM analysis |
| **Ad group: IPhone 11 Pro Max — products** | ASINs / ads tab | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A08718921A1E5M04CWBET/ads?entityId=ENTITY37NJTG1VOHVTB` | **Blocked ASIN mix** — LCD B0FRT15V2G vs GX B0H8FHS4TV |
| **Ad group: IPhone 11 Pro Max — keywords + negatives** | Targeting tab | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A08718921A1E5M04CWBET/targeting?entityId=ENTITY37NJTG1VOHVTB` | Sir review before changes |
| **Ad group: IPhone 11 Pro Max — search terms** | Search Term Report | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A08718921A1E5M04CWBET/search-terms?entityId=ENTITY37NJTG1VOHVTB` | Negative decisions still open |
| **Ad group: Asus Zenfone Max M2 — targeting** | Keywords (Broad+Phrase+Exact) | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A08680473JXEFV7KTWPKK/targeting?entityId=ENTITY37NJTG1VOHVTB` | Fixed 2026-07-22 — Total 42 (14뿯½3) |
| **Ad group: Asus Zenfone Max M2 — negatives** | Negative targeting | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A08680473JXEFV7KTWPKK/negative-targeting?entityId=ENTITY37NJTG1VOHVTB` | Phrase: pro/plus (skip max — in own name) |
| **Ad group: Honor 7X (Black) — ads** | Products | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A020003114YZJSET85GCA/ads?entityId=ENTITY37NJTG1VOHVTB` | Enabled 2026-07-22 (existed Paused) |
| **Ad group: Honor 7X (Black) — negatives** | Negative targeting | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A020003114YZJSET85GCA/negative-targeting?entityId=ENTITY37NJTG1VOHVTB` | Phrase: pro/max/pro max/plus/5g/4g |
| **Ad group: Honor 7X (White) — ads** | Products | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A02297261MRLB24UL9RO4/ads?entityId=ENTITY37NJTG1VOHVTB` | Enabled 2026-07-22 (existed Paused) |
| **Ad group: Honor 7X (White) — negatives** | Negative targeting | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A02297261MRLB24UL9RO4/negative-targeting?entityId=ENTITY37NJTG1VOHVTB` | Phrase: pro/max/pro max/plus/5g/4g |
| **Ad group: Honor 8X** | Existing | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A09918911CAM3AZ763ZXP/ads?entityId=ENTITY37NJTG1VOHVTB` | Enabled prior session |
| **Ad group: Infinix Note 10** | Existing | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A07695821JLG1Q5C69P30/ads?entityId=ENTITY37NJTG1VOHVTB` | Enabled prior session |
| **Ad group: Oppo Reno 10 Pro Plus** | Created 2026-07-22 Phase 2 | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A061581414N6QPFYL3XRL/ads?entityId=ENTITY37NJTG1VOHVTB` | ASIN B0GKGGLF9F (CareOG); session `amazon-ads-2` |
| **Ad group: Oppo Reno 10 Pro Plus — targeting** | Keywords + negatives | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A061581414N6QPFYL3XRL/targeting?entityId=ENTITY37NJTG1VOHVTB` | BPE 뿯½1; Exact base insurance |
| **Ad group: OnePlus 10 Pro** | Created 2026-07-22 Phase 2 | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A02578802M6DXJYDGCTO2/ads?entityId=ENTITY37NJTG1VOHVTB` | ASIN B0GKGC5QDP (CareOG); session `amazon-ads-2` |
| **Ad group: OnePlus 10 Pro — targeting** | Keywords + negatives | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A02578802M6DXJYDGCTO2/targeting?entityId=ENTITY37NJTG1VOHVTB` | BPE 뿯½1; Exact base insurance |
| **Ad group: Oneplus 11R** | Existing (Paused) | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A05358022BVFRV0QXY5KC/ads?entityId=ENTITY37NJTG1VOHVTB` | Duplicate for plan create OnePlus 11R CareOG — left Paused |
| **Ad group: iPhone 14 Pro Max** | Created 2026-07-22 Phase 2 | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A03553021J04HCKA7PRBI/ads?entityId=ENTITY37NJTG1VOHVTB` | ASIN B0GKGNMQYY (LCD≈Incell); session `amazon-ads-2` |
| **Ad group: iPhone 14 Pro Max — targeting** | Keywords + negatives | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A03553021J04HCKA7PRBI/targeting?entityId=ENTITY37NJTG1VOHVTB` | BPE 뿯½1 (no lcd suffix); Exact base/pro insurance |
| **Ad group: Galaxy A32 — products** | ASINs / ads tab | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A091776017XH8Q480GEKN/ads?entityId=ENTITY37NJTG1VOHVTB` | **VERIFIED** LCD `B0FRSVSLH4` Delivering; CareOG+OLED WF **Paused** |
| **Ad group: Galaxy A32 — negatives** | Phrase + Exact 4g | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A091776017XH8Q480GEKN/negative-targeting?entityId=ENTITY37NJTG1VOHVTB` | Total **6**: Phrase pro/max/pro max/plus/5g + Exact `4g` |
| **Ad group: Galaxy A32 — targeting** | Keywords BPE @ ~Rs3 | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A091776017XH8Q480GEKN/targeting?entityId=ENTITY37NJTG1VOHVTB` | **VERIFIED** BPE @ ₹3 — Total **43** |
| **Ad group: Galaxy A31** | Existing Enabled | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A02810171EUNHAMIGCSCJ/ads?entityId=ENTITY37NJTG1VOHVTB` | Enabled prior/this session `amazon-ads-3` |
| **Ad group: Galaxy A10** | Existing Enabled | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A08727522R6N51EWF5W6Z/ads?entityId=ENTITY37NJTG1VOHVTB` | Enabled prior session |
| **Ad group: Galaxy J7 Prime (2016)** | Enabled 2026-07-22 | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A07077631NTH1V7TFJ6WV/ads?entityId=ENTITY37NJTG1VOHVTB` | Was Paused → Enabled this session `amazon-ads-3` |

### URL pattern (new ad groups)

```
https://advertising.amazon.in/cm/sp/campaigns/{CAMPAIGN_ID}/ad-groups/{AD_GROUP_ID}/{TAB}?entityId=ENTITY37NJTG1VOHVTB
```

| Tab path | UI |
|---|---|
| `ads` | Products / advertised ASINs |
| `targeting` | Positive keywords **and** ad-group negative keywords |
| `search-terms` | Search Term Report |

**IDs (locked):** campaign `A038001030A5E0IF4R8UV` 뿯½ entity `ENTITY37NJTG1VOHVTB`

---

## Account context

| Field | Value |
|---|---|
| Seller | Badeja Enterprises |
| Ads account | Sponsored ads, **India** |
| Entity ID | `ENTITY37NJTG1VOHVTB` |
| Reference campaign | `TL_EL_SPN_SG_Mobile Screens - Arun` |
| Campaign ID | `A038001030A5E0IF4R8UV` |
| Type | Sponsored Products — manual keyword targeting |
| Scope | Screens / display combos only (no batteries, housing, etc.) |

---

## Session rules

1. **Ads entry:** Land on Ads homepage `.../campaign-manager/all-campaigns?entityId=ENTITY37NJTG1VOHVTB` — then deep links. Stay on `advertising.amazon.in` only — **never** `www.amazon.in` / retail `amazon.in`.
2. **SC entry:** Normal SC home is `https://sellercentral-europe.amazon.com/` (Sir-locked) — never retail amazon.in.
3. **Browser:** Cursor in-editor visible browser or `user-agent-browser` session `amazon-ads` with `restore: true` — Sir must see the window.
4. **Auth:** Prefer saved cookies / restored session; do **not** loop re-login if session valid (header shows **Badeja Enterprises · Sponsored ads, India**).
5. **Navigation:** After Ads landing, open **deep links** from the URL LOCK table — do not click through campaign manager unless IDs unknown.
6. **Seller Central:** Login lane is separate (`specs/seller-central-flow/login-flow.md`); Ads may open from SC but URLs must stay on `advertising.amazon.in`.

---

## Fast path

1. Land on **Ads homepage** (all-campaigns URL above), then open **campaign ad-groups** URL (table row “Reference campaign — ad groups”).
2. Confirm account header = Badeja Enterprises · India · correct campaign name.
3. Jump to target ad group **`/ads`**, **`/targeting`**, or **`/search-terms`** URL — skip table clicks when ID is locked.
4. For campaign-level off-category negatives only → **campaign negative targeting** URL (read-only unless Sir approves new bleed).
5. After edits → re-open same deep link and verify products, keywords, negatives match approved preview.

---

## Hard ops rules

- **Archive PROHIBITED** — Enable/Pause only (ad groups, products, keywords). Wrong ASIN → Pause, never Archive.
- **Ads domain only** — never open `www.amazon.in` / retail `amazon.in` for Ads work.
- **Login stuck** → follow `specs/seller-central-flow/login-flow.md` (agent S1→S7 + `otp-watch --force`); **never ask Sir to login**.

## Known issues (do not forget)

| Issue | Detail |
|---|---|
| **iPhone 11 Pro Max ASIN mix** | Had LCD `B0FRT15V2G` + Oppo F19 `B0H8FKMJWD` mixed with GX `B0H8FHS4TV` — Pause wrong ASINs (no Archive); GX may show "Price cannot be found" 뿯↽ keep group Paused until eligible |
| **Oppo F17 Pro phrase-negative regression** | `oppo f17` / `f17` Negative phrase **must not** return — blocks own `oppo f17 pro` traffic; use scoped Negative Exact for base queries instead |
| **Oppo F19 / F19 Pro** | Verified shared family — both models in positives; no mutual negatives |
| **Base Oppo F17 vs F17 Pro bleed** | Base group may catch Pro searches; see `SEARCH_TERM_ANALYSIS_2026-07-20.md` |

---

## Communities

| Community | Key nodes |
|---|---|
| Visible access | in-editor browser, login/OTP, seller account, campaign |
| Evidence gate | category, title/details, bullets, compatible-model proof |
| Family design | verified compatible-part family, grouping, duplicate check |
| Targeting | positive keywords, match types, sibling bids |
| Negative safety | campaign off-category terms, model siblings, substring test, Exact alternative |
| Operations | preview, create, post-create verification, rollback, Search Term Report |

## Critical semantic edges

- `listing_evidence` 뿯↽ `verified_compatible_family`
- `verified_compatible_family` 뿯↽ `one_ad_group`
- `own_model_substring_test` 뿯↽ `reject_negative_phrase`
- `unsupported_base_query` 뿯↽ `scoped_negative_exact`
- `shared_compatible_models` 뿯↽ `positive_keywords`
- `search_term_report` 뿯↽ `evidence_based_iteration`

## Guardrail examples

- Redmi Note 8 vs Note 8 Pro: user-research input; verify before live use.
- Oppo F17 Pro: `f17` Phrase negative is a regression case because it blocks own Pro phrase.
- Oppo F19/F19 Pro: verified shared family means both positives and no mutual negatives.
- iPhone 11 Pro: `max` can be a Phrase negative when Max is verified unsupported.

## Regenerate

```powershell
cd "C:\Projects\Amazon Systems Design"
# /graphify agent --update
```

Output: repo-root `graphify-out/` (gitignored).
⌊‣桐獡⁥′牣慥整⁳뿯₽灏潰⼠传敮汐獵⼠椠桐湯⁥㈨㈰ⴶ㜰㈭ⰲ愠慭潺⵮摡⵳⤲ਊ⁼摁朠潲灵簠䄠⁇䑉簠䄠䥓⁎獵摥簠传瑵潣敭簠簊ⴭ簭ⴭ簭ⴭ簭ⴭ簭簊传灰⁯敒潮ㄠ‰牐⁯汐獵簠䄠㘰㔱ㄸㄴ临儶䙐䱙堳䱒簠䈠䜰䝋䱇㥆⁆⁼牣慥整⁤੼⁼湏健畬⁳〱倠潲簠䄠㈰㜵㠸㈰㙍塄奊䝄呃㉏簠䈠䜰䝋㕃䑑⁐⁼牣慥整⁤੼⁼偩潨敮ㄠ‴牐⁯慍⁸⁼ぁ㔳㌵㈰䨱㐰䍈䅋倷䉒⁉⁼あ䭇乇免奙簠挠敲瑡摥簠簊传敮汰獵ㄠ刱簠䄠㔰㔳〸㈲噂剆ざ塑㕙䍋簠⠠硥獩楴杮 ⁼畤汰捩瑡⁥慰獵摥簠簊䤠桐湯⁥ㄱ倠潲䴠硡簠䄠㠰ㄷ㤸ㄲㅁ㕅き䌴䉗呅簠⠠硥獩楴杮 ⁼敬瑦倠畡敳⁤楦彸楦獲⁴੼⁼灏潰䘠㜲簠붿簠䈠䘰兌㥈卄⁊⁼慦汩摥传䕌⁄潮⁴湩䄠獤椠癮湥潴祲簠

---

## Batch D — Galaxy / Redmi / Mi / Poco (2026-07-22)

| Stock | Ad group | ID | Result |
|---|---|---|---|
| Galaxy A32 4G Incell | Galaxy A32 | `A091776017XH8Q480GEKN` | **VERIFIED** products+BPE+negs 2026-07-22 |
| Galaxy J7 2016 Incell | Galaxy J7 Prime (2016) | `A07077631NTH1V7TFJ6WV` | Enabled (existed) |
| Galaxy A31 Incell | Galaxy A31 | `A02810171EUNHAMIGCSCJ` | Enabled (existed) |
| Galaxy A10 Incell | Galaxy A10 | `A08727522R6N51EWF5W6Z` | Enabled (existed) |
| Galaxy J7 Next Incell | Galaxy J7 Nxt (Black) | `A04159192QYI5D4OLG8QM` | Enabled (existed; WRONG_QUALITY Amoled) |
| Galaxy J7 2015 Incell | Galaxy J7 (2015) | `A05291172Z4EU6DFWR38C` | Enabled (existed; WRONG_QUALITY Amoled) |
| Galaxy J7 Max Incell | Galaxy J7 Max (2017) (Black) | `A071651134180XJ29G62W` | Enabled (existed; WRONG_QUALITY Amoled) |
| Galaxy A73 OLED | — | — | skipped_quality_conflict LCD/TFT |
| Galaxy S21 FE OLED | — | — | skipped_quality_conflict LCD/TFT |
| Galaxy S20 FE WF OLED | — | — | **failed_skip** Inactive `B0GKGVNXNL` / `B0F3JR7BQ9` |
| Mi 11X OLED / Incell | — | — | **failed_skip** Inactive listings |
| Mi A3 Incell | — | — | **still_blocked** Active `B0BZT5V9T8` — need Ads login |
| K20 Incell | — | — | **still_blocked** Active `B0BYVP2LWV` — need Ads login |
| Redmi Note 10T WF | — | — | skipped_quality_conflict |
| Redmi 13 Pro Plus WF | — | — | skipped_quality_conflict |
| Poco X3 Incell | — | — | skipped_quality_conflict (X3 vs X3 GT) |

A32 **VERIFIED** live. S20 FE **failed_skip**. A3/K20 need Ads login. Archive never used. Campaign negatives untouched.
| **Ad group: Galaxy A30s** | Exists Enabled | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A088091616JUNTR4QH4A3/ads?entityId=ENTITY37NJTG1VOHVTB` | amazon-ads-3 reuse |

| **Ad group: Redmi 10 Power** | Exists Enabled | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A05907496B6DKCPQISY2/ads?entityId=ENTITY37NJTG1VOHVTB` | amazon-ads-3 reuse |

| **Ad group: Redmi Note 6 Pro** | Exists Enabled | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A04782503ALR6BPUN8J5O/ads?entityId=ENTITY37NJTG1VOHVTB` | amazon-ads-3 reuse |

| **Ad group: Redmi Note 7/7s/7 Pro** | Exists Enabled | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A02577102Z1S9V7SI2BNU/ads?entityId=ENTITY37NJTG1VOHVTB` | amazon-ads-3 reuse; shared family |

## Batch E — Realme + Vivo create queue (2026-07-22, session amazon-ads-1 / CDP)

| Stock / AG | ID | Result |
|---|---|---|
| Realme C67 | `A005394925BGXDRVMULPG` | **exists_enabled** — skip create |
| Realme C33 | `A07067373T44W28UTF7QN` | **FIXED** Phrase-only → BPE keywords Save Total **42** @ ~Rs3; ASIN `B0FRSWZQF1` (Ineligible/price missing — monitor) |
| Realme C21 | `A00404552J91ZEFEKVL01` | **exists** — verified; BPE keywords Save Total **42** @ ~Rs3 |
| Realme 11 Pro CareOG | — | **failed_create_wizard** (listing Inactive; SPAdGroupSettings name field not hydrated) |
| Realme 13 Pro CareOG | — | **failed_create_wizard** (listing Inactive) |
| Realme 3 Pro Frame | — | **failed_create_wizard** |
| Vivo X70 Pro Plus CareOG | — | **failed_create_wizard** (listing Inactive) |
| Vivo V11 Pro CareOG | — | **failed_create_wizard** (listing Inactive) |
| Vivo V15 CareOG | — | **failed_create_wizard** (wizard stuck / no create btn) |
| Vivo X80 CareOG | — | **failed_create_wizard** (listing Inactive) |

### Deep links

| Ad group | URL |
|---|---|
| Realme C33 targeting | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A07067373T44W28UTF7QN/targeting?entityId=ENTITY37NJTG1VOHVTB` |
| Realme C21 targeting | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A00404552J91ZEFEKVL01/targeting?entityId=ENTITY37NJTG1VOHVTB` |
| Realme C67 ads | `https://advertising.amazon.in/cm/sp/campaigns/A038001030A5E0IF4R8UV/ad-groups/A005394925BGXDRVMULPG/ads?entityId=ENTITY37NJTG1VOHVTB` |

Archive: never used. Campaign negatives untouched.
Blocker: Ads `/cb/.../adGroups` create wizard microfrontend often does not mount `#sspa_sp_adGroupSettings_adGroupName` under automation — resume creates manually or after UI fix.