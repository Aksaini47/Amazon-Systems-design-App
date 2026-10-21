"""Cancel watchdog (Sir 2026-10-21): every order that is CANCELLED on Amazon must also be cancelled in Nimbus.

Why: cancelling on Amazon does NOT cancel the Nimbus shipment. Sir's flow is Nimbus first, then Amazon, but a human slip once let cancelled orders be
physically dispatched (loss). This read-only check cross-checks Amazon's Canceled orders (Manage Orders API, last 30 days) against Nimbus shipments
(the app's own shipment/list API, same visible Playwright profile) and raises an alert for every cancelled order whose Nimbus shipment is still alive.

  python agent/scripts/cancel_watchdog.py            live check (visible Playwright, the saved Seller Central + Nimbus logins)
  python agent/scripts/cancel_watchdog.py selftest   classification / dedupe unit tests

Exit codes: 0 done (alerts are in the output + data/mahika/inbox/cancel_watchdog.json) | 2 Seller Central login required | 3 profile busy | 4 error |
            5 Nimbus login required (the Amazon list is saved, no cross-check possible: Sir logs in to Nimbus in the Playwright window himself).
It never logs in, never cancels, never changes anything.
"""
from __future__ import annotations

import io
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "data" / "mahika" / "inbox"
STATE_F = OUT / "cancel_watchdog.json"
AMZ_ORDERS = "https://sellercentral.amazon.in/orders-v3?page=1"
AMZ_SEARCH = ("https://sellercentral.amazon.in/orders-api/search?limit=100&offset={off}&sort=order_date_desc&date-range=last-30&fulfillmentType=mfn"
              "&orderStatus=canceled&program={prog}&forceOrdersTableRefreshTrigger=false")

CANCELLED = {"cancelled", "canceled"}
RTO_INFO = {"rto", "rto in transit", "rto delivered", "rto initiated", "rto undelivered", "exception", "undelivered", "ndr"}      # expected when the buyer refused: no alert
PRE_PICKUP = {"booked", "pending pickup", "pickup scheduled", "manifested", "new", "ready to ship", "pickup pending", "awb assigned", "processing"}
DELIVERED = {"delivered"}
SEVERITY = {"OK_CANCELLED": 0, "NO_SHIPMENT": 0, "RTO_EXPECTED": 1, "CANCEL_NOW": 3, "STOP_DISPATCHED": 3, "DELIVERED_BUT_CANCELLED": 3}
ACTION = {
    "CANCEL_NOW": "Cancel this shipment in Nimbus NOW (not picked up yet) before the courier collects it.",
    "STOP_DISPATCHED": "STOP: the parcel is already with the courier although the order is cancelled on Amazon. Ask the courier to hold / return it (RTO) and do not let it be delivered.",
    "DELIVERED_BUT_CANCELLED": "The parcel was DELIVERED although the order is cancelled on Amazon: check the order and the buyer, this is a loss until resolved.",
}


def classify_status(status: str | None) -> str:
    s = (status or "").strip().lower()
    if s in CANCELLED:
        return "OK_CANCELLED"
    if s in RTO_INFO or s.startswith("rto"):
        return "RTO_EXPECTED"
    if s in PRE_PICKUP:
        return "CANCEL_NOW"
    if s in DELIVERED:
        return "DELIVERED_BUT_CANCELLED"
    return "STOP_DISPATCHED"                       # picked / in transit / out for delivery / anything unknown: treated as physically moving


def cross_check(canceled: list[dict], shipments: list[dict], orders: list[dict] | None = None) -> list[dict]:
    """canceled: [{order_id, order_date}], shipments: raw Nimbus shipment records, orders: raw Nimbus order records (fulfillment_status new / booked / cancelled).
    One verdict per Amazon-cancelled order (worst shipment wins). An order record is used only when the order has NO shipment record (its status then stands for the shipment)."""
    by: dict[str, list[dict]] = {}
    for sh in shipments:
        by.setdefault(str(sh.get("order_id") or ""), []).append(sh)
    for od in orders or []:
        oid = str(od.get("order_id") or "")
        if oid and oid not in by:
            by.setdefault(oid, []).append({"order_id": oid, "ship_status": od.get("fulfillment_status"), "awb_number": None, "created": od.get("order_date"), "pickup_time": None, "delivered_time": None, "_order_record": True})
    res = []
    for o in canceled:
        ships = by.get(o["order_id"], [])
        if not ships:
            res.append({**o, "verdict": "NO_SHIPMENT", "shipments": []}); continue
        verdicts = [(SEVERITY[classify_status(s.get("ship_status"))], classify_status(s.get("ship_status")), s) for s in ships]
        sev, worst, _ = max(verdicts, key=lambda v: v[0])
        res.append({**o, "verdict": worst, "shipments": [{"awb": s.get("awb_number"), "status": s.get("ship_status"), "created": s.get("created"), "pickup": s.get("pickup_time"),
                                                          "delivered": s.get("delivered_time")} for _, _, s in verdicts]})
    return res


