import zipfile
import re
from pathlib import Path

for label, p in [
    ("backup", Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4)_backup.xlsm")),
    ("current", Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4).xlsm")),
]:
    print("===", label)
    with zipfile.ZipFile(p) as z:
        xml = z.read("xl/worksheets/sheet5.xml").decode("utf-8")
        for b in re.findall(r"<dataValidation[^>]*(?:/>|>.*?</dataValidation>)", xml, re.S):
            sq = re.search(r'sqref="([^"]*)"', b)
            if not sq:
                continue
            if "C" in sq.group(1):
                f1 = re.search(r"<formula1>([^<]*)</formula1>", b)
                f1a = re.search(r'formula1="([^"]*)"', b)
                val = (f1.group(1) if f1 else f1a.group(1) if f1a else "?")
                print(" ", sq.group(1), "->", val[:100])
