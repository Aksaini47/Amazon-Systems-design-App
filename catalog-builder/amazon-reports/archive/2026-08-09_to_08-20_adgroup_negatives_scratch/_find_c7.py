import zipfile
from pathlib import Path

p = Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4)_backup.xlsm")
with zipfile.ZipFile(p) as z:
    xml = z.read("xl/worksheets/sheet5.xml").decode("utf-8")
    print("C7 count", xml.count("C7"))
    idx = 0
    while True:
        i = xml.find("C7", idx)
        if i < 0:
            break
        print(xml[max(0, i - 80) : i + 120])
        idx = i + 2
