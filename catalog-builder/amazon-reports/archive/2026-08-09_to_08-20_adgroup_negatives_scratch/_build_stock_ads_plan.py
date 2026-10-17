"""Build stock x listings x known-ad-groups plan sheet."""
from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
stock_path = ROOT / "catalog-builder" / "actual stock.txt"
csv_path = ROOT / "catalog-builder" / "amazon-reports" / "stock_vs_listings_match_report.csv"
out_md = ROOT / "agent" / "Graphs & workflows" / "mahika-ads-flow" / "STOCK_ADS_PLAN_2026-07-21.md"
out_csv = ROOT / "agent" / "Graphs & workflows" / "mahika-ads-flow" / "STOCK_ADS_PLAN_2026-07-21.csv"

LOCKED_IDS = {
    "Oppo F19 / F19 Pro": "A084559912FCQ11YW6QKN",
    "Oppo F17 Pro": "A04445372C07526DZXA0I",
    "IPhone 11 Pro Max": "A08718921A1E5M04CWBET",
    "Honor 8C": "A06786752U1LP4HHAFXEX",
}

# Only these lines are brand section headers — not stock models like "F19 OLED" / "11X OLED".
KNOWN_BRAND_HEADERS = frozenset(
    {
        "REALME",
        "VIVO",
        "OPPO",
        "ONEPLUS",
        "APPLE",
        "SAMSUNG",
        "XIAOMI/REDMI/POCO",
        "MIX",
    }
)


def strip_qty(s: str) -> str:
    return re.sub(r"\s*-\s*\d+\s*$", "", s).strip()


def model_key(stock_model: str) -> str:
    n = strip_qty(stock_model).lower()
    for q in [
        "incell",
        "careog",
        "oled",
        "with frame",
        "frame",
        "white",
        "black",
    ]:
        n = n.replace(q, " ")
    n = re.sub(r"\s+", " ", n).strip()
    if re.match(r"^(f\d+|a\d+|reno)", n):
        n = "oppo " + n
    return n


