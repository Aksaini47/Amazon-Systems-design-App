"""Parsers for Amazon Seller Central flat-file reports."""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def _read_lines(path: Path) -> list[str]:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode {path}")


def _parse_inr(value: str) -> float:
    """Parse ₹1,234.56 or Rs.1,234.00 or plain -76.70."""
    if not value or value.strip() in ("", "N/A"):
        return 0.0
    cleaned = value.strip().replace("₹", "").replace("Rs.", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_pct(value: str) -> float:
    if not value or value.strip() in ("", "N/A"):
        return 0.0
    cleaned = value.strip().replace("%", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


@dataclass
class BusinessSummary:
    days: int = 0
    total_sales_inr: float = 0.0
    total_units: int = 0
    total_sessions: int = 0
    total_refunds: int = 0
    conversion_pct: float = 0.0
    aov_inr: float = 0.0
    refund_rate_pct: float = 0.0
    monthly: list[str] = field(default_factory=list)


def parse_business_report(path: Path) -> BusinessSummary:
    lines = _read_lines(path)
    header_idx = None
    for i, line in enumerate(lines):
        cols = next(csv.reader([line]))
        if cols and cols[0].strip().lower() == "date" and "ordered product sales" in line.lower():
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"No business report header in {path.name}")

    reader = csv.DictReader(lines[header_idx:])
    monthly: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"sales": 0.0, "units": 0, "sessions": 0, "refunds": 0}
    )
    total_sales = 0.0
    total_units = 0
    total_sessions = 0
    total_refunds = 0
    days = 0

    for row in reader:
        date_raw = (row.get("Date") or "").strip()
        if not date_raw or not re.match(r"\d{2}/\d{2}/\d{2}", date_raw):
            continue
        days += 1
        sales = _parse_inr(row.get("Ordered Product Sales") or "")
        units = int(float((row.get("Units Ordered") or "0").replace(",", "") or 0))
        sessions = int(float((row.get("Sessions - Total") or "0").replace(",", "") or 0))
        refunds = int(float((row.get("Units Refunded") or "0").replace(",", "") or 0))
        total_sales += sales
        total_units += units
        total_sessions += sessions
        total_refunds += refunds
        try:
            dt = datetime.strptime(date_raw, "%d/%m/%y")
            key = dt.strftime("%Y-%m")
        except ValueError:
            key = date_raw[:7]
        bucket = monthly[key]
        bucket["sales"] = float(bucket["sales"]) + sales
        bucket["units"] = int(bucket["units"]) + units
        bucket["sessions"] = int(bucket["sessions"]) + sessions
        bucket["refunds"] = int(bucket["refunds"]) + refunds

    conv = (total_units / total_sessions * 100) if total_sessions else 0.0
    aov = (total_sales / total_units) if total_units else 0.0
    refund_rate = (total_refunds / total_units * 100) if total_units else 0.0

    monthly_lines = []
    for key in sorted(monthly.keys()):
        b = monthly[key]
        s, u, sess, ref = b["sales"], b["units"], b["sessions"], b["refunds"]
        m_conv = (u / sess * 100) if sess else 0.0
        m_aov = (s / u) if u else 0.0
        monthly_lines.append(
            f"{key}|{s:,.0f}|{u}|{sess}|{ref}|{m_conv:.1f}%|{m_aov:,.0f}"
        )

    return BusinessSummary(
        days=days,
        total_sales_inr=total_sales,
        total_units=total_units,
        total_sessions=total_sessions,
        total_refunds=total_refunds,
        conversion_pct=conv,
        aov_inr=aov,
        refund_rate_pct=refund_rate,
        monthly=monthly_lines,
    )


@dataclass
class PaymentSummary:
    rows: int = 0
    net_total_inr: float = 0.0
    product_sales_inr: float = 0.0
    selling_fees_inr: float = 0.0
    shipping_fees_inr: float = 0.0
    ad_spend_inr: float = 0.0
    transfers_inr: float = 0.0
    refunds_inr: float = 0.0
    order_count: int = 0


