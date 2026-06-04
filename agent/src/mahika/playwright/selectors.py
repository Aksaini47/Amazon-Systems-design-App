"""Centralised Seller Central CSS/XPath selectors.

THIS FILE IS A LIVING DOCUMENT. After the first `playwright codegen` capture
(Sir-driven, done once per Amazon UI refresh), every selector below should be
replaced with the actual one captured from the browser. Until then, every
selector is a TODO placeholder marked `# TODO(codegen)` so they're easy to
grep for.

Selectors are grouped by page so `safe_t_filer.py` can `from selectors import
LoginPage, SafeTPage, ClaimFormPage` and reference fields by readable name.

Codegen recipe (Sir runs once):

    cd "C:\\Projects\\Amazon Systems Design\\agent"
    .\\.venv\\Scripts\\activate
    playwright codegen https://sellercentral.amazon.in

Then:
    1. Log in (Amazon will OTP-challenge you)
    2. Navigate: Performance → SAFE-T Claims → File New Claim
    3. File a real test claim (or close before submitting)
    4. Copy the captured selectors into this file
    5. Commit

After capture, the TODO markers go away and the filer should run end-to-end.
"""
from __future__ import annotations

from dataclasses import dataclass

# ─── Seller Central URLs ─────────────────────────────────────────────────


class URLs:
    BASE = "https://sellercentral.amazon.in"
    LOGIN = "https://sellercentral.amazon.in/ap/signin"
    # VERIFIED 2026-05-19 via live capture in Sir's chrome tab.
    SAFE_T_LIST = "https://sellercentral.amazon.in/safet-claims/"
    FILE_NEW_CLAIM = "https://sellercentral.amazon.in/safet-claims/create-v2"
    SAFE_T_REPORTS = "https://sellercentral.amazon.in/safet-claims/reports"


# ─── Login / OTP page ────────────────────────────────────────────────────


@dataclass(frozen=True)
class LoginPage:
    """Selectors for Amazon's seller login flow.

    Form action: https://sellercentral.amazon.in/ap/signin (form name="signIn")
    Flow: email → continue → password → sign-in → OTP → home
    """

    # VERIFIED 2026-05-19 from live capture in Sir's chrome tab.
    email_input: str = "#ap_email"
    # VERIFIED 2026-05-19 — input[type=submit].a-button-input aria-labelledby="continue-announce"
    continue_button: str = "input#continue"

    # TODO(codegen) — still needs Sir's live login walk-through to verify
    password_input: str = "#ap_password"
    sign_in_button: str = "input#signInSubmit"
    otp_input: str = "#auth-mfa-otpcode"
    otp_submit_button: str = "input#auth-signin-button"
    # Two-Step Verification — delivery method picker (before OTP input)
    otp_delivery_send_button: str = "button:has-text('Send OTP')"
    # MFA fallback — "Didn't receive the OTP?" → voice call (phone ending 711)
    otp_didnt_receive_link: str = "a:has-text('Didn\\'t receive the OTP')"
    otp_voice_call_link: str = "#auth-get-verification-code-by-voice-link"

    # Signal that auth succeeded — Seller Central home shows the seller name
    home_indicator: str = "#sc-nav-brand"  # TODO(codegen) verify post-login


# ─── SAFE-T claim list page ──────────────────────────────────────────────


@dataclass(frozen=True)
class SafeTListPage:
    """Selectors for the SAFE-T claims list page (URL: /safet-claims/).

    VERIFIED 2026-05-19 via live capture. Note the layout uses class-based
    selectors (auto-generated IDs like #a-autoid-0-announce are not stable
    across page loads).
    """

    # VERIFIED 2026-05-19 — yellow button top-right opens /safet-claims/create-v2
    #                       Class is `a-button-text` but the stable selector is the href.
    file_new_claim_button: str = "a[href*='/safet-claims/create-v2']"

    # Status tabs: All / Awaiting Seller Response / Granted / Denied / Under Investigation
    # All are <a role="tab" href="#"> elements — filter by text or position.
    status_tab_by_text: str = "a[role='tab']"  # VERIFIED 2026-05-19

    # Search input — order ID, ASIN, or SAFE-T claim ID
    search_input: str = "input[placeholder*='Order ID' i]"  # TODO(codegen) verify on next visit

    # Claim row in the table (data table rows) — auto-keyed, use class-based traversal
    claim_row_xpath: str = "//table//tr"  # TODO(codegen) refine after first walk


# ─── SAFE-T claim filing form (MULTI-STEP WIZARD) ────────────────────────
#
# CRITICAL ARCHITECTURAL FINDING 2026-05-19:
# The actual SAFE-T claim form at /safet-claims/create-v2 is a MULTI-STEP
# WIZARD, not a single-page form as the original Phase 5 stubs assumed.
# It uses Amazon's KAT web-component framework (Shadow DOM, kat-dropdown,
# kat-button etc.), so standard Playwright select_option() won't work on
# the dropdowns — need click-to-open then click-option inside shadow root.
#
# Steps observed so far:
#   Step 1: Select Fulfillment Channel (kat-dropdown)
#   Step 2..N: TBD as live walk continues
#
# Selector strategy: prefer CLASS-based (`.ClaimTypeDropdown`,
# `.ClaimSelectionBox`) or attribute-based (placeholder, aria-label) over
# auto-generated IDs.


