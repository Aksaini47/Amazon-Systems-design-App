"""Extract Active inventory rows from Seller Central myinventory GQL HAR."""
from __future__ import annotations
import csv, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
HAR = ROOT / "_inv_har_fresh.har"
OUT_CSV = ROOT / "_active_inventory_live_2026-07-31.csv"
OUT_JSON = ROOT / "_active_inventory_live_2026-07-31.json"

def walk(obj, path=""):
    if isinstance(obj, dict):
        yield path, obj
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")

def pick_str(d, *keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return str(d[k]).strip()
    return ""

def looks_like_listing(d):
    keys = {k.lower() for k in d}
    has_title = any(k in keys for k in ("title", "itemname", "productname", "name"))
    has_id = any(k in keys for k in ("asin", "sku", "sellersku", "fnsku"))
    return has_title and has_id

def normalize_row(d):
    title = pick_str(d, "title", "itemName", "productName", "name", "productTitle")
    sku = pick_str(d, "sku", "sellerSku", "sellerSKU", "merchantSku")
    asin = pick_str(d, "asin", "ASIN").upper()
    qty = pick_str(d, "quantity", "qty", "availableQuantity", "fulfillableQuantity")
    price = pick_str(d, "price", "yourPrice", "listingPrice", "amount")
    status = pick_str(d, "status", "listingStatus", "offerStatus") or "Active"
    if not price:
        for k in ("price", "yourPrice", "listingPrice"):
            v = d.get(k)
            if isinstance(v, dict):
                price = pick_str(v, "amount", "value", "price")
                if price: break
    if not qty:
        for k in ("quantity", "availableQuantity", "inventory"):
            v = d.get(k)
            if isinstance(v, dict):
                qty = pick_str(v, "amount", "value", "quantity", "available")
                if qty: break
            elif isinstance(v, (int, float)):
                qty = str(int(v)); break
    if not title and not sku:
        return None
    return {"sku": sku, "asin": asin, "name": title, "qty": qty, "price": price.replace(",", "") if price else "", "status": status.upper() if status else "ACTIVE"}

def extract_from_payload(payload):
    rows, seen = [], set()
    for path, obj in walk(payload):
        if not isinstance(obj, dict) or not looks_like_listing(obj):
            continue
        row = normalize_row(obj)
        if not row: continue
        key = row["sku"] or row["asin"] or row["name"]
        if key in seen: continue
        seen.add(key); rows.append(row)
    return rows

def main():
    har = json.loads(HAR.read_text(encoding="utf-8"))
    all_rows, seen, gql_sizes = [], set(), []
    for e in har["log"]["entries"]:
        if "/myinventory/gql" not in e["request"]["url"]:
            continue
        content = e["response"].get("content") or {}
        text = content.get("text") or ""
        size = content.get("size") or len(text)
        gql_sizes.append(size)
        if not text or size < 500: continue
        try: payload = json.loads(text)
        except Exception: continue
        for row in extract_from_payload(payload):
            key = row["sku"] or row["asin"] or row["name"]
            if key in seen: continue
            seen.add(key); all_rows.append(row)
    if len(all_rows) < 100:
        biggest = ""
        for e in har["log"]["entries"]:
            if "/myinventory/gql" not in e["request"]["url"]: continue
            text = (e["response"].get("content") or {}).get("text") or ""
            if len(text) > len(biggest): biggest = text
        print("fallback parse on gql chars", len(biggest))
        try:
            j = json.loads(biggest)
            sample_keys = set()
            for path, obj in walk(j):
                if isinstance(obj, dict) and len(obj) >= 3:
                    sample_keys.add(tuple(sorted(obj.keys())[:12]))
            print("sample keysets:")
            for ks in list(sample_keys)[:40]:
                print(" ", ks)
        except Exception as ex:
            print("json fail", ex)
    print("gql sizes", sorted(gql_sizes, reverse=True)[:10])
    print("extracted", len(all_rows))
    if all_rows: print("sample", all_rows[:2])
    OUT_JSON.write_text(json.dumps(all_rows, indent=2), encoding="utf-8")
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sku","asin","name","qty","price","status"]); w.writeheader(); w.writerows(all_rows)
    print("wrote", OUT_CSV, OUT_JSON)

if __name__ == "__main__":
    main()