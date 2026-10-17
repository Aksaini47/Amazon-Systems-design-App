"""Save Glass browser document.cookie export to Playwright cookie JSON format."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

STORAGE = Path(r"c:\Projects\Amazon Systems Design\data\mahika")
COOKIE_FILE = STORAGE / "sessions" / "seller_central_cookies.json"


def parse_cookie_string(raw: str) -> list[dict]:
    cookies: list[dict] = []
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies.append({
            "name": name.strip(),
            "value": value.strip(),
            "domain": ".amazon.in",
            "path": "/",
            "secure": True,
            "httpOnly": False,
            "sameSite": "Lax",
        })
    return cookies


def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        raise SystemExit("No cookie string on stdin")
    cookies = parse_cookie_string(raw)
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOKIE_FILE.write_text(
        json.dumps({"saved_at": datetime.now(UTC).isoformat(), "cookies": cookies}, indent=2),
        encoding="utf-8",
    )
    print(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")


if __name__ == "__main__":
    main()