def diff_alerts(results: list[dict], previous: dict) -> tuple[list[dict], dict]:
    """Flagged = severity >= 1. 'new' = not alerted before or the verdict changed. Returns (flagged with 'new' set, new alerted map)."""
    flagged, alerted = [], {}
    for r in results:
        if SEVERITY[r["verdict"]] >= 1:
            r = {**r, "new": previous.get(r["order_id"]) != r["verdict"]}
            flagged.append(r); alerted[r["order_id"]] = r["verdict"]
    return flagged, alerted


def fetch_amazon_canceled(p) -> list[dict] | None:
    """Manage Orders API replay, both programs, paged by 100. None = login required."""
    js = "async (url) => { const r = await fetch(url, {credentials: 'include'}); return {s: r.status, t: await r.text()}; }"
    seen: dict[str, dict] = {}
    for prog in ("selfship", "easyship"):
        off = 0
        while off < 3000:
            r = p.evaluate(js, AMZ_SEARCH.format(off=off, prog=prog))
            if r["s"] != 200:
                if off == 0 and prog == "selfship":
                    return None
                break
            orders = json.loads(r["t"]).get("orders") or []
            for o in orders:
                seen.setdefault(o["amazonOrderId"], {"order_id": o["amazonOrderId"], "order_date": o.get("orderDate"),
                                                     "qty_shipped": sum(int(i.get("quantityShipped") or 0) for i in (o.get("orderItems") or []))})
            if len(orders) < 100:
                break
            off += 100
    return list(seen.values())


def run_live() -> int:
    from playwright.sync_api import sync_playwright
    from mahika.playwright.session import CHROMIUM_PROFILE_DIR
    import nimbus_track
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(nimbus_track.IST)
    with sync_playwright() as pw:
        try:
            ctx = pw.chromium.launch_persistent_context(user_data_dir=str(CHROMIUM_PROFILE_DIR), headless=False, viewport={"width": 1400, "height": 950},
                                                        args=["--disable-blink-features=AutomationControlled"])
        except Exception as e:
            if re.search(r"existing browser session|ProcessSingleton|already in use|user data directory", str(e), re.I):
                print("PROFILE_BUSY"); return 3
            raise
        p = ctx.pages[0] if ctx.pages else ctx.new_page()
        p.goto(AMZ_ORDERS, wait_until="domcontentloaded", timeout=60000); p.wait_for_timeout(8000)
        if "/ap/signin" in p.url or p.locator("#ap_email, #auth-mfa-otpcode").count():
            print("LOGIN_REQUIRED (Seller Central)"); ctx.close(); return 2
        canceled = fetch_amazon_canceled(p)
        if canceled is None:
            print("LOGIN_REQUIRED (Seller Central orders API)"); ctx.close(); return 2
        print(f"Amazon: {len(canceled)} Canceled orders in the last 30 days")
        req = nimbus_track.capture_shipments_request(p)
        orders = []
        if req is not None:
            oreq = nimbus_track.capture_orders_request(p)               # orders that have no AWB yet (status new / booked / cancelled)
            if oreq is not None:
                orders = nimbus_track.replay_orders(p, oreq, now - timedelta(days=45), now)
        if req is None:
            ctx.close()
            (OUT / "cancel_watchdog_amazon_canceled.json").write_text(json.dumps(canceled, ensure_ascii=False), encoding="utf-8")
            print("NIMBUS_LOGIN_REQUIRED: no cross-check possible. Sir: log in to Nimbus (ship.nimbuspost.com) in the Playwright window yourself, then re-run.")
            print(f"RESULT: watchdog incomplete | canceled={len(canceled)} | Nimbus login required"); return 5
        shipments = nimbus_track.replay_shipments(p, req, now - timedelta(days=45), now, quiet=True)
        ctx.close()
    print(f"Nimbus: {len(shipments)} shipments and {len(orders)} orders (last 45 days)")
    results = cross_check(canceled, shipments, orders)
    prev = json.loads(STATE_F.read_text(encoding="utf-8")).get("alerted", {}) if STATE_F.exists() else {}
    flagged, alerted = diff_alerts(results, prev)
    crit = [f for f in flagged if SEVERITY[f["verdict"]] >= 3]
    info = [f for f in flagged if SEVERITY[f["verdict"]] == 1]
    matched = sum(1 for r in results if r["verdict"] != "NO_SHIPMENT")
    STATE_F.write_text(json.dumps({"last_run": now.isoformat(timespec="seconds"), "canceled": len(canceled), "nimbus_shipments": len(shipments), "nimbus_orders": len(orders), "matched": matched,
                                   "alerted": alerted, "flagged": flagged}, ensure_ascii=False, indent=1), encoding="utf-8")
    for f in crit:
        sh = f["shipments"][0] if f["shipments"] else {}
        print(f"CRITICAL{' [NEW]' if f['new'] else ''} {f['verdict']} | order {f['order_id']} | AWB {sh.get('awb')} Nimbus status '{sh.get('status')}' | cancelled on Amazon | {ACTION[f['verdict']]}")
    for f in info:
        print(f"info RTO_EXPECTED | order {f['order_id']} | Nimbus {[s['status'] for s in f['shipments']]} (buyer refused / undelivered: no action)")
    new_crit = sum(1 for f in crit if f["new"])
    print(f"RESULT: watchdog ok | canceled={len(canceled)} nimbus-shipments={len(shipments)} nimbus-orders={len(orders)} in-nimbus={matched} critical={len(crit)} (new={new_crit}) info={len(info)}")
    return 0


