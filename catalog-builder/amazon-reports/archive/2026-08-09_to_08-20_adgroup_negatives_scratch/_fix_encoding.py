from pathlib import Path
src = Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports\_build_stock_ads_plan.py")
raw = src.read_bytes()
text = raw.decode("utf-16") if b"\x00" in raw[:10] else raw.decode("utf-8")
src.write_text(text, encoding="utf-8", newline="\n")
print("fixed chars", len(text))
