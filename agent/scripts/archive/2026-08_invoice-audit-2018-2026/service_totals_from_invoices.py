"""Aggregate Description of Service fee totals from seller fee invoice PDFs."""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

from pypdf import PdfReader

INV = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices\invoice")
OUT = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices\analysis\service_totals.csv")
FN_DATE_RE = re.compile(r"^(\d{4})-\d{2}-\d{2}_")

# Standard tax invoice summary: "1. 996812 Shipping Fee INR 66.80"
LINE_INVOICE = re.compile(
    r"(?m)^\s*\d+\.\s+(\d{6})\s+((?:[A-Za-z][A-Za-z0-9 \-/]*(?:\n[A-Za-z][A-Za-z0-9 \-/]*){0,2}?))"
    r"\s+(-?)INR\s+([\d,]+\.?\d*)\s*$"
)
# Credit note summary: "1. HR-2425-88037 01-31-2025 996812 FBA Weight Handling..."
LINE_CREDIT = re.compile(
    r"(?m)^\s*\d+\.\s+[A-Z0-9\-]+\s+\d{2}-\d{2}-\d{4}\s+(\d{6})\s+"
    r"((?:[A-Za-z][A-Za-z0-9 \-/]*(?:\n[A-Za-z][A-Za-z0-9 \-/]*){0,2}?))"
    r"\s+(-?)INR\s+([\d,]+\.?\d*)\s*$"
)


def norm_desc(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s


def amt(sign: str, num: str) -> float:
    v = float(num.replace(",", ""))
    return -v if sign == "-" else v


def invoice_year(filename: str) -> int | None:
    m = FN_DATE_RE.match(filename)
    return int(m.group(1)) if m else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate service fee totals from invoice PDFs.")
    parser.add_argument("--year-from", type=int, default=0, help="Only include invoices from this year onward.")
    parser.add_argument(
        "--out",
        type=Path,
        default=OUT,
        help="Output CSV path (default: analysis/service_totals.csv).",
    )
    args = parser.parse_args()

    by_service: dict[str, dict] = defaultdict(lambda: {"fee_inr": 0.0, "lines": 0, "invoices": set(), "sac": ""})
    by_sac: dict[str, dict] = defaultdict(lambda: {"fee_inr": 0.0, "lines": 0})

    pdfs = sorted(INV.glob("*.pdf"))
    for i, p in enumerate(pdfs):
        if args.year_from:
            yr = invoice_year(p.name)
            if yr is None or yr < args.year_from:
                continue
        try:
            text = "\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages)
        except Exception:
            continue
        text = text.replace("\uFFFD", " ")
        for m in list(LINE_INVOICE.finditer(text)) + list(LINE_CREDIT.finditer(text)):
            sac, desc, sign, num = m.group(1), m.group(2), m.group(3), m.group(4)
            desc_n = norm_desc(desc)
            if desc_n.upper().startswith(("IGST", "CGST", "SGST", "TOTAL")):
                continue
            if "Tax Rate" in desc_n or "Original Invoice" in desc_n:
                continue
            val = amt(sign, num)
            by_service[desc_n]["fee_inr"] += val
            by_service[desc_n]["lines"] += 1
            by_service[desc_n]["invoices"].add(p.name)
            by_service[desc_n]["sac"] = sac
            by_sac[sac]["fee_inr"] += val
            by_sac[sac]["lines"] += 1
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(pdfs)}")

    rows = sorted(by_service.items(), key=lambda x: abs(x[1]["fee_inr"]), reverse=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fp:
        fp.write("description,sac_code,line_count,invoice_count,net_fee_inr\n")
        for desc, d in rows:
            fp.write(f"\"{desc}\",{d['sac']},{d['lines']},{len(d['invoices'])},{d['fee_inr']:.2f}\n")

    yr_note = f" (year >= {args.year_from})" if args.year_from else ""
    print(f"Wrote {args.out}{yr_note}")
    print()
    print(f"{'Description':<50} {'Lines':>7} {'Inv':>5} {'Net INR':>14}")
    print("-" * 78)
    for desc, d in rows[:25]:
        print(f"{desc[:50]:<50} {d['lines']:>7} {len(d['invoices']):>5} {d['fee_inr']:>14,.2f}")
    grand = sum(d["fee_inr"] for _, d in rows)
    print("-" * 78)
    print(f"{'TOTAL (fees pre-GST, all services)':<50} {'':>7} {'':>5} {grand:>14,.2f}")


if __name__ == "__main__":
    main()
