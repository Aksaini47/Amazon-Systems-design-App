# -*- coding: utf-8 -*-
"""Reusable AG-Grid interaction library for the TL_EL_SPN_SG_Mobile Screens
campaign's ad-group Targeting/Negative-targeting pages. Built and proven
2026-08-23 during the Phase 2/3 bid-rebalancing + harvest/pause/negative
rollout (71 ad-groups). Import this from any per-batch runner script,
including the weekly_search_term_optimization.py pipeline.

Key AG-Grid facts this library encodes (see PROGRESS notes for the full
debugging story):
- Pinned-left columns (checkbox, keyword name) and center columns (match
  type, bid) render as SEPARATE .ag-row DOM nodes linked only by a shared
  row-id attribute - never nested. Always resolve the checkbox via the
  pinned row matching the same row-id, not via the row that matched the
  text you were searching for.
- Row-selection checkboxes are visually hidden (input.ag-checkbox-input);
  a raw .click() works fine once you've found the RIGHT input.
- The grid virtualizes rows - only ~30-40 of a 70+ row ad-group are in the
  DOM at once. Scrolling the largest scrollable child (heuristic: max
  clientHeight, scrollHeight > clientHeight+20) reveals more; repeat
  select+scroll until 3 stagnant rounds. Even then a single pass typically
  only catches ~40-60% of matching rows - call the *_with_retries variant
  (3 passes) for close-to-complete coverage, and don't be surprised if a
  handful of rows still need a manual follow-up pass later.
- "Enter list" and other tab labels are NOT <button> elements and don't
  reliably respond to a JS .click() (the tab visually never switches, its
  own loading spinner never resolves) - use Playwright's own
  get_by_text(...).click() (real mouse event sequence) instead.
- The "Add negative keywords" submit button can stay permanently disabled
  even after a real Playwright .type() fill - this happens when the typed
  term is IDENTICAL to one of the ad-group's own POSITIVE keywords (Amazon
  correctly blocks a self-conflicting negative). Don't keep retrying this;
  treat add_clicked=False as "likely self-conflict, skip" rather than a bug.
"""
import time

BIDS = {"Broad": "1", "Phrase": "2", "Exact": "3.5"}
CAMPAIGN = "A038001030A5E0IF4R8UV"
ENTITY = "ENTITY37NJTG1VOHVTB"


def targeting_url(ag_id):
    return f"https://advertising.amazon.in/cm/sp/campaigns/{CAMPAIGN}/ad-groups/{ag_id}/targeting?entityId={ENTITY}"


def negative_targeting_url(ag_id):
    return f"https://advertising.amazon.in/cm/sp/campaigns/{CAMPAIGN}/ad-groups/{ag_id}/negative-targeting?entityId={ENTITY}"


def ad_groups_list_url():
    return f"https://advertising.amazon.in/cm/sp/campaigns/{CAMPAIGN}/ad-groups?entityId={ENTITY}"


def wait_for_grid(page, timeout_s=40):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if page.get_by_text("Total:", exact=False).count() > 0:
            return True
        page.wait_for_timeout(500)
    try:
        page.reload(wait_until="domcontentloaded", timeout=60_000)
    except Exception:
        return False
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if page.get_by_text("Total:", exact=False).count() > 0:
            return True
        page.wait_for_timeout(500)
    return False


def select_none(page):
    page.evaluate(
        """() => {
            const el = [...document.querySelectorAll('*')].find(e =>
                e.children.length === 0 && (e.textContent||'').trim() === 'Select none');
            if (el) el.click();
        }"""
    )
    page.wait_for_timeout(300)


def selected_row_count(page):
    """N from the 'Bulk actions (N selected)' button, 0 if nothing is selected."""
    import re
    t = page.evaluate(
        """() => { const b = [...document.querySelectorAll('button,[role=button]')].find(e =>
            /Bulk actions/i.test(e.textContent||'')); return b ? b.textContent : ''; }"""
    )
    m = re.search(r"\((\d+)\s+selected\)", t or "")
    return int(m.group(1)) if m else 0


