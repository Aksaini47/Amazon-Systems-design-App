# -*- coding: utf-8 -*-
"""Rebuild STOCK_ADS_PLAN from stock + listings + Search Term reports (no live Ads)."""
from __future__ import annotations
import csv, re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"c:\Projects\Amazon Systems Design")
stock_path = ROOT / "catalog-builder" / "actual stock.txt"
listings_path = ROOT / "catalog-builder" / "amazon-reports" / "stock_vs_listings_match_report.csv"
reports = [
    Path(r"C:\Users\DELL\Downloads\last year.csv"),
    Path(r"C:\Users\DELL\Downloads\Report_-_07_20_2026T01_28_48.csv"),
]
out_md = ROOT / "agent" / "Graphs & workflows" / "mahika-ads-flow" / "STOCK_ADS_PLAN_2026-07-21.md"
out_csv = ROOT / "agent" / "Graphs & workflows" / "mahika-ads-flow" / "STOCK_ADS_PLAN_2026-07-21.csv"
out_ag = ROOT / "agent" / "Graphs & workflows" / "mahika-ads-flow" / "ADGROUPS_FROM_REPORTS_2026-07-21.csv"

LOCKED = {
    "Oppo F19 / F19 Pro": "A084559912FCQ11YW6QKN",
    "Oppo F17 Pro": "A04445372C07526DZXA0I",
    "IPhone 11 Pro Max": "A08718921A1E5M04CWBET",
}
BRANDS = {"REALME", "VIVO", "OPPO", "ONEPLUS", "APPLE", "SAMSUNG", "XIAOMI/REDMI/POCO", "MIX"}

def strip_qty(s):
    return re.sub(r"\s*-\s*\d+\s*$", "", s).strip()

def clean_id(v):
    v = (v or "").strip()
    v = v.replace('="', "").replace('"', "").strip()
    return v

def load_report_groups():
    # name -> {id, impressions, clicks, spend, sources}
    groups = {}
    for path in reports:
        with path.open(encoding="utf-8-sig", errors="replace") as f:
            r = csv.DictReader(f)
            for row in r:
                name = (row.get("Ad group name") or "").strip()
                if not name:
                    continue
                gid = clean_id(row.get("Ad group ID"))
                # metrics may vary by report version
                def num(key):
                    raw = (row.get(key) or "0").replace(",", "").replace("₹", "").strip()
                    try:
                        return float(raw) if raw not in ("", "—", "-") else 0.0
                    except Exception:
                        return 0.0
                imp = num("Impressions")
                clk = num("Clicks")
                spend = num("Spend") or num("Total cost") or num("Cost")
                key = name.lower()
                g = groups.setdefault(key, {"name": name, "ids": set(), "imp": 0.0, "clk": 0.0, "spend": 0.0, "sources": set()})
                if gid:
                    g["ids"].add(gid)
                g["imp"] += imp
                g["clk"] += clk
                g["spend"] += spend
                g["sources"].add(path.name)
                # prefer canonical casing from more recent report
                if path.name.startswith("Report_"):
                    g["name"] = name
    # flatten
    out = {}
    for k, g in groups.items():
        ids = sorted(g["ids"])
        out[k] = {
            "name": g["name"],
            "id": ids[0] if ids else "",
            "ids": "|".join(ids),
            "imp": g["imp"],
            "clk": g["clk"],
            "spend": round(g["spend"], 2),
            "sources": "|".join(sorted(g["sources"])),
        }
    return out

def norm(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9+]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def stock_search_keys(model):
    n = strip_qty(model).lower()
    for q in ["incell", "careog", "oled", "with frame", "frame", "white", "black"]:
        n = n.replace(q, " ")
    n = re.sub(r"\s+", " ", n).strip()
    keys = [n]
    if re.match(r"^(f\d+|a\d+|reno)", n):
        keys.append("oppo " + n)
    # aliases
    if n.startswith("11x"):
        keys += ["mi 11x", "11x", "mi 11i"]
    if n == "a3" or n.endswith(" a3"):
        keys.append("mi a3")
    if "f19" in n:
        keys += ["oppo f19", "f19 / f19 pro", "f19/f19 pro"]
    if "f17 pro" in n:
        keys += ["oppo f17 pro", "f17 pro"]
    if "11 pro max" in n:
        keys += ["iphone 11 pro max"]
    if "oneplus" in n:
        keys.append(n.replace("oneplus", "1+").strip())
        keys.append(n.replace("oneplus ", "1+ "))
    if "galaxy " in n:
        keys.append(n.replace("galaxy ", ""))
    if "note 10t" in n:
        keys.append("note 10t")
    if "13 pro plus" in n or "13 pro+" in n:
        keys += ["redmi 13 pro", "note 13 pro"]
    if "zenfone" in n:
        keys += ["zenfone max m2", "asus zenfone"]
    if "rog" in n:
        keys += ["rog phone 2", "asus rog"]
    if "reno 10" in n:
        keys += ["reno 10 pro", "oppo reno 10"]
    return [norm(k) for k in keys if k.strip()]

