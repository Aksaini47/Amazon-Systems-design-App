"""Samvaad reply pipeline for Amazon Buyer-Seller Messaging (see .claude/agents/samvaad.md).

  python agent/scripts/amazon_inbox_reply.py plan        latest.json (facts from amazon_inbox_check.py) -> scenario + draft + lint -> plan.json (offline)
  python agent/scripts/amazon_inbox_reply.py send [--dry] [--only <name|order>] [--approve] [--resolve] [--force-template T#]
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
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "mahika" / "inbox"
STATE_F = OUT / "samvaad_state.json"
SENT_LOG = OUT / "sent_log.jsonl"
INBOX = "https://sellercentral.amazon.in/messaging/inbox"
SIGN = {"en": "Regards,\nBadeja Enterprises"}
RTO = ("RTO_RECEIVED", "RTO_IN_TRANSIT")
MOVING = ("DELIVERED", "IN_TRANSIT", "OUT_FOR_DELIVERY")

# ------------------------------------------------------------------ templates (single source of truth)
TEMPLATES = {
    # English only, professional and technical (Sir 2026-10-21). One template = one scenario; wording is the single source of truth.
    "T1": {"name": "cancel asked, order already dispatched / delivered", "resolve": True,
           "en": "Dear Customer,\nRegarding order {order_no}: the shipment was dispatched via {carrier} (tracking ID {awb}){clause_en}. As the order has already been shipped, it cannot be cancelled.{t1_tail}\n" + SIGN["en"]},
    "T2": {"name": "shipped-marked but not moving (delay)", "resolve": True,
           "en": "Dear Customer,\nRegarding order {order_no}: we apologise for the delay. The shipment is still being processed for dispatch.{eta_clause}\n" + SIGN["en"]},
    "T3": {"name": "where is my order / ETA (moving)", "resolve": True,
           "en": "Dear Customer,\nRegarding order {order_no}: {t3_lead} {carrier} (tracking ID {awb}). Current courier status: {status_en}.{eta_clause}\n" + SIGN["en"]},
    "T5": {"name": "refund already issued (fact from the order page): details + Amazon Customer Support for the status", "resolve": True,
           "en": "Dear Customer,\nRegarding order {order_no}: {rto_en}a refund of Rs {amount} has been issued for this order. Refunds are processed by Amazon to the original payment method. If the amount is not reflected in your account, please contact Amazon Customer Support by phone from the Customer Service section of your Amazon account; they can check the refund status with the payment partner.\n" + SIGN["en"]},
    "T6": {"name": "tracker says delivered but buyer says not received: delivery facts + ask to check with family/neighbours/security", "resolve": False, "alert": True,
           "en": "Dear Customer,\nRegarding order {order_no}: as per the courier tracking, this shipment was delivered by {carrier} (tracking ID {awb}) on {delivered_date}. Please check with your family members, neighbours or building security, as the parcel may have been received on your behalf.\nIf you still cannot locate the parcel, please reply here and we will check further with the courier.\n" + SIGN["en"]},
    # Sir 2026-10-20: buyer still disputes delivery after T6 -> courier tracking facts. TEXT ONLY (no link, no attachment: Amazon G1701);
    # the tracker-page screenshot is saved to data/mahika/inbox/proof/ for Sir. Sent once per order (T7_MARKS detect a repeat), then Sir takes over.
    "T7": {"name": "buyer disputes a delivered shipment: courier tracking facts (text only, screenshot saved for Sir)", "resolve": False, "alert": True,
           "en": "Dear Customer,\nRegarding order {order_no}: the courier tracking shows this shipment ({carrier}, tracking ID {awb}) as Delivered. Delivery was recorded on {when_en}{loc_en}.{ver_en}\nWe request you to check once more with your family members, neighbours or building security. You may also look up the same tracking ID in the courier's own app or on its tracking page.\n" + SIGN["en"]},
    # Sir-approved text for a defect claim where Amazon still shows the order as not delivered (ayesha 2026-10-20). Only via `send --only <case> --approve --force-template T8`.
    "T8": {"name": "defect claim while Amazon's status lags: ask for evidence + state the courier delivery fact (Sir-approved text, manual use)", "resolve": False,
           "en": "Dear Customer,\nRegarding order {order_no}: we are sorry that the display is not working properly. To investigate your request, please share a clear video and photos that show the problem.\nOur records show that this order was delivered by {carrier} (tracking ID {awb}) on {delivered_date}. The order status in your Amazon account is updated by Amazon from the courier tracking.\n" + SIGN["en"]},
    # Sir 2026-10-20: defective product inside the return/replacement window (7 days from the courier delivery date): photos here first, then a replacement request in Amazon.
    # Replacements and refunds are raised and processed by Amazon and the buyer, never by us; policy = steer to a replacement ONLY, even when the buyer asked for a refund (Sir 2026-10-21).
    "T9": {"name": "defect inside the return/replacement window: share received-product + defect photos here, then raise a replacement request", "resolve": False,
           "en": "Dear Customer,\nRegarding order {order_no}: we are sorry about the issue with the product. To investigate your request, please share here in this chat clear photos of the product you received (with the packaging label visible), clear photos of all sides of the product, and a video that shows the problem (an unboxing video for a missing, wrong or damaged item).\nAfter sharing them, please raise a replacement request for this order from Your Orders in your Amazon account. Replacement requests are raised and processed through Amazon.\nPlease note that a replacement is available only for a defect on arrival. The warranty does not apply once the screen has been pasted or fitted on the device, or if the warranty protection film or sticker has been removed.\n" + SIGN["en"]},
    # Sir 2026-10-21: defect/refund asked AFTER the 7-day window -> WhatsApp support (number lives in samvaad_state.json "support_whatsapp", not in code; remove the key = kill switch,
    # the case then escalates as WINDOW_CROSSED). Amazon G1701 bans phone numbers / moving buyers off Amazon: Sir's own risk decision.
    "T10": {"name": "defect/refund asked after the return/replacement window: point to WhatsApp support (Sir's risk decision)", "resolve": False, "alert": True,
            "en": "Dear Customer,\nRegarding order {order_no}: the return and replacement window for this order has ended. For further assistance with this product, please contact our WhatsApp support on {whatsapp} and quote your order number.\n" + SIGN["en"]},
    # Sir 2026-10-21: refund not received -> the buyer asks Amazon Customer Support by phone (a refund is already issued; follow-up after T5).
    "T11": {"name": "buyer still asks about a refund that is already issued: Amazon Customer Support by phone", "resolve": False,
            "en": "Dear Customer,\nRegarding order {order_no}: a refund of Rs {amount} has already been issued for this order. Refunds are processed by Amazon to the original payment method, and the credit timeline depends on the payment method. To check the refund status, please contact Amazon Customer Support by phone from the Customer Service section of your Amazon account.\n" + SIGN["en"]},
    # Sir 2026-10-21: pre-sales question without an order -> one generic reply, Sir is alerted to answer the specifics (no link, no price, no stock claim).
    "T12": {"name": "pre-sales enquiry without an order: generic reply, Sir answers the specifics", "resolve": False, "alert": True,
            "en": "Dear Customer,\nThank you for your enquiry. Please refer to the product listing for specifications and compatibility. To confirm availability and compatibility for your device, please reply here with your phone brand and model name.\n" + SIGN["en"]},
    # Sir 2026-10-21: change-of-mind return ('I no longer want the item') on a delivered order -> policy reply. Policy text = Sir's own wording (7 days replacement for defects on arrival, warranty conditions).
    "T13": {"name": "change of mind on a delivered order: return policy", "resolve": False,
            "en": "Dear Customer,\nRegarding order {order_no}: as per our return policy, a replacement is available only for a defect on arrival, reported within 7 days of delivery. Returns or refunds for reasons such as a change of mind are not accepted. The warranty does not apply once the screen has been pasted or fitted on the device, or if the warranty protection film or sticker has been removed.\n" + SIGN["en"]},
    # Sir 2026-10-21: refused / undelivered shipment on its way back (RTO): tell the buyer the status; Sir gets a refund card (Samvaad never refunds). Guardrails: tracker order-id match,
    # RTO state, no conflicting scans, no refund yet. Sir monitors the first orders; whether this ever becomes more automatic is his decision.
    "T14": {"name": "RTO (refused / undelivered): courier status for the buyer, refund card for Sir", "resolve": False, "alert": True,
            "en": "Dear Customer,\nRegarding order {order_no}: the shipment ({carrier}, tracking ID {awb}) could not be delivered and {rto_verb} to the seller (return to origin, RTO). Current courier status: {rto_status}. The refund will be processed against this return to origin.\n" + SIGN["en"]},
}
T14_MARKS = ("could not be delivered and",)
T7_MARKS = ("Delivery was recorded on",)         # a seller message containing one of these = T7 already sent in this thread
T11_MARKS = ("has already been issued",)         # T11 already sent in this thread

# ------------------------------------------------------------------ lint
BANNED_EN = [r"\bwill refund", r"\bwe will (process|issue|refund|replace|send|arrange)", r"\breplac", r"\bdiscount", r"\bcompensat", r"\bcoupon", r"\bvoucher",
             r"\bcashback", r"\bfraud", r"\bfake\b", r"\bcheat", r"\bpolice", r"\blegal", r"\bcourt\b", r"\bIPC\b", r"\bscam", r"\breview", r"\brating",
             r"\bfeedback", r"\bstars?\b", r"\bsupplier", r"\bprocure", r"\bwholesale", r"\bwhatsapp", r"call us", r"contact us", r"\bvisit\b", r"repairfully",
             r"\bpromise", r"\bguarantee", r"\bfree\b"]
URL_RE = re.compile(r"https?://|www\.|\b[A-Za-z0-9-]+\.(?:com|in|co|net|org|store|shop|io|me|app|xyz|info)\b", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")
ALLOWED_CHARS = re.compile(r"^[\x20-\x7E\n]+$")      # plain ASCII only (English only, no emoji, no symbols)


def _norm_num(tok: str) -> str:
    t = tok.replace(",", "")
    if "." in t:
        return t.rstrip("0").rstrip(".")
    return t.lstrip("0") or "0" if len(t) < 4 else t          # day numbers: "01" == "1"; long ids (AWB, order numbers) untouched


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
    for known in [facts.get("order_no"), ((facts.get("order_page") or {}).get("tracking_id")), ((facts.get("tracking") or {}).get("awb")), support_number() if template == "T10" else None]:
        if known:
            stripped = stripped.replace(str(known), " ")
    if URL_RE.search(stripped):
        errs.append("URL / domain")
    if EMAIL_RE.search(stripped):
        errs.append("email address")
    if PHONE_RE.search(stripped):
        errs.append("phone number")
    for pat in BANNED_EN:
        if template in ("T9", "T10", "T13") and pat == r"\breplac":   # T9 guides the buyer to raise a replacement request, T10 names the ended window (promises stay banned)
            continue
        if template == "T10" and pat == r"\bwhatsapp":         # T10 only: Sir's WhatsApp-support rule (his risk decision)
            continue
        if re.search(pat, text, re.I):
            errs.append(f"banned wording /{pat}/")
    has_refund = bool((facts.get("order_page") or {}).get("refunds"))
    if re.search(r"refund", text, re.I) and not (template in ("T1", "T13", "T14") or (template in ("T5", "T11") and has_refund)):
        errs.append("refund wording only allowed in T1 / T13 / T14 (policy, RTO) and in T5 / T11 with a refund on the order page")
    if facts:
        allowed = _fact_numbers(facts)
        if template == "T10" and support_number():
            allowed.add(support_number())
        if template == "T13":
            allowed.add("7")                                                        # the 7-day replacement window in Sir's policy text
        for tok in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
            if _norm_num(tok) not in allowed:
                errs.append(f"number {tok} not found in facts")
        for nm in facts.get("buyer_names") or []:
            if len(nm) >= 3 and re.search(rf"\b{re.escape(nm)}\b", text, re.I):
                errs.append(f"customer name {nm}")
    if not re.match(r"^Dear Customer,\n", text):
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
NOTREC = re.compile(r"not (yet )?(received|recieved|delivered|come|arrived)|undeliver|did(n.?t| not) (get|receive|recieve)|haven.?t (got|received)|mark(ed)? (as )?delivered|showing delivered|shows delivered|never received|नहीं मिला", re.I)
DELAY = re.compile(r"delay|\blate\b|where is|when (will|can|i will)|how long|\bstatus\b|\btrack|कब (तक|मिलेगा)", re.I)
DEFECT = re.compile(r"defect|damag|not working|broken|dead|not starting|wrong (item|product|size|model)|not what i ordered|display (is )?not|touch (is )?not|crack|खराब|टूट|item (is )?missing|missing (item|part)|incomplete|short (item|piece)", re.I)
ABUSE = re.compile(r"\bpolice\b|\blegal\b|\blawyer\b|\bcourt\b|consumer (forum|court)|\bfraud|\bcheat|\bscam|\ba[\s-]?to[\s-]?z\b|\bharass|complaint (against|to)|action against|\bsue\b|\bsuing\b", re.I)


# "I did not receive my refund" is a refund question, not a "parcel not received" claim
REFUND_NOTREC = re.compile(r"(refund|रिफंड|paise|पैसे)[^.,\n]{0,25}\b(not|never|nahi)\b|\b(not|never|nahi)\b[^.,\n]{0,25}(receiv\w*|reciev\w*|got|मिला)[^.,\n]{0,12}(refund|रिफंड|paise|पैसे)", re.I)


CHANGEMIND = re.compile(r"no longer (want|need)|don.?t (want|need)|do not (want|need)|changed my mind|change of mind|ordered by mistake|order(ed)? (it )?by mistake|not needed|no need now", re.I)


def tags_of(text: str) -> set[str]:
    tags = {n for n, rx in (("cancel", CANCEL), ("refund", REFUND), ("returned", RETURNED), ("notrec", NOTREC), ("delay", DELAY), ("defect", DEFECT), ("abuse", ABUSE), ("changemind", CHANGEMIND)) if rx.search(text or "")}
    if REFUND_NOTREC.search(text or ""):
        tags.discard("notrec")
        tags.add("refundq")                                    # a question about a refund's status, not a new product claim
    return tags


# ------------------------------------------------------------------ thread helpers (who wrote what)
def msg_by(m: dict) -> str:
    """'amazon' = Amazon CS forward (has 'Reason for contact'), 'seller' = our own reply, 'buyer' = the customer's own message."""
    if m.get("by"):
        return m["by"]
    raw = (m.get("raw") or "").strip()
    if m.get("reason") or raw.startswith("Dear Amazon Seller"):
        return "amazon"
    if raw.endswith("Badeja Enterprises"):
        return "seller"
    return "buyer"


