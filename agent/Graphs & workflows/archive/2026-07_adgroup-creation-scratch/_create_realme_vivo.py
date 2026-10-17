#!/usr/bin/env python3
"""Batch create/fix Realme+Vivo ad groups on amazon-ads-1."""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

SESSION = "amazon-ads-1"
CAMPAIGN = "A038001030A5E0IF4R8UV"
ENTITY = "ENTITY37NJTG1VOHVTB"
BASE = f"https://advertising.amazon.in/cm/sp/campaigns/{CAMPAIGN}"
AG_LIST = f"{BASE}/ad-groups?entityId={ENTITY}"
OUT = Path(__file__).with_name("_rv_results.json")

# KEYWORD_PATTERNS §1 suffixes — each × Broad+Phrase+Exact @ ~₹3
SUFFIXES = [
    "display original",
    "display",
    "display price",
    "original display price",
    "combo display",
    "combo",
    "folder",
    "folder original",
    "folder display",
    "ka display",
    "ka folder",
    "mobile display",
    "touch display",
    "lcd",
]


def run(*args, timeout=180):
    cmd = ["agent-browser", "--session", SESSION, *args]
    p = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    out = (p.stdout or "") + (p.stderr or "")
    return out.strip(), p.returncode


def ev(js: str, timeout=180):
    out, code = run("eval", js, timeout=timeout)
    return out, code


def open_url(url: str):
    run("open", url)
    time.sleep(5)


def kw_list(model: str) -> str:
    m = model.lower().strip()
    return "\\n".join(f"{m} {s}" for s in SUFFIXES)


def safe_negs(model: str) -> list[str]:
    """Base Phrase negatives — skip tokens present in model name."""
    ml = model.lower()
    cands = ["pro", "max", "pro max", "plus", "5g", "4g"]
    out = []
    for c in cands:
        # skip if qualifier is substring of model tokens in a meaningful way
        if c == "pro max":
            if "pro max" in ml or ("pro" in ml and "max" in ml):
                continue
        elif c in ml.split() or re.search(rf"\\b{re.escape(c)}\\b", ml):
            continue
        # Ads UI often blocks Phrase 4g/5g — still try; caller may filter
        out.append(c)
    return out


def search_ag(name: str):
    open_url(AG_LIST)
    time.sleep(2)
    out, _ = ev(
        f"""(() => {{
      const setNative=(el,val)=>{{
        const desc=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
        if(desc&&desc.set) desc.set.call(el,val); else el.value=val;
        el.dispatchEvent(new Event('input',{{bubbles:true}}));
        el.dispatchEvent(new Event('change',{{bubbles:true}}));
      }};
      const box=document.querySelector('input[type=search], [role=searchbox]');
      if(!box) return 'no-search';
      setNative(box, {json.dumps(name)});
      box.dispatchEvent(new KeyboardEvent('keydown',{{key:'Enter',bubbles:true}}));
      return 'ok';
    }})()"""
    )
    time.sleep(3)
    out, _ = ev(
        f"""(() => {{
      const needle={json.dumps(name.lower())};
      const links=[...document.querySelectorAll('a')].filter(a=>{{
        const t=(a.textContent||'').trim().toLowerCase();
        const href=a.getAttribute('href')||'';
        return /ad-groups\\//i.test(href) && (t===needle || t.includes(needle));
      }}).map(a=>({{
        t:(a.textContent||'').trim(),
        id:(a.getAttribute('href')||'').match(/ad-groups\\/(A[A-Z0-9]+)/i)?.[1]||null,
        href:a.getAttribute('href')||''
      }}));
      return JSON.stringify(links.slice(0,10));
    }})()"""
    )
    try:
        return json.loads(out.split("\n")[-1] if "\n" in out else out)
    except Exception:
        # try find JSON in output
        m = re.search(r"\\[.*\\]", out, re.S)
        if m:
            return json.loads(m.group(0))
        return [{"raw": out}]