def lookup_ag(stock_model: str) -> str | None:
    key = model_key(stock_model)
    rules: list[tuple[str, str | None]] = [
        ("f17 pro", "Oppo F17 Pro"),
        ("f19", "Oppo F19 / F19 Pro"),
        ("11 pro max", "IPhone 11 Pro Max"),
        ("13 pro max", "Iphone 13 Pro Max"),
        ("14 pro max", "Iphone 14 Pro Max"),
        ("13 pro", "Iphone 13 Pro"),
        ("iphone 13", "Iphone 13"),
        ("iphone 11", "Iphone 11"),
        ("8 plus", "Iphone 8 Plus"),
        ("iphone xs", "iPhone X"),
        ("iphone 8", "Iphone 8"),
        ("nord ce 2 lite", "1+ Nord CE 2 Lite"),
        ("oneplus nord", "1+ Nord"),
        ("oneplus 10 pro", "1+ 10 Pro"),
        ("oneplus 8 pro", "1+ 8 Pro"),
        ("oneplus 8", "1+ 8"),
        ("oneplus 7", "1+ 7"),
        ("10r", "1+ 10R"),
        ("11r", "1+ 11R"),
        ("9rt", "1+ 9RT"),
        ("oneplus 9", "1+ 9"),
        ("s20 fe", "Galaxy S20 FE"),
        ("s21 fe", "Galaxy S21 FE"),
        ("j7 next", "Galaxy J7 Next"),
        ("j7 max", "Galaxy J7 Max"),
        ("j7 2016", "Galaxy J7 Prime"),
        ("j7 2015", "Galaxy J7"),
        ("a30s", "Galaxy A30s"),
        ("a73", "Galaxy A73"),
        ("a32", "Galaxy A32"),
        ("a31", "Galaxy A31"),
        ("a10", "Galaxy A10"),
        ("oppo a53", "Oppo A53"),
        ("oppo a57", "Oppo A57"),
        ("oppo a54", "Oppo A54"),
        ("oppo f9", "Oppo F9"),
        ("oppo f5", "Oppo F5"),
        ("oppo f27", None),
        ("reno 10", None),
        ("realme 7i", None),
        ("realme c21", None),
        ("realme 13 pro", None),
        ("realme 3 pro", None),
        ("realme 7 pro", "Realme 7 Pro"),
        ("realme 11 pro", "Realme 11 Pro"),
        ("realme c67", "Realme C67"),
        ("realme 8i", "Realme 8i"),
        ("realme 8", "Realme 8"),
        ("realme 9i", "Realme 9i"),
        ("realme 9", "Realme 9"),
        ("realme c33", "Realme C33"),
        ("realme c30", "Realme C30"),
        ("realme c53", "Realme C53"),
        ("vivo y33s", "Vivo Y33s"),
        ("vivo y22", "Vivo Y22"),
        ("vivo t1", "Vivo T1"),
        ("vivo t2x", "Vivo T2x"),
        ("vivo v11 pro", "Vivo V11 Pro"),
        ("vivo v17", "Vivo V17"),
        ("vivo v15", None),
        ("vivo x70", None),
        ("vivo x80", None),
        ("note 10t", None),
        ("13 pro plus", None),
        ("redmi note 5", "Redmi Note 5"),
        ("redmi 4a", "Redmi 4A"),
        ("redmi 12", "Redmi 12"),
        ("redmi 10 power", "Redmi 10 Power"),
        ("note 6 pro", "Redmi Note 6 Pro"),
        ("note 7", "Redmi Note 7"),
        ("k20", "Redmi K20/K20 Pro"),
        ("11x", "Mi 11X"),
        (" a3", "Mi A3"),
        ("poco x3", "Poco X3"),
        ("poco m4", "Poco M4"),
        ("nothing phone", "Nothing Phone 1"),
        ("infinix note 10", "Infinix Note 10"),
        ("infinix hot 9", "Infinix Hot 9"),
        ("infinix note 11", "Infinix Note 11S"),
        ("honor 7x", "Honor 7X"),
        ("honor 8c", "Honor 8C"),
        ("honor 8x", "Honor 8X"),
        ("honor x9b", None),
        ("nokia g10", "Nokia G10"),
        ("nokia g20", "Nokia G20"),
        ("nokia g21", None),
        ("nokia c3", None),
        ("moto g9", "Moto G9"),
        ("edge 50", "Moto Edge 50 Fusion"),
        ("moto g34", "Moto G34"),
        ("zenfone", None),
        ("rog phone", None),
    ]
    best: str | None = None
    best_len = -1
    found = False
    for needle, ag in rules:
        if needle in key:
            if len(needle) > best_len:
                best = ag
                best_len = len(needle)
                found = True
    if found:
        return best
    if key.strip() in ("a3",) or (key.endswith(" a3") and "oppo" not in key):
        return "Mi A3"
    return None


def group_type(ag_name: str | None, stock_model: str) -> str:
    n = (ag_name or stock_model or "").lower()
    if "f19" in n:
        return "shared"
    if "k20" in n:
        return "shared"
    if "f9" in n:
        return "shared"
    if "pro max" in n or "promax" in n:
        return "pro_max"
    if re.search(r"\bpro\b", n) or " plus" in n or "pro+" in n:
        return "pro"
    return "base"


def negatives_plan(gtype: str, ag_name: str | None, stock_model: str) -> str:
    name = (ag_name or stock_model or "").lower()
    if gtype == "shared":
        return "none (shared family)"
    if gtype == "base":
        quals = []
        for q in ["pro", "max", "pro max", "plus", "5g", "4g"]:
            if q == "5g" and "5g" in name:
                continue
            if q == "4g" and "4g" in name:
                continue
            if q == "pro" and "pro" in name:
                continue
            if q == "max" and "max" in name:
                continue
            if q == "plus" and "plus" in name:
                continue
            if q == "pro max" and ("pro" in name or "max" in name):
                continue
            quals.append(q)
        return "Phrase: " + ", ".join(quals) if quals else "none"
    return "Never Phrase base substring; Exact insurance from STR if available"


