import zipfile
import re
from pathlib import Path

src = Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4)_backup.xlsm")
with zipfile.ZipFile(src) as z:
    wb = z.read("xl/workbook.xml").decode("utf-8")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    sheets = re.findall(r'<sheet[^>]+name="([^"]+)"[^>]+r:id="([^"]+)"', wb)
    print("sheets:", sheets)
    for name, rid in sheets:
        m = re.search(rf'Id="{rid}"[^>]+Target="([^"]+)"', rels)
        if m:
            print(name, "->", m.group(1))
    names = z.namelist()
    print("vba:", [n for n in names if "vba" in n.lower()][:5])
    print("size", src.stat().st_size)
