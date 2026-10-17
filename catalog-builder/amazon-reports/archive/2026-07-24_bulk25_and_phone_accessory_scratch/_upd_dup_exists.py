import csv, json
from pathlib import Path

# Update plan for known exists from dup-check + prior session
updates = {
    "Honor 8X": ("A09918911CAM3AZ763ZXP", "exists_enabled_2026-07-22", "exact name existed Paused; enable next"),
    "Infinix Note 10": ("A07695821JLG1Q5C69P30", "exists_enabled_2026-07-22", "exact name existed Paused; enable next"),
}

p = Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.csv")
with p.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f)); fields = list(rows[0].keys())

def match_stock(r, ag):
    sm = (r.get("stock_model") or "")
    # map AG name tokens into stock
    return ag.replace("Galaxy ", "Galaxy ") in sm or ag in sm or ag.replace(" 4G","") in sm

# more reliable: match by create queue ag field via stock keywords
key_map = {
    "Honor 8X": "Honor 8X",
    "Infinix Note 10": "Infinix Note 10",
}
for r in rows:
    if r.get("action") != "create":
        continue
    sm = r.get("stock_model") or ""
    for ag, (gid, outcome, note) in updates.items():
        if key_map[ag] in sm:
            r["ad_group"] = ag
            r["ad_group_id"] = gid
            r["outcome"] = outcome
            n = (r.get("notes") or "").strip()
            r["notes"] = (n + "; " if n else "") + note

with p.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

created = [r for r in rows if (r.get("outcome") or "").startswith("created")]
exists = [r for r in rows if "exists" in (r.get("outcome") or "")]
pending = [r for r in rows if r.get("action")=="create" and (r.get("outcome") or "").startswith("pending")]
print("created", len(created), [r.get("ad_group") or r.get("stock_model") for r in created])
print("existsish", len(exists))
print("pending_create", len(pending))