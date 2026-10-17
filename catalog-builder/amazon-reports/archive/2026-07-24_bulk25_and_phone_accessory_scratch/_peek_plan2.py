import csv, json
from pathlib import Path
p = Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.csv")
with p.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
creates = [r for r in rows if (r.get("action") or "").strip().lower() == "create"]
seen=set(); uniq=[]
for r in creates:
    n=(r.get("ad_group") or "").strip()
    if n and n not in seen:
        seen.add(n); uniq.append(r)
print("unique_ags", len(uniq))
# group by outcome
from collections import Counter
oc=Counter((r.get("outcome") or "").strip() or "(empty)" for r in creates)
print("outcomes", dict(oc))
active=[r for r in uniq if (r.get("listing_status") or "").lower().startswith("active") or (r.get("listing_status") or "")=="Active"]
inactive=[r for r in uniq if r not in active]
print("active_unique", len(active), "other", len(inactive))
for r in uniq:
    print(f"{r['ad_group']}|{r['asin']}|{r.get('listing_status')}|{r.get('group_type')}|{r.get('negatives')}|{r.get('outcome')}")
qpath=Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports\_create_queue.json")
if qpath.exists():
    q=json.loads(qpath.read_text(encoding='utf-8'))
    print("queue_len", len(q) if isinstance(q,list) else type(q))