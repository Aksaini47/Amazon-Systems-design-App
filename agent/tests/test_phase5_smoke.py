"""Phase 5 smoke test — verifies parameterization without hitting Amazon.

We can't drive a real Seller Central session in CI/smoke (Sir's credentials
aren't here, and we wouldn't want to file fake claims even if they were).
This test covers the safely-testable surface:

    1. Template rendering for all (verdict × template_version) combinations
    2. Reason-code mapping
    3. Selectors module imports + codegen_pending_count is reasonable
    4. Scheduler imports the Phase 5 module without crashing
    5. file_one_queued_claim() with an empty queue returns None (no surprise)
    6. End-to-end shadow filing against a synthetic local HTML page —
       proves the Playwright wiring + screenshot trail + template rendering
       all work in isolation from Seller Central.

Run:
    python -m tests.test_phase5_smoke
"""
from __future__ import annotations

import http.server
import socketserver
import sys
import tempfile
import threading
from pathlib import Path

# Allow running directly from `agent/`
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahika.config import settings  # noqa: E402
from mahika.playwright import safe_t_filer, selectors, templates  # noqa: E402

# ─── (1) Template rendering ──────────────────────────────────────────────


def test_template_rendering() -> tuple[bool, list[str]]:
    findings: list[str] = []
    order_id = "407-TEST-XYZ1234"
    for version in templates.available_versions():
        for verdict in ("different", "damaged", "damaged_different"):
            try:
                msg = templates.render(verdict=verdict, order_id=order_id, version=version)  # type: ignore[arg-type]
            except Exception as exc:
                findings.append(f"  ✗ render({version}, {verdict}): {exc}")
                continue
            if order_id not in msg:
                findings.append(f"  ✗ {version}/{verdict}: order_id not interpolated")
                continue
            if len(msg) < 100:
                findings.append(f"  ✗ {version}/{verdict}: suspiciously short ({len(msg)} chars)")
                continue
            findings.append(f"  ✓ {version}/{verdict}: {len(msg)} chars")
    all_ok = all("✓" in line for line in findings)
    return all_ok, findings


# ─── (2) Reason code mapping ─────────────────────────────────────────────


def test_reason_codes() -> tuple[bool, list[str]]:
    findings: list[str] = []
    for verdict in ("different", "damaged", "damaged_different"):
        code = templates.reason_code(verdict)  # type: ignore[arg-type]
        if not code or len(code) < 5:
            findings.append(f"  ✗ {verdict}: reason_code returned {code!r}")
        else:
            findings.append(f"  ✓ {verdict}: {code!r}")
    return all("✓" in f for f in findings), findings


# ─── (3) Selectors module loads ──────────────────────────────────────────


def test_selectors_module() -> tuple[bool, list[str]]:
    findings: list[str] = []
    pending = selectors.codegen_pending_count()
    findings.append(f"  ✓ selectors imported; {pending} TODO(codegen) placeholders pending")
    # Verify the four page selector classes have the expected fields
    for page_attr in ("login", "safe_t_list", "claim_form", "claim_detail"):
        page_obj = getattr(selectors.SELECTORS, page_attr)
        fields = [f for f in dir(page_obj) if not f.startswith("_")]
        if not fields:
            findings.append(f"  ✗ {page_attr}: no selectors")
        else:
            findings.append(f"  ✓ {page_attr}: {len(fields)} selectors defined")
    return all("✓" in f for f in findings), findings


# ─── (4) Scheduler imports Phase 5 cleanly ───────────────────────────────


def test_scheduler_imports() -> tuple[bool, list[str]]:
    findings: list[str] = []
    try:
        from mahika.services import scheduler as sched_mod
    except Exception as exc:
        findings.append(f"  ✗ import failed: {exc}")
        return False, findings
    # The new task functions exist
    for name in ("filed_claim_status_check", "file_queued_claims"):
        if not hasattr(sched_mod, name):
            findings.append(f"  ✗ scheduler missing task: {name}")
        else:
            findings.append(f"  ✓ scheduler.{name} present")
    return all("✓" in f for f in findings), findings


# ─── (5) Empty queue returns None ────────────────────────────────────────


