"""Read-only pull of the Seller Central Payments data for the profit / leakage review (replays the page's own REST calls in-page).

  python agent/scripts/payments_pull.py [--since 2026-06-20]

Saves (gitignored data/): data/mahika/payments/events_all_<date>.json (every Transaction View row since --since, raw table rows),
groups_all_<date>.json (settlement groups + fund transfers). Visible Playwright profile, never logs in.
"""
import datetime as dt
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "src"))
OUT = ROOT / "data" / "mahika" / "payments"
JS = "async (u) => { const r = await fetch(u, {credentials: 'include'}); return {s: r.status, t: await r.text()}; }"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def row_date(r):
    for c in r["tableCells"]:
        v = c["value"]
        if v.get("type") == "LocalizedDate":
            return dt.datetime.fromtimestamp(v["dateEpochMillis"] / 1000, IST).date()
    return None


def main() -> int:
    from playwright.sync_api import sync_playwright
    from mahika.playwright.session import CHROMIUM_PROFILE_DIR
    since = dt.date.fromisoformat(sys.argv[sys.argv.index("--since") + 1]) if "--since" in sys.argv else dt.date(2026, 6, 20)
    today = dt.date.today().isoformat()
    base = "https://sellercentral.amazon.in/payments/api/events-view?limit=50&offset={n}&fiqlFiltersString=&sortType=DESC"
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(user_data_dir=str(CHROMIUM_PROFILE_DIR), headless=False, viewport={"width": 1500, "height": 1000},
                                                    args=["--disable-blink-features=AutomationControlled"])
        p = ctx.pages[0] if ctx.pages else ctx.new_page()
        p.goto("https://sellercentral.amazon.in/payments/event/view?resultsPerPage=10&pageNumber=1", wait_until="domcontentloaded", timeout=60000)
        p.wait_for_timeout(9000)
        rows, n, cols = [], 1, None
        while n < 400:
            r = p.evaluate(JS, base.format(n=n))
            if r["s"] != 200:
                print("events page", n, "status", r["s"]); break
            j = json.loads(r["t"])
            page_rows = j.get("tableRows") or []
            if n == 1:
                print("total rows (metadata):", (j.get("tableMetadata") or {}).get("numberOfRows"))
            if not page_rows:
                break
            rows += page_rows
            ds = [d for d in (row_date(x) for x in page_rows) if d]
            if ds and max(ds) < since:
                break
            n += 1
        rows = [x for x in rows if (row_date(x) or dt.date.max) >= since]
        print(f"events: {len(rows)} rows since {since} ({n} pages)")
        (OUT / f"events_all_{today}.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        groups, off = [], ""
        for _ in range(30):
            r = p.evaluate(JS, "https://sellercentral.amazon.in/payments/api/groups/?includeSummary=true&limit=20" + off)
            if r["s"] != 200:
                print("groups status", r["s"], r["t"][:100]); break
            j = json.loads(r["t"])
            gs = j.get("financialEventGroups") or []
            groups += gs
            nxt = j.get("nextToken") or (j.get("pagination") or {}).get("nextToken")
            if not nxt or not gs:
                break
            off = f"&nextToken={nxt}"
        print("groups:", len(groups))
        (OUT / f"groups_all_{today}.json").write_text(json.dumps({"financialEventGroups": groups}, ensure_ascii=False), encoding="utf-8")
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.exit(main())