def msg_text(m: dict) -> str:
    if m.get("text"):
        return m["text"]
    return (m.get("reason") or "") if msg_by(m) == "amazon" else (m.get("raw") or "")


def thread_order(msgs: list[dict]) -> str | None:
    """Buyer follow-ups carry no order number: use the newest one anywhere in the thread."""
    return next((m.get("order_no") for m in reversed(msgs) if m.get("order_no")), None)


INTENT_F = OUT / "intent_overrides.json"
VALID_TAGS = {"cancel", "refund", "refundq", "returned", "notrec", "delay", "defect", "changemind", "abuse"}


def load_intents() -> dict:
    return json.loads(INTENT_F.read_text(encoding="utf-8")) if INTENT_F.exists() else {}


def is_past(deliver_by: str | None) -> bool:
    """True when Amazon's deliver-by date is already behind us ('Thu, 15 Oct, 2026 IST')."""
    d = fmt_date(deliver_by)
    try:
        return bool(d) and datetime.strptime(d, "%d %b %Y").date() < datetime.now().date()
    except ValueError:
        return False


RETURN_WINDOW_DAYS = 7                      # Sir 2026-10-20: return/replacement window, counted from the courier delivery date


def days_since(s: str | None) -> float | None:
    """'Oct 01, 2026 13:32' (Nimbus format, IST) -> days elapsed since then."""
    try:
        return (datetime.now() - datetime.strptime(s or "", "%b %d, %Y %H:%M")).total_seconds() / 86400
    except ValueError:
        return None


