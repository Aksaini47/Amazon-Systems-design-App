"""Upload fixed OOS qty0 Partial Update via CDP to Chrome for Testing."""
from __future__ import annotations

import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:51197"
XLSM = Path(__file__).resolve().parent / "PHONE_ACCESSORY_oos_qty0_partial.xlsm"
BULK = "https://sellercentral.amazon.in/product-search/bulk"
STATUS = "https://sellercentral.amazon.in/product-search/bulk-upload-status"
OUT = Path(__file__).resolve().parent


def find_file_input(page):
    for sel in (
        "input#kat-file-attachment",
        "kat-file-attachment input[type=file]",
        "input[type=file]",
    ):
        loc = page.locator(sel)
        if loc.count() > 0:
            return loc.first
    handle = page.evaluate_handle(
        """() => {
          function walk(root) {
            let found = null;
            root.querySelectorAll('input[type=file]').forEach(i => found = i);
            root.querySelectorAll('*').forEach(el => {
              if (el.shadowRoot) {
                const f = walk(el.shadowRoot);
                if (f) found = f;
              }
            });
            return found;
          }
          return walk(document);
        }"""
    )
    el = handle.as_element()
    if el:
        return el
    raise RuntimeError("file input not found")


def click_submit(page):
    for sel in (
        "kat-button[label='Submit products']",
        "button:has-text('Submit products')",
        "[data-testid='submit-products']",
    ):
        loc = page.locator(sel)
        if loc.count() > 0:
            loc.first.click(timeout=15000)
            return
    page.get_by_role("button", name="Submit products").click(timeout=15000)


def main():
    assert XLSM.is_file(), XLSM
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP)
        page = None
        for ctx in browser.contexts:
            for p in ctx.pages:
                print("page:", p.url[:140])
                u = p.url or ""
                if "sellercentral.amazon.in/product-search/bulk" in u and "status" not in u:
                    page = p
        if page is None:
            for ctx in browser.contexts:
                for p in ctx.pages:
                    if "sellercentral.amazon.in" in (p.url or ""):
                        page = p
                        break
                if page:
                    break
        if page is None:
            raise SystemExit("No Seller Central page in Chrome for Testing")

        page.bring_to_front()
        u = page.url or ""
        if "product-search/bulk" not in u or "status" in u or "listing/status" in u:
            page.goto(BULK, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(2500)

        body0 = page.inner_text("body")[:800]
        print("account snip:", "Badeja" in body0, "India" in body0)

        fin = find_file_input(page)
        fin.set_input_files(str(XLSM))
        print("FILE SET:", XLSM.name)
        page.wait_for_timeout(2500)

        click_submit(page)
        print("Submit clicked")
        page.wait_for_timeout(5000)

        deadline = time.time() + 90
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
                break
            page.wait_for_timeout(2000)

        page.screenshot(path=str(OUT / "bulk_upload_qty0_retry_result.png"), full_page=True)
        print("shot result")

        page.goto(STATUS, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3500)
        status_body = page.inner_text("body")
        page.screenshot(path=str(OUT / "bulk_upload_qty0_retry_status.png"), full_page=True)

        batch = None
        m = re.search(
            r"PHONE_ACCESSORY_oos_qty0_partial\.xlsm.*?(\d{8,})",
            status_body,
            re.S | re.I,
        )
        if m:
            batch = m.group(1)
        m2 = re.search(r"Batch ID[:\s]*(\d{8,})", status_body, re.I)
        batches = re.findall(r"\b(1\d{11}|5\d{10}|\d{11,})\b", status_body)
        print("URL:", page.url)
        print("batch_guess:", batch, "m2:", m2.group(1) if m2 else None)
        print("batches_found:", batches[:8])
        print("STATUS_HEAD:")
        print(status_body[:2500])

        note = OUT / "bulk_upload_status_qty0_retry.txt"
        bg = batch or (m2.group(1) if m2 else (batches[0] if batches else "SEE_STATUS"))
        note.write_text(
            "\n".join(
                [
                    f"Checked: {time.strftime('%Y-%m-%d %H:%M IST')}",
                    "Account: Badeja Enterprises · India",
                    f"URL: {page.url}",
                    "Source: Chrome for Testing CDP upload (fixed CX=DEFAULT)",
                    "",
                    "FILE",
                    f"  Name: {XLSM.name}",
                    f"  Path: {XLSM}",
                    f"  Also: C:\\Users\\DELL\\Downloads\\{XLSM.name}",
                    f"  Batch guess: {bg}",
                    f"  Batches seen: {', '.join(batches[:6])}",
                    "",
                    "STATUS PAGE TEXT (head)",
                    status_body[:3500],
                    "",
                    "INTENT",
                    "  Partial Update restock: CX=DEFAULT, CY=master set_qty (1|2), NOT zero.",
                    "  Previous failed batch 107425020664 (error 99022 missing fulfillment_channel_code).",
                ]
            ),
            encoding="utf-8",
        )
        print("WROTE", note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())