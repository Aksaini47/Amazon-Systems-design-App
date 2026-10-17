"""Extract CDP batch response and save PDFs in one step."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

AGENT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cdp_json", type=Path, help="CDP Runtime.evaluate response JSON")
    parser.add_argument("--batch-num", type=int, default=0)
    args = parser.parse_args()

    data = json.loads(args.cdp_json.read_text(encoding="utf-8"))
    batch = data["result"]["value"]["batch"]
    batch_file = OUT_DIR / f"_batch_{args.batch_num}.json"
    batch_file.write_text(json.dumps(batch), encoding="utf-8")

    subprocess.check_call([
        sys.executable,
        str(AGENT / "scripts" / "save_invoice_batch.py"),
        str(batch_file),
    ])


if __name__ == "__main__":
    main()