def fmt_time(s: str | None) -> str | None:
    m = re.search(r"(\d{1,2}):(\d{2})\s*$", s or "")
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def clean_loc(s: str | None) -> str | None:
    """Courier facility name for the text: 'Jewar_SJRoad_D (Uttar Pradesh)' -> 'Jewar SJRoad D (Uttar Pradesh)'. ASCII only, no @ or links."""
    t = re.sub(r"[^A-Za-z0-9 ()\-,.]", " ", (s or "").replace("_", " "))
    t = re.sub(r"\s+", " ", t).strip()
    return t[:70] or None


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
         "deliver_by": fmt_date(op.get("deliver_by")), "amount": f"{max(op.get('refunds') or [0]):,.2f}", "delivered_date": fmt_date(tr.get("delivered_at"))}
    d_at = fmt_date(tr.get("delivered_at"))
    f["clause_en"] = {"DELIVERED": f" and was delivered on {d_at}", "OUT_FOR_DELIVERY": " and is out for delivery"}.get(st, " and is on its way" + ("" if is_past(op.get("deliver_by")) else f". Amazon's estimated delivery date is {f['deliver_by']}"))
    f["status_en"] = status_phrase(tr)[0]
    f["rto_en"] = "the shipment was returned to us and " if st in RTO else ""
    t_at = fmt_time(tr.get("delivered_at"))                                  # T7 proof fields
    loc = clean_loc((tr.get("latest") or {}).get("location")) if st == "DELIVERED" else None
    f["when_en"] = f"{d_at} at {t_at}" if t_at else f"{d_at}"
    f["loc_en"] = f", last scan location: {loc}" if loc else ""
    f["t1_tail"] = (" If you have a concern about the product, please share the details in this chat so that we can look into it." if st == "DELIVERED" else
                    " Please accept the shipment, or refuse it at the time of delivery. The refund will be processed once the return to origin (RTO) has been initiated and the shipment is in transit back to us.")
    rto_d = fmt_date((tr.get("latest") or {}).get("at"))
    f["rto_verb"] = "was returned" if st == "RTO_RECEIVED" else "is being returned"
    f["rto_status"] = (f"returned to the seller on {rto_d}" if st == "RTO_RECEIVED" else f"in transit back to the seller, last updated on {rto_d}")
    past = is_past(op.get("deliver_by"))
    f["eta_clause"] = "" if past else f" The estimated delivery date shown by Amazon for this order is {f['deliver_by']}."
    f["t3_lead"] = "we apologise for the delay. The shipment is in transit with" if past else "your shipment is in transit with"
    f["whatsapp"] = support_number() or ""
    f["ver_en"] = " The courier's record shows this delivery as verified." if tr.get("delivery_verified") else ""
    text = TEMPLATES[tid]["en"].format(**f)
    if tid == "T5" and not f["rto_en"] and lang == "en":
        text = text.replace(": a refund", ": A refund")
    return text


def state_of(tr: dict | None) -> str | None:
    return (tr or {}).get("state")


