"""Mahika command-line entry points.

Invocation:
    python -m mahika start              — boot the scheduler daemon
    python -m mahika start --once       — run every task once + exit
    python -m mahika status             — quick operational snapshot
    python -m mahika audit-tail [N]     — print the last N audit_log rows
    python -m mahika queue              — show the current claim queue
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from mahika.config import settings
from mahika.db.connection import get_session
from mahika.services import claim_queue, scheduler
from mahika.services import pipeline as evidence_pipeline


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ─── Sub-commands ────────────────────────────────────────────────────────


def cmd_start(args: argparse.Namespace) -> int:
    if args.once:
        results = scheduler.run_once()
        print(json.dumps(results, indent=2, default=str))
        return 0
    return scheduler.run_forever()


def cmd_status(_: argparse.Namespace) -> int:
    print("=== Mahika status ===")
    print(f"Runner ID:    {settings.runner_id}")
    print(f"Mode:         {settings.mode}")
    print(f"DB host:      {settings.db_host}")
    print(f"Storage root: {settings.storage_root}")
    from mahika.sp_api.client import check_status

    sp = check_status()
    mode = "sandbox" if sp.sandbox_mode else "production"
    print(f"SP-API:       {mode} | configured={sp.configured} | reachable={sp.api_reachable}")
    if sp.configured:
        print(f"SP-API detail: {sp.detail}")
    print(f"Telegram:     {'configured' if settings.telegram_configured else 'NOT configured'}")
    print()
    with get_session() as s:
        order_states = s.execute(
            text("SELECT state, count(*) FROM orders GROUP BY state ORDER BY state")
        ).all()
        queued = s.execute(text("SELECT count(*) FROM claims WHERE filed_at IS NULL")).scalar()
        last_heartbeat = s.execute(
            text(
                "SELECT runner_id, last_seen_at FROM runner_heartbeat "
                "ORDER BY last_seen_at DESC LIMIT 1"
            )
        ).first()
        recent_audit = s.execute(
            text(
                "SELECT event_at, actor, event_type FROM audit_log "
                "ORDER BY event_at DESC LIMIT 5"
            )
        ).all()
    print("Orders by state:")
    if not order_states:
        print("  (none yet)")
    for state, n in order_states:
        print(f"  {state:24s} {n}")
    print(f"\nClaim queue depth: {queued or 0}")
    if last_heartbeat:
        print(f"Last heartbeat:    {last_heartbeat[0]} at {last_heartbeat[1].isoformat()}")
    else:
        print("Last heartbeat:    (none recorded yet)")
    print("\nRecent audit log:")
    if not recent_audit:
        print("  (empty)")
    for event_at, actor, event_type in recent_audit:
        ts = event_at.isoformat() if isinstance(event_at, datetime) else event_at
        print(f"  {ts}  {actor:30s} {event_type}")
    return 0


def cmd_audit_tail(args: argparse.Namespace) -> int:
    n = args.count
    with get_session() as s:
        rows = s.execute(
            text(
                "SELECT event_at, actor, event_type, order_id, reason "
                "FROM audit_log ORDER BY event_at DESC LIMIT :n"
            ),
            {"n": n},
        ).all()
    for event_at, actor, event_type, order_id, reason in rows:
        ts = event_at.isoformat() if isinstance(event_at, datetime) else event_at
        oid = f" [{order_id}]" if order_id else ""
        rsn = f"  — {reason}" if reason else ""
        print(f"{ts}  {actor:30s} {event_type:30s}{oid}{rsn}")
    return 0


def cmd_queue(_: argparse.Namespace) -> int:
    depth = claim_queue.queue_depth()
    pending = claim_queue.pending_refund_count()
    print(f"Claims awaiting filing:  {depth}")
    print(f"Orders pending refund:   {pending}")
    nxt = claim_queue.pop_next_claim()
    if nxt is not None:
        print("\nNext to file:")
        print(f"  Claim ID:        {nxt.claim_id}")
        print(f"  Order ID:        {nxt.order_id}")
        print(f"  Composite:       {nxt.composite_path}")
        print(f"  Template:        {nxt.template_version}")
        print(f"  Queued at:       {nxt.queued_at}")
        print(f"  Attempt count:   {nxt.attempt_count}")
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    """Self-diagnostic — verify all wiring before Sir boots the daemon.

    Checks (in order, never aborts on first failure):
        1. .env loaded, all required vars present
        2. Python deps importable
        3. Postgres reachable + schema present
        4. NVMe folder structure
        5. Tesseract binary available
        6. Playwright Chromium installed
        7. Cockpit auth token configured
        8. SP-API credentials (sandbox or production)
        9. Telegram bot reachable (if configured)
        10. Heartbeat round-trip
    """
    failures = 0
    total = 0

    def check(label: str, ok: bool, hint: str | None = None) -> None:
        nonlocal failures, total
        total += 1
        marker = "[ OK ]" if ok else "[FAIL]"
        print(f"  {marker} {label}")
        if not ok:
            failures += 1
            if hint:
                print(f"         -> {hint}")

    print("=== Mahika doctor ===")
    print(f"  Runner ID:    {settings.runner_id}")
    print(f"  Mode:         {settings.mode}")
    print()

    # 1. .env loaded
    print("[1/10] Config + .env")
    check(".env file exists", Path(".env").exists(),
          hint="cp .env.example .env, then fill values")
    check("MAHIKA_DB_HOST set", bool(settings.db_password) and bool(settings.db_host)
          and settings.db_host != "oracle-vm-public-ip",
          hint="Run scripts/setup_oracle_vm.md to get the VM IP, then put it in .env")
    check("MAHIKA_DB_PASSWORD set", bool(settings.db_password))
    check("MAHIKA_STORAGE_ROOT set", bool(settings.storage_root))
    print()

    # 2. Python deps
    print("[2/10] Python deps")
    for module_name in ("psycopg", "sqlalchemy", "pydantic_settings", "PIL",
                        "apscheduler", "telegram", "fastapi", "uvicorn", "jinja2",
                        "playwright", "httpx", "tenacity"):
        try:
            __import__(module_name)
            check(f"import {module_name}", True)
        except ImportError as exc:
            check(f"import {module_name}", False, hint=f"pip install missing — {exc}")
    print()

    # 3. Postgres
    print("[3/10] Postgres connectivity + schema")
    if not settings.db_password:
        check("DB configured (MAHIKA_DB_PASSWORD set)", False,
              hint="fill MAHIKA_DB_* in root .env, run sync_env.ps1, then migrate")
    else:
        try:
            from sqlalchemy import text as _text

            from mahika.db.connection import db_engine
            with db_engine.connect() as conn:
                version = conn.execute(_text("SELECT version()")).scalar()
            check(f"DB reachable ({(version or '')[:60]}...)", True)
            with db_engine.connect() as conn:
                tables = {row[0] for row in conn.execute(_text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )).all()}
            for required in ("orders", "claims", "audit_log", "evidence",
                             "refund_events", "returns", "insights", "suggestions",
                             "runner_heartbeat"):
                check(f"table {required} exists", required in tables,
                      hint="run: python -m mahika.db.migrate")
        except Exception as exc:
            check("DB reachable", False, hint=f"{type(exc).__name__}: {exc}")
    print()

    # 4. NVMe folders
    print("[4/10] NVMe folder structure")
    for folder in (settings.orders_dir, settings.sync_inbox_dir,
                   settings.processed_dir, settings.backups_dir, settings.logs_dir):
        check(f"{folder}", folder.exists(),
              hint="run: python -m scripts.setup_nvme_folders")
    print()

    # 5. Evidence pipeline (human verdict — Tesseract optional)
    print("[5/10] Evidence pipeline")
    orders_dir = settings.orders_dir
    has_orders = orders_dir.exists() and any(orders_dir.iterdir()) if orders_dir.exists() else False
    check("orders/ folder reachable", orders_dir.exists(),
          hint="run: python -m scripts.setup_nvme_folders")
    check("sample order data present", has_orders,
          hint="sync camera app or copy test orders into orders/")
    print()

    # 6. Playwright Chromium
    print("[6/10] Playwright Chromium")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            v = browser.version
            browser.close()
        check(f"Chromium launches ({v})", True)
    except Exception:
        check("Chromium launches", False,
              hint="python -m playwright install chromium")
    print()

    # 7. Cockpit token
    print("[7/10] Cockpit auth")
    check("MAHIKA_COCKPIT_TOKEN set", bool(settings.cockpit_token),
          hint='python -c "import secrets; print(secrets.token_urlsafe(32))" then paste into .env')
    check("MAHIKA_COCKPIT_HOST is 127.0.0.1",
          settings.cockpit_host in ("127.0.0.1", "localhost", "::1"))
    print()

    # 8. SP-API
    print("[8/10] SP-API credentials")
    check("LWA Client ID set", bool(settings.sp_api_lwa_client_id))
    check("LWA Client Secret set", bool(settings.sp_api_lwa_client_secret))
    check("Refresh token set", bool(settings.sp_api_refresh_token),
          hint="see scripts/sp_api_registration_checklist.md")
    check("sp_api_configured == True", settings.sp_api_configured)
    if settings.sp_api_configured:
        from mahika.sp_api.client import check_status

        sp = check_status()
        mode = "sandbox" if sp.sandbox_mode else "production"
        check(f"SP-API mode = {mode}", True)
        check("LWA token exchange", sp.lwa_ok)
        check(
            f"SP-API reachable ({sp.detail})",
            sp.api_reachable,
            hint=(
                "sandbox: keep MAHIKA_SP_API_SANDBOX=true; "
                "production: profile approval + Authorize app + SANDBOX=false"
            ),
        )
    print()

    # 9. Telegram
    print("[9/10] Telegram bot (optional)")
    if settings.telegram_configured:
        check("Token + chat_id set", True)
    else:
        check("Telegram NOT configured", True,
              hint="see scripts/telegram_setup.md then mahika.cli telegram-test")
    print()

    # 10. Heartbeat
    print("[10/10] Heartbeat round-trip")
    if not settings.db_password:
        check("heartbeat (needs DB)", False,
              hint="configure MAHIKA_DB_* first, then re-run doctor")
    else:
        try:
            from mahika.runner.heartbeat import am_i_active, claim_active
            claimed = claim_active(notes="doctor self-test")
            active = am_i_active()
            check(f"claim_active() returned {claimed}", bool(claimed))
            check(f"am_i_active() returned {active}", bool(active))
        except Exception as exc:
            check("heartbeat", False, hint=f"{type(exc).__name__}: {exc}")
    print()

    # ─── Summary ─────────────────────────────────────────────────────
    passed = total - failures
    print(f"=== {passed}/{total} checks passed ===")
    if failures == 0:
        print("OK: Mahika is wired up correctly — ready to launch.")
        print("  Boot scheduler: python -m mahika.cli start")
        print("  Boot cockpit:   python -m mahika.cli cockpit")
    else:
        print(f"FAIL: {failures} check(s) failed — see hints above + docs/RUNBOOK.md")
    return 0 if failures == 0 else 1


def cmd_mode(args: argparse.Namespace) -> int:
    """Update MAHIKA_MODE in .env + audit the change.

    Sir must restart the scheduler for the change to take effect
    (settings are loaded once at process start).
    """
    new_mode = args.new_mode
    if new_mode not in ("shadow", "manual", "live", "paused"):
        print(f"ERROR: mode must be one of: shadow, manual, live, paused (got {new_mode!r})",
              file=sys.stderr)
        return 1

    env_path = Path(".env")
    if not env_path.exists():
        print("ERROR: .env not found in current directory", file=sys.stderr)
        return 1

    lines = env_path.read_text(encoding="utf-8").splitlines()
    found = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("MAHIKA_MODE=") or stripped.startswith("# MAHIKA_MODE="):
            lines[i] = f"MAHIKA_MODE={new_mode}"
            found = True
            break
    if not found:
        lines.append(f"MAHIKA_MODE={new_mode}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Audit the change (best-effort — don't fail the CLI if audit fails)
    try:
        from mahika.utils.audit import audit
        audit(
            "mode.changed",
            reason=f"Sir flipped MAHIKA_MODE: {settings.mode} -> {new_mode}",
            payload={"from": settings.mode, "to": new_mode},
            actor="sir.cli",
            human_intervention=True,
        )
    except Exception as exc:
        print(f"WARN: mode set in .env but audit failed: {exc}", file=sys.stderr)

    print(f"MAHIKA_MODE set to {new_mode!r} in .env")
    print("  RESTART REQUIRED: stop + restart `mahika.cli start` for change to take effect")
    if new_mode == "live":
        print()
        print("  LIVE MODE — Mahika will autonomously file SAFE-T claims on")
        print("     Seller Central. Verify cockpit /claims queue + ensure")
        print("     selectors.py has real captures (not TODO(codegen) placeholders).")
    return 0


def cmd_process(args: argparse.Namespace) -> int:
    """Run Phase 3 evidence pipeline on a single order_id. Useful for backfill,
    one-off debugging, and re-running after threshold tuning."""
    try:
        result = evidence_pipeline.process_order(args.order_id, write_db=not args.no_db)
    except evidence_pipeline.OrderNotReady as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Processed {args.order_id}")
    print(f"  Suggested verdict:    {result.suggested.verdict.value} "
          f"(confidence {result.suggested.confidence:.0%})")
    if result.human_verdict:
        match = "matches" if result.human_verdict.upper() == result.suggested.verdict.value else "DIFFERS from"
        print(f"  Human verdict:        {result.human_verdict} ({match} suggestion)")
    print(f"  Mean SSIM:            {result.scores.mean_ssim:.3f}")
    print(f"  FPC sent / received:  "
          f"{result.scores.pk_ocr.fpc_code or '(none)'} / "
          f"{result.scores.rt_ocr.fpc_code or '(none)'}")
    print(f"  Composite saved:      {result.composite_path}")
    return 0


def cmd_cockpit(args: argparse.Namespace) -> int:
    """Launch the Phase 6 FastAPI cockpit. Blocks until SIGINT."""
    if not settings.cockpit_token:
        print(
            "ERROR: MAHIKA_COCKPIT_TOKEN is not set in .env.\n"
            "       Generate one with:\n"
            "           python -c \"import secrets; print(secrets.token_urlsafe(32))\"\n"
            "       Then paste it into .env as MAHIKA_COCKPIT_TOKEN=...",
            file=sys.stderr,
        )
        return 1

    import uvicorn

    host = args.host or settings.cockpit_host
    port = args.port or settings.cockpit_port
    if host not in ("127.0.0.1", "localhost", "::1") and not args.force_public:
        print(
            f"ERROR: Refusing to bind {host} — the cockpit is single-user local "
            "and shouldn't be public.\n"
            "       Add --force-public if you really know what you're doing "
            "(and harden the auth first).",
            file=sys.stderr,
        )
        return 1

    print(f"Mahika cockpit listening on http://{host}:{port}/")
    print("  Paste MAHIKA_COCKPIT_TOKEN on the /login page.")
    uvicorn.run(
        "mahika.cockpit.app:app",
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )
    return 0


def cmd_telegram_test(_: argparse.Namespace) -> int:
    """Send a test ping to Sir's Telegram chat."""
    from mahika.services.notifier import send_plain_message

    if not settings.telegram_configured:
        print("ERROR: Set MAHIKA_TELEGRAM_BOT_TOKEN and MAHIKA_TELEGRAM_CHAT_ID in .env")
        print("       See scripts/telegram_setup.md")
        return 1
    msg = (
        f"Mahika test OK\n"
        f"Runner: {settings.runner_id}\n"
        f"Mode: {settings.mode}\n"
        f"Storage: {settings.storage_root}"
    )
    ok = send_plain_message(msg)
    print("Telegram test sent." if ok else "ERROR: Telegram send failed.")
    return 0 if ok else 1


