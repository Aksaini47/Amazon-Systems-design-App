"""Create one SP ad group on amazon-ads-1. Args: name model_kw asin_hint brand_token
Example: python _ads_create_one.py "Vivo V15" "vivo v15" "Vivo V15 CareOG" "V15"
"""
from __future__ import annotations
import json, subprocess, sys, time

SESSION = "amazon-ads-1"
ENTITY = "ENTITY37NJTG1VOHVTB"
CAMPAIGN = "A038001030A5E0IF4R8UV"
CREATE = f"https://advertising.amazon.in/cb/sp/campaigns/{CAMPAIGN}/adGroups?entityId={ENTITY}"
AG_LIST = f"https://advertising.amazon.in/cm/sp/campaigns/{CAMPAIGN}/ad-groups?entityId={ENTITY}"

SUFFIXES = [
    "display original", "display", "display price", "original display price",
    "combo display", "combo", "folder", "folder original", "folder display",
    "ka display", "ka folder", "mobile display", "touch display", "lcd",
]


def run(args, timeout=90):
    p = subprocess.run(["agent-browser", "--session", SESSION, *args], capture_output=True, text=True, timeout=timeout)
    return ((p.stdout or "") + (p.stderr or "")).strip()


def ev(js, timeout=90):
    out = run(["eval", js], timeout=timeout)
    # parse last json
    start = out.rfind("{")
    end = out.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(out[start : end + 1])
        except Exception:
            pass
    return {"raw": out[-500:]}


