"""Phase 6 — Mahika Cockpit (FastAPI dashboard).

Solo-operator triage UI for Sir. Runs on the active runner at
http://localhost:{MAHIKA_COCKPIT_PORT}/ by default (8765).

Single-user token auth — Sir sets MAHIKA_COCKPIT_TOKEN in .env, pastes it on
the login page, and the cockpit issues a signed session cookie. No remote
access surface, no role hierarchy yet (parked for Phase 7+ when the
helper-role flow exists).

Entry point:
    python -m mahika.cli cockpit       # blocks until Ctrl-C

Pages:
    /              — Dashboard: status snapshot + urgency-coloured worklist
    /orders        — Orders list with state filters
    /claims        — Claim queue browser
    /audit         — Audit log tail with type/date filters
    /insights      — Insights review + suggestion approve/reject
    /login         — Token login form
    /logout        — Clears session

Per `mahika.md §9 forbidden behaviors`: the cockpit NEVER modifies orders
or claims directly. It surfaces state + lets Sir approve Insights
suggestions (status='pending' → 'approved'/'rejected'). All other state
changes go through the scheduler tasks.
"""
from __future__ import annotations
