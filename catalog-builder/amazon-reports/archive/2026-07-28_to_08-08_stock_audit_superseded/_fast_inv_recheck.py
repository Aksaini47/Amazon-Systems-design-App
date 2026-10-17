"""Fast inventory recheck — URL search + pageSize=250. Budget ~210s."""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.parse
from pathlib import Path

AGENT_SRC = Path(r"c:\Projects\Amazon Systems Design\agent\src")
sys.path.insert(0, str(AGENT_SRC))
os.chdir(r"c:\Projects\Amazon Systems Design\agent")

from playwright.sync_api import sync_playwright
from mahika.playwright.account_switcher import complete_account_switcher, is_account_switcher_page
from mahika.playwright.seller_login import (
    _submit_otp_code,
    _trust_device,
    ensure_seller_session,
    load_seller_credentials,
)
from mahika.playwright.amazon_signin_flow import is_otp_entry_screen
from mahika.playwright.session import (
    CHROMIUM_PROFILE_DIR,
    load_cookies,
    save_cookies,
    session_is_authenticated,
)
from mahika.playwright.selectors import SELECTORS

ROOT = Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports")
MANIFEST = ROOT / "PHONE_ACCESSORY_oos_qty0_manifest.csv"
OUT_MD = ROOT / "inventory_check_qty0_restock_2026-07-31.md"
OUT_CSV = ROOT / "inventory_check_qty0_restock_2026-07-31.csv"
OTP = (os.environ.get("MAHIKA_FIXED_OTP") or "699216").strip()
DEADLINE = time.monotonic() + 210  # ~3.5 min hard stop


def left():
    return max(0, DEADLINE - time.monotonic())


def inv_url(sku: str) -> str:
    q = urllib.parse.urlencode(
        {
            "fulfilledBy": "all",
            "page": "1",
            "pageSize": "250",
            "searchField": "all",
            "searchTerm": sku,
            "sort": "available_desc",
            "status": "all",
            "ref_": "xx_invmgr_dnav_xx",
        }
    )
    return f"https://sellercentral.amazon.in/myinventory/inventory?{q}"


def goto(page, url, timeout=25000):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    except Exception as e:
        print("goto_err", str(e)[:120])


def try_otp(page) -> bool:
    if not is_otp_entry_screen(page):
        return False
    print("MFA open — submitting OTP now")
    _trust_device(page)
    try:
        return bool(_submit_otp_code(page, OTP))
    except Exception as e:
        print("otp_submit_err", e)
        return False


def auth(page) -> str:
    if try_otp(page):
        if session_is_authenticated(page):
            save_cookies(page.context)
            return "ok"
    if is_account_switcher_page(page):
        complete_account_switcher(page)
        if session_is_authenticated(page):
            save_cookies(page.context)
            return "ok"
    if session_is_authenticated(page):
        return "ok"
    # fresh login — OTP may already be burned
    class W:
        def __init__(self):
            self._otp_prompt_sent = True
            self._used = set()
        def mark_otp_waiting(self, **k):
            self._used.clear()
        def _write_live_status(self, line):
            print("otp:", line)
        def wait_for_otp(self, **k):
            print("FIXED_OTP", OTP[:2] + "****")
            return OTP

    import mahika.playwright.seller_login as sl
    sl.OTP_TELEGRAM_ATTEMPTS = 1
    sl.OTP_TELEGRAM_WAIT_S = 15
    sl.CALL_711_MAX_ROUNDS = 0
    bud = min(90, int(left()) - 30)
    if bud < 25:
        return "no_time_for_login"
    print("LOGIN budget", bud)
    creds = load_seller_credentials()
    try:
        ok = ensure_seller_session(page, creds, W(), timeout_s=bud)
    except Exception as e:
        return f"login_error:{e}"
    if ok and session_is_authenticated(page):
        save_cookies(page.context)
        return "ok"
    if is_otp_entry_screen(page):
        return "OTP_EXPIRED_NEED_FRESH"
    return "login_failed"


