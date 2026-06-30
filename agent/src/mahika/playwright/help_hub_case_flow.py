"""Help Hub path D — graph: Home/Help → Create issue → NIL → IP2 → Send.

Rules (Sir / BROWSER.md):
- Open Help Hub **once** — never re-goto in retry loops
- **No** Case Lobby, **no** Develop Apps / developer.amazonservices fallback here
- After My issue is not listed: **wait** for step-2 expand — no End/Home scroll spam
"""
from __future__ import annotations

import logging
import os
import re
import time

from playwright.sync_api import FrameLocator, Page

from mahika.config import settings
from mahika.playwright.support_case_flow import (
    INDIA_PAID,
    SupportCaseDraft,
    _goto_resilient,
)

log = logging.getLogger(__name__)

HELP_HUB_HILL = (
    f"https://sellercentral.amazon.in/help/center?redirectSource=Hill"
    f"&mons_sel_dir_paid={INDIA_PAID}"
)
CONTACT_PHONE = os.getenv("MAHIKA_CASE_CONTACT_PHONE", "7015436711").strip()

ISSUE_NOT_LISTED_SELECTORS = (
    "#issueNotListedButton",
    "#MyIssueNotListed",
    "kat-button#issueNotListedButton",
)

_JS_HELP_DOC = """
function helpDoc() {
  let best = document;
  let max = 0;
  for (const iframe of document.querySelectorAll('iframe')) {
    try {
      const d = iframe.contentDocument;
      if (!d) continue;
      const n = d.querySelectorAll('textarea, kat-button').length;
      if (n > max) { max = n; best = d; }
    } catch (_) {}
  }
  return best;
}
"""

_JS_CLICK_NIL = f"""() => {{
{_JS_HELP_DOC}
  function walk(root, fn) {{
    if (!root) return null;
    for (const el of root.querySelectorAll('*')) {{
      if (fn(el)) return el;
      if (el.shadowRoot) {{
        const hit = walk(el.shadowRoot, fn);
        if (hit) return hit;
      }}
    }}
    return null;
  }}
  const doc = helpDoc();
  for (const id of ['issueNotListedButton', 'MyIssueNotListed']) {{
    const box = doc.getElementById(id);
    if (!box) continue;
    box.scrollIntoView({{ block: 'center', behavior: 'instant' }});
    const kat = box.querySelector('kat-button') || box;
    const btn = walk(
      kat.shadowRoot || kat,
      (el) => el.tagName === 'BUTTON' || el.getAttribute?.('role') === 'button'
    );
    if (btn) {{ btn.click(); return {{ ok: true, via: id }}; }}
    kat.click();
    return {{ ok: true, via: id + '/kat' }};
  }}
  return {{ ok: false }};
}}"""

_JS_IP2_FIND = f"""() => {{
{_JS_HELP_DOC}
  function walk(root, out) {{
    if (!root) return;
    for (const el of root.querySelectorAll('textarea, kat-textarea')) {{
      let ta = el;
      if (el.tagName === 'KAT-TEXTAREA') {{
        ta = el.shadowRoot?.querySelector('textarea');
        if (!ta) continue;
      }}
      out.push(ta);
    }}
    for (const el of root.querySelectorAll('*')) {{
      if (el.shadowRoot) walk(el.shadowRoot, out);
    }}
  }}
  function byLabel(doc, needle) {{
    function walkLabels(root) {{
      const out = [];
      if (!root) return out;
      for (const el of root.querySelectorAll('label, kat-label, legend, span, p, div')) {{
        const t = (el.textContent || '').trim().toLowerCase();
        if (t.length > 0 && t.length < 120 && t.includes(needle)) out.push(el);
      }}
      for (const el of root.querySelectorAll('*')) {{
        if (el.shadowRoot) out.push(...walkLabels(el.shadowRoot));
      }}
      return out;
    }}
    for (const el of walkLabels(doc)) {{
      let box = el.parentElement;
      for (let i = 0; i < 8 && box; i++, box = box.parentElement) {{
        for (const raw of box.querySelectorAll('kat-textarea, textarea')) {{
          let ta = raw.tagName === 'KAT-TEXTAREA'
            ? raw.shadowRoot?.querySelector('textarea') : raw;
          if (ta) return ta;
        }}
      }}
    }}
    return null;
  }}
  const doc = helpDoc();
  const bodyText = (doc.body?.innerText || '').toLowerCase();
  const hasLabels = bodyText.includes('what do you need help with')
    && bodyText.includes('what steps have you taken');
  const help = byLabel(doc, 'what do you need help with');
  const steps = byLabel(doc, 'what steps have you taken already');
  if (help && steps) return {{ count: 2, mode: 'label', help: true, steps: true }};
  if (hasLabels) {{
    const all = [];
    walk(doc, all);
    if (all.length >= 2) return {{ count: all.length, mode: 'labels_visible', help: false, steps: false }};
  }}
  const all = [];
  walk(doc, all);
  const ip2 = all.filter((t) => {{
    const p = (t.placeholder || '').toLowerCase();
    return !p.includes('title') && !p.includes('leather') && !p.includes('update the');
  }});
  return {{ count: ip2.length, mode: 'textarea', labels: 0 }};
}}"""

