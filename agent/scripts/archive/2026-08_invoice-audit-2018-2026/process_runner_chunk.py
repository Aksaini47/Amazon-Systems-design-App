"""Extract chunk array from CDP dump JSON and save PDFs."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

AGENT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")


def main() -> None:
    cdp_path = Path(sys.argv[1])
    chunk_num = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    data = json.loads(cdp_path.read_text(encoding="utf-8"))
    chunk = data["result"]["value"]
    chunk_file = OUT_DIR / f"_runner_chunk_{chunk_num}.json"
    chunk_file.write_text(json.dumps(chunk), encoding="utf-8")
    subprocess.check_call([
        sys.executable,
        str(AGENT / "scripts" / "save_invoice_chunk.py"),
        str(chunk_file),
    ])


if __name__ == "__main__":
    main()
