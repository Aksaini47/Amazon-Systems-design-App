"""Headless inventory check — 21 restock SKUs. Login budget max 120s."""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from playwright.sync_api import sync_playwright

from mahika.config import settings
from mahika.playwright.account_switcher import (
    complete_account_switcher,
    is_account_switcher_page,
)
from mahika.playwright.seller_login import ensure_seller_session, load_seller_credentials
from mahika.playwright.session import (
    CHROMIUM_PROFILE_DIR,
    load_cookies,
    save_cookies,
    session_is_authenticated,
)

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "PHONE_ACCESSORY_oos_qty0_manifest.csv"
OUT_MD = ROOT / "inventory_check_qty0_restock_2026-07-31.md"
OUT_CSV = ROOT / "inventory_check_qty0_restock_2026-07-31.csv"
INVENTORY_URL = "https://sellercentral.amazon.in/inventory?ref_=xx_invmgr_dnav_xx"
HOME_INDIA = (
    "https://sellercentral.amazon.in/home?"
    "mons_sel_dir_paid=amzn1.pa.d.AB5ZXZYCP3XOLA6T5BVNPV2EXP6A"
)
LOGIN_BUDGET_S = 120
# Sir-supplied OTP (chat / env) — skip Telegram poll when set
FIXED_OTP = (os.environ.get("MAHIKA_FIXED_OTP") or "").strip()
OTP_FILE = (
    Path(__file__).resolve().parents[2]
    / "agent"
    / "storage"
    / "sessions"
    / "cursor_otp.txt"
)


def _goto(page, url: str) -> None:
    for _ in range(3):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            return
        except Exception as exc:
            if "interrupted" not in str(exc).lower():
                raise
            page.wait_for_timeout(1500)


class _FixedOtpWatcher:
    """Immediate OTP from Sir (chat/env/file) — no Telegram hang."""

    def __init__(self, code: str) -> None:
        self._code = code
        self._otp_prompt_sent = True
        self._used: set[str] = set()

    def mark_otp_waiting(self, *, total_wait_s: float = 600.0) -> None:
        self._used.clear()

    def _write_live_status(self, line: str) -> None:
        print(f"otp_status: {line}")

    def wait_for_otp(self, **_kwargs) -> str | None:
        print(f"FIXED_OTP submit: {self._code[:2]}****")
        return self._code


def _otp():
    code = FIXED_OTP
    if not code and OTP_FILE.is_file():
        code = OTP_FILE.read_text(encoding="utf-8").strip()
    if code and len(code) == 6 and code.isdigit():
        src = "env" if FIXED_OTP else "cursor_otp.txt"
        print(f"Using fixed OTP from {src}")
        return _FixedOtpWatcher(code)
    if not settings.telegram_configured:
        return None
    from mahika.services.otp_watcher import TelegramOtpWatcher

    return TelegramOtpWatcher()


def _auth_or_stop(page) -> str:
    if session_is_authenticated(page):
        return "ok"
    if is_account_switcher_page(page):
        complete_account_switcher(page)
        if session_is_authenticated(page):
            return "ok"
    print(f"LOGIN needed. Budget={LOGIN_BUDGET_S}s (Telegram OTP once, no Call-711 hang).")
    import mahika.playwright.seller_login as sl
    sl.OTP_TELEGRAM_ATTEMPTS = 1
    sl.OTP_TELEGRAM_WAIT_S = 100
    sl.CALL_711_MAX_ROUNDS = 0
    sl.CALL_711_POST_SUBMIT_WAIT_S = 5
    sl.CALL_711_AFTER_RESUBMIT_WAIT_S = 5
    creds = load_seller_credentials()
    watcher = _otp()
    t0 = time.monotonic()
    try:
        ok = ensure_seller_session(page, creds, watcher, timeout_s=LOGIN_BUDGET_S)
    except Exception as exc:
        return f"login_error: {exc}"
    elapsed = time.monotonic() - t0
    if ok and session_is_authenticated(page):
        save_cookies(page.context)
        print(f"LOGIN ok in {elapsed:.0f}s")
        return "ok"
    return f"login_blocked_after_{elapsed:.0f}s (budget {LOGIN_BUDGET_S}s)"