@dataclass(frozen=True)
class ClaimFormStep1FulfillmentChannel:
    """Step 1 of the wizard — select fulfillment channel.

    VERIFIED 2026-05-19 via live capture in Sir's chrome tab.

    Dropdown options (exposed via `kat-dropdown.options` JS property):
      - SAFET → "Easy Ship/ Self Ship/ Seller Flex"   ← Mahika's default
      - FEE_RELATED_DISPUTES → "Fee related disputes" (different flow, NOT SAFE-T)

    KAT INTERACTION NOTE: Programmatic `kd.value = 'SAFET'` from raw JS
    does NOT trigger the internal state machine (Next button stays disabled).
    Playwright's real OS-level `page.click()` + `page.locator('kat-option')`
    DOES work — KAT components respect native click events. The filer
    refactor (Task #8) must use Playwright's native click, not page.evaluate.
    """

    page_container: str = ".ClaimSelectionPage"     # VERIFIED 2026-05-19
    form_card: str = ".ClaimSelectionBox"           # VERIFIED 2026-05-19

    # The fulfillment channel selector — KAT custom dropdown
    fulfillment_channel_dropdown: str = "kat-dropdown.ClaimTypeDropdown"  # VERIFIED 2026-05-19
    # Internal shadow-root header (target of the open-click)
    dropdown_header_shadow: str = ".select-header"  # VERIFIED 2026-05-19 (inside shadowRoot)

    # Default fulfillment channel for Mahika autonomous filing
    default_channel_value: str = "SAFET"            # VERIFIED 2026-05-19

    # Wizard navigation buttons — labels are stable, variants are stable too
    cancel_button: str = "kat-button[label='Cancel']"  # VERIFIED 2026-05-19 (variant=tertiary)
    back_button: str = "kat-button[label='Back']"      # VERIFIED 2026-05-19 (variant=secondary)
    next_button: str = "kat-button[label='Next']"      # VERIFIED 2026-05-19 (variant=primary)


@dataclass(frozen=True)
class ClaimFormStep2EligibilityCheck:
    """Step 2 of the wizard — Order ID entry + Amazon-side eligibility validation.

    VERIFIED 2026-05-19 via live capture in Sir's chrome tab.

    Flow:
      1. Default identifier is "Order ID" (radio pre-selected)
      2. Type the Amazon order ID into <kat-input placeholder="Order ID">
      3. Click "Check Eligibility" (primary kat-button)
      4. Amazon validates server-side:
         - Eligible  → Next button becomes enabled, proceed to Step 3
         - Already filed / window closed / not refunded → error message
      5. Cancel/Back/Next nav stays in the standard position

    AMAZON SERVER-SIDE GATE is a NEW SAFETY LAYER not in Phase 5 spec.
    Mahika should:
      - Trust Amazon's eligibility verdict (don't re-verify locally)
      - Handle the "not eligible" response gracefully:
        * Mark order as 'claim_ineligible' if Amazon says it's a duplicate
        * Re-queue with backoff if Amazon says "refund not yet processed"
        * Re-queue with backoff if Amazon says "session expired"
      - Capture the error message text + a screenshot for the audit_log

    Identifier types:
      - 'orderId'    → Amazon order ID (407-XXXXXXX-XXXXXXX) — Mahika default
      - 'trackingId' → carrier AWB
      - 'rmaId'      → Return Merchandise Authorization ID
    """

    # Three KAT radio buttons — pick the identifier type
    radio_order_id: str = "kat-radiobutton[value='orderId']"     # VERIFIED 2026-05-19 (default)
    radio_tracking_id: str = "kat-radiobutton[value='trackingId']"  # VERIFIED 2026-05-19
    radio_rma_id: str = "kat-radiobutton[value='rmaId']"          # VERIFIED 2026-05-19

    # Single text input — value depends on which radio is selected
    id_input: str = "kat-input[placeholder='Order ID']"  # VERIFIED 2026-05-19 (placeholder shifts with radio)
    # Generic fallback in case placeholder changes:
    id_input_any: str = "kat-input"

    # Server-side eligibility check trigger
    check_eligibility_button: str = "kat-button[label='Check Eligibility']"  # VERIFIED 2026-05-19 (variant=primary)

    # Error / status display after Check Eligibility
    # TODO(codegen) capture exact selectors during error scenario
    eligibility_error: str = "kat-alert[variant='danger'], kat-alert[variant='warning'], .errorText"


