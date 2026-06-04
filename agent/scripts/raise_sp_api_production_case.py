"""Legacy entry — prefer: python -m mahika.cli support-case

Usage:
    .venv\\Scripts\\python.exe scripts\\raise_sp_api_production_case.py
    .venv\\Scripts\\python.exe scripts\\raise_sp_api_production_case.py --submit
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

AGENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENT / "src"))

from mahika.playwright.support_case_flow import run_support_case_flow  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submit", action="store_true", help="Auto-submit support case")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    ok = run_support_case_flow(headless=args.headless, submit=args.submit)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
