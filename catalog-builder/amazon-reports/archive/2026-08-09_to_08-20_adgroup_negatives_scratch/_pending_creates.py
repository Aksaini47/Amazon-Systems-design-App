import csv
from pathlib import Path

p = Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.csv")
rows = list(csv.DictReader(p.open(encoding="utf-8-sig")))
for r in rows:
    for k in list(r.keys()):
        if "brand" in k.lower():
            r["brand"] = r[k]

need = []
for r in rows:
    if (r.get("action") or "").lower() != "create":
        continue
    o = r.get("outcome") or ""
    ol = o.lower()
    done = any(m in ol for m in (
        "exists", "created", "enabled", "fixed", "skipped", "duplicate",
        "fail_skip", "failed_skip",
    ))
    if done and "still_blocked" not in ol and "failed_create" not in ol:
        continue
    if ol in ("pending", "still_blocked", "failed_create_wizard", "") or "failed_create" in ol or "still_blocked" in ol:
        need.append(r)

print("NEED", len(need))
for r in need:
    notes = (r.get("notes") or "")[:90]
    print(" | ".join([
        r.get("brand", ""),
        r["stock_model"],
        r["asin"],
        r.get("listing_status", ""),
        r.get("outcome", ""),
        notes,
    ]))
