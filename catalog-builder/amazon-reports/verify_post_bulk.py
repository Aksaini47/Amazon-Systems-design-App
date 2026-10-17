"""Re-run quality check assuming bulk_create_25 SKUs are now live."""
from __future__ import annotations

import csv
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LISTINGS = ROOT / "All+Listings+Report_05-12-2026.txt"
MERGED = ROOT / "All+Listings+Report_05-12-2026_merged_bulk25.txt"
REVIEW = ROOT / "bulk_create_25_review.csv"
MISSING_BEFORE = ROOT / "stock_missing_this_quality.csv"
CHECK = ROOT / "stock_inventory_check.py"


def append_pending_listings() -> int:
    """Append review CSV rows as minimal All-Listings TSV lines."""
    header = LISTINGS.read_text(encoding="utf-8-sig").splitlines()[0]
    shutil.copy2(LISTINGS, MERGED)
    existing_skus = set()
    for line in MERGED.read_text(encoding="utf-8-sig").splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) > 3:
            existing_skus.add(cols[3].strip())

    added = 0
    with REVIEW.open(encoding="utf-8") as f, MERGED.open("a", encoding="utf-8") as out:
        for row in csv.DictReader(f):
            sku = row["new_sku"].strip()
            if sku in existing_skus:
                continue
            title = row["title"]
            price = row["sell_price"].split(".")[0]
            mrp = row["mrp"].split(".")[0]
            qty = row.get("qty", "100")
            # cols: item-name, desc, listing-id, sku, price, qty, ... status col 29
            cols = [""] * 30
            cols[0] = title
            cols[1] = "bulk_create_25 pending merge"
            cols[2] = f"BULK25{sku}"
            cols[3] = sku
            cols[4] = price
            cols[5] = qty
            cols[29] = "Active"
            out.write("\t".join(cols) + "\n")
            added += 1
    print(f"Merged listings: +{added} rows -> {MERGED.name}")
    return added


def patch_check_listings_path() -> None:
    src = CHECK.read_text(encoding="utf-8")
    patched = src.replace(
        'LISTINGS_FILE = ROOT / "All+Listings+Report_05-12-2026.txt"',
        f'LISTINGS_FILE = ROOT / "{MERGED.name}"',
    )
    (ROOT / "_stock_inventory_check_merged.py").write_text(patched, encoding="utf-8")


def main() -> int:
    if not REVIEW.is_file():
        print("Missing review CSV")
        return 1
    n = append_pending_listings()
    patch_check_listings_path()
    print("Running quality check with merged listings…")
    subprocess.run([sys.executable, str(ROOT / "_stock_inventory_check_merged.py")], check=True)

    before = sum(1 for _ in MISSING_BEFORE.open(encoding="utf-8")) - 1 if MISSING_BEFORE.is_file() else 25
    after_path = ROOT / "stock_missing_this_quality.csv"
    after = sum(1 for _ in after_path.open(encoding="utf-8")) - 1 if after_path.is_file() else -1
    summary = ROOT / "bulk_create_25_verify_summary.txt"
    summary.write_text(
        f"Before missing-this-quality: {before} models\n"
        f"After (merged listings): {after} models\n"
        f"New SKUs injected: {n}\n"
        f"Note: Re-run with fresh All Listings report after Amazon processing completes.\n",
        encoding="utf-8",
    )
    print(summary.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
