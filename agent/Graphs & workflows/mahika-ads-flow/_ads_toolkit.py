"""Reusable Playwright helpers for advertising.amazon.in automation.

Distilled from the 2026-08-09 ad-group-creation session, where a plain
text/CSS-selector click failed silently on two separate dynamic-UI cases:
  1. "Enter list" tab text exists TWICE on the New Ad group page (Products
     section + Keyword targeting section below it), the second copy mounting
     asynchronously on an unpredictable delay.
  2. "Negative keyword targeting" heading TEXT has no click handler at all -
     up to 14 DOM ancestors were checked, none were interactive. The real
     toggle is a separate chevron <svg>/<i> icon positioned to the left of
     the heading.

Rather than hard-code either fix, these helpers "observe" the page first
(poll for real state, or scan for the actual interactive element near a
label) and then perform a genuine Playwright click - the same
observe-before-act, self-healing-selector idea Stagehand uses, just without
an LLM in the loop.
"""
import time


def click_or_coords(page, locator, timeout_ms=5000):
    """Click `locator` normally; if Playwright's own actionability check
    reports the click intercepted by another element (a stray overlay -
    confirmed reproducible on the ad-group detail page's 'Negative phrase'
    radio for at least one ad-group, where a data-e2e-id="keywordPicker"
    node from the navbar subtree sat over it on every attempt despite being
    visually empty), fall back to a raw coordinate click via page.mouse,
    which bypasses the interception guard entirely."""
    try:
        locator.click(timeout=timeout_ms)
    except Exception:
        box = locator.bounding_box()
        if not box:
            raise
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def wait_until_loaded(page, timeout_ms=8000):
    """Poll until no 'Loading' spinner text is present. Amazon Ads panels
    (Targeting, Negative targeting, keyword tables) render a 'Loading' state
    that a fixed sleep can race - a screenshot/read taken mid-spinner shows
    nothing useful even though the click that triggered it worked fine."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if page.get_by_text("Loading", exact=True).count() == 0:
            return True
        page.wait_for_timeout(200)
    return False


def wait_for_any_text(page, texts, timeout_ms=12000):
    """Positive wait: poll until ANY of `texts` is visible, instead of
    waiting for absence of a loading indicator. Some Amazon Ads panels (the
    ad-group detail page's Targeting / Negative targeting tabs) show a bare
    spinner icon with no accompanying 'Loading' text at all, so
    wait_until_loaded() returns instantly before the table has rendered.
    Waiting for the actual expected end-state (e.g. a 'Total:' summary row
    or a 'No data available' empty-state) is more reliable than waiting for
    a loading signal to go away when you don't know if one exists."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for t in texts:
            if page.get_by_text(t, exact=False).count() > 0:
                return True
        page.wait_for_timeout(300)
    return False


def click_below(page, section_text, target_text, min_count=1, timeout_ms=10000):
    """Click the occurrence of `target_text` positioned BELOW `section_text`
    on the page. Fixes the duplicate-label race (case 1 above): poll for the
    real element by bounding-box geometry instead of trusting DOM order or a
    fixed sleep, then issue a genuine Playwright .click() (a trusted browser
    event - a raw DOM click via page.evaluate() does not reliably trigger
    this app's React handlers)."""
    heading = page.get_by_text(section_text, exact=False).first
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        heading_box = heading.bounding_box()
        if heading_box:
            candidates = page.get_by_text(target_text, exact=True)
            n = candidates.count()
            below = [
                i for i in range(n)
                if (b := candidates.nth(i).bounding_box()) and b["y"] > heading_box["y"]
            ]
            if len(below) >= min_count:
                candidates.nth(below[0]).click()
                return
        page.wait_for_timeout(250)
    raise RuntimeError(
        f"click_below: no '{target_text}' found below '{section_text}' within {timeout_ms}ms"
    )


def robust_toggle(page, heading_text, verify_text, timeout_ms=8000):
    """Expand a collapsed accordion section labelled `heading_text`, verifying
    success by checking `verify_text` becomes visible. Fixes case 2 above by
    trying strategies in order instead of assuming which one applies:

      1. Click the heading text itself (works for plain clickable tabs).
      2. Click the chevron icon (svg/i) positioned to the left of the
         heading and vertically centered on it - the actual toggle target
         for Amazon Ads' collapsible sections, confirmed via DOM inspection
         this session (heading text itself had no click handler on any of
         14 checked ancestors).
    Raises if neither strategy makes `verify_text` visible within the
    timeout - callers should treat that as a real UI-structure change worth
    re-inspecting, not silently retry.
    """
    heading = page.get_by_text(heading_text, exact=False).first
    heading.scroll_into_view_if_needed()
    page.wait_for_timeout(300)

    def is_expanded():
        loc = page.get_by_text(verify_text, exact=True)
        return loc.count() > 0 and loc.first.is_visible()

    if is_expanded():
        return  # already open

    # strategy 1: click the heading text directly
    try:
        heading.click(timeout=2000)
        page.wait_for_timeout(500)
        if is_expanded():
            return
    except Exception:
        pass

    box = heading.bounding_box()
    if not box:
        raise RuntimeError(f"robust_toggle: heading '{heading_text}' not visible")

    # strategy 2: click the chevron icon to the left of the heading
    icon = page.evaluate(
        """
        (hRect) => {
            const icons = [...document.querySelectorAll('svg, i')].map(el => {
                const r = el.getBoundingClientRect();
                return {x: r.x, y: r.y, w: r.width, h: r.height};
            }).filter(ic => ic.x < hRect.left && ic.y > hRect.top - 10 && ic.y < hRect.bottom + 10);
            return icons[0] || null;
        }
        """,
        {"left": box["x"], "top": box["y"], "bottom": box["y"] + box["height"]},
    )
    if icon:
        page.mouse.click(icon["x"] + icon["w"] / 2, icon["y"] + icon["h"] / 2)
        page.wait_for_timeout(500)
        if is_expanded():
            return

    # strategies 1/2 cover every case seen in this UI so far; give the
    # expand animation a little more time before giving up.
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if is_expanded():
            return
        page.wait_for_timeout(250)
    raise RuntimeError(
        f"robust_toggle: could not expand '{heading_text}' (verify text "
        f"'{verify_text}' never became visible) within {timeout_ms}ms"
    )


def goto_negative_tab(page, timeout_ms=15000):
    """From an ad-group detail page (any tab), click the left-nav 'Negative
    targeting' item and land on it. Confirmed via recon (2026-08-11) that a
    single click often doesn't register the first few times - the nav item
    isn't reliably interactive immediately after the previous tab's own page
    finishes loading (took 5 attempts / ~3.5s in testing). Retries with a
    fresh locator each attempt and verifies via the real end-state markers
    ('Add negative keywords' button or 'Find a negative keyword' placeholder)
    rather than trusting the click to have worked."""
    deadline = time.time() + timeout_ms / 1000
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            page.get_by_text("Negative targeting", exact=True).first.click(timeout=3000)
        except Exception:
            pass
        page.wait_for_timeout(700)
        if (page.get_by_text("Add negative keywords").count() > 0
                or page.get_by_placeholder("Find a negative keyword").count() > 0):
            return True
    return False


def read_total_count(page):
    """After wait_until_loaded(), read the 'Total: N' summary row Amazon Ads
    tables show at the bottom (keyword count, negative count, product count
    all use this same pattern). Returns None if no such row is present."""
    rows = page.get_by_text("Total:", exact=False)
    if rows.count() == 0:
        return None
    text = rows.first.inner_text()
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None
