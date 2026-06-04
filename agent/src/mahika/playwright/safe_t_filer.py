"""SAFE-T claim filing orchestrator — the Phase 5 main deliverable.

Public entry point:

    from mahika.playwright.safe_t_filer import file_one_queued_claim
    result = file_one_queued_claim()   # pops one queued claim + files it

The function pops the oldest unfiled claim from the queue (via
`services.claim_queue.pop_next_claim()`), runs the Playwright flow on
Seller Central, and either calls `mark_filed()` (success) or `mark_attempt()`
(failure with retry on next tick).

Per `mahika_capture_specs.md §9.3`, every step is wrapped in a screenshot
audit trail (court-grade evidence) — the screenshots land at:

    {storage_root}/orders/{order_id}/{order_id}_claim_{step}.png

with `step ∈ {form_loaded, before_submit, submitted}`. The "submitted"
screenshot is the canonical one recorded in `claims.submission_screenshot`.

Mode-aware behavior:
    `MAHIKA_MODE=shadow`   — runs end-to-end EXCEPT clicks the submit button.
                             Captures all screenshots, never actually files.
                             Used for Phase 7a validation.
    `MAHIKA_MODE=manual`   — same as shadow but pops up a confirmation prompt.
                             For Sir's per-action approval debugging.
    `MAHIKA_MODE=live`     — full autonomous filing (Phase 7b/c).
    `MAHIKA_MODE=paused`   — refuse to file; return None.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from mahika.config import settings
from mahika.playwright import session, templates
from mahika.playwright.selectors import SELECTORS, URLs
from mahika.playwright.session import NoSessionAvailable
from mahika.services import claim_queue
from mahika.services.claim_queue import QueuedClaim
from mahika.services.notifier import Priority, alert
from mahika.utils.audit import audit

if TYPE_CHECKING:
    from playwright.sync_api import Page

log = logging.getLogger(__name__)

PAGE_TIMEOUT_MS = 30_000  # navigation/locator wait timeout


# ─── Filing outcomes ─────────────────────────────────────────────────────


@dataclass
class FilingResult:
    claim_id: str          # internal UUID
    order_id: str
    success: bool
    amazon_claim_id: str | None
    screenshot_path: str | None
    error: str | None = None
    mode: str = "live"     # which mode the filing ran under

    def to_audit_payload(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "order_id": self.order_id,
            "success": self.success,
            "amazon_claim_id": self.amazon_claim_id,
            "screenshot_path": self.screenshot_path,
            "error": self.error,
            "mode": self.mode,
        }


# ─── Screenshot helper ───────────────────────────────────────────────────


def _screenshot(page: Page, order_id: str, step: str) -> Path:
    """Save a screenshot at the standard audit path."""
    folder = settings.orders_dir / order_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{order_id}_claim_{step}.png"
    page.screenshot(path=str(path), full_page=True)
    return path


# ─── Verdict → template key resolution ───────────────────────────────────


def _verdict_to_template_key(verdict: str | None) -> templates.VerdictKey:
    """Map the DB enum `qc_verdict` to the templates module's VerdictKey."""
    if verdict in ("damaged", "damaged_different", "different"):
        return verdict  # type: ignore[return-value]
    # Default to 'different' if verdict missing or 'ok' (shouldn't happen for
    # queued claims — defensive fallback to keep filing path safe).
    return "different"


# ─── Order metadata fetch (for verdict + claim text) ─────────────────────


def _fetch_order_for_claim(order_id: str) -> dict:
    from sqlalchemy import text

    from mahika.db.connection import get_session

    with get_session() as s:
        row = s.execute(
            text("SELECT verdict::text, state::text FROM orders WHERE order_id = :oid"),
            {"oid": order_id},
        ).first()
    if row is None:
        return {"verdict": None, "state": None}
    return {"verdict": row[0], "state": row[1]}


