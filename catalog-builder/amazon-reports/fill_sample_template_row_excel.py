"""Fill sample row in PHONE_ACCESSORY (4).xlsm via Excel COM.

Rules (from Valid Values / Dropdown Lists / Browse Data sheets):
  Col C — Listing Action (dropdown, exact string):
    • Create or Replace (Full Update)  → new listing
    • Edit (Partial Update)            → update existing
    • Delete                           → remove listing
  Col L — Recommended Browse Nodes (dropdown full path + node id):
    • Mobile screen parts → ... > Mobile Displays (11180541031)

Only row 7 is written. Rows 1–6 (headers / dropdown presets) are never touched.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import openpyxl
import win32com.client as win32

SOURCE = Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4)_backup.xlsm")
OUT = Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4).xlsm")
CAT = Path(
    r"C:\Projects\Amazon Systems Design\catalog-builder\amazon-reports"
    r"\Category+Listings+Report_05-12-2026.xlsm"
)
PROJECT_COPY = Path(__file__).parent / "PHONE_ACCESSORY_sample_row.xlsm"
SUMMARY = Path(__file__).parent / "PHONE_ACCESSORY_sample_row_summary.txt"
DATA_ROW = 7
DONOR_ROW = 56

# New 237-col template (row 4 labels)
T = {
    "sku": 1,
    "product_type": 2,
    "listing_action": 3,
    "item_name": 7,
    "brand": 9,
    "browse1": 12,
    "model_number": 17,
    "manufacturer": 18,
    "main_image": 21,
    "description": 31,
    "bullet1": 32,
    "keyword": 37,
    "num_items": 39,
    "item_type": 40,
    "part_number": 43,
    "compat1": 45,
    "hsn_entity": 57,
    "hsn": 58,
    "packer": 68,
    "condition": 77,
    "tax_code": 79,
    "max_order_qty": 81,
    "fulfillment": 101,
    "quantity": 102,
    "price": 106,
    "mrp": 107,
    "pkg_len": 140,
    "pkg_len_u": 141,
    "pkg_w": 142,
    "pkg_w_u": 143,
    "pkg_h": 144,
    "pkg_h_u": 145,
    "pkg_weight": 146,
    "pkg_weight_u": 147,
    "country": 149,
    "warranty": 150,
    "batteries_required": 153,
    "dangerous_goods": 176,
}

# Category report (591 cols) donor fields
C = {
    "manufacturer": 20,
    "main_image": 29,
    "num_items": 61,
    "item_type": 63,
    "hsn_entity": 114,
    "hsn": 115,
    "packer": 121,
    "condition": 395,
    "max_order_qty": 399,
    "fulfillment": 419,
    "pkg_len": 452,
    "pkg_len_u": 453,
    "pkg_w": 454,
    "pkg_w_u": 455,
    "pkg_h": 456,
    "pkg_h_u": 457,
    "pkg_weight": 458,
    "pkg_weight_u": 459,
    "country": 469,
    "warranty": 470,
    "batteries_required": 475,
    "dangerous_goods": 498,
}

LISTING_ACTION_CREATE = "Create or Replace (Full Update)"


def load_valid_values(path: Path) -> dict:
    """Read dropdown strings from template Valid Values sheet."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    vv = wb["Valid Values"]
    out: dict = {
        "listing_actions": [],
        "browse_nodes": [],
        "product_types": [],
        "conditions": [],
        "tax_codes": [],
        "hsn_entities": [],
        "batteries_required": [],
        "dangerous_goods": [],
        "fulfillment": [],
    }
    for c in range(3, vv.max_column + 1):
        v = vv.cell(3, c).value
        if v in ("Create or Replace (Full Update)", "Edit (Partial Update)", "Delete"):
            out["listing_actions"].append(v)
        v2 = vv.cell(2, c).value
        if v2 == "PHONE_ACCESSORY":
            out["product_types"].append(v2)
    for c in range(3, vv.max_column + 1):
        v = vv.cell(10, c).value
        if v and isinstance(v, str) and "(" in v and ">" in v:
            out["browse_nodes"].append(v)
    for c in range(3, 30):
        for row, key in ((19, "conditions"), (20, "tax_codes"), (13, "hsn_entities"),
                         (24, "batteries_required")):
            v = vv.cell(row, c).value
            if v and isinstance(v, str):
                out[key].append(v)
    # Fulfillment from Dropdown Lists col 18 area
    dl = wb["Dropdown Lists"]
    for r in range(4, 20):
        v = dl.cell(r, 18).value
        if v and "Fulfillment" in str(v) or v in ("AMAZON_IN",):
            pass
    for c in range(18, 22):
        v = dl.cell(4, c).value
        if v:
            out["fulfillment"].append(str(v))
    # row 18 in DL often has fulfillment channel
    for r in range(4, 12):
        v = dl.cell(r, 18).value
        if v and ("Merchant" in str(v) or "AMAZON" in str(v)):
            out["fulfillment"].append(str(v))
    wb.close()
    return out


