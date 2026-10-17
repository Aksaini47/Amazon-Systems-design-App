# Ads progress — 2026-07-31 (K20 verify + RV reconcile + V15 attempt)

**Campaign:** TL_EL_SPN_SG_Mobile Screens - Arun (`A038001030A5E0IF4R8UV`) · entity `ENTITY37NJTG1VOHVTB`
**Session:** agent-browser `ads-sso` · Badeja / India (SC cookie SSO)
**Updated:** 2026-07-31 ~02:20 IST

## Ads done this pass

| Priority | Result | ID / notes |
|---|---|---|
| **1 Mi A3** | skip recreate | `A0237552245ODQ3Z08K5O` · `B0FRSX7288` Ineligible — listing/price fix. Not Archived. |
| **2 Redmi K20** | **VERIFIED** | `A02851655NMF3GRW8X4R` · LCD `MIK20`/`B0FRSYCY2W` Ineligible; kw **156** base+pro; Phrase negs max/pro max/plus/5g/4g (**no Phrase pro**). |
| **3 Realme/Vivo** | **reconciled + ASIN checks** | Most AGs already live (IDs below). Live ASINs often `B0FRS*` (plan ASINs stale). |
| **4 Vivo V15** | **create_blocked** | Wizard: product CareOG `V15CARE`/`B0FRSX29JG` (OOS) Added; BPE keywords staged; Create failed — empty/group bids + Phrase `4g`/`plus` junk-query modal. Browser then CDP timeout. |

### Realme/Vivo live ASINs (verified)

| AG | ID | Live ASIN(s) | Title note |
|---|---|---|---|
| Realme 7 Pro | `A022568729OX5U6B7H6A` | `B0FRSZMXD5` | LCD 7 Pro — priced OK |
| Realme 7i | `A05601153KWG4QDC0T7GU` | `B0FRSVD92Q` | Ineligible price |
| Realme 8 | `A07680621AJNOC1F9CHBW` | `B0FRSZXB9S` + `B0FRSYL2BH` | **4G LCD + 5G CareOG already on same AG** |
| Vivo T1 (2022) | `A08623972SG26AMSUG7C5` | `B0FRSXKYT4` | 2022 CareOG — queue 2021 may still need AG |
| Vivo T2x | `A06419922EIQG4C52VS1X` | `B0FRSWZZZV` | CareOG Ineligible |
| Vivo Y22/Y22s | `A012677278Z93VLIHH4R` | `B0FRSVSZ3R` + `B0FRSY39PX` | CareOG present (+ 2nd ASIN) |
| Also name-found | 8i `A08198052V4MJ4GDUCRVH`, 9 `A023145030JDVP3J8JYB`, 9i `A03911801KTXP3G12EKE`, Y33s `A04462871VX5R6AAFJ6DF` | — | ASIN pull not finished |

Archive: **never used**. Campaign negatives: **untouched**.

## Blocker (STOP)

`agent-browser` CDP **timeout / connection failed** (`os error 10060`) during Vivo V15 create. Shell also briefly died earlier (`STATUS_DLL_INIT_FAILED`).

**Auth tip:** `--state ads-from-sc.json` (SC cookies) → Ads homepage works without OTP.

## Remaining (next agent)

1. Relaunch Ads (`ads-from-sc.json` / otp-watch).
2. Finish **Vivo V15** create: Custom bid ₹3 **before** Add keywords; skip Phrase `4g`/`5g`/`plus` in wizard (add `pro`/`max`/`pro max` after create on AG page); product `B0FRSX29JG`.
3. Decide T1 2021 CareOG vs existing T1 2022.
4. SC eligibility fixes (Mi A3, K20, many Ineligible).
5. Apple / MIX queue.
