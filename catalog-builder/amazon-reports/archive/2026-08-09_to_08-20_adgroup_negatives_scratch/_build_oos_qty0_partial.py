"""Build PHONE_ACCESSORY Partial Update xlsm for master OOS qty=0 SKUs only.
Writes ONLY to Template sheet (sheet5.xml).
Columns: A=SKU, B=Product Type, C=Listing Action,
         CX=Fulfillment Channel Code (IN)=DEFAULT, CY=Quantity (IN)=set_qty.
Restock intent: Quantity = master stock (1 or 2), NOT 0.
"""
from __future__ import annotations

import csv
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
ET.register_namespace("", NS["m"])
ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
ET.register_namespace("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006")
ET.register_namespace("x14ac", "http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac")
ET.register_namespace("xr", "http://schemas.microsoft.com/office/spreadsheetml/2014/revision")
ET.register_namespace("xr2", "http://schemas.microsoft.com/office/spreadsheetml/2015/revision2")
ET.register_namespace("xr3", "http://schemas.microsoft.com/office/spreadsheetml/2016/revision3")

ROOT = Path(__file__).resolve().parent
AUDIT = ROOT / "master_vs_all_listings_07-11-2026.csv"
SRC = Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (6).xlsm")
if not SRC.exists():
    SRC = ROOT / "PHONE_ACCESSORY_oos_partial_47.xlsm"
OUT = ROOT / "PHONE_ACCESSORY_oos_qty0_partial.xlsm"
OUT_MANIFEST = ROOT / "PHONE_ACCESSORY_oos_qty0_manifest.csv"
TEMPLATE_SHEET = "xl/worksheets/sheet5.xml"  # Template
FF_CHANNEL = "DEFAULT"  # MFN / Fulfillment by Merchant


