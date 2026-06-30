"""Check top-20 ASINs for existing Sponsored Products ad groups (headed)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from mahika.config import settings
from mahika.playwright.session import load_cookies, save_cookies

ASINS = [
    "B0FRSY8H6X", "B0FRSYVGPC", "B0GKGSN6XW", "B0FRT21V5X", "B0FRSX1DTM",
    "B0FRSX2GKD", "B0FRSWP42C", "B0FRSXWQ8K", "B0FRSWXQND", "B0FRSY3YKH",
    "B0FR29DSQD", "B0FR27KZBW", "B0FRSTQ3Y7", "B0FR28BCDK", "B0FRSX2YP9",
    "B0GKGK7PZ5", "B0FRSV59KK", "B0FRSX9LP5", "B0FRSV6HXQ", "B0FRSWR6Z7",
]

INDIA_PAID = "amzn1.pa.d.AB5ZXZYCP3XOLA6T5BVNPV2EXP6A"
HOME = f"https://sellercentral.amazon.in/home?mons_sel_dir_paid={INDIA_PAID}"
ADS_URLS = (
    f"https://advertising.amazon.in/cm/campaigns?entityId={INDIA_PAID}",
    "https://advertising.amazon.in/campaign-manager/campaigns",
    "https://sellercentral.amazon.in/campaign-manager/home",
)


def _page_text(page) -> str:
    try:
        return page.inner_text("body", timeout=30_000)
    except Exception:
        return ""


def main() -> int:
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    out_dir = settings.storage_root / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict] = {a: {"in_ads_ui": False, "ad_group_hint": ""} for a in ASINS}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        load_cookies(context)
        page = context.new_page()

        page.goto(HOME, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(3_000)

        ads_ok = False
        for url in ADS_URLS:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                page.wait_for_timeout(5_000)
                if "advertising" in (page.url or "") or "campaign" in (page.url or "").lower():
                    ads_ok = True
                    break
            except Exception:
                continue

        if not ads_ok:
            try:
                page.get_by_role("link", name=re.compile(r"campaign", re.I)).first.click(timeout=8_000)
                page.wait_for_timeout(5_000)
                ads_ok = "advertising" in (page.url or "") or "campaign" in (page.url or "").lower()
            except Exception:
                pass

        page.screenshot(path=str(out_dir / "ads_check_landing.png"), full_page=True)

        # Try global search per ASIN in ads console
        for asin in ASINS:
            found = False
            hint = ""
            try:
                for sel in (
                    "input[placeholder*='Search' i]",
                    "input[aria-label*='Search' i]",
                    "input[type='search']",
                    "#cm-search-campaigns",
                    "input[name='search']",
                ):
                    loc = page.locator(sel)
                    if not loc.count():
                        continue
                    box = loc.first
                    box.click(timeout=3_000)
                    box.fill(asin, timeout=5_000)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(2_500)
                    text = _page_text(page)
                    if asin in text and not re.search(r"no results|0 campaigns|nothing found", text, re.I):
                        found = True
                        # crude: line with asin + nearby ad group / campaign words
                        for line in text.splitlines():
                            if asin in line:
                                hint = line.strip()[:120]
                                break
                    box.fill("", timeout=2_000)
                    break
            except Exception:
                pass

            if not found:
                text = _page_text(page)
                if asin in text:
                    found = True
                    hint = "visible on page (no search box)"

            results[asin] = {"in_ads_ui": found, "ad_group_hint": hint}

        # Fallback: full page scan once
        full = _page_text(page)
        for asin in ASINS:
            if not results[asin]["in_ads_ui"] and asin in full:
                results[asin] = {"in_ads_ui": True, "ad_group_hint": "found in ads page text"}

        save_cookies(context)
        browser.close()

    report_path = out_dir / "ads_asin_adgroup_check.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    yes = [a for a, v in results.items() if v["in_ads_ui"]]
    no = [a for a, v in results.items() if not v["in_ads_ui"]]
    print(f"ADS_URL={ads_ok}")
    print(f"HAS_AD_GROUP_HINT={len(yes)}")
    print(f"NO_MATCH={len(no)}")
    for a in ASINS:
        flag = "YES" if results[a]["in_ads_ui"] else "NO"
        print(f"{a}\t{flag}\t{results[a]['ad_group_hint']}")
    print(f"JSON={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
