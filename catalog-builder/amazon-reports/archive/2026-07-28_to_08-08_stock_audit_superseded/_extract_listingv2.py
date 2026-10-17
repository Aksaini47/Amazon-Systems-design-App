import json, csv
from pathlib import Path
ROOT = Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports")
har=json.loads((ROOT/"_inv_har_fresh.har").read_text(encoding="utf-8"))
biggest=""
for e in har["log"]["entries"]:
    if "/myinventory/gql" not in e["request"]["url"]:
        continue
    text=(e["response"].get("content") or {}).get("text") or ""
    if len(text)>len(biggest):
        biggest=text
j=json.loads(biggest)

def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)

listings=[]
for o in walk(j):
    if o.get("__typename") == "ListingV2":
        listings.append(o)
print("ListingV2 count", len(listings))
if listings:
    print(json.dumps(listings[0], indent=2)[:2000])

rows=[]
for L in listings:
    data = L.get("listingData") or L.get("myiServiceListingData") or {}
    # try common nests
    if not data:
        for k,v in L.items():
            if isinstance(v, dict) and v.get("__typename")=="MYIServiceListingData":
                data=v; break
    avail = None
    price = None
    status = None
    for k,v in L.items():
        if isinstance(v, dict):
            tn=v.get("__typename")
            if tn=="Availability": avail=v
            elif tn in ("PriceAndShipping","Pricing","Price"): price=v
            elif tn=="ListingStatus": status=v
    # deeper search
    if avail is None or price is None or status is None:
        for o in walk(L):
            tn=o.get("__typename")
            if tn=="Availability" and avail is None: avail=o
            if tn=="PriceAndShipping" and price is None: price=o
            if tn=="ListingStatus" and status is None: status=o
            if tn=="MYIServiceListingData" and not data: data=o
    title = (data or {}).get("title") or L.get("title") or ""
    sku = (data or {}).get("sku") or L.get("sku") or ""
    asin = (data or {}).get("asin") or L.get("asin") or ""
    qty = ""
    if avail:
        qty = avail.get("quantity")
        if qty is None and avail.get("availabilities"):
            qty = avail["availabilities"][0].get("quantity")
    pr=""
    if price:
        # PriceAndShipping often has yourPrice/price
        for key in ("yourPrice","price","listingPrice","Price"):
            pv=price.get(key) if isinstance(price, dict) else None
            if isinstance(pv, dict):
                cur=pv.get("price") if "price" in pv else pv
                if isinstance(cur, dict) and cur.get("amount") is not None:
                    pr=str(cur["amount"]); break
                if pv.get("amount") is not None:
                    pr=str(pv["amount"]); break
    st=""
    if status:
        st = status.get("status") or status.get("value") or status.get("listingStatus") or ""
        if isinstance(st, dict):
            st = st.get("value") or st.get("status") or ""
    rows.append({
        "sku": sku, "asin": asin, "name": title,
        "qty": "" if qty is None else str(qty),
        "price": pr,
        "status": str(st or "ACTIVE").upper(),
    })

print("rows", len(rows), "with qty", sum(1 for r in rows if r["qty"]!=""), "qty>0", sum(1 for r in rows if r["qty"].isdigit() and int(r["qty"])>0))
print("sample", rows[:3])
# write
out=ROOT/"_active_inventory_live_2026-07-31.csv"
with out.open("w", newline="", encoding="utf-8") as f:
    w=csv.DictWriter(f, fieldnames=["sku","asin","name","qty","price","status"])
    w.writeheader(); w.writerows(rows)
(ROOT/"_active_inventory_live_2026-07-31.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
print("wrote", out)