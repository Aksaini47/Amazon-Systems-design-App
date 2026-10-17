"""Poll listing/status until bulk upload completes; download processing report."""
from __future__ import annotations

import sys
import time
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
sys.path.insert(0, str(AGENT_SRC))

from playwright.sync_api import sync_playwright

from mahika.playwright.session import CHROMIUM_PROFILE_DIR, load_cookies

STATUS_URL = "https://sellercentral.amazon.in/listing/status"
OUT = Path(__file__).parent
POLL_S = 45
MAX_WAIT_S = 1800


def main() -> int:
    batch = sys.argv[1] if len(sys.argv) > 1 else "50001020639"
    print(f"Polling {STATUS_URL} for batch {batch}…")

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(CHROMIUM_PROFILE_DIR), headless=True,
        )
        load_cookies(ctx)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        deadline = time.time() + MAX_WAIT_S
        final_body = ""
        status_word = "unknown"

        while time.time() < deadline:
            page.goto(STATUS_URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(4_000)
            body = page.inner_text("body")
            final_body = body
            low = body.lower()
            if batch not in body and "bulk_create_25" not in low:
                print("Batch row not visible yet")
            elif "in progress" in low:
                status_word = "in_progress"
                print(f"[{time.strftime('%H:%M:%S')}] In Progress")
            elif any(w in low for w in ("done", "complete", "processed", "successful")):
                status_word = "complete"
                print(f"[{time.strftime('%H:%M:%S')}] Complete")
                break
            elif "action required" in low or "failed" in low or "error" in low:
                status_word = "error"
                print(f"[{time.strftime('%H:%M:%S')}] Error/Action required")
                break
            else:
                print(f"[{time.strftime('%H:%M:%S')}] status unclear")
            time.sleep(POLL_S)

        (OUT / "bulk_upload_status.txt").write_text(
            f"URL: {page.url}\nSTATUS: {status_word}\n\n{final_body}", encoding="utf-8"
        )
        page.screenshot(path=str(OUT / "bulk_upload_status_final.png"), full_page=True)

        for sel in (
            "text=Download processing report",
            "text=Download processing summary",
            "text=Processing report",
        ):
            loc = page.locator(sel)
            if loc.count():
                try:
                    with page.expect_download(timeout=30_000) as dl:
                        loc.first.click()
                    dest = OUT / "bulk_create_25_processing_report.xlsm"
                    dl.value.save_as(str(dest))
                    print(f"Downloaded: {dest}")
                except Exception as exc:
                    print(f"Download failed: {exc}")
                break

        ctx.close()

    print(f"Final status: {status_word}")
    return 0 if status_word == "complete" else 0


if __name__ == "__main__":
    raise SystemExit(main())
