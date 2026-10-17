"""Samvaad reply pipeline for Amazon Buyer-Seller Messaging (see .claude/agents/samvaad.md).

  python agent/scripts/amazon_inbox_reply.py plan        latest.json (facts from amazon_inbox_check.py) -> scenario + draft + lint -> plan.json (offline)
  python agent/scripts/amazon_inbox_reply.py send [--dry] [--only <name|order>] [--approve] [--resolve]
                                                         sends SEND items through the case composer (visible Playwright).
                                                         --dry fills the composer, screenshots, clears it (nothing is sent).
  python agent/scripts/amazon_inbox_reply.py templates   print every template (EN / HI)
  python agent/scripts/amazon_inbox_reply.py lint "text" run the strict pre-send lint on a text
  python agent/scripts/amazon_inbox_reply.py selftest    lint + decision unit tests

Safety: the model never types into the composer. Replies are built only from TEMPLATES + facts, must pass lint(), are verified by
sha16 before Send and re-read after Send. Live sends need samvaad_state.json auto_send=true, or --only <case> --approve (Sir's OK).
Refunds, cancellations, return decisions, Report Message, attachments and settings are never touched.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "mahika" / "inbox"
STATE_F = OUT / "samvaad_state.json"
SENT_LOG = OUT / "sent_log.jsonl"
INBOX = "https://sellercentral.amazon.in/messaging/inbox"
SIGN = {"en": "Regards,\nBadeja Enterprises", "hi": "सादर,\nBadeja Enterprises"}
RTO = ("RTO_RECEIVED", "RTO_IN_TRANSIT")
MOVING = ("DELIVERED", "IN_TRANSIT", "OUT_FOR_DELIVERY")

# ------------------------------------------------------------------ templates (single source of truth)
TEMPLATES = {
    "T1": {"name": "cancel asked, order already dispatched / delivered", "resolve": True,
           "en": "Hello,\nRegarding your order {order_no}: this order has already been dispatched with {carrier} (tracking ID {awb}){clause_en}. As it has already been shipped, it cannot be cancelled now.\nIf you face any issue with the product, please share the details with us here.\n" + SIGN["en"],
           "hi": "नमस्ते,\nआपके ऑर्डर {order_no} के बारे में: यह ऑर्डर पहले ही {carrier} (ट्रैकिंग आईडी {awb}) से डिस्पैच हो चुका है{clause_hi}। ऑर्डर शिप हो चुका है, इसलिए अब इसे रद्द नहीं किया जा सकता।\nअगर आपको प्रोडक्ट में कोई समस्या है तो कृपया उसकी जानकारी हमें यहीं बताएं।\n" + SIGN["hi"]},
    "T2": {"name": "shipped-marked but not moving (delay)", "resolve": True,
           "en": "Hello,\nRegarding your order {order_no}: your order is still being processed for dispatch and there is a delay in shipping. We apologise for the inconvenience.\nAmazon's estimated delivery date for this order is {deliver_by}.\n" + SIGN["en"],
           "hi": "नमस्ते,\nआपके ऑर्डर {order_no} के बारे में: आपका ऑर्डर अभी डिस्पैच के लिए प्रोसेस हो रहा है और शिपिंग में देरी हो रही है। असुविधा के लिए हमें खेद है।\nइस ऑर्डर की Amazon द्वारा अनुमानित डिलीवरी तारीख {deliver_by} है।\n" + SIGN["hi"]},
    "T3": {"name": "where is my order / ETA (moving)", "resolve": True,
           "en": "Hello,\nRegarding your order {order_no}: your order is on its way with {carrier} (tracking ID {awb}). Current status: {status_en}.\nAmazon's estimated delivery date is {deliver_by}.\n" + SIGN["en"],
           "hi": "नमस्ते,\nआपके ऑर्डर {order_no} के बारे में: आपका ऑर्डर {carrier} (ट्रैकिंग आईडी {awb}) के साथ रास्ते में है। वर्तमान स्थिति: {status_hi}।\nAmazon की अनुमानित डिलीवरी तारीख {deliver_by} है।\n" + SIGN["hi"]},
    "T4": {"name": "defect / refund asked on a delivered order: ask issue + video and photos", "resolve": False,
           "en": "Hello,\nRegarding your order {order_no}: please share the issue you are facing with the product, along with a clear video and photos that show the problem, so that we can look into your request.\n" + SIGN["en"],
           "hi": "नमस्ते,\nआपके ऑर्डर {order_no} के बारे में: कृपया बताएं कि आपको प्रोडक्ट में क्या समस्या आ रही है, और समस्या दिखाने वाला साफ़ वीडियो और फोटो भी भेजें, ताकि हम आपके अनुरोध की जांच कर सकें।\n" + SIGN["hi"]},
    "T5": {"name": "refund already processed (fact from the order page)", "resolve": True,
           "en": "Hello,\nRegarding your order {order_no}: {rto_en}a refund of Rs {amount} has been processed for this order. Please check the refund in your original payment method.\n" + SIGN["en"],
           "hi": "नमस्ते,\nआपके ऑर्डर {order_no} के बारे में: {rto_hi}इस ऑर्डर के लिए Rs {amount} का रिफंड प्रोसेस कर दिया गया है। कृपया अपने मूल भुगतान माध्यम में रिफंड देखें।\n" + SIGN["hi"]},
}

# ------------------------------------------------------------------ lint
BANNED_EN = [r"\bwill refund", r"\bwe will (process|issue|refund|replace|send|arrange)", r"\breplac", r"\bdiscount", r"\bcompensat", r"\bcoupon", r"\bvoucher",
             r"\bcashback", r"\bfraud", r"\bfake\b", r"\bcheat", r"\bpolice", r"\blegal", r"\bcourt\b", r"\bIPC\b", r"\bscam", r"\breview", r"\brating",
             r"\bfeedback", r"\bstars?\b", r"\bsupplier", r"\bprocure", r"\bwholesale", r"\bwhatsapp", r"call us", r"contact us", r"\bvisit\b", r"repairfully",
             r"\bpromise", r"\bguarantee", r"\bfree\b"]
BANNED_HI = ["रिप्लेसमेंट", "बदलकर", "बदल कर", "छूट", "डिस्काउंट", "धोखा", "फ्रॉड", "पुलिस", "कानूनी", "रिव्यू", "रेटिंग", "फीडबैक", "व्हाट्सएप", "वादा", "गारंटी", "मुफ्त"]
URL_RE = re.compile(r"https?://|www\.|\b[A-Za-z0-9-]+\.(?:com|in|co|net|org|store|shop|io|me|app|xyz|info)\b", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")
ALLOWED_CHARS = re.compile(r"^[\x20-\x7E\nऀ-ॿ]+$")      # ASCII + Devanagari incl. danda (no emoji, no symbols)


def _norm_num(tok: str) -> str:
    t = tok.replace(",", "")
    return t.rstrip("0").rstrip(".") if "." in t else t


def _fact_numbers(facts: dict) -> set[str]:
    blob = json.dumps({k: facts.get(k) for k in ("order_no", "order_page", "tracking")}, ensure_ascii=False)
    nums = set(_norm_num(x) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", blob))
    for r in ((facts.get("order_page") or {}).get("refunds") or []):
        nums.add(_norm_num(f"{r:.2f}"))
    return nums


def lint(text: str, facts: dict | None = None, template: str | None = None, lang: str = "en") -> list[str]:
    """Return the list of violations (empty = safe to send)."""
    facts = facts or {}
    errs: list[str] = []
    if not (20 <= len(text) <= 1000):
        errs.append(f"length {len(text)} outside 20-1000")
    if not ALLOWED_CHARS.match(text):
        errs.append("characters outside ASCII/Devanagari (emoji or symbol)")
    if re.search(r"\n{3,}", text):
        errs.append("more than two line breaks in a row")
    stripped = text
    for known in [facts.get("order_no"), ((facts.get("order_page") or {}).get("tracking_id")), ((facts.get("tracking") or {}).get("awb"))]:
        if known:
            stripped = stripped.replace(str(known), " ")
    if URL_RE.search(stripped):
        errs.append("URL / domain")
    if EMAIL_RE.search(stripped):
        errs.append("email address")
    if PHONE_RE.search(stripped):
        errs.append("phone number")
    for pat in BANNED_EN:
        if re.search(pat, text, re.I):
            errs.append(f"banned wording /{pat}/")
    for w in BANNED_HI:
        if w in text:
            errs.append(f"banned wording {w}")
    has_refund = bool((facts.get("order_page") or {}).get("refunds"))
    if re.search(r"refund|रिफंड", text, re.I) and not (template == "T5" and has_refund):
        errs.append("refund wording only allowed in T5 with a refund on the order page")
    if facts:
        allowed = _fact_numbers(facts)
        for tok in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
            if _norm_num(tok) not in allowed:
                errs.append(f"number {tok} not found in facts")
        for nm in facts.get("buyer_names") or []:
            if len(nm) >= 3 and re.search(rf"\b{re.escape(nm)}\b", text, re.I):
                errs.append(f"customer name {nm}")
    if not re.match(r"^(Hello,|नमस्ते,)\n", text):
        errs.append("missing greeting")
    if not text.rstrip().endswith("Badeja Enterprises"):
        errs.append("missing sign-off")
    return errs


# ------------------------------------------------------------------ date helpers
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def fmt_date(s: str | None) -> str | None:
    """'Mon, 28 Sept, 2026 IST' / 'Sep 22, 2026 17:24' / '22 Sept 2026 ...' -> '28 Sep 2026'."""
    if not s:
        return None
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", s)
    if m:
        d, mon, y = m.groups()
    else:
        m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", s)
        if not m:
            return None
        mon, d, y = m.groups()
    if mon[:3].lower() not in MONTHS:
        return None
    return f"{int(d)} {mon[:3].title()} {y}"


# ------------------------------------------------------------------ decision
CANCEL = re.compile(r"cancel|रद्द|कैंसल", re.I)
REFUND = re.compile(r"refund|money back|paise|पैसे|रिफंड", re.I)
RETURNED = re.compile(r"already returned|returned the|return(ed)? (the )?(item|product|order)|self[- ]?return|return (picked|pick ?up|delivered|reached)|item return|वापस (कर|भेज)", re.I)
NOTREC = re.compile(r"not (yet )?(received|recieved|delivered|come|arrived)|undeliver|didn.?t (get|receive)|haven.?t (got|received)|mark(ed)? (as )?delivered|showing delivered|shows delivered|never received|नहीं मिला", re.I)
DELAY = re.compile(r"delay|\blate\b|where is|when (will|can|i will)|how long|\bstatus\b|\btrack|कब (तक|मिलेगा)", re.I)
DEFECT = re.compile(r"defect|damag|not working|broken|dead|not starting|wrong (item|product|size|model)|not what i ordered|display (is )?not|touch (is )?not|crack|खराब|टूट", re.I)
ABUSE = re.compile(r"\bpolice\b|\blegal\b|\blawyer\b|\bcourt\b|consumer (forum|court)|\bfraud|\bcheat|\bscam|\ba[\s-]?to[\s-]?z\b|\bharass|complaint (against|to)|action against|\bsue\b|\bsuing\b", re.I)


def tags_of(text: str) -> set[str]:
    return {n for n, rx in (("cancel", CANCEL), ("refund", REFUND), ("returned", RETURNED), ("notrec", NOTREC), ("delay", DELAY), ("defect", DEFECT), ("abuse", ABUSE)) if rx.search(text or "")}


def status_phrase(tr: dict) -> tuple[str, str]:
    st = tr.get("state")
    if st == "OUT_FOR_DELIVERY":
        return "out for delivery", "डिलीवरी के लिए निकल चुका है"
    d = fmt_date((tr.get("latest") or {}).get("at"))
    return (f"in transit, last updated on {d}" if d else "in transit"), (f"रास्ते में है, आखिरी अपडेट {d}" if d else "रास्ते में है")


def render(tid: str, lang: str, facts: dict) -> str:
    op, tr = facts.get("order_page") or {}, facts.get("tracking") or {}
    st = tr.get("state")
    f = {"order_no": facts.get("order_no"), "carrier": op.get("carrier") or tr.get("courier"), "awb": op.get("tracking_id") or tr.get("awb"),
         "deliver_by": fmt_date(op.get("deliver_by")), "amount": f"{max(op.get('refunds') or [0]):,.2f}"}
    d_at = fmt_date(tr.get("delivered_at"))
    f["clause_en"] = {"DELIVERED": f" and was delivered on {d_at}", "OUT_FOR_DELIVERY": " and is out for delivery"}.get(st, f" and is on its way. Amazon's estimated delivery date is {f['deliver_by']}")
    f["clause_hi"] = {"DELIVERED": f" और {d_at} को डिलीवर हो गया है", "OUT_FOR_DELIVERY": " और डिलीवरी के लिए निकल चुका है"}.get(st, f" और रास्ते में है। Amazon की अनुमानित डिलीवरी तारीख {f['deliver_by']} है")
    f["status_en"], f["status_hi"] = status_phrase(tr)
    f["rto_en"] = "the shipment was returned to us and " if st in RTO else ""
    f["rto_hi"] = "शिपमेंट हमें वापस मिल गया है और " if st in RTO else ""
    text = TEMPLATES[tid][lang].format(**f)
    if tid == "T5" and not f["rto_en"] and lang == "en":
        text = text.replace(": a refund", ": A refund")
    return text


def decide(case: dict) -> dict:
    """Deterministic scenario choice. Returns {scenario, template, action, code, why}; action SEND or ESCALATE."""
    def esc(code, why, scenario="S11"):
        return {"scenario": scenario, "template": None, "action": "ESCALATE", "code": code, "why": why}
    msgs, facts = case.get("messages") or [], case.get("facts") or {}
    if case.get("error") or not msgs:
        return esc("FACTS_MISSING", "case could not be read")
    last = msgs[-1]
    t_last, t_all = tags_of(last.get("reason") or ""), tags_of(" ".join((m.get("reason") or "") for m in msgs))
    if "abuse" in t_all:
        return esc("SENSITIVE", "legal / fraud / A-to-z wording: Sir only", "S8")
    if not last.get("order_no"):
        return esc("PRESALES_OR_NO_ORDER", "no order in the message (pre-sales question): draft-only, Sir decides", "S6")
    op, tr = facts.get("order_page"), facts.get("tracking")
    if not op:
        return esc("FACTS_MISSING", "order page not read")
    if facts.get("language") not in ("English", "Hindi"):
        return esc("LANGUAGE", f"thread language {facts.get('language')}")
    state = (tr or {}).get("state")
    if op.get("refunds") and t_last & {"refund", "cancel", "returned", "notrec"}:
        return {"scenario": "S5", "template": "T5", "action": "SEND", "code": "REFUND_PROCESSED", "why": f"refund {op['refunds']} is on the order page"}
    if not tr or state in ("ERROR", "NOT_FOUND", "UNKNOWN", "ORDER_MISMATCH"):
        return esc("TRACKING_UNVERIFIED", f"tracker state {state}")
    if tr.get("notes"):
        return esc("TRACKING_CONFLICT", "; ".join(tr["notes"]))
    if state in RTO:
        return esc("REFUND_PENDING", "shipment returned to us (RTO) and no refund on the order page: Sir issues the refund", "S5")
    if "cancel" in t_last:
        if state in MOVING:
            return {"scenario": "S1", "template": "T1", "action": "SEND", "code": "CANCEL_SHIPPED", "why": f"tracker {state}"}
        return esc("CANCEL_NOT_SHIPPED", f"cancel asked while tracker is {state}: Sir decides", "S2")
    if t_last & {"notrec", "delay"} and "defect" not in t_last:
        if state in ("IN_TRANSIT", "OUT_FOR_DELIVERY"):
            return {"scenario": "S3", "template": "T3", "action": "SEND", "code": "ETA", "why": f"tracker {state}"}
        if state == "NOT_MOVING":
            return {"scenario": "S2", "template": "T2", "action": "SEND", "code": "DELAY_NOT_MOVING", "why": "shipment has not started moving"}
        return esc("DELIVERED_NOT_RECEIVED", "tracker says delivered but the buyer asks where it is / not received: no rule yet", "S11")
    if "defect" in t_last or ("refund" in t_last and "returned" not in t_last):
        if state == "DELIVERED" and tr.get("delivery_verified"):
            return {"scenario": "S4", "template": "T4", "action": "SEND", "code": "ASK_ISSUE_EVIDENCE", "why": "delivered, code verified"}
        return esc("DELIVERY_UNVERIFIED", f"defect/refund asked but delivery state is {state}, verified={tr.get('delivery_verified')}", "S4")
    if "returned" in t_last:
        return esc("RETURN_CLAIM_UNVERIFIED", "buyer says the item was returned, no refund on the page and no RTO: Sir checks the return", "S5")
    return esc("UNKNOWN", "no rule matched")


def make_item(case: dict, sent_keys: set[str]) -> dict:
    d = decide(case)
    facts = case.get("facts") or {}
    it = {"name": case.get("name"), "order_no": facts.get("order_no"), "key": case.get("key"), "language": facts.get("language"), "sla": case.get("sla"),
          "reason": ((case.get("messages") or [{}])[-1]).get("reason"), **d, "text": None, "lint": [], "resolve_after": False}
    if d["action"] == "SEND":
        lang = "hi" if facts.get("language") == "Hindi" else "en"
        it["text"] = render(d["template"], lang, facts)
        it["lint"] = lint(it["text"], facts, d["template"], lang)
        it["resolve_after"] = TEMPLATES[d["template"]]["resolve"]
        if it["lint"]:
            it.update(action="ESCALATE", code="LINT_FAILED", why="; ".join(it["lint"]))
    if it["key"] in sent_keys and it["action"] == "SEND":
        it.update(action="SKIP", code="ALREADY_REPLIED", why="sent_log has this message key")
    return it


# ------------------------------------------------------------------ state / log
def load_state() -> dict:
    base = {"auto_send": False, "auto_resolve": False, "max_per_run": 12, "max_per_day": 25}
    if STATE_F.exists():
        base.update(json.loads(STATE_F.read_text(encoding="utf-8")))
    return base


def read_log() -> list[dict]:
    if not SENT_LOG.exists():
        return []
    return [json.loads(x) for x in SENT_LOG.read_text(encoding="utf-8").splitlines() if x.strip()]


def sha16(t: str) -> str:
    return hashlib.sha256(t.replace("\r\n", "\n").strip("\n ").encode("utf-8")).hexdigest()[:16]


def cmd_plan() -> int:
    d = json.loads((OUT / "latest.json").read_text(encoding="utf-8"))
    sent = {x["key"] for x in read_log() if x.get("sent") and not x.get("dry")}
    items = [make_item(c, sent) for c in d["cases"]]
    st = load_state()
    (OUT / "plan.json").write_text(json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"), "checked_at": d.get("checked_at"), "state": st, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    for it in items:
        print(f"{it['name']:11s} | {it['order_no']} | {it['action']:8s} | {it['scenario']} {it['template'] or '--'} | {it['code']} | {it['why'][:90]}")
        if it["text"]:
            print("    " + it["text"].replace("\n", "\n    "))
    print(f"mode: auto_send={st['auto_send']} auto_resolve={st['auto_resolve']} | SEND={sum(i['action']=='SEND' for i in items)} ESCALATE={sum(i['action']=='ESCALATE' for i in items)} SKIP={sum(i['action']=='SKIP' for i in items)}")
    return 0


def cmd_templates() -> int:
    for tid, t in TEMPLATES.items():
        print(f"== {tid}: {t['name']} (resolve after send: {t['resolve']})\n-- EN\n{t['en']}\n-- HI\n{t['hi']}\n")
    return 0


# ------------------------------------------------------------------ send (Playwright)
def cmd_send(args: list[str]) -> int:
    from playwright.sync_api import sync_playwright
    sys.path.insert(0, str(ROOT / "agent" / "src"))
    from mahika.playwright.session import CHROMIUM_PROFILE_DIR
    dry, approve, resolve_flag = "--dry" in args, "--approve" in args, "--resolve" in args
    only = args[args.index("--only") + 1] if "--only" in args else None
    st = load_state()
    if not dry and not (st["auto_send"] or (only and approve)):
        print("BLOCKED: auto_send is false. Sir must approve: use --only <case> --approve for a single case, or set auto_send=true in samvaad_state.json."); return 4
    plan = json.loads((OUT / "plan.json").read_text(encoding="utf-8"))
    items = [i for i in plan["items"] if i["action"] == "SEND" and (not only or only.lower() in (i["name"] or "").lower() or only == i["order_no"])]
    if not items:
        print("NOTHING_TO_SEND"); return 0
    today = datetime.now().strftime("%Y-%m-%d")
    done_today = sum(1 for x in read_log() if x.get("sent") and not x.get("dry") and str(x.get("at", "")).startswith(today))
    budget = min(st["max_per_run"], max(0, st["max_per_day"] - done_today)) if not dry else len(items)
    if budget <= 0:
        print("CAP_REACHED: daily cap hit"); return 5
    (OUT / "shots").mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        try:
            ctx = pw.chromium.launch_persistent_context(user_data_dir=str(CHROMIUM_PROFILE_DIR), headless=False, viewport={"width": 1500, "height": 1000}, args=["--disable-blink-features=AutomationControlled"])
        except Exception as e:
            print("PROFILE_BUSY", str(e)[:150]); return 3
        p = ctx.pages[0] if ctx.pages else ctx.new_page()
        for it in items[:budget]:
            rec = {"at": datetime.now().isoformat(timespec="seconds"), "key": it["key"], "order_no": it["order_no"], "name": it["name"], "template": it["template"],
                   "sha16": sha16(it["text"]), "text": it["text"], "dry": dry, "sent": False, "verified": False, "resolved": False}
            try:
                p.goto(INBOX, wait_until="domcontentloaded", timeout=60000); p.wait_for_timeout(12000)
                if "/ap/signin" in p.url:
                    rec["error"] = "LOGIN_REQUIRED"; results.append(rec); break
                p.get_by_text(it["name"], exact=True).first.click(timeout=8000); p.wait_for_timeout(4000)
                pane = p.evaluate("() => document.body.innerText")
                if it["order_no"] not in pane:
                    rec["error"] = "case pane does not show the expected order number: not sending"; results.append(rec); continue
                ta = p.locator("textarea[placeholder^='Please limit your text']")
                if ta.count() == 0:                                   # topic cases (e.g. Cancel Order) show Amazon templates + a "Write Message" button first
                    wm = p.locator("kat-button[label='Write Message']")
                    if wm.count():
                        wm.first.click(); p.wait_for_timeout(3000)
                if ta.count() == 0:
                    rec["error"] = "no reply composer on this case (no textarea, no Write Message button)"; results.append(rec); continue
                send_btn = p.locator("kat-button[label='Send']")
                ta.click(); ta.fill(it["text"]); p.wait_for_timeout(600)
                if send_btn.get_attribute("disabled") is not None:      # Katal wants real key events
                    ta.press_sequentially(" "); ta.press("Backspace"); p.wait_for_timeout(600)
                if sha16(ta.input_value()) != rec["sha16"]:
                    rec["error"] = "composer text hash mismatch: not sending"; ta.fill(""); results.append(rec); break
                if dry:
                    p.screenshot(path=str(OUT / "shots" / f"{it['order_no']}_{it['template']}_dry.png")); ta.fill("")
                    rec["verified"] = True; results.append(rec); continue
                if send_btn.get_attribute("disabled") is not None:
                    rec["error"] = "Send stayed disabled"; results.append(rec); break
                send_btn.click(); p.wait_for_timeout(7000)
                after = re.sub(r"\s+", " ", p.evaluate("() => document.body.innerText"))
                rec["sent"] = True; rec["verified"] = re.sub(r"\s+", " ", it["text"])[:60] in after
                p.screenshot(path=str(OUT / "shots" / f"{it['order_no']}_{it['template']}_sent.png"))
                if rec["verified"] and it["resolve_after"] and (resolve_flag or st["auto_resolve"]):
                    p.locator("kat-button[label='Resolve case']").click(); p.wait_for_timeout(5000)
                    rec["resolved"] = "Resolved" in p.evaluate("() => document.body.innerText")
                if not rec["verified"]:
                    rec["error"] = "sent but the message text was not found in the thread afterwards: stopping"; results.append(rec); break
            except Exception as e:
                rec["error"] = str(e)[:200]; results.append(rec); break
            results.append(rec)
        ctx.close()
    with SENT_LOG.open("a", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    for r in results:
        print(f"{r['name']:11s} {r['order_no']} {r['template']} dry={r['dry']} sent={r['sent']} verified={r['verified']} resolved={r['resolved']} {r.get('error', '')}")
    return 0


# ------------------------------------------------------------------ tests
def cmd_selftest() -> int:
    good_facts = {"order_no": "402-1292244-5057153", "buyer_names": ["Himani", "Tushar"], "order_page": {"tracking_id": "4218630821242", "carrier": "Delhivery", "deliver_by": "Mon, 28 Sept, 2026 IST", "refunds": [3149.8]},
                  "tracking": {"awb": "4218630821242", "state": "DELIVERED", "delivered_at": "Sep 22, 2026 17:24", "delivery_verified": True, "latest": {"at": "Sep 22, 2026 17:24"}}}
    ok_text = render("T1", "en", good_facts)
    cases = [("good T1 passes", ok_text, [], True), ("url", ok_text.replace("Regards,", "Visit https://x.com\nRegards,"), [], False), ("domain repairfully.com", ok_text.replace("Regards,", "repairfully.com\nRegards,"), [], False),
             ("phone", ok_text.replace("Regards,", "Call 9876543210\nRegards,"), [], False), ("email", ok_text.replace("Regards,", "a@b.com\nRegards,"), [], False), ("emoji", ok_text.replace("Hello,", "Hello 😊,"), [], False),
             ("refund promise", ok_text.replace("Regards,", "We will refund you.\nRegards,"), [], False), ("unknown number", ok_text.replace("Regards,", "Delivery in 5 days.\nRegards,"), [], False),
             ("customer name", ok_text.replace("Hello,", "Hello Himani,"), [], False), ("triple newline", ok_text.replace("Regards,", "\n\nRegards,"), [], False),
             ("review request", ok_text.replace("Regards,", "Please leave a review.\nRegards,"), [], False), ("refund word outside T5", ok_text.replace("Regards,", "Refund later.\nRegards,"), [], False),
             ("no sign-off", ok_text.replace("Badeja Enterprises", "Team"), [], False)]
    fails = 0
    for name, text, _, expect_ok in cases:
        errs = lint(text, good_facts, "T1")
        passed = (not errs) == expect_ok
        fails += not passed
        print(("PASS " if passed else "FAIL ") + name + ("" if not errs else f"  <- {errs[0]}"))
    t5 = render("T5", "en", good_facts)
    e5 = lint(t5, good_facts, "T5"); print(("PASS " if not e5 else "FAIL ") + "T5 passes with refund on page" + (f" <- {e5}" if e5 else "")); fails += bool(e5)
    e5b = lint(t5, {**good_facts, "order_page": {**good_facts["order_page"], "refunds": []}}, "T5"); print(("PASS " if e5b else "FAIL ") + "T5 blocked without a refund on the page"); fails += not e5b
    for tid in TEMPLATES:
        for lang in ("en", "hi"):
            e = lint(render(tid, lang, good_facts), good_facts, tid)
            print(("PASS " if not e else "FAIL ") + f"{tid}/{lang} renders and lints" + (f" <- {e}" if e else "")); fails += bool(e)
    # decision tests (synthetic cases)
    def case(reason, state, refunds=(), notes=(), lang="English", verified=True, order_page=True, subject="Order enquiry from Amazon customer Test"):
        tr = {"awb": "111111111111", "state": state, "courier": "Delhivery", "delivery_verified": verified, "notes": list(notes), "delivered_at": "Sep 22, 2026 17:24", "latest": {"at": "Oct 12, 2026 18:03"}}
        op = {"carrier": "Delhivery", "tracking_id": "111111111111", "deliver_by": "Mon, 28 Sept, 2026 IST", "refunds": list(refunds), "status": "Sent"}
        return {"name": "Test", "key": "1|1", "subject": subject, "messages": [{"order_no": "400-0000000-0000000", "reason": reason}],
                "facts": {"order_no": "400-0000000-0000000", "language": lang, "order_page": op if order_page else None, "tracking": tr, "buyer_names": ["Test"]}}
    dec = [("cancel + in transit -> T1", case("cx want to cancel", "IN_TRANSIT"), "T1"), ("cancel + delivered -> T1", case("cancel the item", "DELIVERED"), "T1"),
           ("cancel + not moving -> escalate", case("cancel", "NOT_MOVING"), None), ("where is my order + in transit -> T3", case("when will I get my package", "IN_TRANSIT"), "T3"),
           ("delay + not moving -> T2", case("order is too delay", "NOT_MOVING"), "T2"), ("not received + delivered -> escalate", case("customer not received order but showing delivered", "DELIVERED"), None),
           ("defective + delivered verified -> T4", case("received a defective product", "DELIVERED"), "T4"), ("defective + delivered unverified -> escalate", case("received a defective product", "DELIVERED", verified=False), None),
           ("refund + RTO, no refund yet -> escalate", case("want refund", "RTO_RECEIVED"), None), ("refund + refund on page -> T5", case("want refund", "RTO_RECEIVED", refunds=[999.0]), "T5"),
           ("legal wording -> escalate", case("customer will send a lawyer notice", "DELIVERED"), None), ("A to Z claim -> escalate", case("A to Z claim filed", "DELIVERED"), None),
           ("tracking conflict -> escalate", case("cancel", "DELIVERED", notes=["refusal scan"]), None), ("Hindi cancel + in transit -> HI T1", case("cancel", "IN_TRANSIT", lang="Hindi"), "T1"),
           ("language Tamil -> escalate", case("cancel", "IN_TRANSIT", lang="Tamil"), None), ("no order page -> escalate", case("cancel", "IN_TRANSIT", order_page=False), None),
           ("returned claim, no refund, delivered -> escalate", case("customer already returned the item", "DELIVERED"), None)]
    for name, c, want in dec:
        it = make_item(c, set())
        okd = (it["action"] == "SEND" and it["template"] == want) if want else it["action"] == "ESCALATE"
        if want and "Hindi" in name:
            okd = okd and it["text"].startswith("नमस्ते")
        fails += not okd
        print(("PASS " if okd else "FAIL ") + "decide: " + name + f"  [{it['action']} {it['template']} {it['code']}]")
    return 1 if fails else 0


def main() -> int:
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); return 0
    if a[0] == "plan":
        return cmd_plan()
    if a[0] == "send":
        return cmd_send(a[1:])
    if a[0] == "templates":
        return cmd_templates()
    if a[0] == "selftest":
        return cmd_selftest()
    if a[0] == "lint":
        errs = lint(a[1].replace("\\n", "\n")); print("OK" if not errs else "\n".join(errs)); return 1 if errs else 0
    print("unknown command", a[0]); return 2


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.exit(main())