def cmd_telegram_chatid(_: argparse.Namespace) -> int:
    """Fetch chat_id from Telegram getUpdates after Sir messages the bot."""
    if not settings.telegram_bot_token:
        print("ERROR: MAHIKA_TELEGRAM_BOT_TOKEN not set in .env")
        return 1
    import httpx

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates"
    try:
        resp = httpx.get(url, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"ERROR: getUpdates failed: {exc}")
        return 1
    results = data.get("result") or []
    if not results:
        print("No messages yet. Message your bot on Telegram, then re-run this command.")
        return 1
    chat_ids: set[str] = set()
    for item in results:
        msg = item.get("message") or item.get("edited_message") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid is not None:
            chat_ids.add(str(cid))
    if not chat_ids:
        print("Could not parse chat_id from getUpdates response.")
        return 1
    print("Found chat ID(s) — paste one into root .env as MAHIKA_TELEGRAM_CHAT_ID:")
    for cid in sorted(chat_ids):
        print(f"  {cid}")
    return 0


def cmd_digest(_: argparse.Namespace) -> int:
    """Send daily-style status summary to Telegram (manual trigger)."""
    from mahika.services.notifier import send_plain_message

    if not settings.telegram_configured:
        print("ERROR: Telegram not configured — see scripts/telegram_setup.md")
        return 1

    lines = [
        f"Mahika daily digest",
        f"Runner: {settings.runner_id}",
        f"Mode: {settings.mode}",
        f"Storage: {settings.storage_root}",
    ]
    try:
        with get_session() as s:
            order_states = s.execute(
                text("SELECT state, count(*) FROM orders GROUP BY state ORDER BY state")
            ).all()
            queued = s.execute(
                text("SELECT count(*) FROM claims WHERE filed_at IS NULL")
            ).scalar()
        lines.append("")
        lines.append("Orders:")
        if order_states:
            for state, n in order_states:
                lines.append(f"  {state}: {n}")
        else:
            lines.append("  (none yet)")
        lines.append(f"Claim queue: {queued or 0}")
    except Exception as exc:
        lines.append(f"DB summary skipped: {type(exc).__name__}")

    ok = send_plain_message("\n".join(lines))
    print("Digest sent." if ok else "ERROR: digest send failed.")
    return 0 if ok else 1