def decide(case: dict) -> dict:
    """Deterministic scenario choice. Returns {scenario, template, action, code, why}; action SEND or ESCALATE."""
    def esc(code, why, scenario="S11"):
        return {"scenario": scenario, "template": None, "action": "ESCALATE", "code": code, "why": why}
    msgs, facts = case.get("messages") or [], case.get("facts") or {}
    if case.get("error") or not msgs:
        return esc("FACTS_MISSING", "case could not be read")
    by = [msg_by(m) for m in msgs]
    if by[-1] == "seller":
        return {"scenario": "-", "template": None, "action": "SKIP", "code": "WAITING_BUYER", "why": "the last message in the thread is ours: waiting for the buyer"}
    buyer_msgs = [m for m, b in zip(msgs, by) if b != "seller"]
    intent = {t for t in (case.get("intent_tags") or []) if t in VALID_TAGS}       # set by the agent after reading a message the regexes cannot (other language, Devanagari)
    t_last, t_all = (set(intent), set(intent)) if intent else (tags_of(msg_text(buyer_msgs[-1])), tags_of(" ".join(msg_text(m) for m in buyer_msgs)))
    last_amz = max((i for i, b in enumerate(by) if b == "amazon"), default=-1)
    seller_replied = "seller" in by[last_amz + 1:]               # we already answered the newest Amazon forward: this is a follow-up
    mine = " ".join(m.get("raw") or m.get("text") or "" for m, b in zip(msgs, by) if b == "seller")
    if "abuse" in t_all:
        return esc("SENSITIVE", "legal / fraud / A-to-z wording: Sir only", "S8")
    if facts.get("language") not in ("English", "Hindi") and not intent:
        return esc("LANGUAGE", f"thread language {facts.get('language')}: the agent reads the message, translates the intent and records it with the `intent` command, then re-plans (reply stays English)")
    if not thread_order(msgs):
        subj = (case.get("subject") or "").lower()
        if seller_replied:
            return esc("FOLLOWUP_NEEDS_SIR", "buyer replied to our pre-sales answer: Sir reads it", "S6")
        if not msg_text(buyer_msgs[-1]).strip() or subj.startswith(("update from seller", "important update")):
            return esc("PRESALES_OR_NO_ORDER", "no order and no readable question (seller-initiated / empty forward): Sir decides", "S6")
        return {"scenario": "S6", "template": "T12", "action": "SEND", "code": "PRESALES_GENERIC", "alert": True,
                "why": "pre-sales question without an order (Sir 2026-10-21): generic reply, Sir is alerted to answer the specifics"}
    op, tr = facts.get("order_page"), facts.get("tracking")
    if not op:
        return esc("FACTS_MISSING", "order page not read")
    ret_req = any((m.get("return_requested") or "").lower().startswith("yes") for m in msgs)
    returned = "returned" in t_last or ret_req                  # a customer-initiated return: NEVER refunded by us (SAFE-T), Sir is informed with the delivery facts
    delivery_note = f"tracker {state_of(tr)}, delivered {(tr or {}).get('delivered_at')}, code verified={(tr or {}).get('delivery_verified')}"
    state = (tr or {}).get("state")
    if re.search("cancel", op.get("status") or "", re.I) and tr and state in ("NOT_MOVING", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "EXCEPTION"):
        return {"scenario": "S1", "template": None, "action": "ESCALATE", "code": "CANCELLED_BUT_SHIPMENT_ACTIVE", "alert": True,
                "sir_action": f"STOP: order {thread_order(msgs)} is cancelled on Amazon but the Nimbus shipment {op.get('tracking_id')} is {state} (last scan {(tr.get('latest') or {}).get('at')}). Cancel the shipment in Nimbus NOW and make sure nothing is physically dispatched (Amazon cancel does not cancel Nimbus).",
                "why": f"order cancelled on Amazon but the shipment is still {state} in Nimbus"}
    if re.search("cancel", op.get("status") or "", re.I) and state == "CANCELLED":
        return esc("CANCEL_DONE", "order cancelled on Amazon and the Nimbus shipment is cancelled too: what to send / whether to resolve is Sir's call (not decided yet)", "S1")
    if op.get("refunds") and t_last & {"refund", "refundq", "cancel", "returned", "notrec"}:
        if seller_replied:                                                          # Sir 2026-10-21: refund not seen -> Amazon Customer Support by phone (T11), once
            if any(mk in mine for mk in T11_MARKS):
                return esc("REFUND_QUERY_REPEAT", "buyer asks about the refund again after we pointed to Amazon Customer Support: Sir checks", "S5")
            return {"scenario": "S5", "template": "T11", "action": "SEND", "code": "REFUND_ISSUED_ASK_AMAZON", "why": f"refund {op['refunds']} is already on the order page; buyer asks again: Amazon Customer Support by phone"}
        return {"scenario": "S5", "template": "T5", "action": "SEND", "code": "REFUND_PROCESSED", "why": f"refund {op['refunds']} is on the order page"}
    if not tr or state in ("ERROR", "NOT_FOUND", "UNKNOWN", "ORDER_MISMATCH"):
        return esc("TRACKING_UNVERIFIED", f"tracker state {state}")
    if tr.get("notes"):
        return esc("TRACKING_CONFLICT", "; ".join(tr["notes"]))
    if state in RTO:
        lt = tr.get("latest") or {}
        card = (f"REFUND DUE (RTO, refund eligible): order {thread_order(msgs)} | Rs {op.get('grand_total') or '?'} | {op.get('carrier')} {op.get('tracking_id')} | RTO {state}, last scan {lt.get('at')} {lt.get('location')} ({lt.get('remark')}) | "
                "guardrails OK: tracker order id matches, no conflicting scans, no refund on the order page | Sir: Seller Central > Manage Orders > open the order > Refund order (full refund, reason: customer refused / undelivered RTO)")
        if any(mk in mine for mk in T14_MARKS):                                    # the buyer already has the status: only Sir's refund step is left
            return {"scenario": "S5", "template": None, "action": "ESCALATE", "code": "REFUND_PENDING", "sir_action": card,
                    "why": f"RTO {state}, buyer already told (T14), no refund on the order page yet: Sir issues the refund"}
        return {"scenario": "S5", "template": "T14", "action": "SEND", "code": "RTO_STATUS_REFUND_DUE", "alert": True, "sir_action": card,
                "why": f"RTO {state} (customer refused / undelivered): status to the buyer + refund card for Sir (Sir 2026-10-21; Samvaad never refunds)"}
    if "refundq" in t_last and not (t_last & {"defect"} or returned):
        return esc("REFUND_STATUS_QUERY", "buyer asks where a refund is (not a new product claim): Sir checks", "S5")
    if seller_replied and state == "DELIVERED" and "notrec" in t_last:             # delivery DISPUTE (Sir 2026-10-20): facts-only proof, once
        if any(mk in mine for mk in T7_MARKS):
            return esc("DELIVERY_DISPUTE_REPEAT", "buyer still says not received after our tracking-proof reply: Sir checks the carrier POD / handles the claim", "S11")
        if not tr.get("delivered_at"):
            return esc("DELIVERY_UNVERIFIED", "dispute but the tracker has no delivery time", "S11")
        return {"scenario": "S11", "template": "T7", "action": "SEND", "code": "DELIVERY_DISPUTE_PROOF", "alert": True, "proof": True,
                "why": "buyer disputes a delivered shipment: text-only courier facts, tracker screenshot saved for Sir (Sir 2026-10-20), Sir is alerted"}
    if seller_replied:                                                              # templates are first answers; a follow-up is for Sir
        if returned:
            return esc("RETURN_CLAIM_UNVERIFIED", f"customer-initiated return (follow-up after our reply): do NOT refund (SAFE-T); {delivery_note}: Sir decides", "S5")
        return esc("FOLLOWUP_NEEDS_SIR", "buyer wrote again after our reply and it is not a delivery dispute: Sir reads it", "S11")
    if "cancel" in t_last or ("changemind" in t_last and state != "DELIVERED"):
        if state in MOVING:
            return {"scenario": "S1", "template": "T1", "action": "SEND", "code": "CANCEL_SHIPPED", "why": f"tracker {state}"}
        card = (f"CANCEL ORDER (not moving): order {thread_order(msgs)} | {op.get('carrier')} {op.get('tracking_id')} tracker {state}, last scan {((tr or {}).get('latest') or {}).get('at')} | "
                "STEP 1 Nimbus: cancel the shipment FIRST (confirm it has not been picked up) | STEP 2 Amazon: cancel the order | "
                "WARNING: cancelling on Amazon does NOT cancel Nimbus (this caused physical dispatches before). Samvaad guides, Sir executes; if the order page already shows Canceled while the Nimbus shipment is active, Samvaad raises a STOP alert.")
        return {"scenario": "S2", "template": None, "action": "ESCALATE", "code": "CANCEL_NOT_SHIPPED", "sir_action": card, "why": f"cancel asked while tracker is {state}: Sir cancels Nimbus first, then Amazon"}
    if "changemind" in t_last and state == "DELIVERED" and not t_last & {"defect", "notrec"}:      # Sir 2026-10-21: change of mind -> policy reply
        return {"scenario": "S4", "template": "T13", "action": "SEND", "code": "CHANGE_OF_MIND_POLICY", "why": "change of mind on a delivered order: return policy reply"}
    if t_last & {"notrec", "delay"} and "defect" not in t_last:
        if state in ("IN_TRANSIT", "OUT_FOR_DELIVERY"):
            return {"scenario": "S3", "template": "T3", "action": "SEND", "code": "ETA", "why": f"tracker {state}"}
        if state == "NOT_MOVING":
            return {"scenario": "S2", "template": "T2", "action": "SEND", "code": "DELAY_NOT_MOVING", "why": "shipment has not started moving"}
        if state != "DELIVERED":
            return esc("TRACKING_UNVERIFIED", f"buyer asks about the parcel but the tracker state is {state}: Sir reads it", "S11")
        if "notrec" in t_last:
            return {"scenario": "S11", "template": "T6", "action": "SEND", "code": "DELIVERED_NOT_RECEIVED", "alert": True,
                    "why": "tracker says delivered, buyer says not received: delivery facts + check with family/neighbours (Sir 2026-10-17), Sir is alerted"}
        return esc("DELIVERED_TRACKING_QUERY", "buyer asks about tracking/status but does not say the parcel is missing and the tracker says delivered: Sir reads it", "S11")
    if "defect" in t_last or ("refund" in t_last and not returned):
        if state == "DELIVERED" and tr.get("delivery_verified"):
            days = days_since(tr.get("delivered_at"))
            if days is None:
                return esc("DELIVERY_UNVERIFIED", "defect asked but the tracker has no delivery date to check the return/replacement window", "S4")
            if days > RETURN_WINDOW_DAYS:                                           # Sir 2026-10-21: window over -> WhatsApp support guidance (T10), automatic
                if not support_number():
                    return esc("WINDOW_CROSSED", f"defect/refund asked {days:.0f} days after delivery (window {RETURN_WINDOW_DAYS} days) and no support_whatsapp number is set: Sir answers", "S4")
                return {"scenario": "S4", "template": "T10", "action": "SEND", "code": "WINDOW_CROSSED_WHATSAPP", "alert": True,
                        "why": f"defect/refund asked {days:.0f} days after delivery (window {RETURN_WINDOW_DAYS} days): WhatsApp-support guidance (Sir 2026-10-21), Sir is alerted"}
            return {"scenario": "S4", "template": "T9", "action": "SEND", "code": "DEFECT_IN_WINDOW", "why": f"delivered {days:.0f} days ago, code verified: guide to share photos here, then raise a replacement request"}
        return esc("DELIVERY_UNVERIFIED", f"defect/refund asked but delivery state is {state}, verified={tr.get('delivery_verified')}", "S4")
    if returned:
        return esc("RETURN_CLAIM_UNVERIFIED", f"customer-initiated return / return requested, no RTO: do NOT refund (SAFE-T); {delivery_note}: Sir decides", "S5")
    return esc("UNKNOWN", "no rule matched")


def make_item(case: dict, sent_keys: set[str]) -> dict:
    d = decide(case)
    msgs = case.get("messages") or []
    order_no = (case.get("facts") or {}).get("order_no") or thread_order(msgs)
    facts = {**(case.get("facts") or {}), "order_no": order_no}
    buyer_msgs = [m for m in msgs if msg_by(m) != "seller"]
    tr, op = facts.get("tracking") or {}, facts.get("order_page") or {}
    it = {"name": case.get("name"), "order_no": order_no, "key": case.get("key"), "language": facts.get("language"), "sla": case.get("sla"),
          "reason": (msg_text(buyer_msgs[-1]) if buyer_msgs else "")[:300], **d, "text": None, "lint": [], "resolve_after": False}
    if d.get("proof"):
        it["proof_awb"] = op.get("tracking_id") or tr.get("awb")
    if d["action"] == "SEND":
        lang = "en"
        it["text"] = render(d["template"], lang, facts)
        it["lint"] = lint(it["text"], facts, d["template"], lang)
        it["resolve_after"] = TEMPLATES[d["template"]]["resolve"]
        if it["lint"]:
            it.update(action="ESCALATE", code="LINT_FAILED", why="; ".join(it["lint"]))
    if it["key"] in sent_keys and it["action"] == "SEND":
        it.update(action="SKIP", code="ALREADY_REPLIED", why="sent_log has this message key")
    return it


