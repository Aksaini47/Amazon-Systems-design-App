"""Short Help Hub case copy — plain seller tone (Amazon examples style)."""
from __future__ import annotations

import os
from dataclasses import dataclass

MAX_HELP_LINES = 5
MAX_STEPS_LINES = 3
MAX_SUBJECT_WORDS = 5

DEVELOPER_ID = "A8C5XXFI7YLLM"
APP_ID = "amzn1.sp.solution.8fd7d23a-72d4-4152-a8aa-40654de8c215"
MARKETPLACE_ID = "A21TJRUUN4KGV"


@dataclass(frozen=True)
class CaseTextVariant:
    """One preset for Help Hub IP2 + subject."""

    variant_id: int
    help_with: str
    steps_taken: str
    subject: str


def _trim_lines(text: str, max_lines: int) -> str:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return "\n".join(lines[:max_lines])


def _trim_subject(text: str, max_words: int = MAX_SUBJECT_WORDS) -> str:
    words = text.strip().split()
    return " ".join(words[:max_words])


# Style: short sentences, label: value, no jargon — like Help Hub examples.

_V1_HELP = """\
I need help turning on live seller tools for my own shop only.
Seller: Badeja Enterprises, India.
App name: Mahika V1. I use it only for our store, not for other sellers.
Test setup works. Live setup is blocked until my developer profile is approved.
Developer id: A8C5XXFI7YLLM. App id: amzn1.sp.solution.8fd7d23a-72d4-4152-a8aa-40654de8c215."""

_V1_STEPS = (
    "I built the test app, finished partner signup step 2, "
    "and live registration still will not open."
)

# Browser retry trims (plain tone, steps = one line each)
RETRY_HELP: tuple[str, ...] = (
    _V1_HELP,
    """\
I need live seller tools for my own shop only.
Seller: Badeja Enterprises, India.
App: Mahika V1, store use only.
Test works, live blocked pending profile approval.
Developer id: A8C5XXFI7YLLM. App id: amzn1.sp.solution.8fd7d23a-72d4-4152-a8aa-40654de8c215.""",
    """\
Need live seller tools for my India shop.
Seller: Badeja Enterprises. App: Mahika V1.
Test ok, live blocked. Developer id: A8C5XXFI7YLLM.""",
    "Need live tools for Badeja Enterprises India, app Mahika V1, test ok live blocked.",
)

RETRY_STEPS: tuple[str, ...] = (
    _V1_STEPS,
    "Built test app, partner step 2 done, live app still blocked.",
    "Test app and partner step 2 done, live still blocked.",
    "Test app ok, live app still blocked.",
)

_V1_SUBJECT = "need live seller tools"

_V2_HELP = """\
I cannot create a live version of my seller tools app.
Shop: Badeja Enterprises on Amazon.in.
App: Mahika V1, private use for refunds and order checks on our account.
Sandbox side is fine. Live side says profile approval is still needed.
Developer id: A8C5XXFI7YLLM. App id: amzn1.sp.solution.8fd7d23a-72d4-4152-a8aa-40654de8c215."""

_V2_STEPS = """\
I registered the test app and ran a sample order pull.
I completed partner portal step 2.
The live app option stays greyed out."""

_V2_SUBJECT = "live app not opening"

_V3_HELP = """\
Please review my developer profile so I can use live seller tools.
I am an existing seller and need this for my own account only.
Brand / shop: Badeja Enterprises, India. App: Mahika V1.
Test tools work. Live tools are still blocked.
Developer id: A8C5XXFI7YLLM. App id: amzn1.sp.solution.8fd7d23a-72d4-4152-a8aa-40654de8c215."""

_V3_STEPS = """\
I set up the test app and saved login for it.
I walked through partner signup step 2.
I am waiting on approval to add the live app."""

_V3_SUBJECT = "developer profile approval"

_V4_HELP = """\
I need approval to run live seller tools on my India account.
Seller: Badeja Enterprises.
Use: track our own orders and refund cases, not a public app.
Sandbox Mahika V1 is working. Production Mahika V1 will not register yet.
Developer id: A8C5XXFI7YLLM. App id: amzn1.sp.solution.8fd7d23a-72d4-4152-a8aa-40654de8c215."""

_V4_STEPS = """\
Built and tested Mahika V1 in sandbox.
Finished partner portal step 2.
Still cannot open production registration."""

_V4_SUBJECT = "mahika live access india"

_V5_HELP = """\
I am asking for help with live seller api access for one private app.
Account: Badeja Enterprises, India marketplace.
App: Mahika V1, self use only.
Sandbox is approved in practice. Live registration asks me to wait on profile review.
Developer id: A8C5XXFI7YLLM. App id: amzn1.sp.solution.8fd7d23a-72d4-4152-a8aa-40654de8c215."""

_V5_STEPS = """\
Created sandbox Mahika V1 and tested order download.
Completed seller partner step 2 onboarding.
Production app creation still blocked."""

_V5_SUBJECT = "help with live app"


def _pack(vid: int, help: str, steps: str, subject: str) -> CaseTextVariant:
    return CaseTextVariant(
        variant_id=vid,
        help_with=_trim_lines(help, MAX_HELP_LINES),
        steps_taken=_trim_lines(steps, MAX_STEPS_LINES),
        subject=_trim_subject(subject),
    )


VARIANTS: dict[int, CaseTextVariant] = {
    1: _pack(1, _V1_HELP, _trim_lines(_V1_STEPS, MAX_STEPS_LINES), _V1_SUBJECT),
    2: _pack(2, _V2_HELP, _V2_STEPS, _V2_SUBJECT),
    3: _pack(3, _V3_HELP, _V3_STEPS, _V3_SUBJECT),
    4: _pack(4, _V4_HELP, _V4_STEPS, _V4_SUBJECT),
    5: _pack(5, _V5_HELP, _V5_STEPS, _V5_SUBJECT),
}


def get_case_text_variant(variant: int | None = None) -> CaseTextVariant:
    if variant is None:
        raw = os.getenv("MAHIKA_CASE_TEXT_VARIANT", "1").strip()
        try:
            variant = int(raw)
        except ValueError:
            variant = 1
    return VARIANTS.get(variant, VARIANTS[1])
