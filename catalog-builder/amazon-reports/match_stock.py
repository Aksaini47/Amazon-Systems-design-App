import re, csv
from collections import defaultdict

# Parse actual stock
with open('actual stock.txt','r',encoding='utf-8') as f:
    slines = f.readlines()
BRAND_KEYWORDS = ['REALME','VIVO','OPPO','ONEPLUS','APPLE','SAMSUNG','XIAOMI','REDMI','POCO','MIX','MOTO','HONOR','NOKIA','ASUS','NOTHING','INFINIX']
stock = []
current_brand = ''
for line in slines:
    stripped = line.rstrip().strip()
    if not stripped or stripped == 'actual stock': continue
    is_brand = stripped.isupper() and any(b in stripped for b in BRAND_KEYWORDS)
    if is_brand: current_brand = stripped
    else:
        name = stripped
        if name and current_brand:
            qty_match = re.search(r' - (\d+)$', name)
            qty = int(qty_match.group(1)) if qty_match else 1
            clean_name = re.sub(r' - \d+$', '', name).strip()
            nl = clean_name.lower()

            if 'oled' in nl or 'amoled' in nl: screen_type = 'OLED'
            elif 'incell' in nl: screen_type = 'Incell LCD'
            elif 'tft' in nl: screen_type = 'TFT LCD'
            elif 'lcd' in nl: screen_type = 'LCD'
            else: screen_type = 'Unknown'

            if 'careog' in nl: quality = 'CareOG'
            elif 'frame' in nl or ' wf ' in nl: quality = 'With Frame'
            else: quality = 'Standard'

            stock.append({
                'brand': current_brand,
                'original_name': clean_name,
                'qty': qty,
                'screen_type': screen_type,
                'quality': quality,
            })

# Parse All Listings
with open('All+Listings+Report_05-12-2026.txt','r',encoding='utf-8-sig') as f:
    lines = f.readlines()
hdr_idx = next(i for i,l in enumerate(lines) if 'seller-sku' in l)
hdrs = [c.strip() for c in lines[hdr_idx].split('\t')]
listings = []
for l in lines[hdr_idx+1:]:
    if not l.strip(): continue
    cols = [c.strip() for c in l.split('\t')]
    if len(cols) < len(hdrs): cols += [''] * (len(hdrs) - len(cols))
    row = dict(zip(hdrs, cols))
    listings.append(row)

print(f'Stock: {len(stock)} variants, Listings: {len(listings)} SKUs, Active: {len([l for l in listings if l.get("status")=="Active"])}')

QUALITY_KEYWORDS = ['CareOG', 'Careog', 'OLED', 'LCD', 'Incell', 'TFT', 'Amoled', 'AMOLED']
FINGERPRINT_KW = ['Fingerprint Support', 'No Fingerprint Support']

