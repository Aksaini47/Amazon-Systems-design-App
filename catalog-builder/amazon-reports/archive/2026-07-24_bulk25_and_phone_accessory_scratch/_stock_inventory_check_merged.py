"""Stock vs Amazon inventory — model + quality (screen/grade) matching."""
import re
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STOCK_FILE = ROOT.parent / "actual stock.txt"
LISTINGS_FILE = ROOT / "All+Listings+Report_05-12-2026_merged_bulk25.txt"

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


def parse_stock_quality(name):
    """Screen type + quality grade from stock item name (stock_v6 rules)."""
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


def parse_listing_quality(title):
    """Screen type + quality grade from Amazon listing title."""
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

    if "careog" in t:
        quality = "CareOG"
    elif "with frame" in t or "(with frame)" in t or " wf " in t:
        quality = "With Frame"
    else:
        quality = "Standard"
    return screen, quality


def screen_match(stock_screen, listing_screen):
    if stock_screen == listing_screen:
        return True
    if stock_screen in ("Incell LCD", "LCD") and listing_screen in ("Incell LCD", "LCD"):
        return True
    return False


def quality_match(stock_screen, stock_quality, listing_screen, listing_quality):
    return screen_match(stock_screen, listing_screen) and stock_quality == listing_quality


def parse_stock():
    lines = STOCK_FILE.read_text(encoding="utf-8").splitlines()
    stock, brand = [], ""
    for line in lines:
        s = line.strip()
        if not s or s.lower() == "actual stock":
            continue
        if s.isupper() and any(b in s for b in BRAND_KEYWORDS):
            brand = s
            continue
        if not brand:
            continue
        qty_m = re.search(r" - (\d+)$", s)
        qty = int(qty_m.group(1)) if qty_m else 1
        name = re.sub(r" - \d+$", "", s).strip()
        screen, quality = parse_stock_quality(name)
        stock.append({
            "brand": brand, "name": name, "qty": qty,
            "screen": screen, "quality": quality,
        })
    return stock


