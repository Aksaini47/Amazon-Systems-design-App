"""NimbusPost shipment helper for Mahika (tracking facts for the Amazon inbox agent).

  python agent/scripts/nimbus_track.py track <awb> [<awb> ...] [--order <amazon-order-id>] [--json]
      Public tracker https://ship.nimbuspost.com/trk/<AWB>: no login, no token. Returns state, courier,
      Amazon order id (cross-check), full scan history, notes on conflicting signals.
  python agent/scripts/nimbus_track.py jwt-status
      Looks for NIMBUSPOST_JWT in the root .env or data/mahika/sessions/nimbus_jwt.json and prints whether it
      is still valid (exp claim). Never prints the token.
  python agent/scripts/nimbus_track.py login
      SIR RUNS THIS HIMSELF. Signs in with NIMBUSPOST_LOGIN / NIMBUSPOST_PASSWORD from the root .env and saves the
      JWT to data/mahika/sessions/nimbus_jwt.json (gitignored). The assistant does not authenticate with passwords.
  python agent/scripts/nimbus_track.py ui-login [minutes]
      SIR RUNS THIS HIMSELF. Fills the Nimbus sign-in form from NIMBUSPOST_LOGIN / NIMBUSPOST_PASSWORD (root .env), then opens the
      Shipments tab, saves a JWT if the app keeps one, and leaves the window open. OTP/captcha -> stops typing, Sir finishes by hand.
  python agent/scripts/nimbus_track.py open-shipments [minutes]
      Uses the saved browser session only (no credentials typed): opens the Shipments tab; LOGIN_REQUIRED if the session expired.
  python agent/scripts/nimbus_track.py browser-login [minutes]
      Opens the Nimbus sign-in page in the visible Playwright Chromium profile and WAITS while Sir logs in by hand
      (nothing is typed by the script). Once logged in it reports the session and, if the app keeps a JWT in
      localStorage/sessionStorage, saves it to data/mahika/sessions/nimbus_jwt.json (prints key name + expiry only).

States: DELIVERED | OUT_FOR_DELIVERY | IN_TRANSIT | NOT_MOVING | RTO_IN_TRANSIT | RTO_RECEIVED | EXCEPTION | NOT_FOUND | UNKNOWN
"""
from __future__ import annotations

import base64
import io
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOKEN_FILE = ROOT / "data" / "mahika" / "sessions" / "nimbus_jwt.json"
IST = timezone(timedelta(hours=5, minutes=30))
UA = {"User-Agent": "Mozilla/5.0"}
TS = re.compile(r"^[A-Z][a-z]{2} \d{2}, \d{4} \d{2}:\d{2}$")
PRE_MOVE = re.compile(r"manifest uploaded|pickup scheduled|out for pickup|not ready for pickup|pending pickup|pickup (re)?scheduled", re.I)
MOVE = re.compile(r"picked up|in transit|bag|trip|facility|hub|vehicle|outscan|inscan|out for delivery|delivered|received|dispatched|scanned|arrived|departed", re.I)
RTO_RECEIVED = re.compile(r"return accepted|rto delivered|delivered to origin|rto received|returned to (origin|shipper|seller)", re.I)
VERIFIED = re.compile(r"code verified|otp verified|pod", re.I)
BAD_NEAR_DELIVERY = re.compile(r"refus|otp not shared|incorrect|undeliver|rto", re.I)


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.exists():
        for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", ln)
            if m and not ln.lstrip().startswith("#"):
                out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def fetch(awb: str, tries: int = 3) -> str:
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(f"https://ship.nimbuspost.com/trk/{awb}", headers=UA)
            return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "Sorry, the page you are looking for could not be found."
            last = e
        except Exception as e:  # network hiccup
            last = e
    raise RuntimeError(f"fetch failed for {awb}: {last}")


def lines_of(html: str) -> list[str]:
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    t = re.sub(r"<[^>]+>", "\n", t)
    return [ln.strip() for ln in t.splitlines() if ln.strip()]


def split_loc_remark(s: str) -> tuple[str, str]:
    """'Jewar_SJRoad_D (Uttar Pradesh) (Out for delivery)' -> ('Jewar_SJRoad_D (Uttar Pradesh)', 'Out for delivery')."""
    s = s.strip()
    if not s.endswith(")"):
        return s, ""
    depth = 0
    for i in range(len(s) - 1, -1, -1):
        if s[i] == ")":
            depth += 1
        elif s[i] == "(":
            depth -= 1
            if depth == 0:
                return s[:i].strip(), s[i + 1:-1].strip()
    return s, ""