def _set_view_250(page) -> bool:
    info = page.evaluate(
        """() => {
      const selects = Array.from(document.querySelectorAll('select'));
      for (const s of selects) {
        const opts = Array.from(s.options || []);
        const hit = opts.find(o => String(o.value).trim()==='250'
          || String(o.textContent||'').trim()==='250');
        if (hit) {
          s.value = hit.value;
          s.dispatchEvent(new Event('change', {bubbles:true}));
          return {ok:true, via:'select'};
        }
      }
      const nodes = Array.from(document.querySelectorAll(
        'button,a,[role=option],[role=menuitem],span,div,kat-option'));
      for (const el of nodes) {
        const t = (el.innerText||el.textContent||'').trim();
        if (t === '250') { el.click(); return {ok:true, via:'click'}; }
      }
      return {ok:false};
    }"""
    )
    print("view250:", info)
    if info.get("ok"):
        page.wait_for_timeout(2000)
        return True
    for sel in ("select#pageSize", "select[name='pageSize']", "#myi-table-results-per-page"):
        loc = page.locator(sel)
        if loc.count() == 0:
            continue
        try:
            loc.first.select_option(label="250")
            page.wait_for_timeout(2000)
            return True
        except Exception:
            try:
                loc.first.select_option(value="250")
                page.wait_for_timeout(2000)
                return True
            except Exception:
                pass
    return False


def _search(page, sku: str) -> None:
    box = None
    for sel in (
        "input#search-text-input",
        "#myi-search-text-input",
        "input[placeholder*='Search' i]",
        "input[aria-label*='Search' i]",
        "input[type='search']",
    ):
        loc = page.locator(sel)
        if loc.count() and loc.first.is_visible():
            box = loc.first
            break
    if box is None:
        box = page.locator("input[type='text']").first
    box.click(timeout=8000)
    box.fill(sku)
    box.press("Enter")
    page.wait_for_timeout(2200)


def _parse(page, sku: str) -> dict:
    return page.evaluate(
        """(sku) => {
          const norm = s => (s||'').replace(/\\s+/g,' ').trim();
          const skuL = sku.toLowerCase();
          const rows = Array.from(document.querySelectorAll(
            'tr,[role=row],.mt-row,kat-table-row,[data-sku]'));
          for (const row of rows) {
            const txt = norm(row.innerText || row.textContent || '');
            if (!txt.toLowerCase().includes(skuL) || txt.length < 8) continue;
            let qty = null;
            for (const inp of row.querySelectorAll('input')) {
              const meta = ((inp.name||'')+' '+(inp.id||'')+' '+
                (inp.getAttribute('aria-label')||'')).toLowerCase();
              const val = (inp.value||'').trim();
              if (/qty|quantity|available/.test(meta) && /^\\d+$/.test(val)) {
                qty = parseInt(val,10); break;
              }
            }
            if (qty === null) {
              const m = txt.match(/Quantity\\s*[:\\s]\\s*(\\d+)/i)
                || txt.match(/Qty\\s*[:\\s]\\s*(\\d+)/i);
              if (m) qty = parseInt(m[1],10);
            }
            let status = '';
            for (const lab of ['Active','Inactive','Incomplete','Suppressed','Blocked','Closed']) {
              if (new RegExp('\\\\b'+lab+'\\\\b','i').test(txt)) { status = lab; break; }
            }
            return {found:true, live_qty:qty, status, snip: txt.slice(0,180)};
          }
          const body = norm(document.body ? document.body.innerText : '');
          if (!body.toLowerCase().includes(skuL) ||
              /0 results|no matching|no results|we couldn/i.test(body.slice(0,2000))) {
            return {found:false, live_qty:null, status:'', snip:'missing'};
          }
          return {found:true, live_qty:null, status:'', snip: body.slice(0,180)};
        }""",
        sku,
    )


def _verdict(expected, live_qty, status, found):
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