def parse(page, sku: str) -> dict:
    return page.evaluate(
        """(sku) => {
          const norm = s => (s||'').replace(/\\s+/g,' ').trim();
          const skuL = sku.toLowerCase();
          const body = norm(document.body ? document.body.innerText : '');
          const head = body.slice(0, 2500);
          if (/sign in|two-step|enter (the )?otp|authentication required/i.test(head)
              && !/manage.*(inventory|listings)/i.test(head)) {
            return {found:false, live_qty:null, status:'', snip:'auth_wall', auth:true};
          }
          // Prefer table rows
          const rows = Array.from(document.querySelectorAll(
            'tr,[role=row],.mt-row,kat-table-row,[data-sku],tbody tr'));
          let best = null;
          for (const row of rows) {
            const txt = norm(row.innerText || row.textContent || '');
            if (!txt.toLowerCase().includes(skuL) || txt.length < 6) continue;
            let qty = null;
            for (const inp of row.querySelectorAll('input')) {
              const meta = ((inp.name||'')+' '+(inp.id||'')+' '+
                (inp.getAttribute('aria-label')||'')+' '+(inp.getAttribute('placeholder')||'')).toLowerCase();
              const val = (inp.value||'').trim();
              if ((/qty|quantity|available/.test(meta) || inp.type==='number') && /^\\d+$/.test(val)) {
                qty = parseInt(val,10); break;
              }
            }
            // shadow/kat-input
            for (const kat of row.querySelectorAll('kat-input')) {
              try {
                const v = kat.value || (kat.shadowRoot && kat.shadowRoot.querySelector('input')?.value) || '';
                if (/^\\d+$/.test(String(v).trim())) { qty = parseInt(v,10); break; }
              } catch(e) {}
            }
            if (qty === null) {
              const m = txt.match(/\\b(?:Quantity|Qty|Available)\\s*[:\\s]?\\s*(\\d+)\\b/i);
              if (m) qty = parseInt(m[1],10);
            }
            let status = '';
            for (const lab of ['Active','Inactive','Incomplete','Suppressed','Blocked','Closed']) {
              if (new RegExp('\\\\b'+lab+'\\\\b','i').test(txt)) { status = lab; break; }
            }
            best = {found:true, live_qty:qty, status, snip: txt.slice(0,200)};
            break;
          }
          if (best) return best;
          if (/0 results|no matching|no results|we couldn.?t find|didn.?t find any/i.test(head)) {
            return {found:false, live_qty:null, status:'', snip:'no_results'};
          }
          // ASIN-ish fallback in body
          if (body.toLowerCase().includes(skuL)) {
            const m = body.match(new RegExp(sku.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&') + '[\\\\s\\\\S]{0,400}?(?:Quantity|Qty)[:\\\\s]*(\\\\d+)', 'i'));
            let qty = m ? parseInt(m[1],10) : null;
            let status = '';
            for (const lab of ['Active','Inactive','Incomplete']) {
              if (body.includes(lab)) { status = lab; break; }
            }
            return {found:true, live_qty:qty, status, snip: body.slice(0,180)};
          }
          return {found:false, live_qty:null, status:'', snip: head.slice(0,160)};
        }""",
        sku,
    )


def verdict(expected, live_qty, status, found):
    if not found:
        return "missing"
    st = (status or "").lower()
    if live_qty is None:
        return "inactive_unknown_qty" if "inactive" in st else "found_unknown_qty"
    if int(live_qty) == 0:
        return "still_0"
    if int(live_qty) >= int(expected):
        return "ok_qty_but_inactive" if "inactive" in st else "ok"
    return "qty_below_expected"


def write_out(results, note=""):
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["sku","asin","model","expected_qty","live_qty","status","verdict","notes"],
        )
        w.writeheader()
        w.writerows(results)

    def n(v):
        return sum(1 for r in results if r["verdict"] == v)

    ok, ok_i, z, miss = n("ok"), n("ok_qty_but_inactive"), n("still_0"), n("missing")
    below = n("qty_below_expected")
    unk = n("found_unknown_qty") + n("inactive_unknown_qty")
    lines = [
        "# Inventory check — qty0 restock batch 107438020664",
        "",
        f"**When:** {time.strftime('%Y-%m-%d %H:%M')} IST",
        "**Account:** Badeja Enterprises → India",
        "**Method:** headless Playwright URL search (pageSize=250)",
        f"**Manifest:** `{MANIFEST.name}` ({len(results)} SKUs checked)",
        f"**View 250 set:** True (URL pageSize=250)",
        f"**Note:** {note}" if note else "",
        "",
        "## Summary",
        "",
        "| Bucket | Count |",
        "|---|---|",
        f"| OK (qty ≥ expected) | {ok} |",
        f"| OK qty but Inactive | {ok_i} |",
        f"| Still qty 0 | {z} |",
        f"| Qty below expected | {below} |",
        f"| Missing | {miss} |",
        f"| Found but qty unknown | {unk} |",
        f"| **Total** | **{len(results)}** |",
        "",
        "## Per SKU",
        "",
        "| SKU | Expected | Live | Status | Verdict |",
        "|---|---:|---:|---|---|",
    ]
    for r in results:
        lq = "" if r["live_qty"] is None else r["live_qty"]
        lines.append(
            f"| `{r['sku']}` | {r['expected_qty']} | {lq} | {r['status'] or '—'} | {r['verdict']} |"
        )
    lines += ["", f"CSV: `{OUT_CSV.name}`", "", "Source batch: **107438020664**."]
    OUT_MD.write_text("\n".join([x for x in lines if x is not None]) + "\n", encoding="utf-8")
    print(json.dumps({"ok": ok, "ok_inactive": ok_i, "still_0": z, "missing": miss, "below": below, "unknown": unk, "left_s": int(left())}))