def main() -> None:
    rows_stock: list[tuple[str, str]] = []
    brand = None
    for line in stock_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.lower() == "actual stock":
            continue
        if line in KNOWN_BRAND_HEADERS:
            brand = line
            continue
        if brand:
            rows_stock.append((brand, strip_qty(line)))

    listings: dict[str, dict] = {}
    with csv_path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            listings[r["model"].strip()] = r

    seen: set[str] = set()
    plan: list[dict] = []
    for brand, model in rows_stock:
        if model in seen:
            continue
        seen.add(model)
        L = listings.get(model, {})
        asin = L.get("listing_asin", "")
        match = L.get("listing_match", "")
        lstatus = L.get("listing_status", "")
        title = L.get("listing_title", "")
        ag = lookup_ag(model)
        gtype = group_type(ag, model)

        if not asin:
            action, reason = "skip", "no listing ASIN"
        elif ag == "IPhone 11 Pro Max":
            action, reason = "fix_first", "ASIN mix LCD/Oppo — fix before activate"
        elif ag:
            action, reason = "activate", "existing group (confirm live)"
        else:
            action, reason = "create", "listed, no known ad group"

        notes = []
        if lstatus == "Inactive":
            notes.append("listing Inactive — may be ineligible")
        if match == "WRONG_QUALITY":
            notes.append("WRONG_QUALITY ASIN")

        plan.append(
            {
                "brand": brand,
                "stock_model": model,
                "listing_match": match,
                "asin": asin,
                "listing_status": lstatus,
                "ad_group": ag or "",
                "ad_group_id": LOCKED_IDS.get(ag or "", ""),
                "action": action,
                "group_type": gtype,
                "negatives": negatives_plan(gtype, ag, model),
                "reason": reason,
                "notes": "; ".join(notes),
                "title": (title or "")[:100],
                "live_confirmed": "",
                "outcome": "",
            }
        )

    fields = list(plan[0].keys())
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(plan)

    c = Counter(p["action"] for p in plan)
    lines = [
        "# Stock Ads Plan — 2026-07-21",
        "",
        "**Sources:** `catalog-builder/actual stock.txt` + `stock_vs_listings_match_report.csv` + STOCK_VS_ADGROUPS known names",
        "**Campaign:** `TL_EL_SPN_SG_Mobile Screens - Arun` (`A038001030A5E0IF4R8UV`)",
        "**CSV:** [STOCK_ADS_PLAN_2026-07-21.csv](STOCK_ADS_PLAN_2026-07-21.csv)",
        "",
        "## Summary",
        "",
        "| Action | Count |",
        "|---|---:|",
    ]
    for k in ["activate", "create", "fix_first", "skip"]:
        lines.append(f"| {k} | {c.get(k, 0)} |")
    lines.append(f"| **Total unique stock models** | **{len(plan)}** |")
    lines += [
        "",
        "## Actions detail",
        "",
        "| Stock | ASIN | Match | Ad group | Action | Negatives | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in plan:
        ag = p["ad_group"] or "—"
        neg = (p["negatives"] or "")[:50]
        note = p["notes"] or p["reason"]
        lines.append(
            f"| {p['stock_model']} | {p['asin']} | {p['listing_match']} | {ag} | **{p['action']}** | {neg} | {note} |"
        )
    lines += ["", "## Create candidates (listed, no known AG)", ""]
    for p in plan:
        if p["action"] == "create":
            lines.append(f"- **{p['stock_model']}** — `{p['asin']}` — {p['title']}")
    lines += [
        "",
        "## Live confirm required",
        "Browser must re-search each create/activate candidate by exact model name before mutate (virtualization caveat).",
        "",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", out_md)
    print("Wrote", out_csv)
    print(dict(c))
    print("CREATE:")
    for p in plan:
        if p["action"] == "create":
            print(" ", p["stock_model"], p["asin"])


if __name__ == "__main__":
    main()
