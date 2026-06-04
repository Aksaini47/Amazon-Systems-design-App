"""Scan + analyze Amazon report folders."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from mahika.config import settings
from mahika.reports.detect import ReportKind, detect_report
from mahika.reports import parsers


REPORT_GLOBS = ("*.csv", "*.txt", "*.tsv", "*.xlsx")


@dataclass
class ScanResult:
    path: Path
    kind: ReportKind


@dataclass
class AnalysisBundle:
    directory: Path
    scanned: list[ScanResult] = field(default_factory=list)
    business: parsers.BusinessSummary | None = None
    business_file: str | None = None
    payment: parsers.PaymentSummary | None = None
    payment_file: str | None = None
    listings: parsers.ListingsSummary | None = None
    listings_file: str | None = None
    dashboard: parsers.SalesDashboardSummary | None = None
    dashboard_file: str | None = None
    errors: list[str] = field(default_factory=list)


def _iter_report_files(directory: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in REPORT_GLOBS:
        files.extend(directory.glob(pattern))
    return sorted({p.resolve() for p in files if p.is_file()})


def scan_directory(directory: Path) -> list[ScanResult]:
    return [
        ScanResult(path=p, kind=detect_report(p))
        for p in _iter_report_files(directory)
    ]


def analyze_directory(directory: Path) -> AnalysisBundle:
    bundle = AnalysisBundle(directory=directory.resolve())
    for item in scan_directory(directory):
        bundle.scanned.append(item)
        path = item.path
        try:
            if item.kind == ReportKind.BUSINESS and bundle.business is None:
                bundle.business = parsers.parse_business_report(path)
                bundle.business_file = path.name
            elif item.kind == ReportKind.PAYMENT_UNIFIED and bundle.payment is None:
                bundle.payment = parsers.parse_payment_unified(path)
                bundle.payment_file = path.name
            elif item.kind == ReportKind.ALL_LISTINGS and bundle.listings is None:
                bundle.listings = parsers.parse_all_listings(path)
                bundle.listings_file = path.name
            elif item.kind == ReportKind.SALES_DASHBOARD and bundle.dashboard is None:
                bundle.dashboard = parsers.parse_sales_dashboard(path)
                bundle.dashboard_file = path.name
        except Exception as exc:
            bundle.errors.append(f"{path.name}: {exc}")
    return bundle


def format_summary(bundle: AnalysisBundle) -> str:
    lines = [
        "=== Mahika Reports Analysis ===",
        f"Directory: {bundle.directory}",
        f"Files scanned: {len(bundle.scanned)}",
        "",
    ]

    by_kind: dict[ReportKind, list[str]] = {}
    for item in bundle.scanned:
        by_kind.setdefault(item.kind, []).append(item.path.name)
    lines.append("Detected:")
    for kind in ReportKind:
        names = by_kind.get(kind)
        if names:
            lines.append(f"  {kind.value}: {', '.join(names)}")
    unknown = by_kind.get(ReportKind.UNKNOWN, [])
    if unknown:
        lines.append(f"  (unknown — skipped): {', '.join(unknown)}")
    lines.append("")

    if bundle.business:
        b = bundle.business
        lines.extend([
            f"--- Business report ({bundle.business_file}) ---",
            f"Days: {b.days} | Sales: Rs.{b.total_sales_inr:,.0f} | Units: {b.total_units}",
            f"Sessions: {b.total_sessions:,} | Refunds: {b.total_refunds}",
            f"Conv: {b.conversion_pct:.2f}% | AOV: Rs.{b.aov_inr:,.0f} | Refund rate: {b.refund_rate_pct:.1f}%",
            "",
            "Monthly (sales|units|sessions|refunds|conv|aov):",
        ])
        lines.extend(f"  {row}" for row in b.monthly)
        lines.append("")

    if bundle.payment:
        p = bundle.payment
        lines.extend([
            f"--- Payments unified ({bundle.payment_file}) ---",
            f"Rows: {p.rows:,} | Orders: {p.order_count:,}",
            f"Net total: Rs.{p.net_total_inr:,.2f}",
            f"Product sales: Rs.{p.product_sales_inr:,.2f} | Selling fees: Rs.{p.selling_fees_inr:,.2f}",
            f"Shipping/other fees: Rs.{p.shipping_fees_inr:,.2f} | Ad spend: Rs.{p.ad_spend_inr:,.2f}",
            f"Bank transfers: Rs.{p.transfers_inr:,.2f} | Refunds: Rs.{p.refunds_inr:,.2f}",
            "",
        ])

    if bundle.listings:
        li = bundle.listings
        lines.extend([
            f"--- All listings ({bundle.listings_file}) ---",
            f"SKUs: {li.total_skus} (active {li.active_skus}, inactive {li.inactive_skus})",
            f"Listed qty total: {li.total_listed_qty:,} | Zero-qty SKUs: {li.zero_qty_skus}",
            f"Avg active price: Rs.{li.avg_price_inr:,.0f}",
            "",
        ])

    if bundle.dashboard:
        d = bundle.dashboard
        lines.extend([
            f"--- Sales dashboard ({bundle.dashboard_file}) ---",
            f"Filter: {d.date_label or '(n/a)'}",
            f"Today: {d.order_items} orders, {d.units} units, Rs.{d.sales_inr:,.2f}",
            f"Yesterday sales: Rs.{d.yesterday_sales_inr:,.2f} | Same day last week: Rs.{d.last_week_sales_inr:,.2f}",
            "",
        ])

    if bundle.errors:
        lines.append("--- Parse errors ---")
        lines.extend(f"  ! {err}" for err in bundle.errors)
        lines.append("")

    missing = []
    if not bundle.business:
        missing.append("business_report")
    if not bundle.payment:
        missing.append("payment_unified")
    if not bundle.listings:
        missing.append("all_listings")
    if missing:
        lines.append(f"Missing (download from Seller Central): {', '.join(missing)}")
        lines.append("  Guide: specs/seller-reports/DOWNLOAD_GUIDE.md")

    return "\n".join(lines)


def ensure_report_dirs() -> None:
    for folder in (
        settings.reports_inbox_dir,
        settings.reports_archive_dir,
        settings.reports_analysis_dir,
    ):
        folder.mkdir(parents=True, exist_ok=True)


def write_summary(bundle: AnalysisBundle, text: str) -> Path:
    ensure_report_dirs()
    out = settings.reports_analysis_dir / f"summary-{date.today().isoformat()}.txt"
    out.write_text(text + "\n", encoding="utf-8")
    return out