def _write_blocker(reason: str) -> None:
    OUT_MD.write_text(
        "\n".join(
            [
                "# Inventory check — qty0 restock batch 107438020664",
                "",
                f"**When:** {time.strftime('%Y-%m-%d %H:%M')} IST",
                "**Account:** Badeja Enterprises → India (attempted)",
                f"**Status:** BLOCKED — {reason}",
                "",
                "Headless login needed OTP; stopped after budget (no hang).",
                "Re-run after Telegram OTP / `seller-login`.",
                "",
                "Manifest: PHONE_ACCESSORY_oos_qty0_manifest.csv (21 SKUs) — not verified live.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "sku",
                "asin",
                "model",
                "expected_qty",
                "live_qty",
                "status",
                "verdict",
                "notes",
            ],
        )
        w.writeheader()
        for r in csv.DictReader(MANIFEST.open(encoding="utf-8-sig")):
            w.writerow(
                {
                    "sku": r["sku"],
                    "asin": r["asin"],
                    "model": r["model"],
                    "expected_qty": r["set_qty"],
                    "live_qty": "",
                    "status": "",
                    "verdict": "blocked_login",
                    "notes": reason,
                }
            )
    print("WROTE blocker", OUT_MD)


def main() -> int:
    rows = list(csv.DictReader(MANIFEST.open(encoding="utf-8-sig")))
    print(f"SKUs={len(rows)}")
    results = []
    v250 = False
    with sync_playwright() as pw:
        CHROMIUM_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(CHROMIUM_PROFILE_DIR),
            headless=True,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        load_cookies(context)
        page = context.pages[0] if context.pages else context.new_page()

        _goto(page, HOME_INDIA)
        page.wait_for_timeout(1500)
        if is_account_switcher_page(page):
            complete_account_switcher(page)

        auth = _auth_or_stop(page)
        if auth != "ok":
            print("BLOCKER:", auth)
            _write_blocker(auth)
            context.close()
            return 2

        _goto(page, INVENTORY_URL)
        page.wait_for_timeout(2500)
        if is_account_switcher_page(page):
            complete_account_switcher(page)
            _goto(page, INVENTORY_URL)
            page.wait_for_timeout(2000)
        if "signin" in (page.url or "").lower():
            auth = _auth_or_stop(page)
            if auth != "ok":
                _write_blocker(auth)
                context.close()
                return 2
            _goto(page, INVENTORY_URL)
            page.wait_for_timeout(2500)

        print("inv_url:", (page.url or "")[:140])
        v250 = _set_view_250(page)
        print("view250_ok:", v250)

        for i, r in enumerate(rows, 1):
            sku = r["sku"].strip()
            exp = int(r["set_qty"] or 1)
            print(f"[{i}/21] {sku}")
            try:
                _search(page, sku)
                p = _parse(page, sku)
            except Exception as exc:
                p = {"found": False, "live_qty": None, "status": "", "snip": str(exc)}
            ver = _verdict(
                exp, p.get("live_qty"), p.get("status") or "", bool(p.get("found"))
            )
            results.append(
                {
                    "sku": sku,
                    "asin": r["asin"],
                    "model": r["model"],
                    "expected_qty": exp,
                    "live_qty": p.get("live_qty"),
                    "status": p.get("status") or "",
                    "verdict": ver,
                    "notes": (p.get("snip") or "")[:160].replace("\n", " "),
                }
            )
            print(f"  {ver} qty={p.get('live_qty')} status={p.get('status')!r}")

        try:
            save_cookies(context)
        except Exception:
            pass
        context.close()

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "sku",
                "asin",
                "model",
                "expected_qty",
                "live_qty",
                "status",
                "verdict",
                "notes",
            ],
        )
        w.writeheader()
        w.writerows(results)

    def n(v):
        return sum(1 for r in results if r["verdict"] == v)

    ok = n("ok")
    ok_i = n("ok_qty_but_inactive")
    z = n("still_0")
    miss = n("missing")
    below = n("qty_below_expected")
    unk = n("found_unknown_qty") + n("inactive_unknown_qty")
    lines = [
        "# Inventory check — qty0 restock batch 107438020664",
        "",
        f"**When:** {time.strftime('%Y-%m-%d %H:%M')} IST",
        "**Account:** Badeja Enterprises → India",
        "**Method:** headless Playwright Manage Inventory, view≈250, SKU search",
        f"**Manifest:** `{MANIFEST.name}` (21 SKUs)",
        f"**View 250 set:** {v250}",
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
    lines += [
        "",
        f"CSV: `{OUT_CSV.name}`",
        "",
        "Source batch: **107438020664** (Done 21/21).",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("WROTE", OUT_MD)
    print(
        json.dumps(
            {
                "ok": ok,
                "ok_inactive": ok_i,
                "still_0": z,
                "missing": miss,
                "below": below,
                "unknown": unk,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
