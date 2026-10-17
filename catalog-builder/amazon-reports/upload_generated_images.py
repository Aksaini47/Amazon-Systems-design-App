"""Resize generated listing images to 1600x1600, upload to R2, patch template rows."""
from __future__ import annotations

import io
import re
import shutil
from pathlib import Path

import openpyxl
import pythoncom
import win32com.client as win32
from PIL import Image

try:
    import boto3
    from botocore.config import Config
except ImportError:
    boto3 = None

ROOT = Path(__file__).resolve().parent
ASSETS = Path(r"C:\Users\DELL\.cursor\projects\c-Projects-Amazon-Systems-Design\assets")
OUT_DIR = ROOT / "generated_images"
TEMPLATE = Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4).xlsm")
BACKUP = Path(r"C:\Users\DELL\Downloads\PHONE_ACCESSORY (4)_backup.xlsm")
DATA_START = 7
COL_SKU = 1
COL_IMG_START = 21

SKUS = [
    "RMREALMEC6LCD",
    "OPF17PROOLED",
    "MXMOTOG34WF",
    "MXASUSROGPLCD",
]

FILES = {
    "RMREALMEC6LCD": ["RMREALMEC6LCD_01_main.jpg", "RMREALMEC6LCD_02_front_back.jpg"],
    "OPF17PROOLED": ["OPF17PROOLED_01_main.jpg", "OPF17PROOLED_02_front_back.jpg"],
    "MXMOTOG34WF": ["MXMOTOG34WF_01_main.jpg", "MXMOTOG34WF_02_front_back.jpg"],
    "MXASUSROGPLCD": ["MXASUSROGPLCD_01_main.jpg", "MXASUSROGPLCD_02_front_back.jpg"],
}


def load_r2_config() -> dict:
    text = Path(r"c:\Projects\Amazon Systems Design\.env").read_text(encoding="utf-8")

    def get(key: str) -> str:
        m = re.search(rf'{key}="([^"]+)"', text)
        return m.group(1) if m else ""

    return {
        "account_id": get("R2_ACCOUNT_ID"),
        "access_key": get("R2_ACCESS_KEY_ID"),
        "secret_key": get("R2_SECRET_ACCESS_KEY"),
        "bucket": get("R2_BUCKET") or "repairfully",
        "cdn": get("R2_CDN_BASE").rstrip("/"),
    }


def resize_to_1600(src: Path, dst: Path) -> None:
    img = Image.open(src).convert("RGB")
    if img.size != (1600, 1600):
        img = img.resize((1600, 1600), Image.Resampling.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, format="JPEG", quality=92, optimize=True)


def upload_r2(local: Path, key: str, cfg: dict) -> str:
    if boto3 is None:
        raise RuntimeError("boto3 not installed — pip install boto3")
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{cfg['account_id']}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg["access_key"],
        aws_secret_access_key=cfg["secret_key"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    client.upload_file(
        str(local),
        cfg["bucket"],
        key,
        ExtraArgs={"ContentType": "image/jpeg"},
    )
    return f"{cfg['cdn']}/{key}"


def sku_row_map() -> dict[str, int]:
    wb = openpyxl.load_workbook(TEMPLATE, read_only=True, data_only=True)
    ws = wb["Template"]
    out: dict[str, int] = {}
    for r in range(DATA_START, DATA_START + 30):
        sku = ws.cell(r, COL_SKU).value
        if sku:
            out[str(sku).strip().upper()] = r
    wb.close()
    return out


def patch_template(urls_by_sku: dict[str, list[str]]) -> None:
    rows = sku_row_map()
    pythoncom.CoInitialize()
    excel = win32.DispatchEx("Excel.Application")
    try:
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(str(TEMPLATE.resolve()))
        ws = wb.Worksheets("Template")
        for sku, urls in urls_by_sku.items():
            r = rows.get(sku.upper())
            if not r:
                print(f"  skip template row missing: {sku}")
                continue
            for i in range(10):
                ws.Cells(r, COL_IMG_START + i).ClearContents()
            for i, url in enumerate(urls[:10]):
                ws.Cells(r, COL_IMG_START + i).Value = url
            print(f"  template row {r} {sku}: {len(urls)} urls")
        wb.Save()
        wb.Close(SaveChanges=True)
    finally:
        excel.Quit()
        pythoncom.CoUninitialize()


def main() -> None:
    cfg = load_r2_config()
    urls_by_sku: dict[str, list[str]] = {}

    for sku in SKUS:
        sku_urls: list[str] = []
        folder = OUT_DIR / sku
        folder.mkdir(parents=True, exist_ok=True)
        for idx, fname in enumerate(FILES[sku], 1):
            src = ASSETS / fname
            if not src.exists():
                print(f"MISSING {src}")
                continue
            local = folder / f"{sku}_{idx}.jpg"
            resize_to_1600(src, local)
            key = f"products/GEN_{sku}/{sku}_{idx}.jpg"
            try:
                url = upload_r2(local, key, cfg)
                sku_urls.append(url)
                print(f"OK {sku} #{idx} -> {url}")
            except Exception as e:
                print(f"R2 fail {sku} #{idx}: {e} — local only {local}")
                sku_urls.append(str(local))
        urls_by_sku[sku] = sku_urls

    manifest = OUT_DIR / "generated_4_listings_manifest.txt"
    lines = ["Generated images — 4 listings", "Format: 1600x1600 JPEG RGB (matched Mongo ref)", ""]
    for sku, urls in urls_by_sku.items():
        lines.append(f"## {sku}")
        for u in urls:
            lines.append(f"  {u}")
        lines.append("")
    manifest.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nManifest: {manifest}")

    if TEMPLATE.exists():
        patch_template(urls_by_sku)
        print(f"Template updated: {TEMPLATE}")


if __name__ == "__main__":
    main()
