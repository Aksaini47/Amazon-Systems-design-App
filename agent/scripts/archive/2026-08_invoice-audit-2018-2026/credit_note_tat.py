"""Compute credit note TAT: days from original invoice date to credit note date."""
from __future__ import annotations

import csv
import re
import statistics
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

INV = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices\invoice")
DETAIL = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices\analysis\invoice_detail_analysis.csv")
OUT_CSV = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices\analysis\credit_note_tat.csv")

CN_DATE_RE = re.compile(r"Credit Note Date:\s*(\d{2}/\d{2}/\d{4})", re.I)
# Line: "1. KA-2021-134900 06-30-2020 998599 ..."
ORIG_LINE_RE = re.compile(
    r"(?m)^\s*\d+\.\s+([A-Z0-9\-]+)\s+(\d{2}-\d{2}-\d{4})\s+\d{6}\s+",
)
ORIG_NUM_RE = re.compile(r"Original Invoice Number:\s*([A-Z0-9\-]+)", re.I)
FN_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_")


def parse_cn_date(text: str, filename: str) -> datetime | None:
    m = CN_DATE_RE.search(text)
    if m:
        return datetime.strptime(m.group(1), "%d/%m/%Y")
    m2 = FN_DATE_RE.match(filename)
    if m2:
        return datetime.strptime(m2.group(1), "%Y-%m-%d")
    return None


def parse_orig_date_mmddyyyy(s: str) -> datetime:
    return datetime.strptime(s, "%m-%d-%Y")


def load_invoice_dates() -> dict[str, datetime]:
    lookup: dict[str, datetime] = {}
    with DETAIL.open(encoding="utf-8", newline="") as fp:
        for row in csv.DictReader(fp):
            lookup[row["invoice_id"]] = datetime.strptime(row["end_date"], "%Y-%m-%d")
    return lookup


def main() -> None:
    inv_dates = load_invoice_dates()
    credit_pdfs = sorted(p for p in INV.glob("*.pdf") if "Credit_Note" in p.name)

    line_tats: list[int] = []
    cn_summaries: list[dict] = []

    for p in credit_pdfs:
        text = "\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages)
        cn_dt = parse_cn_date(text, p.name)
        if not cn_dt:
            continue

        orig_pairs: list[tuple[str, datetime]] = []
        for m in ORIG_LINE_RE.finditer(text):
            orig_id, orig_d = m.group(1), m.group(2)
            orig_pairs.append((orig_id, parse_orig_date_mmddyyyy(orig_d)))

        if not orig_pairs:
            for m in ORIG_NUM_RE.finditer(text):
                oid = m.group(1).strip()
                if oid in inv_dates:
                    orig_pairs.append((oid, inv_dates[oid]))

        if not orig_pairs:
            continue

        days_list = [(cn_dt - od).days for _, od in orig_pairs]
        line_tats.extend(days_list)

        cn_summaries.append({
            "credit_note_id": p.stem.split("_")[-1],
            "credit_note_file": p.name,
            "credit_note_date": cn_dt.strftime("%Y-%m-%d"),
            "line_count": len(days_list),
            "min_days": min(days_list),
            "max_days": max(days_list),
            "avg_days": round(statistics.mean(days_list), 1),
            "orig_invoices": "; ".join(f"{i}:{d.strftime('%Y-%m-%d')}" for i, d in orig_pairs[:5]),
        })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(cn_summaries[0].keys()) if cn_summaries else [])
        w.writeheader()
        w.writerows(cn_summaries)

    print(f"Credit notes analyzed: {len(cn_summaries)}")
    print(f"Line-level TAT samples: {len(line_tats)}")
    if line_tats:
        print(f"MIN days:  {min(line_tats)}")
        print(f"MAX days:  {max(line_tats)}")
        print(f"AVG days:  {statistics.mean(line_tats):.1f}")
        print(f"MEDIAN:    {statistics.median(line_tats):.1f}")
    if cn_summaries:
        cn_avgs = [c["avg_days"] for c in cn_summaries]
        print(f"Per-CN avg of line TATs — MIN: {min(cn_avgs)}  MAX: {max(cn_avgs)}  AVG: {statistics.mean(cn_avgs):.1f}")
    print(f"CSV: {OUT_CSV}")


if __name__ == "__main__":
    main()
