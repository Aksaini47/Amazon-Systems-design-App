"""Download seller fee invoices using Playwright in-page fetch (active SC session).

Falls back to saved cookies; uses persistent Chromium profile when available.
"""
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
from mahika.playwright.session import (
    CHROMIUM_PROFILE_DIR,
    COOKIE_FILE,
    load_cookies,
    session_is_authenticated,
)

BASE = "https://sellercentral.amazon.in"
INVOICES_URL = f"{BASE}/tax/seller-fee-invoices"
EXECUTE_URL = f"{BASE}/tax/view-seller-fee-invoice-execute"
DEFAULT_MANIFEST = (
    settings.storage_root / "amazon-seller-invoices" / "invoice_manifest_2021plus.json"
)
OUT_DIR = settings.storage_root / "amazon-seller-invoices"
LOG_FILE = OUT_DIR / "invoice_download_log.csv"

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
    return { ok: false, status: execResp.status, url: execResp.url, error: await execResp.text().catch(()=>'') };
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


def _append_log(writer, fp, **row) -> None:
    row.setdefault("logged_at", datetime.now(UTC).isoformat())
    writer.writerow(row)
    fp.flush()


def _open_context(pw, *, headless: bool = True):
  if CHROMIUM_PROFILE_DIR.exists():
    return pw.chromium.launch_persistent_context(
      str(CHROMIUM_PROFILE_DIR),
      headless=headless,
      accept_downloads=True,
    )
  browser = pw.chromium.launch(headless=headless)
  context = browser.new_context()
  load_cookies(context)
  return context


def download_all(manifest_path: Path, *, delay_s: float = 1.0, headless: bool = True) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    invoices = json.loads(manifest_path.read_text(encoding="utf-8"))
    downloaded = skipped = failed = 0
    total_bytes = 0
    log_exists = LOG_FILE.exists()

    fieldnames = ["invoice_id", "date", "type", "status", "path", "error", "logged_at"]

    with sync_playwright() as pw:
        context = _open_context(pw, headless=headless)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(INVOICES_URL, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(2_000)

        if not session_is_authenticated(page) or "/ap/signin" in page.url:
            print("SESSION EXPIRED — login required. Open Seller Central and re-run.")
            context.close()
            return 2

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
                if existing and existing.exists():
                    skipped += 1
                    _append_log(
                        writer, log_fp,
                        invoice_id=invoice_id, date=end_iso, type=inv_type,
                        status="skipped", path=str(existing), error="",
                    )
                    print(f"[{i}/{len(invoices)}] SKIP {invoice_id}")
                    continue

                try:
                    result = page.evaluate(FETCH_JS, inv)
                    if not result.get("ok"):
                        url = result.get("url", "")
                        if "/ap/signin" in url:
                            print("SESSION EXPIRED mid-run — stopping.")
                            _append_log(
                                writer, log_fp,
                                invoice_id=invoice_id, date=end_iso, type=inv_type,
                                status="session_expired", path="", error=url,
                            )
                            context.close()
                            return 2
                        raise RuntimeError(
                            f"fetch failed status={result.get('status')} {result.get('error','')[:200]}"
                        )

                    content = base64.b64decode(result["b64"])
                    if not content.startswith(b"%PDF"):
                        raise RuntimeError(f"Not PDF ({len(content)} bytes)")

                    target.write_bytes(content)
                    downloaded += 1
                    total_bytes += len(content)
                    _append_log(
                        writer, log_fp,
                        invoice_id=invoice_id, date=end_iso, type=inv_type,
                        status="downloaded", path=str(target), error="",
                    )
                    print(f"[{i}/{len(invoices)}] OK {invoice_id} ({len(content):,} B)")

                except Exception as exc:
                    failed += 1
                    _append_log(
                        writer, log_fp,
                        invoice_id=invoice_id, date=end_iso, type=inv_type,
                        status="failed", path="", error=str(exc)[:500],
                    )
                    print(f"[{i}/{len(invoices)}] FAIL {invoice_id}: {exc}")

                if delay_s > 0:
                    time.sleep(delay_s)

        context.close()

    all_pdfs = list(OUT_DIR.glob("*.pdf"))
    all_bytes = sum(p.stat().st_size for p in all_pdfs)
    print()
    print("=== Seller Fee Invoice Download Summary ===")
    print(f"Total:       {len(invoices)}")
    print(f"Downloaded:  {downloaded}")
    print(f"Skipped:     {skipped}")
    print(f"Failed:      {failed}")
    print(f"New bytes:   {total_bytes:,} ({total_bytes / 1024 / 1024:.1f} MB)")
    print(f"On disk:     {len(all_pdfs)} PDFs, {all_bytes / 1024 / 1024:.1f} MB")
    print(f"Log:         {LOG_FILE}")
    return 0 if failed == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    if not args.manifest.exists():
        raise SystemExit(f"Manifest not found: {args.manifest}")
    raise SystemExit(download_all(args.manifest, delay_s=args.delay, headless=not args.headed))


if __name__ == "__main__":
    main()
