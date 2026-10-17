"""Match NEW office stock audit (2026-08-22, Gemini-generated) vs the FULL All
Listings Report (Active+Inactive+OOS), pulled 2026-08-08 (~2 weeks old -
title/SKU pairing should still be accurate, qty/status may have drifted;
flag to Sir before trusting OK/OUT_OF_STOCK split as live-current).

Stock source: catalog-builder/amazon-reports/_master_inventory_2026-08-22_gemini.txt
  (office physical-stock audit, stamp INV-22082026-0138, 22-AUG-2026 01:38 AM IST)
Listings: catalog-builder/amazon-reports/all_listings_2026-08-08.tsv

Adapted from stock_vs_all_listings_2026-08-07.py - only STOCK_FILE/OUT_CSV
changed. All matching logic (incl. the clean-match + TFT-equivalence fixes)
is unchanged - see [[project_matcher_false_positive_fix]] memory.

Classification (4-way):
  MISSING       - no listing exists for this model/brand at all, any status
  QUALITY_GAP   - a listing exists (any status) but none match stock's screen/quality
  OUT_OF_STOCK  - a correctly-quality-matched listing exists but qty=0 or status != Active
  OK            - a correctly-quality-matched, qty>0, Active listing exists
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STOCK_FILE = ROOT / "_master_inventory_2026-08-22_gemini.txt"
LISTINGS_FILE = ROOT / "all_listings_2026-10-02.tsv"
OUT_CSV = ROOT / "stock_vs_all_listings_report_2026-08-22.csv"

BRAND_KEYWORDS = [
    "REALME", "VIVO", "OPPO", "ONEPLUS", "APPLE", "SAMSUNG",
    "XIAOMI", "REDMI", "POCO", "MIX", "MOTO", "HONOR",
    "NOKIA", "ASUS", "NOTHING", "INFINIX",
]

BRAND_ALIASES = {
    "XIAOMI/REDMI/POCO": ["XIAOMI", "REDMI", "POCO"],
    "XIAOMI": ["XIAOMI", "REDMI", "POCO"],
    "REDMI": ["XIAOMI", "REDMI", "POCO"],
    "POCO": ["XIAOMI", "REDMI", "POCO"],
    "MIX": ["INFINIX", "HONOR", "NOKIA", "MOTO", "ASUS", "NOTHING"],
}

MIX_SUB_BRAND = [
    (r"\bhonor\b", "HONOR"),
    (r"\bnokia\b", "NOKIA"),
    (r"\bmoto\b|\bmotorola\b", "MOTO"),
    (r"\basus\b", "ASUS"),
    (r"\bnothing\b", "NOTHING"),
    (r"\binfinix\b", "INFINIX"),
]

BRAND_TITLE_TOKENS = {
    "APPLE": ["apple iphone", "iphone"],
    "SAMSUNG": ["samsung galaxy", "galaxy", "samsung"],
    "ONEPLUS": ["oneplus"],
    "OPPO": ["oppo"],
    "VIVO": ["vivo"],
    "REALME": ["realme"],
    "XIAOMI/REDMI/POCO": ["xiaomi", "redmi", "poco", "mi "],
    "HONOR": ["honor"],
    "NOKIA": ["nokia"],
    "MOTO": ["moto", "motorola"],
    "ASUS": ["asus"],
    "NOTHING": ["nothing"],
    "INFINIX": ["infinix"],
}


def parse_stock_quality(name: str):
    nl = name.lower()
    if "oled" in nl or "amoled" in nl:
        screen = "OLED"
    elif "incell" in nl:
        screen = "Incell LCD"
    elif "tft" in nl:
        screen = "TFT LCD"
    elif "lcd" in nl:
        screen = "LCD"
    else:
        screen = "Not Specified"

    if "careog" in nl:
        quality = "CareOG"
    elif "frame" in nl or "with frame" in nl or " wf " in nl:
        quality = "With Frame"
    else:
        quality = "Standard"
    return screen, quality


def parse_listing_quality(title: str):
    t = title.lower()
    if "super oled" in t or "amoled" in t or ("oled" in t and "lcd" not in t and "incell" not in t):
        screen = "OLED"
    elif "incell" in t:
        screen = "Incell LCD"
    elif "tft" in t:
        screen = "TFT LCD"
    elif "lcd" in t:
        screen = "LCD"
    else:
        screen = "Not Specified"

    has_careog = "careog" in t
    has_frame = "with frame" in t or "(with frame)" in t or " wf " in t
    if has_careog and has_frame:
        quality = "CareOG+With Frame"
    elif has_careog:
        quality = "CareOG"
    elif has_frame:
        quality = "With Frame"
    else:
        quality = "Standard"
    return screen, quality


def screen_match(stock_screen, listing_screen):
    # Project rule (.claude/rules/amazon-ads-ad-groups.md, via MASTER_VS_LISTINGS_AUDIT):
    # Incell ~ LCD ~ TFT are the same grade; only OLED/AMOLED is a distinct grade.
    LCD_GROUP = ("Incell LCD", "LCD", "TFT LCD")
    if stock_screen == listing_screen:
        return True
    if stock_screen in LCD_GROUP and listing_screen in LCD_GROUP:
        return True
    if stock_screen == "Not Specified":
        return True
    return False


def quality_grade_compatible(stock_quality, listing_quality):
    if stock_quality == listing_quality:
        return True
    if listing_quality == "CareOG+With Frame" and stock_quality in ("CareOG", "With Frame"):
        return True
    return False


def quality_match(stock_screen, stock_quality, listing_screen, listing_quality):
    return screen_match(stock_screen, listing_screen) and quality_grade_compatible(
        stock_quality, listing_quality
    )


def parse_stock():
    lines = STOCK_FILE.read_text(encoding="utf-8").splitlines()
    stock, brand = [], ""
    for line in lines:
        s = line.strip()
        if not s or s.lower() in ("actual stock", "master inventory"):
            continue
        if s.isupper() and any(b in s for b in BRAND_KEYWORDS):
            brand = s.replace(" ", "")
            continue
        if not brand:
            continue
        qty_m = re.search(r" - (\d+)(?: QTY)?$", s)
        qty = int(qty_m.group(1)) if qty_m else 1
        name = re.sub(r" - \d+(?: QTY)?$", "", s).strip()
        screen, quality = parse_stock_quality(name)
        stock.append({
            "brand": brand, "name": name, "qty": qty,
            "screen": screen, "quality": quality,
        })
    return stock


def parse_listings():
    """Read the RAW Amazon 'All Listings Report' (tab-delimited).

    Real Amazon columns used: item-name, seller-sku, asin1, quantity, status.
    """
    rows = []
    with LISTINGS_FILE.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for rec in reader:
            title_raw = (rec.get("item-name") or "").strip()
            if not title_raw:
                continue
            screen, quality = parse_listing_quality(title_raw)
            rows.append({
                "title_raw": title_raw,
                "title": title_raw.lower(),
                "sku": (rec.get("seller-sku") or "").strip(),
                "asin": (rec.get("asin1") or "").strip(),
                "price": (rec.get("price") or "").strip(),
                "quantity": (rec.get("quantity") or "0").strip(),
                "status": (rec.get("status") or "").strip(),
                "screen": screen,
                "quality": quality,
            })
    return rows


def actual_brand(stock_brand, name):
    if stock_brand != "MIX":
        return stock_brand
    n = name.lower()
    for pat, b in MIX_SUB_BRAND:
        if re.search(pat, n):
            return b
    return "MIX"


def normalize_name(name):
    n = name.lower()
    n = re.sub(r"^galaxy\s+", "samsung galaxy ", n)
    n = re.sub(r"^iphone\s+", "apple iphone ", n)
    for w in [
        "incell", "oled", "amoled", "lcd", "tft", "careog", "frame",
        "with frame", "standard", "white", "black", "gold", "super", "with",
    ]:
        n = re.sub(rf"\b{w}\b", " ", n)
    # Canonicalize "+" to the word "plus" (not the reverse) - stock text mostly
    # spells it out ("Pro Plus", "8 Plus") while listing titles mix both ("Pro+",
    # "8+"); collapsing both sides to one form is what makes the exact-token
    # clean-match work regardless of which form either side happens to use.
    n = re.sub(r"\+", " plus ", n)
    n = re.sub(r"\(([^)]+)\)", r" \1 ", n)
    n = re.sub(r"[^a-z0-9+]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def search_tokens(name, brand):
    n = normalize_name(name)
    for prefix in [
        "apple iphone", "samsung galaxy", "oneplus", "realme", "oppo", "vivo",
        "redmi", "poco", "xiaomi", "honor", "nokia", "moto", "asus",
        "nothing", "infinix",
    ]:
        if n.startswith(prefix + " "):
            n = n[len(prefix):].strip()
            break
    tokens = [t for t in n.split() if t and t != "with"]
    aliases = {"next": "nxt", "nxt": "nxt"}
    return [aliases.get(t, t) for t in tokens]


def title_matches(tokens, title, brand):
    if not tokens:
        return False
    brand_keys = [brand] + [b for b in BRAND_ALIASES.get(brand, []) if b != brand]
    brand_ok = False
    for b in brand_keys:
        for tok in BRAND_TITLE_TOKENS.get(b, [b.lower()]):
            if tok in title:
                brand_ok = True
                break
        if brand_ok:
            break
    if not brand_ok and brand != "MIX":
        return False

    for tok in tokens:
        if tok == "5g" or tok == "4g":
            if tok not in title and f"({tok.upper()})" not in title.upper():
                if tok == "5g":
                    continue
                return False
        elif len(tok) <= 2 and tok.isdigit():
            if not re.search(rf"(?<![0-9]){re.escape(tok)}(?![0-9])", title):
                return False
        elif tok not in title:
            if tok.endswith("x") and tok[:-1].isdigit():
                alt = tok[:-1] + " x"
                if alt not in title and tok not in title.replace(" ", ""):
                    return False
            elif tok == "nxt" and "next" in title:
                continue
            elif tok == "pro+" and "pro+" in title:
                continue
            elif tok == "13" and "pro+" in " ".join(tokens) and "13 pro+" in title:
                continue
            else:
                return False
    return True


TITLE_BOILERPLATE_PHRASES_RE = re.compile(
    r"display\s*\+\s*touch\s*screen\s*combo\s*folder|"
    r"display\s*screen\s*replacement\s*combo\s*folder|"
    r"touch\s*screen\s*combo\s*folder"
)

TITLE_BOILERPLATE_RE = re.compile(
    r"^(compatible for|for)\s+|"
    r"\(no fingerprint support\)|\(fingerprint support\)|"
    r"\bgx\b|\bcompatible\b|\bdisplay\b|\btouch\b|\bscreen\b|"
    r"\bcombo\b|\bfolder\b|\breplacement\b|,\s*(black|white|gold)\b"
)

BRAND_PREFIXES = [
    "apple iphone", "samsung galaxy", "oneplus", "realme", "oppo", "vivo",
    "redmi", "poco", "xiaomi", "honor", "nokia", "motorola moto",
    "motorola", "moto", "asus", "nothing", "infinix",
]

# NOT in BRAND_PREFIXES (deliberately): "mi" is a genuine sub-brand identity
# word within Xiaomi's lineup, not filler - "Mi A3" and "Redmi A3" are two
# different real phones that happen to share a model number. Blanket-
# stripping "mi" would make stock "Mi A3" wrongly clean-match a "Redmi A3"
# listing. It's only carried across a '/' (see below), never stripped.
XIAOMI_SUBBRAND_WORDS = ("redmi", "poco", "mi")

# Network-generation tags and bare production years don't distinguish which
# physical screen part fits (a 4G/5G or 2021/2022 variant of the same
# numbered model uses the same display) - ignore them on both sides so they
# don't block an otherwise-exact model match.
IGNORABLE_TOKENS_RE = re.compile(r"^(4g|5g|20[12]\d)$")


def _significant_tokens(tokens):
    return {t for t in tokens if not IGNORABLE_TOKENS_RE.match(t)}


def title_variant_tokensets(title_raw):
    """Model-identity tokens per '/'-separated variant in a listing title.

    A listing like "Oppo F19/F19 Pro Amoled..." explicitly names two variants
    (shared-compatible family) - each side of the '/' is tokenized separately
    so a stock item matching EITHER side counts as a clean, verified match.
    Boilerplate (compatible-for, fingerprint notes, "display+touch screen
    combo folder", colors) is stripped first so it never pollutes tokens.

    A title like "Mi 11i/11X" states its Xiaomi sub-brand word ("Mi") only
    once, before the '/', but it implicitly applies to the second variant
    too - so a later segment lacking any of its own {mi, redmi, poco} word
    inherits the first segment's, keeping it comparable to stock text
    (which always states its sub-brand word once, no slash of its own).
    """
    t = TITLE_BOILERPLATE_PHRASES_RE.sub(" ", title_raw.lower())
    t = TITLE_BOILERPLATE_RE.sub(" ", t)
    variants = []
    first_subbrand = None
    for idx, segment in enumerate(t.split("/")):
        n = normalize_name(segment)
        own_subbrand = next(
            (w for w in XIAOMI_SUBBRAND_WORDS if n == w or n.startswith(w + " ")),
            None,
        )
        if idx == 0:
            first_subbrand = own_subbrand
        for prefix in BRAND_PREFIXES:
            if n == prefix:
                n = ""
                break
            if n.startswith(prefix + " "):
                n = n[len(prefix):].strip()
                break
        toks = [tok for tok in n.split() if tok and tok != "with"]
        aliases = {"next": "nxt"}
        toks = [aliases.get(tok, tok) for tok in toks]
        if idx > 0 and not own_subbrand and first_subbrand and toks:
            toks = [first_subbrand] + toks
        if toks:
            variants.append(toks)
    return variants


def is_clean_match(stock_tokens, title_raw):
    """True if the title's own model tokens are an EXACT set-match to stock's
    tokens on at least one '/'-variant - i.e. genuinely the same model, not a
    same-numbered sibling (Pro / Pro Max / Note-prefixed / suffixed variant)
    riding along on a loose substring match."""
    stock_set = _significant_tokens(stock_tokens)
    return any(
        _significant_tokens(v) == stock_set for v in title_variant_tokensets(title_raw)
    )


def find_listings(stock_item, listings):
    brand = actual_brand(stock_item["brand"], stock_item["name"])
    tokens = search_tokens(stock_item["name"], brand)
    return [
        row for row in listings
        if title_matches(tokens, row["title"].replace("+", " plus "), brand)
    ]


def classify_stock_item(item, listings):
    """4-way classification: MISSING / QUALITY_GAP / OUT_OF_STOCK / OK.

    Only "clean" matches (exact model-token match, not a same-numbered
    sibling like Pro/Pro Max/Note-Pro riding along on substring containment)
    are eligible for OK/QUALITY_GAP/OUT_OF_STOCK. A stock item with only
    inflated (wrong-sibling) hits is MISSING - those hits don't confirm this
    exact model is listed at all.
    """
    tokens = search_tokens(item["name"], actual_brand(item["brand"], item["name"]))
    hits = find_listings(item, listings)
    clean_hits = [h for h in hits if is_clean_match(tokens, h["title_raw"])]
    if not clean_hits:
        return "MISSING", None, hits

    quality_hits = [
        h for h in clean_hits
        if quality_match(item["screen"], item["quality"], h["screen"], h["quality"])
    ]
    if not quality_hits:
        return "QUALITY_GAP", clean_hits[0], clean_hits

    def sellable(h):
        try:
            qty = int(h["quantity"] or "0")
        except ValueError:
            qty = 0
        return h["status"].lower() == "active" and qty > 0

    sellable_hits = [h for h in quality_hits if sellable(h)]
    if sellable_hits:
        return "OK", sellable_hits[0], clean_hits
    return "OUT_OF_STOCK", quality_hits[0], clean_hits


def main():
    if not STOCK_FILE.exists():
        raise SystemExit(f"Stock file missing: {STOCK_FILE}")
    if not LISTINGS_FILE.exists():
        raise SystemExit(f"Listings file missing: {LISTINGS_FILE}")

    stock = parse_stock()
    listings = parse_listings()

    report_rows = []
    counts = {"OK": 0, "OUT_OF_STOCK": 0, "QUALITY_GAP": 0, "MISSING": 0}

    for item in stock:
        status, best, all_hits = classify_stock_item(item, listings)
        counts[status] += 1
        stock_q = f"{item['screen']}/{item['quality']}"
        row = {
            "brand": item["brand"],
            "model": item["name"],
            "qty": item["qty"],
            "stock_screen": item["screen"],
            "stock_quality": item["quality"],
            "classification": status,
            "listing_sku": "",
            "listing_asin": "",
            "listing_status": "",
            "listing_qty": "",
            "listing_screen": "",
            "listing_quality": "",
            "listing_title": "",
            "other_hits": "",
            "notes": "",
        }
        if best:
            row.update({
                "listing_sku": best["sku"],
                "listing_asin": best["asin"],
                "listing_status": best["status"],
                "listing_qty": best["quantity"],
                "listing_screen": best["screen"],
                "listing_quality": best["quality"],
                "listing_title": best["title_raw"][:120],
            })
        if status == "MISSING":
            row["notes"] = f"no listing found at all for this model (need {stock_q})"
        elif status == "QUALITY_GAP":
            others = sorted({f"{h['screen']}/{h['quality']}" for h in all_hits})
            row["other_hits"] = " | ".join(others)
            row["notes"] = f"model listed but none in {stock_q} quality"
        elif status == "OUT_OF_STOCK":
            row["notes"] = f"correct listing exists ({best['status']}, qty={best['quantity']}) but not currently sellable"
        else:
            row["notes"] = "active, in stock, correct quality"
        report_rows.append(row)

    fields = [
        "brand", "model", "qty", "stock_screen", "stock_quality", "classification",
        "listing_sku", "listing_asin", "listing_status", "listing_qty",
        "listing_screen", "listing_quality", "listing_title", "other_hits", "notes",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(report_rows)

    print("=" * 70)
    print("STOCK vs ALL LISTINGS (Active+Inactive+OOS) MATCH REPORT (2026-08-22)")
    print("=" * 70)
    print(f"Listings rows parsed: {len(listings)}")
    print(f"Stock models: {len(stock)}")
    for k in ["OK", "OUT_OF_STOCK", "QUALITY_GAP", "MISSING"]:
        print(f"  {k}: {counts[k]}")
    print()
    print("--- MISSING (genuinely no listing at all) ---")
    for r in report_rows:
        if r["classification"] == "MISSING":
            print(f"  [{r['brand']}] {r['model']} x{r['qty']} | need {r['stock_screen']}/{r['stock_quality']}")
    print()
    print("--- QUALITY_GAP (listed, but not in the right quality) ---")
    for r in report_rows:
        if r["classification"] == "QUALITY_GAP":
            print(f"  [{r['brand']}] {r['model']} x{r['qty']} | need {r['stock_screen']}/{r['stock_quality']} | Amazon has: {r['other_hits']}")
    print()
    print("--- OUT_OF_STOCK (correct listing exists, needs qty/status fix) ---")
    for r in report_rows:
        if r["classification"] == "OUT_OF_STOCK":
            print(f"  [{r['brand']}] {r['model']} -> {r['listing_sku']} ({r['listing_status']}, qty={r['listing_qty']})")
    print()
    print(f"CSV: {OUT_CSV}")


if __name__ == "__main__":
    main()
