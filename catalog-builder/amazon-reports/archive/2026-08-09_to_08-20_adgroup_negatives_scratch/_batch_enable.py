import subprocess, time, re, pathlib
from collections import Counter

SESSION = "amazon-ads"
AB = r"C:\Users\DELL\AppData\Roaming\npm\agent-browser.cmd"
JS = r"""new Promise(function(resolve){ setTimeout(function(){ var want=document.querySelector("input[type=search]").value.trim(); var rows=document.querySelectorAll("[role=row]"); for(var i=0;i<rows.length;i++){ var a=rows[i].querySelector("a"); if(!a) continue; if(a.innerText.trim()!==want) continue; var sw=rows[i].querySelector("[role=switch]"); if(!sw){ resolve(want+"|no_switch"); return;} if(sw.getAttribute("aria-checked")==="true"){ resolve(want+"|already"); return;} sw.click(); resolve(want+"|enabled"); return;} resolve(want+"|not_found"); },2000); })"""

ROOT = pathlib.Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports")
names = [n.strip() for n in (ROOT / "_activate_remaining.txt").read_text(encoding="utf-8").splitlines() if n.strip()]
done = {"Oppo F9", "Oppo A54", "Oppo F19 / F19 Pro", "OnePlus 9RT"}
names = [n for n in names if n not in done]

out = [
    "OnePlus 9RT|enabled",
    "Oppo A54|already",
    "Oppo F19 / F19 Pro|already",
    "Oppo F9|already",
]

for name in names:
    subprocess.run([AB, "--session", SESSION, "fill", "input[type=search]", name], capture_output=True, text=True, shell=False)
    time.sleep(0.4)
    r = subprocess.run([AB, "--session", SESSION, "eval", JS], capture_output=True, text=True, shell=False)
    text = (r.stdout or "") + (r.stderr or "")
    m = re.search(r'([^\n"]+\|(?:enabled|already|not_found|no_switch))', text)
    line = m.group(1) if m else f"{name}|error"
    print(line, flush=True)
    out.append(line)

(ROOT / "_activate_results.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
print("SUMMARY", dict(Counter(x.split("|", 1)[1] for x in out)), flush=True)