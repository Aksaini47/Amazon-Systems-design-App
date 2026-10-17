"""Recheck 2 missing SKUs by SKU + ASIN. Budget 90s."""
from __future__ import annotations
import csv, json, sys, time, urllib.parse
from pathlib import Path
sys.path.insert(0, r"c:\Projects\Amazon Systems Design\agent\src")
import os
os.chdir(r"c:\Projects\Amazon Systems Design\agent")
from playwright.sync_api import sync_playwright
from mahika.playwright.account_switcher import complete_account_switcher, is_account_switcher_page
from mahika.playwright.session import CHROMIUM_PROFILE_DIR, load_cookies, save_cookies, session_is_authenticated

ROOT = Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports")
OUT_MD = ROOT / "inventory_check_qty0_restock_2026-07-31.md"
OUT_CSV = ROOT / "inventory_check_qty0_restock_2026-07-31.csv"
TARGETS = [
    ("F17PROLED", "B0CPWBGWBF", "F17 Pro OLED", 1),
    ("RLM13ProOG", "B0F3JMDNDK", "Realme 13 Pro CareOG", 1),
]

def inv_url(term: str) -> str:
    q = urllib.parse.urlencode({
        "fulfilledBy":"all","page":"1","pageSize":"250","searchField":"all",
        "searchTerm":term,"sort":"available_desc","status":"all","ref_":"xx_invmgr_dnav_xx",
    })
    return f"https://sellercentral.amazon.in/myinventory/inventory?{q}"

def parse(page, needle: str):
    return page.evaluate("""(needle) => {
      const norm = s => (s||'').replace(/\\s+/g,' ').trim();
      const nL = needle.toLowerCase();
      const rows = Array.from(document.querySelectorAll('tr,[role=row],.mt-row,kat-table-row,[data-sku],tbody tr'));
      for (const row of rows) {
        const txt = norm(row.innerText || row.textContent || '');
        if (!txt.toLowerCase().includes(nL) || txt.length < 6) continue;
        let qty = null;
        for (const inp of row.querySelectorAll('input')) {
          const val = (inp.value||'').trim();
          const meta = ((inp.name||'')+' '+(inp.id||'')+' '+(inp.getAttribute('aria-label')||'')).toLowerCase();
          if ((/qty|quantity|available/.test(meta) || inp.type==='number') && /^\\d+$/.test(val)) { qty=parseInt(val,10); break; }
        }
        if (qty === null) {
          const m = txt.match(/\\b(?:Quantity|Qty|Available)\\s*[:\\s]?\\s*(\\d+)\\b/i);
          if (m) qty = parseInt(m[1],10);
        }
        let status = '';
        for (const lab of ['Active','Inactive','Incomplete','Suppressed']) {
          if (new RegExp('\\\\b'+lab+'\\\\b','i').test(txt)) { status = lab; break; }
        }
        return {found:true, live_qty:qty, status, snip: txt.slice(0,200)};
      }
      const body = norm(document.body?document.body.innerText:'');
      if (/0 results|no matching|no results|didn.?t find/i.test(body.slice(0,2500)))
        return {found:false, live_qty:null, status:'', snip:'no_results'};
      return {found:false, live_qty:null, status:'', snip: body.slice(0,120)};
    }""", needle)

