"""Compare master stock vs live Active inventory (qty>0 Active preferred)."""
from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STOCK_FILE = ROOT / "_master_inventory_2026-07-30.txt"
LISTINGS_FILE = ROOT / "_active_inventory_live_2026-07-31.csv"
OUT_CSV = ROOT / "STOCK_VS_ACTIVE_INVENTORY_2026-07-31.csv"
OUT_MD = ROOT / "STOCK_VS_ACTIVE_INVENTORY_2026-07-31.md"

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

# Sibling-safe: model numbers that must not match a longer sibling
SIBLING_GUARDS = [
    # (token that matched, forbidden extra in title when stock lacks it)
]


def parse_stock_quality(name: str):
    nl = name.lower()
    if "oled" in nl or "amoled" in nl:
        screen = "OLED"
    elif "incell" in nl:
        screen = "Incell"
    elif "tft" in nl:
        screen = "TFT"
    elif "lcd" in nl:
        screen = "LCD"
    else:
        screen = "Not Specified"

    if "careog" in nl or "care og" in nl:
        quality = "CareOG"
    elif "original" in nl:
        quality = "Original"
    elif "frame" in nl or "with frame" in nl or " wf " in nl:
        quality = "With Frame"
    else:
        quality = "Standard"
    return screen, quality


def parse_listing_quality(title: str):
    t = title.lower()
    if "super oled" in t or "amoled" in t or ("oled" in t and "lcd" not in t and "incell" not in t and "tft" not in t):
        screen = "OLED"
    elif "incell" in t:
        screen = "Incell"
    elif "tft" in t:
        screen = "TFT"
    elif "lcd" in t:
        screen = "LCD"
    else:
        screen = "Not Specified"

    has_careog = "careog" in t or "care og" in t
    has_original = re.search(r"\boriginal\b", t) is not None
    has_frame = "with frame" in t or "(with frame)" in t or " wf " in t
    if has_careog and has_frame:
        quality = "CareOG+With Frame"
    elif has_careog:
        quality = "CareOG"
    elif has_original:
        quality = "Original"
    elif has_frame:
        quality = "With Frame"
    else:
        quality = "Standard"
    return screen, quality


def screen_match(stock_screen, listing_screen):
    """Incell ≈ LCD ≈ TFT; OLED separate."""
    if stock_screen == listing_screen:
        return True
    lcd_family = {"Incell", "LCD", "TFT"}
    if stock_screen in lcd_family and listing_screen in lcd_family:
        return True
    if stock_screen == "Not Specified":
        return True
    if listing_screen == "Not Specified" and stock_screen != "OLED":
        # vague listing may still be ok for non-OLED stock; treat as soft match
        return True
    return False


def quality_grade_compatible(stock_quality, listing_quality):
    """CareOG ≈ Original; CareOG+With Frame covers CareOG or With Frame."""
    if stock_quality == listing_quality:
        return True
    care_orig = {"CareOG", "Original"}
    if stock_quality in care_orig and listing_quality in care_orig:
        return True
    if listing_quality == "CareOG+With Frame" and stock_quality in ("CareOG", "Original", "With Frame"):
        return True
    if stock_quality == "CareOG+With Frame" and listing_quality in ("CareOG", "Original", "With Frame"):
        return True
    return False


def quality_match(ss, sq, ls, lq):
    return screen_match(ss, ls) and quality_grade_compatible(sq, lq)


def parse_stock():
    lines = STOCK_FILE.read_text(encoding="utf-8").splitlines()
    stock, brand = [], ""
    for line in lines:
        s = line.strip()
        if not s or s.upper().startswith("MASTER"):
            continue
        if s.isupper() and any(b in s for b in BRAND_KEYWORDS):
            brand = s
            continue
        if not brand:
            continue
        qty_m = re.search(r" - (\d+)\s*QTY$", s, re.I) or re.search(r" - (\d+)$", s)
        qty = int(qty_m.group(1)) if qty_m else 1
        name = re.sub(r" - \d+\s*QTY$", "", s, flags=re.I)
        name = re.sub(r" - \d+$", "", name).strip()
        screen, quality = parse_stock_quality(name)
        stock.append({
            "brand": brand, "name": name, "qty": qty,
            "screen": screen, "quality": quality,
        })
    return stock


