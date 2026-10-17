from playwright.sync_api import sync_playwright
import re
import time
from pathlib import Path

OUT = Path(r"C:\Projects\Amazon Systems Design\catalog-builder\amazon-reports")
CDP = "http://127.0.0.1:51197"

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CDP)
    page = None
    for ctx in browser.contexts:
        for p in ctx.pages:
            print("page", p.url[:140])
            if "product-search/bulk" in (p.url or ""):
                page = p
    if page is None:
        raise SystemExit("no page")
    page.bring_to_front()
    page.keyboard.press("Control+0")
    page.wait_for_timeout(800)
    body = page.inner_text("body")
    print("READY" if "Ready to submit 21" in body or "Ready to submit" in body else "NOREADY")
    print("snip:", body[:800].replace("\n", " | "))

    clicked = False
    candidates = [
        page.get_by_role("button", name=re.compile(r"^Submit$")),
        page.get_by_role("button", name=re.compile(r"Submit products", re.I)),
        page.locator("button:has-text('Submit')"),
        page.locator("kat-button:has-text('Submit')"),
    ]
    for loc in candidates:
        try:
            n = loc.count()
        except Exception:
            n = 0
        print("cand", n)
        if n:
            try:
                loc.first.click(timeout=8000, force=True)
                clicked = True
                print("CLICKED")
                break
            except Exception as e:
                print("fail", e)

    if not clicked:
        # JS click any visible Submit button
        clicked = page.evaluate(
            """() => {
              const nodes = [...document.querySelectorAll('button, kat-button, [role=button]')];
              const hit = nodes.find(n => /\\bSubmit\\b/i.test((n.innerText||n.textContent||n.getAttribute('label')||'').trim()));
              if (!hit) return false;
              hit.click();
              return true;
            }"""
        )
        print("JS click", clicked)

    page.wait_for_timeout(6000)
    page.screenshot(path=str(OUT / "bulk_upload_qty0_retry_result.png"), full_page=True)
    print("URL", page.url)
    print(page.inner_text("body")[:2000])