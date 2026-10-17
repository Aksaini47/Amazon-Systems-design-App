# -*- coding: utf-8 -*-
"""Weekly Search Term + Ad Campaign optimization pipeline for
TL_EL_SPN_SG_Mobile Screens - Arun (Sir's standing request, set up
2026-08-23 after the Phase 2/3 manual rollout).

Run this end-to-end, once a week, to keep ad spend aligned with real
converting traffic:

  1. Fetch the CURRENT ad-group list + status (Delivering/Paused) fresh -
     never reuse a stale list from a prior week; ad-groups get paused/
     un-paused/created between runs (dead-stock cleanup, new listings).
  2. Request + download a fresh 30-day Search Term Report (Amazon's report
     only retains ~30-33 days of real search-term-level data regardless of
     a longer requested range - confirmed 2026-08-23, don't bother asking
     for 60+ days again).
  3. Analyze: aggregate spend/sales/orders by (ad_group, match_type);
     split into "matched" (customer search term == our own keyword,
     usually converts far better) vs "discovered" (broad/phrase caught a
     different phrase).
  4. Build candidate lists, filtered to ad-groups that are CURRENTLY
     ACTIVE (this filter matters - a large fraction of "bleed" in any
     given week's data comes from ad-groups already paused as dead stock
     earlier in the week; touching them wastes a cycle):
       - zero_sale_pause: (ad_group, match_type) with spend>=Rs.50 and
         sales==0 over the report window -> pause those rows.
       - harvest: DISCOVERED search terms that converted (orders>0) and
         aren't already one of the ad-group's own keywords -> add as a
         dedicated Exact keyword at Rs.3.5 so they get proper priority
         instead of riding on a Broad/Phrase catch-all.
       - noise_candidates: DISCOVERED terms with spend>=Rs.30 and zero
         orders -> REVIEW ONLY, never auto-negatived (see
         feedback_search_term_negative_price_confound in memory: a term
         can be perfectly relevant and still never convert because the
         LISTING's price isn't competitive, not because the keyword is
         bad - collapsing "zero conversions" and "bad keyword" into one
         auto-action was the mistake here before 2026-09-11). Printed and
         written to the output JSON for Sir to triage once the separate
         pricing/listing-quality workstream exists.
  5. Execute pause+harvest via _ads_bid_worker_lib.py, one ad-group per
     browser visit.
  6. Print a summary Sir can skim: counts per bucket, total newly-paused
     spend, keywords harvested, noise candidates flagged for review.

This does NOT re-run the full Broad=1/Phrase=2/Exact=3.5 bid rebalance
every week (that was a one-time correction after finding no such policy
existed). It only touches ad-groups that this week's report flags.

Usage (interactive or from a scheduled/cron session):
    python weekly_search_term_optimization.py
"""
import io
import sys
import json
import time
from pathlib import Path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

AGENT_SRC = Path(r"C:\Projects\Amazon Systems Design\agent\src")
THIS_DIR = Path(__file__).parent
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import openpyxl
from playwright.sync_api import sync_playwright

from mahika.playwright.session import CHROMIUM_PROFILE_DIR, save_cookies
from mahika.playwright.account_switcher import complete_account_switcher, is_account_switcher_page
from _ads_bid_worker_lib import (
    CAMPAIGN, ENTITY, ad_groups_list_url, wait_for_grid, targeting_url,
    pause_matchtype_rows, add_exact_keyword,
)

REPORTS_DIR = Path(r"C:\Projects\Amazon Systems Design\catalog-builder\amazon-reports")
STAMP = time.strftime("%Y-%m-%d") if hasattr(time, "strftime") else "run"
# NOTE: time.strftime is fine here (this script runs standalone via a
# scheduled session, not inside a Workflow script where Date/time are
# disallowed).

PAUSE_SPEND_THRESHOLD = 50.0
NOISE_SPEND_THRESHOLD = 30.0
HARVEST_BID = "3.5"


# ---------------------------------------------------------------------
# Step 1: fresh ad-group list (name, id, status)
# ---------------------------------------------------------------------