def after(lines: list[str], label: str) -> str | None:
    for i, ln in enumerate(lines):
        if ln.rstrip(" :").upper() == label and i + 1 < len(lines):
            return lines[i + 1]
    return None


def parse(awb: str, html: str, order: str | None = None) -> dict:
    L = lines_of(html)
    res: dict = {"awb": awb, "state": "UNKNOWN", "courier": None, "order_id": None, "placed_on": None, "status_label": None,
                 "events": [], "latest": None, "delivered_at": None, "delivery_verified": None, "days_since_last_scan": None, "notes": []}
    if len(L) <= 2 and any("could not be found" in x for x in L):
        res["state"] = "NOT_FOUND"; return res
    try:
        i = L.index("Order Details")
        res["status_label"] = L[i + 1]
    except ValueError:
        pass
    res["placed_on"], res["courier"], res["order_id"] = after(L, "ORDER PLACED ON"), after(L, "COURIER"), after(L, "ORDER ID")
    try:
        start = L.index("Shipment Progress") + 1
    except ValueError:
        start = len(L)
    cur = None
    for ln in L[start:]:
        if TS.match(ln):
            cur = {"at": ln, "parts": []}; res["events"].append(cur)
        elif cur is not None:
            if re.match(r"^(Powered by|.*@.*\..*)", ln):
                break
            cur["parts"].append(ln)
    for ev in res["events"]:
        loc, remark = split_loc_remark(" ".join(ev.pop("parts")))
        ev["location"], ev["remark"] = loc, remark
    ev0 = res["events"][0] if res["events"] else None
    if ev0:
        res["latest"] = ev0
        last = datetime.strptime(ev0["at"], "%b %d, %Y %H:%M").replace(tzinfo=IST)
        res["days_since_last_scan"] = round((datetime.now(IST) - last).total_seconds() / 86400, 1)
    label = (res["status_label"] or "").lower()
    remarks = " | ".join(e["remark"] for e in res["events"])
    moved = any(MOVE.search(e["remark"]) and not PRE_MOVE.search(e["remark"]) for e in res["events"])
    if "rto" in label or any("rto" in e["remark"].lower() for e in res["events"][:3]):
        res["state"] = "RTO_RECEIVED" if ev0 and RTO_RECEIVED.search(ev0["remark"]) else "RTO_IN_TRANSIT"
    elif label.startswith("deliver"):
        res["state"] = "DELIVERED"; res["delivered_at"] = ev0["at"] if ev0 else None
        res["delivery_verified"] = bool(VERIFIED.search(remarks))
        dt = datetime.strptime(ev0["at"], "%b %d, %Y %H:%M") if ev0 else None
        for e in res["events"][1:]:
            et = datetime.strptime(e["at"], "%b %d, %Y %H:%M")
            if dt and (dt - et) <= timedelta(hours=6) and BAD_NEAR_DELIVERY.search(e["remark"]):
                res["notes"].append(f"conflicting scan {e['at']}: {e['remark']} (shortly before 'delivered')")
    elif "out for delivery" in label:
        res["state"] = "OUT_FOR_DELIVERY"
    elif any(w in label for w in ("ndr", "undeliver", "exception", "lost", "damag")):
        res["state"] = "EXCEPTION"
    elif not moved:
        res["state"] = "NOT_MOVING"
    else:
        res["state"] = "IN_TRANSIT"
    if res["state"] == "IN_TRANSIT" and (res["days_since_last_scan"] or 0) > 4:
        res["notes"].append(f"stalled: no scan for {res['days_since_last_scan']} days")
    if order and res["order_id"] and order != res["order_id"]:
        res["state"] = "ORDER_MISMATCH"; res["notes"].append(f"tracker order id {res['order_id']} != expected {order}")
    return res


def cmd_track(args: list[str]) -> int:
    as_json = "--json" in args
    order = None
    if "--order" in args:
        k = args.index("--order"); order = args[k + 1]; args = args[:k] + args[k + 2:]
    awbs = [a for a in args if not a.startswith("--")]
    if not awbs:
        print("usage: track <awb> [<awb> ...] [--order <amazon-order-id>] [--json]"); return 2
    results = [parse(a, fetch(a), order if len(awbs) == 1 else None) for a in awbs]
    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=1)); return 0
    for r in results:
        lt = r["latest"]
        print(f"{r['awb']} | {r['state']} | {r['courier']} | order {r['order_id']} | last: {lt['at'] + ' ' + lt['location'] + ' (' + lt['remark'] + ')' if lt else '-'}"
              + (f" | verified={r['delivery_verified']}" if r["state"] == "DELIVERED" else "") + (f" | NOTES: {'; '.join(r['notes'])}" if r["notes"] else ""))
    return 0