def match_group(model, groups_by_norm):
    keys = stock_search_keys(model)
    # exact / containment scoring
    best = None
    best_score = -1
    for gnorm, g in groups_by_norm.items():
        for k in keys:
            score = -1
            if gnorm == k:
                score = 100 + len(k)
            elif k and k in gnorm:
                score = 50 + len(k)
            elif gnorm and gnorm in k:
                score = 40 + len(gnorm)
            # token overlap
            else:
                kt, gt = set(k.split()), set(gnorm.split())
                if kt and gt and kt.issubset(gt):
                    score = 30 + len(kt)
                elif kt and gt and len(kt & gt) >= max(2, len(kt) - 1):
                    score = 20 + len(kt & gt)
            if score > best_score:
                best_score = score
                best = g
    if best_score < 30:
        return None, best_score
    return best, best_score

def group_type(ag_name, stock_model):
    n = (ag_name or stock_model or "").lower()
    if "f19" in n:
        return "shared"
    if "f9" in n and "pro" in n:
        return "shared"
    if "k20" in n:
        return "shared"
    if "pro max" in n or "promax" in n:
        return "pro_max"
    if re.search(r"\bpro\b", n) or " plus" in n or "pro+" in n:
        return "pro"
    return "base"

def negatives_plan(gtype, ag_name, stock_model):
    name = (ag_name or stock_model or "").lower()
    if gtype == "shared":
        return "none (shared family)"
    if gtype == "base":
        quals = []
        for q in ["pro", "max", "pro max", "plus", "5g", "4g"]:
            if q == "5g" and "5g" in name: continue
            if q == "4g" and "4g" in name: continue
            if q == "pro" and "pro" in name: continue
            if q == "max" and "max" in name: continue
            if q == "plus" and "plus" in name: continue
            if q == "pro max" and ("pro" in name or "max" in name): continue
            quals.append(q)
        # special: Oppo F17 base
        if "f17" in name and "pro" not in name:
            return "Phrase: " + ", ".join(quals + (["f17 pro"] if "f17 pro" not in quals else []))
        return "Phrase: " + ", ".join(quals) if quals else "none"
    return "Never Phrase base substring; Exact insurance from STR if available"

# load
groups = load_report_groups()
groups_by_norm = {norm(g["name"]): g for g in groups.values()}

# write adgroups extract
with out_ag.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["ad_group_name", "ad_group_id", "ids_all", "imp", "clk", "spend", "sources"])
    w.writeheader()
    for g in sorted(groups.values(), key=lambda x: x["name"].lower()):
        w.writerow({
            "ad_group_name": g["name"], "ad_group_id": g["id"], "ids_all": g["ids"],
            "imp": g["imp"], "clk": g["clk"], "spend": g["spend"], "sources": g["sources"],
        })

# stock
rows_stock = []
brand = None
for line in stock_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.lower() == "actual stock":
        continue
    if line in BRANDS:
        brand = line
        continue
    if brand:
        rows_stock.append((brand, strip_qty(line)))

listings = {}
with listings_path.open(encoding="utf-8") as f:
    for r in csv.DictReader(f):
        listings[r["model"].strip()] = r