def cmd_seller_login(args: argparse.Namespace) -> int:
    """Login to Seller Central, auto-fill OTP from Telegram, save cookies."""
    from mahika.playwright.seller_login import run_seller_login
    from mahika.playwright.session import LoginAborted, COOKIE_FILE

    headless = getattr(args, "headless", False)
    fresh = getattr(args, "fresh", False)
    print("=== Mahika Seller Central login ===")
    print(f"Cookies target: {COOKIE_FILE}")
    if fresh:
        print("Mode: FRESH — delete saved cookies, clean sign-in")
    if headless:
        print("Browser: headless (no window)")
    else:
        print(
            "Browser: Playwright Chromium — alag window khulegi (Cursor Browser tab NAHI). "
            "Alt+Tab se 'Chromium' / Chrome dekho. Script khatam = window band."
        )
    print("OTP: auto from Telegram if MAHIKA_TELEGRAM_* set (see scripts/OTP_SETUP.md)")
    print()

    try:
        ok = run_seller_login(headless=headless, fresh=fresh)
    except LoginAborted as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if ok:
        print("OK: Login complete — cookies saved.")
        return 0
    print("ERROR: Login failed.", file=sys.stderr)
    return 1


def cmd_support_case(args: argparse.Namespace) -> int:
    """Open Case Log, fill support case (after seller-login cookies)."""
    from mahika.playwright.support_case_flow import run_support_case_flow

    headless = getattr(args, "headless", False)
    submit = getattr(args, "submit", False)
    skip_login = getattr(args, "skip_login", False)
    print("=== Mahika Create Seller Support Case (Case Log) ===")
    print("Prerequisite: seller-login OK (cookies)")
    if skip_login:
        print("Mode: --skip-login (no re-auth if cookies invalid)")
    if headless:
        print("Browser: headless")
    else:
        print("Browser: Playwright Chromium (headed)")
    print(f"Submit: {'yes' if submit else 'review only (120s)'}")
    print()

    try:
        ok = run_support_case_flow(
            headless=headless,
            submit=submit,
            skip_login=skip_login,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if ok:
        print("OK: Support case flow complete — check screenshot in data/mahika/logs/")
        return 0
    print("ERROR: Support case flow failed.", file=sys.stderr)
    return 1


def cmd_session_check(_: argparse.Namespace) -> int:
    """Verify saved Seller Central cookies still work (headless)."""
    from playwright.sync_api import sync_playwright

    from mahika.playwright.session import COOKIE_FILE, load_cookies, session_is_authenticated
    from mahika.playwright.selectors import URLs

    if not COOKIE_FILE.exists():
        print("FAIL: No cookie file — run: mahika.cli seller-login")
        return 1

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        load_cookies(context)
        page = context.new_page()
        page.goto(URLs.SAFE_T_LIST, wait_until="domcontentloaded", timeout=60_000)
        ok = session_is_authenticated(page) and "/ap/signin" not in page.url
        browser.close()

    print(f"Cookie file: {COOKIE_FILE}")
    print("Session valid: YES" if ok else "Session valid: NO — run seller-login")
    return 0 if ok else 1


def cmd_otp_test(_: argparse.Namespace) -> int:
    """Test OTP parser — pass sample text as first arg or use default SMS."""
    from mahika.services.otp_watcher import extract_otp

    sample = "123456 is your Amazon OTP. Do not share it with anyone."
    got = extract_otp(sample)
    print(f"Sample SMS: {sample!r}")
    print(f"Extracted:  {got!r}")
    if got == "123456":
        print("OK: OTP parser works.")
        return 0
    print("FAIL: OTP parser did not match sample.")
    return 1


def cmd_otp_watch(args: argparse.Namespace) -> int:
    """Poll Telegram for OTP (3×60s). For Cursor-browser login — writes cursor_otp.txt."""
    from mahika.playwright.seller_login import (
        OTP_TELEGRAM_ATTEMPTS,
        OTP_TELEGRAM_WAIT_S,
        _telegram_wait_round,
    )
    from mahika.services.notifier import send_plain_message

    if not settings.telegram_configured:
        print("ERROR: MAHIKA_TELEGRAM_* not set", file=sys.stderr)
        return 1

    from mahika.services.otp_watcher import TelegramOtpWatcher

    out = settings.storage_root / "sessions" / "cursor_otp.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    label = getattr(args, "round_label", "cursor-browser")
    reset = getattr(args, "reset", False)
    watcher = TelegramOtpWatcher()
    print(f"=== OTP watch ({label}) — {OTP_TELEGRAM_ATTEMPTS}×{OTP_TELEGRAM_WAIT_S}s ===")
    send_plain_message(
        f"Mahika Cursor login [{label}]: sirf 6-digit OTP @mahika_arun_bot par bhejo."
    )
    otp = _telegram_wait_round(watcher, round_label=label, reset_prompt=reset)
    if not otp:
        print("TIMEOUT: no OTP from Telegram")
        return 1
    out.write_text(otp, encoding="utf-8")
    print(f"OK: OTP received — saved {out}")
    send_plain_message(f"Mahika: OTP mil gaya ({label}) — Cursor browser mein fill ho raha hai.")
    return 0


def cmd_reports_init(_: argparse.Namespace) -> int:
    """Create reports/inbox, archive, analysis under MAHIKA_STORAGE_ROOT."""
    from mahika.reports.analyzer import ensure_report_dirs

    ensure_report_dirs()
    print("Reports folders ready:")
    print(f"  inbox:    {settings.reports_inbox_dir}")
    print(f"  archive:  {settings.reports_archive_dir}")
    print(f"  analysis: {settings.reports_analysis_dir}")
    print()
    print("Drop Seller Central downloads in inbox/, then:")
    print("  python -m mahika.cli reports analyze")
    print("Guide: specs/seller-reports/DOWNLOAD_GUIDE.md")
    return 0


def cmd_reports_scan(args: argparse.Namespace) -> int:
    """List report files in a folder and detect their types."""
    from mahika.reports.analyzer import scan_directory

    directory = Path(args.directory) if args.directory else settings.reports_inbox_dir
    if not directory.exists():
        print(f"ERROR: {directory} does not exist — run: mahika.cli reports init")
        return 1
    results = scan_directory(directory)
    if not results:
        print(f"No report files in {directory}")
        print("Supported: *.csv, *.txt, *.tsv")
        return 0
    print(f"=== Reports scan: {directory} ===")
    for item in results:
        print(f"  [{item.kind.value:18s}] {item.path.name}")
    return 0


def cmd_reports_analyze(args: argparse.Namespace) -> int:
    """Parse order/payment/inventory reports and write summary."""
    from mahika.reports.analyzer import analyze_directory, format_summary, write_summary

    directory = Path(args.directory) if args.directory else settings.reports_inbox_dir
    if not directory.exists():
        print(f"ERROR: {directory} does not exist — run: mahika.cli reports init")
        return 1
    bundle = analyze_directory(directory)
    text = format_summary(bundle)
    print(text)
    if args.no_write:
        return 0
    out = write_summary(bundle, text)
    print(f"\nSaved: {out}")
    return 0 if not bundle.errors else 1


# ─── Top-level parser ────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mahika",
        description="Mahika — Amazon Seller Operations Agent (Project Alpha)",
    )
    subs = parser.add_subparsers(dest="command", required=True)

    p_start = subs.add_parser("start", help="Run the scheduler daemon")
    p_start.add_argument("--once", action="store_true",
                         help="Run every task once + exit (smoke test)")
    p_start.set_defaults(func=cmd_start)

    p_status = subs.add_parser("status", help="Print current operational snapshot")
    p_status.set_defaults(func=cmd_status)

    p_audit = subs.add_parser("audit-tail", help="Tail the audit_log")
    p_audit.add_argument("count", type=int, nargs="?", default=20,
                         help="Number of rows (default: 20)")
    p_audit.set_defaults(func=cmd_audit_tail)

    p_queue = subs.add_parser("queue", help="Show claim queue snapshot")
    p_queue.set_defaults(func=cmd_queue)

    p_process = subs.add_parser("process", help="Run Phase 3 evidence pipeline on one order_id")
    p_process.add_argument("order_id", help="Amazon order ID, e.g. 407-1234567-1234567")
    p_process.add_argument("--no-db", action="store_true", help="Skip Postgres writes (dry-run)")
    p_process.set_defaults(func=cmd_process)

    p_doctor = subs.add_parser("doctor", help="Self-diagnostic — verify wiring before launch")
    p_doctor.set_defaults(func=cmd_doctor)

    p_mode = subs.add_parser("mode", help="Flip MAHIKA_MODE (shadow/manual/live/paused) in .env")
    p_mode.add_argument("new_mode", choices=["shadow", "manual", "live", "paused"],
                        help="New operating mode")
    p_mode.set_defaults(func=cmd_mode)

    p_cockpit = subs.add_parser("cockpit", help="Launch the FastAPI dashboard (Phase 6)")
    p_cockpit.add_argument("--host", default=None, help="Bind host (default 127.0.0.1)")
    p_cockpit.add_argument("--port", default=None, type=int, help="Bind port (default 8765)")
    p_cockpit.add_argument("--force-public", action="store_true",
                           help="Override the 127.0.0.1-only safety check. DON'T.")
    p_cockpit.set_defaults(func=cmd_cockpit)

    p_tg_test = subs.add_parser("telegram-test", help="Send a test message to Telegram")
    p_tg_test.set_defaults(func=cmd_telegram_test)

    p_tg_id = subs.add_parser("telegram-chatid", help="Print chat_id from bot getUpdates")
    p_tg_id.set_defaults(func=cmd_telegram_chatid)

    p_digest = subs.add_parser("digest", help="Send daily-style status to Telegram now")
    p_digest.set_defaults(func=cmd_digest)

    p_sc_login = subs.add_parser(
        "seller-login",
        help="Login Seller Central + Telegram OTP + save cookies",
    )
    p_sc_login.add_argument(
        "--headless", action="store_true",
        help="Run Chromium headless (default: visible window)",
    )
    p_sc_login.add_argument(
        "--fresh",
        action="store_true",
        help="TEST ONLY: delete cookies + Chromium profile (normal login omits this)",
    )
    p_sc_login.set_defaults(func=cmd_seller_login)

    p_support = subs.add_parser(
        "support-case",
        help="Case Log — create SP-API / seller support case (login if needed)",
    )
    p_support.add_argument(
        "--headless", action="store_true",
        help="Run Chromium headless (default: visible window)",
    )
    p_support.add_argument(
        "--submit", action="store_true",
        help="Try to submit the form (default: fill + 120s review)",
    )
    p_support.add_argument(
        "--skip-login",
        action="store_true",
        help="Require existing cookies; fail if session expired",
    )
    p_support.set_defaults(func=cmd_support_case)

    p_sess = subs.add_parser("session-check", help="Verify saved Seller Central cookies")
    p_sess.set_defaults(func=cmd_session_check)

    p_otp = subs.add_parser("otp-test", help="Test Amazon OTP regex parser")
    p_otp.set_defaults(func=cmd_otp_test)

    p_otp_watch = subs.add_parser(
        "otp-watch",
        help="Telegram OTP poll for Cursor browser login (writes cursor_otp.txt)",
    )
    p_otp_watch.add_argument(
        "--round-label", default="cursor-browser", help="Label for logs/Telegram"
    )
    p_otp_watch.add_argument(
        "--reset", action="store_true", help="Reset prompt/used OTPs (scenario 2 retry)"
    )
    p_otp_watch.set_defaults(func=cmd_otp_watch)

    p_reports = subs.add_parser("reports", help="Seller Central flat-file reports (no SP-API)")
    reports_subs = p_reports.add_subparsers(dest="reports_command", required=True)

    p_r_init = reports_subs.add_parser("init", help="Create reports/inbox + archive + analysis folders")
    p_r_init.set_defaults(func=cmd_reports_init)

    p_r_scan = reports_subs.add_parser("scan", help="Detect report types in a folder")
    p_r_scan.add_argument(
        "directory", nargs="?",
        help="Folder to scan (default: MAHIKA_STORAGE_ROOT/reports/inbox)",
    )
    p_r_scan.set_defaults(func=cmd_reports_scan)

    p_r_analyze = reports_subs.add_parser("analyze", help="Parse reports and write summary")
    p_r_analyze.add_argument(
        "directory", nargs="?",
        help="Folder to analyze (default: inbox)",
    )
    p_r_analyze.add_argument(
        "--no-write", action="store_true",
        help="Print summary only; do not write analysis/summary-*.txt",
    )
    p_r_analyze.set_defaults(func=cmd_reports_analyze)

    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
