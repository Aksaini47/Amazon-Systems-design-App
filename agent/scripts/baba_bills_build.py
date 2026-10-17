"""Baba Mobile cash memos: parse the transcription (data/baba_bills/bills_raw.txt), run tally / duplicate / price checks,
write data/baba_bills/BABA_BILLS.md (date-wise blocks) and bills.csv (one row per line item).

  python agent/scripts/baba_bills_build.py

Quality words (Sir): FD = incell/LCD, incell/insell/inco/i4 = incell, LED/OLED = OLED (+AMOLED), OG = flag, old = old model.
Brand/model guesses are heuristics for review only; ambiguous ones are listed in the md for Sir to confirm."""
from __future__ import annotations

import csv
import itertools
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "baba_bills"
RAW = D / "bills_raw.txt"


def parse_date(s: str):
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2})", s.strip().rstrip("?"))
    if not m or "?" in s.split("?")[0]:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(2000 + y, mo, d)
    except ValueError:
        return None


def parse_items(txt: str):
    out = []
    for part in [p.strip() for p in txt.split(";") if p.strip()]:
        m = re.match(r"(?:(\d+)x\s+)?(.*?)(?:\s*@\s*(\d+))?\s*=\s*(\d+)$", part)
        if not m:
            raise ValueError("bad item: " + part)
        qty = int(m.group(1) or 1)
        out.append({"qty": qty, "raw": m.group(2).strip(), "rate": int(m.group(3)) if m.group(3) else None, "amount": int(m.group(4))})
    return out


def quality_of(raw: str) -> tuple[str, list[str]]:
    t = raw.lower()
    flags = []
    if re.search(r"\bold\b", t):
        flags.append("old")
    if "blp" in t:
        return "BATTERY?", flags
    if "panel" in t:
        return "PANEL", flags
    if re.search(r"\bdt\b", t):
        return "NON-SCREEN?", flags
    if re.search(r"\bog\b", t):
        return "CareOG", flags            # Sir: OG = CareOG
    if "gx" in t:
        return "GX/OLED", flags
    if re.search(r"o?led\b", t):
        return "OLED", flags
    if re.search(r"incell|insell|inco\b|\bi4\b|\bi\b", t) or re.search(r"\bfd\b", t):
        return "INCELL/LCD", flags
    return "UNTAGGED", flags


def guess(raw: str):
    """(brand, model, confidence, why). Heuristic only."""
    t = re.sub(r"\b(fd|incell|insell|inco|i4|oled|led|og|old|black|white)\b", " ", raw, flags=re.I)
    t = re.sub(r"[?()]", " ", t); t = re.sub(r"\s+", " ", t).strip()
    tl = t.lower()
    rules = [
        (r"^(rm|realme)\s*(.+)", "Realme", "high" , "RM = Realme"), (r"^xt\b", "Realme", "high", "XT = Realme XT"),
        (r"^nt\s*(.+)", "Redmi", "high", "NT = Redmi Note"), (r"^(mi|poco)\b", "Xiaomi/Poco", "medium", "Mi/Poco"),
        (r"^(sam|samsung)\s*(.+)", "Samsung", "high", "written Samsung"), (r"^m\s?\d+", "Samsung", "medium", "M+number = Galaxy M"),
        (r"^j\s?\d+", "Samsung", "medium", "J+number = Galaxy J"), (r"^(1\+|ce2|nord|10r)", "OnePlus", "high", "1+/CE/Nord"),
        (r"^i[p]?\s?(\d|x|s)", "Apple", "medium", "iP"), (r"^iphone", "Apple", "high", "written"), (r"^(vivo|v\d|s1|s6|y\d|va\d|u\d|iqoo|k10)", "Vivo", "medium", "V/Y/S/iQOO"),
        (r"^(oppo|f\d|reno|c55)", "Oppo/Other", "low", "F/Reno/C55"), (r"^(moto|g\d{2,3}|fusion|one power|one fusion|e3)", "Motorola", "medium", "Moto G/Fusion/Power"),
        (r"^camon", "Tecno", "high", "Camon = Tecno Camon (Sir)"), (r"^(hot|smart|spark)", "Infinix/Tecno", "medium", "Hot/Smart/Spark"), (r"^(honor|h\d)", "Honor", "medium", "Honor"), (r"^(asus|pro m1)", "Asus", "medium", "Pro M1"),
        (r"^a\s?\d+", "Samsung/Oppo", "low", "A+number: Sir says brand follows from model uniqueness"), (r"^note\b", "Redmi/Infinix", "low", "Note N ambiguous"),
    ]
    for pat, brand, conf, why in rules:
        if re.search(pat, tl):
            return brand, t, conf, why
    return "?", t, "low", "no rule"


