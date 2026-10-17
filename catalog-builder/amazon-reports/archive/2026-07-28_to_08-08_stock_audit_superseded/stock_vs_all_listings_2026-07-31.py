"""Match actual stock.txt models vs the FULL All Listings Report (Active+Inactive+OOS).

Stock source: catalog-builder/actual stock.txt
Listings: catalog-builder/amazon-reports/all_listings_2026-06-23.tsv
  (real Seller Central "All Listings Report", tab-delimited,
  columns: sku,asin,price,qty,status,name)

This is a 4-way classification (finer than the OK/WRONG_QUALITY/MISSING original):
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
STOCK_FILE = ROOT / "_master_inventory_2026-07-30.txt"
LISTINGS_FILE = ROOT / "all_listings_2026-07-31.tsv"
OUT_CSV = ROOT / "stock_vs_all_listings_report_2026-07-31.csv"

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
    if stock_screen == listing_screen:
        return True
    if stock_screen in ("Incell LCD", "LCD") and listing_screen in ("Incell LCD", "LCD"):
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
    rows = []
    with LISTINGS_FILE.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for rec in reader:
            title_raw = (rec.get("name") or "").strip()
            if not title_raw:
                continue
            screen, quality = parse_listing_quality(title_raw)
            rows.append({
                "title_raw": title_raw,
                "title": title_raw.lower(),
                "sku": (rec.get("sku") or "").strip(),
                "asin": (rec.get("asin") or "").strip(),
                "price": (rec.get("price") or "").strip(),
                "quantity": (rec.get("qty") or "0").strip(),
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
    n = n.replace("pro plus", "pro+").replace("pro +", "pro+")
    n = re.sub(r"\(([^)]+)\)", r" \1 ", n)
    n = re.sub(r"[^a-z0-9+]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def search_tokens(name, brand):
    n = normalize_name(name)
    for prefix in [
        "apple iphone", "samsung galaxy", "oneplus", "realme", "oppo", "vivo",
        "redmi", "poco", "xiaomi", "honor", "nokia", "moto", "asus", "nothing",
        "infinix",
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


def find_listings(stock_item, listings):
    brand = actual_brand(stock_item["brand"], stock_item["name"])
    tokens = search_tokens(stock_item["name"], brand)
    return [row for row in listings if title_matches(tokens, row["title"], brand)]


def classify_stock_item(item, listings):
    """4-way classification: MISSING / QUALITY_GAP / OUT_OF_STOCK / OK."""
    hits = find_listings(item, listings)
    if not hits:
        return "MISSING", None, hits

    quality_hits = [
        h for h in hits
        if quality_match(item["screen"], item["quality"], h["screen"], h["quality"])
    ]
    if not quality_hits:
        return "QUALITY_GAP", hits[0], hits

    def sellable(h):
        try:
            qty = int(h["quantity"] or "0")
        except ValueError:
            qty = 0
        return h["status"].lower() == "active" and qty > 0

    sellable_hits = [h for h in quality_hits if sellable(h)]
    if sellable_hits:
        return "OK", sellable_hits[0], hits
    return "OUT_OF_STOCK", quality_hits[0], hits


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
    print("STOCK vs ALL LISTINGS (Active+Inactive+OOS) MATCH REPORT (2026-07-28)")
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