def col_to_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def letter_to_col(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def load_shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    out = []
    for si in root.findall("m:si", NS):
        texts = [
            t.text or ""
            for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
        ]
        out.append("".join(texts))
    return out


def cell_value(c, ss: list[str]) -> str:
    if c.get("t") == "inlineStr":
        ts = [
            t.text or ""
            for t in c.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
        ]
        return "".join(ts)
    v = c.find("m:v", NS)
    if v is None or v.text is None:
        return ""
    if c.get("t") == "s":
        try:
            return ss[int(v.text)]
        except Exception:
            return v.text
    return v.text


def find_header_col(sheet, ss: list[str], *predicates) -> int | None:
    for row in sheet.findall("m:sheetData/m:row", NS):
        if row.get("r") not in ("4", "5"):
            continue
        for c in row.findall("m:c", NS):
            val = cell_value(c, ss).lower().strip()
            ref = c.get("r", "")
            m = re.match(r"([A-Z]+)", ref)
            if not m:
                continue
            if any(p(val) for p in predicates):
                return letter_to_col(m.group(1))
    return None


def find_qty_col(sheet, ss: list[str]) -> int:
    # Exact stock qty field only — NOT Maximum Order Quantity / B2B qty
    n = find_header_col(
        sheet,
        ss,
        lambda v: v == "quantity (in)" or v.startswith("quantity (in)"),
        lambda v: v == "fulfillment_availability#1.quantity",
    )
    return n if n is not None else 103  # CY on PHONE_ACCESSORY (6).xlsm


def find_ff_channel_col(sheet, ss: list[str]) -> int:
    n = find_header_col(
        sheet,
        ss,
        lambda v: "fulfillment channel code" in v,
        lambda v: "fulfillment_channel_code" in v,
    )
    return n if n is not None else 102  # CX on PHONE_ACCESSORY (6).xlsm


def qty0_rows_from_audit() -> list[dict]:
    rows = []
    with AUDIT.open(encoding="utf-8", newline="") as f:
        for rec in csv.DictReader(f):
            if rec["classification"] != "OUT_OF_STOCK":
                continue
            try:
                lq = int(rec["listing_qty"] or "0")
            except ValueError:
                lq = 0
            if lq != 0:
                continue
            try:
                mq = int(rec["qty"] or "1")
            except ValueError:
                mq = 1
            rows.append(
                {
                    "brand": rec["brand"],
                    "model": rec["model"],
                    "sku": rec["listing_sku"],
                    "asin": rec["listing_asin"],
                    "set_qty": mq,
                    "listing_title": rec["listing_title"],
                }
            )
    by_sku: dict[str, dict] = {}
    for r in rows:
        sku = r["sku"]
        if not sku:
            continue
        if sku not in by_sku or r["set_qty"] > by_sku[sku]["set_qty"]:
            by_sku[sku] = r
    out = list(by_sku.values())
    out.sort(key=lambda x: (x["brand"], x["model"]))
    return out


def clear_data_rows(sheet) -> None:
    sd = sheet.find("m:sheetData", NS)
    for row in list(sd.findall("m:row", NS)):
        r = int(row.get("r", "0"))
        if r >= 7:
            sd.remove(row)


def make_cell(ref: str, value, as_string: bool = False):
    c = ET.Element("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c")
    c.set("r", ref)
    if as_string:
        c.set("t", "inlineStr")
        is_el = ET.SubElement(c, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is")
        t_el = ET.SubElement(is_el, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
        # escape handled by ET
        if isinstance(value, str) and value.startswith("="):
            t_el.text = value
        else:
            t_el.text = str(value)
    else:
        v = ET.SubElement(c, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
        v.text = str(value)
    return c


def write_rows(sheet, items: list[dict], ff_col: int, qty_col: int) -> None:
    sd = sheet.find("m:sheetData", NS)
    ff_letter = col_to_letter(ff_col)
    qty_letter = col_to_letter(qty_col)
    for i, item in enumerate(items):
        r = 7 + i
        row = ET.Element("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row")
        row.set("r", str(r))
        row.append(make_cell(f"A{r}", item["sku"], as_string=True))
        row.append(make_cell(f"B{r}", "PHONE_ACCESSORY", as_string=True))
        row.append(make_cell(f"C{r}", "Edit (Partial Update)", as_string=True))
        row.append(make_cell(f"{ff_letter}{r}", FF_CHANNEL, as_string=True))
        row.append(make_cell(f"{qty_letter}{r}", item["set_qty"], as_string=False))
        sd.append(row)


def build(src: Path, items: list[dict], dest: Path) -> tuple[int, int]:
    if dest.exists():
        dest.unlink()
    shutil.copy2(src, dest)
    tmp = dest.with_suffix(".zipbuild")
    if tmp.exists():
        tmp.unlink()

    with zipfile.ZipFile(dest, "r") as zin:
        ss = load_shared_strings(zin)
        sheet = ET.fromstring(zin.read(TEMPLATE_SHEET))
        ff_col = find_ff_channel_col(sheet, ss)
        qty_col = find_qty_col(sheet, ss)
        print(
            f"Template ff_col={ff_col} ({col_to_letter(ff_col)}) "
            f"qty_col={qty_col} ({col_to_letter(qty_col)})"
        )
        # show headers
        ff_l = col_to_letter(ff_col)
        qty_l = col_to_letter(qty_col)
        for row in sheet.findall("m:sheetData/m:row", NS):
            if row.get("r") in ("3", "4", "5", "6", "7"):
                bits = []
                for c in row.findall("m:c", NS):
                    ref = c.get("r", "")
                    if (
                        re.match(r"^[ABC]\d+$", ref)
                        or ref.startswith(ff_l)
                        or ref.startswith(qty_l)
                    ):
                        bits.append(f"{ref}={cell_value(c, ss)[:50]}")
                if bits:
                    print(" ", bits)
        clear_data_rows(sheet)
        write_rows(sheet, items, ff_col, qty_col)
        sheet_xml = ET.tostring(sheet, encoding="utf-8", xml_declaration=True)

        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == TEMPLATE_SHEET:
                    data = sheet_xml
                zout.writestr(info, data)

    dest.unlink()
    tmp.rename(dest)
    return ff_col, qty_col


def verify(path: Path, expect_n: int) -> None:
    with zipfile.ZipFile(path) as z:
        # Confirm Template is sheet5, not Instructions (sheet1)
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheets = []
        for sh in wb.findall("m:sheets/m:sheet", NS):
            sheets.append((sh.get("name"), sh.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")))
        print("Workbook sheets:", sheets)
        assert any(n == "Template" for n, _ in sheets), "Template sheet missing"

        ss = load_shared_strings(z)
        sheet = ET.fromstring(z.read(TEMPLATE_SHEET))
        ff_col = find_ff_channel_col(sheet, ss)
        qty_col = find_qty_col(sheet, ss)
        fl = col_to_letter(ff_col)
        ql = col_to_letter(qty_col)
        assert fl == "CX", f"expected CX for fulfillment channel, got {fl}"
        assert ql == "CY", f"expected CY for quantity, got {ql}"
        data = []
        for row in sheet.findall("m:sheetData/m:row", NS):
            r = int(row.get("r", "0"))
            if r < 7:
                continue
            cells = {}
            for c in row.findall("m:c", NS):
                ref = c.get("r", "")
                m = re.match(r"([A-Z]+)", ref)
                if not m:
                    continue
                cells[m.group(1)] = cell_value(c, ss)
            data.append(
                (
                    r,
                    cells.get("A", ""),
                    cells.get("B", ""),
                    cells.get("C", ""),
                    cells.get(fl, ""),
                    cells.get(ql, ""),
                )
            )
        print(f"VERIFY Template sheet5: rows={len(data)} expect={expect_n} ff={fl} qty={ql}")
        for r, a, b, c, ff, q in data:
            print(f"  {r}: {a} | {b} | {c} | ff={ff} | qty={q}")
        assert len(data) == expect_n
        assert all(
            x[1]
            and x[2] == "PHONE_ACCESSORY"
            and "Partial" in x[3]
            and x[4] == FF_CHANNEL
            and str(x[5]).isdigit()
            and int(x[5]) > 0
            for x in data
        ), "row validation failed (need DEFAULT + qty>0)"


def items_from_manifest() -> list[dict] | None:
    if not OUT_MANIFEST.exists():
        return None
    with OUT_MANIFEST.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    for r in rows:
        r["set_qty"] = int(r["set_qty"])
    return rows


def main():
    print("SRC", SRC)
    items = items_from_manifest() or qty0_rows_from_audit()
    print(f"QTY0 SKUs: {len(items)}")
    for it in items:
        print(f"  {it['sku']} <- {it.get('model', '')} qty={it['set_qty']}")

    with OUT_MANIFEST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(items[0].keys()))
        w.writeheader()
        w.writerows(items)

    build(SRC, items, OUT)
    print("WROTE", OUT)
    verify(OUT, len(items))
    downloads = Path(r"C:\Users\DELL\Downloads") / OUT.name
    shutil.copy2(OUT, downloads)
    print("COPIED", downloads)


if __name__ == "__main__":
    main()
