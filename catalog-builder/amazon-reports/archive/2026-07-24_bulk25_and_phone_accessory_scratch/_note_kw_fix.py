import csv
from pathlib import Path
p = Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.csv")
with p.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
    fields = list(rows[0].keys())

def note(row, msg):
    n = (row.get("notes") or "").strip()
    if msg in n: return
    row["notes"] = (n + "; " if n else "") + msg

for r in rows:
    ag = (r.get("ad_group") or "").strip()
    sm = r.get("stock_model") or ""
    if ag == "Realme C33" or ("Realme C33" in sm and "C33S" not in sm and "C67" not in sm):
        if (r.get("outcome") or "").startswith("created"):
            note(r, "FIX_NEEDED: positives were Phrase-only — add Broad+Exact per Sir 2026-07-22")
    if ag == "Asus Zenfone Max M2" or "Zenfone Max M2" in sm:
        if not (r.get("ad_group") or "").strip():
            r["ad_group"] = "Asus Zenfone Max M2"
            r["ad_group_id"] = "A08680473JXEFV7KTWPKK"
            r["outcome"] = "created_2026-07-22"
        note(r, "FIX_NEEDED: positives were Phrase-only — add Broad+Exact per Sir 2026-07-22")

with p.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(rows)

md = Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.md")
if md.exists():
    t = md.read_text(encoding="utf-8")
    block = "\n### Keyword rule (Sir 2026-07-22)\n- **Positives:** each KEYWORD_PATTERNS §1 string × **Broad + Phrase + Exact** @ ~Rs3. NOT Phrase-only.\n- **Negatives:** unchanged (Phrase qualifiers for base / Exact insurance for Pro).\n- **Needs fix (Phrase-only creates):** Realme C33 `A07067373T44W28UTF7QN`, Asus Zenfone Max M2 `A08680473JXEFV7KTWPKK`.\n"
    if "Keyword rule (Sir 2026-07-22)" not in t:
        md.write_text(t.rstrip()+"\n"+block, encoding="utf-8")
print("ok")