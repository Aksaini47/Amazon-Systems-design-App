import csv
from pathlib import Path
p = Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.csv")
with p.open(encoding="utf-8-sig", newline="") as f:
    rows=list(csv.DictReader(f)); fields=list(rows[0].keys())
for r in rows:
    if r.get("action")=="create" and "Galaxy A10" in (r.get("stock_model") or ""):
        r["ad_group"]="Galaxy A10"
        r["ad_group_id"]="A08727522R6N51EWF5W6Z"
        r["outcome"]="exists_enabled_2026-07-22"
        n=(r.get("notes") or "").strip()
        r["notes"]=(n+"; " if n else "")+"existed Paused; Enabled this session (no recreate)"
with p.open("w",encoding="utf-8",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
md=Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.md")
if md.exists():
    t=md.read_text(encoding="utf-8")
    line="- **Galaxy A10** existed Paused `A08727522R6N51EWF5W6Z` — Enabled (no recreate).\n"
    if "Galaxy A10** existed" not in t:
        md.write_text(t.rstrip()+"\n"+line, encoding="utf-8")
print("ok")