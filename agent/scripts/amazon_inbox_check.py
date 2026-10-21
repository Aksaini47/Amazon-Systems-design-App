"""Read-only Seller Central inbox check for the daily 12pm routine (amazon-inbox-daily-12pm).

Reads Buyer-Seller Messaging "Response needed" cases (every message + the order panel) and the
Seller Central notification unread count, using the persistent Playwright Chromium profile
(visible window - the login lives in that profile). It only clicks list rows; it never replies,
resolves, reports, attaches or changes anything.

Exit codes: 0 ok | 2 login required (do NOT log in from here) | 3 profile busy | 4 other error.
Output: data/mahika/inbox/latest.json (+ timestamped copy) and data/mahika/inbox/state.json (seen keys).
"""
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402
from mahika.playwright.session import CHROMIUM_PROFILE_DIR  # noqa: E402
import nimbus_track  # noqa: E402  (public tracker: no login)
from amazon_inbox_reply import msg_by, msg_text, thread_order  # noqa: E402  (who wrote a message / its text / the thread's order number)

OUT = ROOT / "data" / "mahika" / "inbox"
INBOX = "https://sellercentral.amazon.in/messaging/inbox"
NOTIF = "https://sellercentral.amazon.in/notifications/inbox"
MSG_TS = re.compile(r"^\d{1,2} [A-Za-z]{3,9} \d{4} \d{1,2}:\d{2} [ap]m$")


def parse_messages(pane: str) -> list[dict]:
    lines = [ln.strip() for ln in pane.splitlines()]
    msgs, cur = [], None
    for ln in lines:
        if MSG_TS.match(ln):
            cur = {"at": ln, "body": []}
            msgs.append(cur)
        elif cur is not None:
            cur["body"].append(ln)
    out = []
    for m in msgs:
        body = "\n".join(x for x in m["body"] if x)
        body = body.split("Spell check settings")[0].split("Attach file(s)")[0].split("\nOrder\n")[0]
        def grab(label):
            r = re.search(label + r":\s*(.*)", body)
            return r.group(1).strip() if r else None
        rec = {"at": m["at"], "product_asin": grab("Product"), "order_no": grab("Order number"),
               "return_requested": grab("Return requested"), "reason": grab("Reason for contact"), "raw": body[:1500]}
        rec["by"] = msg_by(rec)                      # amazon (CS forward) | seller (our reply) | buyer (customer follow-up)
        rec["text"] = msg_text(rec)[:1200]
        out.append(rec)
    return out


def parse_order_panel(pane: str) -> dict:
    i = pane.find("\nOrder\n")
    if i < 0:
        return {}
    t = pane[i:].split("Site map")[0]
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    d = {"product_title": next((ln for ln in lines if ln.startswith("Compatible for") or ln.startswith("Adjustable")), None)}
    for key in ("Qty", "Id", "Purchase date", "Ship by", "Deliver by", "Carrier", "Tracking Number", "Status", "Date Shipped"):
        for n, ln in enumerate(lines):
            if ln == key and n + 1 < len(lines):
                d[key] = lines[n + 1]; break
            if ln.startswith(key + ":"):
                d[key] = ln.split(":", 1)[1].strip(); break
    return d


def parse_language(pane: str) -> str | None:
    m = re.search(r"\nIndia\n\|\n([A-Za-z]+)\n", pane)
    return m.group(1) if m else None