def count_match_types(ag_id: str):
    open_url(f"{BASE}/ad-groups/{ag_id}/targeting?entityId={ENTITY}")
    time.sleep(5)
    out, _ = ev(
        """(() => {
      const t=document.body.innerText;
      const broad=(t.match(/\\bBroad\\b/gi)||[]).length;
      const phrase=(t.match(/\\bPhrase\\b/gi)||[]).length;
      const exact=(t.match(/\\bExact\\b/gi)||[]).length;
      // keyword rows often show Match type column
      const rows=[...document.querySelectorAll('tr')].map(r=>r.innerText.replace(/\\s+/g,' ').trim()).filter(x=>/display|folder|combo|lcd|ka /i.test(x));
      const mt={Broad:0,Phrase:0,Exact:0};
      for (const r of rows) {
        if (/\\bBroad\\b/i.test(r)) mt.Broad++;
        if (/\\bPhrase\\b/i.test(r)) mt.Phrase++;
        if (/\\bExact\\b/i.test(r)) mt.Exact++;
      }
      return JSON.stringify({mt, sample:rows.slice(0,8), totalHint:/Total\\s*(\\d+)/i.exec(t)?.[1]||null});
    })()"""
    )
    try:
        return json.loads(re.search(r"\\{.*\\}", out, re.S).group(0))
    except Exception:
        return {"raw": out}


def add_missing_bpe(ag_id: str, model: str):
    """On targeting page, add keywords with Broad+Phrase+Exact if Phrase-only."""
    open_url(f"{BASE}/ad-groups/{ag_id}/targeting?entityId={ENTITY}")
    time.sleep(5)
    # Click Add keywords / Enter list flow
    ev(
        """(() => {
      const b=[...document.querySelectorAll('button')].find(x=>/Add keywords|Enter list|Add keyword/i.test(x.textContent||''));
      if(b){b.click(); return 'clicked:'+(b.textContent||'').trim();}
      return 'no-add';
    })()"""
    )
    time.sleep(2)
    ev(
        """(() => {
      for (const lab of ['Broad','Phrase','Exact']) {
        const labels=[...document.querySelectorAll('label')].filter(l=>new RegExp('^\\\\s*'+lab+'\\\\s*$','i').test(l.textContent||''));
        for (const l of labels) {
          const cb=l.querySelector('input[type=checkbox]');
          if (cb && !cb.checked) cb.click();
        }
      }
      const bidBtn=[...document.querySelectorAll('button')].find(b=>/Bid selection/i.test(b.textContent||''));
      if(bidBtn) bidBtn.click();
      return 'prep';
    })()"""
    )
    time.sleep(1)
    ev(
        """(() => {
      const opt=[...document.querySelectorAll('[role=option], li, button')].find(el=>/Custom bid/i.test(el.textContent||''));
      if(opt){opt.click(); return 'custom';} return 'no-custom';
    })()"""
    )
    time.sleep(1)
    ev(
        """(() => {
      const btns=[...document.querySelectorAll('button')].filter(b=>/^Enter list$/i.test((b.textContent||'').trim()));
      if(btns.length){btns[btns.length-1].click(); return 'enter-list';}
      return 'no-enter';
    })()"""
    )
    time.sleep(1)
    kws = kw_list(model)
    out, _ = ev(
        f"""(() => {{
      const setNative=(el,val)=>{{
        const proto = el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
        const desc=Object.getOwnPropertyDescriptor(proto,'value');
        if(desc&&desc.set) desc.set.call(el,val); else el.value=val;
        el.dispatchEvent(new Event('input',{{bubbles:true}}));
        el.dispatchEvent(new Event('change',{{bubbles:true}}));
      }};
      const tb=[...document.querySelectorAll('textarea,input,[role=textbox]')].find(el=>{{
        const a=((el.getAttribute('aria-label')||'')+(el.placeholder||'')).toLowerCase();
        return a.includes('enter keywords') || a.includes('new line') || a.includes('keyword');
      }});
      if(!tb) return 'no-kw-box:'+[...document.querySelectorAll('textarea')].map(t=>t.getAttribute('aria-label')||t.placeholder||'ta').join('|');
      setNative(tb, `{kws}`);
      const bid=[...document.querySelectorAll('input')].find(el=>{{
        const a=((el.getAttribute('aria-label')||'')+(el.placeholder||'')).toLowerCase();
        return a.includes('edit custom bid') || a.includes('bid') && a.includes('amount') || a.includes('enter amount');
      }});
      if(bid) setNative(bid,'3');
      const add=[...document.querySelectorAll('button')].find(b=>/Add keywords|^Add$/i.test((b.textContent||'').trim()) && !b.disabled);
      if(add){{ add.click(); return 'kw-added'; }}
      return 'kw-filled-no-add';
    }})()"""
    )
    time.sleep(3)
    # Save if needed
    ev(
        """(() => {
      const b=[...document.querySelectorAll('button')].find(x=>/^(Save|Apply|Confirm)$/i.test((x.textContent||'').trim()) && !x.disabled);
      if(b){b.click(); return 'saved';}
      return 'no-save';
    })()"""
    )
    time.sleep(3)
    return out


