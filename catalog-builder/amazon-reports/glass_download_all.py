"""Automate Glass CDP superbatch: run chunked steps via Playwright page.evaluate on manifest.

NOTE: Requires active Seller Central session in Playwright profile OR use
emit_cdp_chunked.py + MCP browser_cdp manually when Glass browser is logged in.

This script uses Playwright persistent profile (may need seller-login first).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")
SUPER_DIR = OUT_DIR / "_cdp_superbatches"
START = datetime.now(UTC)


def _emit_chunked(num: int) -> Path:
    subprocess.check_call([sys.executable, str(SCRIPT_DIR / "emit_cdp_chunked.py"), str(num)])
    return OUT_DIR / f"_cdp_chunked_super_{num:03d}.json"


def _save_response(num: int, response: dict) -> dict:
    resp_path = OUT_DIR / f"_cdp_super_{num:03d}_response.json"
    resp_path.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
    subprocess.check_call([
        sys.executable, str(SCRIPT_DIR / "save_superbatch_response.py"), str(resp_path),
    ])
    (OUT_DIR / f"_cdp_super_{num:03d}_done.marker").write_text(
        datetime.now(UTC).isoformat(), encoding="utf-8",
    )
    value = response.get("result", {}).get("value", [])
    return {
        "downloaded": sum(1 for x in value if x.get("ok")),
        "failed": sum(1 for x in value if not x.get("ok")),
    }


def run_playwright_superbatch(num: int, *, headless: bool = True) -> int:
    """Try Playwright profile session; returns 2 if login required."""
    from run_superbatch_cdp import run_superbatch
    return run_superbatch(num, headless=headless)


def summary() -> dict:
    pdfs = list(OUT_DIR.glob("*.pdf"))
    folder_bytes = sum(p.stat().st_size for p in pdfs)
    end = datetime.now(UTC)
    return {
        "start": START.isoformat(),
        "end": end.isoformat(),
        "duration_s": (end - START).total_seconds(),
        "folder_count": len(pdfs),
        "folder_bytes": folder_bytes,
        "folder_mb": round(folder_bytes / 1024 / 1024, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-super", type=int, default=0)
    parser.add_argument("--to-super", type=int, default=8)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--emit-only", action="store_true")
    args = parser.parse_args()

    for num in range(args.from_super, args.to_super + 1):
        marker = OUT_DIR / f"_cdp_super_{num:03d}_done.marker"
        if marker.exists():
            print(f"skip super_{num:03d} (done)")
            continue
        plan = _emit_chunked(num)
        print(f"emitted {plan}")
        if args.emit_only:
            continue
        code = run_playwright_superbatch(num, headless=not args.headed)
        if code == 2:
            print("SESSION EXPIRED — use Glass browser CDP or mahika seller-login")
            break

    s = summary()
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
