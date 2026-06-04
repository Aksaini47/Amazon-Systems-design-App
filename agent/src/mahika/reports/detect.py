"""Sniff Amazon Seller Central report files by content + filename."""
from __future__ import annotations

import csv
from enum import Enum
from pathlib import Path


class ReportKind(str, Enum):
    BUSINESS = "business_report"
    PAYMENT_UNIFIED = "payment_unified"
    ALL_LISTINGS = "all_listings"
    SALES_DASHBOARD = "sales_dashboard"
    ALL_ORDERS = "all_orders"
    RETURNS = "returns"
    UNKNOWN = "unknown"


def _read_head(path: Path, max_lines: int = 20) -> list[str]:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with path.open(encoding=encoding) as fh:
                return [line.rstrip("\n\r") for _, line in zip(range(max_lines), fh)]
        except UnicodeDecodeError:
            continue
    return []


def _first_csv_row(line: str) -> list[str]:
    try:
        return next(csv.reader([line]))
    except csv.Error:
        return line.split(",")


def detect_report(path: Path) -> ReportKind:
    """Return report kind for a single file."""
    name = path.name.lower()
    head = _read_head(path)
    joined = "\n".join(head).lower()

    if "custom unified transaction" in joined or "customunifiedtransaction" in name:
        return ReportKind.PAYMENT_UNIFIED
    if "all amounts in inr" in joined and "settlement id" in joined:
        return ReportKind.PAYMENT_UNIFIED

    if name.startswith("businessreport") or "ordered product sales" in joined:
        for line in head:
            cols = _first_csv_row(line)
            if cols and cols[0].strip().lower() == "date" and "ordered product sales" in line.lower():
                return ReportKind.BUSINESS

    if "all+listings+report" in name or (
        head and head[0].startswith("item-name\t") and "seller-sku" in head[0]
    ):
        return ReportKind.ALL_LISTINGS

    if name.startswith("salesdashboard") or head[:1] == ["Sales Dashboard"]:
        return ReportKind.SALES_DASHBOARD

    if "return" in name and ("return-date" in joined or "return request date" in joined):
        return ReportKind.RETURNS

    if "order" in name and ("amazon-order-id" in joined or "order-id" in joined):
        return ReportKind.ALL_ORDERS

    return ReportKind.UNKNOWN
