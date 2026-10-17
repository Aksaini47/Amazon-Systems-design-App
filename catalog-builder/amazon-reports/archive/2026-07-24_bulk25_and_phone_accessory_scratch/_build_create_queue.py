import csv, json, re, subprocess, time
from pathlib import Path

AB = r"C:\Users\DELL\AppData\Roaming\npm\agent-browser.cmd"
ROOT = Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports")
PLAN = Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.csv")

def ag_name(r):
    name = r["stock_model"]
    brand = r["brand"]
    name = re.sub(r"\s+With Frame( White)?$", "", name)
    name = re.sub(r"\s+White Incell$", "", name)
    name = re.sub(r"\s+(Incell|CareOG|OLED|Frame)$", "", name)
    if name.endswith(" White"):
        name = name[:-6]
    if brand == "OPPO" and (name.startswith("F") or name.startswith("A") or name.startswith("Reno")):
        name = "Oppo " + name
    return name.strip()

rows = []
seen = set()
for r in csv.DictReader(PLAN.open(encoding="utf-8")):
    if r.get("action") != "create":
        continue
    name = ag_name(r)
    if name in seen:
        continue
    seen.add(name)
    # keyword model string for patterns (lowercase brand-aware)
    model_kw = name
    rows.append({
        "ag": name,
        "asin": r["asin"],
        "status": r["listing_status"],
        "group_type": r["group_type"],
        "negatives": r["negatives"],
        "stock": r["stock_model"],
        "brand": r["brand"],
        "model_kw": model_kw,
    })
rows.sort(key=lambda x: (0 if x["status"] == "Active" else 1, x["ag"]))
(ROOT / "_create_queue.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
print("COUNT", len(rows))
for r in rows:
    print("%s|%s|%s|%s" % (r["status"], r["ag"], r["asin"], r["group_type"]))