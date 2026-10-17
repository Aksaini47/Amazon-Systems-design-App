import csv
from pathlib import Path
p = Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.csv")
with p.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f)); fields=list(rows[0].keys())
for r in rows:
    if r.get("action")=="create" and "Zenfone Max M2" in (r.get("stock_model") or ""):
        r["ad_group"]="Asus Zenfone Max M2"
        r["ad_group_id"]="A08680473JXEFV7KTWPKK"
        r["outcome"]="created_2026-07-22"
        n=(r.get("notes") or "").strip()
        r["notes"]=(n+"; " if n else "")+"Phrase kws ~Rs3; Phrase neg pro/plus (max in own name; 4g/5g skipped Ads UI)"
with p.open("w", encoding="utf-8", newline="") as f:
    w=csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
md=Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.md")
if md.exists():
    t=md.read_text(encoding="utf-8")
    line="- **Asus Zenfone Max M2** created `A08680473JXEFV7KTWPKK` — Phrase kws ~Rs3; Phrase neg `pro/plus` (skip max: in own name; skip 4g/5g Ads UI).\n"
    if "Asus Zenfone Max M2** created" not in t:
        md.write_text(t.rstrip()+"\n"+line, encoding="utf-8")
pending=sum(1 for r in rows if r.get("action")=="create" and (r.get("outcome") or "").startswith("pending"))
print("pending", pending)