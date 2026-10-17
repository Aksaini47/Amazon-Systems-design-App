"""Deep analysis of Amazon seller fee invoice PDFs — month-wise compilation.

Reads PDFs from {storage_root}/amazon-seller-invoices/invoice/ and writes:
  analysis/invoice_detail_analysis.csv
  analysis/invoice_monthly_summary.csv
  analysis/invoice_type_summary.csv
  analysis/invoice_analysis.json
  analysis/INVOICE_ANALYSIS.md

Usage (from agent/):
    python scripts/analyze_seller_invoices.py
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahika.config import settings

DEFAULT_INVOICE_DIR = settings.storage_root / "amazon-seller-invoices" / "invoice"
DEFAULT_OUT = settings.storage_root / "amazon-seller-invoices" / "analysis"

FILENAME_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<type>.+)_(?P<id>[A-Z0-9\-]+(?:-\d+)?)\.pdf$",
    re.I,
)
AMOUNT_PATTERNS = [
    ("total_invoice_amount", re.compile(r"Total Invoice amount\s+(-?)INR\s+([\d,]+\.?\d*)", re.I)),
    ("total_amount", re.compile(r"Total:\s+(-?)INR\s+([\d,]+\.?\d*)", re.I)),
    ("subtotal_fees", re.compile(r"Subtotal of fees amount\s+(-?)INR\s+([\d,]+\.?\d*)", re.I)),
    ("subtotal_gst", re.compile(r"Subtotal of GST amount\s+(-?)INR\s+([\d,]+\.?\d*)", re.I)),
    ("igst", re.compile(r"Subtotal for IGST\s+(-?)INR\s+([\d,]+\.?\d*)", re.I)),
    ("cgst", re.compile(r"Subtotal for CGST\s+(-?)INR\s+([\d,]+\.?\d*)", re.I)),
    ("sgst", re.compile(r"Subtotal for SGST\s+(-?)INR\s+([\d,]+\.?\d*)", re.I)),
]
INVOICE_NUM_RE = re.compile(r"(?:Invoice|Credit Note) Number:?\s*([A-Z0-9\-]+)", re.I)
INVOICE_DATE_RE = re.compile(
    r"(?:Invoice|Credit Note) Date:\s*(\d{2}/\d{2}/\d{4})", re.I
)


@dataclass
class InvoiceRecord:
    filename: str
    end_date: str
    year_month: str
    year: str
    invoice_type: str
    invoice_id: str
    file_size_bytes: int
    page_count: int
    pdf_invoice_number: str
    pdf_invoice_date: str
    total_invoice_amount: float | None
    subtotal_fees: float | None
    subtotal_gst: float | None
    igst: float | None
    cgst: float | None
    sgst: float | None
    parse_ok: bool
    error: str = ""


def _parse_amount(match: re.Match[str] | None) -> float | None:
    if not match:
        return None
    sign, raw = match.group(1), match.group(2)
    try:
        val = float(raw.replace(",", ""))
        return -val if sign == "-" else val
    except ValueError:
        return None


def analyze_pdf(path: Path) -> InvoiceRecord:
    m = FILENAME_RE.match(path.name)
    if not m:
        return InvoiceRecord(
            filename=path.name,
            end_date="",
            year_month="",
            year="",
            invoice_type="UNKNOWN",
            invoice_id=path.stem,
            file_size_bytes=path.stat().st_size,
            page_count=0,
            pdf_invoice_number="",
            pdf_invoice_date="",
            total_invoice_amount=None,
            subtotal_fees=None,
            subtotal_gst=None,
            igst=None,
            cgst=None,
            sgst=None,
            parse_ok=False,
            error="filename pattern mismatch",
        )

    end_date = m.group("date")
    year_month = end_date[:7]
    invoice_type = m.group("type").replace("_", " ")
    invoice_id = m.group("id")

    try:
        reader = PdfReader(str(path))
        text = "\n".join((pg.extract_text() or "") for pg in reader.pages)
        page_count = len(reader.pages)
        amounts: dict[str, float | None] = {}
        for key, pat in AMOUNT_PATTERNS:
            amounts[key] = _parse_amount(pat.search(text))

        total = amounts.get("total_invoice_amount") or amounts.get("total_amount")
        num_m = INVOICE_NUM_RE.search(text)
        date_m = INVOICE_DATE_RE.search(text)

        return InvoiceRecord(
            filename=path.name,
            end_date=end_date,
            year_month=year_month,
            year=end_date[:4],
            invoice_type=invoice_type,
            invoice_id=invoice_id,
            file_size_bytes=path.stat().st_size,
            page_count=page_count,
            pdf_invoice_number=(num_m.group(1).strip() if num_m else ""),
            pdf_invoice_date=(date_m.group(1).strip() if date_m else ""),
            total_invoice_amount=total,
            subtotal_fees=amounts.get("subtotal_fees"),
            subtotal_gst=amounts.get("subtotal_gst"),
            igst=amounts.get("igst"),
            cgst=amounts.get("cgst"),
            sgst=amounts.get("sgst"),
            parse_ok=total is not None,
            error="" if total is not None else "amount not found",
        )
    except Exception as exc:
        return InvoiceRecord(
            filename=path.name,
            end_date=end_date,
            year_month=year_month,
            year=end_date[:4],
            invoice_type=invoice_type,
            invoice_id=invoice_id,
            file_size_bytes=path.stat().st_size,
            page_count=0,
            pdf_invoice_number="",
            pdf_invoice_date="",
            total_invoice_amount=None,
            subtotal_fees=None,
            subtotal_gst=None,
            igst=None,
            cgst=None,
            sgst=None,
            parse_ok=False,
            error=str(exc)[:300],
        )


def _analyze_worker(path_str: str) -> dict:
    return asdict(analyze_pdf(Path(path_str)))


def build_monthly_summary(records: list[InvoiceRecord]) -> list[dict]:
    by_month: dict[str, list[InvoiceRecord]] = defaultdict(list)
    for r in records:
        if r.year_month:
            by_month[r.year_month].append(r)

    rows = []
    for ym in sorted(by_month):
        items = by_month[ym]
        totals = [r.total_invoice_amount for r in items if r.total_invoice_amount is not None]
        fees = [r.subtotal_fees for r in items if r.subtotal_fees is not None]
        gst = [r.subtotal_gst for r in items if r.subtotal_gst is not None]
        type_counts = Counter(r.invoice_type for r in items)
        rows.append({
            "year_month": ym,
            "invoice_count": len(items),
            "parsed_amount_count": len(totals),
            "total_inr": round(sum(totals), 2) if totals else None,
            "fees_inr": round(sum(fees), 2) if fees else None,
            "gst_inr": round(sum(gst), 2) if gst else None,
            "avg_invoice_inr": round(sum(totals) / len(totals), 2) if totals else None,
            "merchant_vat_invoice": type_counts.get("Merchant VAT Invoice", 0),
            "merchant_vat_credit_note": type_counts.get("Merchant VAT Credit Note", 0),
            "product_ads_vat_invoice": type_counts.get("Product Ads VAT Invoice", 0),
            "product_ads_vat_credit_note": type_counts.get("Product Ads VAT Credit Note", 0),
            "fba_tax_invoice": sum(v for k, v in type_counts.items() if "Fulfillment" in k),
        })
    return rows


def build_year_summary(records: list[InvoiceRecord]) -> list[dict]:
    by_year: dict[str, list[InvoiceRecord]] = defaultdict(list)
    for r in records:
        if r.year:
            by_year[r.year].append(r)
    rows = []
    for y in sorted(by_year):
        items = by_year[y]
        totals = [r.total_invoice_amount for r in items if r.total_invoice_amount is not None]
        fees = [r.subtotal_fees for r in items if r.subtotal_fees is not None]
        gst = [r.subtotal_gst for r in items if r.subtotal_gst is not None]
        rows.append({
            "year": y,
            "invoice_count": len(items),
            "total_inr": round(sum(totals), 2) if totals else None,
            "fees_inr": round(sum(fees), 2) if fees else None,
            "gst_inr": round(sum(gst), 2) if gst else None,
        })
    return rows


def build_type_summary(records: list[InvoiceRecord]) -> list[dict]:
    by_type: dict[str, list[InvoiceRecord]] = defaultdict(list)
    for r in records:
        by_type[r.invoice_type].append(r)
    rows = []
    for t in sorted(by_type):
        items = by_type[t]
        totals = [r.total_invoice_amount for r in items if r.total_invoice_amount is not None]
        rows.append({
            "invoice_type": t,
            "count": len(items),
            "total_inr": round(sum(totals), 2) if totals else None,
            "avg_inr": round(sum(totals) / len(totals), 2) if totals else None,
        })
    return rows


def write_markdown_summary(
    out_path: Path,
    records: list[InvoiceRecord],
    monthly: list[dict],
    yearly: list[dict],
    type_summary: list[dict],
) -> None:
    parsed = [r for r in records if r.parse_ok]
    totals = [r.total_invoice_amount for r in parsed if r.total_invoice_amount is not None]
    fees = [r.subtotal_fees for r in parsed if r.subtotal_fees is not None]
    gst = [r.subtotal_gst for r in parsed if r.subtotal_gst is not None]

    lines = [
        "# Amazon Seller Fee Invoices — Deep Analysis",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Executive summary",
        "",
        f"- **PDF files:** {len(records)}",
        f"- **Amount parsed:** {len(parsed)} ({100 * len(parsed) / max(len(records), 1):.1f}%)",
    ]
    if records:
        dates = sorted(r.end_date for r in records if r.end_date)
        lines.append(f"- **Date range:** {dates[0]} → {dates[-1]}")
    if totals:
        lines += [
            f"- **Net total (incl. credit notes):** INR {sum(totals):,.2f}",
            f"- **Net fees:** INR {sum(fees):,.2f}",
            f"- **Net GST:** INR {sum(gst):,.2f}",
        ]

    lines += ["", "## Year-wise", "", "| Year | Count | Net INR | Fees INR | GST INR |",
              "|------|------:|--------:|---------:|--------:|"]
    for row in yearly:
        lines.append(
            f"| {row['year']} | {row['invoice_count']} | "
            f"{row['total_inr']:,.2f} | {row['fees_inr']:,.2f} | {row['gst_inr']:,.2f} |"
        )

    lines += ["", "## By invoice type", "", "| Type | Count | Net INR | Avg INR |",
              "|------|------:|--------:|--------:|"]
    for row in type_summary:
        lines.append(
            f"| {row['invoice_type']} | {row['count']} | "
            f"{row['total_inr']:,.2f} | {row['avg_inr']:,.2f} |"
        )

    lines += ["", "## Month-wise compilation", "",
              "| Month | Count | Net INR | Fees INR | GST INR | MVI | MVCN | Ads | FBA |",
              "|-------|------:|--------:|---------:|--------:|----:|-----:|----:|----:|"]
    for row in monthly:
        lines.append(
            f"| {row['year_month']} | {row['invoice_count']} | "
            f"{row['total_inr']:,.2f} | {row['fees_inr']:,.2f} | {row['gst_inr']:,.2f} | "
            f"{row['merchant_vat_invoice']} | {row['merchant_vat_credit_note']} | "
            f"{row['product_ads_vat_invoice']} | {row['fba_tax_invoice']} |"
        )

    failed = [r for r in records if not r.parse_ok]
    if failed:
        lines += ["", f"## Parse failures ({len(failed)})", ""]
        for r in failed[:20]:
            lines.append(f"- `{r.filename}`: {r.error}")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--invoice-dir", type=Path, default=DEFAULT_INVOICE_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    pdfs = sorted(args.invoice_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {args.invoice_dir}", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Analyzing {len(pdfs)} PDFs with {args.workers} workers...")

    raw_rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_analyze_worker, str(p)): p for p in pdfs}
        done = 0
        for fut in as_completed(futures):
            raw_rows.append(fut.result())
            done += 1
            if done % 50 == 0 or done == len(pdfs):
                print(f"  {done}/{len(pdfs)}")

    records = [InvoiceRecord(**r) for r in sorted(raw_rows, key=lambda x: x["end_date"])]
    monthly = build_monthly_summary(records)
    yearly = build_year_summary(records)
    type_summary = build_type_summary(records)

    fieldnames = list(asdict(records[0]).keys())
    detail_csv = args.out_dir / "invoice_detail_analysis.csv"
    with detail_csv.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(asdict(r))

    monthly_csv = args.out_dir / "invoice_monthly_summary.csv"
    with monthly_csv.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(monthly[0].keys()) if monthly else [])
        writer.writeheader()
        writer.writerows(monthly)

    type_csv = args.out_dir / "invoice_type_summary.csv"
    with type_csv.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(type_summary[0].keys()) if type_summary else [])
        writer.writeheader()
        writer.writerows(type_summary)

    parsed = sum(1 for r in records if r.parse_ok)
    grand = sum(r.total_invoice_amount for r in records if r.total_invoice_amount is not None)
    summary_json = args.out_dir / "invoice_analysis.json"
    summary_json.write_text(json.dumps({
        "generated_at": datetime.now(UTC).isoformat(),
        "pdf_count": len(records),
        "parsed_ok": parsed,
        "grand_total_inr": round(grand, 2),
        "yearly": yearly,
        "monthly": monthly,
        "by_type": type_summary,
    }, indent=2), encoding="utf-8")

    md_path = args.out_dir / "INVOICE_ANALYSIS.md"
    write_markdown_summary(md_path, records, monthly, yearly, type_summary)

    print()
    print("=== Analysis complete ===")
    print(f"PDFs:        {len(records)}")
    print(f"Parsed:      {parsed}")
    print(f"Grand total: INR {grand:,.2f}")
    print(f"Outputs:     {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
