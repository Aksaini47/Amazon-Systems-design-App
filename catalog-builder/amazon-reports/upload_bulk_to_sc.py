"""Upload bulk_create_25_quality.xlsm to Seller Central (headed Playwright).

Glass browser blocks DOM.setFileInputFiles; this uses saved mahika cookies + set_input_files.
Run from agent venv:
  cd agent && ..\\.venv\\Scripts\\python.exe ..\\catalog-builder\\amazon-reports\\upload_bulk_to_sc.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

from playwright.sync_api import sync_playwright

from mahika.playwright.account_switcher import (
    complete_account_switcher,
    is_account_switcher_page,
)
from mahika.playwright.session import (
    CHROMIUM_PROFILE_DIR,
    load_cookies,
    save_cookies,
    session_is_authenticated,
)

BULK_URL = "https://sellercentral.amazon.in/product-search/bulk"
STATUS_URL = "https://sellercentral.amazon.in/product-search/bulk-upload-status"
DEFAULT_XLSM = Path(__file__).parent / "bulk_create_25_quality.xlsm"
WAIT_SUBMIT_MS = 120_000


def _find_file_input(page):
    """kat-file-attachment hides input in shadow DOM."""
    selectors = (
        "input#kat-file-attachment",
        "kat-file-attachment input[type=file]",
        "input[type=file]",
    )
    for sel in selectors:
        loc = page.locator(sel)
        if loc.count() > 0:
            return loc.first
    # pierce shadow roots
    handle = page.evaluate_handle(
        """() => {
          function walk(root) {
            let found = null;
            root.querySelectorAll('input[type=file]').forEach(i => found = i);
            root.querySelectorAll('*').forEach(el => {
              if (el.shadowRoot) { const f = walk(el.shadowRoot); if (f) found = f; }
            });
            return found;
          }
          return walk(document);
        }"""
    )
    el = handle.as_element()
    if el:
        return page.locator("input[type=file]").first
    raise RuntimeError("file input not found on bulk upload page")


def _click_submit(page) -> None:
    for sel in (
        "kat-button[label='Submit products']",
        "button:has-text('Submit products')",
        "[data-testid='submit-products']",
    ):
        loc = page.locator(sel)
        if loc.count() > 0:
            loc.first.click(timeout=15_000)
            return
    page.get_by_role("button", name="Submit products").click(timeout=15_000)


def main() -> int:
    xlsm = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSM
    if not xlsm.is_file():
        print(f"ERROR: file not found: {xlsm}")
        return 1

    print(f"Upload target: {xlsm}")
    print("Opening headed Chromium — do not close until done.")

    with sync_playwright() as pw:
        CHROMIUM_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(CHROMIUM_PROFILE_DIR),
            headless=False,
            viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        if not load_cookies(context):
            print("WARN: no cookies loaded — may need login")

        page = context.pages[0] if context.pages else context.new_page()
        page.goto(BULK_URL, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(3_000)

        if is_account_switcher_page(page):
            print("Account switcher — completing S7")
            complete_account_switcher(page)
            page.goto(BULK_URL, wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(2_000)

        url = page.url or ""
        if "/ap/signin" in url or "/ap/mfa" in url:
            print("ERROR: session expired — run seller-login first")
            context.close()
            return 2

        if not session_is_authenticated(page) and "product-search/bulk" not in url:
            print(f"WARN: unexpected URL {url}")

        file_input = _find_file_input(page)
        file_input.set_input_files(str(xlsm.resolve()))
        print("File attached.")
        page.wait_for_timeout(2_000)

        submit = page.get_by_role("button", name="Submit products")
        try:
            submit.wait_for(state="visible", timeout=10_000)
            if submit.is_disabled():
                print("Submit still disabled — waiting 5s")
                page.wait_for_timeout(5_000)
        except Exception:
            pass

        _click_submit(page)
        print("Clicked Submit products — waiting for upload acknowledgement…")
        page.wait_for_timeout(5_000)

        # Poll for success banner or redirect
        deadline = time.time() + WAIT_SUBMIT_MS / 1000
        uploaded = False
        while time.time() < deadline:
            body = page.inner_text("body")[:4000].lower()
            if any(
                k in body
                for k in (
                    "uploaded successfully",
                    "feed submitted",
                    "submission complete",
                    "your file has been submitted",
                    "processing",
                )
            ):
                uploaded = True
                break
            if "error" in body and "submit" not in body:
                break
            page.wait_for_timeout(3_000)

        save_cookies(context)
        page.screenshot(path=str(xlsm.parent / "bulk_upload_result.png"), full_page=True)
        print(f"Screenshot: {xlsm.parent / 'bulk_upload_result.png'}")

        page.goto(STATUS_URL, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(3_000)
        status_text = page.inner_text("body")[:2000]
        (xlsm.parent / "bulk_upload_status.txt").write_text(
            f"URL: {page.url}\n\n{status_text}", encoding="utf-8"
        )
        print(f"Status saved: {xlsm.parent / 'bulk_upload_status.txt'}")
        page.screenshot(path=str(xlsm.parent / "bulk_upload_status.png"), full_page=True)

        context.close()

    print("DONE" if uploaded else "Submit clicked — verify status file/screenshot")
    return 0 if uploaded else 0


if __name__ == "__main__":
    raise SystemExit(main())