def pick_browse_mobile_displays(browse_nodes: list[str]) -> str:
    for b in browse_nodes:
        if "Mobile Displays" in b and "11180541031" in b:
            return b
    raise ValueError("Mobile Displays browse node not in Valid Values")


def donor(cat_ws, col: int):
    return cat_ws.cell(DONOR_ROW, col).value


def make_bullets(title: str) -> list[str]:
    t = title.lower()
    tier = "gold" if "careog" in t else "silver" if "oled" in t else "bronze"
    fp = "fingerprint support" in t and "no fingerprint" not in t
    frame = "with frame" in t or "folder" in t
    m = re.search(r"compatible for\s+(.+?)(?:\s+\(|display)", title, re.I)
    model = m.group(1).strip() if m else "your phone"
    b1 = (
        f"Compatible with {model}"
        + (" — Fingerprint supported after fitting" if fp else " — Fingerprint not supported")
        + " — Verify model number from Settings before ordering"
    )
    tier_txt = {
        "gold": "Gold Tier CareOG — Tested OG combo with premium quality for professional repair.",
        "silver": "Silver Tier OLED — Premium display with vivid colors and better contrast.",
        "bronze": "Bronze Tier LCD — Budget friendly good quality display. Reliable performance.",
    }
    b3 = (
        "Quality Tested — Checked for dead pixels, color calibration, touch response."
        + (" With frame for easy installation." if frame else "")
    )
    return [
        b1[:255],
        tier_txt[tier][:255],
        b3[:255],
        "Professional installation recommended — Self-install without skills may damage device.",
        "7-Day replacement warranty — QC tested before dispatch. Film removal = acceptance.",
    ]