def create_ag(name: str, model_kw: str, asin: str | None, search_terms: list[str], title_regex: str, negs: list[str]):
    open_url(AG_LIST)
    time.sleep(2)
    # Create ad group button
    out, _ = ev(
        """(() => {
      const b=[...document.querySelectorAll('button')].find(x=>/Create ad group/i.test(x.textContent||''));
      if(!b) return 'no-btn';
      b.click(); return 'clicked';
    })()"""
    )
    time.sleep(6)
    # Name
    out, _ = ev(
        f"""(() => {{
      const setNative=(el,val)=>{{
        const proto = el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
        const desc=Object.getOwnPropertyDescriptor(proto,'value');
        if(desc&&desc.set) desc.set.call(el,val); else el.value=val;
        el.dispatchEvent(new Event('input',{{bubbles:true}}));
        el.dispatchEvent(new Event('change',{{bubbles:true}}));
      }};
      const inputs=[...document.querySelectorAll('input,textarea')];
      const nameBox=inputs.find(i=>((i.getAttribute('aria-label')||'')+(i.placeholder||'')).toLowerCase().includes('ad group name'));
      if(!nameBox) return 'no-name:'+inputs.map(i=>i.getAttribute('aria-label')||i.placeholder||i.type).slice(0,15).join('|');
      setNative(nameBox, {json.dumps(name)});
      return 'ok:'+nameBox.value;
    }})()"""
    )
    if "ok:" not in out:
        return {"status": "failed", "step": "name", "detail": out}

    # Product search tab
    ev(
        """(() => {
      const b=[...document.querySelectorAll('button')].find(x=>/^Search$/i.test((x.textContent||'').trim()));
      if(b){b.click(); return 'search-tab';} return 'no-search-tab';
    })()"""
    )
    time.sleep(1)

    added = None
    for term in search_terms:
        ev(
            f"""(() => {{
      const setNative=(el,val)=>{{
        const desc=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
        if(desc&&desc.set) desc.set.call(el,val); else el.value=val;
        el.dispatchEvent(new Event('input',{{bubbles:true}}));
      }};
      const box=[...document.querySelectorAll('input,[role=searchbox]')].find(el=>{{
        const a=((el.getAttribute('aria-label')||'')+(el.placeholder||'')).toLowerCase();
        return a.includes('asin') || a.includes('product name') || a.includes('sku') || a.includes('search');
      }});
      if(!box) return 'no-box';
      setNative(box, {json.dumps(term)});
      box.dispatchEvent(new KeyboardEvent('keydown',{{key:'Enter',bubbles:true}}));
      return 'searched';
    }})()"""
        )
        time.sleep(4)
        out, _ = ev(
            f"""(() => {{
      const re=new RegExp({json.dumps(title_regex)}, 'i');
      const bad=/OLED|AMOLED/i;
      const wantOled=/OLED|AMOLED/i.test({json.dumps(title_regex)});
      const links=[...document.querySelectorAll('a')];
      let link=links.find(a=>re.test(a.textContent||'') && (wantOled ? true : !bad.test(a.textContent||'')));
      if(!link && {json.dumps(asin or '')}) {{
        link=links.find(a=>(a.textContent||'').includes({json.dumps(asin or '')}) || (a.getAttribute('href')||'').includes({json.dumps(asin or '')}));
      }}
      if(!link) {{
        const titles=links.map(a=>a.textContent.trim()).filter(t=>t.length>20).slice(0,12);
        // also try table cells
        const cells=[...document.querySelectorAll('[role=row], tr, li')].map(el=>el.innerText.replace(/\\s+/g,' ').trim()).filter(t=>/Compatible|Display/i.test(t)).slice(0,8);
        return 'no-link:'+JSON.stringify({{titles, cells, term:{json.dumps(term)}}});
      }}
      let node=link;
      let btn=null;
      for(let i=0;i<10 && node;i++){{
        btn=[...node.querySelectorAll('button')].find(b=>/^Add$/i.test((b.textContent||'').trim()));
        if(btn) break;
        node=node.parentElement;
      }}
      if(!btn){{
        // search nearby rows
        const row=link.closest('tr, [role=row], li, div');
        if(row) btn=[...row.querySelectorAll('button')].find(b=>/^Add$/i.test((b.textContent||'').trim()));
      }}
      if(!btn) return 'no-add-btn:'+link.textContent.trim().slice(0,100);
      btn.click();
      return 'added:'+link.textContent.trim().slice(0,120);
    }})()"""
        )
        if out.startswith('"added:') or '"added:' in out or out.startswith("added:") or "added:" in out:
            added = out
            break
    if not added:
        return {"status": "failed_skip", "step": "product", "detail": out}

    # Keywords BPE
    time.sleep(2)
    ev(
        """(() => {
      for (const lab of ['Broad','Phrase','Exact']) {
        const labels=[...document.querySelectorAll('label')].filter(l=>new RegExp('^\\\\s*'+lab+'\\\\s*$','i').test(l.textContent||''));
        for (const l of labels) {
          const cb=l.querySelector('input[type=checkbox]');
          if (cb && !cb.checked) cb.click();
        }
      }
      const bidBtn=[...document.querySelectorAll('button')].find(b=>/Bid selection/i.test(b.textContent||''));
      if(bidBtn) bidBtn.click();
      return 'prep';
    })()"""
    )
    time.sleep(1)
    ev(
        """(() => {
      const opt=[...document.querySelectorAll('[role=option], li, button')].find(el=>/Custom bid/i.test(el.textContent||''));
      if(opt){opt.click(); return 'custom';} return 'no-custom';
    })()"""
    )
    time.sleep(1)
    ev(
        """(() => {
      const btns=[...document.querySelectorAll('button')].filter(b=>/^Enter list$/i.test((b.textContent||'').trim()));
      if(btns.length>=2){btns[1].click(); return 'kw-enter-2';}
      if(btns.length===1){btns[0].click(); return 'kw-enter-1';}
      return 'no-kw-enter';
    })()"""
    )
    time.sleep(1)
    kws = kw_list(model_kw)
    out, _ = ev(
        f"""(() => {{
      const setNative=(el,val)=>{{
        const proto = el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
        const desc=Object.getOwnPropertyDescriptor(proto,'value');
        if(desc&&desc.set) desc.set.call(el,val); else el.value=val;
        el.dispatchEvent(new Event('input',{{bubbles:true}}));
        el.dispatchEvent(new Event('change',{{bubbles:true}}));
      }};
      const tb=[...document.querySelectorAll('textarea,input,[role=textbox]')].find(el=>{{
        const a=((el.getAttribute('aria-label')||'')+(el.placeholder||'')).toLowerCase();
        return a.includes('enter keywords') || a.includes('new line');
      }});
      if(!tb) return 'no-kw-box';
      setNative(tb, `{kws}`);
      const bid=[...document.querySelectorAll('input')].find(el=>{{
        const a=((el.getAttribute('aria-label')||'')+(el.placeholder||'')).toLowerCase();
        return a.includes('edit custom bid') || (a.includes('enter amount') && a.includes('bid'));
      }});
      if(bid) setNative(bid,'3');
      const add=[...document.querySelectorAll('button')].find(b=>/^Add keywords$/i.test((b.textContent||'').trim()) && !b.disabled);
      if(add){{ add.click(); return 'kw-added'; }}
      return 'kw-filled-no-add';
    }})()"""
    )
    time.sleep(4)

    # Negatives
    if negs:
        ev(
            """(() => {
      const h=[...document.querySelectorAll('h3,h2,button,span')].find(el=>/Negative keyword targeting/i.test(el.textContent||''));
      if(h){
        const wrap=h.closest('div');
        const expand=wrap && wrap.querySelector('button[aria-expanded="false"]');
        if(expand) expand.click();
        else h.click();
      }
      return 'neg-expand';
    })()"""
        )
        time.sleep(1)
        neg_text = "\\n".join(negs)
        # Prefer Phrase; skip 4g/5g if UI blocks (try without first if needed)
        out, _ = ev(
            f"""(() => {{
      const setNative=(el,val)=>{{
        const proto = el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
        const desc=Object.getOwnPropertyDescriptor(proto,'value');
        if(desc&&desc.set) desc.set.call(el,val); else el.value=val;
        el.dispatchEvent(new Event('input',{{bubbles:true}}));
      }};
      const phraseLab=[...document.querySelectorAll('label,button,[role=radio]')].find(el=>/Negative phrase/i.test(el.textContent||el.getAttribute('aria-label')||''));
      if(phraseLab) phraseLab.click();
      const boxes=[...document.querySelectorAll('textarea')];
      const target=boxes[boxes.length-1];
      if(!target) return 'no-neg-box';
      setNative(target, `{neg_text}`);
      const add=[...document.querySelectorAll('button')].find(b=>/Add negative keywords|Add keywords/i.test((b.textContent||'').trim()) && !b.disabled);
      if(add){{add.click(); return 'neg-added';}}
      const adds=[...document.querySelectorAll('button')].filter(b=>/^Add$/i.test((b.textContent||'').trim()) && !b.disabled);
      if(adds.length){{adds[adds.length-1].click(); return 'neg-add-last';}}
      return 'neg-filled';
    }})()"""
        )
        time.sleep(2)

    # Create
    out, _ = ev(
        """(() => {
      const btns=[...document.querySelectorAll('button')].filter(b=>/^Create ad group$/i.test((b.textContent||'').trim()) && !b.disabled);
      if(!btns.length) return 'no-create-btn:'+[...document.querySelectorAll('button')].map(b=>(b.textContent||'').trim()).filter(Boolean).slice(0,20).join('|');
      btns[btns.length-1].click();
      return 'create-clicked:'+btns.length;
    })()"""
    )
    time.sleep(12)
    out, _ = ev(
        """(() => {
      const t=document.body.innerText;
      const m=location.href.match(/ad-groups\\/(A[A-Z0-9]+)/i);
      return JSON.stringify({
        url: location.href,
        id: m?m[1]:null,
        err: /fix these issues|weren.?t added|cannot create|Add at least one product|not eligible|not advertisable/i.test(t),
        snippet: t.replace(/\\s+/g,' ').slice(0,600)
      });
    })()"""
    )
    try:
        data = json.loads(re.search(r"\\{.*\\}", out, re.S).group(0))
    except Exception:
        data = {"raw": out}
    if data.get("id") and data["id"] != CAMPAIGN:
        return {"status": "created", "id": data["id"], "product": added, "detail": data}
    if data.get("err"):
        return {"status": "failed", "step": "create", "detail": data, "product": added}
    # maybe still on create page
    return {"status": "uncertain", "detail": data, "product": added}


