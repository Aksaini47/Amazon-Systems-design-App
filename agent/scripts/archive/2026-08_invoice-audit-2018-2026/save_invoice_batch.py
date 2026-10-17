"""Save a batch of invoice PDFs returned from browser CDP fetch."""
from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

OUT_DIR = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")
LOG_FILE = OUT_DIR / "invoice_download_log.csv"
MANIFEST = OUT_DIR / "invoice_manifest_2021plus.json"


def _slug_type(invoice_type: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", invoice_type.strip())
    return re.sub(r"_+", "_", slug).strip("_")


def _target_filename(inv: dict) -> str:
    return f"{inv['end_date_iso']}_{_slug_type(inv['invoice_type'])}_{inv['invoice_id']}.pdf"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results_json", help="JSON file with batch results from CDP")
    args = parser.parse_args()

    results = json.loads(Path(args.results_json).read_text(encoding="utf-8"))
    manifest = {i["invoice_id"]: i for i in json.loads(MANIFEST.read_text(encoding="utf-8"))}
    log_exists = LOG_FILE.exists()

    with LOG_FILE.open("a", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=["invoice_id", "date", "type", "status", "path", "error", "logged_at"],
        )
        if not log_exists:
            writer.writeheader()

        for item in results:
            inv_id = item["invoice_id"]
            inv = manifest[inv_id]
            end_iso = inv["end_date_iso"]
            inv_type = inv["invoice_type"]

            if item.get("skipped"):
                writer.writerow({
                    "invoice_id": inv_id, "date": end_iso, "type": inv_type,
                    "status": "skipped", "path": item.get("path", ""), "error": "",
                    "logged_at": datetime.now(UTC).isoformat(),
                })
                print(f"SKIP {inv_id}")
                continue

            if not item.get("ok"):
                writer.writerow({
                    "invoice_id": inv_id, "date": end_iso, "type": inv_type,
                    "status": "failed", "path": "", "error": item.get("error", "")[:500],
                    "logged_at": datetime.now(UTC).isoformat(),
                })
                print(f"FAIL {inv_id}: {item.get('error', '')[:120]}")
                continue

            content = base64.b64decode(item["b64"])
            target = OUT_DIR / _target_filename(inv)
            target.write_bytes(content)
            writer.writerow({
                "invoice_id": inv_id, "date": end_iso, "type": inv_type,
                "status": "downloaded", "path": str(target), "error": "",
                "logged_at": datetime.now(UTC).isoformat(),
            })
            print(f"OK {inv_id} -> {target.name} ({len(content):,} B)")


if __name__ == "__main__":
    main()