def select_all_rows_header(page):
    """Select EVERY row of the Targeting grid via the header checkbox and return how many are selected.

    Verified 2026-09-21 on 43- and 72-row ad-groups (7/7 clean, bid change re-read from the
    SPAdGroupTargetsReport payload afterwards). The header checkbox's real <input> is a 1x1 sprite,
    so a locator .click() hits nothing - click the visible 16x16 box by its bounding-box centre.
    Always compare the returned count with the payload's row count before a bulk action, and
    verify the change by re-reading the payload (never trust the script's own 'saved' flag).
    """
    select_none(page)
    page.wait_for_timeout(900)
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(500)
    box = page.evaluate(
        """() => { const h = document.querySelector('.ag-header-cell-comp-wrapper'); if (!h) return null;
            const el = h.querySelector('input, [class*=sc-storm-ui]'); if (!el) return null;
            const r = (el.closest('label')||el.parentElement).getBoundingClientRect();
            return [r.x + r.width/2, r.y + r.height/2]; }"""
    )
    if box:
        page.mouse.click(box[0], box[1])
        page.wait_for_timeout(1500)
    return selected_row_count(page)


def select_all_of_matchtype_once(page, match_type):
    """One scroll-through pass. Returns set of row-ids newly selected."""
    total_selected = set()
    stagnant_rounds = 0
    for _ in range(40):
        result = page.evaluate(
            f"""() => {{
                const targetType = {match_type!r};
                const rows = [...document.querySelectorAll('.ag-row')];
                const matchTypeRowIds = new Set();
                for (const row of rows) {{
                    if ((row.textContent || '').includes(targetType)) {{
                        matchTypeRowIds.add(row.getAttribute('row-id'));
                    }}
                }}
                for (const rowId of matchTypeRowIds) {{
                    const pinnedRow = rows.find(r => r.getAttribute('row-id') === rowId && r.querySelector('input.ag-checkbox-input'));
                    if (!pinnedRow) continue;
                    const cb = pinnedRow.querySelector('input.ag-checkbox-input');
                    if (!cb.checked) cb.click();
                }}
                return {{seenIds: [...matchTypeRowIds]}};
            }}"""
        )
        before_count = len(total_selected)
        total_selected.update(result["seenIds"])

        scroll_info = page.evaluate(
            """() => {
                const candidates = [...document.querySelectorAll('div')].filter(e =>
                    e.scrollHeight > e.clientHeight + 20 && e.clientHeight > 100);
                let best = null;
                for (const c of candidates) {
                    if (!best || c.clientHeight > best.clientHeight) best = c;
                }
                if (!best) return {found: false};
                const before = best.scrollTop;
                best.scrollTop += 300;
                return {found: true, before, after: best.scrollTop};
            }"""
        )
        page.wait_for_timeout(350)

        stagnant = (len(total_selected) == before_count)
        no_scroll = (not scroll_info.get("found") or scroll_info.get("before") == scroll_info.get("after"))
        stagnant_rounds = stagnant_rounds + 1 if (stagnant and no_scroll) else 0
        if stagnant_rounds >= 3:
            break
    return total_selected


def click_adjust_bid_and_save(page, bid):
    page.evaluate(
        """() => {
            const el = [...document.querySelectorAll('button, [role=button]')].find(e =>
                /Bulk actions/i.test(e.textContent||''));
            if (el) el.click();
        }"""
    )
    page.wait_for_timeout(600)
    opened = page.evaluate(
        """() => {
            const el = [...document.querySelectorAll('*')].find(e =>
                e.children.length === 0 && /^Adjust bid$/i.test((e.textContent||'').trim()));
            if (el) { el.click(); return true; }
            return false;
        }"""
    )
    if not opened:
        return {"error": "adjust_bid_not_found"}
    page.wait_for_timeout(900)

    # Real Playwright .fill() - native-setter + dispatchEvent was confirmed
    # unreliable in this app for a near-identical modal (add_exact_keyword's
    # textarea, see feedback_add_keyword_missing_save_click in memory).
    bid_input = page.locator(
        "input[aria-label*='bid' i], input[aria-label*='amount' i]"
    ).first
    if bid_input.count() == 0:
        bid_input = page.locator("input[type=text]:visible, input[type=number]:visible").last
    if bid_input.count() == 0:
        return {"fill": {"err": "no input"}}
    bid_input.fill(str(bid))
    fill_result = {"filled": True, "value": bid_input.input_value()}
    page.wait_for_timeout(300)
    saved = page.evaluate(
        """() => {
            const btn = [...document.querySelectorAll('button')].find(b =>
                /^Save changes$/i.test((b.textContent||'').trim()) && !b.disabled);
            if (btn) { btn.click(); return true; }
            return false;
        }"""
    )
    page.wait_for_timeout(2200)
    return {"fill": fill_result, "saved": saved}