def jwt_exp(token: str) -> datetime | None:
    try:
        seg = token.split(".")[1]; seg += "=" * (-len(seg) % 4)
        exp = json.loads(base64.urlsafe_b64decode(seg)).get("exp")
        return datetime.fromtimestamp(exp, IST) if exp else None
    except Exception:
        return None


def load_token() -> tuple[str | None, str]:
    tok = read_env(ROOT / ".env").get("NIMBUSPOST_JWT")
    if tok:
        return tok, "root .env (NIMBUSPOST_JWT)"
    if TOKEN_FILE.exists():
        try:
            return json.loads(TOKEN_FILE.read_text(encoding="utf-8")).get("token"), "data/mahika/sessions/nimbus_jwt.json"
        except Exception:
            return None, "token file unreadable"
    return None, "none"


def cmd_jwt_status() -> int:
    tok, src = load_token()
    if not tok:
        print(f"NO_TOKEN (looked in: root .env NIMBUSPOST_JWT, {TOKEN_FILE.relative_to(ROOT)}). Run `login` yourself or save NIMBUSPOST_JWT in .env."); return 1
    exp = jwt_exp(tok)
    if exp is None:
        print(f"TOKEN_FOUND in {src} but no readable exp claim (not a standard JWT?)"); return 1
    left = exp - datetime.now(IST)
    print(f"JWT in {src}: " + (f"VALID until {exp:%Y-%m-%d %H:%M} IST ({left.days}d {left.seconds // 3600}h left)" if left.total_seconds() > 0 else f"EXPIRED at {exp:%Y-%m-%d %H:%M} IST"))
    return 0 if left.total_seconds() > 0 else 1


def cmd_login() -> int:
    env = read_env(ROOT / ".env"); email, pw = env.get("NIMBUSPOST_LOGIN"), env.get("NIMBUSPOST_PASSWORD")
    if not (email and pw):
        print("NIMBUSPOST_LOGIN / NIMBUSPOST_PASSWORD missing in root .env"); return 2
    req = urllib.request.Request("https://api.nimbuspost.com/v1/users/login", data=json.dumps({"email": email, "password": pw}).encode(),
                                 headers={"Content-Type": "application/json", **UA}, method="POST")
    try:
        body = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:200].replace(pw, "***")
        print(f"LOGIN_FAILED http {e.code}: {msg}"); return 1
    except Exception as e:
        print(f"LOGIN_FAILED {type(e).__name__}: {str(e)[:150]}"); return 1
    tok = body.get("data") if isinstance(body, dict) else None
    if not (isinstance(tok, str) and tok.count(".") == 2):
        print("LOGIN_FAILED: response has no JWT. Status/message:", str(body.get("message") if isinstance(body, dict) else body)[:150]); return 1
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps({"token": tok, "saved_at": datetime.now(IST).isoformat(timespec="seconds")}), encoding="utf-8")
    exp = jwt_exp(tok)
    print("LOGIN_OK, token saved to data/mahika/sessions/nimbus_jwt.json" + (f"; expires {exp:%Y-%m-%d %H:%M} IST" if exp else ""))
    return 0


JWT_RE = re.compile(r"^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$")
FIND_JWT_JS = """() => { const out = []; const walk = (v, where, d) => { if (d > 3 || v == null) return;
  if (typeof v === 'string') { if (/^[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}$/.test(v)) out.push({where, value: v}); return; }
  if (typeof v === 'object') for (const k of Object.keys(v).slice(0, 40)) walk(v[k], where + '.' + k, d + 1); };
  for (const st of [localStorage, sessionStorage]) for (let i = 0; i < st.length; i++) { const k = st.key(i); const raw = st.getItem(k);
    let v = raw; try { v = JSON.parse(raw); } catch (e) {} walk(v, (st === localStorage ? 'localStorage:' : 'sessionStorage:') + k, 0); }
  return out; }"""


