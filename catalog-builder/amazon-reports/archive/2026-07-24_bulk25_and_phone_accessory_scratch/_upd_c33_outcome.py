import csv
from pathlib import Path
from datetime import datetime

p = Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.csv")
with p.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

def touch(row, outcome, note=None):
    row["outcome"] = outcome
    if note:
        n = (row.get("notes") or "").strip()
        row["notes"] = (n + "; " if n else "") + note

for r in rows:
    sm = (r.get("stock_model") or "")
    title = (r.get("title") or "")
    if r.get("action") == "create" and "Realme C33" in sm and "C33S" not in sm and "C67" not in sm:
        r["ad_group"] = "Realme C33"
        r["ad_group_id"] = "A07067373T44W28UTF7QN"
        touch(r, "created_2026-07-22", "live ASIN B0FRSWZQF1S (plan B0C94R2YHG stale); Phrase kws ~Rs3; Phrase neg pro/max/pro max/plus (4g/5g blocked by Ads UI)")
    if r.get("action") == "create" and "Realme C67" in sm:
        r["ad_group"] = "Realme C67"
        touch(r, "exists_enabled_skip_create", "already Enabled in campaign")

with p.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

# append md outcomes
md = Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.md")
if md.exists():
    text = md.read_text(encoding="utf-8")
    block = "\n### Create batch 2026-07-22 (session continue)\n- **Realme C33** created `A07067373T44W28UTF7QN` — ASIN `B0FRSWZQF1S` (plan ASIN stale), Phrase positives @ ~Rs3, Phrase neg `pro/max/pro max/plus` (Ads UI blocks Phrase `4g`/`5g`).\n- **Realme C67** skip create — already Enabled.\n"
    if "Create batch 2026-07-22 (session continue)" not in text:
        md.write_text(text.rstrip() + "\n" + block, encoding="utf-8")
print("updated")
pending = sum(1 for r in rows if r.get("action")=="create" and (r.get("outcome") or "").startswith("pending"))
print("pending_create", pending)