def parse_payment_unified(path: Path) -> PaymentSummary:
    lines = _read_lines(path)
    header_idx = None
    for i, line in enumerate(lines):
        if line.lower().startswith('"date/time"') or line.lower().startswith("date/time"):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"No payment header in {path.name}")

    reader = csv.DictReader(lines[header_idx:])
    net = product = selling = shipping = ads = transfers = refunds = 0.0
    order_ids: set[str] = set()
    rows = 0

    for row in reader:
        rows += 1
        typ = (row.get("type") or "").strip()
        order_id = (row.get("order id") or "").strip()
        total = _parse_inr(row.get("total") or "")
        net += total
        if typ == "Order" and order_id:
            order_ids.add(order_id)
            product += _parse_inr(row.get("product sales") or "")
        selling += _parse_inr(row.get("selling fees") or "")
        shipping += _parse_inr(row.get("other transaction fees") or "")
        if typ == "Service Fee" and "advertising" in (row.get("description") or "").lower():
            ads += abs(total)
        if typ == "Transfer":
            transfers += abs(total)
        if typ == "Refund" or typ == "Chargeback Refund":
            refunds += abs(total)

    return PaymentSummary(
        rows=rows,
        net_total_inr=net,
        product_sales_inr=product,
        selling_fees_inr=selling,
        shipping_fees_inr=shipping,
        ad_spend_inr=ads,
        transfers_inr=transfers,
        refunds_inr=refunds,
        order_count=len(order_ids),
    )


@dataclass
class ListingsSummary:
    total_skus: int = 0
    active_skus: int = 0
    inactive_skus: int = 0
    total_listed_qty: int = 0
    zero_qty_skus: int = 0
    avg_price_inr: float = 0.0


def parse_all_listings(path: Path) -> ListingsSummary:
    lines = _read_lines(path)
    if not lines:
        raise ValueError(f"Empty listings file {path.name}")
    header = lines[0].split("\t")
    try:
        sku_idx = header.index("seller-sku")
        price_idx = header.index("price")
        qty_idx = header.index("quantity")
        status_idx = header.index("status")
    except ValueError as exc:
        raise ValueError(f"Unexpected listings columns in {path.name}") from exc

    total = active = inactive = zero_qty = listed_qty = 0
    price_sum = 0.0
    priced = 0

    for line in lines[1:]:
        if not line.strip():
            continue
        cols = line.split("\t")
        if len(cols) <= status_idx:
            continue
        total += 1
        status = cols[status_idx].strip().lower()
        if status == "active":
            active += 1
        else:
            inactive += 1
        try:
            qty = int(float(cols[qty_idx] or 0))
        except ValueError:
            qty = 0
        listed_qty += max(qty, 0)
        if qty <= 0:
            zero_qty += 1
        try:
            price = float(cols[price_idx] or 0)
            if price > 0:
                price_sum += price
                priced += 1
        except ValueError:
            pass

    return ListingsSummary(
        total_skus=total,
        active_skus=active,
        inactive_skus=inactive,
        total_listed_qty=listed_qty,
        zero_qty_skus=zero_qty,
        avg_price_inr=(price_sum / priced) if priced else 0.0,
    )


@dataclass
class SalesDashboardSummary:
    date_label: str = ""
    order_items: int = 0
    units: int = 0
    sales_inr: float = 0.0
    yesterday_sales_inr: float = 0.0
    last_week_sales_inr: float = 0.0


def parse_sales_dashboard(path: Path) -> SalesDashboardSummary:
    lines = _read_lines(path)
    out = SalesDashboardSummary()
    for i, line in enumerate(lines):
        if line.startswith("Date,"):
            out.date_label = line.split(",", 1)[1].strip()
        if line.startswith("Total Order Items,Units Ordered,Ordered Product Sales"):
            if i + 1 < len(lines):
                parts = next(csv.reader([lines[i + 1]]))
                if len(parts) >= 3:
                    out.order_items = int(float(parts[0] or 0))
                    out.units = int(float(parts[1] or 0))
                    out.sales_inr = _parse_inr(parts[2])
        if line.startswith("Today so far,") or line.startswith("Today so far"):
            parts = next(csv.reader([line]))
            if len(parts) >= 4:
                out.sales_inr = _parse_inr(parts[3])
        if line.startswith("Yesterday,"):
            parts = next(csv.reader([line]))
            if len(parts) >= 4:
                out.yesterday_sales_inr = _parse_inr(parts[3])
        if line.startswith("Same day last week,"):
            parts = next(csv.reader([line]))
            if len(parts) >= 4:
                out.last_week_sales_inr = _parse_inr(parts[3])
    return out
