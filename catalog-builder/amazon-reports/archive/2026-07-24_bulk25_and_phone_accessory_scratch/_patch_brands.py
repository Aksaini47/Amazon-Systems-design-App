from pathlib import Path
p = Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports\_build_stock_ads_plan.py")
t = p.read_text(encoding="utf-8")
old = '        if line.isupper() or line in ("XIAOMI/REDMI/POCO", "MIX"):\n            brand = line\n            continue'
new = '''        BRANDS = {"REALME", "VIVO", "OPPO", "ONEPLUS", "APPLE", "SAMSUNG", "XIAOMI/REDMI/POCO", "MIX"}
        if line in BRANDS:
            brand = line
            continue'''
if old not in t:
    raise SystemExit("old block not found: " + repr(t[t.find("isupper")-40:t.find("isupper")+100]))
p.write_text(t.replace(old, new), encoding="utf-8")
print("patched")
