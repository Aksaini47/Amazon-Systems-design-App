"""Master stock -> sibling-safe SKUs from All Listings 07-11-2026."""
from __future__ import annotations

import csv
import importlib.util
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STOCK = ROOT / "_master_inventory_2026-07-30.txt"
LISTINGS = Path(r"C:\Users\DELL\Downloads\All+Listings+Report_07-11-2026.txt")
if not LISTINGS.exists():
    for alt in [
        ROOT / "All+Listings+Report_07-11-2026.txt",
        ROOT / "all_listings_2026-06-23.tsv",
        ROOT / "All+Listings+Report_05-12-2026.txt",
    ]:
        if alt.exists():
            LISTINGS = alt
            break

OUT_CSV = ROOT / "MASTER_STOCK_SKUS_2026-07-31.csv"
OUT_MD = ROOT / "MASTER_STOCK_SKUS_2026-07-31.md"

spec = importlib.util.spec_from_file_location(
    "stock_match", ROOT / "stock_vs_all_listings_2026-07-28.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def parse_stock_quality(name: str):
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

ALLOWED_SEGMENT_NOISE = set()  # 4g/5g are real differentiators - not noise


def model_segments(title: str):
    t = title
    low = t.lower()
    cut_at = None
    for sep in [
        " careog", " lcd", " oled", " amoled", " incell", " tft",
        " display", " (fingerprint", " (no fingerprint", " (with frame",
        " compatible",
    ]:
        idx = low.find(sep)
        if idx > 0 and (cut_at is None or idx < cut_at):
            cut_at = idx
    if cut_at is not None:
        t = t[:cut_at]
    mobj = re.search(r"(?:compatible\s+for|for)\s+(.+)$", t, re.I)
    core = mobj.group(1) if mobj else t
    parts = [p.strip() for p in re.split(r"/", core) if p.strip()]
    segs = []
    brands = [
        "apple iphone", "samsung galaxy", "samsung", "oneplus", "realme", "oppo",
        "vivo", "xiaomi", "redmi", "poco", "honor", "nokia", "motorola moto",
        "moto", "asus", "nothing phone", "nothing", "infinix", "zenfone", "rog phone",
    ]
    for part in parts:
        part = re.sub(r"\([^)]*\)", " ", part).lower()
        for b in brands:
            part = re.sub(rf"\b{re.escape(b)}\b", " ", part)
        part = part.replace("pro plus", "pro+").replace("pro +", "pro+")
        part = re.sub(r"\bmi\b(?=\s+\w)", " ", part)
        part = re.sub(r"[^a-z0-9+]+", " ", part)
        toks = [x for x in part.split() if x]
        if toks:
            segs.append(toks)
    return segs


# Brand/product words kept in search_tokens but stripped from title segments.
BRAND_FILLER = {
    "mi", "phone", "zenfone", "rog", "galaxy", "iphone", "nothing",
    "samsung", "apple", "oppo", "vivo", "realme", "redmi", "poco", "xiaomi",
    "honor", "nokia", "moto", "asus", "infinix", "oneplus", "motorola",
}


def sibling_ok(stock_tokens, title_raw: str) -> bool:
    """True if at least one slash-segment equals stock model (no sibling extras)."""
    core = [t for t in stock_tokens if t not in BRAND_FILLER]
    if not core:
        core = list(stock_tokens)
    st = set(core)
    segs = model_segments(title_raw)
    if not segs:
        return True

    def seg_ok(seg):
        sset = set(seg)
        for tok in core:
            if tok in ("4g", "5g"):
                continue  # network often only in stripped parens
            if tok.isdigit() and len(tok) == 4:
                continue  # years like 2016 often only in parens
            if tok in sset or tok in "".join(seg):
                continue
            return False
        extras = [t for t in seg if t not in st and t not in ALLOWED_SEGMENT_NOISE]
        if "4g" in st and "5g" in sset:
            return False
        if "5g" in st and "4g" in sset:
            return False
        return not extras

    return any(seg_ok(seg) for seg in segs)


def find_listings_safe(item, listings):
    brand = m.actual_brand(item["brand"], item["name"])
    tokens = m.search_tokens(item["name"], brand)
    hits = []
    for row in listings:
        if not m.title_matches(tokens, row["title"], brand):
            continue
        if not sibling_ok(tokens, row["title_raw"]):
            continue
        hits.append(row)
    return hits


def classify(item, listings):
    hits = find_listings_safe(item, listings)
    if not hits:
        return "MISSING", None, hits
    quality_hits = [
        h for h in hits
        if m.quality_match(item["screen"], item["quality"], h["screen"], h["quality"])
    ]
    if not quality_hits:
        return "QUALITY_GAP", hits[0], hits

    def sellable(h):
        try:
            qty = int(h["quantity"] or "0")
        except ValueError:
            qty = 0
        return h["status"].lower() == "active" and qty > 0

    def rank_key(h):
        t = h["title_raw"].lower()
        name_l = item["name"].lower()
        has5 = "5g" in name_l
        has4 = "4g" in name_l and not has5
        title5 = "(5g)" in t or " 5g" in t or "5g)" in t
        title4 = "(4g)" in t or " 4g" in t or "4g)" in t
        if has5:
            net_pen = 0 if title5 else 5
        elif has4:
            net_pen = 0 if title4 else 5
        else:
            net_pen = 0
            if title5:
                net_pen += 2
            if title4:
                net_pen += 1
        color_pen = 0
        if "white" in name_l and "white" not in t:
            color_pen += 3
        if "black" in name_l and "black" not in t and "white" not in name_l:
            color_pen += 3
        if "white" in name_l and "black" in t and "white" not in t:
            color_pen += 5
        try:
            qty = int(h["quantity"] or "0")
        except ValueError:
            qty = 0
        return (net_pen, color_pen, -qty)

    sellable_hits = sorted([h for h in quality_hits if sellable(h)], key=rank_key)
    if sellable_hits:
        return "OK", sellable_hits[0], hits
    quality_hits = sorted(quality_hits, key=rank_key)
    return "OUT_OF_STOCK", quality_hits[0], hits


KNOWN_BRANDS = {
    "REALME", "VIVO", "OPPO", "ONEPLUS", "APPLE", "SAMSUNG",
    "XIAOMI / REDMI / POCO", "XIAOMI/REDMI/POCO", "XIAOMI", "MIX",
}


def parse_stock():
    stock, brand = [], ""
    for line in STOCK.read_text(encoding="utf-8-sig").splitlines():
        s = line.strip()
        if not s or s.upper() == "MASTER INVENTORY":
            continue
        if s in KNOWN_BRANDS or s.startswith("XIAOMI"):
            brand = "XIAOMI/REDMI/POCO" if s.startswith("XIAOMI") else s
            continue
        if not brand:
            continue
        qty_m = re.search(r"\s*-\s*(\d+)\s*QTY\s*$", s, re.I)
        qty = int(qty_m.group(1)) if qty_m else 1
        name = re.sub(r"\s*-\s*\d+\s*QTY\s*$", "", s, flags=re.I).strip()
        sc, q = parse_stock_quality(name)
        stock.append({"brand": brand, "name": name, "qty": qty, "screen": sc, "quality": q})
    return stock


def parse_listings():
    rows = []
    with LISTINGS.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fields = reader.fieldnames or []
        # support both All Listings SC export and local tsv aliases
        name_key = "item-name" if "item-name" in fields else "name"
        sku_key = "seller-sku" if "seller-sku" in fields else "sku"
        asin_key = "asin1" if "asin1" in fields else ("asin" if "asin" in fields else "product-id")
        qty_key = "quantity" if "quantity" in fields else "qty"
        for rec in reader:
            title = (rec.get(name_key) or "").strip()
            if not title:
                continue
            sc, q = parse_listing_quality(title)
            rows.append({
                "title_raw": title,
                "title": title.lower(),
                "sku": (rec.get(sku_key) or "").strip(),
                "asin": (rec.get(asin_key) or rec.get("product-id") or "").strip(),
                "quantity": (rec.get(qty_key) or "0").strip(),
                "status": (rec.get("status") or "").strip(),
                "screen": sc,
                "quality": q,
            })
    return rows


def main():
    if not STOCK.exists():
        raise SystemExit(f"Missing stock: {STOCK}")
    if not LISTINGS.exists():
        raise SystemExit(f"Missing listings: {LISTINGS}")

    stock = parse_stock()
    listings = parse_listings()
    counts = Counter()
    rows = []

    for item in stock:
        status, best, hits = classify(item, listings)
        counts[status] += 1
        want = f"{item['screen']}/{item['quality']}"
        if status == "MISSING":
            note = f"no sibling-safe listing; want {want}; stock_qty={item['qty']}"
        elif status == "QUALITY_GAP":
            others = sorted({f"{h['screen']}/{h['quality']}" for h in hits})
            note = (
                f"model ok, wrong quality (want {want}; have {' | '.join(others)}); "
                f"stock_qty={item['qty']}"
            )
        elif status == "OUT_OF_STOCK":
            note = f"quality match but not sellable; want {want}; stock_qty={item['qty']}"
        else:
            note = f"active+qty>0 quality match; want {want}; stock_qty={item['qty']}"
        rows.append({
            "brand": item["brand"],
            "model": item["name"],
            "sku": best["sku"] if best else "",
            "asin": best["asin"] if best else "",
            "status": best["status"] if best else "",
            "qty": best["quantity"] if best else "",
            "classification": status,
            "note": note,
        })

    fields = ["brand", "model", "sku", "asin", "status", "qty", "classification", "note"]
    out_csv = OUT_CSV
    try:
        f = OUT_CSV.open("w", encoding="utf-8", newline="")
    except PermissionError:
        out_csv = OUT_CSV.with_name(OUT_CSV.stem + ".new.csv")
        f = out_csv.open("w", encoding="utf-8", newline="")
        print("CSV locked; writing", out_csv.name)
    with f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    lines = [
        "# Master stock SKUs — 2026-07-31",
        "",
        f"- Master: `_master_inventory_2026-07-30.txt` (**{len(stock)}** models)",
        f"- Listings: `{LISTINGS.name}` ({len(listings)} rows)",
        "- Rules: sibling-safe model match; Incell≈LCD≈TFT; OLED≠LCD; CareOG≈Original; WF=With Frame",
        "",
        "## Summary",
        "",
        "| Result | Count |",
        "|---|---:|",
        f"| OK | {counts['OK']} |",
        f"| OUT_OF_STOCK | {counts['OUT_OF_STOCK']} |",
        f"| QUALITY_GAP | {counts['QUALITY_GAP']} |",
        f"| MISSING | {counts['MISSING']} |",
        "",
    ]
    for key, title in [
        ("OK", "OK — Active + qty>0 + quality match"),
        ("OUT_OF_STOCK", "OUT_OF_STOCK — quality match, not sellable"),
        ("QUALITY_GAP", "QUALITY_GAP — model found, wrong quality"),
        ("MISSING", "MISSING — no sibling-safe listing"),
    ]:
        lines.append(f"## {title} ({counts[key]})")
        lines.append("")
        for r in rows:
            if r["classification"] != key:
                continue
            if key == "MISSING":
                lines.append(f"- **{r['model']}** — _(no SKU)_ | {r['note']}")
            else:
                lines.append(
                    f"- **{r['model']}** → `{r['sku']}` | {r['asin']} | "
                    f"{r['status']} qty={r['qty']} | {r['note']}"
                )
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("stock", len(stock), "listings", len(listings), "source", LISTINGS.name)
    print("COUNTS", dict(counts))
    print("WROTE", out_csv.name, OUT_MD.name)
    for needle in [
        "Nord", "Poco X3", "Redmi 12 With Frame", "Redmi 12 5G",
        "iPhone 13 Incell", "iPhone 11 Incell", "Moto G9",
    ]:
        for r in rows:
            if r["model"] == needle or needle.lower() in r["model"].lower():
                print(f"  {r['model']} => {r['classification']} sku={r['sku']}")


if __name__ == "__main__":
    main()
