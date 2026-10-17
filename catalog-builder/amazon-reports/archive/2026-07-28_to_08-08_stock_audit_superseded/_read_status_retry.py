from playwright.sync_api import sync_playwright
from pathlib import Path
import time

OUT = Path(r"C:\Projects\Amazon Systems Design\catalog-builder\amazon-reports")
URL = "https://sellercentral.amazon.in/listing/status?reference_id=107438020664&account_id=amzn1.merchant.o.AF2WD92BX5KMB"

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("http://127.0.0.1:51197")
    page = None
    for ctx in browser.contexts:
        for p in ctx.pages:
            if "listing/status" in (p.url or "") or "bulk-upload-status" in (p.url or "") or "product-search/bulk" in (p.url or ""):
                page = p
    page.bring_to_front()
    if "107438020664" not in (page.url or ""):
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    # refresh once for initial status
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    body = page.inner_text("body")
    page.screenshot(path=str(OUT / "bulk_upload_qty0_retry_status.png"), full_page=True)
    (OUT / "_status_body_retry.txt").write_text(body, encoding="utf-8")
    print(page.url)
    # ascii-safe print
    print(body[:2500].encode("ascii", "replace").decode("ascii"))