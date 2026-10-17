"""Compare service line totals vs invoice header fee subtotals."""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

from pypdf import PdfReader

DETAIL = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices\analysis\invoice_detail_analysis.csv")
SERVICE = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices\analysis\service_totals_2020.csv")
INV = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices\invoice")

LINE_INVOICE = re.compile(
    r"(?m)^\s*\d+\.\s+(\d{6})\s+((?:[A-Za-z][A-Za-z0-9 \-/]*(?:\n[A-Za-z][A-Za-z0-9 \-/]*){0,2}?))"
    r"\s+(-?)INR\s+([\d,]+\.?\d*)\s*$"
)
LINE_CREDIT = re.compile(
    r"(?m)^\s*\d+\.\s+[A-Z0-9\-]+\s+\d{2}-\d{2}-\d{4}\s+(\d{6})\s+"
    r"((?:[A-Za-z][A-Za-z0-9 \-/]*(?:\n[A-Za-z][A-Za-z0-9 \-/]*){0,2}?))"
    r"\s+(-?)INR\s+([\d,]+\.?\d*)\s*$"
)


def parse_lines(text: str) -> float:
    total = 0.0
    for m in list(LINE_INVOICE.finditer(text)) + list(LINE_CREDIT.finditer(text)):
        desc = re.sub(r"\s+", " ", m.group(2)).strip()
        if desc.upper().startswith(("IGST", "CGST", "SGST", "TOTAL")):
            continue
        if "Tax Rate" in desc or "Original Invoice" in desc:
            continue
        sign, num = m.group(3), m.group(4)
        v = float(num.replace(",", ""))
        total += -v if sign == "-" else v
    return total


def main() -> None:
    rows = [r for r in csv.DictReader(DETAIL.open(encoding="utf-8")) if int(r["year"]) >= 2020]
    fees_header = sum(float(r["subtotal_fees"] or 0) for r in rows)
    svc = list(csv.DictReader(SERVICE.open(encoding="utf-8")))
    svc_total = sum(float(r["net_fee_inr"]) for r in svc)

    print("=== COMPARISON (2020+) ===")
    print(f"Invoice header fee subtotal:  INR {fees_header:,.2f}")
    print(f"Service line sum (CSV):         INR {svc_total:,.2f}")
    print(f"Gap:                            INR {fees_header - svc_total:,.2f}")
    print()

    # Per-invoice reconciliation
    by_file = {r["filename"]: float(r["subtotal_fees"] or 0) for r in rows}
    diffs = []
    lines_missed = 0
    for p in sorted(INV.glob("*.pdf")):
        if not p.name[:4].isdigit() or int(p.name[:4]) < 2020:
            continue
        header = by_file.get(p.name)
        if header is None:
            continue
        try:
            text = "\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages)
        except Exception:
            continue
        lines = parse_lines(text.replace("\uFFFD", " "))
        diff = header - lines
        if abs(diff) > 0.05:
            diffs.append((p.name, header, lines, diff))

    diffs.sort(key=lambda x: abs(x[3]), reverse=True)
    print(f"Invoices with header != parsed lines: {len(diffs)} / {len(by_file)}")
    print(f"Sum of per-invoice gaps: INR {sum(d[3] for d in diffs):,.2f}")
    print()
    print("Top 10 gaps (header - lines):")
    for name, h, l, d in diffs[:10]:
        print(f"  {d:>12,.2f}  header={h:,.2f} lines={l:,.2f}  {name[:55]}")

    # By invoice type
    print()
    print("Gap by invoice type:")
    type_gap: dict[str, float] = defaultdict(float)
    type_count: dict[str, int] = defaultdict(int)
    lookup = {r["filename"]: r["invoice_type"] for r in rows}
    for name, h, l, d in diffs:
        t = lookup.get(name, "?")
        type_gap[t] += d
        type_count[t] += 1
    for t, g in sorted(type_gap.items(), key=lambda x: abs(x[1]), reverse=True):
        print(f"  {t}: INR {g:,.2f} ({type_count[t]} invoices)")


if __name__ == "__main__":
    main()