def parse_listings():
    rows = []
    for line in LISTINGS_FILE.read_text(encoding="utf-8-sig").splitlines()[1:]:
        if not line.strip():
            continue
        cols = [c.strip() for c in line.split("\t")]
        if len(cols) < 30:
            cols += [""] * (30 - len(cols))
        title_raw = cols[0]
        title = title_raw.lower()
        screen, quality = parse_listing_quality(title)
        rows.append({
            "title_raw": title_raw,
            "title": title,
            "sku": cols[3],
            "price": cols[4],
            "quantity": cols[5],
            "status": cols[29],
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
    n = re.sub(r"\(([^)]+)\)", r" \1 ", n)  # (4G) -> 4g
    n = re.sub(r"[^a-z0-9+]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def search_tokens(name, brand):
    n = normalize_name(name)
    # drop brand prefix from tokens
    for prefix in [
        "apple iphone", "samsung galaxy", "oneplus", "realme", "oppo", "vivo",
        "redmi", "poco", "xiaomi", "honor", "nokia", "moto", "asus", "nothing",
        "infinix",
    ]:
        if n.startswith(prefix + " "):
            n = n[len(prefix):].strip()
            break
    tokens = [t for t in n.split() if t and t != "with"]
    # spelling aliases
    aliases = {"next": "nxt", "nxt": "nxt"}
    expanded = []
    for t in tokens:
        expanded.append(aliases.get(t, t))
    return expanded


def title_matches(tokens, title, brand):
    if not tokens:
        return False
    allowed = BRAND_ALIASES.get(brand, [brand])
    brand_ok = False
    for b in allowed:
        for tok in BRAND_TITLE_TOKENS.get(b, [b.lower()]):
            if tok in title:
                brand_ok = True
                break
        if brand_ok:
            break
    if not brand_ok and brand != "MIX":
        return False

    # Require multi-char tokens; avoid "3" matching inside "13"
    for tok in tokens:
        if tok == "5g" or tok == "4g":
            if tok not in title and f"({tok.upper()})" not in title.upper():
                if tok == "5g":
                    continue
                return False
        elif len(tok) <= 2 and tok.isdigit():
            # lone digit token must appear as whole model token (not substring of 13, etc.)
            if not re.search(rf"(?<![0-9]){re.escape(tok)}(?![0-9])", title):
                return False
        elif tok not in title:
            # pro+ vs pro plus already normalized; allow 11x = 11 x
            if tok.endswith("x") and tok[:-1].isdigit():
                alt = tok[:-1] + " x"
                if alt not in title and tok not in title.replace(" ", ""):
                    return False
            elif tok == "nxt" and "next" in title:
                continue
            elif tok == "pro+" and "pro+" in title:
                continue
            elif tok == "13" and "pro+" in " ".join(tokens) and "13 pro+" in title:
                continue  # Redmi 13 Pro Plus stock = Note 13 Pro+ listing
            else:
                return False
    return True


def find_listings(stock_item, listings):
    brand = actual_brand(stock_item["brand"], stock_item["name"])
    tokens = search_tokens(stock_item["name"], brand)
    matches = []
    for row in listings:
        if not title_matches(tokens, row["title"], brand):
            continue
        matches.append(row)
    return matches


def classify_stock_item(item, listings):
    hits = find_listings(item, listings)
    if not hits:
        return "NOT_LISTED", None, hits

    exact = [
        h for h in hits
        if quality_match(item["screen"], item["quality"], h["screen"], h["quality"])
    ]
    active_exact = [h for h in exact if h["status"] == "Active"]
    pick = (active_exact or exact or [None])[0]
    if pick:
        return "EXACT", pick, hits
    return "QUALITY_MISSING", hits[0], hits


def main():
    stock = parse_stock()
    listings = parse_listings()

    exact_rows, quality_missing_rows, not_listed_rows = [], [], []

    for item in stock:
        status, best, all_hits = classify_stock_item(item, listings)
        base = {
            "brand": item["brand"],
            "name": item["name"],
            "qty": item["qty"],
            "stock_screen": item["screen"],
            "stock_quality": item["quality"],
        }
        if status == "EXACT":
            exact_rows.append({
                **base,
                "amazon_status": best["status"],
                "amazon_sku": best["sku"],
                "listing_screen": best["screen"],
                "listing_quality": best["quality"],
                "amazon_title": best["title_raw"][:90],
            })
        elif status == "QUALITY_MISSING":
            others = sorted({
                f"{h['screen']}/{h['quality']}" for h in all_hits
            })
            quality_missing_rows.append({
                **base,
                "amazon_has": " | ".join(others),
                "sample_title": all_hits[0]["title_raw"][:90],
                "sample_status": all_hits[0]["status"],
            })
        else:
            not_listed_rows.append(base)

    total_units = sum(i["qty"] for i in stock)
    exact_units = sum(i["qty"] for i in exact_rows)
    qmiss_units = sum(i["qty"] for i in quality_missing_rows)
    not_units = sum(i["qty"] for i in not_listed_rows)

    print("=" * 70)
    print("STOCK vs AMAZON — MODEL + QUALITY MATCH")
    print("=" * 70)
    print(f"Total stock: {len(stock)} variants ({total_units} units)")
    print(f"EXACT quality listed:     {len(exact_rows)} models ({exact_units} units)")
    print(f"Model listed, WRONG quality: {len(quality_missing_rows)} models ({qmiss_units} units)")
    print(f"Model NOT on Amazon at all:  {len(not_listed_rows)} models ({not_units} units)")
    print()
    print("Quality rules: Screen=OLED|Incell LCD|LCD|TFT|Not Specified")
    print("               Grade=CareOG|With Frame|Standard")
    print()

    fields_exact = [
        "brand", "name", "qty", "stock_screen", "stock_quality",
        "listing_screen", "listing_quality", "amazon_status", "amazon_sku", "amazon_title",
    ]
    fields_qmiss = [
        "brand", "name", "qty", "stock_screen", "stock_quality",
        "amazon_has", "sample_status", "sample_title",
    ]
    fields_not = ["brand", "name", "qty", "stock_screen", "stock_quality"]

    with open(ROOT / "stock_exact_quality.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields_exact)
        w.writeheader()
        w.writerows(exact_rows)

    with open(ROOT / "stock_wrong_quality.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields_qmiss)
        w.writeheader()
        w.writerows(quality_missing_rows)

    with open(ROOT / "stock_not_listed_quality.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields_not)
        w.writeheader()
        w.writerows(not_listed_rows)

    # Combined: not listed WITH this quality = wrong quality + not listed at all
    not_this_quality = quality_missing_rows + not_listed_rows
    not_this_quality_units = qmiss_units + not_units
    with open(ROOT / "stock_missing_this_quality.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "brand", "name", "qty", "stock_screen", "stock_quality", "reason", "amazon_has", "sample_title",
        ])
        w.writeheader()
        for r in quality_missing_rows:
            w.writerow({
                "brand": r["brand"], "name": r["name"], "qty": r["qty"],
                "stock_screen": r["stock_screen"], "stock_quality": r["stock_quality"],
                "reason": "model listed, different quality",
                "amazon_has": r["amazon_has"], "sample_title": r["sample_title"],
            })
        for r in not_listed_rows:
            w.writerow({
                "brand": r["brand"], "name": r["name"], "qty": r["qty"],
                "stock_screen": r["stock_screen"], "stock_quality": r["stock_quality"],
                "reason": "model not on Amazon", "amazon_has": "", "sample_title": "",
            })

    print("--- NOT LISTED with THIS quality (wrong grade OR no listing) ---")
    for r in quality_missing_rows:
        print(f"  [{r['brand']}] {r['name']} x{r['qty']} | need {r['stock_screen']}/{r['stock_quality']} | Amazon has: {r['amazon_has']}")
    for r in not_listed_rows:
        print(f"  [{r['brand']}] {r['name']} x{r['qty']} | need {r['stock_screen']}/{r['stock_quality']} | NO listing")

    print()
    print(f"TOTAL missing this quality: {len(not_this_quality)} models ({not_this_quality_units} units)")
    print("CSV: stock_missing_this_quality.csv")


if __name__ == "__main__":
    main()