def main():
    rows = list(csv.DictReader(MANIFEST.open(encoding="utf-8-sig")))
    results = []
    note = ""
    print("START left", int(left()), "skus", len(rows))
    with sync_playwright() as pw:
        CHROMIUM_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(CHROMIUM_PROFILE_DIR),
            headless=True,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        load_cookies(ctx)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(20000)

        goto(page, "https://sellercentral.amazon.in/home")
        page.wait_for_timeout(800)
        a = auth(page)
        print("AUTH", a, "left", int(left()))
        if a == "OTP_EXPIRED_NEED_FRESH":
            note = "OTP 699216 expired/rejected — Sir needs NEW OTP"
            # write partial blocker
            for r in rows:
                results.append({
                    "sku": r["sku"], "asin": r["asin"], "model": r["model"],
                    "expected_qty": int(r["set_qty"] or 1), "live_qty": None,
                    "status": "", "verdict": "blocked_login", "notes": note,
                })
            write_out(results, note)
            try:
                ctx.close()
            except Exception:
                pass
            return 2
        if a != "ok":
            note = f"login blocked: {a}"
            for r in rows:
                results.append({
                    "sku": r["sku"], "asin": r["asin"], "model": r["model"],
                    "expected_qty": int(r["set_qty"] or 1), "live_qty": None,
                    "status": "", "verdict": "blocked_login", "notes": note,
                })
            write_out(results, note)
            try:
                ctx.close()
            except Exception:
                pass
            return 2

        # probe first SKU for auth/wall
        first = rows[0]["sku"].strip()
        goto(page, inv_url(first))
        page.wait_for_timeout(2000)
        if is_account_switcher_page(page):
            complete_account_switcher(page)
            goto(page, inv_url(first))
            page.wait_for_timeout(1500)
        if try_otp(page):
            goto(page, inv_url(first))
            page.wait_for_timeout(1500)

        print("probe_url", (page.url or "")[:160])
        probe = parse(page, first)
        print("probe", probe)
        if probe.get("auth"):
            note = "auth wall on inventory — OTP may be needed again"
            # try one more auth
            a2 = auth(page)
            print("reauth", a2)
            if a2 != "ok":
                for r in rows:
                    results.append({
                        "sku": r["sku"], "asin": r["asin"], "model": r["model"],
                        "expected_qty": int(r["set_qty"] or 1), "live_qty": None,
                        "status": "", "verdict": "blocked_login", "notes": note,
                    })
                write_out(results, note)
                try:
                    save_cookies(ctx)
                except Exception:
                    pass
                ctx.close()
                return 2

        for i, r in enumerate(rows, 1):
            if left() < 15:
                note = f"time_budget_stop after {i-1}/21"
                print(note)
                for rr in rows[i-1:]:
                    results.append({
                        "sku": rr["sku"], "asin": rr["asin"], "model": rr["model"],
                        "expected_qty": int(rr["set_qty"] or 1), "live_qty": None,
                        "status": "", "verdict": "not_checked_timeout", "notes": note,
                    })
                break
            sku = r["sku"].strip()
            exp = int(r["set_qty"] or 1)
            print(f"[{i}/21] {sku} left={int(left())}")
            try:
                goto(page, inv_url(sku), timeout=18000)
                page.wait_for_timeout(1400)
                p = parse(page, sku)
            except Exception as e:
                p = {"found": False, "live_qty": None, "status": "", "snip": str(e)[:120]}
            ver = verdict(exp, p.get("live_qty"), p.get("status") or "", bool(p.get("found")))
            results.append({
                "sku": sku, "asin": r["asin"], "model": r["model"],
                "expected_qty": exp, "live_qty": p.get("live_qty"),
                "status": p.get("status") or "", "verdict": ver,
                "notes": (p.get("snip") or "")[:160].replace("\n", " "),
            })
            print(" ", ver, "qty=", p.get("live_qty"), "st=", p.get("status"))

        try:
            save_cookies(ctx)
        except Exception:
            pass
        ctx.close()

    write_out(results, note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())