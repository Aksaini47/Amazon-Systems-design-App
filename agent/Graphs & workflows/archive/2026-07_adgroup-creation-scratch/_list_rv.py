#!/usr/bin/env python3
import csv
from pathlib import Path

p = Path(__file__).resolve().parents[3] / "catalog-builder" / "amazon-reports" / "stock_vs_listings_match_report.csv"
rows = list(csv.DictReader(p.open(encoding="utf-8")))
for r in rows:
    b = (r.get("brand") or "").upper()
    if b not in ("REALME", "VIVO"):
        continue
    title = (r.get("listing_title") or "")[:90]
    print(
        "|".join(
            [
                r.get("brand") or "",
                r.get("model") or "",
                r.get("stock_screen") or "",
                r.get("stock_quality") or "",
                r.get("listing_match") or "",
                r.get("listing_asin") or "",
                r.get("listing_status") or "",
                r.get("listing_screen") or "",
                r.get("listing_quality") or "",
                title,
            ]
        )
    )
