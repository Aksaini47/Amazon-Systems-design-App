"""Download 2020 seller fee invoices from live SC table (headed, waits for login)."""
from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahika.config import settings
from mahika.playwright.session import COOKIE_FILE, load_cookies, save_cookies, session_is_authenticated

BASE = "https://sellercentral.amazon.in"
INVOICES_URL = f"{BASE}/tax/seller-fee-invoices"
OUT_DIR = settings.storage_root / "amazon-seller-invoices"
LOG_FILE = OUT_DIR / "invoice_download_log.csv"
MANIFEST_2020 = OUT_DIR / "invoice_manifest_2020.json"

EXTRACT_2020_JS = """
() => {
  const y0 = new Date('2020-01-01T00:00:00Z');
  const y1 = new Date('2021-01-01T00:00:00Z');
  const items = [];
  for (const btn of document.querySelectorAll('button[data-invoice]')) {
    const endDate = new Date(btn.dataset.enddate);
    if (endDate < y0 || endDate >= y1) continue;
    const row = btn.closest('tr');
    const cells = Array.from(row.querySelectorAll('td.info')).map(c => c.innerText.trim());
    items.push({
      invoice_id: btn.dataset.invoice,
      invoice_type: cells[0] || '',
      end_date: btn.dataset.enddate,
      end_date_iso: endDate.toISOString().slice(0, 10),
      file_type: btn.dataset.filetype,
      filter_name: btn.dataset.filtername,
      payee_registration: btn.dataset.payeeregistrationnumber,
      document_version_id: btn.value,
      rar_id: btn.dataset.rarid || '',
      shed_document_name: btn.dataset.sheddocumentname || '',
    });
  }
  return items;
}
"""

FETCH_JS = """
async (inv) => {
  const enc = (s) => encodeURIComponent(s);
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
  const execResp = await fetch('/tax/view-seller-fee-invoice-execute', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    credentials: 'include',
    body: JSON.stringify(payload),
  });
  if (!execResp.ok) {
    return { ok: false, status: execResp.status, url: execResp.url, error: await execResp.text().catch(() => '') };
  }
  const data = await execResp.json();
  const pdfResp = await fetch(data.url, { credentials: 'include' });
  if (!pdfResp.ok) {
    return { ok: false, status: pdfResp.status, url: pdfResp.url, error: 'pdf fetch failed' };
  }
  const buf = await pdfResp.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return { ok: true, b64: btoa(binary), size: bytes.length, pdfUrl: data.url };
}
"""


def _slug_type(invoice_type: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", invoice_type.strip())
    return re.sub(r"_+", "_", slug).strip("_")


def _target_filename(inv: dict) -> str:
    return f"{inv['end_date_iso']}_{_slug_type(inv['invoice_type'])}_{inv['invoice_id']}.pdf"


def _existing_for_invoice(invoice_id: str) -> Path | None:
    matches = list(OUT_DIR.glob(f"*_{invoice_id}.pdf"))
    return matches[0] if matches else None


def _wait_for_invoices_page(page, *, timeout_s: float = 300.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if "/tax/seller-fee-invoices" in (page.url or "") and page.locator("button[data-invoice]").count() > 0:
            return True
        if session_is_authenticated(page) and page.locator("button[data-invoice]").count() > 0:
            return True
        page.wait_for_timeout(2_000)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--wait-login", type=float, default=300.0)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = skipped = failed = 0
    total_bytes = 0
    log_exists = LOG_FILE.exists()
    fieldnames = ["invoice_id", "date", "type", "status", "path", "error", "logged_at"]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        if COOKIE_FILE.exists():
            load_cookies(context)
        page = context.new_page()
        page.goto(INVOICES_URL, wait_until="domcontentloaded", timeout=90_000)

        if page.locator("button[data-invoice]").count() == 0:
            print(f"Login needed — invoices table not visible. Waiting up to {args.wait_login:.0f}s...")
            if not _wait_for_invoices_page(page, timeout_s=args.wait_login):
                print("STOP: Seller Central login / invoices page not ready.")
                context.close()
                browser.close()
                return 2
            save_cookies(context)
            print("Session OK — cookies saved.")

        invoices = page.evaluate(EXTRACT_2020_JS)
        MANIFEST_2020.write_text(json.dumps(invoices, indent=2), encoding="utf-8")
        print(f"Found {len(invoices)} invoices for 2020")

        with LOG_FILE.open("a", encoding="utf-8", newline="") as log_fp:
            writer = csv.DictWriter(log_fp, fieldnames=fieldnames)
            if not log_exists:
                writer.writeheader()

            for i, inv in enumerate(invoices, 1):
                invoice_id = inv["invoice_id"]
                end_iso = inv["end_date_iso"]
                inv_type = inv["invoice_type"]
                target = OUT_DIR / _target_filename(inv)

                existing = _existing_for_invoice(invoice_id)
                if existing:
                    skipped += 1
                    writer.writerow({
                        "invoice_id": invoice_id, "date": end_iso, "type": inv_type,
                        "status": "skipped", "path": str(existing), "error": "",
                        "logged_at": datetime.now(UTC).isoformat(),
                    })
                    log_fp.flush()
                    print(f"[{i}/{len(invoices)}] SKIP {invoice_id}")
                    continue

                try:
                    result = page.evaluate(FETCH_JS, inv)
                    if not result.get("ok"):
                        url = result.get("url", "")
                        if "/ap/signin" in url:
                            print("SESSION EXPIRED mid-run.")
                            context.close()
                            browser.close()
                            return 2
                        raise RuntimeError(result.get("error", f"status {result.get('status')}"))

                    content = base64.b64decode(result["b64"])
                    if not content.startswith(b"%PDF"):
                        raise RuntimeError("Not a PDF")
                    target.write_bytes(content)
                    downloaded += 1
                    total_bytes += len(content)
                    writer.writerow({
                        "invoice_id": invoice_id, "date": end_iso, "type": inv_type,
                        "status": "downloaded", "path": str(target), "error": "",
                        "logged_at": datetime.now(UTC).isoformat(),
                    })
                    log_fp.flush()
                    print(f"[{i}/{len(invoices)}] OK {invoice_id} ({len(content):,} B)")
                except Exception as exc:
                    failed += 1
                    writer.writerow({
                        "invoice_id": invoice_id, "date": end_iso, "type": inv_type,
                        "status": "failed", "path": "", "error": str(exc)[:500],
                        "logged_at": datetime.now(UTC).isoformat(),
                    })
                    log_fp.flush()
                    print(f"[{i}/{len(invoices)}] FAIL {invoice_id}: {exc}")

                if args.delay > 0:
                    time.sleep(args.delay)

        save_cookies(context)
        context.close()
        browser.close()

    pdfs = list(OUT_DIR.glob("2020-*.pdf"))
    print()
    print("=== 2020 Invoice Download ===")
    print(f"Target:      {len(invoices)}")
    print(f"Downloaded:  {downloaded}")
    print(f"Skipped:     {skipped}")
    print(f"Failed:      {failed}")
    print(f"2020 on disk: {len(pdfs)}")
    print(f"New bytes:   {total_bytes / 1024 / 1024:.1f} MB")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