def apply_bid_for_matchtype_with_retries(page, match_type, bid, passes=3):
    total_processed = 0
    for _p in range(passes):
        select_none(page)
        selected = select_all_of_matchtype_once(page, match_type)
        if not selected:
            break
        result = click_adjust_bid_and_save(page, bid)
        if result.get("error") or not result.get("saved"):
            break
        total_processed += len(selected)
    return total_processed


def pause_matchtype_rows(page, match_type):
    """Select all rows of match_type, Bulk actions -> Quick Actions -> Pause."""
    select_none(page)
    selected = select_all_of_matchtype_once(page, match_type)
    if not selected:
        return {"selected": 0, "status": "no_rows_found"}
    page.evaluate(
        """() => {
            const el = [...document.querySelectorAll('button, [role=button]')].find(e =>
                /Bulk actions/i.test(e.textContent||''));
            if (el) el.click();
        }"""
    )
    page.wait_for_timeout(600)
    clicked = page.evaluate(
        """() => {
            const el = [...document.querySelectorAll('*')].find(e =>
                e.children.length === 0 && /^Pause$/i.test((e.textContent||'').trim()));
            if (el) { el.click(); return true; }
            return false;
        }"""
    )
    page.wait_for_timeout(2000)
    return {"selected": len(selected), "paused_clicked": clicked}


def add_exact_keyword(page, keyword_text, bid="3.5"):
    """Add ONE keyword as Exact match only, via the 'Add keywords' -> Enter
    list flow (existing ad-group's Targeting page)."""
    clicked = page.evaluate(
        """() => {
            const btn = [...document.querySelectorAll('button')].find(b =>
                /^Add keywords$/i.test((b.textContent||'').trim()));
            if (btn) { btn.click(); return true; }
            return false;
        }"""
    )
    if not clicked:
        return {"error": "no Add keywords button"}
    modal_ready = False
    for _ in range(40):
        if page.get_by_text("Enter list", exact=True).count() > 0:
            modal_ready = True
            break
        page.wait_for_timeout(500)
    if not modal_ready:
        return {"error": "modal never loaded (Enter list tab never appeared)"}
    page.wait_for_timeout(500)

    enter_list_loc = page.get_by_text("Enter list", exact=True).first
    enter_list_loc.click()
    page.wait_for_timeout(1200)

    page.evaluate(
        """() => {
            for (const lab of document.querySelectorAll('label')) {
                const t = lab.innerText.trim().toLowerCase();
                const cb = lab.querySelector('input[type=checkbox]');
                if (!cb) continue;
                if (t === 'broad' && cb.checked) cb.click();
                if (t === 'phrase' && cb.checked) cb.click();
                if (t === 'exact' && !cb.checked) cb.click();
            }
        }"""
    )
    page.wait_for_timeout(400)

    bid_opened = page.evaluate(
        """() => {
            const btn = [...document.querySelectorAll('button,[role=button]')].find(b =>
                /^Suggested bid$/i.test((b.textContent||'').trim()));
            if (btn) { btn.click(); return true; }
            return false;
        }"""
    )
    page.wait_for_timeout(500)
    if bid_opened:
        page.evaluate(
            """() => {
                const opt = [...document.querySelectorAll('[role=option],li,button,div,span')].find(e =>
                    /^Custom bid$/i.test((e.textContent||'').trim()));
                if (opt) opt.click();
            }"""
        )
        page.wait_for_timeout(500)

    # Real Playwright .fill() (native-setter + dispatchEvent was silently
    # ignored by React on this textarea, same class of bug as the bid
    # dialog - see feedback_ads_grid_bid_write_fails in memory).
    bid_input = page.locator("input[aria-label*='bid' i], input[placeholder*='bid' i]").first
    if bid_input.count() > 0:
        bid_input.fill(str(bid))

    textarea = page.locator("textarea[aria-label*='keyword' i], textarea[aria-label*='new line' i]").first
    if textarea.count() == 0:
        textarea = page.locator("textarea").last
    if textarea.count() == 0:
        return {"fill": {"err": "no textarea"}}
    textarea.fill(keyword_text)
    page.wait_for_timeout(400)

    # This "Add keywords" click only stages the keyword into an in-modal
    # preview list ("N/N keywords were added successfully") - it does NOT
    # persist anything by itself. A separate "Save" button commits the
    # staged list to the ad-group. Confirmed live 2026-09-16: two prior
    # attempts both reported added=True and left nothing saved, because
    # this Save click was missing entirely.
    add_button = page.get_by_role("button", name="Add keywords", exact=True)
    staged = False
    if add_button.count() > 0 and add_button.first.is_enabled():
        add_button.first.click()
        staged = True
    page.wait_for_timeout(1200)

    save_button = page.get_by_role("button", name="Save", exact=True)
    saved = False
    if save_button.count() > 0 and save_button.first.is_enabled():
        save_button.first.click()
        saved = True
    page.wait_for_timeout(2500)
    return {"fill": {"staged": staged, "saved": saved, "textarea_value_set": keyword_text}}


