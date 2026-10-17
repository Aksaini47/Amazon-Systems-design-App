import zipfile
from pathlib import Path

for label, p in [
    ("backup", Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4)_backup.xlsm")),
    ("current", Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4).xlsm")),
]:
    x = zipfile.ZipFile(p).read("xl/worksheets/sheet5.xml").decode()
    print("===", label)
    idx = 0
    n = 0
    while True:
        i = x.find("dataValidation", idx)
        if i < 0:
            break
        chunk = x[i : i + 400]
        if "C7" in chunk[:120] or ("sqref=\"C7" in chunk):
            print(chunk[:350])
            print("---")
            n += 1
        idx = i + 5
    print("C7-related dvs:", n)
