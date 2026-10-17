"""Execute one CDP superbatch via Playwright in-page fetch (needs live SC session).

Uses persistent Chromium profile. If session expired, exits with code 2.
For Glass browser session, use MCP CDP batch mode instead (see --help).
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

OUT_DIR = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")
SUPER_DIR = OUT_DIR / "_cdp_superbatches"
MANIFEST = OUT_DIR / "invoice_manifest_2021plus.json"
LOG_FILE = OUT_DIR / "invoice_download_log.csv"
CHROMIUM_PROFILE = Path(r"c:\Projects\Amazon Systems Design\data\mahika\sessions\chromium_profile")
COOKIE_FILE = Path(r"c:\Projects\Amazon Systems Design\data\mahika\sessions\seller_central_cookies.json")
INVOICES_URL = "https://sellercentral.amazon.in/tax/seller-fee-invoices"

FETCH_BATCH_JS = """
async (invoices) => {
  const enc = (s) => encodeURIComponent(s);
  const fetchOne = async (inv) => {
    const payload = {
      fileType: enc(inv.file_type),
      vatInvoiceNumber: enc(inv.invoice_id),
      endDate: enc(inv.end_date),
      payeeRegistrationNumber: enc(inv.payee_registration),
      filterName: enc(inv.filter_name),
    };
    const rar = (inv.rar_id || '').trim();
    const shed = (inv.shed_document_name || '').trim();
    if (rar && shed && rar !== 'null' && shed !== 'null') {
      payload.rarId = enc(rar);
      payload.shedDocumentName = enc(shed);
    } else {
      payload.documentVersionId = enc(inv.document_version_id);
    }
    try {
      const execResp = await fetch('/tax/view-seller-fee-invoice-execute', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        credentials: 'include', body: JSON.stringify(payload),
      });
      if (!execResp.ok || execResp.url.includes('/ap/signin')) {
        return { invoice_id: inv.invoice_id, ok: false, error: execResp.url || String(execResp.status) };
      }
      const data = await execResp.json();
      const pdfResp = await fetch(data.url, { credentials: 'include' });
      if (!pdfResp.ok) return { invoice_id: inv.invoice_id, ok: false, error: 'pdf ' + pdfResp.status };
      const buf = await pdfResp.arrayBuffer();
      const bytes = new Uint8Array(buf);
      let binary = '';
      for (let i = 0; i < bytes.length; i += 0x8000) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
      }
      return { invoice_id: inv.invoice_id, ok: true, b64: btoa(binary), size: bytes.length };
    } catch (e) {
      return { invoice_id: inv.invoice_id, ok: false, error: String(e) };
    }
  };
  const limit = 8;
  const out = [];
  for (let i = 0; i < invoices.length; i += limit) {
    const chunk = invoices.slice(i, i + limit);
    out.push(...await Promise.all(chunk.map(fetchOne)));
  }
  return out;
}
"""


def _slug_type(invoice_type: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", invoice_type.strip())
    return re.sub(r"_+", "_", slug).strip("_")


def _target_filename(inv: dict) -> str:
    return f"{inv['end_date_iso']}_{_slug_type(inv['invoice_type'])}_{inv['invoice_id']}.pdf"


def save_results(results: list[dict]) -> dict:
    manifest = {i["invoice_id"]: i for i in json.loads(MANIFEST.read_text(encoding="utf-8"))}
    stats = {"downloaded": 0, "failed": 0}
    import csv

    log_exists = LOG_FILE.exists()
    with LOG_FILE.open("a", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=["invoice_id", "date", "type", "status", "path", "error", "logged_at"],
        )
        if not log_exists:
            writer.writeheader()
        for item in results:
            inv = manifest[item["invoice_id"]]
            if not item.get("ok"):
                stats["failed"] += 1
                writer.writerow({
                    "invoice_id": item["invoice_id"], "date": inv["end_date_iso"],
                    "type": inv["invoice_type"], "status": "failed",
                    "path": "", "error": item.get("error", "")[:500],
                    "logged_at": datetime.now(UTC).isoformat(),
                })
                continue
            content = base64.b64decode(item["b64"])
            target = OUT_DIR / _target_filename(inv)
            target.write_bytes(content)
            stats["downloaded"] += 1
            writer.writerow({
                "invoice_id": item["invoice_id"], "date": inv["end_date_iso"],
                "type": inv["invoice_type"], "status": "downloaded",
                "path": str(target), "error": "",
                "logged_at": datetime.now(UTC).isoformat(),
            })
    return stats


def run_superbatch(num: int, *, headless: bool = True) -> int:
    batch_file = SUPER_DIR / f"super_{num:03d}.json"
    if not batch_file.exists():
        raise SystemExit(f"Missing {batch_file}")
    invoices = json.loads(batch_file.read_text(encoding="utf-8"))

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        if CHROMIUM_PROFILE.exists():
            ctx = pw.chromium.launch_persistent_context(
                str(CHROMIUM_PROFILE), headless=headless, accept_downloads=True,
            )
        else:
            browser = pw.chromium.launch(headless=headless)
            ctx = browser.new_context()
            if COOKIE_FILE.exists():
                data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
                ctx.add_cookies(data.get("cookies", []))

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(INVOICES_URL, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(2000)
        if "/ap/signin" in page.url:
            ctx.close()
            return 2

        results = page.evaluate(FETCH_BATCH_JS, invoices)
        ctx.close()

    stats = save_results(results)
    print(f"super_{num:03d}: {stats}")
    return 0 if stats["failed"] == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("superbatch", type=int, nargs="?", help="Superbatch number (0-8)")
    parser.add_argument("--all", action="store_true", help="Run all pending superbatches")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    if args.all:
        codes = []
        for n in range(len(list(SUPER_DIR.glob("super_*.json")))):
            code = run_superbatch(n, headless=not args.headed)
            if code == 2:
                print("SESSION EXPIRED")
                raise SystemExit(2)
            codes.append(code)
        raise SystemExit(max(codes))
    if args.superbatch is None:
        parser.error("superbatch number or --all required")
    raise SystemExit(run_superbatch(args.superbatch, headless=not args.headed))


if __name__ == "__main__":
    main()
