"""Parallel batch download of Amazon Seller Fee Invoices (2021+).

Phase A: read invoice manifest (extracted from seller-fee-invoices table).
Phase B: resolve PDF URLs via /tax/view-seller-fee-invoice-execute, download in parallel.

Usage:
  python catalog-builder/amazon-reports/download_seller_invoices.py
  python catalog-builder/amazon-reports/download_seller_invoices.py --workers 8 --from-year 2021
  python catalog-builder/amazon-reports/download_seller_invoices.py --refresh-cookies
  python catalog-builder/amazon-reports/download_seller_invoices.py --browser-fetch --workers 4
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urljoin

import requests

STORAGE_ROOT = Path(
    os.environ.get(
        "MAHIKA_STORAGE_ROOT",
        r"c:\Projects\Amazon Systems Design\data\mahika",
    )
)
COOKIE_FILE = STORAGE_ROOT / "sessions" / "seller_central_cookies.json"
CHROMIUM_PROFILE_DIR = STORAGE_ROOT / "sessions" / "chromium_profile"

BASE = "https://sellercentral.amazon.in"
INVOICES_URL = f"{BASE}/tax/seller-fee-invoices"
EXECUTE_URL = f"{BASE}/tax/view-seller-fee-invoice-execute"
DEFAULT_OUT = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices")
DEFAULT_MANIFEST = DEFAULT_OUT / "invoice_manifest_2021plus.json"
DEFAULT_LOG = DEFAULT_OUT / "invoice_download_log.csv"

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
  return { ok: true, b64: btoa(binary), size: bytes.length };
}
"""

_log_lock = threading.Lock()


def _slug_type(invoice_type: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", invoice_type.strip())
    return re.sub(r"_+", "_", slug).strip("_")


def _target_filename(inv: dict) -> str:
    return f"{inv['end_date_iso']}_{_slug_type(inv['invoice_type'])}_{inv['invoice_id']}.pdf"


def _existing_for_invoice(out_dir: Path, invoice_id: str) -> Path | None:
    matches = list(out_dir.glob(f"*_{invoice_id}.pdf"))
    return matches[0] if matches else None


def _cookies_for_requests(cookie_file: Path) -> dict[str, str]:
    if not cookie_file.exists():
        raise FileNotFoundError(f"No cookie file at {cookie_file}")
    data = json.loads(cookie_file.read_text(encoding="utf-8"))
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


def _session_expired(resp: requests.Response) -> bool:
    url = str(resp.url)
    return "/ap/signin" in url or "/ap/mfa" in url or "/ap/cvf" in url


def _http_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE,
        "Referer": INVOICES_URL,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
    }


def _load_cookies(context) -> None:
    if not COOKIE_FILE.exists():
        return
    data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
    cookies = data.get("cookies", [])
    if cookies:
        context.add_cookies(cookies)


def _save_cookies(context) -> None:
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cookies = context.cookies()
    COOKIE_FILE.write_text(
        json.dumps({"saved_at": datetime.now(UTC).isoformat(), "cookies": cookies}, indent=2),
        encoding="utf-8",
    )


def _session_is_authenticated(page) -> bool:
    url = page.url
    if "/ap/signin" in url or "/ap/mfa" in url or "/ap/cvf" in url:
        return False
    if "sellercentral.amazon.in" in url and (
        "/home" in url or "/tax/" in url or "/inventory" in url
    ):
        return True
    try:
        return page.locator("#sc-logo-nav, [data-test-id='nav-home']").count() > 0
    except Exception:
        return False


