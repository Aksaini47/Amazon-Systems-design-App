"""Execute one Glass chunked CDP superbatch via Playwright connect_over_cdp.

Requires Glass browser tab on seller-fee-invoices. Uses viewId from chunked plan
only to locate target page by URL (not stale CDP attachment).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT = Path(
    r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices-import-hub-ecom"
)
INVOICES_URL = "seller-fee-invoices"
CDP_URLS = [
    "http://127.0.0.1:9222",
    "http://localhost:9222",
]


def _save_response(out_dir: Path, num: int, response: dict) -> dict:
    resp_path = out_dir / f"_cdp_super_{num:03d}_response.json"
    resp_path.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
    subprocess.check_call([
        sys.executable,
        str(SCRIPT_DIR / "save_superbatch_response.py"),
        str(resp_path),
        "--out-dir",
        str(out_dir),
    ])
    (out_dir / f"_cdp_super_{num:03d}_done.marker").write_text(
        datetime.now(UTC).isoformat(), encoding="utf-8",
    )
    value = response.get("result", {}).get("value", [])
    return {
        "ok": sum(1 for x in value if x.get("ok")),
        "fail": sum(1 for x in value if not x.get("ok")),
    }


def _session_expired(value: list) -> bool:
    for item in value:
        err = str(item.get("error", ""))
        if "/ap/signin" in err or "signin" in err.lower():
            return True
    return False


def run_batch(num: int, out_dir: Path, *, cdp_url: str | None = None) -> int:
    plan_path = out_dir / f"_cdp_chunked_super_{num:03d}.json"
    if not plan_path.exists():
        raise SystemExit(f"Missing {plan_path} — run emit_cdp_chunked.py {num}")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    steps = plan["steps"]

    from playwright.sync_api import sync_playwright

    urls = [cdp_url] if cdp_url else CDP_URLS
    last_err: Exception | None = None
    for url in urls:
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.connect_over_cdp(url)
                page = None
                for ctx in browser.contexts:
                    for p in ctx.pages:
                        if INVOICES_URL in p.url and "/ap/signin" not in p.url:
                            page = p
                            break
                    if page:
                        break
                if page is None:
                    raise RuntimeError(f"No seller-fee-invoices tab on {url}")

                response = None
                for step in steps:
                    params = step["params"]
                    if step["method"] == "Runtime.evaluate":
                        if params.get("awaitPromise"):
                            response = page.evaluate(
                                f"() => {params['expression']}"
                            )
                        else:
                            page.evaluate(f"() => {{ {params['expression']}; }}")
                    else:
                        raise RuntimeError(f"Unsupported step: {step['method']}")

                if response is None:
                    raise RuntimeError("No fetch step response")

                wrapped = {"result": {"value": response}}
                if _session_expired(response):
                    print("SESSION EXPIRED")
                    return 2

                stats = _save_response(out_dir, num, wrapped)
                print(f"super_{num:03d}: {stats}")
                return 0 if stats["fail"] == 0 else 1
        except Exception as exc:
            last_err = exc
            continue

    raise SystemExit(f"CDP connect failed: {last_err}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("num", type=int, nargs="?")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--cdp-url", default=None)
    parser.add_argument("--from", dest="from_num", type=int, default=None)
    parser.add_argument("--to", dest="to_num", type=int, default=None)
    args = parser.parse_args()
    out_dir = args.out_dir

    if args.from_num is not None:
        codes = []
        for n in range(args.from_num, (args.to_num or args.from_num) + 1):
            marker = out_dir / f"_cdp_super_{n:03d}_done.marker"
            if marker.exists():
                print(f"skip super_{n:03d}")
                continue
            code = run_batch(n, out_dir, cdp_url=args.cdp_url)
            if code == 2:
                raise SystemExit(2)
            codes.append(code)
        raise SystemExit(max(codes) if codes else 0)

    if args.num is None:
        parser.error("batch num or --from required")
    raise SystemExit(run_batch(args.num, out_dir, cdp_url=args.cdp_url))


if __name__ == "__main__":
    main()
