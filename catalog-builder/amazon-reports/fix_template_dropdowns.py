"""Fix C/L dropdowns, blank images, preserve Sir row-7 data. Output analysis."""
from __future__ import annotations

from pathlib import Path

import openpyxl
import win32com.client as win32

FILE = Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4).xlsm")
BACKUP = Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4)_backup.xlsm")
ANALYSIS = Path(__file__).parent / "PHONE_ACCESSORY_fill_analysis.txt"
DATA_ROW = 7
IMAGE_COLS = list(range(21, 31))  # 21-30 all image URLs

LISTING_ACTIONS = (
    "Create or Replace (Full Update)",
    "Edit (Partial Update)",
    "Delete",
)

XL_VALIDATE_LIST = 3
XL_VALID_ALERT_STOP = 1


def read_row7(path: Path) -> dict[int, object]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["Template"]
    cells = {}
    for c in range(1, ws.max_column + 1):
        v = ws.cell(DATA_ROW, c).value
        if v is not None and str(v).strip():
            cells[c] = v
    wb.close()
    return cells


def write_analysis(cells: dict[int, object]) -> None:
    wb = openpyxl.load_workbook(FILE, read_only=True, data_only=True)
    ws = wb["Template"]
    dd = wb["Data Definitions"]

    dd_required: dict[int, str] = {}
    for r in range(4, dd.max_row + 1):
        field = dd.cell(r, 2).value
        req = dd.cell(r, 6).value
        if field and req and str(req).strip().lower() == "required":
            for c in range(1, ws.max_column + 1):
                if ws.cell(5, c).value == field:
                    dd_required[c] = str(dd.cell(r, 3).value or field)
                    break

    mandatory_create = {
        1: "SKU",
        2: "Product Type",
        3: "Listing Action",
        7: "Item Name",
        9: "Brand Name",
        12: "Recommended Browse Nodes",
        101: "Fulfillment Channel",
        102: "Quantity",
    }

    lines = [
        f"File: {FILE}",
        f"Row {DATA_ROW} — after fix",
        "",
        "=== Listing Action (col C) — dropdown rules ===",
        "  Create or Replace (Full Update)  → NEW listing",
        "  Edit (Partial Update)            → update existing",
        "  Delete                           → remove listing",
        f"  Current C7: {cells.get(3)!r}",
        "",
        "=== Images (cols 21-30) ===",
        "  LEFT BLANK per Sir — Amazon uses donor images on create or add later",
        "",
        "=== MANDATORY for CREATE ===",
    ]
    for col, name in sorted(mandatory_create.items()):
        v = cells.get(col)
        st = "OK" if v is not None and str(v).strip() else "MISSING"
        lines.append(f"  [{st}] col{col:3d} {name}: {str(v)[:75] if v else '-'}")

    lines.append("\n=== DATA DEFINITIONS Required ===")
    for col in sorted(dd_required):
        v = cells.get(col)
        st = "OK" if v is not None and str(v).strip() else "MISSING"
        lines.append(f"  [{st}] col{col:3d} {dd_required[col]}")

    filled_cols = sorted(cells)
    optional_filled = [c for c in filled_cols if c not in dd_required and c not in mandatory_create]
    blank_optional = [
        c for c in range(1, ws.max_column + 1)
        if c not in cells and c not in dd_required and c not in mandatory_create
    ]

    lines += [
        f"\n=== Sir filled (non-mandatory extras): {len(optional_filled)} cols ===",
    ]
    for c in optional_filled:
        lbl = ws.cell(4, c).value or f"col{c}"
        lines.append(f"  col{c:3d} {str(lbl)[:45]}: {str(cells[c])[:70]}")

    lines += [
        f"\n=== Blank & NOT mandatory: {len(blank_optional)} cols ===",
        "  (safe to leave empty for CREATE — sample):",
    ]
    for c in blank_optional[:35]:
        lbl = ws.cell(4, c).value or f"col{c}"
        lines.append(f"  col{c:3d} {lbl}")
    if len(blank_optional) > 35:
        lines.append(f"  ... +{len(blank_optional) - 35} more")

    lines += [
        "\n=== Verdict ===",
        "Ready for CREATE test upload if mandatory all OK.",
        "Product Id Type (col 10) = GTIN Exempt recommended when no barcode.",
    ]
    wb.close()
    ANALYSIS.write_text("\n".join(lines), encoding="utf-8")
    print(ANALYSIS)


def main() -> None:
    saved = read_row7(FILE)
    # Images blank
    for c in IMAGE_COLS:
        saved.pop(c, None)
    # Ensure create defaults
    saved[2] = "PHONE_ACCESSORY"
    saved[3] = LISTING_ACTIONS[0]
    if 10 not in saved:
        saved[10] = "GTIN Exempt"

    excel = win32.DispatchEx("Excel.Application")
    try:
        excel.DisplayAlerts = False
    except AttributeError:
        pass

    try:
        wb = excel.Workbooks.Open(str(FILE.resolve()))
        ws = wb.Worksheets("Template")

        # Re-apply listing-action dropdown on C7 (named range record_action)
        c_rng = ws.Range(f"C{DATA_ROW}:C1048576")
        try:
            c_rng.Validation.Delete()
        except Exception:
            pass
        c_rng.Validation.Add(
            Type=XL_VALIDATE_LIST,
            AlertStyle=XL_VALID_ALERT_STOP,
            Operator=1,
            Formula1="=record_action",
        )
        c_rng.Validation.IgnoreBlank = True
        c_rng.Validation.InCellDropdown = True

        # Product type first — L browse dropdown depends on B7
        ws.Cells(DATA_ROW, 2).Value = "PHONE_ACCESSORY"
        saved[2] = "PHONE_ACCESSORY"

        # Clear + set listing action via valid list value
        ws.Cells(DATA_ROW, 3).ClearContents()
        ws.Cells(DATA_ROW, 3).Value = LISTING_ACTIONS[0]

        # Blank all image columns
        for c in IMAGE_COLS:
            ws.Cells(DATA_ROW, c).ClearContents()

        # Write rest of Sir's data (skip C,B already set)
        skip = {2, 3, *IMAGE_COLS}
        for col, val in sorted(saved.items()):
            if col in skip:
                continue
            if val is not None and str(val).strip():
                ws.Cells(DATA_ROW, col).Value = val

        wb.Save()
        wb.Close(SaveChanges=True)
    finally:
        excel.Quit()

    final = read_row7(FILE)
    write_analysis(final)
    print(f"Fixed: C7 dropdown, images blank, col10 GTIN Exempt if needed")
    print(f"Size: {FILE.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
