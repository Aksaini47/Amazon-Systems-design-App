"""English-only SAFE-T claim message templates.

Locked verbatim from `mahika_capture_specs.md §9.4`. The Insights Engine
(Phase 4) can propose template revisions over time, but those proposals must
be approved by Sir before being added here as new versions.

Version semantics:
    v1 — initial baseline (this file). Captured from spec §9.4 exactly.
    v2+ — added via Sir-approved proposals from the Insights Engine.

The chosen template is recorded in `claims.template_version` on enqueue, so
the Insights Engine can compare approval rates per template version (§10.3).

Usage:
    from mahika.playwright.templates import render
    message = render(verdict='different', order_id='407-1234567-1234567')
"""
from __future__ import annotations

from typing import Literal

# Template version → verdict → message text
_TEMPLATES: dict[str, dict[str, str]] = {
    "v1": {
        "different": (
            "Sir/Madam,\n"
            "\n"
            "The buyer has returned a materially different item from what was shipped. "
            "The attached comparison image clearly demonstrates the discrepancy:\n"
            "\n"
            "1. The shipped product (front and back, top row) matches the dispatched packing "
            "video and contains the original FPC code/manufacturing serial.\n"
            "2. The received product (front and back, bottom row) is a different unit with "
            "different identifying marks and FPC code.\n"
            "\n"
            "The composite image attached shows all four angles in a single view with FPC code "
            "comparison clearly highlighting the mismatch.\n"
            "\n"
            "Requesting reimbursement under SAFE-T as this constitutes buyer fraud.\n"
            "\n"
            "Order ID: {order_id}\n"
            "Claim type: Materially different item returned"
        ),
        "damaged": (
            "Sir/Madam,\n"
            "\n"
            "The buyer has returned the item in a damaged condition not consistent with "
            "the dispatched product. The shipped product was in pristine condition as "
            "evidenced by the packing video and front/back photographs (top row of attached "
            "composite).\n"
            "\n"
            "The attached comparison image shows the damage incurred between dispatch and "
            "return in a single 2x2 view.\n"
            "\n"
            "Requesting reimbursement under SAFE-T as the return is not in resellable "
            "condition due to buyer-side damage.\n"
            "\n"
            "Order ID: {order_id}\n"
            "Claim type: Item received damaged in return"
        ),
        # Damaged AND different is rare but real — buyer swapped AND damaged
        "damaged_different": (
            "Sir/Madam,\n"
            "\n"
            "The buyer has returned both a materially different item AND that item is "
            "damaged. The attached comparison image clearly demonstrates the swap (FPC "
            "code/manufacturing serial mismatch between top and bottom row) AND the damage "
            "on the returned unit.\n"
            "\n"
            "Both issues are visible in a single 2x2 view in the attached composite.\n"
            "\n"
            "Requesting reimbursement under SAFE-T as this constitutes buyer fraud + "
            "non-resellable condition.\n"
            "\n"
            "Order ID: {order_id}\n"
            "Claim type: Materially different item returned AND damaged"
        ),
    },
}

DEFAULT_VERSION = "v1"

VerdictKey = Literal["different", "damaged", "damaged_different"]


class UnknownTemplate(ValueError):
    """Requested template version + verdict combination doesn't exist."""


def render(
    *,
    verdict: VerdictKey,
    order_id: str,
    version: str = DEFAULT_VERSION,
) -> str:
    """Render the claim message body. Returns the final string ready to paste.

    Raises UnknownTemplate when version or verdict is not in the catalogue.
    """
    if version not in _TEMPLATES:
        raise UnknownTemplate(f"Template version {version!r} not registered")
    templates = _TEMPLATES[version]
    if verdict not in templates:
        raise UnknownTemplate(
            f"No template for verdict={verdict!r} in version {version!r}"
        )
    return templates[verdict].format(order_id=order_id)


def available_versions() -> list[str]:
    return sorted(_TEMPLATES.keys())


def reason_code(verdict: VerdictKey) -> str:
    """Map an internal verdict enum to the SAFE-T form's reason-code label.

    These are placeholders — Seller Central's actual reason-code dropdown labels
    will be filled in during `playwright codegen` capture. Sir confirms during
    the first manual run.
    """
    # TODO(phase5): Replace with the actual Seller Central reason-code label
    #               text. Capture via codegen during the first real filing.
    return {
        "different": "Materially different item returned",
        "damaged": "Item received damaged",
        "damaged_different": "Materially different item returned",
    }[verdict]