def refresh_cookies_from_browser(*, headless: bool = True) -> bool:
    """Open Seller Central with Playwright profile and save fresh cookies."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        if CHROMIUM_PROFILE_DIR.exists():
            context = pw.chromium.launch_persistent_context(
                str(CHROMIUM_PROFILE_DIR),
                headless=headless,
                accept_downloads=True,
            )
        else:
            browser = pw.chromium.launch(headless=headless)
            context = browser.new_context()
            _load_cookies(context)

        page = context.pages[0] if context.pages else context.new_page()
        page.goto(INVOICES_URL, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(2_000)

        if not _session_is_authenticated(page) or "/ap/signin" in page.url:
            context.close()
            return False

        _save_cookies(context)
        context.close()
        return True


def _download_one_http(
    inv: dict,
    *,
    out_dir: Path,
    cookies: dict[str, str],
    session: requests.Session,
) -> dict:
    invoice_id = inv["invoice_id"]
    end_iso = inv["end_date_iso"]
    inv_type = inv["invoice_type"]
    target = out_dir / _target_filename(inv)

    existing = _existing_for_invoice(out_dir, invoice_id)
    if existing and existing.exists():
        return {
            "invoice_id": invoice_id,
            "date": end_iso,
            "type": inv_type,
            "status": "skipped",
            "path": str(existing),
            "error": "",
        }

    try:
        exec_resp = session.post(EXECUTE_URL, json=_build_payload(inv), timeout=60)
        if _session_expired(exec_resp):
            return {
                "invoice_id": invoice_id,
                "date": end_iso,
                "type": inv_type,
                "status": "session_expired",
                "path": "",
                "error": str(exec_resp.url)[:500],
            }

        exec_resp.raise_for_status()
        body = exec_resp.json()
        pdf_path = body.get("url")
        if not pdf_path:
            raise RuntimeError(f"No url in execute response: {body!r}")

        pdf_resp = session.get(urljoin(BASE, pdf_path), timeout=60)
        if _session_expired(pdf_resp):
            return {
                "invoice_id": invoice_id,
                "date": end_iso,
                "type": inv_type,
                "status": "session_expired",
                "path": "",
                "error": str(pdf_resp.url)[:500],
            }

        pdf_resp.raise_for_status()
        content = pdf_resp.content
        if not content.startswith(b"%PDF"):
            raise RuntimeError(
                f"Not a PDF ({len(content)} bytes, starts {content[:20]!r})"
            )

        target.write_bytes(content)
        return {
            "invoice_id": invoice_id,
            "date": end_iso,
            "type": inv_type,
            "status": "downloaded",
            "path": str(target),
            "error": "",
            "bytes": len(content),
        }
    except Exception as exc:
        return {
            "invoice_id": invoice_id,
            "date": end_iso,
            "type": inv_type,
            "status": "failed",
            "path": "",
            "error": str(exc)[:500],
        }


def _download_batch_browser(page, invoices: list[dict], out_dir: Path) -> list[dict]:
    results: list[dict] = []
    for inv in invoices:
        invoice_id = inv["invoice_id"]
        end_iso = inv["end_date_iso"]
        inv_type = inv["invoice_type"]
        target = out_dir / _target_filename(inv)

        existing = _existing_for_invoice(out_dir, invoice_id)
        if existing and existing.exists():
            results.append({
                "invoice_id": invoice_id,
                "date": end_iso,
                "type": inv_type,
                "status": "skipped",
                "path": str(existing),
                "error": "",
            })
            continue

        try:
            result = page.evaluate(FETCH_JS, inv)
            if not result.get("ok"):
                url = result.get("url", "")
                if "/ap/signin" in url:
                    results.append({
                        "invoice_id": invoice_id,
                        "date": end_iso,
                        "type": inv_type,
                        "status": "session_expired",
                        "path": "",
                        "error": url[:500],
                    })
                    break
                raise RuntimeError(
                    f"fetch failed status={result.get('status')} "
                    f"{result.get('error', '')[:200]}"
                )

            content = base64.b64decode(result["b64"])
            if not content.startswith(b"%PDF"):
                raise RuntimeError(f"Not PDF ({len(content)} bytes)")

            target.write_bytes(content)
            results.append({
                "invoice_id": invoice_id,
                "date": end_iso,
                "type": inv_type,
                "status": "downloaded",
                "path": str(target),
                "error": "",
                "bytes": len(content),
            })
        except Exception as exc:
            results.append({
                "invoice_id": invoice_id,
                "date": end_iso,
                "type": inv_type,
                "status": "failed",
                "path": "",
                "error": str(exc)[:500],
            })
    return results


def _append_logs(log_file: Path, rows: list[dict]) -> None:
    log_exists = log_file.exists()
    with _log_lock:
        with log_file.open("a", encoding="utf-8", newline="") as fp:
            fieldnames = [
                "invoice_id", "date", "type", "status", "path", "error", "logged_at",
            ]
            writer = csv.DictWriter(fp, fieldnames=fieldnames)
            if not log_exists and fp.tell() == 0:
                writer.writeheader()
            for row in rows:
                out = dict(row)
                out["logged_at"] = datetime.now(UTC).isoformat()
                out.pop("bytes", None)
                writer.writerow(out)


def _filter_from_year(invoices: list[dict], from_year: int) -> list[dict]:
    cutoff = f"{from_year}-01-01"
    return [i for i in invoices if i.get("end_date_iso", "") >= cutoff]


def download_all(
    *,
    manifest_path: Path,
    out_dir: Path,
    log_file: Path,
    cookie_file: Path,
    from_year: int,
    workers: int,
    browser_fetch: bool,
    refresh_cookies: bool,
    headless: bool,
) -> dict:
    start = datetime.now(UTC)
    out_dir.mkdir(parents=True, exist_ok=True)

    invoices = json.loads(manifest_path.read_text(encoding="utf-8"))
    invoices = _filter_from_year(invoices, from_year)

    downloaded = skipped = failed = session_expired = 0
    total_bytes = 0
    errors: list[str] = []

    if refresh_cookies:
        print("Refreshing cookies from Playwright browser profile...")
        if not refresh_cookies_from_browser(headless=headless):
            print("WARNING: Could not refresh cookies — login may be required.")

    if browser_fetch:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            if CHROMIUM_PROFILE_DIR.exists():
                context = pw.chromium.launch_persistent_context(
                    str(CHROMIUM_PROFILE_DIR),
                    headless=headless,
                    accept_downloads=True,
                )
            else:
                browser = pw.chromium.launch(headless=headless)
                context = browser.new_context()
                _load_cookies(context)

            page = context.pages[0] if context.pages else context.new_page()
            page.goto(INVOICES_URL, wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(2_000)

            if not _session_is_authenticated(page) or "/ap/signin" in page.url:
                context.close()
                end = datetime.now(UTC)
                return {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "duration_s": (end - start).total_seconds(),
                    "total": len(invoices),
                    "downloaded": 0,
                    "skipped": 0,
                    "failed": 0,
                    "session_expired": len(invoices),
                    "errors": ["SESSION EXPIRED — login required"],
                    "folder_bytes": sum(p.stat().st_size for p in out_dir.glob("*.pdf")),
                    "folder_count": len(list(out_dir.glob("*.pdf"))),
                }

            batch_size = max(1, workers)
            for batch_start in range(0, len(invoices), batch_size):
                batch = invoices[batch_start : batch_start + batch_size]
                rows = _download_batch_browser(page, batch, out_dir)
                _append_logs(log_file, rows)

                for row in rows:
                    st = row["status"]
                    if st == "downloaded":
                        downloaded += 1
                        total_bytes += row.get("bytes", 0)
                        print(f"OK {row['invoice_id']} ({row.get('bytes', 0):,} B)")
                    elif st == "skipped":
                        skipped += 1
                    elif st == "session_expired":
                        session_expired += 1
                        errors.append(f"{row['invoice_id']}: session_expired")
                        print("SESSION EXPIRED — stopping browser fetch.")
                        context.close()
                        end = datetime.now(UTC)
                        return _summary(
                            start, end, len(invoices), downloaded, skipped,
                            failed, session_expired, total_bytes, out_dir, errors,
                        )
                    else:
                        failed += 1
                        errors.append(f"{row['invoice_id']}: {row['error'][:120]}")
                        print(f"FAIL {row['invoice_id']}: {row['error'][:120]}")

                done = batch_start + len(batch)
                print(f"Progress: {done}/{len(invoices)}")

            context.close()
    else:
        cookies = _cookies_for_requests(cookie_file)
        session_expired_hit = False

        def _worker(inv: dict) -> dict:
            thread_session = requests.Session()
            thread_session.cookies.update(cookies)
            thread_session.headers.update(_http_headers())
            return _download_one_http(inv, out_dir=out_dir, cookies=cookies, session=thread_session)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_worker, inv): inv for inv in invoices}
            done_count = 0

            for fut in as_completed(futures):
                row = fut.result()
                _append_logs(log_file, [row])
                done_count += 1

                st = row["status"]
                if st == "downloaded":
                    downloaded += 1
                    total_bytes += row.get("bytes", 0)
                    if done_count % 25 == 0 or done_count == len(invoices):
                        print(f"Progress: {done_count}/{len(invoices)} (downloaded {downloaded})")
                elif st == "skipped":
                    skipped += 1
                elif st == "session_expired":
                    session_expired += 1
                    session_expired_hit = True
                    errors.append(f"{row['invoice_id']}: session_expired")
                else:
                    failed += 1
                    errors.append(f"{row['invoice_id']}: {row['error'][:120]}")

        if session_expired_hit:
            print("SESSION EXPIRED on HTTP — retry with --refresh-cookies or --browser-fetch")

    end = datetime.now(UTC)
    return _summary(
        start, end, len(invoices), downloaded, skipped,
        failed, session_expired, total_bytes, out_dir, errors,
    )


def _summary(
    start, end, total, downloaded, skipped, failed, session_expired,
    total_bytes, out_dir, errors,
) -> dict:
    pdfs = list(out_dir.glob("*.pdf"))
    folder_bytes = sum(p.stat().st_size for p in pdfs)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "duration_s": (end - start).total_seconds(),
        "total": total,
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "session_expired": session_expired,
        "new_bytes": total_bytes,
        "folder_count": len(pdfs),
        "folder_bytes": folder_bytes,
        "errors": errors[:5],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--cookie-file", type=Path, default=COOKIE_FILE)
    parser.add_argument("--from-year", type=int, default=2021)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--refresh-cookies", action="store_true")
    parser.add_argument(
        "--browser-fetch",
        action="store_true",
        help="Use Playwright in-page fetch (active browser session)",
    )
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    if not args.manifest.exists():
        raise SystemExit(f"Manifest not found: {args.manifest}")

    print(f"Manifest: {args.manifest}")
    print(f"Output:   {args.out_dir}")
    print(f"Workers:  {args.workers}")
    print(f"Mode:     {'browser-fetch' if args.browser_fetch else 'http-parallel'}")
    print()

    summary = download_all(
        manifest_path=args.manifest,
        out_dir=args.out_dir,
        log_file=args.log_file,
        cookie_file=args.cookie_file,
        from_year=args.from_year,
        workers=args.workers,
        browser_fetch=args.browser_fetch,
        refresh_cookies=args.refresh_cookies,
        headless=not args.headed,
    )

    print()
    print("=== Seller Fee Invoice Download Summary ===")
    print(f"Start:            {summary['start']}")
    print(f"End:              {summary['end']}")
    print(f"Duration:         {summary['duration_s']:.1f}s")
    print(f"Total manifest:   {summary['total']}")
    print(f"Downloaded:       {summary['downloaded']}")
    print(f"Skipped:          {summary['skipped']}")
    print(f"Failed:           {summary['failed']}")
    print(f"Session expired:  {summary['session_expired']}")
    print(f"New bytes:        {summary.get('new_bytes', 0):,} ({summary.get('new_bytes', 0)/1024/1024:.1f} MB)")
    print(f"Folder:           {summary['folder_count']} PDFs, {summary['folder_bytes']:,} bytes ({summary['folder_bytes']/1024/1024:.1f} MB)")
    if summary["errors"]:
        print("First errors:")
        for e in summary["errors"]:
            print(f"  - {e}")

    if summary["session_expired"] > 0 and summary["downloaded"] == 0:
        raise SystemExit(2)
    raise SystemExit(1 if summary["failed"] > 0 else 0)


if __name__ == "__main__":
    main()