def suggest(items, written):
    """Try 6<->8 and 5<->6 slips (one or two amounts) that make the sum match the written sum."""
    amts = [i["amount"] for i in items]
    def variants(a):
        v = {a}
        s = str(a)
        for i, ch in enumerate(s):
            for x, y in (("6", "8"), ("8", "6"), ("5", "6"), ("6", "5"), ("0", "8"), ("8", "0")):
                if ch == x:
                    v.add(int(s[:i] + y + s[i + 1:]))
        return v
    for r in (1, 2):
        for idx in itertools.combinations(range(len(amts)), r):
            for combo in itertools.product(*[variants(amts[i]) - {amts[i]} for i in idx]):
                new = amts[:]
                for i, c in zip(idx, combo):
                    new[i] = c
                if sum(new) == written:
                    return [(items[i]["raw"], amts[i], c) for i, c in zip(idx, combo)]
    return None


def main() -> int:
    bills = []
    for ln in RAW.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        f = ln.split("|")
        img, pos, dt, wsum, baki, wtot, notes = f[:7]
        items = parse_items("|".join(f[7:]))
        b = {"img": int(img), "pos": int(pos), "date_raw": dt, "date": parse_date(dt), "wsum": int(wsum) if wsum else None, "baki": int(baki) if baki != "" else None,
             "wtot": int(wtot) if wtot else None, "notes": notes.strip(), "items": items}
        b["csum"] = sum(i["amount"] for i in items)
        b["flags"] = []
        if b["wsum"] is not None and b["csum"] != b["wsum"]:
            b["flags"].append(f"SUM items {b['csum']} != written {b['wsum']}")
            sug = suggest(items, b["wsum"])
            if sug:
                b["flags"].append("likely slip: " + "; ".join(f"{r}: {a}->{c}" for r, a, c in sug))
        if b["wtot"] is not None and b["baki"] is not None and b["wsum"] is not None and b["wsum"] + b["baki"] != b["wtot"]:
            b["flags"].append(f"TOTAL {b['wsum']} + baki {b['baki']} != written {b['wtot']}")
        for it in items:
            if it["rate"] and it["qty"] * it["rate"] != it["amount"]:
                b["flags"].append(f"QTY {it['qty']} x {it['rate']} != {it['amount']}")
        if b["date"] is None:
            b["flags"].append("DATE missing/unclear")
        bills.append(b)
    bills.sort(key=lambda b: (b["date"] or date(2099, 1, 1), b["img"], b["pos"]))
    # duplicates
    sig = defaultdict(list)
    for b in bills:
        sig[tuple(sorted((i["raw"].lower(), i["amount"]) for i in b["items"]))].append(b)
    dups = [v for v in sig.values() if len(v) > 1]
    same_day = defaultdict(list)
    for b in bills:
        if b["date"]:
            same_day[b["date"]].append(b)
    # item rows
    rows, rate_by = [], defaultdict(list)
    amb = Counter()
    for b in bills:
        for it in b["items"]:
            q, fl = quality_of(it["raw"]); br, md, conf, why = guess(it["raw"])
            unit = it["rate"] or it["amount"] // it["qty"]
            rows.append({"date": b["date"].isoformat() if b["date"] else "", "date_raw": b["date_raw"], "img": b["img"], "pos": b["pos"], "raw": it["raw"], "qty": it["qty"], "unit_rate": unit, "amount": it["amount"],
                         "quality": q, "flags": ",".join(fl), "brand_guess": br, "model_guess": md, "confidence": conf})
            rate_by[(br, md.lower(), q)].append((unit, b["date"]))
            if conf != "high":
                amb[(it["raw"], br, md, conf, why)] += 1
    with (D / "bills.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    # markdown
    L = ["# Baba Mobile cash memos - date-wise (first pass, 2026-10-16)", "",
         f"Source: 14 WhatsApp photos in `data/baba_bills/raw/` (73 memos; Subhash / Hans memo books, party 'Arun Patoudi'). Transcribed by the assistant from the photos; amounts are as read, items with a doubtful reading carry `?`. "
         "Quality: FD = incell/LCD, incell = incell, OLED/LED = OLED. 'baki' = previous balance carried on the memo.", ""]
    n_items = sum(len(b["items"]) for b in bills); tot = sum(b["csum"] for b in bills)
    L += [f"**{len(bills)} memos, {n_items} line items, Rs{tot:,} of goods (sum of read item amounts).** Flagged memos: {sum(1 for b in bills if b['flags'])}.", ""]
    cur = None
    for b in bills:
        key = b["date"].strftime("%Y-%m") if b["date"] else "undated"
        if key != cur:
            L += [f"## {key}", ""]; cur = key
        d = b["date"].strftime("%d %b %Y") if b["date"] else f"undated ({b['date_raw']})"
        L.append(f"### {d} - memo img{b['img']:02d}/{b['pos']}  (items Rs{b['csum']:,}" + (f", baki Rs{b['baki']:,}" if b["baki"] is not None else "") + (f", total Rs{b['wtot']:,}" if b["wtot"] else "") + ")")
        for it in b["items"]:
            q, fl = quality_of(it["raw"]); L.append(f"- {it['qty']}x {it['raw']} - Rs{it['amount']:,}" + (f" (@{it['rate']})" if it["rate"] else "") + f"  [{q}{' ' + ','.join(fl) if fl else ''}]")
        if b["notes"]:
            L.append(f"- note: {b['notes']}")
        for fl in b["flags"]:
            L.append(f"- **CHECK:** {fl}")
        L.append("")
    L += ["## Tally and ledger checks", ""]
    bad = [b for b in bills if b["flags"]]
    L.append(f"- Memos whose read items do not add up to the written sum: {sum(1 for b in bills if any(f.startswith('SUM') for f in b['flags']))} (listed above with the likely 6/8 or 5/6 slip).")
    L.append(f"- Memos where written sum + baki != written total: {sum(1 for b in bills if any(f.startswith('TOTAL') for f in b['flags']))}.")
    L.append(f"- Undated memos: {sum(1 for b in bills if b['date'] is None)}. Years to confirm: 29/9/25 (two memos), 31/3/24 (read as 2026), 28/9/26 'Arun Online'.")
    L += ["", "### Running balance (baki) chain - implied payments", "", "| memo | items | baki | total | previous total | implied payment |", "|---|---|---|---|---|---|"]
    prev_total = None
    for b in bills:
        if b["wtot"] is not None or b["baki"] is not None:
            tot_b = b["wtot"] if b["wtot"] is not None else (b["csum"] + (b["baki"] or 0))
            pay = (prev_total - b["baki"]) if (prev_total is not None and b["baki"] is not None) else None
            L.append(f"| {b['date_raw']} img{b['img']:02d}/{b['pos']} | {b['csum']:,} | {b['baki'] if b['baki'] is not None else ''} | {tot_b:,} | {prev_total if prev_total is not None else ''} | {pay if pay is not None else ''} |")
            prev_total = tot_b
    L += ["", "### Possible duplicates", ""]
    if dups:
        for v in dups:
            L.append("- " + " vs ".join(f"{b['date_raw']} img{b['img']:02d}/{b['pos']}" for b in v) + f" (same items+amounts: {', '.join(i['raw'] for i in v[0]['items'][:3])}...)")
    else:
        L.append("- No memo repeats the same item+amount set. Same-day pairs: " + (", ".join(f"{k:%d %b %Y}" for k, v in same_day.items() if len(v) > 1) or "none") + ".")
    L += ["", "### Rate spread by item (same model + quality, different rates)", "", "| item | quality | rates seen | n |", "|---|---|---|---|"]
    for (br, md, q), v in sorted(rate_by.items(), key=lambda kv: -len(kv[1])):
        rates = sorted({r for r, _ in v})
        if len(v) >= 3 and len(rates) > 1 and q in ("INCELL/LCD", "OLED"):
            L.append(f"| {br} {md} | {q} | {', '.join(map(str, rates))} | {len(v)} |")
    L += ["", "### Names to confirm (guess confidence below high)", "", "| as written | guess | confidence | times |", "|---|---|---|---|"]
    for (raw, br, md, conf, why), n in sorted(amb.items(), key=lambda kv: -kv[1])[:80]:
        L.append(f"| {raw} | {br} / {md} | {conf} ({why}) | {n} |")
    (D / "BABA_BILLS.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"memos {len(bills)} | items {n_items} | goods Rs{tot:,} | flagged memos {len(bad)} | dups {len(dups)} | undated {sum(1 for b in bills if b['date'] is None)}")
    for b in bad:
        print(f"  img{b['img']:02d}/{b['pos']} {b['date_raw']}: " + " || ".join(b["flags"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
