import zipfile
from pathlib import Path

p = Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4)_backup.xlsm")
x = zipfile.ZipFile(p).read("xl/worksheets/sheet5.xml").decode()
idx = 0
while True:
    i = x.find("dataValidation", idx)
    if i < 0:
        break
    chunk = x[i : i + 500]
    if 'sqref="L7:L1048576"' in chunk or "sqref=\"L7:L1048576\"" in chunk:
        print(chunk[:450])
        print("---")
    idx = i + 5