def main():
    results = []

    # 1) Fix Realme C33
    print("=== FIX Realme C33 ===")
    mt = count_match_types("A07067373T44W28UTF7QN")
    print("C33 match types", mt)
    need_fix = True
    if isinstance(mt, dict) and mt.get("mt"):
        if mt["mt"].get("Broad", 0) >= 10 and mt["mt"].get("Exact", 0) >= 10:
            need_fix = False
    if need_fix:
        fix_out = add_missing_bpe("A07067373T44W28UTF7QN", "realme c33")
        print("C33 fix", fix_out)
        mt2 = count_match_types("A07067373T44W28UTF7QN")
        results.append({"stock": "Realme C33", "id": "A07067373T44W28UTF7QN", "status": "fixed", "before": mt, "after": mt2, "fix_out": fix_out})
    else:
        results.append({"stock": "Realme C33", "id": "A07067373T44W28UTF7QN", "status": "already_bpe", "detail": mt})

    # 2) Verify Realme C21
    print("=== VERIFY Realme C21 ===")
    links = search_ag("Realme C21")
    print("C21 links", links)
    c21_id = None
    for L in links if isinstance(links, list) else []:
        if isinstance(L, dict) and L.get("t", "").lower() == "realme c21":
            c21_id = L.get("id")
            break
    if not c21_id:
        for L in links if isinstance(links, list) else []:
            if isinstance(L, dict) and L.get("id"):
                c21_id = L["id"]
                break
    if c21_id:
        mt = count_match_types(c21_id)
        print("C21 mt", mt)
        need_fix = True
        if isinstance(mt, dict) and mt.get("mt"):
            if mt["mt"].get("Broad", 0) >= 5 and mt["mt"].get("Exact", 0) >= 5:
                need_fix = False
        if need_fix:
            fix_out = add_missing_bpe(c21_id, "realme c21")
            results.append({"stock": "Realme C21", "id": c21_id, "status": "exists_fixed", "before": mt, "fix_out": fix_out})
        else:
            results.append({"stock": "Realme C21", "id": c21_id, "status": "exists_enabled", "detail": mt})
    else:
        results.append({"stock": "Realme C21", "status": "not_found_will_create"})

    # Create queue
    queue = [
        {
            "stock": "Realme 11 Pro",
            "name": "Realme 11 Pro",
            "model_kw": "realme 11 pro",
            "asin": "B0F3JM7ZB1",
            "search": ["B0F3JM7ZB1", "Realme 11 Pro", "Realme 11 Pro+"],
            "title_re": r"Realme 11 Pro.*CareOG|Realme 11 Pro\\+",
            "negs": [],  # Pro group — Exact insurance optional; skip Phrase base
        },
        {
            "stock": "Realme 13 Pro",
            "name": "Realme 13 Pro",
            "model_kw": "realme 13 pro",
            "asin": "B0F3JKYJMY",
            "search": ["B0F3JKYJMY", "Realme 13 Pro", "Realme 13 Pro+"],
            "title_re": r"Realme 13 Pro.*CareOG|Realme 13 Pro\\+",
            "negs": [],
        },
        {
            "stock": "Realme 3 Pro",
            "name": "Realme 3 Pro",
            "model_kw": "realme 3 pro",
            "asin": "B0CPTF5XXM",
            "search": ["B0CPTF5XXM", "Realme 3 Pro"],
            "title_re": r"Realme 3 Pro.*CareOG|Realme 3 Pro",
            "negs": [],
        },
        {
            "stock": "Vivo X70 Pro Plus",
            "name": "Vivo X70 Pro Plus",
            "model_kw": "vivo x70 pro plus",
            "asin": "B0F3JL1YLV",
            "search": ["B0F3JL1YLV", "Vivo X70 Pro", "X70 Pro+"],
            "title_re": r"Vivo X70 Pro.*CareOG|X70 Pro\\+",
            "negs": [],
        },
        {
            "stock": "Vivo V11 Pro",
            "name": "Vivo V11 Pro",
            "model_kw": "vivo v11 pro",
            "asin": "B0CPTBQFNG",
            "search": ["B0CPTBQFNG", "Vivo V11 Pro"],
            "title_re": r"Vivo V11 Pro.*CareOG",
            "negs": [],
        },
        {
            "stock": "Vivo V15",
            "name": "Vivo V15",
            "model_kw": "vivo v15",
            "asin": "B0CPTCXZRQ",
            "search": ["B0CPTCXZRQ", "Vivo V15"],
            "title_re": r"Vivo V15.*CareOG|Compatible for Vivo V15",
            "negs": ["pro", "max", "pro max", "plus", "5g", "4g"],
        },
        {
            "stock": "Vivo X80",
            "name": "Vivo X80",
            "model_kw": "vivo x80",
            "asin": "B0F3JLSJ8R",
            "search": ["B0F3JLSJ8R", "Vivo X80"],
            "title_re": r"Vivo X80.*CareOG|Compatible for Vivo X80",
            "negs": ["pro", "max", "pro max", "plus", "5g", "4g"],
        },
    ]

    # If C21 missing, create it
    if any(r.get("stock") == "Realme C21" and r.get("status") == "not_found_will_create" for r in results):
        queue.insert(
            0,
            {
                "stock": "Realme C21",
                "name": "Realme C21",
                "model_kw": "realme c21",
                "asin": "B0C94VX6K9",
                "search": ["B0C94VX6K9", "Realme C21"],
                "title_re": r"Realme C21.*LCD|Compatible for Realme C21",
                "negs": ["pro", "max", "pro max", "plus", "5g", "4g"],
            },
        )

    for item in queue:
        print(f"=== CREATE/CHECK {item['stock']} ===")
        # dup check
        links = search_ag(item["name"])
        print("dup", links)
        existing = None
        for L in links if isinstance(links, list) else []:
            if isinstance(L, dict) and L.get("t", "").lower() == item["name"].lower():
                existing = L.get("id")
                break
        if existing:
            mt = count_match_types(existing)
            need_fix = True
            if isinstance(mt, dict) and mt.get("mt"):
                if mt["mt"].get("Broad", 0) >= 5 and mt["mt"].get("Exact", 0) >= 5:
                    need_fix = False
            if need_fix:
                fix_out = add_missing_bpe(existing, item["model_kw"])
                results.append({"stock": item["stock"], "id": existing, "status": "exists_fixed", "mt": mt, "fix_out": fix_out})
            else:
                results.append({"stock": item["stock"], "id": existing, "status": "exists_enabled", "mt": mt})
            continue

        res = create_ag(
            item["name"],
            item["model_kw"],
            item.get("asin"),
            item["search"],
            item["title_re"],
            item.get("negs") or [],
        )
        print("result", res)
        results.append({"stock": item["stock"], **res})
        OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # C67 skip note
    results.append({"stock": "Realme C67", "id": "A005394925BGXDRVMULPG", "status": "exists_enabled_skip_create"})
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("DONE", json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
