"""Audit all figures in Amazon_Fee_Invoice_Summary docx against source CSVs."""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

from docx import Document

ANALYSIS = Path(r"c:\Projects\Amazon Systems Design\data\mahika\amazon-seller-invoices\analysis")
DETAIL = ANALYSIS / "invoice_detail_analysis.csv"
SERVICE_2020 = ANALYSIS / "service_totals_2020.csv"
DOCX = ANALYSIS / "Amazon_Fee_Invoice_Summary_2020_onwards.docx"

INVOICE_TYPES = {
    "Merchant VAT Invoice",
    "Fulfillment by Amazon Tax Invoice",
    "Product Ads VAT Invoice",
}
CREDIT_TYPES = {
    "Merchant VAT Credit Note",
    "Product Ads VAT Credit Note",
}


def flt(row: dict, key: str) -> float:
    v = row.get(key, "")
    return 0.0 if v in ("", None) else float(v)


def parse_inr(text: str) -> float | None:
    m = re.search(r"INR\s+(-?[\d,]+\.\d{2})", text)
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def main() -> int:
    rows = list(csv.DictReader(DETAIL.open(encoding="utf-8")))
    rows2020 = [r for r in rows if int(r["year"]) >= 2020]

    exp: dict = {}
    exp["gross_2020"] = sum(flt(r, "total_invoice_amount") for r in rows2020 if r["invoice_type"] in INVOICE_TYPES)
    exp["credits_2020"] = sum(flt(r, "total_invoice_amount") for r in rows2020 if r["invoice_type"] in CREDIT_TYPES)
    exp["net_2020"] = sum(flt(r, "total_invoice_amount") for r in rows2020)
    exp["fees_2020"] = sum(flt(r, "subtotal_fees") for r in rows2020)
    exp["gst_2020"] = sum(flt(r, "subtotal_gst") for r in rows2020)
    exp["count_2020"] = len(rows2020)
    exp["count_invoices_2020"] = sum(1 for r in rows2020 if r["invoice_type"] in INVOICE_TYPES)
    exp["gross_2020_positive"] = sum(
        flt(r, "total_invoice_amount")
        for r in rows2020
        if r["invoice_type"] not in CREDIT_TYPES and flt(r, "total_invoice_amount") >= 0
    )
    exp["credits_2020_year_col"] = sum(
        flt(r, "total_invoice_amount")
        for r in rows2020
        if r["invoice_type"] in CREDIT_TYPES or flt(r, "total_invoice_amount") < 0
    )
    exp["credits_all"] = sum(flt(r, "total_invoice_amount") for r in rows if r["invoice_type"] in CREDIT_TYPES)
    exp["net_all"] = sum(flt(r, "total_invoice_amount") for r in rows)

    ys: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "gross": 0.0, "credits": 0.0, "net": 0.0, "fees": 0.0, "gst": 0.0}
    )
    for r in rows2020:
        y = str(int(r["year"]))
        amt = flt(r, "total_invoice_amount")
        t = r["invoice_type"]
        ys[y]["count"] += 1
        ys[y]["net"] += amt
        ys[y]["fees"] += flt(r, "subtotal_fees")
        ys[y]["gst"] += flt(r, "subtotal_gst")
        if t in CREDIT_TYPES or amt < 0:
            ys[y]["credits"] += amt
        else:
            ys[y]["gross"] += amt

    exp["count_credits_2020"] = sum(1 for r in rows2020 if r["invoice_type"] in CREDIT_TYPES)

    exp["gross_all"] = sum(flt(r, "total_invoice_amount") for r in rows if r["invoice_type"] in INVOICE_TYPES)

    byt: dict[str, dict] = defaultdict(lambda: {"count": 0, "total": 0.0, "fees": 0.0, "gst": 0.0})
    for r in rows2020:
        t = r["invoice_type"]
        byt[t]["count"] += 1
        byt[t]["total"] += flt(r, "total_invoice_amount")
        byt[t]["fees"] += flt(r, "subtotal_fees")
        byt[t]["gst"] += flt(r, "subtotal_gst")

    bym: dict[str, dict] = defaultdict(lambda: {"count": 0, "gross": 0.0, "credits": 0.0, "net": 0.0})
    for r in rows2020:
        amt = flt(r, "total_invoice_amount")
        m = r["year_month"]
        bym[m]["count"] += 1
        bym[m]["net"] += amt
        if r["invoice_type"] in CREDIT_TYPES or amt < 0:
            bym[m]["credits"] += amt
        else:
            bym[m]["gross"] += amt

    svc = list(csv.DictReader(SERVICE_2020.open(encoding="utf-8")))
    exp["svc_total_2020"] = sum(float(r["net_fee_inr"]) for r in svc)
    exp["svc_rows"] = {
        r["description"]: {"count": int(r["invoice_count"]), "fee": float(r["net_fee_inr"])} for r in svc
    }

    doc = Document(str(DOCX))
    issues: list[str] = []
    ok: list[str] = []

    def chk(label: str, got: float | None, expected: float, tol: float = 0.01) -> None:
        if got is None:
            issues.append(f"FAIL {label}: missing in doc")
            return
        if abs(got - expected) <= tol:
            ok.append(f"OK   {label}")
        else:
            issues.append(
                f"FAIL {label}: doc={got:,.2f} expected={expected:,.2f} diff={got - expected:,.2f}"
            )

    # Table 0 — Gross vs Net
    for row in doc.tables[0].rows[1:]:
        metric = row.cells[0].text.strip()
        amt = parse_inr(row.cells[1].text)
        notes = row.cells[2].text.strip()
        if "Gross invoices" in metric:
            chk("Gross vs Net / Gross", amt, exp["gross_2020"])
        elif "Credit notes" in metric:
            chk("Gross vs Net / Credits", amt, exp["credits_2020"])
        elif metric == "Net paid to Amazon":
            chk("Gross vs Net / Net", amt, exp["net_2020"])
        elif "Fee subtotal" in metric:
            chk("Gross vs Net / Fees", amt, exp["fees_2020"])
        elif "GST component" in metric:
            chk("Gross vs Net / GST", amt, exp["gst_2020"])
        elif "Invoice count" in metric:
            c = int(row.cells[1].text.strip())
            if c != exp["count_2020"]:
                issues.append(f"FAIL count 2020+: doc={c} expected={exp['count_2020']}")
            else:
                ok.append("OK   count 2020+")
            if f"{exp['count_invoices_2020']} invoices" not in notes and "invoices" in notes:
                issues.append(
                    f"WARN notes invoice count stale: says '{notes}' expected {exp['count_invoices_2020']} invoices"
                )

    if abs(exp["gross_2020"] + exp["credits_2020"] - exp["net_2020"]) > 0.02:
        issues.append("FAIL internal: gross + credits != net")
    else:
        ok.append("OK   internal gross + credits = net")

    # Table 1 — All-time
    for row in doc.tables[1].rows[1:]:
        metric = row.cells[0].text.strip()
        amt = parse_inr(row.cells[1].text)
        if metric == "Gross invoices":
            chk("All-time / Gross", amt, exp["gross_all"])
        elif metric == "Credit notes":
            chk("All-time / Credits", amt, exp["credits_all"])
        elif "Net paid" in metric:
            chk("All-time / Net", amt, exp["net_all"])

    # Table 2 — Year-wise
    for row in doc.tables[2].rows[1:]:
        y = row.cells[0].text.strip()
        if y == "TOTAL":
            chk("Year TOTAL gross", parse_inr(row.cells[2].text), exp["gross_2020_positive"])
            chk("Year TOTAL credits", parse_inr(row.cells[3].text), exp["credits_2020_year_col"])
            chk("Year TOTAL net", parse_inr(row.cells[4].text), exp["net_2020"])
            chk("Year TOTAL fees", parse_inr(row.cells[5].text), exp["fees_2020"])
            chk("Year TOTAL gst", parse_inr(row.cells[6].text), exp["gst_2020"])
            if int(row.cells[1].text) != exp["count_2020"]:
                issues.append(f"FAIL Year TOTAL count doc={row.cells[1].text} exp={exp['count_2020']}")
        elif y in ys:
            s = ys[y]
            chk(f"Year {y} gross", parse_inr(row.cells[2].text), s["gross"])
            chk(f"Year {y} credits", parse_inr(row.cells[3].text), s["credits"])
            chk(f"Year {y} net", parse_inr(row.cells[4].text), s["net"])
            if int(row.cells[1].text) != s["count"]:
                issues.append(f"FAIL Year {y} count doc={row.cells[1].text} exp={s['count']}")

    # Table 3 — By type
    for row in doc.tables[3].rows[1:]:
        t = row.cells[0].text.strip()
        if t not in byt:
            continue
        s = byt[t]
        chk(f"Type {t} net", parse_inr(row.cells[2].text), s["total"])
        chk(f"Type {t} fees", parse_inr(row.cells[3].text), s["fees"])
        chk(f"Type {t} gst", parse_inr(row.cells[4].text), s["gst"])
        if int(row.cells[1].text) != s["count"]:
            issues.append(f"FAIL Type {t} count doc={row.cells[1].text} exp={s['count']}")

    # Table 4 — Services
    svc_doc_total = 0.0
    for row in doc.tables[4].rows[1:]:
        desc = row.cells[0].text.strip()
        c = int(row.cells[1].text)
        fee = parse_inr(row.cells[2].text)
        if desc not in exp["svc_rows"]:
            issues.append(f"FAIL service missing in CSV: {desc}")
            continue
        e = exp["svc_rows"][desc]
        if c != e["count"]:
            issues.append(f"FAIL service count {desc}: doc={c} exp={e['count']}")
        chk(f"Service {desc} fee", fee, e["fee"])
        if fee:
            svc_doc_total += fee
    chk("Service table sum", svc_doc_total, exp["svc_total_2020"])

    for p in doc.paragraphs:
        if "Total service fees" in p.text:
            chk("Service total paragraph", parse_inr(p.text), exp["svc_total_2020"])
        if "Net amount paid to Amazon" in p.text:
            chk("Executive net", parse_inr(p.text), exp["net_2020"])
        if p.text.startswith("Amazon net earnings"):
            chk("Insight net", parse_inr(p.text), exp["net_2020"])

    # Table 5 — Months
    for row in doc.tables[5].rows[1:]:
        m = row.cells[0].text.strip()
        if m not in bym:
            continue
        s = bym[m]
        chk(f"Month {m} net", parse_inr(row.cells[4].text), s["net"])
        chk(f"Month {m} gross", parse_inr(row.cells[2].text), s["gross"])
        chk(f"Month {m} credits", parse_inr(row.cells[3].text), s["credits"])
        if int(row.cells[1].text) != s["count"]:
            issues.append(f"FAIL Month {m} count doc={row.cells[1].text} exp={s['count']}")

    peak_year = max(ys.items(), key=lambda x: x[1]["net"])[0]
    listing_share = exp["svc_rows"].get("Listing Fee", {}).get("fee", 0) / exp["svc_total_2020"] * 100
    for p in doc.paragraphs:
        if "Peak net spending year" in p.text and peak_year not in p.text:
            issues.append(f"WARN peak year insight wrong: expected {peak_year}")
        elif "Peak net spending year" in p.text:
            ok.append(f"OK   peak year={peak_year}")
        if "Listing Fee (~58%" in p.text and abs(listing_share - 58) > 5:
            issues.append(f"WARN Listing Fee share is {listing_share:.1f}% not ~58%")
        elif "Listing Fee (~58%" in p.text:
            ok.append(f"OK   listing fee share ~{listing_share:.0f}%")

    warns: list[str] = []
    if abs(exp["gross_2020"] - exp["gross_2020_positive"]) > 0.02:
        warns.append(
            f"WARN methodology: Executive gross (INR {exp['gross_2020']:,.2f}) != year-table gross "
            f"(INR {exp['gross_2020_positive']:,.2f}); {47} negative invoice-type PDFs sit in year credits column"
        )
    if abs(exp["credits_2020"] - exp["credits_2020_year_col"]) > 0.02:
        warns.append(
            f"WARN methodology: Executive credits (INR {exp['credits_2020']:,.2f}) != year-table credits "
            f"(INR {exp['credits_2020_year_col']:,.2f})"
        )
    if abs(exp["fees_2020"] - exp["svc_total_2020"]) > 1000:
        warns.append(
            f"INFO service pre-GST total (INR {exp['svc_total_2020']:,.2f}) differs from invoice fee subtotal "
            f"(INR {exp['fees_2020']:,.2f}) — different aggregation basis"
        )

    fails = [i for i in issues if i.startswith("FAIL")]
    warns.extend(i for i in issues if not i.startswith("FAIL"))

    print("=== DOCX AUDIT ===")
    print(f"Passed: {len(ok)}")
    print(f"Failures: {len(fails)}")
    print(f"Warnings/Info: {len(warns)}")
    print()
    if fails:
        print("--- FAILURES ---")
        for f in fails:
            print(f)
    if warns:
        print("--- WARNINGS / INFO ---")
        for w in warns:
            print(w)
    print()
    print("--- KEY FIGURES (source truth) ---")
    print(f"2020+ Gross:     INR {exp['gross_2020']:,.2f}")
    print(f"2020+ Credits:   INR {exp['credits_2020']:,.2f}")
    print(f"2020+ Net:        INR {exp['net_2020']:,.2f}")
    print(f"2020+ Fees/GST:   INR {exp['fees_2020']:,.2f} / {exp['gst_2020']:,.2f}")
    print(f"2020+ Counts:    {exp['count_2020']} total ({exp['count_invoices_2020']} inv + {exp['count_credits_2020']} CN)")
    print(f"All-time Net:    INR {exp['net_all']:,.2f}")
    print(f"Service 2020+:   INR {exp['svc_total_2020']:,.2f} pre-GST")
    print(f"Listing share:   {listing_share:.1f}% of service fees")
    print(f"Peak year:       {peak_year} (net INR {ys[peak_year]['net']:,.2f})")

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
