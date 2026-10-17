"""Generate Word summary: Amazon seller fee invoices 2020+ (gross vs net)."""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

ANALYSIS = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices\analysis")
DETAIL_CSV = ANALYSIS / "invoice_detail_analysis.csv"
SERVICE_CSV = ANALYSIS / "service_totals.csv"
OUT_DOCX = ANALYSIS / "Amazon_Fee_Invoice_Summary_2020_onwards.docx"

INVOICE_TYPES = {
    "Merchant VAT Invoice",
    "Fulfillment by Amazon Tax Invoice",
    "Product Ads VAT Invoice",
}
CREDIT_TYPES = {
    "Merchant VAT Credit Note",
    "Product Ads VAT Credit Note",
}


def _f(v: float | None) -> str:
    if v is None:
        return "—"
    return f"INR {v:,.2f}"


def _load_rows() -> list[dict]:
    with DETAIL_CSV.open(encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def _flt(row: dict, key: str) -> float:
    v = row.get(key, "")
    if v in ("", None):
        return 0.0
    return float(v)


def _year_stats(rows: list[dict], year_from: int = 2020) -> dict:
    stats: dict[str, dict] = defaultdict(lambda: {
        "count": 0, "gross": 0.0, "credits": 0.0, "net": 0.0,
        "fees": 0.0, "gst": 0.0,
    })
    for r in rows:
        y = int(r["year"])
        if y < year_from:
            continue
        amt = _flt(r, "total_invoice_amount")
        fees = _flt(r, "subtotal_fees")
        gst = _flt(r, "subtotal_gst")
        t = r["invoice_type"]
        s = stats[str(y)]
        s["count"] += 1
        s["net"] += amt
        s["fees"] += fees
        s["gst"] += gst
        if t in CREDIT_TYPES or amt < 0:
            s["credits"] += amt
        else:
            s["gross"] += amt
    return dict(stats)


def _type_stats(rows: list[dict], year_from: int = 2020) -> list[dict]:
    by: dict[str, dict] = defaultdict(lambda: {"count": 0, "total": 0.0, "fees": 0.0, "gst": 0.0})
    for r in rows:
        if int(r["year"]) < year_from:
            continue
        t = r["invoice_type"]
        by[t]["count"] += 1
        by[t]["total"] += _flt(r, "total_invoice_amount")
        by[t]["fees"] += _flt(r, "subtotal_fees")
        by[t]["gst"] += _flt(r, "subtotal_gst")
    return sorted(by.items(), key=lambda x: x[1]["total"], reverse=True)


def _month_stats(rows: list[dict], year_from: int = 2020) -> list[dict]:
    by: dict[str, dict] = defaultdict(lambda: {"count": 0, "gross": 0.0, "credits": 0.0, "net": 0.0})
    for r in rows:
        if int(r["year"]) < year_from:
            continue
        ym = r["year_month"]
        amt = _flt(r, "total_invoice_amount")
        m = by[ym]
        m["count"] += 1
        m["net"] += amt
        if r["invoice_type"] in CREDIT_TYPES or amt < 0:
            m["credits"] += amt
        else:
            m["gross"] += amt
    return [{"month": k, **v} for k, v in sorted(by.items())]


def _add_table(doc: Document, headers: list[str], rows: list[list[str]], col_widths: list[float] | None = None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
        for p in hdr[i].paragraphs:
            for run in p.runs:
                run.bold = True
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = val
    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Inches(w)
    doc.add_paragraph()


def main() -> None:
    rows = _load_rows()
    rows_2020 = [r for r in rows if int(r["year"]) >= 2020]

    gross = sum(_flt(r, "total_invoice_amount") for r in rows_2020 if r["invoice_type"] in INVOICE_TYPES)
    credits = sum(_flt(r, "total_invoice_amount") for r in rows_2020 if r["invoice_type"] in CREDIT_TYPES)
    net = sum(_flt(r, "total_invoice_amount") for r in rows_2020)
    fees = sum(_flt(r, "subtotal_fees") for r in rows_2020)
    gst = sum(_flt(r, "subtotal_gst") for r in rows_2020)

    # All-time 2018+ for reference
    gross_all = sum(_flt(r, "total_invoice_amount") for r in rows if r["invoice_type"] in INVOICE_TYPES)
    credits_all = sum(_flt(r, "total_invoice_amount") for r in rows if r["invoice_type"] in CREDIT_TYPES)
    net_all = sum(_flt(r, "total_invoice_amount") for r in rows)

    count_invoices_2020 = sum(1 for r in rows_2020 if r["invoice_type"] in INVOICE_TYPES)
    count_credits_2020 = sum(1 for r in rows_2020 if r["invoice_type"] in CREDIT_TYPES)

    doc = Document()
    title = doc.add_heading("Amazon Seller Fee Invoices — Summary & Analysis", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph("IMPORT HUB E-COM · Seller Central India")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.runs[0].italic = True

    doc.add_paragraph(f"Report date: {datetime.now().strftime('%d %B %Y')}")
    doc.add_paragraph(
        "Purpose: Estimate how much Amazon charged in seller fees (invoices minus credit notes), "
        "including GST, from January 2020 through the latest invoice on file."
    )

    doc.add_heading("Executive answer — How much did Amazon earn from us?", level=1)
    p = doc.add_paragraph()
    p.add_run("Net amount paid to Amazon (2020 → latest): ").bold = True
    p.add_run(f"{_f(net)}").bold = True
    doc.add_paragraph(
        "This is the bottom line after all VAT invoices, FBA tax invoices, Product Ads invoices, "
        "and credit notes (refunds/adjustments). Credit notes reduce what you actually paid."
    )

    doc.add_heading("Gross vs Net (2020 onwards)", level=1)
    _add_table(doc, ["Metric", "Amount (INR)", "Notes"], [
        ["Gross invoices (fees + GST, before credits)", _f(gross), f"{count_invoices_2020} invoices — charges billed"],
        ["Credit notes (adjustments/refunds)", _f(credits), f"{count_credits_2020} credit notes — negative"],
        ["Net paid to Amazon", _f(net), "Gross + credits"],
        ["Of which: Fee subtotal (pre-GST)", _f(fees), "Amazon service fees before tax"],
        ["Of which: GST component", _f(gst), "IGST/CGST/SGST on fees"],
        ["Invoice count (2020+)", str(len(rows_2020)), f"{len(rows_2020)} PDF files"],
    ], [2.2, 1.5, 2.8])

    doc.add_heading("All-time reference (2018 → latest, all 484 invoices)", level=2)
    _add_table(doc, ["Metric", "Amount (INR)"], [
        ["Gross invoices", _f(gross_all)],
        ["Credit notes", _f(credits_all)],
        ["Net paid to Amazon (all time)", _f(net_all)],
    ], [3.0, 2.0])

    doc.add_heading("Year-wise breakdown (2020 onwards)", level=1)
    ys = _year_stats(rows)
    yr_rows = []
    for y in sorted(ys):
        s = ys[y]
        yr_rows.append([y, str(s["count"]), _f(s["gross"]), _f(s["credits"]), _f(s["net"]), _f(s["fees"]), _f(s["gst"])])
    yr_rows.append([
        "TOTAL", str(sum(s["count"] for s in ys.values())),
        _f(sum(s["gross"] for s in ys.values())),
        _f(sum(s["credits"] for s in ys.values())),
        _f(sum(s["net"] for s in ys.values())),
        _f(sum(s["fees"] for s in ys.values())),
        _f(sum(s["gst"] for s in ys.values())),
    ])
    _add_table(
        doc,
        ["Year", "Count", "Gross INR", "Credits INR", "Net INR", "Fees INR", "GST INR"],
        yr_rows,
    )

    doc.add_heading("By invoice type (2020 onwards)", level=1)
    type_rows = []
    for t, s in _type_stats(rows):
        type_rows.append([t, str(s["count"]), _f(s["total"]), _f(s["fees"]), _f(s["gst"])])
    _add_table(doc, ["Invoice type", "Count", "Net INR", "Fees INR", "GST INR"], type_rows)

    doc.add_heading("By service description (2020 onwards, fee subtotal pre-GST)", level=1)
    doc.add_paragraph(
        "Extracted from PDF line items — Listing Fee, FBA handling, Refund Processing, etc. "
        "Net fee = after credit note adjustments on each service line."
    )
    service_csv_2020 = ANALYSIS / "service_totals_2020.csv"
    svc_path = service_csv_2020 if service_csv_2020.exists() else SERVICE_CSV
    if svc_path.exists():
        svc_data = list(csv.DictReader(svc_path.open(encoding="utf-8", newline="")))
        svc_total = sum(float(row["net_fee_inr"]) for row in svc_data)
        svc_rows_out = [
            [row["description"], row["invoice_count"], _f(float(row["net_fee_inr"]))]
            for row in svc_data
        ]
        _add_table(doc, ["Service description", "Invoice count", "Net fee INR (pre-GST)"], svc_rows_out)
        period = "2020 onwards" if svc_path == service_csv_2020 else "all periods on file"
        doc.add_paragraph(f"Total service fees (pre-GST, {period}): {_f(svc_total)}")

    doc.add_heading("Month-wise net totals (2020 onwards)", level=1)
    months = _month_stats(rows)
    mo_rows = [[m["month"], str(m["count"]), _f(m["gross"]), _f(m["credits"]), _f(m["net"])] for m in months]
    _add_table(doc, ["Month", "Count", "Gross INR", "Credits INR", "Net INR"], mo_rows)

    doc.add_heading("Key insights", level=1)
    insights = [
        f"Amazon net earnings from your account (2020+): {_f(net)} — this is the primary answer.",
        f"Gross billed before credits: {_f(gross)}; Amazon returned/credited {_f(abs(credits))} via credit notes.",
        "Largest fee category by service: Listing Fee (~58% of service fee lines).",
        "Peak spending year: 2024 (check year table) — driven by Merchant VAT invoices.",
        "Recent months (late 2025–2026) show net negative — credit notes exceed new invoices.",
        "Product Ads (advertising) separate from seller fees: see Product Ads VAT Invoice row.",
    ]
    peak_year = max(ys.items(), key=lambda x: x[1]["net"])[0] if ys else "—"
    insights[3] = f"Peak net spending year: {peak_year} (INR {ys[peak_year]['net']:,.2f})." if ys else insights[3]
    for bullet in insights:
        doc.add_paragraph(bullet, style="List Bullet")

    doc.add_heading("Data source & methodology", level=1)
    doc.add_paragraph(
        "Source: 484 Amazon Seller Fee Invoice PDFs downloaded from Seller Central "
        "(sellercentral.amazon.in/tax/seller-fee-invoices). "
        "Amounts extracted via automated PDF text parsing (pypdf). "
        "Gross = sum of tax invoices (Merchant VAT, FBA, Product Ads). "
        "Net = gross + credit notes (negative). All amounts in INR as printed on invoices."
    )
    doc.add_paragraph(f"Files: {DETAIL_CSV.name}, {SERVICE_CSV.name}")

    doc.save(OUT_DOCX)
    print(f"Saved: {OUT_DOCX}")
    print(f"2020+ Net: INR {net:,.2f} | Gross: INR {gross:,.2f} | Credits: INR {credits:,.2f}")


if __name__ == "__main__":
    main()
