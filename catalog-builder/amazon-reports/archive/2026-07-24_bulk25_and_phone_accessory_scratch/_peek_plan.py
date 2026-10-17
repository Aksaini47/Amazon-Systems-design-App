import csv
from pathlib import Path
p = Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.csv")
with p.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
creates = [r for r in rows if (r.get("action") or "").strip().lower() == "create"]
print("create_rows", len(creates))
# unique by ag_name
seen=set(); uniq=[]
for r in creates:
    n=(r.get("ad_group_name") or r.get("ag_name") or "").strip()
    if not n: 
        # try common cols
        for k in r: 
            if "ad" in k.lower() and "group" in k.lower() and "name" in k.lower():
                n=r[k].strip(); break
    if n and n not in seen:
        seen.add(n); uniq.append(r)
print("unique", len(uniq))
print("cols", list(rows[0].keys())[:20] if rows else None)
for r in uniq[:8]:
    print("---")
    for k,v in r.items():
        if v and str(v).strip():
            print(f"  {k}: {v[:80]}")