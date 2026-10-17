from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(r"Graphs & workflows/mahika-ads-flow").resolve()))
import _create_realme_vivo as m
AB = r"C:\Users\DELL\AppData\Roaming\npm\agent-browser.cmd"
m.SESSION = "ads-sso"
def run(*args, timeout=180):
    cmd = [AB, "--session", m.SESSION, "--headed", *args]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    return ((p.stdout or "") + (p.stderr or "")).strip(), p.returncode
m.run = run
out = Path(r"Graphs & workflows/mahika-ads-flow/_v15_result.json")
links = m.search_ag("Vivo V15")
out.write_text(json.dumps({"phase":"dup", "links":links}, indent=2, ensure_ascii=True), encoding="utf-8")
existing = None
for L in links if isinstance(links, list) else []:
    if isinstance(L, dict) and "v15" in (L.get("t") or "").lower():
        existing = L
        break
if existing:
    out.write_text(json.dumps({"status":"exists", **existing}, indent=2, ensure_ascii=True), encoding="utf-8")
    raise SystemExit(0)
res = m.create_ag(
    name="Vivo V15",
    model_kw="vivo v15",
    asin="B0CPTCXZRQ",
    search_terms=["B0CPTCXZRQ", "Vivo V15 CareOG", "Vivo V15"],
    title_regex=r"Vivo V15.*CareOG|Compatible for Vivo V15",
    negs=["pro", "max", "pro max", "plus", "5g", "4g"],
)
out.write_text(json.dumps(res, indent=2, ensure_ascii=True), encoding="utf-8")
print("wrote", out)