def main():
    name, model, search_term = sys.argv[1], sys.argv[2], sys.argv[3]
    quality_re = sys.argv[4] if len(sys.argv) > 4 else "LCD|Incell|CareOG|Display|Compatible"
    print("CREATE", name, model, search_term)

    run(["open", CREATE], timeout=120)
    time.sleep(5)

    # wait name + set
    r = ev(
        f"""
new Promise(res => {{
  let n=0; const t=setInterval(() => {{
    const el=document.getElementById('sspa_sp_adGroupSettings_adGroupName');
    if(el || n>50){{
      clearInterval(t);
      if(!el){{res({{err:'no name',url:location.href}}); return;}}
      const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
      setter.call(el, {json.dumps(name)});
      el.dispatchEvent(new Event('input',{{bubbles:true}}));
      el.dispatchEvent(new Event('change',{{bubbles:true}}));
      res({{name:el.value,url:location.href}});
    }}
    n++;
  }},400);
}})
"""
    )
    print("name", r)
    if r.get("err"):
        return 1

    # Your Listings + search
    ev(
        """
(() => {
  const yl=[...document.querySelectorAll('button')].find(b=>/Your Listings/i.test(b.innerText));
  yl?.click();
  return !!yl;
})()
"""
    )
    time.sleep(1.5)
    ev(
        f"""
(() => {{
  const el=document.getElementById('ucb-sp-ups:ups-asin-search-input');
  if(!el) return {{err:'no search'}};
  const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
  setter.call(el, {json.dumps(search_term)});
  el.dispatchEvent(new Event('input',{{bubbles:true}}));
  return {{v:el.value}};
}})()
"""
    )
    time.sleep(4)

    # Click Add on quality-matched row
    add = ev(
        f"""
(() => {{
  const reQual = new RegExp({json.dumps(quality_re)}, 'i');
  const reBad = /OLED|AMOLED/i;
  let clicked=false, ctx='';
  for (const b of document.querySelectorAll('button')) {{
    if (b.innerText.trim()!=='Add' || b.disabled) continue;
    ctx=(b.closest('li,tr,[role=row],div')?.innerText||'').replace(/\\s+/g,' ');
    if (!new RegExp({json.dumps(name.split()[0])}, 'i').test(ctx) && !/{json.dumps(search_term)}/i.test(ctx)) continue;
    if (!reQual.test(ctx)) continue;
    // for CareOG stock prefer CareOG; for Incell prefer LCD and not CareOG-only if both
    b.scrollIntoView({{block:'center'}});
    b.click();
    clicked=true;
    break;
  }}
  return {{clicked, ctx: ctx.slice(0,200)}};
}})()
"""
    )
    print("product", add)
    time.sleep(3)

    # Prefer Enter list with ASIN extracted from ctx if Add failed
    if not add.get("clicked"):
        # try Enter list fallback - extract B0 from page
        asin = ev(
            f"""
(() => {{
  const txt=document.body.innerText;
  const m=txt.match(/ASIN:(B0[A-Z0-9]+)/g) || [];
  return {{asins: [...new Set(m.map(x=>x.replace('ASIN:','')))].slice(0,8), snip: txt.slice(0,200)}};
}})()
"""
        )
        print("asins found", asin)

    prod_check = ev(
        """
(() => {
  const txt=document.body.innerText;
  const removeAlls=[...document.querySelectorAll('button')].filter(b=>b.innerText.trim()==='Remove all').map(b=>(b.parentElement?.innerText||'').replace(/\\s+/g,' ').slice(0,30));
  return {lines:(txt.match(/[^\\n]*product[^\\n]*/gi)||[]).slice(0,6), removeAlls};
})()
"""
    )
    print("prod_check", prod_check)

    # Keywords Enter list
    ev(
        """
(() => {
  const h=[...document.querySelectorAll('h3')].find(e=>/Keyword targeting/i.test(e.innerText));
  h?.scrollIntoView({block:'center'});
  const enters=[...document.querySelectorAll('button')].filter(b=>b.innerText.trim()==='Enter list');
  enters[enters.length-1]?.click();
  return enters.length;
})()
"""
    )
    time.sleep(1)
    kw_text = "\\n".join(f"{model} {s}" for s in SUFFIXES)
    # actually use real newlines in JSON
    kw_text = "\n".join(f"{model} {s}" for s in SUFFIXES)
    kw = ev(
        f"""
(() => {{
  for (const lab of document.querySelectorAll('label')) {{
    const t=lab.innerText.trim().toLowerCase();
    const cb=lab.querySelector('input[type=checkbox]');
    if(!cb) continue;
    if ((t==='broad'||t==='phrase'||t==='exact') && !cb.checked) cb.click();
  }}
  const bidBtn=[...document.querySelectorAll('button')].find(b=>/Bid selection/i.test(b.innerText));
  if (bidBtn && /Suggested/i.test(bidBtn.innerText)) bidBtn.click();
  return 'ok';
}})()
"""
    )
    time.sleep(0.8)
    ev(
        """
(() => {
  const opt=[...document.querySelectorAll('[role=option],li,button,div')].find(e=>/^Custom bid$/i.test((e.innerText||'').trim()));
  opt?.click();
  return !!opt;
})()
"""
    )
    time.sleep(0.5)
    kw2 = ev(
        f"""
(() => {{
  const bidInputs=[...document.querySelectorAll('input')].filter(i=>/bid for keyword|enter amount in/i.test(i.getAttribute('aria-label')||''));
  const bid=bidInputs[0];
  if(bid){{
    const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    setter.call(bid,'3');
    bid.dispatchEvent(new Event('input',{{bubbles:true}}));
  }}
  const ta=[...document.querySelectorAll('textarea')].find(t=>/keyword/i.test(t.placeholder||'')) || [...document.querySelectorAll('textarea')].pop();
  if(!ta) return {{err:'no ta'}};
  const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
  setter.call(ta, {json.dumps(kw_text)});
  ta.dispatchEvent(new Event('input',{{bubbles:true}}));
  const add=[...document.querySelectorAll('button')].find(b=>b.innerText.trim()==='Add keywords'&&!b.disabled);
  add?.click();
  return {{bid:bid?.value, add:!!add, lines:ta.value.split('\\n').filter(Boolean).length}};
}})()
"""
    )
    print("keywords", kw2)
    time.sleep(3)
    # confirm dialog if any
    ev(
        """
(() => {
  const add=[...document.querySelectorAll('button')].find(b=>b.innerText.trim()==='Add keywords'&&!b.disabled);
  add?.click();
  return (document.body.innerText.match(/\\d+\\/\\d+ keywords were added/)||[])[0];
})()
"""
    )
    time.sleep(2)

    # Create
    created = ev(
        """
(() => {
  const btn=[...document.querySelectorAll('button')].filter(b=>b.innerText.trim()==='Create ad group'&&!b.disabled).pop();
  btn?.click();
  return !!btn;
})()
"""
    )
    print("create clicked", created)
    time.sleep(10)

    # Verify on list
    run(["open", AG_LIST], timeout=120)
    time.sleep(4)
    found = ev(
        f"""
new Promise(res => {{
  const s=document.querySelector('input[placeholder=\"Find an ad group\"], input[type=search]');
  if(!s){{res({{err:'no search'}}); return;}}
  const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
  setter.call(s, {json.dumps(name)});
  s.dispatchEvent(new Event('input',{{bubbles:true}}));
  setTimeout(() => {{
    const links=[...document.querySelectorAll('a[href*=\"ad-groups/\"]')].map(a=>({{t:a.innerText.trim(),href:a.href}})).filter(x=>new RegExp({json.dumps(name)},'i').test(x.t));
    res({{links, body: document.body.innerText.includes({json.dumps(name)})}});
  }}, 2000);
}})
"""
    )
    print("FOUND", json.dumps(found))
    Path = __import__("pathlib").Path
    Path(r"c:\Projects\Amazon Systems Design\agent\Graphs & workflows\mahika-ads-flow\_last_create.json").write_text(
        json.dumps({"name": name, "found": found, "product": add, "kw": kw2}, indent=2), encoding="utf-8"
    )
    return 0 if found.get("links") else 2


if __name__ == "__main__":
    raise SystemExit(main())