def fetch_all_ad_groups(page):
    page.goto(ad_groups_list_url(), wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(3000)
    if is_account_switcher_page(page):
        complete_account_switcher(page)
        page.goto(ad_groups_list_url(), wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(2000)
    wait_for_grid(page, timeout_s=30)

    # Bump results-per-page to the max to minimize pagination round-trips.
    page.evaluate(
        """() => {
            const el = [...document.querySelectorAll('*')].find(e =>
                (e.textContent||'').includes('Results per page'));
            if (el) el.click();
        }"""
    )
    page.wait_for_timeout(500)
    page.evaluate(
        """() => {
            const opts = [...document.querySelectorAll('[role=option],li,div,span')].filter(e =>
                /^\\d+$/.test((e.textContent||'').trim()));
            if (!opts.length) return;
            opts.sort((a,b) => parseInt(b.textContent) - parseInt(a.textContent));
            opts[0].click();
        }"""
    )
    page.wait_for_timeout(1500)

    all_rows = {}
    for _page_num in range(10):  # safety cap
        rows = page.evaluate(
            """() => {
                const out = [];
                for (const row of document.querySelectorAll('.ag-row')) {
                    const link = row.querySelector('a[href*="ad-groups/"]');
                    if (!link) continue;
                    const href = link.getAttribute('href') || '';
                    const m = href.match(/ad-groups\\/(A[A-Z0-9]+)/i);
                    if (!m) continue;
                    const statusText = row.textContent || '';
                    const status = /Delivering/i.test(statusText) ? 'Delivering'
                                  : /Paused/i.test(statusText) ? 'Paused'
                                  : 'Unknown';
                    out.push({name: link.textContent.trim(), id: m[1], status});
                }
                return out;
            }"""
        )
        for r in rows:
            all_rows[r["id"]] = r
        next_clicked = page.evaluate(
            """() => {
                const btn = [...document.querySelectorAll('button')].find(b =>
                    (b.getAttribute('aria-label')||'').toLowerCase().includes('next page') && !b.disabled);
                if (btn) { btn.click(); return true; }
                return false;
            }"""
        )
        if not next_clicked:
            break
        page.wait_for_timeout(1500)
        wait_for_grid(page, timeout_s=15)

    return all_rows


# ---------------------------------------------------------------------
# Step 2: request + download a fresh Search Term Report
# ---------------------------------------------------------------------

def request_and_download_report(page, report_name):
    reports_url = f"https://advertising.amazon.in/reports?entityId={ENTITY}"
    page.goto(reports_url, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(3000)

    page.get_by_role("button", name="Create report").click()
    page.wait_for_timeout(2500)
    name_input = page.locator("#report-name-input")
    if name_input.count() == 0:
        name_input = page.get_by_placeholder("Report name")
    name_input.first.click()
    name_input.first.fill(report_name)
    page.get_by_role("button", name="Run report").click()
    page.wait_for_timeout(3000)

    history_url = page.url
    print("report requested, history url:", history_url)

    # Poll for completion - a 30-day Search Term report typically finishes
    # within a few minutes.
    for _ in range(30):
        page.goto(history_url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(3000)
        body = page.inner_text("body")
        if "Completed" in body:
            break
        page.wait_for_timeout(60_000)
    else:
        print("WARNING: report did not complete within the poll window")
        return None

    dest = REPORTS_DIR / f"weekly_search_term_{STAMP}.xlsx"
    with page.expect_download(timeout=30_000) as dl_info:
        page.get_by_text("Download", exact=True).first.click()
    dl_info.value.save_as(str(dest))
    print("downloaded to:", dest)
    return dest


# ---------------------------------------------------------------------
# Step 3: analyze
# ---------------------------------------------------------------------

def f(v):
    return float(v) if v is not None else 0.0


def norm(s):
    return (s or "").strip().lower()


def analyze_report(xlsx_path, active_names):
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = []
    for row in ws.iter_rows(min_row=2, max_row=2_000_000, min_col=1, max_col=25, values_only=True):
        if row[0] is None:
            break
        rows.append(row)
    print(f"Report rows: {len(rows)}")

    # Columns: 5 Ad Group, 7 Targeting, 8 Match Type, 9 Customer Search Term,
    # 11 Clicks, 14 Spend, 15 Sales, 18 Orders
    by_agmt = defaultdict(lambda: {"spend": 0.0, "sales": 0.0, "orders": 0})
    for r in rows:
        key = (r[5], r[8])
        d = by_agmt[key]
        d["spend"] += f(r[14]); d["sales"] += f(r[15]); d["orders"] += f(r[18])

    zero_sale_pause = []
    for (ag, mt), d in by_agmt.items():
        if ag in active_names and d["spend"] >= PAUSE_SPEND_THRESHOLD and d["sales"] == 0:
            zero_sale_pause.append({"ad_group": ag, "match_type": mt, "spend": d["spend"]})

    harvest = []
    seen_harvest = set()
    for r in rows:
        ag, targeting, mt, search_term = r[5], r[7], r[8], r[9]
        if ag not in active_names:
            continue
        if norm(targeting) == norm(search_term):
            continue  # matched, not discovered
        if f(r[18]) <= 0:
            continue  # didn't convert
        key = (ag, norm(search_term))
        if key in seen_harvest:
            continue
        seen_harvest.add(key)
        harvest.append({"ad_group": ag, "term": search_term, "orders": f(r[18]), "sales": f(r[15])})

    noise_candidates = []
    seen_noise = set()
    for r in rows:
        ag, targeting, mt, search_term = r[5], r[7], r[8], r[9]
        if ag not in active_names:
            continue
        if norm(targeting) == norm(search_term):
            continue
        if f(r[18]) > 0 or f(r[14]) < NOISE_SPEND_THRESHOLD:
            continue
        key = (ag, norm(search_term))
        if key in seen_noise:
            continue
        seen_noise.add(key)
        noise_candidates.append({"ad_group": ag, "term": search_term, "spend": f(r[14])})

    return {"zero_sale_pause": zero_sale_pause, "harvest": harvest, "noise_candidates": noise_candidates}


# ---------------------------------------------------------------------
# Step 4: execute
# ---------------------------------------------------------------------

def build_per_adgroup_tasks(analysis):
    tasks = defaultdict(lambda: {"pause": [], "harvest": []})
    for z in analysis["zero_sale_pause"]:
        tasks[z["ad_group"]]["pause"].append(z["match_type"].capitalize())
    for h in analysis["harvest"]:
        tasks[h["ad_group"]]["harvest"].append(h["term"])
    return dict(tasks)


def execute_tasks(context, page, name_to_id, tasks):
    results = []
    for ag_name, task in tasks.items():
        ag_id = name_to_id.get(ag_name)
        if not ag_id:
            results.append({"ad_group": ag_name, "status": "no_id_mapping"})
            continue
        result = {"ad_group": ag_name, "id": ag_id, "pause": {}, "harvest": {}}
        try:
            if task["pause"] or task["harvest"]:
                page.goto(targeting_url(ag_id), wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(1500)
                if not wait_for_grid(page, timeout_s=40):
                    result["status"] = "grid_not_loaded"
                    results.append(result)
                    continue
                for mt in task["pause"]:
                    result["pause"][mt] = pause_matchtype_rows(page, mt)
                for kw in task["harvest"]:
                    page.reload(wait_until="domcontentloaded", timeout=60_000)
                    page.wait_for_timeout(1000)
                    wait_for_grid(page, timeout_s=30)
                    result["harvest"][kw] = add_exact_keyword(page, kw, bid=HARVEST_BID)
            result["status"] = "done"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)[:200]
            # The old page is dead after an exception; every ad-group visited
            # later in this same loop needs a live page, so replace it here
            # instead of leaving `page` closed for the rest of the run.
            try:
                page.close()
            except Exception:
                pass
            page = context.new_page()
        results.append(result)
        print("[weekly]", result)
    return results


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(CHROMIUM_PROFILE_DIR), headless=False,
            viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        print("=== Step 1: fetching fresh ad-group list ===")
        all_ags = fetch_all_ad_groups(page)
        active_names = {r["name"] for r in all_ags.values() if r["status"] == "Delivering"}
        name_to_id = {r["name"]: agid for agid, r in all_ags.items()}
        print(f"Total ad-groups: {len(all_ags)}, active (Delivering): {len(active_names)}")

        print("\n=== Step 2: requesting + downloading Search Term report ===")
        report_path = request_and_download_report(page, f"Weekly_SearchTerm_{STAMP}")
        if report_path is None:
            print("Aborting - report never completed.")
            save_cookies(context)
            context.close()
            return 1

        print("\n=== Step 3: analyzing ===")
        analysis = analyze_report(report_path, active_names)
        print(f"zero_sale_pause candidates: {len(analysis['zero_sale_pause'])}")
        print(f"harvest candidates: {len(analysis['harvest'])}")
        print(f"noise candidates (review only, not auto-actioned): {len(analysis['noise_candidates'])}")

        tasks = build_per_adgroup_tasks(analysis)
        print(f"\nDistinct ad-groups needing pause/harvest action: {len(tasks)}")

        print("\n=== Step 4: executing (pause + harvest only) ===")
        results = execute_tasks(context, page, name_to_id, tasks)

        out_file = REPORTS_DIR / f"weekly_optimization_result_{STAMP}.json"
        out_file.write_text(
            json.dumps(
                {
                    "ad_group_results": results,
                    "noise_candidates_for_review": analysis["noise_candidates"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nSaved results to {out_file}")

        save_cookies(context)
        context.close()

    # Summary
    n_paused = sum(1 for r in results for v in r.get("pause", {}).values() if v.get("paused_clicked"))
    n_harvested = sum(1 for r in results for v in r.get("harvest", {}).values() if v.get("fill", {}).get("saved"))
    print(f"\n=== SUMMARY ===")
    print(f"Ad-groups touched: {len(results)}")
    print(f"Match-type rows paused: {n_paused}")
    print(f"Keywords harvested: {n_harvested}")
    print(f"\n=== NOISE CANDIDATES - REVIEW ONLY, nothing auto-negatived ===")
    print("Zero conversions here can mean a bad keyword OR just an uncompetitive")
    print("listing price - don't negative any of these until that's checked.")
    for n in analysis["noise_candidates"]:
        print(f"  ad_group={n['ad_group']!r}  term={n['term']!r}  spend=Rs{n['spend']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
