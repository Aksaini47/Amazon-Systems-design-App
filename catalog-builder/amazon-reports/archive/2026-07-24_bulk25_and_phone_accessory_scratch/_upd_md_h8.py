from pathlib import Path
md = Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\STOCK_ADS_PLAN_2026-07-21.md")
if md.exists():
    t = md.read_text(encoding="utf-8")
    block = "\n- **Honor 8X** existed Paused `A09918911CAM3AZ763ZXP` — Enabled (no recreate).\n- **Infinix Note 10** existed Paused `A07695821JLG1Q5C69P30` — Enabled (no recreate).\n"
    if "Honor 8X** existed" not in t:
        md.write_text(t.rstrip()+block, encoding="utf-8")
print("md ok")