_JS_FILL_IP2 = f"""(args) => {{
  const [help, steps] = args;
{_JS_HELP_DOC}
  function walk(root, out) {{
    if (!root) return;
    for (const el of root.querySelectorAll('textarea, kat-textarea')) {{
      let ta = el;
      if (el.tagName === 'KAT-TEXTAREA') {{
        ta = el.shadowRoot?.querySelector('textarea');
        if (!ta) continue;
      }}
      out.push(ta);
    }}
    for (const el of root.querySelectorAll('*')) {{
      if (el.shadowRoot) walk(el.shadowRoot, out);
    }}
  }}
  function byLabel(doc, needle) {{
    function walkLabels(root) {{
      const out = [];
      if (!root) return out;
      for (const el of root.querySelectorAll('label, kat-label, legend, span, p, div')) {{
        const t = (el.textContent || '').trim().toLowerCase();
        if (t.length > 0 && t.length < 120 && t.includes(needle)) out.push(el);
      }}
      for (const el of root.querySelectorAll('*')) {{
        if (el.shadowRoot) out.push(...walkLabels(el.shadowRoot));
      }}
      return out;
    }}
    for (const el of walkLabels(doc)) {{
      let box = el.parentElement;
      for (let i = 0; i < 8 && box; i++, box = box.parentElement) {{
        for (const raw of box.querySelectorAll('kat-textarea, textarea')) {{
          let ta = raw.tagName === 'KAT-TEXTAREA'
            ? raw.shadowRoot?.querySelector('textarea') : raw;
          if (ta) return ta;
        }}
      }}
    }}
    return null;
  }}
  function setVal(ta, val) {{
    ta.focus();
    ta.value = val;
    ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
    ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
  }}
  const doc = helpDoc();
  const h = byLabel(doc, 'what do you need help with');
  const s = byLabel(doc, 'what steps have you taken already');
  if (h && s) {{
    setVal(h, help);
    setVal(s, steps);
    return {{ ok: true, count: 2, mode: 'label' }};
  }}
  const all = [];
  walk(doc, all);
  const ip2 = all.filter((t) => {{
    const p = (t.placeholder || '').toLowerCase();
    return !p.includes('title') && !p.includes('leather') && !p.includes('update the');
  }});
  if (ip2.length < 2) return {{ ok: false, count: ip2.length }};
  setVal(ip2[0], help);
  setVal(ip2[1], steps);
  return {{ ok: true, count: ip2.length, mode: 'textarea' }};
}}"""

_JS_IP2_COUNT = f"""() => {{
  const r = ({_JS_IP2_FIND})();
  return typeof r === 'object' ? r.count : 0;
}}"""

_JS_RED_VALIDATION = f"""() => {{
{_JS_HELP_DOC}
  const doc = helpDoc();
  const text = (doc.body?.innerText || '').toLowerCase();
  return text.includes('select an issue') || text.includes('complete the required');
}}"""

_JS_NIL_EXISTS = f"""() => {{
{_JS_HELP_DOC}
  const doc = helpDoc();
  return !!(doc.getElementById('issueNotListedButton') || doc.getElementById('MyIssueNotListed'));
}}"""

_IP1_READY_WAIT_S = 45.0
_IP2_EXPAND_WAIT_S = 30.0
_IP2_POLL_MS = 500


def _help_hub_frame(page: Page) -> FrameLocator:
    page.wait_for_selector("iframe#mons-body-container", state="attached", timeout=60_000)
    page.wait_for_timeout(400)
    return page.frame_locator("iframe#mons-body-container")


