"""Read-only history pull of the Seller Central Buyer-Seller Messaging inbox (training data for Samvaad).

Opens the Resolved / Sent Messages / Reported Unresolved tabs in the persistent visible Playwright profile, scrolls each list until nothing new loads,
opens every case and stores the full thread with the true sender of each message (DOM class sent-message-component = our reply).
Never replies, resolves, reports or changes anything. Never logs in (exit 2 = login required, 3 = profile busy, 4 = error).

  python agent/scripts/amazon_inbox_history.py [--limit N]     -> data/mahika/inbox/history.json
"""
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402
from mahika.playwright.session import CHROMIUM_PROFILE_DIR  # noqa: E402
from amazon_inbox_check import parse_messages, parse_order_panel, parse_language  # noqa: E402

OUT = ROOT / "data" / "mahika" / "inbox"
INBOX = "https://sellercentral.amazon.in/messaging/inbox"
TABS = ["Resolved", "Sent Messages", "Reported Unresolved"]
SIDES_JS = "() => [...document.querySelectorAll('.case-message-view-messages .message-component')].map(e => e.classList.contains('sent-message-component') ? 'sent' : 'received')"
# the list is a scrollable container: scroll the nearest scrollable ancestor of a row to the bottom
SCROLL_JS = """() => {
  const row = [...document.querySelectorAll('*')].find(e => e.children.length === 0 && /^(Order enquiry|Enquiry from|Amazon ग्राहक|Important update)/.test((e.textContent || '').trim()));
  let n = row; while (n && !(n.scrollHeight > n.clientHeight + 20 && /(auto|scroll)/.test(getComputedStyle(n).overflowY))) n = n.parentElement;
  if (!n) return -1;
  n.scrollTop = n.scrollHeight; return n.scrollHeight;
}"""


def list_rows(text: str) -> list[dict]:
    a = text.find("Filters (")
    b = text.find("\nSpell check settings", a)
    seg = text[a:b if b > a else None].splitlines()[1:]
    lines = [x.strip() for x in seg if x.strip()]
    rows, i = [], 0
    while i + 3 < len(lines):
        name, date, subject = lines[i], lines[i + 1], lines[i + 2]
        if not re.match(r"^\d{1,2} [A-Za-z]{3,9} \d{4}$", date):
            i += 1; continue
        status = lines[i + 3] if lines[i + 3] in ("Resolved", "Open", "Over SLA", "Reported unresolved") or lines[i + 3].startswith("Due") else ""
        rows.append({"name": name, "list_date": date, "subject": subject, "status": status})
        i += 4 if status else 3
    return rows


def main() -> int:
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 400
    cases, seen = [], set()
    pw = sync_playwright().start()
    try:
        try:
            ctx = pw.chromium.launch_persistent_context(user_data_dir=str(CHROMIUM_PROFILE_DIR), headless=False, viewport={"width": 1500, "height": 1000},
                                                        args=["--disable-blink-features=AutomationControlled"])
        except Exception as e:
            if re.search(r"existing browser session|ProcessSingleton|already in use|user data directory", str(e), re.I):
                print("PROFILE_BUSY"); return 3
            raise
        p = ctx.pages[0] if ctx.pages else ctx.new_page()
        p.goto(INBOX, wait_until="domcontentloaded", timeout=60000); p.wait_for_timeout(12000)
        if "/ap/signin" in p.url or p.locator("#ap_email, #auth-mfa-otpcode").count():
            print("LOGIN_REQUIRED"); ctx.close(); return 2
        for tab in TABS:
            try:
                p.get_by_text(tab, exact=True).first.click(timeout=8000); p.wait_for_timeout(5000)
            except Exception as e:
                print("tab not clickable:", tab, str(e)[:60]); continue
            page_no = 0
            while True:                                                  # the list is paged (10 per page): a.cases-paging-change-page.next-page
                page_no += 1
                prev = -1
                for _ in range(10):                                      # scroll the page's list until all of its rows are rendered
                    p.evaluate(SCROLL_JS); p.wait_for_timeout(1500)
                    n = len(list_rows(p.evaluate("() => document.body.innerText")))
                    if n == prev:
                        break
                    prev = n
                rows = list_rows(p.evaluate("() => document.body.innerText"))
                print(f"{tab} page {page_no}: {len(rows)} rows listed")
                occ = {}
                for r in rows:
                    k = f"{r['name']}|{r['list_date']}|{r['subject']}"
                    nth = occ.get(r["name"], 0); occ[r["name"]] = nth + 1
                    if k in seen or len(cases) >= limit:
                        continue
                    seen.add(k)
                    rec = {"tab": tab, **r}
                    try:
                        el = p.get_by_text(r["name"], exact=True).nth(nth)
                        el.scroll_into_view_if_needed(timeout=5000); el.click(timeout=8000); p.wait_for_timeout(3500)
                        pane = p.evaluate("() => document.body.innerText")
                        j = pane.find(r["name"] + "\nIndia")
                        pane = pane[j:] if j >= 0 else pane
                        msgs = parse_messages(pane)
                        sides = p.evaluate(SIDES_JS)
                        if len(sides) == len(msgs):
                            for m, sd in zip(msgs, sides):
                                m["side"] = sd
                                m["by"] = "seller" if sd == "sent" else ("amazon" if (m.get("reason") or m["raw"].startswith("Dear Amazon Seller")) else "buyer")
                        rec.update(messages=msgs, order_panel=parse_order_panel(pane), language=parse_language(pane), sides_matched=len(sides) == len(msgs))
                    except Exception as e:
                        rec["error"] = str(e)[:150]
                    cases.append(rec)
                    if len(cases) % 10 == 0:
                        print("  cases read:", len(cases))
                nxt = p.locator("a.cases-paging-change-page.next-page:not(.disabled-link)")
                if page_no >= 30 or len(cases) >= limit or nxt.count() == 0:
                    break
                nxt.first.click(timeout=8000); p.wait_for_timeout(4000)
        ctx.close()
    except Exception as e:
        print("ERROR", repr(e)[:300]); return 4
    finally:
        pw.stop()
    (OUT / "history.json").write_text(json.dumps({"pulled_at": datetime.now().isoformat(timespec="seconds"), "cases": cases}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("OK", len(cases), "cases ->", OUT / "history.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
