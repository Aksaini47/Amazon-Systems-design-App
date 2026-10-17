import json, subprocess, time
from pathlib import Path
EXE = r"C:\Users\DELL\AppData\Roaming\npm\node_modules\agent-browser\bin\agent-browser-win32-x64.exe"

def ab(*args):
    r = subprocess.run([EXE, "--session", "amazon-ads", *args], capture_output=True, text=True, timeout=120)
    out = (r.stdout or "") + (r.stderr or "")
    lines = [l for l in out.splitlines() if not l.startswith("[agent-browser]")]
    return "\n".join(lines).strip()

names = [
  "Galaxy A32 4G","Galaxy A73","Galaxy J7 2015","Galaxy J7 2016","Galaxy J7 Max","Galaxy J7 Next","Galaxy S21 FE",
  "Honor 7X","Honor 8X","Infinix Note 10","Moto Edge 50 Fusion","Nokia G21","Oppo F27","Poco X3",
  "Realme 3 Pro","Realme C21","Redmi 13 Pro Plus","Redmi Note 10T","Vivo V15"
]
results = []
for name in names:
    search_js = "(() => { const box=document.querySelector('input[type=search]'); const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set; setter.call(box, %s); box.dispatchEvent(new Event('input',{bubbles:true})); box.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); return 'OK'; })()" % json.dumps(name)
    ab("eval", search_js)
    time.sleep(2.6)
    read_js = """(() => { const want=%s; const exact=[...document.querySelectorAll('a')].filter(a=>(a.textContent||'').trim()===want); const near=[...document.querySelectorAll('a')].map(a=>({n:(a.textContent||'').trim(),id:((a.href.match(/ad-groups\\/([^/?]+)/)||[])[1])})).filter(x=>x.n && x.n!==want && x.n.toLowerCase().includes(want.toLowerCase().split(' ')[0].toLowerCase()) && want.toLowerCase().split(' ').slice(-1)[0].toLowerCase() in x.n.toLowerCase()).slice(0,6); if(!exact.length){ return JSON.stringify({name:want,exists:false,near}); } const a=exact[0]; const id=(a.href.match(/ad-groups\\/([^/?]+)/)||[])[1]; let row=a.closest('[role=row]')||a.parentElement; let enabled=null; for(let i=0;i<10&&row;i++){ const sw=row.querySelector('[role=switch]'); if(sw){ enabled=sw.getAttribute('aria-checked'); break;} row=row.parentElement;} return JSON.stringify({name:want,exists:true,id,enabled,near}); })()""" % json.dumps(name)
    raw = ab("eval", read_js)
    try:
        if raw.startswith('"') and raw.endswith('"'):
            raw = json.loads(raw)
        results.append(json.loads(raw) if isinstance(raw, str) else raw)
    except Exception as e:
        results.append({"name": name, "raw": raw[:400], "error": str(e)})
    print(results[-1])

Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports\_create_dup_check.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print("DONE", len(results))