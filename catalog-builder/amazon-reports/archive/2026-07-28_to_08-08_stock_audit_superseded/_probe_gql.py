import json, re
from pathlib import Path
har=json.loads(Path(r"c:\Projects\Amazon Systems Design\catalog-builder\amazon-reports\_inv_har_fresh.har").read_text(encoding="utf-8"))
biggest=""
for e in har["log"]["entries"]:
    if "/myinventory/gql" not in e["request"]["url"]:
        continue
    text=(e["response"].get("content") or {}).get("text") or ""
    if len(text)>len(biggest):
        biggest=text
keys=set(re.findall(r'"([A-Za-z0-9_]*(?:[Qq]ty|[Qq]uantity|[Pp]rice|[Aa]vailable|[Ss]tatus)[A-Za-z0-9_]*)"', biggest))
print("keys", sorted(keys)[:100])
types=sorted(set(re.findall(r'"__typename":"([^"]+)"', biggest)))
print("types", types)
j=json.loads(biggest)

def find_objs(o, out=None, depth=0):
    if out is None: out=[]
    if depth>40 or len(out)>5: return out
    if isinstance(o, dict):
        kl=" ".join(o.keys()).lower()
        if ("quantity" in kl or "available" in kl or "yourprice" in kl) and len(o)>=2:
            out.append(dict(list(o.items())[:25]))
        for v in o.values():
            find_objs(v, out, depth+1)
    elif isinstance(o, list):
        for v in o:
            find_objs(v, out, depth+1)
    return out
objs=find_objs(j)
print("found", len(objs))
for o in objs[:4]:
    print(json.dumps(o, indent=2)[:900])
    print("---")