def parse_listings():
    rows = []
    with LISTINGS_FILE.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            title_raw = (rec.get("name") or "").strip()
            if not title_raw:
                continue
            screen, quality = parse_listing_quality(title_raw)
            try:
                qn = int(float(rec.get("qty") or 0))
            except ValueError:
                qn = 0
            status = (rec.get("status") or "").strip() or "ACTIVE"
            rows.append({
                "title_raw": title_raw,
                "title": title_raw.lower(),
                "sku": (rec.get("sku") or "").strip(),
                "asin": (rec.get("asin") or "").strip(),
                "price": (rec.get("price") or "").strip(),
                "quantity": qn,
                "status": status,
                "screen": screen,
                "quality": quality,
            })
    return rows


def actual_brand(stock_brand, name):
    if stock_brand != "MIX" and "XIAOMI" not in stock_brand:
        return stock_brand
    if stock_brand == "MIX":
        n = name.lower()
        for pat, b in MIX_SUB_BRAND:
            if re.search(pat, n):
                return b
        return "MIX"
    return stock_brand


def normalize_name(name):
    n = name.lower()
    n = re.sub(r"^galaxy\s+", "samsung galaxy ", n)
    n = re.sub(r"^iphone\s+", "apple iphone ", n)
    for w in [
        "incell", "oled", "amoled", "lcd", "tft", "careog", "frame",
        "with frame", "standard", "white", "black", "gold", "super", "with",
        "original", "internal",
    ]:
        n = re.sub(rf"\b{w}\b", " ", n)
    n = n.replace("pro plus", "pro+").replace("pro +", "pro+")
    n = re.sub(r"\(([^)]+)\)", r" \1 ", n)
    n = re.sub(r"[^a-z0-9+]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def search_tokens(name, brand):
    n = normalize_name(name)
    for prefix in [
        "apple iphone", "samsung galaxy", "oneplus", "realme", "oppo", "vivo",
        "redmi", "poco", "xiaomi", "honor", "nokia", "moto", "asus", "nothing",
        "infinix", "mi",
    ]:
        if n.startswith(prefix + " "):
            n = n[len(prefix):].strip()
            break
    tokens = [t for t in n.split() if t and t != "with"]
    aliases = {"next": "nxt", "nxt": "nxt"}
    return [aliases.get(t, t) for t in tokens]


def sibling_safe(tokens, title):
    """Reject if title clearly is a sibling model (extra digit/letter series)."""
    t = title.lower()
    # OnePlus 8 vs OnePlus 8 Pro / 8T
    joined = " ".join(tokens)
    # iPhone 13 vs 13 Pro / 13 Pro Max: if stock tokens lack pro/max, reject titles that add them when another stock sibling exists — handled by requiring all tokens; extra words ok.
    # Hard guards for common collisions:
    guards = [
        # stock tokens, forbidden substrings in title (when not in stock tokens)
        (["8"], ["8 pro", "8t", "8+", "nord"]),  # too broad — skip
    ]
    # Specific: OnePlus 7 vs 7 Pro / 7T
    if tokens == ["7"] or (len(tokens) == 1 and tokens[0] == "7"):
        if re.search(r"\b7\s*pro\b|\b7t\b|\b7\s*t\b", t):
            return False
    if tokens == ["8"] or (len(tokens) == 1 and tokens[0] == "8"):
        if re.search(r"\b8\s*pro\b|\b8t\b|\bnord\b", t):
            return False
    if "pro" not in tokens and "pro+" not in tokens:
        # iPhone 13 stock must not match 13 Pro / 13 Pro Max listings
        if "13" in tokens and re.search(r"\b13\s*pro\b", t):
            return False
        if "11" in tokens and re.search(r"\b11\s*pro\b", t):
            return False
    if "max" not in tokens and re.search(r"\bpro\s*max\b", t) and any(x in tokens for x in ("13", "11", "14", "12", "xs")):
        # stock without Max shouldn't match Pro Max (unless only Pro was intended — Pro Max is sibling of Pro)
        if "pro" in tokens:
            return False
    # Galaxy A32 4G vs others already handled by 4g token
    # Realme 9 vs 9i / 9 Pro
    if tokens == ["9"] or (tokens == ["9"] ):
        pass
    if tokens == ["9"]:
        if re.search(r"\b9i\b|\b9\s*pro\b|\b9\s*pro\+", t):
            return False
    if tokens == ["7"]:
        if "realme" in t and re.search(r"\b7i\b|\b7\s*pro\b", t):
            return False
    # OnePlus Nord vs Nord CE / Nord 2 / Nord 3
    if "nord" in tokens and "ce" not in tokens:
        if re.search(r"\bnord\s*ce\b|\bnord\s*2\b|\bnord\s*3\b|\bnord\s*n\d", t):
            return False
    return True


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
        if tok in ("5g", "4g"):
            if tok not in title and f"({tok.upper()})" not in title.upper():
                if tok == "5g":
                    continue
                return False
        elif len(tok) <= 2 and tok.isdigit():
            if not re.search(rf"(?<![0-9a-z]){re.escape(tok)}(?![0-9a-z])", title):
                return False
        elif tok not in title:
            if tok.endswith("x") and tok[:-1].isdigit():
                alt = tok[:-1] + " x"
                if alt not in title and tok not in title.replace(" ", ""):
                    return False
            elif tok == "nxt" and "next" in title:
                continue
            elif tok == "pro+" and ("pro+" in title or "pro plus" in title or "pro+" in title.replace(" ", "")):
                continue
            else:
                return False
    if not sibling_safe(tokens, title):
        return False
    return True


def find_listings(stock_item, listings):
    brand = actual_brand(stock_item["brand"], stock_item["name"])
    tokens = search_tokens(stock_item["name"], brand)
    return [row for row in listings if title_matches(tokens, row["title"], brand)]


def is_active_qty(h):
    return h["status"].lower() == "active" and h["quantity"] > 0


def classify_stock_item(item, listings):
    hits = find_listings(item, listings)
    if not hits:
        return "MISSING", None, hits

    exact = [
        h for h in hits
        if quality_match(item["screen"], item["quality"], h["screen"], h["quality"])
    ]
    active_exact = [h for h in exact if is_active_qty(h)]
    if active_exact:
        # prefer highest qty
        pick = sorted(active_exact, key=lambda h: h["quantity"], reverse=True)[0]
        return "OK", pick, hits

    if exact:
        # quality ok but inactive / qty 0
        pick = exact[0]
        return "OUT_OF_STOCK_OR_INACTIVE", pick, hits

    # model exists but wrong quality/screen
    active_hits = [h for h in hits if is_active_qty(h)]
    pick = (active_hits or hits)[0]
    return "QUALITY_GAP", pick, hits


def main():
    stock = parse_stock()
    listings = parse_listings()
    active_qty = [l for l in listings if is_active_qty(l)]

    report_rows = []
    counts = Counter()

    for item in stock:
        status, best, all_hits = classify_stock_item(item, listings)
        counts[status] += 1
        stock_q = f"{item['screen']}/{item['quality']}"
        base = {
            "brand": item["brand"],
            "model": item["name"],
            "stock_qty": item["qty"],
            "stock_screen": item["screen"],
            "stock_quality": item["quality"],
            "bucket": status,
            "listing_sku": "",
            "listing_asin": "",
            "listing_qty": "",
            "listing_status": "",
            "listing_screen": "",
            "listing_quality": "",
            "listing_title": "",
            "amazon_has_qualities": "",
            "notes": "",
        }
        if best:
            base.update({
                "listing_sku": best["sku"],
                "listing_asin": best["asin"],
                "listing_qty": best["quantity"],
                "listing_status": best["status"],
                "listing_screen": best["screen"],
                "listing_quality": best["quality"],
                "listing_title": best["title_raw"][:140],
            })
        if status == "OK":
            base["notes"] = "active qty>0 + quality/screen match (Incell~LCD~TFT; CareOG~Original)"
        elif status == "OUT_OF_STOCK_OR_INACTIVE":
            base["notes"] = f"quality match but inactive/qty0; need {stock_q}"
        elif status == "QUALITY_GAP":
            others = sorted({f"{h['screen']}/{h['quality']}" for h in all_hits})
            base["amazon_has_qualities"] = " | ".join(others)
            base["notes"] = f"model listed but need {stock_q}; Amazon has other grades"
        else:
            base["notes"] = f"no listing match for model (need {stock_q})"
        report_rows.append(base)

    fields = [
        "brand", "model", "stock_qty", "stock_screen", "stock_quality", "bucket",
        "listing_sku", "listing_asin", "listing_qty", "listing_status",
        "listing_screen", "listing_quality", "listing_title",
        "amazon_has_qualities", "notes",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(report_rows)

    def lines_for(bucket):
        out = []
        for r in report_rows:
            if r["bucket"] != bucket:
                continue
            out.append(
                f"- **{r['model']}** (x{r['stock_qty']}) — need {r['stock_screen']}/{r['stock_quality']}"
                + (f" | Amazon: {r['amazon_has_qualities']}" if r["amazon_has_qualities"] else "")
                + (f" | SKU `{r['listing_sku']}` qty={r['listing_qty']}" if r["listing_sku"] else "")
            )
        return out or ["- _(none)_"]

    md = []
    md.append("# Stock vs Active Inventory — 2026-07-31")
    md.append("")
    md.append("**Account:** Badeja Enterprises (India)  ")
    md.append("**Source stock:** `_master_inventory_2026-07-30.txt`  ")
    md.append("**Source listings:** Seller Central Manage Inventory · Active · pageSize=250 (live GQL HAR)  ")
    md.append(f"**Active listings pulled:** {len(listings)} (qty>0: {len(active_qty)})  ")
    md.append(f"**Master stock variants:** {len(stock)}")
    md.append("")
    md.append("## Quality rules")
    md.append("- Screen: Incell ≈ LCD ≈ TFT; OLED separate")
    md.append("- Grade: CareOG ≈ Original; With Frame distinct")
    md.append("- Sibling-safe model matching (e.g. 13 vs 13 Pro / Pro Max)")
    md.append("")
    md.append("## Counts")
    md.append("")
    md.append("| Bucket | Count |")
    md.append("|---|---:|")
    for b in ("OK", "OUT_OF_STOCK_OR_INACTIVE", "QUALITY_GAP", "MISSING"):
        md.append(f"| {b} | {counts[b]} |")
    md.append(f"| **TOTAL** | **{len(stock)}** |")
    md.append("")
    md.append("## MISSING")
    md.extend(lines_for("MISSING"))
    md.append("")
    md.append("## QUALITY_GAP")
    md.extend(lines_for("QUALITY_GAP"))
    md.append("")
    md.append("## OUT_OF_STOCK_OR_INACTIVE")
    md.extend(lines_for("OUT_OF_STOCK_OR_INACTIVE"))
    md.append("")
    md.append("## OK")
    md.extend(lines_for("OK"))
    md.append("")
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("=" * 60)
    print("STOCK vs ACTIVE INVENTORY 2026-07-31")
    print("=" * 60)
    print(f"Stock: {len(stock)} | Active listings: {len(listings)} (qty>0 {len(active_qty)})")
    for b in ("OK", "OUT_OF_STOCK_OR_INACTIVE", "QUALITY_GAP", "MISSING"):
        print(f"  {b}: {counts[b]}")
    print(f"CSV: {OUT_CSV}")
    print(f"MD:  {OUT_MD}")


if __name__ == "__main__":
    main()