seen = set()
plan = []
for brand, model in rows_stock:
    if model in seen:
        continue
    seen.add(model)
    L = listings.get(model, {})
    asin = L.get("listing_asin", "")
    match = L.get("listing_match", "")
    lstatus = L.get("listing_status", "")
    title = L.get("listing_title", "")
    g, score = match_group(model, groups_by_norm)
    ag_name = g["name"] if g else ""
    ag_id = g["id"] if g else ""
    # prefer locked console IDs when known by name
    for lk, lid in LOCKED.items():
        if ag_name and norm(ag_name) == norm(lk):
            ag_id = lid
            ag_name = lk
            break
    # special locked names even if report uses different casing
    if "11 pro max" in model.lower() and "iphone" in model.lower():
        ag_name = "IPhone 11 Pro Max"
        ag_id = LOCKED["IPhone 11 Pro Max"]
        g = {"name": ag_name, "id": ag_id, "clk": g["clk"] if g else 0, "spend": g["spend"] if g else 0}
    if "f19" in model.lower():
        ag_name = "Oppo F19 / F19 Pro"
        ag_id = LOCKED["Oppo F19 / F19 Pro"]
        g = {"name": ag_name, "id": ag_id, "clk": (g or {}).get("clk", 0), "spend": (g or {}).get("spend", 0)}
    if "f17 pro" in model.lower():
        ag_name = "Oppo F17 Pro"
        ag_id = LOCKED["Oppo F17 Pro"]
        g = {"name": ag_name, "id": ag_id, "clk": (g or {}).get("clk", 0), "spend": (g or {}).get("spend", 0)}

    gtype = group_type(ag_name, model)
    if not asin:
        action, reason = "skip", "no listing ASIN"
    elif ag_name == "IPhone 11 Pro Max":
        action, reason = "fix_first", "ASIN mix LCD/Oppo — fix before activate"
    elif ag_name:
        action, reason = "activate", f"found in Search Term reports (score={score})"
    else:
        action, reason = "create", "listed, not in either report as ad group"

    notes = []
    if lstatus == "Inactive":
        notes.append("listing Inactive")
    if match == "WRONG_QUALITY":
        notes.append("WRONG_QUALITY ASIN")
    if g:
        notes.append(f"report clk={g.get('clk',0)} spend={g.get('spend',0)}")

    plan.append({
        "brand": brand,
        "stock_model": model,
        "listing_match": match,
        "asin": asin,
        "listing_status": lstatus,
        "ad_group": ag_name,
        "ad_group_id": ag_id,
        "action": action,
        "group_type": gtype,
        "negatives": negatives_plan(gtype, ag_name, model),
        "reason": reason,
        "notes": "; ".join(notes),
        "title": (title or "")[:100],
        "match_score": score,
        "source": "reports",
    })

fields = list(plan[0].keys())
with out_csv.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(plan)

c = Counter(p["action"] for p in plan)
lines = [
    "# Stock Ads Plan — 2026-07-21 (report-based)",
    "",
    "**Sources (no live Ads search):**",
    "- `catalog-builder/actual stock.txt`",
    "- `catalog-builder/amazon-reports/stock_vs_listings_match_report.csv`",
    "- `C:/Users/DELL/Downloads/last year.csv`",
    "- `C:/Users/DELL/Downloads/Report_-_07_20_2026T01_28_48.csv`",
    "",
    f"**Unique ad groups in reports:** {len(groups)} — see [ADGROUPS_FROM_REPORTS_2026-07-21.csv](ADGROUPS_FROM_REPORTS_2026-07-21.csv)",
    "**Campaign:** `TL_EL_SPN_SG_Mobile Screens - Arun`",
    "",
    "## Summary",
    "",
    "| Action | Count |",
    "|---|---:|",
]
for k in ["activate", "create", "fix_first", "skip"]:
    lines.append(f"| {k} | {c.get(k, 0)} |")
lines.append(f"| **Total unique stock models** | **{len(plan)}** |")
lines += ["", "## Create candidates (listed, not in reports)", ""]
for p in plan:
    if p["action"] == "create":
        lines.append(f"- **{p['stock_model']}** — `{p['asin']}` — {p['title']}")
lines += ["", "## Fix-first", ""]
for p in plan:
    if p["action"] == "fix_first":
        lines.append(f"- **{p['stock_model']}** — `{p['ad_group']}` `{p['ad_group_id']}` — {p['reason']}")
lines += ["", "## Activate sample (first 25)", "", "| Stock | Ad group | ID | Negatives |", "|---|---|---|---|"]
for p in [x for x in plan if x["action"]=="activate"][:25]:
    lines.append(f"| {p['stock_model']} | {p['ad_group']} | {p['ad_group_id']} | {p['negatives'][:40]} |")
lines.append("")
out_md.write_text("\n".join(lines), encoding="utf-8")
print("groups", len(groups))
print(dict(c))
print("CREATE:")
for p in plan:
    if p["action"]=="create":
        print(" ", p["stock_model"], p["asin"])
print("FIX:")
for p in plan:
    if p["action"]=="fix_first":
        print(" ", p["stock_model"], p["ad_group"], p["ad_group_id"])
