import csv, json
from pathlib import Path
p = Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.csv")
with p.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
for r in rows:
    if "C33" in (r.get("stock_model") or "") or "C33" in (r.get("title") or ""):
        print({k:r[k] for k in r if r[k]})
q=json.loads(Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports\_create_queue.json").read_text(encoding="utf-8"))
for x in q:
    if "C33" in x.get("ag",""):
        print("Q", x)