# ------------------------------------------------------------------ state / log
_support_override: str | None = None            # selftest only


def support_number() -> str | None:
    """WhatsApp support number for T10, from samvaad_state.json ("support_whatsapp"); None = T10 off (case escalates as WINDOW_CROSSED)."""
    n = _support_override if _support_override is not None else load_state().get("support_whatsapp")
    return n if n and re.fullmatch(r"[6-9][0-9]{9}", str(n)) else None


def load_state() -> dict:
    base = {"auto_send": False, "auto_resolve": False, "max_per_run": 12, "max_per_day": 25, "support_whatsapp": None}
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
    intents = load_intents()
    for c in d["cases"]:
        if intents.get(c.get("key")):
            c["intent_tags"] = intents[c["key"]]
    items = [make_item(c, sent) for c in d["cases"]]
    st = load_state()
    (OUT / "plan.json").write_text(json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"), "checked_at": d.get("checked_at"), "state": st, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    for it in items:
        print(f"{it['name']:11s} | {it['order_no']} | {it['action']:8s} | {it['scenario']} {it['template'] or '--'} | {it['code']} | {it['why'][:90]}")
        if it.get("sir_action"):
            print("    >> SIR ACTION: " + it["sir_action"])
        if it["text"]:
            print("    " + it["text"].replace("\n", "\n    "))
    print(f"mode: auto_send={st['auto_send']} auto_resolve={st['auto_resolve']} | SEND={sum(i['action']=='SEND' for i in items)} ESCALATE={sum(i['action']=='ESCALATE' for i in items)} SKIP={sum(i['action']=='SKIP' for i in items)}")
    return 0


def cmd_templates() -> int:
    for tid, t in TEMPLATES.items():
        print(f"== {tid}: {t['name']} (resolve after send: {t['resolve']})\n{t['en']}\n")
    return 0


def cmd_intent(args: list[str]) -> int:
    """intent --case <name|order> --tags cancel,delay : the agent records the buyer's intent for a message the regexes cannot read (other language, Devanagari).
    Only the scenario choice changes; the reply is still an English template + facts + lint. Tags: """ + ", ".join(sorted(VALID_TAGS)) + """."""
    if "--case" not in args or "--tags" not in args:
        print("usage: intent --case <name|order> --tags tag1,tag2   (tags: " + ", ".join(sorted(VALID_TAGS)) + ")"); return 2
    who, tags = args[args.index("--case") + 1], [t for t in args[args.index("--tags") + 1].split(",") if t]
    bad = [t for t in tags if t not in VALID_TAGS]
    if bad or not tags:
        print("INVALID tags:", bad or "none given"); return 2
    d = json.loads((OUT / "latest.json").read_text(encoding="utf-8"))
    case = next((c for c in d["cases"] if who.lower() in (c.get("name") or "").lower() or who == thread_order(c.get("messages") or [])), None)
    if not case:
        print("NOT_FOUND: no such case in latest.json"); return 4
    cur = load_intents(); cur[case["key"]] = tags
    INTENT_F.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"intent saved for {case['name']} ({case['key']}): {tags}; run `plan` again"); return 0