def parse_order_page(t: str) -> dict:
    """Facts from sellercentral orders-v3 order page text (read-only)."""
    def g(pat, flags=0):
        m = re.search(pat, t, flags)
        return m.group(1).strip() if m else None
    refunds = sorted({float(x.replace(",", "")) for x in re.findall(r"Refund:\s*\n?\s*-?₹\s*([\d,]+(?:\.\d+)?)", t)})
    title = next((ln.strip() for ln in t.splitlines() if ln.strip().startswith("Compatible for")), None)
    st = re.search(r"Status\s*\n[\s\S]{0,80}?\n(Sent|Shipped|Unshipped|Pending|Canceled|Cancelled|Delivered|Return[^\n]*)\n", t)
    return {"status": st.group(1) if st else None, "purchase_date": g(r"Purchase date:\s*([^\n]+)"), "ship_by": g(r"Ship by:\s*([^\n]+)"),
            "deliver_by": g(r"Deliver by:\s*([^\n]+)"), "carrier": g(r"\nCarrier\s*\n([^\n]+)"), "tracking_id": g(r"\nTracking ID\s*\n([^\n]+)"),
            "ship_date": g(r"\nShip date\s*\n([^\n]+)"), "refunds": refunds, "title": title, "sku": g(r"SKU:\s*(\S+)"), "asin": g(r"ASIN:\s*(\S+)"),
            "grand_total": g(r"Grand total:\s*₹\s*([\d,]+(?:\.\d+)?)"), "ship_to_name": g(r"Ship to\s*\n([^\n]+)"), "contact_buyer": g(r"Contact Buyer:\s*([^\n]+)")}


