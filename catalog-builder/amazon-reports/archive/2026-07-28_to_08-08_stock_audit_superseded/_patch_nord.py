from pathlib import Path
p = Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports\_stock_vs_active_2026-07-31.py")
t = p.read_text(encoding="utf-8")
needle = "    # Oppo F5 vs F5 Youth — rare\n    # Redmi 12 vs 12 5G: if stock has no 5g, allow both unless stock is specifically non-5g with sibling — keep permissive\n    # Honor 7X vs 7X White: white stripped from stock tokens\n    # Mi 11X vs 11 — brand tokens\n    return True"
insert = '''    # OnePlus Nord vs Nord CE / Nord 2 / Nord 3
    if "nord" in tokens and "ce" not in tokens:
        if re.search(r"\\bnord\\s*ce\\b|\\bnord\\s*2\\b|\\bnord\\s*3\\b|\\bnord\\s*n\\d", t):
            return False
    return True'''
if needle not in t:
    # try ascii hyphen variants
    idx = t.find("return True\n\n\ndef title_matches")
    if idx < 0:
        idx = t.find("def title_matches")
        # insert before title_matches end of sibling_safe
        idx2 = t.rfind("return True", 0, idx)
        print("fallback idx", idx2)
        t = t[:idx2] + insert + t[idx2+len("return True"):]
    else:
        raise SystemExit("needle missing")
else:
    t = t.replace(needle, insert)
p.write_text(t, encoding="utf-8")
print("ok")