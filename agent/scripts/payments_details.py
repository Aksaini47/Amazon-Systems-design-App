"""Read-only: fetch the fee / charge breakdown (payments/api/event-details) of every Transaction View row pulled by payments_pull.py.

  python agent/scripts/payments_details.py            -> data/mahika/payments/event_details_<date>.json  {rowIdentifier: raw detail json}
Resumes: rows already in today's file are skipped. Visible Playwright profile, same-origin fetches only, never logs in.
"""
import datetime as dt
import glob
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "src"))
OUT = ROOT / "data" / "mahika" / "payments"
JS = "async (u) => { const r = await fetch(u, {credentials: 'include'}); return {s: r.status, t: await r.text()}; }"


def main() -> int:
    from playwright.sync_api import sync_playwright
    from mahika.playwright.session import CHROMIUM_PROFILE_DIR
    rows = json.loads(Path(sorted(glob.glob(str(OUT / "events_all_*.json")))[-1]).read_text(encoding="utf-8"))
    today = dt.date.today().isoformat()
    f = OUT / f"event_details_{today}.json"
    have = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    todo = [r["rowIdentifier"] for r in rows if r["rowIdentifier"] not in have]
    print(f"rows {len(rows)} | already {len(have)} | to fetch {len(todo)}")
    if not todo:
        return 0
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(user_data_dir=str(CHROMIUM_PROFILE_DIR), headless=False, viewport={"width": 1500, "height": 1000},
                                                    args=["--disable-blink-features=AutomationControlled"])
        p = ctx.pages[0] if ctx.pages else ctx.new_page()
        p.goto("https://sellercentral.amazon.in/payments/event/view?resultsPerPage=10&pageNumber=1", wait_until="domcontentloaded", timeout=60000)
        p.wait_for_timeout(8000)
        bad = 0
        for i, rid in enumerate(todo, 1):
            r = p.evaluate(JS, f"https://sellercentral.amazon.in/payments/api/event-details?financialEventId={rid}")
            if r["s"] == 200:
                have[rid] = json.loads(r["t"])
            else:
                bad += 1
                if bad > 25:
                    print("too many failures, stopping at", i); break
            if i % 100 == 0:
                f.write_text(json.dumps(have, ensure_ascii=False), encoding="utf-8"); print("fetched", i, flush=True)
        ctx.close()
    f.write_text(json.dumps(have, ensure_ascii=False), encoding="utf-8")
    print("saved", len(have), "details ->", f)
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.exit(main())