def goto_negative_tab(page, ag_id):
    page.goto(negative_targeting_url(ag_id), wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(1500)
    wait_for_grid(page, timeout_s=20)


def add_negative_exact(page, term):
    """Add ONE Negative Exact keyword on the Negative targeting tab. Returns
    add_clicked=False (with no error) when Amazon silently blocks the term
    for conflicting with the ad-group's own positive keyword set - treat
    that as an expected skip, not a bug to keep retrying."""
    clicked = page.evaluate(
        """() => {
            const btn = [...document.querySelectorAll('button')].find(b =>
                /Add negative keywords|^Add keywords$/i.test((b.textContent||'').trim()));
            if (btn) { btn.click(); return true; }
            return false;
        }"""
    )
    if not clicked:
        return {"error": "no add-negative button"}
    modal_ready = False
    for _ in range(30):
        if page.locator("textarea").count() > 0:
            modal_ready = True
            break
        page.wait_for_timeout(500)
    if not modal_ready:
        return {"error": "modal never loaded"}
    page.wait_for_timeout(400)

    exact_result = page.evaluate(
        """() => {
            const el = [...document.querySelectorAll('label,button,[role=radio]')].find(e =>
                /Negative exact/i.test(e.textContent||e.getAttribute('aria-label')||''));
            if (el) { el.click(); return true; }
            return false;
        }"""
    )
    page.wait_for_timeout(400)

    ta_locator = page.locator("textarea").last
    ta_locator.click()
    ta_locator.fill("")
    ta_locator.type(term, delay=15)
    page.wait_for_timeout(500)
    filled_value = page.evaluate("() => [...document.querySelectorAll('textarea')].pop().value")

    add_clicked = False
    for _ in range(15):
        add_clicked = page.evaluate(
            """() => {
                const add = [...document.querySelectorAll('button')].find(b =>
                    /Add negative keywords|^Add$/i.test((b.textContent||'').trim()) && !b.disabled);
                if (add) { add.click(); return true; }
                return false;
            }"""
        )
        if add_clicked:
            break
        page.wait_for_timeout(400)
    page.wait_for_timeout(2000)
    return {"exact_selected": exact_result, "fill": {"filled": filled_value}, "add_clicked": add_clicked}


def process_ad_group_bids(page, ag_id, ag_name):
    """Apply the standard Broad=1/Phrase=2/Exact=3.5 bid policy to one
    ad-group. Used for newly-created or newly-reactivated ad-groups that
    haven't been through the rebalancing pass yet."""
    url = targeting_url(ag_id)
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(1500)
    if not wait_for_grid(page, timeout_s=15):
        page.reload(wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(1500)
        if not wait_for_grid(page, timeout_s=20):
            return {"ad_group": ag_name, "id": ag_id, "status": "grid_not_loaded"}

    counts = {}
    for mt, bid in BIDS.items():
        counts[mt] = apply_bid_for_matchtype_with_retries(page, mt, bid, passes=3)
    return {"ad_group": ag_name, "id": ag_id, "status": "done", "counts": counts}