def cmd_browser_login(minutes: int = 10) -> int:
    from playwright.sync_api import sync_playwright
    sys.path.insert(0, str(ROOT / "agent" / "src"))
    from mahika.playwright.session import CHROMIUM_PROFILE_DIR
    with sync_playwright() as pw:
        try:
            ctx = pw.chromium.launch_persistent_context(user_data_dir=str(CHROMIUM_PROFILE_DIR), headless=False, viewport={"width": 1400, "height": 950},
                                                         args=["--disable-blink-features=AutomationControlled"])
        except Exception as e:
            print("PROFILE_BUSY (another Playwright window holds the profile):", str(e)[:150]); return 3
        p = ctx.pages[0] if ctx.pages else ctx.new_page()
        p.goto("https://app.nimbuspost.com/signin", wait_until="domcontentloaded", timeout=60000)
        print(f"WAITING_FOR_LOGIN: Nimbus sign-in is open in the Playwright window - log in by hand (up to {minutes} min). Nothing is typed by this script.", flush=True)
        found, stable = None, 0
        for _ in range(minutes * 20):
            p.wait_for_timeout(3000)
            looks_logged = False
            for pg in ctx.pages:
                try:
                    url = pg.url
                    if "nimbuspost.com" not in url:
                        continue
                    cands = pg.evaluate(FIND_JWT_JS)
                    best = max((c for c in cands if jwt_exp(c["value"])), key=lambda c: jwt_exp(c["value"]), default=None)
                    if best:
                        found = best; break
                    if not re.search(r"sign-?in|login|signup|otp|verify|auth", url, re.I) and pg.evaluate(
                            "() => !document.querySelector('input[type=password]') && !/Enter mobile number|Enter password|Enter OTP|Continue/i.test(document.body.innerText.slice(0, 1500))"):
                        looks_logged = True
                except Exception:
                    pass
            stable = stable + 1 if looks_logged else 0
            if found or stable >= 2:
                break
        else:
            print("TIMEOUT: no login seen"); ctx.close(); return 1
        if not found:                              # logged in but no token yet: give the app a moment to write it
            p.wait_for_timeout(6000)
            for pg in ctx.pages:
                try:
                    cands = pg.evaluate(FIND_JWT_JS)
                    found = max((c for c in cands if jwt_exp(c["value"])), key=lambda c: jwt_exp(c["value"]), default=None)
                    if found:
                        break
                except Exception:
                    pass
        urls = [pg.url.split("?")[0] for pg in ctx.pages]
        if found:
            exp = jwt_exp(found["value"])
            TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_FILE.write_text(json.dumps({"token": found["value"], "saved_at": datetime.now(IST).isoformat(timespec="seconds"), "source": found["where"].split(":")[0]}), encoding="utf-8")
            print(f"LOGGED_IN: JWT found at {found['where']}, expires {exp:%Y-%m-%d %H:%M} IST, saved to data/mahika/sessions/nimbus_jwt.json | pages: {urls}")
        else:
            print(f"LOGGED_IN: session active in the browser profile, no JWT visible in local/session storage (cookie-based session). pages: {urls}")
        ctx.close(); return 0


APP = "https://ship.nimbuspost.com"          # the logged-in app lives here (login starts at app.nimbuspost.com/signin)
SIGNIN = "https://app.nimbuspost.com/signin"
SHIPMENT_URLS = ("/shipping/all", "/cargo_shipping/all", "/document_shipping/all")      # B2C, B2B, Document shipments (sidebar "Shipment")


def _launch(pw):
    sys.path.insert(0, str(ROOT / "agent" / "src"))
    from mahika.playwright.session import CHROMIUM_PROFILE_DIR
    return pw.chromium.launch_persistent_context(user_data_dir=str(CHROMIUM_PROFILE_DIR), headless=False, viewport={"width": 1400, "height": 950},
                                                  args=["--disable-blink-features=AutomationControlled"])


def _on_signin(p) -> bool:
    try:
        return bool(re.search(r"sign-?in|login|signup", p.url, re.I)) or p.locator("input[type=password]").count() > 0 \
            or p.get_by_placeholder(re.compile("mobile number|email", re.I)).count() > 0
    except Exception:
        return True


def _save_jwt(ctx) -> str:
    found = None
    for pg in ctx.pages:
        try:
            cands = pg.evaluate(FIND_JWT_JS)
            best = max((c for c in cands if jwt_exp(c["value"])), key=lambda c: jwt_exp(c["value"]), default=None)
            if best:
                found = best; break
        except Exception:
            pass
    if not found:
        return "no JWT in local/session storage (cookie-based session)"
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps({"token": found["value"], "saved_at": datetime.now(IST).isoformat(timespec="seconds"), "source": found["where"].split(":")[0]}), encoding="utf-8")
    return f"JWT saved from {found['where']}, expires {jwt_exp(found['value']):%Y-%m-%d %H:%M} IST"


