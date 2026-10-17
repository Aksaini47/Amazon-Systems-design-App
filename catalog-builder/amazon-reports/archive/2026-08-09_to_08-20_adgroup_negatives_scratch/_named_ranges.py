import zipfile
import re
import openpyxl
from pathlib import Path

for label, p in [
    ("backup", Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4)_backup.xlsm")),
    ("current", Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4).xlsm")),
]:
    print("===", label)
    with zipfile.ZipFile(p) as z:
        wbxml = z.read("xl/workbook.xml").decode()
    for m in re.finditer(r'<definedName[^>]*name="([^"]*record_action[^"]*)"[^>]*>([^<]*)</definedName>', wbxml):
        print(" definedName", m.group(1), "->", m.group(2))
    for m in re.finditer(r'<definedName[^>]*name="record_action"[^>]*>([^<]*)</definedName>', wbxml):
        print(" record_action ->", m.group(1))

    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    dl = wb["Dropdown Lists"]
    print(" DL col3 rows 2-8:")
    for r in range(2, 9):
        print(f"  r{r}", [dl.cell(r, c).value for c in range(2, 6)])
    print(" DL col3 rows 3-7 (listing):")
    for r in range(3, 8):
        print(f"  r{r}", dl.cell(r, 3).value)
    wb.close()
