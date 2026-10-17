"""Headed status check — uses same Chromium profile as upload."""
from __future__ import annotations

import sys
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
sys.path.insert(0, str(AGENT_SRC))

from playwright.sync_api import sync_playwright

from mahika.playwright.account_switcher import complete_account_switcher, is_account_switcher_page
from mahika.playwright.session import CHROMIUM_PROFILE_DIR, load_cookies

OUT = Path(__file__).parent
URLS = [
    "https://sellercentral.amazon.in/product-search/bulk-upload-status",
    "https://sellercentral.amazon.in/listing/upload/status",
    "https://sellercentral.amazon.in/product-search/bulk",
]


def main() -> int:
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(CHROMIUM_PROFILE_DIR), headless=False,
            viewport={"width": 1400, "height": 900},
        )
        load_cookies(ctx)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(URLS[2], wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(4_000)
        if is_account_switcher_page(page):
            complete_account_switcher(page)
            page.goto(URLS[2], wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(3_000)

        # Open status from bulk page link
        for sel in ("text=Check Upload Status", "a:has-text('Check Upload Status')"):
            loc = page.locator(sel)
            if loc.count():
                loc.first.click(timeout=10_000)
                page.wait_for_timeout(5_000)
                break

        body = page.inner_text("body")
        (OUT / "bulk_upload_status.txt").write_text(f"URL: {page.url}\n\n{body}", encoding="utf-8")
        page.screenshot(path=str(OUT / "bulk_upload_status_final.png"), full_page=True)
        low = body.lower()
        if "bulk_create_25" in low:
            print(f"Batch found at {page.url}")
        elif "in progress" in low:
            print("STATUS: In Progress")
        elif "done" in low or "complete" in low or "processed" in low:
            print("STATUS: Complete")
        else:
            print(f"STATUS: see screenshot ({page.url})")

        for sel in ("text=Download processing report", "text=Processing report"):
            loc = page.locator(sel)
            if loc.count():
                try:
                    with page.expect_download(timeout=20_000) as dl:
                        loc.first.click()
                    p = OUT / "bulk_create_25_processing_report.xlsm"
                    dl.value.save_as(str(p))
                    print(f"Report: {p}")
                except Exception as exc:
                    print(f"Download skip: {exc}")
                break

        ctx.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