def capture_proof(ctx, awb: str, order_no: str) -> tuple[str | None, str | None]:
    """Screenshot of the public Nimbus tracking page (evidence for Sir; never sent to the buyer). Returns (path, error)."""
    d = OUT / "proof"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{order_no}_{awb}_{datetime.now():%Y%m%d-%H%M}.png"
    pg = ctx.new_page()
    try:
        pg.goto(f"https://ship.nimbuspost.com/trk/{awb}", wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(5000)
        if str(awb) not in pg.evaluate("() => document.body.innerText"):
            return None, "tracker page does not show the tracking id"
        pg.screenshot(path=str(path), full_page=True)
        return str(path), None
    except Exception as e:
        return None, str(e)[:150]
    finally:
        pg.close()


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
    force = args[args.index("--force-template") + 1] if "--force-template" in args else None
    if force:                                       # Sir picks the template for ONE case (still template + facts + lint, never free text)
        if not (only and approve) or force not in TEMPLATES:
            print("BLOCKED: --force-template <T#> needs --only <case> --approve and an existing template"); return 4
        latest = json.loads((OUT / "latest.json").read_text(encoding="utf-8"))
        case = next((c for c in latest["cases"] if only.lower() in (c.get("name") or "").lower() or only == thread_order(c.get("messages") or [])), None)
        if not case:
            print("NOT_FOUND: no such case in latest.json"); return 4
        it = make_item(case, {x["key"] for x in read_log() if x.get("sent") and not x.get("dry")})
        if it["action"] == "SKIP":
            print(f"SKIPPED: {it['code']} ({it['why']})"); return 0
        facts = {**(case.get("facts") or {}), "order_no": it["order_no"]}
        lang = "en"
        text = render(force, lang, facts)
        errs = lint(text, facts, force, lang)
        if errs:
            print("LINT_FAILED:", "; ".join(errs)); return 6
        it.update(action="SEND", template=force, text=text, lint=[], code="SIR_FORCED_TEMPLATE", why=f"Sir approved template {force} for this case", resolve_after=False)
        items = [it]
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
            if it.get("proof_awb"):                                   # dispute proof: tracker screenshot saved for Sir (non-fatal if it fails)
                rec["proof_path"], rec["proof_error"] = capture_proof(ctx, it["proof_awb"], it["order_no"])
            try:
                p.goto(INBOX, wait_until="domcontentloaded", timeout=60000); p.wait_for_timeout(12000)
                if "/ap/signin" in p.url:
                    rec["error"] = "LOGIN_REQUIRED"; results.append(rec); break
                p.get_by_text(it["name"], exact=True).first.click(timeout=8000); p.wait_for_timeout(3000)
                pane = p.evaluate("() => document.body.innerText")
                for _ in range(8):                                    # the pane can take a few seconds to render the clicked case
                    if it["order_no"] in pane:
                        break
                    p.wait_for_timeout(2000); pane = p.evaluate("() => document.body.innerText")
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
        print(f"{r['name']:11s} {r['order_no']} {r['template']} dry={r['dry']} sent={r['sent']} verified={r['verified']} resolved={r['resolved']} {r.get('error', '')}"
              + (f" proof={r.get('proof_path') or 'MISSING ' + str(r.get('proof_error'))}" if r["template"] == "T7" else ""))
    return 0


# ------------------------------------------------------------------ tests
def cmd_selftest() -> int:
    global _support_override
    _support_override = ""                      # tests never depend on the live samvaad_state.json
    good_facts = {"order_no": "402-1292244-5057153", "buyer_names": ["Himani", "Tushar"], "order_page": {"tracking_id": "4218630821242", "carrier": "Delhivery", "deliver_by": "Mon, 28 Sept, 2026 IST", "refunds": [3149.8]},
                  "tracking": {"awb": "4218630821242", "state": "DELIVERED", "delivered_at": "Sep 22, 2026 17:24", "delivery_verified": True, "latest": {"at": "Sep 22, 2026 17:24"}}}
    ok_text = render("T1", "en", good_facts)
    cases = [("good T1 passes", ok_text, [], True), ("url", ok_text.replace("Regards,", "Visit https://x.com\nRegards,"), [], False), ("domain repairfully.com", ok_text.replace("Regards,", "repairfully.com\nRegards,"), [], False),
             ("phone", ok_text.replace("Regards,", "Call 9876543210\nRegards,"), [], False), ("email", ok_text.replace("Regards,", "a@b.com\nRegards,"), [], False), ("emoji", ok_text.replace("Dear Customer,", "Dear 😊,"), [], False),
             ("refund promise", ok_text.replace("Regards,", "We will refund you.\nRegards,"), [], False), ("unknown number", ok_text.replace("Regards,", "Delivery in 5 days.\nRegards,"), [], False),
             ("customer name", ok_text.replace("Dear Customer,", "Dear Himani,"), [], False), ("triple newline", ok_text.replace("Regards,", "\n\nRegards,"), [], False),
             ("review request", ok_text.replace("Regards,", "Please leave a review.\nRegards,"), [], False),              ("no sign-off", ok_text.replace("Badeja Enterprises", "Team"), [], False)]
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
        for lang in ("en",):
            e = lint(render(tid, lang, good_facts), good_facts, tid)
            print(("PASS " if not e else "FAIL ") + f"{tid}/{lang} renders and lints" + (f" <- {e}" if e else "")); fails += bool(e)
    # decision tests (synthetic cases)
    def case(reason, state, refunds=(), notes=(), lang="English", verified=True, order_page=True, subject="Order enquiry from Amazon customer Test", ago=2):
        tr = {"awb": "111111111111", "state": state, "courier": "Delhivery", "delivery_verified": verified, "notes": list(notes), "delivered_at": (datetime.now() - timedelta(days=ago)).strftime("%b %d, %Y %H:%M"), "latest": {"at": "Oct 12, 2026 18:03"}}
        op = {"carrier": "Delhivery", "tracking_id": "111111111111", "deliver_by": "Mon, 28 Sept, 2026 IST", "refunds": list(refunds), "status": "Sent"}
        return {"name": "Test", "key": "1|1", "subject": subject, "messages": [{"order_no": "400-0000000-0000000", "reason": reason}],
                "facts": {"order_no": "400-0000000-0000000", "language": lang, "order_page": op if order_page else None, "tracking": tr, "buyer_names": ["Test"]}}
    dec = [("cancel + in transit -> T1", case("cx want to cancel", "IN_TRANSIT"), "T1"), ("cancel + delivered -> T1", case("cancel the item", "DELIVERED"), "T1"),
           ("cancel + not moving -> escalate", case("cancel", "NOT_MOVING"), None), ("where is my order + in transit -> T3", case("when will I get my package", "IN_TRANSIT"), "T3"),
           ("delay + not moving -> T2", case("order is too delay", "NOT_MOVING"), "T2"), ("not received + delivered -> T6", case("customer not received order but showing delivered", "DELIVERED"), "T6"),
           ("defective + delivered verified, inside window -> T9", case("received a defective product", "DELIVERED"), "T9"), ("defective + delivered unverified -> escalate", case("received a defective product", "DELIVERED", verified=False), None),
           ("refund + RTO, no refund yet -> T14 (status + refund card for Sir)", case("want refund", "RTO_RECEIVED"), "T14"), ("refund + refund on page -> T5", case("want refund", "RTO_RECEIVED", refunds=[999.0]), "T5"),
           ("legal wording -> escalate", case("customer will send a lawyer notice", "DELIVERED"), None), ("A to Z claim -> escalate", case("A to Z claim filed", "DELIVERED"), None),
           ("tracking conflict -> escalate", case("cancel", "DELIVERED", notes=["refusal scan"]), None), ("Hindi-locale cancel + in transit -> English T1", case("cancel", "IN_TRANSIT", lang="Hindi"), "T1"),
           ("language Tamil -> escalate", case("cancel", "IN_TRANSIT", lang="Tamil"), None), ("no order page -> escalate", case("cancel", "IN_TRANSIT", order_page=False), None),
           ("returned claim, no refund, delivered -> escalate", case("customer already returned the item", "DELIVERED"), None),
           ("defective + window crossed (20 days) -> escalate", case("received a defective product", "DELIVERED", ago=20), None),
           ("Hindi-locale defective inside window -> English T9", case("product kharab hai defective", "DELIVERED", lang="Hindi"), "T9")]
    for name, c, want in dec:
        it = make_item(c, set())
        okd = (it["action"] == "SEND" and it["template"] == want) if want else it["action"] == "ESCALATE"
        if want and "Hindi" in name:
            okd = okd and it["text"].startswith("Dear Customer")
        fails += not okd
        print(("PASS " if okd else "FAIL ") + "decide: " + name + f"  [{it['action']} {it['template']} {it['code']}]")
    # thread tests: follow-ups, delivery dispute (T7), repeats, tracking-status queries
    def thread(msgs, state="DELIVERED", lang="English", verified=True, refunds=()):
        tr = {"awb": "222222222222", "state": state, "courier": "Bluedart", "delivery_verified": verified, "notes": [], "delivered_at": "Oct 01, 2026 12:34",
              "latest": {"at": "Oct 01, 2026 12:34", "location": "Jewar_SJRoad_D (Uttar Pradesh)", "remark": "Delivered"}}
        op = {"carrier": "Bluedart", "tracking_id": "222222222222", "deliver_by": "Mon, 12 Oct, 2026 IST", "refunds": list(refunds), "status": "Sent"}
        return {"name": "Test", "key": "408-0000000-0000000|x", "subject": "Order enquiry from Amazon customer Test", "messages": msgs,
                "facts": {"order_no": "408-0000000-0000000", "language": lang, "order_page": op, "tracking": tr, "buyer_names": ["Test"]}}
    def AMZ(reason): return {"order_no": "408-0000000-0000000", "reason": reason, "raw": "Dear Amazon Seller,\nReason for contact: " + reason}
    ME = {"order_no": None, "reason": None, "raw": "Hello,\nRegarding your order 408-0000000-0000000: our records show delivered.\nRegards,\nBadeja Enterprises"}
    ME7 = {"order_no": None, "reason": None, "raw": "Hello,\nRegarding your order 408-0000000-0000000: Delivery was recorded on 1 Oct 2026.\nRegards,\nBadeja Enterprises"}
    def BUY(t): return {"order_no": None, "reason": None, "raw": "Hello,\n" + t}
    NR = AMZ("customer not received order but showing delivered")
    tests = [("dispute after T6 -> T7 (proof, alert)", thread([NR, ME, BUY("still not received the parcel, please check")]), "SEND", "T7", "DELIVERY_DISPUTE_PROOF"),
             ("dispute repeats after T7 -> escalate", thread([NR, ME, BUY("not received"), ME7, BUY("I did not receive it")]), "ESCALATE", None, "DELIVERY_DISPUTE_REPEAT"),
             ("tracking-status query on a delivered order -> escalate (T6 misfire fix)", thread([AMZ("Customer receive the item on 1 Oct but the tracking still didnt updated, kindly update the tracking")]), "ESCALATE", None, "DELIVERED_TRACKING_QUERY"),
             ("follow-up that is not a dispute -> escalate", thread([AMZ("want refund"), ME, BUY("please refund quickly")]), "ESCALATE", None, "FOLLOWUP_NEEDS_SIR"),
             ("follow-up returned claim -> escalate", thread([AMZ("issue"), ME, BUY("i already returned the item but not received refund")]), "ESCALATE", None, "RETURN_CLAIM_UNVERIFIED"),
             ("last message is ours -> skip", thread([NR, ME]), "SKIP", None, "WAITING_BUYER"),
             ("'did not receive my refund' is not a not-received parcel -> not T6", thread([AMZ("I did not receive my refund")]), "ESCALATE", None, "REFUND_STATUS_QUERY"),
             ("fresh Amazon forward after our reply is a new first answer", thread([AMZ("old"), ME, AMZ("cancel the order")]), "SEND", "T1", None),
             ("not received + tracker EXCEPTION -> escalate", thread([AMZ("order not received")], state="EXCEPTION"), "ESCALATE", None, "TRACKING_UNVERIFIED"),
             ("T7 with a Hindi-locale buyer is answered in English", thread([NR, ME, BUY("abhi tak nahi mila, not received")], lang="Hindi"), "SEND", "T7", None)]
    for name, c, want_action, want_tpl, want_code in tests:
        it = make_item(c, set())
        okd = it["action"] == want_action and (want_tpl is None or it["template"] == want_tpl) and (want_code is None or it["code"] == want_code)
        if want_tpl == "T7":
            okd = okd and it.get("proof") and it.get("alert") and it["proof_awb"] == "222222222222" and it["order_no"] == "408-0000000-0000000" and not it["lint"]
            okd = okd and "http" not in it["text"] and "12:34" in it["text"] and "Jewar SJRoad D" in it["text"] and any(mk in it["text"] for mk in T7_MARKS)
            okd = okd and it["text"].startswith("Dear Customer")
        fails += not okd
        print(("PASS " if okd else "FAIL ") + "thread: " + name + f"  [{it['action']} {it['template']} {it['code']}]")
    it = make_item(case("received a defective product", "DELIVERED", ago=20), set())
    okd = it["action"] == "ESCALATE" and it["code"] == "WINDOW_CROSSED"
    fails += not okd; print(("PASS " if okd else "FAIL ") + f"window crossed -> WINDOW_CROSSED [{it['action']} {it['code']}]")
    it = make_item(case("received a defective product", "DELIVERED"), set())
    okd = it["template"] == "T9" and not it["lint"] and "replacement request" in it["text"] and "photos" in it["text"] and "http" not in it["text"]
    fails += not okd; print(("PASS " if okd else "FAIL ") + "T9 text: photos here + replacement request, lint clean")
    bad = lint(it["text"].replace("Regards,", "We will replace it.\nRegards,"), {"order_no": "400-0000000-0000000"}, "T9")
    okd = any("banned wording" in e for e in bad)
    fails += not okd; print(("PASS " if okd else "FAIL ") + "T9 still blocks a replacement promise")
    for lang_name, lang_tag in (("English", "en"), ("Hindi", "hi")):                # T10 WhatsApp guidance (Sir 2026-10-21), only with a number set
        _support_override = "9876501234"
        it = make_item(case("received a defective product", "DELIVERED", ago=20, lang=lang_name), set())
        okd = it["action"] == "SEND" and it["template"] == "T10" and it.get("alert") and not it["lint"] and "9876501234" in it["text"] and it["code"] == "WINDOW_CROSSED_WHATSAPP"
        fails += not okd; print(("PASS " if okd else "FAIL ") + f"window crossed + number set -> T10 {lang_tag} [{it['action']} {it['template']} {it['code']}] {it['lint']}")
        e_other = lint(it["text"], {"order_no": "400-0000000-0000000"}, "T9", lang_tag)
        okd = any(("phone" in e) or ("whatsapp" in e.lower()) or ("व्हाट्सएप" in e) for e in e_other)
        fails += not okd; print(("PASS " if okd else "FAIL ") + f"the number / WhatsApp wording is blocked outside T10 ({lang_tag})")
    _support_override = ""
    it = make_item(case("want refund asap", "DELIVERED"), set())
    okd = it["template"] == "T9" and "efund" not in it["text"] and "replacement request" in it["text"]
    fails += not okd; print(("PASS " if okd else "FAIL ") + "refund asked first, inside the window -> T9 asks for a replacement request only")
    t8 = render("T8", "en", {**thread([])["facts"]})
    e8 = lint(t8, thread([])["facts"], "T8")
    okd = not e8 and "1 Oct 2026" in t8 and "Bluedart" in t8
    fails += not okd; print(("PASS " if okd else "FAIL ") + "T8 renders and lints" + (f" <- {e8}" if e8 else ""))
    ME11 = {"order_no": None, "reason": None, "raw": "A refund of Rs 3,011.00 has already been issued for this order. Regards, Badeja Enterprises"}
    r_tests = [("refund issued, buyer says not received after our reply -> T11 (Amazon Customer Support)", thread([AMZ("refund issue"), ME, BUY("I did not receive my refund yet")], refunds=[3011.0]), "SEND", "T11", "REFUND_ISSUED_ASK_AMAZON"),
               ("T11 already sent, buyer asks again -> escalate", thread([AMZ("refund issue"), ME, BUY("no refund yet"), ME11, BUY("still no refund")], refunds=[3011.0]), "ESCALATE", None, "REFUND_QUERY_REPEAT"),
               ("refund asked first and a refund is on the page -> T5", thread([AMZ("want refund")], refunds=[3011.0]), "SEND", "T5", "REFUND_PROCESSED"),
               ("refund status asked, nothing issued -> escalate for Sir", thread([AMZ("refund issue"), ME, BUY("my refund is not received")]), "ESCALATE", None, "REFUND_STATUS_QUERY")]
    for name, c, want_action, want_tpl, want_code in r_tests:
        it = make_item(c, set())
        okd = it["action"] == want_action and (want_tpl is None or it["template"] == want_tpl) and (want_code is None or it["code"] == want_code)
        if want_tpl:
            okd = okd and not it["lint"] and "Amazon Customer Support" in it["text"] and "Rs 3,011.00" in it["text"]
        fails += not okd; print(("PASS " if okd else "FAIL ") + "refund: " + name + f"  [{it['action']} {it['template']} {it['code']}] {it['lint']}")
    # Sir 2026-10-21 round-1 answers: T1 rejection wording, pre-sales T12, change of mind T13, refund policy (never refund a customer return)
    e_x = lint(ok_text.replace("Regards,", "Refund later." + chr(10) + "Regards,"), good_facts, "T3")
    fails += not e_x; print(("PASS " if e_x else "FAIL ") + "refund wording is blocked outside T1 / T13 / T5 / T11")
    ship = [(n, make_item(c, set())) for n, c in (("cancel in transit", case("cancel", "IN_TRANSIT")), ("cancel delivered", case("cancel", "DELIVERED")))]
    okd = ("accept the shipment, or refuse it" in ship[0][1]["text"] and "return to origin (RTO)" in ship[0][1]["text"] and not ship[0][1]["lint"]
           and "accept the shipment" not in ship[1][1]["text"] and "concern about the product" in ship[1][1]["text"] and not ship[1][1]["lint"])
    fails += not okd; print(("PASS " if okd else "FAIL ") + "T1: in transit = accept or refuse + RTO refund line; delivered = product concern line")
    def PRE(t, subject="Enquiry from Amazon customer X"): return {"name": "Test", "key": "k", "subject": subject, "messages": [{"order_no": None, "reason": None, "raw": t, "by": "buyer"}],
                                                                  "facts": {"order_no": None, "language": "English", "order_page": None, "tracking": None, "buyer_names": []}}
    for name, c, want_action, want_tpl, want_code in [("pre-sales without order -> T12 + alert", PRE("Kya aapke pass oppo reno 10 pro ki display available hai"), "SEND", "T12", "PRESALES_GENERIC"),
                                                      ("empty seller-initiated update -> escalate", PRE("", "Update from Seller on Order ID 403-1"), "ESCALATE", None, "PRESALES_OR_NO_ORDER"),
                                                      ("Telugu pre-sales -> escalate", {**PRE("hello"), "facts": {"order_no": None, "language": "Telugu", "order_page": None, "tracking": None, "buyer_names": []}}, "ESCALATE", None, "LANGUAGE")]:
        it = make_item(c, set())
        okd = it["action"] == want_action and (want_tpl is None or it["template"] == want_tpl) and (want_code is None or it["code"] == want_code) and (not want_tpl or (not it["lint"] and it.get("alert")))
        fails += not okd; print(("PASS " if okd else "FAIL ") + "pre-sales: " + name + f"  [{it['action']} {it['template']} {it['code']}] {it['lint']}")
    c2 = PRE("what is the price"); c2["messages"] = [{"order_no": None, "reason": None, "raw": "what is the price", "by": "buyer"}, {"order_no": None, "reason": None, "raw": "Dear Customer, thanks. Regards, Badeja Enterprises", "by": "seller"}, {"order_no": None, "reason": None, "raw": "and cod?", "by": "buyer"}]
    it = make_item(c2, set()); okd = it["action"] == "ESCALATE" and it["code"] == "FOLLOWUP_NEEDS_SIR"
    fails += not okd; print(("PASS " if okd else "FAIL ") + "pre-sales follow-up after our generic reply -> escalate (one generic reply only)")
    it = make_item(case("I no longer want the item", "DELIVERED"), set())
    okd = it["template"] == "T13" and not it["lint"] and "7 days" in it["text"] and "warranty protection film" in it["text"]
    fails += not okd; print(("PASS " if okd else "FAIL ") + f"change of mind, delivered -> T13 policy reply [{it['action']} {it['template']} {it['code']}] {it['lint']}")
    it = make_item(case("I no longer want the item", "IN_TRANSIT"), set()); okd = it["template"] == "T1"
    fails += not okd; print(("PASS " if okd else "FAIL ") + "change of mind, still in transit -> T1 (shipped, accept or refuse)")
    ret = make_item(case("Item return kindly refund asap", "DELIVERED"), set())
    okd = ret["action"] == "ESCALATE" and ret["code"] == "RETURN_CLAIM_UNVERIFIED" and "SAFE-T" in ret["why"] and "code verified" in ret["why"]
    fails += not okd; print(("PASS " if okd else "FAIL ") + "customer return: escalate with delivery facts, never refund (SAFE-T)")
    c3 = case("want refund", "DELIVERED"); c3["messages"][0]["return_requested"] = "Yes"
    it = make_item(c3, set()); okd = it["action"] == "ESCALATE" and it["code"] == "RETURN_CLAIM_UNVERIFIED"
    fails += not okd; print(("PASS " if okd else "FAIL ") + "'Return requested: Yes' on the Amazon forward -> customer return, escalate")
    rto = make_item(case("want refund", "RTO_IN_TRANSIT"), set())
    okd = (rto["action"] == "SEND" and rto["template"] == "T14" and rto["code"] == "RTO_STATUS_REFUND_DUE" and rto.get("alert") and not rto["lint"]
           and "REFUND DUE" in rto["sir_action"] and "Refund order" in rto["sir_action"] and "in transit back to the seller" in rto["text"] and "Samvaad" not in rto["text"])
    fails += not okd; print(("PASS " if okd else "FAIL ") + f"RTO in transit -> T14 + refund card [{rto['action']} {rto['template']} {rto['code']}] {rto['lint']}")
    rto2 = make_item(case("want refund", "RTO_RECEIVED"), set()); okd = "returned to the seller on" in rto2["text"] and not rto2["lint"]
    fails += not okd; print(("PASS " if okd else "FAIL ") + "RTO received -> T14 says returned to the seller on <date>")
    c4 = case("want refund", "RTO_RECEIVED"); c4["messages"] += [{"order_no": None, "reason": None, "raw": "Dear Customer, the shipment could not be delivered and was returned to the seller. Regards, Badeja Enterprises", "by": "seller"},
                                                              {"order_no": None, "reason": None, "raw": "where is my refund", "by": "buyer"}]
    it = make_item(c4, set()); okd = it["action"] == "ESCALATE" and it["code"] == "REFUND_PENDING" and "REFUND DUE" in it["sir_action"]
    fails += not okd; print(("PASS " if okd else "FAIL ") + "RTO already told (T14) and the buyer asks again -> escalate with the refund card only")
    it = make_item(case("want refund", "RTO_RECEIVED", notes=["conflicting scan"]), set()); okd = it["action"] == "ESCALATE" and it["code"] == "TRACKING_CONFLICT"
    fails += not okd; print(("PASS " if okd else "FAIL ") + "guardrail: RTO with a conflicting scan is never auto-answered")
    it = make_item(case("The package arrived but an item is missing", "DELIVERED"), set())
    okd = it["template"] == "T9" and "unboxing video" in it["text"] and "warranty protection film" in it["text"] and not it["lint"]
    fails += not okd; print(("PASS " if okd else "FAIL ") + f"missing item inside the window -> T9 with unboxing video + warranty conditions [{it['action']} {it['template']} {it['code']}] {it['lint']}")
    # Sir 2026-10-21 round 3: EDD missed, cancel flow (Nimbus first), other languages via the agent's intent
    fut = (datetime.now() + timedelta(days=5)).strftime("%a, %d %b, %Y IST")
    def ship(ago_deliver_by, state="IN_TRANSIT", reason="where is my order", status="Sent", lang="English", tags=None, notes=()):
        c = case(reason, state, lang=lang, notes=notes); c["facts"]["order_page"]["deliver_by"] = ago_deliver_by; c["facts"]["order_page"]["status"] = status
        if tags: c["intent_tags"] = tags
        return c
    it = make_item(ship("Mon, 28 Sept, 2026 IST"), set()); okd = it["template"] == "T3" and "apologise for the delay" in it["text"] and "estimated delivery date" not in it["text"] and not it["lint"]
    fails += not okd; print(("PASS " if okd else "FAIL ") + f"EDD missed (deliver-by in the past) -> T3 apology + courier status, no stale date [{it['code']}] {it['lint']}")
    it = make_item(ship(fut), set()); okd = it["template"] == "T3" and "estimated delivery date shown by Amazon" in it["text"] and "apologise" not in it["text"] and not it["lint"]
    fails += not okd; print(("PASS " if okd else "FAIL ") + f"deliver-by in the future -> T3 shows the date [{it['code']}] {it['lint']}")
    it = make_item(ship("Mon, 28 Sept, 2026 IST", state="NOT_MOVING", reason="order is too delay"), set()); okd = it["template"] == "T2" and "estimated delivery date" not in it["text"] and not it["lint"]
    fails += not okd; print(("PASS " if okd else "FAIL ") + f"T2 with a past deliver-by drops the date [{it['code']}] {it['lint']}")
    it = make_item(ship(fut, state="NOT_MOVING", reason="kindly cancel this order"), set())
    okd = it["action"] == "ESCALATE" and it["code"] == "CANCEL_NOT_SHIPPED" and "STEP 1 Nimbus" in it["sir_action"] and "STEP 2 Amazon" in it["sir_action"] and "does NOT cancel Nimbus" in it["sir_action"]
    fails += not okd; print(("PASS " if okd else "FAIL ") + "cancel on a not-moving order -> escalate with the Nimbus-first cancel card")
    it = make_item(ship(fut, state="NOT_MOVING", reason="kindly cancel this order", status="Canceled"), set())
    okd = it["action"] == "ESCALATE" and it["code"] == "CANCELLED_BUT_SHIPMENT_ACTIVE" and it.get("alert") and it["sir_action"].startswith("STOP")
    fails += not okd; print(("PASS " if okd else "FAIL ") + "guardrail: cancelled on Amazon but the Nimbus shipment is still active -> STOP alert")
    it = make_item(ship(fut, state="CANCELLED", reason="kindly cancel this order", status="Canceled"), set())
    okd = it["action"] == "ESCALATE" and it["code"] == "CANCEL_DONE"
    fails += not okd; print(("PASS " if okd else "FAIL ") + "cancelled on Amazon and in Nimbus -> CANCEL_DONE (Sir decides the closing message)")
    it = make_item(ship("Mon, 28 Sept, 2026 IST", lang="Telugu", reason="telugu text the regexes cannot read"), set())
    okd = it["action"] == "ESCALATE" and it["code"] == "LANGUAGE" and "intent" in it["why"]
    fails += not okd; print(("PASS " if okd else "FAIL ") + "Telugu without an intent -> LANGUAGE escalate (agent must read it)")
    it = make_item(ship("Mon, 28 Sept, 2026 IST", lang="Telugu", reason="telugu text the regexes cannot read", tags=["delay"]), set())
    okd = it["action"] == "SEND" and it["template"] == "T3" and it["text"].startswith("Dear Customer") and not it["lint"]
    fails += not okd; print(("PASS " if okd else "FAIL ") + "Telugu + the agent's intent [delay] -> English T3")
    it = make_item(ship("Mon, 28 Sept, 2026 IST", lang="Telugu", reason="x", tags=["abuse"]), set())
    okd = it["code"] == "SENSITIVE"
    fails += not okd; print(("PASS " if okd else "FAIL ") + "intent [abuse] -> SENSITIVE, never answered")
    _support_override = None
    return 1 if fails else 0
    _support_override = None
    return 1 if fails else 0


def main() -> int:
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); return 0
    if a[0] == "plan":
        return cmd_plan()
    if a[0] == "send":
        return cmd_send(a[1:])
    if a[0] == "intent":
        return cmd_intent(a[1:])
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