def open_shipments(p) -> str:
    """Open the Shipments tab of the logged-in Nimbus app. Returns a short description of where we ended up."""
    try:                                         # sidebar link: Shipment > B2C
        link = p.locator(f"a[href='{SHIPMENT_URLS[0]}']")
        if link.count():
            link.first.click(timeout=8000, force=True); p.wait_for_timeout(6000)
            if not _on_signin(p) and "/shipping/all" in p.url:
                return f"opened via sidebar link: {p.url.split('?')[0]}"
    except Exception:
        pass
    for path in SHIPMENT_URLS:
        try:
            p.goto(APP + path, wait_until="domcontentloaded", timeout=40000); p.wait_for_timeout(6000)
            if not _on_signin(p) and not re.search(r"404 Page Not Found", p.evaluate("() => document.body.innerText")):
                return f"opened via url: {p.url.split('?')[0]}"
        except Exception:
            pass
    return f"Shipments tab not found automatically (page: {p.url.split('?')[0]})"


def _keep_open(ctx, minutes: int) -> None:
    print(f"Window stays open for up to {minutes} min (close it to finish).", flush=True)
    for _ in range(minutes * 20):
        try:
            if not ctx.pages:
                break
            ctx.pages[0].wait_for_timeout(3000)
        except Exception:
            break