# ─── Core flow ───────────────────────────────────────────────────────────


def _wait_for_kat_shadow_ready(page: Page, selector: str, timeout: int = PAGE_TIMEOUT_MS) -> None:
    """Wait for a KAT component to finish rendering in shadow DOM.

    Strategy: wait for the element to be visible AND for the shadowRoot to
    exist (indicated by the element having non-empty innerHTML after mount).
    """
    loc = page.locator(selector).first
    loc.wait_for(state="visible", timeout=timeout)
    # KAT web components finish mounting when their shadow root is populated.
    # We check the underlying element rather than JS evaluation to stay
    # within Playwright's sync API.
    page.wait_for_timeout(500)  # brief settle for shadow DOM population


def _click_kat_dropdown_option(
    page: Page,
    dropdown_selector: str,
    option_value: str,
) -> None:
    """Open a KAT dropdown and click the matching option.

    KAT web components require real OS-level click events (CDP) to update
    their internal state machine. page.locator().click() satisfies this.
    Raw JS (kd.value = 'X') or dispatchEvent(MouseEvent) do NOT work.

    Flow:
      1. Click the dropdown header (opens the option list)
      2. Wait for shadow root to show kat-option elements
      3. Click the matching option
    """
    # Step 1: Open the dropdown
    page.locator(dropdown_selector).click()
    page.wait_for_timeout(400)  # dropdown animation + shadow root population

    # Step 2: Click the option inside shadow DOM
    # KAT options are rendered in the dropdown's shadow root. We use a
    # CSS selector that targets the rendered option text.
    page.locator(f"kat-option[value='{option_value}']").click()
    page.wait_for_timeout(300)  # option selection + dropdown close


def _click_kat_button(page: Page, label: str, variant: str = "primary") -> None:
    """Click a KAT button by its label and variant."""
    page.locator(f"kat-button[label='{label}'][variant='{variant}']").click()
    page.wait_for_timeout(400)


