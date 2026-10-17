"""Run all CDP superbatches via Glass browser — reads request JSON, writes response, saves PDFs."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

OUT_DIR = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")
SUPER_DIR = OUT_DIR / "_cdp_superbatches"
SCRIPT_DIR = Path(__file__).resolve().parent


def pending_superbatches() -> list[int]:
    done = {int(p.stem.split("_")[-1]) for p in OUT_DIR.glob("_cdp_super_*_done.marker")}
    all_nums = sorted(int(p.stem.split("_")[1]) for p in SUPER_DIR.glob("super_*.json"))
    return [n for n in all_nums if n not in done]


def save_response(num: int, response: dict) -> dict:
    resp_file = OUT_DIR / f"_cdp_super_{num:03d}_response.json"
    resp_file.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
    subprocess.check_call([
        sys.executable,
        str(SCRIPT_DIR / "save_superbatch_response.py"),
        str(resp_file),
    ])
    (OUT_DIR / f"_cdp_super_{num:03d}_done.marker").write_text(
        datetime.now(UTC).isoformat(), encoding="utf-8",
    )
    value = response.get("result", {}).get("value", [])
    ok = sum(1 for x in value if x.get("ok"))
    fail = sum(1 for x in value if not x.get("ok"))
    return {"ok": ok, "fail": fail}


def main() -> None:
    pending = pending_superbatches()
    print(json.dumps({"pending_superbatches": pending, "count": len(pending)}))


if __name__ == "__main__":
    main()