def _frame_click(frame: FrameLocator, *labels: str) -> bool:
    for label in labels:
        for factory in (
            lambda l=label: frame.get_by_role("button", name=re.compile(l, re.I)),
            lambda l=label: frame.get_by_role("tab", name=re.compile(l, re.I)),
            lambda l=label: frame.get_by_text(l, exact=False),
        ):
            loc = factory()
            if not loc.count():
                continue
            try:
                loc.first.click(timeout=10_000)
                return True
            except Exception:
                continue
    return False


def _wait_ip1_ready(page: Page, frame: FrameLocator) -> bool:
    """Wait for issue picker (NIL button) inside Help Hub iframe — no page scroll."""
    log.info("help_hub: waiting IP1 / NIL button (max %.0fs)", _IP1_READY_WAIT_S)
    deadline = time.monotonic() + _IP1_READY_WAIT_S
    tab_clicks = 0
    while time.monotonic() < deadline:
        try:
            if page.evaluate(_JS_NIL_EXISTS):
                log.info("help_hub: IP1 ready — NIL button found")
                return True
        except Exception:
            pass
        if tab_clicks < 5:
            _frame_click(frame, "Create new issue")
            tab_clicks += 1
        page.wait_for_timeout(1_000)
    return bool(page.evaluate(_JS_NIL_EXISTS))


def _ensure_help_hub_once(page: Page) -> FrameLocator:
    """Graph D3/D5: Help Hub Create new issue — navigate at most once."""
    url = (page.url or "").lower()
    if "help/center" not in url:
        log.info("help_hub: open Help Hub once (Hill)")
        _goto_resilient(page, HELP_HUB_HILL)
        try:
            page.wait_for_url(re.compile(r"help/center", re.I), timeout=30_000)
        except Exception:
            log.warning("help_hub: URL may not be help/center yet — %s", page.url)
        page.wait_for_timeout(2_000)
    else:
        log.info("help_hub: already on Help Hub — skip re-navigate")

    frame = _help_hub_frame(page)
    _frame_click(frame, "Create new issue")
    page.wait_for_timeout(800)

    if not _wait_ip1_ready(page, frame):
        log.error("help_hub: IP1 never loaded (NIL button missing)")
    return frame


def _click_my_issue_not_listed(frame: FrameLocator, page: Page) -> bool:
    """IP1 → NIL. JS shadow click first, then Playwright — no page scroll."""
    try:
        result = page.evaluate(_JS_CLICK_NIL)
        if isinstance(result, dict) and result.get("ok"):
            log.info("help_hub: NIL JS click via %s", result.get("via"))
            page.wait_for_timeout(1_000)
            return True
    except Exception as exc:
        log.debug("help_hub: NIL JS first failed (%s)", exc)

    for sel in ISSUE_NOT_LISTED_SELECTORS:
        loc = frame.locator(sel)
        if not loc.count():
            continue
        try:
            loc.first.scroll_into_view_if_needed(timeout=6_000)
            inner = loc.first.locator("kat-button")
            if inner.count():
                inner.first.click(timeout=10_000, force=True)
                log.info("help_hub: NIL click %s → kat-button", sel)
                return True
            loc.first.click(timeout=10_000, force=True)
            log.info("help_hub: NIL click %s", sel)
            return True
        except Exception as exc:
            log.debug("help_hub: NIL %s failed (%s)", sel, exc)

    if _frame_click(frame, "My issue is not listed"):
        log.info("help_hub: NIL click via label text")
        return True

    try:
        result = page.evaluate(_JS_CLICK_NIL)
        if isinstance(result, dict) and result.get("ok"):
            log.info("help_hub: NIL JS click via %s", result.get("via"))
            return True
    except Exception as exc:
        log.warning("help_hub: NIL JS failed (%s)", exc)
    return False


def _wait_ip2_expand(page: Page) -> bool:
    """After NIL: step-2 expands in ~few seconds — poll quietly, no scroll."""
    log.info("help_hub: waiting IP2 expand (max %.0fs, no scroll)", _IP2_EXPAND_WAIT_S)
    page.wait_for_timeout(1_500)  # expand animation after NIL
    deadline = time.monotonic() + _IP2_EXPAND_WAIT_S
    last_diag = None
    while time.monotonic() < deadline:
        try:
            diag = page.evaluate(_JS_IP2_FIND)
            if isinstance(diag, dict):
                last_diag = diag
                if diag.get("count", 0) >= 2:
                    log.info("help_hub: IP2 ready — %s fields (%s)", diag["count"], diag.get("mode"))
                    return True
        except Exception:
            pass
        page.wait_for_timeout(_IP2_POLL_MS)
    log.warning("help_hub: IP2 expand timeout — last diag %s", last_diag)
    try:
        count = page.evaluate(_JS_IP2_COUNT)
        return isinstance(count, int) and count >= 2
    except Exception:
        return False


