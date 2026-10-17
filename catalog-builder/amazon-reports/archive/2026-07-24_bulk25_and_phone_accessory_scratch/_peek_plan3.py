import csv, json
from pathlib import Path
p = Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.csv")
raw = p.read_bytes()[:200]
print("bom", raw[:4])
with p.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
creates = [r for r in rows if (r.get("action") or "").strip().lower() == "create"]
print("n", len(creates))
r0=creates[0]
for k,v in r0.items():
    print(repr(k), "=", repr(v)[:100])
q=json.loads(Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports\_create_queue.json").read_text(encoding="utf-8"))
print("q0", json.dumps(q[0], indent=2)[:500])
print("q names:")
for i,x in enumerate(q):
    name=x.get("ad_group") or x.get("name") or x.get("ag")
    print(i, name, x.get("asin"), x.get("listing_status") or x.get("status"))