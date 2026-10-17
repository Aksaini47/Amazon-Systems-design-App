import csv, re, sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports")
import stock_vs_all_listings_2026_07_28 as m

def parse_stock_quality(name):
    nl = name.lower()
    if "oled" in nl or "amoled" in nl:
        screen = "OLED"
    elif "incell" in nl or "internal lcd" in nl:
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
    has_careog = "careog" in t or bool(re.search(r"\boriginal\b", t))
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

def screen_match(ss, ls):
    if ss == ls:
        return True
    fam = {"Incell LCD", "LCD", "TFT LCD"}
    if ss in fam and ls in fam:
        return True
    if ss == "Not Specified":
        return True
    return False

m.parse_stock_quality = parse_stock_quality
m.parse_listing_quality = parse_listing_quality
m.screen_match = screen_match

STOCK = Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports\_master_inventory_2026-07-30.txt")
LISTINGS = Path(r"C:\Users\DELL\Downloads\All+Listings+Report_07-11-2026.txt")
OUT_CSV = Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports\master_vs_all_listings_07-11-2026.csv")
OUT_MD = Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports\master_vs_all_listings_07-11-2026.md")

stock, brand = [], ""
for line in STOCK.read_text(encoding="utf-8-sig").splitlines():
    s = line.strip()
    if not s or s.upper() == "MASTER INVENTORY":
        continue
    if s.isupper() or s.startswith("XIAOMI"):
        brand = "XIAOMI/REDMI/POCO" if s.startswith("XIAOMI") else s
        continue
    if not brand:
        continue
    qty_m = re.search(r"\s*-\s*(\d+)\s*QTY\s*$", s, re.I)
    qty = int(qty_m.group(1)) if qty_m else 1
    name = re.sub(r"\s*-\s*\d+\s*QTY\s*$", "", s, flags=re.I).strip()
    sc, q = parse_stock_quality(name)
    stock.append({"brand": brand, "name": name, "qty": qty, "screen": sc, "quality": q})

listings = []
with LISTINGS.open(encoding="utf-8-sig", newline="") as f:
    for rec in csv.DictReader(f, delimiter="\t"):
        title = (rec.get("item-name") or "").strip()
        if not title:
            continue
        sc, q = parse_listing_quality(title)
        listings.append({
            "title_raw": title,
            "title": title.lower(),
            "sku": (rec.get("seller-sku") or "").strip(),
            "asin": (rec.get("asin1") or rec.get("product-id") or "").strip(),
            "price": (rec.get("price") or "").strip(),
            "quantity": (rec.get("quantity") or "0").strip(),
            "status": (rec.get("status") or "").strip(),
            "screen": sc,
            "quality": q,
        })

print("stock", len(stock), "listings", len(listings))
counts = Counter()
rows = []
for item in stock:
    status, best, hits = m.classify_stock_item(item, listings)
    counts[status] += 1
    rows.append({
        "brand": item["brand"], "model": item["name"], "qty": item["qty"],
        "stock_screen": item["screen"], "stock_quality": item["quality"],
        "classification": status,
        "listing_sku": best["sku"] if best else "",
        "listing_asin": best["asin"] if best else "",
        "listing_status": best["status"] if best else "",
        "listing_qty": best["quantity"] if best else "",
        "listing_screen": best["screen"] if best else "",
        "listing_quality": best["quality"] if best else "",
        "listing_title": (best["title_raw"][:120] if best else ""),
        "hit_count": len(hits),
    })

with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

lines = [
    "# Master inventory vs All Listings 07-11-2026",
    "",
    f"- Report: `All+Listings+Report_07-11-2026.txt` ({len(listings)} rows)",
    f"- Master models: **{len(stock)}**",
    "- Quality: Incell~LCD~TFT | OLED~AMOLED | CareOG~Original | WF=With Frame",
    "",
    "## Summary",
    "",
    "| Result | Count | Meaning |",
    "|---|---:|---|",
    f"| OK | {counts['OK']} | quality match + Active + qty>0 |",
    f"| OUT_OF_STOCK | {counts['OUT_OF_STOCK']} | quality match but qty=0 or Inactive |",
    f"| QUALITY_GAP | {counts['QUALITY_GAP']} | model found, wrong quality |",
    f"| MISSING | {counts['MISSING']} | no listing for model |",
    "",
]
for key, title in [
    ("OK", "OK - ready"),
    ("OUT_OF_STOCK", "OUT_OF_STOCK - qty restock candidates"),
    ("QUALITY_GAP", "QUALITY_GAP - wrong quality listing"),
    ("MISSING", "MISSING - need Create"),
]:
    lines.append(f"## {title} ({counts[key]})")
    lines.append("")
    for r in rows:
        if r["classification"] != key:
            continue
        if key == "MISSING":
            lines.append(f"- [{r['qty']}x] **{r['model']}** want {r['stock_screen']}/{r['stock_quality']}")
        else:
            lines.append(
                f"- [{r['qty']}x] **{r['model']}** want {r['stock_screen']}/{r['stock_quality']} -> "
                f"`{r['listing_sku']}` [{r['listing_status']} qty={r['listing_qty']}] "
                f"{r['listing_screen']}/{r['listing_quality']} | {r['listing_title']}"
            )
    lines.append("")

OUT_MD.write_text("\n".join(lines), encoding="utf-8")
print("COUNTS", dict(counts))
print("WROTE", OUT_CSV.name, OUT_MD.name)
for key in ["OK", "OUT_OF_STOCK", "QUALITY_GAP", "MISSING"]:
    print(f"\n== {key} {counts[key]} ==")
    for r in rows:
        if r["classification"] == key:
            print(f"{r['model']} | {r['listing_sku']} | {r['listing_status']} q={r['listing_qty']} | {r['listing_screen']}/{r['listing_quality']}")
