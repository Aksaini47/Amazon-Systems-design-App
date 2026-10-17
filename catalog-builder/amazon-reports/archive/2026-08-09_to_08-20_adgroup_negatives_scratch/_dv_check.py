import zipfile
import re
from pathlib import Path

p = Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4)_backup.xlsm")
with zipfile.ZipFile(p) as z:
    xml = z.read("xl/worksheets/sheet5.xml").decode("utf-8")
    blocks = re.findall(r"<dataValidation[^>]*(?:/>|>.*?</dataValidation>)", xml, re.S)
    for b in blocks:
        sq = re.search(r'sqref="([^"]*)"', b)
        f1 = re.search(r'formula1="([^"]*)"', b)
        if sq and sq.group(1) in ("C4", "L4", "C7", "L7"):
            print("FIXED", sq.group(1), "|", (f1.group(1) if f1 else "?"))
    for b in blocks:
        sq = re.search(r'sqref="([^"]*)"', b)
        if sq and "7" in sq.group(1):
            f1 = re.search(r'formula1="([^"]*)"', b)
            print(sq.group(1)[:70], "|", (f1.group(1)[:90] if f1 else "?"))