def selftest() -> int:
    fails = 0
    def check(name, ok):
        nonlocal fails
        fails += not ok
        print(("PASS " if ok else "FAIL ") + name)
    for st, want in [("cancelled", "OK_CANCELLED"), ("Canceled", "OK_CANCELLED"), ("booked", "CANCEL_NOW"), ("pending pickup", "CANCEL_NOW"), ("picked", "STOP_DISPATCHED"), ("in transit", "STOP_DISPATCHED"),
                     ("out for delivery", "STOP_DISPATCHED"), ("delivered", "DELIVERED_BUT_CANCELLED"), ("rto", "RTO_EXPECTED"), ("RTO In Transit", "RTO_EXPECTED"), ("exception", "RTO_EXPECTED"),
                     ("some new status", "STOP_DISPATCHED"), (None, "STOP_DISPATCHED")]:
        check(f"status {st!r} -> {want}", classify_status(st) == want)
    canc = [{"order_id": "A", "order_date": 1}, {"order_id": "B", "order_date": 2}, {"order_id": "C", "order_date": 3}, {"order_id": "D", "order_date": 4}, {"order_id": "E", "order_date": 5}]
    ships = [{"order_id": "A", "ship_status": "cancelled", "awb_number": "1"}, {"order_id": "B", "ship_status": "booked", "awb_number": "2"}, {"order_id": "C", "ship_status": "in transit", "awb_number": "3"},
             {"order_id": "D", "ship_status": "cancelled", "awb_number": "4"}, {"order_id": "D", "ship_status": "picked", "awb_number": "5"}, {"order_id": "Z", "ship_status": "delivered", "awb_number": "9"}]
    res = {r["order_id"]: r["verdict"] for r in cross_check(canc, ships)}
    check("cancelled in both -> OK", res["A"] == "OK_CANCELLED")
    check("Amazon cancelled, Nimbus booked -> CANCEL_NOW", res["B"] == "CANCEL_NOW")
    check("Amazon cancelled, Nimbus in transit -> STOP_DISPATCHED", res["C"] == "STOP_DISPATCHED")
    check("two shipments, one cancelled one picked -> the worst wins", res["D"] == "STOP_DISPATCHED")
    check("no Nimbus shipment at all -> NO_SHIPMENT (no alert)", res["E"] == "NO_SHIPMENT")
    check("a Nimbus shipment for an order Amazon did not cancel is ignored", "Z" not in res)
    ords = [{"order_id": "E", "fulfillment_status": "new", "order_date": 5}, {"order_id": "A", "fulfillment_status": "booked", "order_date": 1}, {"order_id": "F", "fulfillment_status": "cancelled", "order_date": 6}]
    res2 = {r["order_id"]: r["verdict"] for r in cross_check(canc + [{"order_id": "F", "order_date": 6}], ships, ords)}
    check("Nimbus ORDER still 'new' while Amazon cancelled (no shipment yet) -> CANCEL_NOW", res2["E"] == "CANCEL_NOW")
    check("a shipment record wins over a stale 'booked' order record (A stays OK_CANCELLED)", res2["A"] == "OK_CANCELLED")
    check("Nimbus order cancelled -> OK", res2["F"] == "OK_CANCELLED")
    flagged, alerted = diff_alerts(cross_check(canc, ships), {})
    check("first run: B, C, D flagged and all new", {f["order_id"] for f in flagged} == {"B", "C", "D"} and all(f["new"] for f in flagged))
    flagged2, alerted2 = diff_alerts(cross_check(canc, ships), alerted)
    check("same state again: still flagged, none new (no repeat notification)", len(flagged2) == 3 and not any(f["new"] for f in flagged2))
    ships2 = [s if s["order_id"] != "B" else {**s, "ship_status": "picked"} for s in ships]
    flagged3, _ = diff_alerts(cross_check(canc, ships2), alerted)
    check("a verdict that worsens (booked -> picked) is new again", {f["order_id"]: f["new"] for f in flagged3}["B"])
    ships3 = [s if s["order_id"] != "B" else {**s, "ship_status": "cancelled"} for s in ships]
    flagged4, alerted4 = diff_alerts(cross_check(canc, ships3), alerted)
    check("fixed in Nimbus (B cancelled) -> no longer flagged and dropped from the alerted map", "B" not in {f["order_id"] for f in flagged4} and "B" not in alerted4)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        sys.exit(selftest())
    try:
        sys.exit(run_live())
    except Exception as e:
        print("ERROR", repr(e)[:300]); sys.exit(4)