def extract_model_from_title(title):
    if not title or 'Compatible for' not in title: return []
    after_prefix = title.split('Compatible for', 1)[1].strip()
    text = after_prefix
    for kw in QUALITY_KEYWORDS + FINGERPRINT_KW:
        text = re.sub(r'\b' + kw + r'\b', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'Display\+Touch Screen Combo.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'LCD Display.*', '', text, flags=re.IGNORECASE)
    parts = text.split('/')
    models = []
    for part in parts:
        part = part.strip()
        for brand in ['Samsung Galaxy','Vivo','Oppo','OnePlus','Apple iPhone','Apple','Redmi','Xiaomi','POCO','Motorola Moto','Moto','Realme','Infinix','Honor','Nokia','Asus','Nothing Phone','Nothing','Tecno']:
            part = re.sub(r'\b' + brand + r'\b', '', part, flags=re.IGNORECASE)
        part = part.strip()
        if part:
            models.append(part)
    return models

def extract_quality_screen_from_title(title):
    title_lower = title.lower()
    quality = 'Standard'
    screen = 'LCD'
    if 'careog' in title_lower: quality = 'CareOG'
    elif 'with frame' in title_lower or 'wf' in title_lower: quality = 'With Frame'
    if 'oled' in title_lower or 'amoled' in title_lower: screen = 'OLED'
    elif 'incell' in title_lower: screen = 'Incell LCD'
    elif 'tft' in title_lower: screen = 'TFT LCD'
    return quality, screen

# Build listing lookup by normalized model
listing_by_model = defaultdict(list)
for row in listings:
    title = row.get('item-name','')
    if not title: continue
    models = extract_model_from_title(title)
    q, s = extract_quality_screen_from_title(title)
    for m in models:
        m_clean = m.lower().replace(' ','')
        listing_by_model[m_clean].append({
            'row': row,
            'title': title,
            'model_raw': m,
            'quality': q,
            'screen': s,
        })

# Also build a lookup by partial model match
listing_by_partial = defaultdict(list)
for row in listings:
    title = row.get('item-name','')
    if not title: continue
    models = extract_model_from_title(title)
    for m in models:
        m_clean = m.lower().replace(' ','')
        if len(m_clean) >= 3:
            listing_by_partial[m_clean[:3]].append({'row': row, 'title': title})

# Match stock items
results = []
for s in stock:
    original = s['original_name']
    nl = original.lower()

    # Extract model from stock name
    model = original
    for skip in ['Realme ','Vivo ','Oppo ','OnePlus ','Apple iPhone ','Apple ','Samsung Galaxy ',
                 'Xiaomi ','Redmi ','Poco ','Moto ','Honor ','Nokia ','Asus ','Nothing Phone ',
                 'Infinix ','Inc Cell','Inc ell','LCD ','OLED ','AMOLED ']:
        model = model.replace(skip, '')
        model = model.replace(skip.lower(), '')
    for skip in ['Incell','OLED','AMOLED','CareOG','Careog','Frame','With','Standard']:
        model = re.sub(r'\b' + skip + r'\b', '', model, flags=re.IGNORECASE)
    model = ' '.join(model.split()).strip().lower()
    s['model'] = model

    # Search
    matches = listing_by_model.get(model, [])

    if not matches and len(model) >= 3:
        prefix = model[:3]
        partial = listing_by_partial.get(prefix, [])
        # Filter to only those where model appears in title
        for p in partial:
            t = p['title'].lower()
            if model in t.replace(' ',''):
                if p['row'] not in [v['row'] for v in matches]:
                    matches.append(p)

    results.append({'stock': s, 'matches': matches})

# Output
out_lines = []
out_lines.append('STOCK vs AMAZON LISTING MATCHING')
out_lines.append('=' * 120)
out_lines.append('')

brand_counts = defaultdict(lambda: {'total':0,'active':0,'inactive':0,'not_listed':0})

for r in results:
    s = r['stock']
    matches = r['matches']
    brand_counts[s['brand']]['total'] += 1

    active = [v for v in matches if v['row'].get('status') == 'Active']
    inactive = [v for v in matches if v['row'].get('status') != 'Active']

    line = f'{s["brand"]}|{s["original_name"]}|qty:{s["qty"]}|screen:{s["screen_type"]}|quality:{s["quality"]}'

    if active:
        brand_counts[s['brand']]['active'] += 1
        for m in active:
            out_lines.append(f'ACTIVE   {line}')
            out_lines.append(f'         -> {m["row"]["seller-sku"]} | qty:{m["row"].get("quantity","?")} | Rs.{m["row"].get("price","?")} | {m["title"][:80]}')
        out_lines.append('')
    elif inactive:
        brand_counts[s['brand']]['inactive'] += 1
        out_lines.append(f'INACTIVE {line}')
        out_lines.append(f'         -> {inactive[0]["row"]["seller-sku"]} | status:{inactive[0]["row"].get("status","?")}')
        out_lines.append('')
    else:
        brand_counts[s['brand']]['not_listed'] += 1
        out_lines.append(f'NOT LISTED {line}')
        out_lines.append('')

active_total = sum(1 for r in results if any(v['row'].get('status')=='Active' for v in r['matches']))
inactive_total = sum(1 for r in results if any(v['row'].get('status')!='Active' for v in r['matches']) and not any(v['row'].get('status')=='Active' for v in r['matches']))
not_listed_total = sum(1 for r in results if not r['matches'])

out_lines.append('=' * 120)
out_lines.append('SUMMARY BY BRAND:')
out_lines.append('')
for b, d in sorted(brand_counts.items(), key=lambda x: -x[1]['total']):
    out_lines.append(f'  {b}: {d["total"]} stock | {d["active"]} ACTIVE | {d["inactive"]} INACTIVE | {d["not_listed"]} NOT LISTED')
out_lines.append('')
out_lines.append(f'TOTAL STOCK: {len(results)} variants, {sum(s["qty"] for s in stock)} units')
out_lines.append(f'  ACTIVE on Amazon: {active_total}')
out_lines.append(f'  INACTIVE on Amazon: {inactive_total}')
out_lines.append(f'  NOT LISTED at all: {not_listed_total}')

with open('stock_listing_match.txt','w',encoding='utf-8') as f:
    f.write('\n'.join(out_lines))

print('Written to stock_listing_match.txt')
print()
for line in out_lines[-20:]:
    print(line)