def _fill_ip2_fields(page: Page, draft: SupportCaseDraft, frame: FrameLocator | None = None) -> bool:
    result = page.evaluate(
        _JS_FILL_IP2,
        [draft.help_with, draft.steps_taken],
    )
    if isinstance(result, dict) and result.get("ok"):
        log.info("help_hub: IP2 filled (%s fields)", result.get("count"))
        return True

    if frame is not None:
        try:
            pairs = (
                (re.compile(r"need help with", re.I), draft.help_with),
                (re.compile(r"steps have you", re.I), draft.steps_taken),
            )
            filled = 0
            for pattern, text in pairs:
                loc = frame.get_by_label(pattern)
                if loc.count():
                    loc.first.fill(text, timeout=10_000)
                    filled += 1
            if filled >= 2:
                log.info("help_hub: IP2 filled via Playwright labels (%s)", filled)
                return True
        except Exception as exc:
            log.debug("help_hub: IP2 playwright fill (%s)", exc)

    log.warning("help_hub: IP2 JS fill failed: %s", result)
    return False


def _post_ip2_steps(
    page: Page,
    frame: FrameLocator,
    draft: SupportCaseDraft,
    *,
    submit: bool,
) -> None:
    """Graph: after IP2 Continue → ignore suggestion → Other account issues → subject → email → Send."""
    _frame_click(frame, "None of these", "Ignore", "Not related", "Continue")
    page.wait_for_timeout(800)

    _frame_click(frame, "Other account issues")
    page.wait_for_timeout(2_000)

    subject = frame.locator(
        "input[type='text'], input[placeholder*='subject' i], "
        "input[aria-label*='subject' i]"
    )
    if subject.count():
        subject.first.fill(draft.subject, timeout=10_000)

    _frame_click(frame, "Email")
    page.wait_for_timeout(600)

    phone = frame.locator(
        "input[type='tel'], input[name*='phone' i], input[placeholder*='phone' i]"
    )
    if phone.count():
        phone.first.fill(CONTACT_PHONE, timeout=10_000)

    out = settings.storage_root / "logs" / "support_case_form.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out), full_page=True)
    log.info("help_hub: screenshot %s", out)

    if submit:
        _frame_click(frame, "Send", "Submit", "Create case")


def run_help_hub_case_path(
    page: Page,
    draft: SupportCaseDraft,
    *,
    submit: bool,
) -> bool:
    """Path D only — BROWSER.md / FLOW.md graph."""
    frame = _ensure_help_hub_once(page)

    if not page.evaluate(_JS_NIL_EXISTS):
        log.error("help_hub: abort — IP1 not ready")
        return False

    if not _click_my_issue_not_listed(frame, page):
        log.error("help_hub: NIL click failed")
        return False

    page.wait_for_timeout(1_200)

    if not _wait_ip2_expand(page):
        log.info("help_hub: IP2 slow — retry NIL once (same page)")
        _click_my_issue_not_listed(frame, page)
        page.wait_for_timeout(1_500)
        if not _wait_ip2_expand(page):
            log.error("help_hub: IP2 did not expand after NIL (stay on page — no re-open)")
            out = settings.storage_root / "logs" / "support_case_ip2_fail.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(out), full_page=True)
                log.info("help_hub: IP2 fail screenshot %s", out)
            except Exception:
                pass
            return False

    if not _fill_ip2_fields(page, draft, frame):
        return False

    _frame_click(frame, "Continue")
    page.wait_for_timeout(1_200)

    # Red validation only (BROWSER.md): re-NIL + refill once — no scroll loop
    try:
        if page.evaluate(_JS_RED_VALIDATION):
            log.info("help_hub: red validation — NIL + refill once")
            _click_my_issue_not_listed(frame, page)
            page.wait_for_timeout(800)
            _wait_ip2_expand(page)
            _fill_ip2_fields(page, draft, frame)
            _frame_click(frame, "Continue")
            page.wait_for_timeout(1_200)
    except Exception:
        pass

    _post_ip2_steps(page, frame, draft, submit=submit)
    return True
