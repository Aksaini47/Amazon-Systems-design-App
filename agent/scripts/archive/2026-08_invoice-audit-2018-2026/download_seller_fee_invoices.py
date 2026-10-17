"""Batch-download Amazon Seller Fee Invoices (2021+) via saved SC cookies.

Reads invoice manifest extracted from the seller-fee-invoices table, resolves
each PDF URL through /tax/view-seller-fee-invoice-execute, and saves files to
{storage_root}/amazon-seller-invoices/.

Usage (from agent/):
    python scripts/download_seller_fee_invoices.py
    python scripts/download_seller_fee_invoices.py --manifest path/to/manifest.json
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urljoin

import httpx

# Allow `from mahika...` when invoked as scripts/download_*.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahika.config import settings
from mahika.playwright.session import COOKIE_FILE

BASE = "https://sellercentral.amazon.in"
EXECUTE_URL = f"{BASE}/tax/view-seller-fee-invoice-execute"
MIN_DATE = datetime(2021, 1, 1, tzinfo=UTC)
DEFAULT_MANIFEST = (
    settings.storage_root / "amazon-seller-invoices" / "invoice_manifest_2021plus.json"
)
OUT_DIR = settings.storage_root / "amazon-seller-invoices"
LOG_FILE = OUT_DIR / "invoice_download_log.csv"


def _slug_type(invoice_type: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", invoice_type.strip())
    return re.sub(r"_+", "_", slug).strip("_")


def _target_filename(inv: dict) -> str:
    return f"{inv['end_date_iso']}_{_slug_type(inv['invoice_type'])}_{inv['invoice_id']}.pdf"


def _existing_for_invoice(invoice_id: str) -> Path | None:
    matches = list(OUT_DIR.glob(f"*_{invoice_id}.pdf"))
    return matches[0] if matches else None


def _cookies_for_httpx() -> dict[str, str]:
    if not COOKIE_FILE.exists():
        raise FileNotFoundError(f"No cookie file at {COOKIE_FILE}")
    data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
    cookies = data.get("cookies", data if isinstance(data, list) else [])
    jar: dict[str, str] = {}
    for c in cookies:
        if c.get("domain", "").endswith("amazon.in"):
            jar[c["name"]] = c["value"]
    return jar


def _build_payload(inv: dict) -> dict[str, str]:
    payload = {
        "fileType": quote(inv["file_type"], safe=""),
        "vatInvoiceNumber": quote(inv["invoice_id"], safe=""),
        "endDate": quote(inv["end_date"], safe=""),
        "payeeRegistrationNumber": quote(inv["payee_registration"], safe=""),
        "filterName": quote(inv["filter_name"], safe=""),
    }
    rar_id = (inv.get("rar_id") or "").strip()
    shed = (inv.get("shed_document_name") or "").strip()
    if rar_id and shed and rar_id != "null" and shed != "null":
        payload["rarId"] = quote(rar_id, safe="")
        payload["shedDocumentName"] = quote(shed, safe="")
    else:
        payload["documentVersionId"] = quote(inv["document_version_id"], safe="")
    return payload


def _session_expired(resp: httpx.Response) -> bool:
    url = str(resp.url)
    return "/ap/signin" in url or "/ap/mfa" in url or "/ap/cvf" in url


def _append_log(
    writer: csv.DictWriter,
    fp,
    *,
    invoice_id: str,
    date: str,
    invoice_type: str,
    status: str,
    path: str = "",
    error: str = "",
) -> None:
    writer.writerow({
        "invoice_id": invoice_id,
        "date": date,
        "type": invoice_type,
        "status": status,
        "path": path,
        "error": error,
        "logged_at": datetime.now(UTC).isoformat(),
    })
    fp.flush()


def download_all(manifest_path: Path, *, delay_s: float = 1.0) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    invoices = json.loads(manifest_path.read_text(encoding="utf-8"))
    cookies = _cookies_for_httpx()

    downloaded = skipped = failed = 0
    total_bytes = 0
    log_exists = LOG_FILE.exists()

    with LOG_FILE.open("a", encoding="utf-8", newline="") as log_fp:
        fieldnames = [
            "invoice_id", "date", "type", "status", "path", "error", "logged_at",
        ]
        writer = csv.DictWriter(log_fp, fieldnames=fieldnames)
        if not log_exists:
            writer.writeheader()

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": BASE,
            "Referer": f"{BASE}/tax/seller-fee-invoices",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        }

        with httpx.Client(cookies=cookies, headers=headers, timeout=60.0, follow_redirects=True) as client:
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
                        invoice_id=invoice_id, date=end_iso, invoice_type=inv_type,
                        status="skipped", path=str(existing),
                    )
                    print(f"[{i}/{len(invoices)}] SKIP {invoice_id} (exists)")
                    continue

                try:
                    exec_resp = client.post(EXECUTE_URL, json=_build_payload(inv))
                    if _session_expired(exec_resp):
                        print("SESSION EXPIRED — login required. Stopping.")
                        _append_log(
                            writer, log_fp,
                            invoice_id=invoice_id, date=end_iso, invoice_type=inv_type,
                            status="session_expired", error=str(exec_resp.url),
                        )
                        return 2

                    exec_resp.raise_for_status()
                    body = exec_resp.json()
                    pdf_path = body.get("url")
                    if not pdf_path:
                        raise RuntimeError(f"No url in execute response: {body!r}")

                    pdf_url = urljoin(BASE, pdf_path)
                    pdf_resp = client.get(pdf_url)
                    if _session_expired(pdf_resp):
                        print("SESSION EXPIRED on PDF fetch — login required. Stopping.")
                        _append_log(
                            writer, log_fp,
                            invoice_id=invoice_id, date=end_iso, invoice_type=inv_type,
                            status="session_expired", error=str(pdf_resp.url),
                        )
                        return 2

                    pdf_resp.raise_for_status()
                    content = pdf_resp.content
                    if not content.startswith(b"%PDF"):
                        raise RuntimeError(
                            f"Not a PDF ({len(content)} bytes, starts {content[:20]!r})"
                        )

                    target.write_bytes(content)
                    downloaded += 1
                    total_bytes += len(content)
                    _append_log(
                        writer, log_fp,
                        invoice_id=invoice_id, date=end_iso, invoice_type=inv_type,
                        status="downloaded", path=str(target),
                    )
                    print(f"[{i}/{len(invoices)}] OK {invoice_id} -> {target.name} ({len(content):,} B)")

                except Exception as exc:
                    failed += 1
                    _append_log(
                        writer, log_fp,
                        invoice_id=invoice_id, date=end_iso, invoice_type=inv_type,
                        status="failed", error=str(exc)[:500],
                    )
                    print(f"[{i}/{len(invoices)}] FAIL {invoice_id}: {exc}")

                if delay_s > 0:
                    time.sleep(delay_s)

    print()
    print("=== Seller Fee Invoice Download Summary ===")
    print(f"Manifest:    {manifest_path}")
    print(f"Output dir:  {OUT_DIR}")
    print(f"Total:       {len(invoices)}")
    print(f"Downloaded:  {downloaded}")
    print(f"Skipped:     {skipped}")
    print(f"Failed:      {failed}")
    print(f"New bytes:   {total_bytes:,} ({total_bytes / 1024 / 1024:.1f} MB)")
    all_pdfs = list(OUT_DIR.glob("*.pdf"))
    all_bytes = sum(p.stat().st_size for p in all_pdfs)
    print(f"On disk:     {len(all_pdfs)} PDFs, {all_bytes:,} bytes ({all_bytes / 1024 / 1024:.1f} MB)")
    print(f"Log:         {LOG_FILE}")
    return 0 if failed == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="JSON manifest of invoices to download",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds between downloads (default 1.0)",
    )
    args = parser.parse_args()
    if not args.manifest.exists():
        raise SystemExit(f"Manifest not found: {args.manifest}")
    raise SystemExit(download_all(args.manifest, delay_s=args.delay))


if __name__ == "__main__":
    main()
