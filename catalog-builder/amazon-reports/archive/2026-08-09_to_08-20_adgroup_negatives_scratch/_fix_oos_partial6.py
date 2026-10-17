import time
from pathlib import Path
import pythoncom
import win32com.client as win32

PATH = Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (6).xlsm")
pythoncom.CoInitialize()
excel = win32.DispatchEx("Excel.Application")
excel.Visible = False
excel.DisplayAlerts = False
try:
    wb = excel.Workbooks.Open(str(PATH), UpdateLinks=0, ReadOnly=False)
    time.sleep(1.5)
    ws = wb.Worksheets("Template")
    hits = []
    for r in range(7, 80):
        sku = ws.Cells(r, 1).Value
        if sku and str(sku).strip() == "IP13PMGX":
            hits.append(r)
    print("hits", hits)
    if len(hits) > 1:
        del_row = hits[-1]
        ws.Rows(del_row).Delete()
        print("deleted", del_row)
    wb.Save()
    print("saved")
    wb.Close(SaveChanges=True)
finally:
    excel.Quit()
    pythoncom.CoUninitialize()
