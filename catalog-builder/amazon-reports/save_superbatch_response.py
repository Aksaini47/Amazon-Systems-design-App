"""Save CDP superbatch response JSON to PDF files."""
from __future__ import annotations

import argparse
import base64
import csv
import json
import re
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_OUT = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")


def _slug_type(invoice_type: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", invoice_type.strip())
    return re.sub(r"_+", "_", slug).strip("_")


def _target_filename(inv: dict) -> str:
    return f"{inv['end_date_iso']}_{_slug_type(inv['invoice_type'])}_{inv['invoice_id']}.pdf"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("response_json", type=Path)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Manifest JSON (default: <out-dir>/invoice_manifest_2020plus.json)",
    )
    args = parser.parse_args()

    out_dir = args.out_dir
    manifest_path = args.manifest or (out_dir / "invoice_manifest_2020plus.json")
    log_file = out_dir / "invoice_download_log.csv"

    data = json.loads(args.response_json.read_text(encoding="utf-8"))
    results = data["result"]["value"]
    manifest = {i["invoice_id"]: i for i in json.loads(manifest_path.read_text(encoding="utf-8"))}
    stats = {"downloaded": 0, "failed": 0, "skipped": 0}

    log_exists = log_file.exists()
    with log_file.open("a", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=["invoice_id", "date", "type", "status", "path", "error", "logged_at"],
        )
        if not log_exists:
            writer.writeheader()

        for item in results:
            inv_id = item["invoice_id"]
            inv = manifest[inv_id]
            target = out_dir / _target_filename(inv)
            if target.exists():
                stats["skipped"] += 1
                writer.writerow({
                    "invoice_id": inv_id, "date": inv["end_date_iso"], "type": inv["invoice_type"],
                    "status": "skipped", "path": str(target), "error": "",
                    "logged_at": datetime.now(UTC).isoformat(),
                })
                continue
            if not item.get("ok"):
                stats["failed"] += 1
                writer.writerow({
                    "invoice_id": inv_id, "date": inv["end_date_iso"], "type": inv["invoice_type"],
                    "status": "failed", "path": "", "error": item.get("error", "")[:500],
                    "logged_at": datetime.now(UTC).isoformat(),
                })
                print(f"FAIL {inv_id}: {item.get('error', '')[:80]}")
                continue
            content = base64.b64decode(item["b64"])
            target.write_bytes(content)
            stats["downloaded"] += 1
            writer.writerow({
                "invoice_id": inv_id, "date": inv["end_date_iso"], "type": inv["invoice_type"],
                "status": "downloaded", "path": str(target), "error": "",
                "logged_at": datetime.now(UTC).isoformat(),
            })

    print(stats)


if __name__ == "__main__":
    main()