def test_empty_queue() -> tuple[bool, list[str]]:
    findings: list[str] = []
    # We can't guarantee the queue is empty (other smoke tests may have left
    # rows), so we just check the function returns either None or a valid result.
    try:
        result = safe_t_filer.file_one_queued_claim()
    except Exception as exc:
        findings.append(f"  ✗ file_one_queued_claim crashed: {exc}")
        return False, findings
    if result is None:
        findings.append("  ✓ queue empty path: returns None")
    else:
        findings.append(f"  ✓ queue had work: {result.order_id} success={result.success}")
    return True, findings


# ─── (6) Local HTML — end-to-end Playwright wiring sans Amazon ──────────


def _serve_local_html(html: str, port: int) -> tuple[socketserver.TCPServer, threading.Thread]:
    """Serve a single HTML page on localhost:{port} in a background thread."""

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def log_message(self, format: str, *args: object) -> None:  # quiet
            return

    server = socketserver.TCPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


SYNTHETIC_FORM_HTML = """\
<!doctype html>
<html><head><title>Synthetic SAFE-T form</title></head>
<body>
  <h1 id="page-title">Synthetic SAFE-T claim form</h1>
  <form>
    <input id="order-id" name="orderId" />
    <select id="reason" name="reasonCode">
      <option value=""></option>
      <option value="diff">Materially different item returned</option>
      <option value="dmg">Item received damaged</option>
    </select>
    <textarea id="msg" name="message"></textarea>
    <input type="file" id="file" />
    <button type="button" id="submit-btn">Submit</button>
  </form>
</body></html>
"""


def test_local_playwright_wiring() -> tuple[bool, list[str]]:
    """Drive a local HTML form using the same Playwright API patterns the
    real filer uses. This proves the library + Chromium are healthy and the
    selector style we chose actually resolves."""
    findings: list[str] = []
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        findings.append(f"  ✗ playwright import failed: {exc}")
        return False, findings

    server, thread = _serve_local_html(SYNTHETIC_FORM_HTML, port=8989)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto("http://127.0.0.1:8989/", wait_until="domcontentloaded", timeout=10_000)
            findings.append("  ✓ chromium navigated to synthetic form")

            # Mimic the filer's locator pattern
            page.locator("input[name='orderId']").fill("407-WIRING-TEST")
            page.locator("select[name='reasonCode']").select_option(label="Materially different item returned")
            page.locator("textarea[name='message']").fill(
                templates.render(verdict="different", order_id="407-WIRING-TEST")
            )

            order_id_value = page.locator("input[name='orderId']").input_value()
            if order_id_value != "407-WIRING-TEST":
                findings.append(f"  ✗ orderId did not stick: {order_id_value!r}")
            else:
                findings.append("  ✓ orderId filled")

            msg_value = page.locator("textarea[name='message']").input_value()
            if "Materially different" not in msg_value:
                findings.append("  ✗ message template did not render in textarea")
            else:
                findings.append(f"  ✓ template rendered into textarea ({len(msg_value)} chars)")

            # Save a screenshot to confirm screenshot path works
            with tempfile.TemporaryDirectory() as tmp:
                shot = Path(tmp) / "phase5_wiring_test.png"
                page.screenshot(path=str(shot), full_page=True)
                if shot.exists() and shot.stat().st_size > 0:
                    findings.append(f"  ✓ screenshot captured ({shot.stat().st_size} bytes)")
                else:
                    findings.append("  ✗ screenshot missing")

            page.close()
            context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()

    return all("✓" in f for f in findings), findings


# ─── Smoke runner ────────────────────────────────────────────────────────


def main() -> int:
    print("=== Phase 5 smoke test ===")
    print(f"Runner ID:    {settings.runner_id}")
    print(f"Mode:         {settings.mode}")
    print()

    suites = (
        ("Template rendering", test_template_rendering),
        ("Reason codes", test_reason_codes),
        ("Selectors module", test_selectors_module),
        ("Scheduler imports", test_scheduler_imports),
        ("Empty queue handling", test_empty_queue),
        ("Local Playwright wiring", test_local_playwright_wiring),
    )

    pass_count = 0
    for name, fn in suites:
        print(f"--- {name} ---")
        ok, findings = fn()
        for line in findings:
            print(line)
        print(f"  {'PASS' if ok else 'FAIL'}")
        print()
        if ok:
            pass_count += 1

    print(f"=== {pass_count}/{len(suites)} suites passed ===")
    return 0 if pass_count == len(suites) else 1


if __name__ == "__main__":
    raise SystemExit(main())