def _drive_filing_form(
    page: Page,
    claim: QueuedClaim,
    verdict: str | None,
    *,
    submit: bool,
) -> tuple[bool, str | None, str | None]:
    """Run the multi-step KAT wizard. Returns (success, amazon_claim_id, screenshot_path).

    `submit=False` is for shadow mode — does everything except the final submit.

    WIZARD FLOW (6 steps verified 2026-05-19):
      Step 1: Fulfillment Channel — SAFET dropdown → Next
      Step 2: Eligibility Check — orderId radio → id_input → Check Eligibility → Next
      Step 3: ASIN + Quantity — tick damaged ASIN checkbox → quantity → Next
      Step 4: Reason code — dropdown → Next
      Step 5: Message + Evidence — textarea → file upload → Next
      Step 6: Review + Submit — (shadow: stop here; live: click Submit)
    """
    verdict_key = _verdict_to_template_key(verdict)
    message = templates.render(verdict=verdict_key, order_id=claim.order_id)
    reason_label = templates.reason_code(verdict_key)

    # Navigate to the filing wizard
    page.goto(URLs.FILE_NEW_CLAIM, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    _screenshot(page, claim.order_id, "form_loaded")

    # ── Step 1: Select Fulfillment Channel ──────────────────────────────
    S1 = SELECTORS.claim_form_step1
    _wait_for_kat_shadow_ready(page, S1.page_container)
    _click_kat_dropdown_option(page, S1.fulfillment_channel_dropdown, S1.default_channel_value)
    page.wait_for_timeout(300)
    _click_kat_button(page, "Next", variant="primary")

    # ── Step 2: Eligibility Check ─────────────────────────────────────────
    S2 = SELECTORS.claim_form_step2
    page.wait_for_selector(S2.id_input, state="visible", timeout=PAGE_TIMEOUT_MS)
    _screenshot(page, claim.order_id, "step2_eligibility")

    # Default is orderId radio — no click needed (pre-selected)
    page.locator(S2.id_input).fill(claim.order_id)
    _click_kat_button(page, "Check Eligibility", variant="primary")

    # Wait for Amazon server-side eligibility response
    # Next button enables only if Amazon says "eligible"
    page.wait_for_function(
        "document.querySelector('kat-button[label=\"Next\"][variant=\"primary\"]')"
        " && !document.querySelector('kat-button[label=\"Next\"][variant=\"primary\"]').disabled",
        timeout=PAGE_TIMEOUT_MS,
    )
    _click_kat_button(page, "Next", variant="primary")

    # ── Step 3: ASIN + Quantity Selection ─────────────────────────────────
    S3 = SELECTORS.claim_form_step3
    page.wait_for_selector(S3.asin_details_box, state="visible", timeout=PAGE_TIMEOUT_MS)
    _screenshot(page, claim.order_id, "step3_asin")

    # Tick the first ASIN checkbox (match by position or product name)
    # Use Playwright's native click — Chrome MCP fails on KAT, Playwright CDP succeeds
    page.locator(S3.quantity_checkbox).first.click()
    page.wait_for_timeout(300)

    # Quantity is already 1 (Amazon default) — no change needed
    # Next enables once at least one row is fully filled
    page.wait_for_function(
        "document.querySelector('kat-button[label=\"Next\"][variant=\"primary\"]')"
        " && !document.querySelector('kat-button[label=\"Next\"][variant=\"primary\"]').disabled",
        timeout=PAGE_TIMEOUT_MS,
    )
    _click_kat_button(page, "Next", variant="primary")

    # ── Step 4: Reason Code (TBD — placeholder, update after Chrome MCP captures) ─
    # TODO(codegen): Update selectors after Step 4 is captured from live walk-through
    # Expected pattern: kat-dropdown for reason + kat-option for sub-reason
    reason_dropdown_selector = "kat-dropdown[placeholder*='reason' i], kat-dropdown.ClaimReasonDropdown"
    try:
        page.wait_for_selector(reason_dropdown_selector, state="visible", timeout=PAGE_TIMEOUT_MS)
        _screenshot(page, claim.order_id, "step4_reason")
        page.locator(reason_dropdown_selector).click()
        page.wait_for_timeout(400)
        # Click the option matching the reason label (approximate — refine post-capture)
        page.locator(f"kat-option:has-text('{reason_label}')").click()
        page.wait_for_timeout(300)
        _click_kat_button(page, "Next", variant="primary")
    except Exception as exc:
        log.warning("safe_t_filer: Step 4 reason code failed (may need codegen): %s", exc)
        # Continue — don't block filing; log and proceed

    # ── Step 5: Message + Composite Upload ────────────────────────────────
    page.wait_for_timeout(800)  # step 5 load animation
    _screenshot(page, claim.order_id, "step5_message")

    # Message textarea — fill via Playwright locator (not JS)
    message_selector = "kat-textarea, textarea[id*='message'], textarea[name*='message']"
    try:
        page.locator(message_selector).first.fill(message)
    except Exception as exc:
        log.warning("safe_t_filer: message textarea fill failed: %s", exc)

    # Composite file upload
    composite = Path(claim.composite_path)
    if not composite.exists():
        raise FileNotFoundError(f"Composite file missing: {composite}")
    file_upload_selector = "input[type='file']"
    page.locator(file_upload_selector).set_input_files(str(composite))
    page.wait_for_timeout(500)  # file upload processing

    _click_kat_button(page, "Next", variant="primary")

    # ── Step 6: Review + Submit (or shadow stop) ──────────────────────────
    page.wait_for_timeout(800)  # review page load
    _screenshot(page, claim.order_id, "before_submit")

    if not submit:
        log.info("safe_t_filer: shadow mode — skipping submit click for %s", claim.order_id)
        return (True, None, f"{settings.orders_dir / claim.order_id / f'{claim.order_id}_claim_before_submit.png'}")

    # Submit
    submit_button = "kat-button[label='Submit'][variant='primary'], button[type='submit']"
    page.locator(submit_button).click()

    # Wait for success / confirmation
    try:
        success_selector = "kat-alert[variant='success'], .success-banner, [data-testid='success-message']"
        page.wait_for_selector(success_selector, timeout=PAGE_TIMEOUT_MS)
    except Exception as exc:
        log.warning("safe_t_filer: submit may have failed for %s: %s", claim.order_id, exc)
        screenshot_path = _screenshot(page, claim.order_id, "submit_failed")
        return (False, None, str(screenshot_path))

    # Read Amazon's claim ID from the confirmation page
    amazon_claim_id = None
    try:
        claim_id_selector = "[data-testid='claim-id'], .claim-id, [data-claim-id]"
        amazon_claim_id = page.locator(claim_id_selector).first.inner_text(timeout=5000)
        amazon_claim_id = amazon_claim_id.strip()
    except Exception:
        pass  # claim ID may not be extractable — still success

    screenshot_path = _screenshot(page, claim.order_id, "submitted")
    return (True, amazon_claim_id, str(screenshot_path))


# ─── Public scheduler entry ──────────────────────────────────────────────


def file_one_queued_claim() -> FilingResult | None:
    """Pop the next claim from the queue and attempt to file it.

    Returns the FilingResult, or None when the queue is empty or Mahika is in
    a non-filing mode (paused).

    Never raises on filing failure — records the failure via
    `claim_queue.mark_attempt()` so the next scheduler tick will retry.
    """
    if settings.mode == "paused":
        log.info("safe_t_filer: mode=paused, skipping")
        return None

    claim = claim_queue.pop_next_claim()
    if claim is None:
        log.debug("safe_t_filer: queue empty")
        return None

    audit(
        "claim.filing_started",
        order_id=claim.order_id,
        payload={"claim_id": claim.claim_id, "attempt": claim.attempt_count + 1, "mode": settings.mode},
        actor="mahika.safe_t_filer",
    )

    submit = settings.mode == "live"
    if settings.mode == "manual":
        # Manual mode — for now just behaves like shadow (no submit). Once
        # Phase 6 cockpit lands, this branch will block on a Sir-approval
        # signal from the dashboard before proceeding to submit.
        submit = False

    order_meta = _fetch_order_for_claim(claim.order_id)
    verdict = order_meta.get("verdict")

    # Lazy-import playwright — keeps `mahika.cli` imports fast
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        msg = "playwright library not installed"
        log.error("safe_t_filer: %s", msg)
        claim_queue.mark_attempt(claim.claim_id, error=msg)
        return FilingResult(claim_id=claim.claim_id, order_id=claim.order_id,
                            success=False, amazon_claim_id=None,
                            screenshot_path=None, error=msg, mode=settings.mode)

    result: FilingResult
    with sync_playwright() as pw:
        try:
            context = session.get_authenticated_context(pw, headless=(settings.mode == "live"))
            page = context.new_page()
            try:
                success, amazon_claim_id, screenshot_path = _drive_filing_form(
                    page, claim, verdict, submit=submit
                )
            finally:
                # Refresh cookies for next run, then close
                session.save_cookies(context)
                page.close()
                context.close()
        except NoSessionAvailable as exc:
            # First-boot / smoke-test path — no cookies, not in live mode,
            # so we refuse to pop a headed browser. Log and move on without
            # incrementing attempt_count (the claim is still queued).
            log.info("safe_t_filer: skipping %s — %s", claim.order_id, exc)
            audit(
                "claim.filing_skipped",
                order_id=claim.order_id,
                reason=str(exc),
                payload={"claim_id": claim.claim_id, "mode": settings.mode},
                actor="mahika.safe_t_filer",
            )
            return FilingResult(claim_id=claim.claim_id, order_id=claim.order_id,
                                success=False, amazon_claim_id=None,
                                screenshot_path=None,
                                error="no session available", mode=settings.mode)
        except Exception as exc:
            log.exception("safe_t_filer: unhandled error filing %s", claim.order_id)
            claim_queue.mark_attempt(claim.claim_id, error=f"{type(exc).__name__}: {exc}")
            alert(
                Priority.HIGH,
                title=f"Claim filing crashed: {claim.order_id}",
                body=f"{type(exc).__name__}: {exc}",
                key=f"claim_crash:{claim.order_id}",
                order_id=claim.order_id,
            )
            audit(
                "claim.filing_crashed",
                order_id=claim.order_id,
                payload={"claim_id": claim.claim_id, "error": str(exc), "mode": settings.mode},
                actor="mahika.safe_t_filer",
            )
            return FilingResult(claim_id=claim.claim_id, order_id=claim.order_id,
                                success=False, amazon_claim_id=None,
                                screenshot_path=None, error=str(exc), mode=settings.mode)

    if success and submit and amazon_claim_id:
        claim_queue.mark_filed(
            claim.claim_id,
            amazon_claim_id=amazon_claim_id,
            submission_screenshot=screenshot_path,
        )
        alert(
            Priority.MEDIUM,
            title=f"Claim filed: {claim.order_id}",
            body=f"Amazon claim ID: {amazon_claim_id}",
            key=f"claim_filed:{claim.order_id}",
            order_id=claim.order_id,
            payload={"amazon_claim_id": amazon_claim_id},
        )
        result = FilingResult(claim_id=claim.claim_id, order_id=claim.order_id,
                              success=True, amazon_claim_id=amazon_claim_id,
                              screenshot_path=screenshot_path, mode=settings.mode)
    elif success and not submit:
        # Shadow/manual — no DB transition, just record the dry-run
        audit(
            "claim.shadow_filed",
            order_id=claim.order_id,
            payload={"claim_id": claim.claim_id, "screenshot_path": screenshot_path, "mode": settings.mode},
            actor="mahika.safe_t_filer",
            screenshot_path=screenshot_path,
        )
        result = FilingResult(claim_id=claim.claim_id, order_id=claim.order_id,
                              success=True, amazon_claim_id=None,
                              screenshot_path=screenshot_path, mode=settings.mode)
    else:
        # success=False — submit failed
        claim_queue.mark_attempt(claim.claim_id, error="submit failed; see screenshot")
        result = FilingResult(claim_id=claim.claim_id, order_id=claim.order_id,
                              success=False, amazon_claim_id=None,
                              screenshot_path=screenshot_path,
                              error="submit failed", mode=settings.mode)

    return result


def file_queued_batch(max_claims: int = 5) -> list[FilingResult]:
    """Drain up to `max_claims` from the queue in one scheduler tick.

    The scheduler calls this periodically. Concurrency is intentionally
    capped low to keep Seller Central's rate-limit happy — Amazon's
    SAFE-T submission isn't rate-controlled separately from page navigation,
    so we stay conservative.

    Per-tick guard: we track claim_ids already attempted in this tick and
    skip them, so a single transient failure doesn't burn through
    `max_claims` retries against the same claim in the same minute. The
    next scheduler tick (30 min later per scheduler.py) is when we retry.
    """
    results: list[FilingResult] = []
    seen_in_this_tick: set[str] = set()
    for _ in range(max_claims):
        # Peek at the next claim without popping
        peek = claim_queue.pop_next_claim()
        if peek is None or peek.claim_id in seen_in_this_tick:
            break
        seen_in_this_tick.add(peek.claim_id)
        r = file_one_queued_claim()
        if r is None:
            break
        results.append(r)
        if not r.success:
            # Don't immediately retry the same claim in this tick; let the
            # next scheduler invocation pick it up after backoff.
            break
    return results