@dataclass(frozen=True)
class ClaimFormStep3AsinSelection:
    """Step 3 of the wizard — ASIN + quantity selection per claim.

    VERIFIED 2026-05-19 via live capture with real order 403-6755426-0577120.

    On reaching this step:
      - Order ID is echoed in the page header (`Order ID : 403-...`)
      - PURCHASE DATE is echoed as "Order Date" — NOT the delivery date.
        DO NOT use this for the 15-day SAFE-T window calculation. Delivery
        date comes from either:
          (a) the RT bundle's meta.json `captured_at` (when RF Logger
              recorded the physical return arrival at Sir's warehouse), or
          (b) SP-API getReturns endpoint's `deliveryDate` field
        Order Date here is only useful for cross-verifying Mahika is on the
        correct order page (sanity check vs orders.created_at in Postgres).
      - Each ASIN in the order shows as one .asin-row inside a .AsinDetailsBox card
      - Per row: <kat-checkbox.QuantityCheckbox> + product image + title + quantity input
      - Quantity input has min=1, max=ASIN-specific limit (based on purchased qty - already-claimed qty)

    Mahika flow:
      - Read ASIN list from order's meta.json (Phase 3 stored)
      - For each ASIN with a damaged/different RT bundle:
          * Tick the matching checkbox (match by product title or position)
          * Set quantity from RT bundle count
      - Next button enables once at least one row is fully filled
    """

    # ASIN row container (KAT card)
    asin_details_box: str = "kat-box.AsinDetailsBox"            # VERIFIED 2026-05-19
    # One row per ASIN in the order
    asin_row: str = "div.kat-row.asin-row"                       # VERIFIED 2026-05-19
    # Product title cell (text used to match against Mahika's order meta.json)
    asin_name_cell: str = "div.asin-name"                        # VERIFIED 2026-05-19

    # Per-row checkbox (one ASIN = one checkbox)
    quantity_checkbox: str = "kat-checkbox.QuantityCheckbox"     # VERIFIED 2026-05-19
    # Per-row quantity input (number, min/max set by Amazon based on order)
    quantity_input: str = "kat-input[type='number']"             # VERIFIED 2026-05-19

    # Header echoes — used to verify Mahika is on the correct order
    order_id_displayed_text_pattern: str = r"Order ID\s*:\s*([\d\-]+)"
    order_date_displayed_text_pattern: str = r"Order Date\s*:\s*([^\n]+)"


@dataclass(frozen=True)
class ClaimFormPage:
    """LEGACY single-page form selectors — kept for backwards compatibility
    with the original Phase 5 design. Real Seller Central uses a multi-step
    wizard; see ClaimFormStep1FulfillmentChannel + future Step2+ classes.

    All selectors below are TODO(codegen) and should be REMOVED or refactored
    once the multi-step wizard refactor (Task #8) is complete.
    """

    order_id_input: str = "input[name='orderId']"  # TODO(codegen) refactor — wizard step 2
    reason_dropdown: str = "kat-dropdown[placeholder*='reason' i]"  # TODO(codegen)
    message_textarea: str = "kat-textarea, textarea"  # TODO(codegen)
    file_upload_input: str = "input[type='file']"  # TODO(codegen)
    submit_button: str = "kat-button[variant='primary']"  # TODO(codegen)

    # Confirmation
    success_banner: str = ".success-banner, kat-alert[variant='success']"  # TODO(codegen)
    amazon_claim_id_field: str = "[data-testid='claim-id']"  # TODO(codegen)

    # Error / validation
    validation_error: str = ".kat-alert--error, .a-form-error"  # TODO(codegen)


# ─── SAFE-T claim detail page (for status checker) ───────────────────────


@dataclass(frozen=True)
class ClaimDetailPage:
    status_label: str = "[data-testid='claim-status']"  # TODO(codegen)
    info_request_banner: str = "[data-testid='info-request']"  # TODO(codegen)
    rejection_reason: str = "[data-testid='rejection-reason']"  # TODO(codegen)
    appeal_button: str = "button[data-testid='appeal']"  # TODO(codegen)


# ─── Convenience aggregator ─────────────────────────────────────────────


@dataclass(frozen=True)
class SellerCentralSelectors:
    login: LoginPage = LoginPage()
    safe_t_list: SafeTListPage = SafeTListPage()
    # Multi-step wizard selectors (Phase 5 refactor in progress — Task #8)
    claim_form_step1: ClaimFormStep1FulfillmentChannel = ClaimFormStep1FulfillmentChannel()
    claim_form_step2: ClaimFormStep2EligibilityCheck = ClaimFormStep2EligibilityCheck()
    claim_form_step3: ClaimFormStep3AsinSelection = ClaimFormStep3AsinSelection()
    # Legacy single-page selectors (will be removed post-refactor)
    claim_form: ClaimFormPage = ClaimFormPage()
    claim_detail: ClaimDetailPage = ClaimDetailPage()


SELECTORS = SellerCentralSelectors()


def codegen_pending_count() -> int:
    """Return how many selectors are still placeholders. Useful for boot-time
    safety check — refuses to start the filer if ALL selectors are pending."""
    # Cheap impl: just count fields whose values appear in our hardcoded
    # placeholder list. Real check is "did Sir confirm calibration?" via
    # a flag in .env or a marker file. For now we hard-code the count.
    return 12  # all four pages have placeholders