def cmd_open_shipments(minutes: int = 5) -> int:
    """Uses the saved browser session only. No credentials are typed."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        try:
            ctx = _launch(pw)
        except Exception as e:
            print("PROFILE_BUSY:", str(e)[:150]); return 3
        p = ctx.pages[0] if ctx.pages else ctx.new_page()
        p.goto(APP + "/dash", wait_until="domcontentloaded", timeout=60000); p.wait_for_timeout(8000)
        if _on_signin(p):
            print("LOGIN_REQUIRED: Nimbus session missing/expired. Run `ui-login` (Sir) or `browser-login`."); ctx.close(); return 2
        print("NAV:", [t for t in p.evaluate("() => [...document.querySelectorAll('a,button,[role=menuitem]')].map(e => (e.innerText||'').trim().replace(/\\s+/g,' ')).filter(t => t && t.length < 30)")][:40])
        print("SHIPMENTS:", open_shipments(p)); print("JWT:", _save_jwt(ctx))
        print("PAGE:", re.sub(r"\s+", " ", p.evaluate("() => document.body.innerText"))[:300])
        _keep_open(ctx, minutes); ctx.close(); return 0


def cmd_ui_login(minutes: int = 5) -> int:
    """SIR RUNS THIS. Types NIMBUSPOST_LOGIN / NIMBUSPOST_PASSWORD (root .env) into the Nimbus sign-in form, then opens Shipments.
    If Nimbus asks for an OTP or a captcha, the script stops typing and waits for Sir to finish by hand."""
    from playwright.sync_api import sync_playwright
    env = read_env(ROOT / ".env"); email, pw_ = env.get("NIMBUSPOST_LOGIN"), env.get("NIMBUSPOST_PASSWORD")
    if not (email and pw_):
        print("NIMBUSPOST_LOGIN / NIMBUSPOST_PASSWORD missing in root .env"); return 2
    with sync_playwright() as pw:
        try:
            ctx = _launch(pw)
        except Exception as e:
            print("PROFILE_BUSY:", str(e)[:150]); return 3
        p = ctx.pages[0] if ctx.pages else ctx.new_page()
        p.goto(SIGNIN, wait_until="domcontentloaded", timeout=60000); p.wait_for_timeout(6000)
        if _on_signin(p):
            try:
                p.get_by_placeholder(re.compile("mobile number|email", re.I)).first.fill(email, timeout=10000)
                p.get_by_role("button", name=re.compile(r"^\s*Continue\s*$", re.I)).first.click(timeout=8000)
                p.wait_for_selector("input[type=password]", timeout=20000)
                p.locator("input[type=password]").first.fill(pw_)
                btn = p.get_by_role("button", name=re.compile(r"^\s*(Log ?in|Sign ?in|Continue|Submit|Verify)\s*$", re.I))
                (btn.first.click(timeout=8000) if btn.count() else p.keyboard.press("Enter"))
            except Exception as e:
                print("AUTOFILL_STOPPED (OTP/captcha or a different form?):", str(e)[:120].replace(pw_, "***"), "- finish the login by hand in the window.", flush=True)
            for _ in range(minutes * 20):
                p.wait_for_timeout(3000)
                if not _on_signin(p):
                    break
            else:
                print("TIMEOUT: still on the sign-in page"); ctx.close(); return 1
        p.wait_for_timeout(5000)
        print("LOGGED_IN:", p.url.split("?")[0]); print("SHIPMENTS:", open_shipments(p)); print("JWT:", _save_jwt(ctx))
        _keep_open(ctx, minutes); ctx.close(); return 0


def cmd_export_shipments(start: str, end: str) -> int:
    """Replay the Nimbus app's own POST /mapi/v1/shipment/list (month by month, 500 per page) with the saved login session.
    Saves data/mahika/nimbus/shipments_<start>_<end>.json (order_id, awb, created, pickup, delivered, status, fees, rto...). No credentials typed."""
    from playwright.sync_api import sync_playwright
    d0, d1 = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=IST), datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=IST)
    cap = {}
    with sync_playwright() as pw:
        try:
            ctx = _launch(pw)
        except Exception as e:
            print("PROFILE_BUSY:", str(e)[:150]); return 3
        p = ctx.pages[0] if ctx.pages else ctx.new_page()
        p.on("request", lambda r: cap.setdefault("req", (r.url, r.post_data, dict(r.headers))) if "mapi/v1/shipment/list" in r.url else None)
        p.goto(APP + "/shipping/all", wait_until="domcontentloaded", timeout=60000); p.wait_for_timeout(10000)
        if _on_signin(p) or "req" not in cap:
            print("LOGIN_REQUIRED (or list request not seen)"); ctx.close(); return 2
        url, body, hdr = cap["req"]
        for k in ("cookie", "host", "content-length", "accept-encoding", "connection"):
            hdr.pop(k, None)
        js = """async ([u, body, h]) => { const r = await fetch(u, {method:'POST', credentials:'include', headers:h, body}); return {s: r.status, j: await r.json()}; }"""
        out, cur = [], d0
        while cur < d1:
            nxt = min((cur.replace(day=28) + timedelta(days=4)).replace(day=1), d1 + timedelta(days=1))
            page, got = 1, 0
            while True:
                u = re.sub(r"start_date=\d+", f"start_date={int(cur.timestamp())}", url); u = re.sub(r"end_date=\d+", f"end_date={int(nxt.timestamp()) - 1}", u)
                u = re.sub(r"limit=\d+", "limit=500", u); u = re.sub(r"page=\d+", f"page={page}", u)
                b = json.loads(body); b["page"], b["limit"] = str(page), "500"
                res = p.evaluate(js, [u, json.dumps(b), hdr])
                recs = ((res.get("j") or {}).get("data") or {}).get("records") or []
                out += recs; got += len(recs)
                if len(recs) < 500 or res.get("s") != 200:
                    break
                page += 1
            print(f"{cur:%Y-%m}: {got}", flush=True)
            cur = nxt
        ctx.close()
    dest = ROOT / "data" / "mahika" / "nimbus"; dest.mkdir(parents=True, exist_ok=True)
    seen, uniq = set(), []
    for r in out:
        if r.get("id") not in seen:
            seen.add(r.get("id")); uniq.append(r)
    f = dest / f"shipments_{start}_{end}.json"; f.write_text(json.dumps(uniq, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print(f"saved {len(uniq)} shipments -> {f.relative_to(ROOT)} | status: {dict(Counter(r.get('ship_status') for r in uniq))}")
    return 0


def main() -> int:
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); return 0
    if a[0] == "export-shipments":
        return cmd_export_shipments(a[1], a[2])
    if a[0] == "open-shipments":
        return cmd_open_shipments(int(a[1]) if len(a) > 1 else 5)
    if a[0] == "ui-login":
        return cmd_ui_login(int(a[1]) if len(a) > 1 else 5)
    if a[0] == "browser-login":
        return cmd_browser_login(int(a[1]) if len(a) > 1 else 10)
    if a[0] == "track":
        return cmd_track(a[1:])
    if a[0] == "jwt-status":
        return cmd_jwt_status()
    if a[0] == "login":
        return cmd_login()
    print("unknown command:", a[0]); return 2


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)   # CLI only (importers keep their own stdout)
    sys.exit(main())
