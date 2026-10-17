"""Remove AI-generated image URLs from template — keep Mongo-matched images only."""
from __future__ import annotations

import csv
from pathlib import Path

import openpyxl
import pythoncom
import win32com.client as win32

TEMPLATE = Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4).xlsm")
REPORT = Path(__file__).parent / "bulk_25_image_match_report.csv"
GEN_PREFIX = "/products/GEN_"
SKIP_SKUS = {
    "RMREALMEC6LCD",
    "OPF17PROOLED",
    "MXMOTOG34WF",
    "MXASUSROGPLCD",
}
DATA_START = 7
COL_SKU = 1
COL_IMG_START = 21
COL_IMG_END = 30


def clear_generated_urls() -> list[str]:
    cleared: list[str] = []
    pythoncom.CoInitialize()
    excel = win32.DispatchEx("Excel.Application")
    try:
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(str(TEMPLATE.resolve()))
        ws = wb.Worksheets("Template")
        for r in range(DATA_START, DATA_START + 25):
            sku = str(ws.Cells(r, COL_SKU).Value or "").strip().upper()
            if sku not in SKIP_SKUS:
                continue
            had = False
            for c in range(COL_IMG_START, COL_IMG_END + 1):
                val = ws.Cells(r, c).Value
                if val and GEN_PREFIX in str(val):
                    had = True
                ws.Cells(r, c).ClearContents()
            if had:
                cleared.append(sku)
        wb.Save()
        wb.Close(SaveChanges=True)
    finally:
        excel.Quit()
        pythoncom.CoUninitialize()
    return cleared


def refresh_report() -> None:
    wb = openpyxl.load_workbook(TEMPLATE, read_only=True, data_only=True)
    ws = wb["Template"]
    rows = list(csv.DictReader(REPORT.open(encoding="utf-8")))
    by_sku = {r["sku"]: r for r in rows}
    for r in range(DATA_START, DATA_START + 25):
        sku = str(ws.cell(r, COL_SKU).value or "").strip()
        if not sku or sku not in by_sku:
            continue
        imgs = [ws.cell(r, c).value for c in range(COL_IMG_START, COL_IMG_END + 1) if ws.cell(r, c).value]
        by_sku[sku]["images"] = str(len(imgs))
        if imgs:
            by_sku[sku]["matched_product"] = by_sku[sku].get("matched_product") or "(mongo)"
            flags = by_sku[sku].get("flags", "")
            if sku in SKIP_SKUS:
                by_sku[sku]["flags"] = "ai_images_skipped"
            elif flags == "ai_images_skipped":
                by_sku[sku]["flags"] = by_sku[sku].get("flags", "")
        else:
            if sku in SKIP_SKUS:
                by_sku[sku]["flags"] = "no_image_ai_skipped"
    wb.close()
    out = list(by_sku.values())
    with REPORT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out[0].keys())
        w.writeheader()
        w.writerows(out)


def main() -> None:
    taskkill_msg = clear_generated_urls()
    print("Cleared GEN URLs for:", taskkill_msg or list(SKIP_SKUS))
    refresh_report()
    print("Report updated:", REPORT)

    wb = openpyxl.load_workbook(TEMPLATE, read_only=True, data_only=True)
    ws = wb["Template"]
    with_img = sum(
        1
        for r in range(DATA_START, DATA_START + 25)
        if any(ws.cell(r, c).value for c in range(COL_IMG_START, COL_IMG_END + 1))
    )
    wb.close()
    print(f"Final: {with_img}/25 rows with Mongo images, {25 - with_img} blank (manual later)")


if __name__ == "__main__":
    main()