def build_row7_cells(valid: dict, cat_ws) -> dict[int, object]:
    sku = "SAMPLE-S21FE-OLED"
    title = (
        "Compatible for Samsung Galaxy S21 FE (Fingerprint Support) "
        "OLED Display+Touch Screen Combo Folder"
    )
    price, mrp, qty = 2586, 3700, 100
    bullets = make_bullets(title)
    browse = pick_browse_mobile_displays(valid["browse_nodes"])
    tax = "A_GEN_STANDARD"
    if tax not in valid["tax_codes"]:
        tax = valid["tax_codes"][0] if valid["tax_codes"] else "A_GEN_STANDARD"

    cells: dict[int, object] = {
        T["sku"]: sku,
        T["product_type"]: "PHONE_ACCESSORY",
        T["listing_action"]: LISTING_ACTION_CREATE,
        T["item_name"]: title,
        T["brand"]: "Generic",
        T["browse1"]: browse,
        T["model_number"]: sku,
        T["manufacturer"]: donor(cat_ws, C["manufacturer"]) or "Generic",
        T["main_image"]: donor(cat_ws, C["main_image"]),
        T["description"]: (
            "Compatible mobile phone OLED display and touch screen combo replacement. "
            "Tested for quality before dispatch. Professional installation recommended."
        ),
        T["keyword"]: "galaxy s21 fe oled display touch screen combo folder replacement",
        T["num_items"]: donor(cat_ws, C["num_items"]) or 1,
        T["item_type"]: donor(cat_ws, C["item_type"]) or "Mobile Screen Replacement Part",
        T["part_number"]: sku,
        T["compat1"]: "Samsung Galaxy S21 FE",
        T["hsn_entity"]: donor(cat_ws, C["hsn_entity"]) or "HSN Code",
        T["hsn"]: donor(cat_ws, C["hsn"]) or "851770",
        T["packer"]: donor(cat_ws, C["packer"]),
        T["condition"]: "New",
        T["tax_code"]: tax,
        T["max_order_qty"]: donor(cat_ws, C["max_order_qty"]) or 1,
        T["fulfillment"]: donor(cat_ws, C["fulfillment"]) or "Fulfillment by Merchant (Default)",
        T["quantity"]: qty,
        T["price"]: price,
        T["mrp"]: mrp,
        T["pkg_len"]: donor(cat_ws, C["pkg_len"]),
        T["pkg_len_u"]: donor(cat_ws, C["pkg_len_u"]),
        T["pkg_w"]: donor(cat_ws, C["pkg_w"]),
        T["pkg_w_u"]: donor(cat_ws, C["pkg_w_u"]),
        T["pkg_h"]: donor(cat_ws, C["pkg_h"]),
        T["pkg_h_u"]: donor(cat_ws, C["pkg_h_u"]),
        T["pkg_weight"]: donor(cat_ws, C["pkg_weight"]),
        T["pkg_weight_u"]: donor(cat_ws, C["pkg_weight_u"]),
        T["country"]: donor(cat_ws, C["country"]) or "China",
        T["warranty"]: donor(cat_ws, C["warranty"]),
        T["batteries_required"]: "No",
        T["dangerous_goods"]: donor(cat_ws, C["dangerous_goods"]) or "Not Applicable",
    }
    for i, b in enumerate(bullets):
        cells[T["bullet1"] + i] = b
    return cells


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)

    valid = load_valid_values(SOURCE)
    if LISTING_ACTION_CREATE not in valid["listing_actions"]:
        raise RuntimeError("Create action missing from Valid Values")

    cat_wb = openpyxl.load_workbook(CAT, read_only=True, data_only=True)
    cat_ws = cat_wb["Template"]
    cells = build_row7_cells(valid, cat_ws)
    cat_wb.close()

    shutil.copy2(SOURCE, OUT)

    excel = win32.DispatchEx("Excel.Application")
    try:
        excel.DisplayAlerts = False
    except AttributeError:
        pass
    try:
        wb = excel.Workbooks.Open(str(OUT.resolve()))
        ws = wb.Worksheets("Template")
        last_col = 237
        # Clear data row only — never rows 1-6
        ws.Range(ws.Cells(DATA_ROW, 1), ws.Cells(DATA_ROW, last_col)).ClearContents()
        for col, val in sorted(cells.items()):
            if val is not None and str(val).strip() != "":
                ws.Cells(DATA_ROW, col).Value = val
        wb.Save()
        wb.Close(SaveChanges=True)
    finally:
        excel.Quit()

    shutil.copy2(OUT, PROJECT_COPY)

    lines = [
        f"Output: {OUT}",
        f"Source: {SOURCE} (rows 1-6 untouched)",
        f"Data row: {DATA_ROW}",
        "",
        "Listing Action (col C) — dropdown values:",
        "  Create or Replace (Full Update)  → NEW listing (used in sample)",
        "  Edit (Partial Update)            → change existing listing",
        "  Delete                           → delete listing",
        "",
        f"Browse node (col L): {cells[T['browse1']]}",
        f"SKU: {cells[T['sku']]}",
        f"Price: {cells[T['price']]} MRP: {cells[T['mrp']]} Qty: {cells[T['quantity']]}",
        "",
        "Filled columns:",
    ]
    wb2 = openpyxl.load_workbook(OUT, read_only=True, data_only=True)
    ws2 = wb2["Template"]
    for c in range(1, ws2.max_column + 1):
        v = ws2.cell(DATA_ROW, c).value
        if v is not None and str(v).strip():
            lines.append(f"  col{c:3d} {ws2.cell(4, c).value}: {str(v)[:85]}")
    # verify header rows untouched
    lines += [
        "",
        "Header check (must be template defaults):",
        f"  C6={ws2.cell(6,3).value!r}",
        f"  L6={ws2.cell(6,12).value!r}",
    ]
    wb2.close()
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    print(SUMMARY)
    print(f"Size: {OUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
