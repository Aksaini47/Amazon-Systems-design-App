"""Pull invoice results from browser memory in chunks and save PDFs."""
from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

OUT_DIR = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")
LOG_FILE = OUT_DIR / "invoice_download_log.csv"
AGENT = Path(__file__).resolve().parents[1]


def _slug_type(invoice_type: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", invoice_type.strip())
    return re.sub(r"_+", "_", slug).strip("_")


def _target_filename(item: dict) -> str:
    return f"{item['end_date_iso']}_{_slug_type(item['invoice_type'])}_{item['invoice_id']}.pdf"


def _existing_for_invoice(invoice_id: str) -> Path | None:
    matches = list(OUT_DIR.glob(f"*_{invoice_id}.pdf"))
    return matches[0] if matches else None


def save_chunk(items: list[dict], writer, log_fp) -> tuple[int, int, int]:
    downloaded = skipped = failed = 0
    for item in items:
        inv_id = item["invoice_id"]
        inv_type = item.get("invoice_type", "")
        end_iso = item.get("end_date_iso", "")

        existing = _existing_for_invoice(inv_id)
        if existing:
            skipped += 1
            writer.writerow({
                "invoice_id": inv_id, "date": end_iso, "type": inv_type,
                "status": "skipped", "path": str(existing), "error": "",
                "logged_at": datetime.now(UTC).isoformat(),
            })
            continue

        try:
            content = base64.b64decode(item["b64"])
            if not content.startswith(b"%PDF"):
                raise RuntimeError("Not a PDF")
            target = OUT_DIR / _target_filename(item)
            target.write_bytes(content)
            downloaded += 1
            writer.writerow({
                "invoice_id": inv_id, "date": end_iso, "type": inv_type,
                "status": "downloaded", "path": str(target), "error": "",
                "logged_at": datetime.now(UTC).isoformat(),
            })
            print(f"OK {inv_id}")
        except Exception as exc:
            failed += 1
            writer.writerow({
                "invoice_id": inv_id, "date": end_iso, "type": inv_type,
                "status": "failed", "path": "", "error": str(exc)[:500],
                "logged_at": datetime.now(UTC).isoformat(),
            })
            print(f"FAIL {inv_id}: {exc}")
    log_fp.flush()
    return downloaded, skipped, failed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("chunk_json", type=Path)
    args = parser.parse_args()

    items = json.loads(args.chunk_json.read_text(encoding="utf-8"))
    log_exists = LOG_FILE.exists()
    fieldnames = ["invoice_id", "date", "type", "status", "path", "error", "logged_at"]

    with LOG_FILE.open("a", encoding="utf-8", newline="") as log_fp:
        writer = csv.DictWriter(log_fp, fieldnames=fieldnames)
        if not log_exists:
            writer.writeheader()
        d, s, f = save_chunk(items, writer, log_fp)
    print(f"chunk: downloaded={d} skipped={s} failed={f}")


if __name__ == "__main__":
    main()