def collect_facts(p, case: dict) -> dict:
    """Order page + Nimbus public tracker facts for one case. Read-only."""
    order_no = thread_order(case.get("messages") or [])         # buyer follow-ups carry no order number
    facts = {"order_no": order_no, "language": case.get("language"), "order_page": None, "tracking": None, "buyer_names": []}
    names = {case.get("name")}
    m = re.search(r"customer\s+(\S+)", case.get("subject") or "")
    if m:
        names.add(m.group(1))
    if order_no:
        try:
            p.goto(f"https://sellercentral.amazon.in/orders-v3/order/{order_no}", wait_until="domcontentloaded", timeout=60000); p.wait_for_timeout(9000)
            op = parse_order_page(p.evaluate("() => document.body.innerText")); facts["order_page"] = op
            names.update(x for x in (op.get("ship_to_name"), op.get("contact_buyer")) if x)
            if op.get("tracking_id"):
                try:
                    r = nimbus_track.parse(op["tracking_id"], nimbus_track.fetch(op["tracking_id"]), order_no)
                    facts["tracking"] = {k: r.get(k) for k in ("awb", "state", "courier", "order_id", "latest", "delivered_at", "delivery_verified", "days_since_last_scan", "notes")}
                except Exception as e:
                    facts["tracking"] = {"state": "ERROR", "error": str(e)[:120]}
        except Exception as e:
            facts["order_page_error"] = str(e)[:150]
    facts["buyer_names"] = sorted({w for n in names if n for w in re.findall(r"[A-Za-z]{3,}", n)})
    return facts


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    result = {"checked_at": now.isoformat(timespec="seconds"), "cases": [], "notifications": None, "summary": {}}
    try:
        pw_cm = sync_playwright()
        pw = pw_cm.start()
        try:
            ctx = pw.chromium.launch_persistent_context(user_data_dir=str(CHROMIUM_PROFILE_DIR), headless=False,
                                                         viewport={"width": 1500, "height": 1000},
                                                         args=["--disable-blink-features=AutomationControlled"])
        except Exception as e:  # profile locked by another Playwright process
            msg = str(e)
            if re.search(r"existing browser session|ProcessSingleton|already in use|user data directory", msg, re.I):
                print("PROFILE_BUSY", msg[:200]); pw.stop(); return 3
            raise
        p = ctx.pages[0] if ctx.pages else ctx.new_page()
        p.goto(INBOX, wait_until="domcontentloaded", timeout=60000); p.wait_for_timeout(12000)
        if "/ap/signin" in p.url or "/ap/mfa" in p.url or p.locator("#ap_email, #auth-mfa-otpcode").count():
            print("LOGIN_REQUIRED", p.url[:120]); ctx.close(); pw.stop(); return 2
        text = p.evaluate("() => document.body.innerText")
        m = re.search(r"Cases requiring attention\s+(\d+)", text); result["summary"]["response_needed"] = int(m.group(1)) if m else None
        m = re.search(r"Cases resolved\s+(\d+)", text); result["summary"]["resolved"] = int(m.group(1)) if m else None
        a, b = text.find("Filters ("), text.find("\n1\n", text.find("Filters ("))
        listing = [ln.strip() for ln in text[a:b].splitlines()[1:] if ln.strip()] if a >= 0 and b > a else []
        rows = []
        for k in range(0, len(listing) - 3, 4):
            rows.append({"name": listing[k], "list_date": listing[k + 1], "subject": listing[k + 2], "sla": listing[k + 3]})
        seen_names = {}
        for r in rows:
            n = seen_names.get(r["name"], 0); seen_names[r["name"]] = n + 1
            try:
                p.get_by_text(r["name"], exact=True).nth(n).click(timeout=8000); p.wait_for_timeout(4000)
                pane = p.evaluate("() => document.body.innerText")
                j = pane.find(r["name"] + "\nIndia")
                pane = pane[j:] if j >= 0 else pane
                r["messages"] = parse_messages(pane); r["order_panel"] = parse_order_panel(pane); r["language"] = parse_language(pane)
                sides = p.evaluate("() => [...document.querySelectorAll('.case-message-view-messages .message-component')].map(e => e.classList.contains('sent-message-component') ? 'sent' : 'received')")
                if len(sides) == len(r["messages"]):                    # the DOM tells who wrote each message (sent = our reply, incl. Sir's manual ones)
                    att = p.evaluate("() => [...document.querySelectorAll('.case-message-view-messages .message-component')].map(e => e.querySelectorAll('video, a[download], [class*=attach], [class*=Attach], [class*=media-file]').length)")
                    for m, sd, n_att in zip(r["messages"], sides, att):
                        m["attachments"] = n_att
                        m["side"] = sd
                        m["by"] = "seller" if sd == "sent" else ("amazon" if (m.get("reason") or m["raw"].startswith("Dear Amazon Seller")) else "buyer")
                r["amazon_templates"] = p.evaluate("() => [...document.querySelectorAll('kat-button')].map(e => e.getAttribute('label')).filter(l => l && /template/i.test(l))")
            except Exception as e:
                r["error"] = str(e)[:200]
            result["cases"].append(r)
        for c in result["cases"]:                      # facts for the reply agent (order page + Nimbus tracker)
            try:
                c["facts"] = collect_facts(p, c)
            except Exception as e:
                c["facts"] = {"error": str(e)[:150]}
        p.goto(NOTIF, wait_until="domcontentloaded", timeout=60000); p.wait_for_timeout(5000)
        try:
            result["notifications"] = json.loads(p.evaluate("() => document.body.innerText"))
        except Exception:
            result["notifications"] = {"error": "unparsed"}
        ctx.close(); pw.stop()
    except Exception as e:
        print("ERROR", repr(e)[:300]); return 4

    state_f = OUT / "state.json"
    seen = set(json.loads(state_f.read_text(encoding="utf-8")).get("seen", [])) if state_f.exists() else set()
    for c in result["cases"]:
        last = (c.get("messages") or [{}])[-1]
        c["key"] = f"{thread_order(c.get('messages') or [])}|{last.get('at')}"
        c["new"] = c["key"] not in seen
    result["summary"]["new_cases"] = sum(1 for c in result["cases"] if c["new"])
    result["summary"]["over_sla"] = sum(1 for c in result["cases"] if "over sla" in (c.get("sla") or "").lower())
    result["summary"]["cases_listed"] = len(result["cases"])
    (OUT / "latest.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / f"{now:%Y-%m-%d_%H%M}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    state_f.write_text(json.dumps({"seen": sorted(seen | {c["key"] for c in result["cases"]}), "updated": result["checked_at"]}), encoding="utf-8")
    print("OK", json.dumps(result["summary"]), str(OUT / "latest.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
