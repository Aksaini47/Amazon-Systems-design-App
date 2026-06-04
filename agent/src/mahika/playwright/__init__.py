"""Phase 5 — Playwright browser automation for Seller Central SAFE-T flow.

Public entry points:

    from mahika.playwright.safe_t_filer import file_one_queued_claim
    from mahika.playwright.status_checker import check_filed_claims

Sub-modules:
    selectors      — centralized CSS / XPath selectors for Seller Central pages
    templates      — English-only claim message templates (spec §9.4)
    session        — cookie load/save + 2FA OTP coordinator
    safe_t_filer   — the actual claim-filing flow (the main deliverable)
    status_checker — polls filed claims through their state transitions

Per `mahika.md` §9 forbidden behaviors, this layer NEVER files a claim until:
    1. The claim row exists in `claims` table with composite_path present
    2. The composite file exists on disk
    3. The order is in `claim_queued` state (not already filed)
    4. The active runner heartbeat is current
    5. The Seller Central session is valid (or refreshed via OTP flow)
"""
from __future__ import annotations