updates = {}
with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(CHROMIUM_PROFILE_DIR), headless=True,
        viewport={"width":1440,"height":900},
        args=["--disable-blink-features=AutomationControlled"],
    )
    load_cookies(ctx)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(20000)
    page.goto("https://sellercentral.amazon.in/home", wait_until="domcontentloaded", timeout=25000)
    page.wait_for_timeout(800)
    if is_account_switcher_page(page):
        complete_account_switcher(page)
    if not session_is_authenticated(page):
        print("NOT_AUTH")
        ctx.close()
        raise SystemExit(2)
    for sku, asin, model, exp in TARGETS:
        best = None
        for term in (sku, asin):
            print("try", sku, "term", term)
            page.goto(inv_url(term), wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2200)
            p = parse(page, sku if term==sku else asin)
            print(" ", p)
            if p.get("found"):
                best = p
                break
        if best:
            ver = "ok" if best.get("live_qty") is not None and int(best["live_qty"]) >= exp else (
                "still_0" if best.get("live_qty")==0 else (
                "ok_qty_but_inactive" if (best.get("status") or "").lower()=="inactive" and best.get("live_qty") and int(best["live_qty"])>=exp else "found_unknown_qty"
                )
            )
            if best.get("live_qty") is not None and int(best["live_qty"]) >= exp and (best.get("status") or "").lower()=="inactive":
                ver = "ok_qty_but_inactive"
            elif best.get("live_qty") is not None and int(best["live_qty"]) >= exp:
                ver = "ok"
            elif best.get("live_qty") == 0:
                ver = "still_0"
            elif best.get("live_qty") is not None and int(best["live_qty"]) < exp:
                ver = "qty_below_expected"
            else:
                ver = "found_unknown_qty"
            updates[sku] = {
                "live_qty": best.get("live_qty"),
                "status": best.get("status") or "",
                "verdict": ver,
                "notes": (best.get("snip") or "")[:160].replace("\n"," "),
            }
        else:
            updates[sku] = {"live_qty": None, "status": "", "verdict": "missing", "notes": "recheck_no_results"}
    try:
        save_cookies(ctx)
    except Exception:
        pass
    ctx.close()

rows = list(csv.DictReader(OUT_CSV.open(encoding="utf-8")))
for r in rows:
    if r["sku"] in updates:
        u = updates[r["sku"]]
        r["live_qty"] = "" if u["live_qty"] is None else u["live_qty"]
        r["status"] = u["status"]
        r["verdict"] = u["verdict"]
        r["notes"] = u["notes"]

with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["sku","asin","model","expected_qty","live_qty","status","verdict","notes"])
    w.writeheader(); w.writerows(rows)

def n(v): return sum(1 for r in rows if r["verdict"]==v)
ok, ok_i, z, miss = n("ok"), n("ok_qty_but_inactive"), n("still_0"), n("missing")
below = n("qty_below_expected")
unk = n("found_unknown_qty")+n("inactive_unknown_qty")
lines = [
"# Inventory check — qty0 restock batch 107438020664","","**When:** "+time.strftime("%Y-%m-%d %H:%M")+" IST",
"**Account:** Badeja Enterprises → India",
"**Method:** headless Playwright URL search (pageSize=250) + ASIN recheck for misses",
"**Manifest:** `PHONE_ACCESSORY_oos_qty0_manifest.csv` (21 SKUs)",
"**View 250 set:** True (URL pageSize=250)","","## Summary","","| Bucket | Count |","|---|---|",
f"| OK (qty ≥ expected) | {ok} |",
f"| OK qty but Inactive | {ok_i} |",
f"| Still qty 0 | {z} |",
f"| Qty below expected | {below} |",
f"| Missing | {miss} |",
f"| Found but qty unknown | {unk} |",
f"| **Total** | **{len(rows)}** |","","## Per SKU","","| SKU | Expected | Live | Status | Verdict |","|---|---:|---:|---|---|",
]
for r in rows:
    lq = r["live_qty"]
    lines.append(f"| `{r['sku']}` | {r['expected_qty']} | {lq} | {r['status'] or '—'} | {r['verdict']} |")
lines += ["", f"CSV: `{OUT_CSV.name}`", "", "Source batch: **107438020664**."]
OUT_MD.write_text("\n".join(lines)+"\n", encoding="utf-8")
print(json.dumps({"ok":ok,"ok_inactive":ok_i,"still_0":z,"missing":miss,"below":below,"unknown":unk,"updates":updates}, default=str))