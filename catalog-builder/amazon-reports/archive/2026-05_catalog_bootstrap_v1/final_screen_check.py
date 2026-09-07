import re
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

            # Screen type from stock file
            if 'oled' in nl or 'amoled' in nl: stock_screen = 'OLED'
            elif 'incell' in nl: stock_screen = 'Incell LCD'
            elif 'tft' in nl: stock_screen = 'TFT LCD'
            elif 'lcd' in nl: stock_screen = 'LCD'
            else: stock_screen = 'Not Specified'

            # Quality from stock file
            if 'careog' in nl: stock_quality = 'CareOG'
            elif 'frame' in nl or ' wf ' in nl: stock_quality = 'With Frame'
            else: stock_quality = 'Standard'

            stock.append({
                'brand': current_brand,
                'original_name': clean_name,
                'qty': qty,
                'stock_screen': stock_screen,
                'stock_quality': stock_quality,
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

print(f'Stock: {len(stock)} variants, Listings: {len(listings)} SKUs')
print()

def extract_from_title(title):
    t = title.lower()
    # Screen type
    if 'super oled' in t or 'amoled' in t or ('oled' in t and 'lcd' not in t and 'incell' not in t):
        ls = 'OLED'
    elif 'incell' in t: ls = 'Incell LCD'
    elif 'tft' in t: ls = 'TFT LCD'
    elif 'lcd' in t: ls = 'LCD'
    else: ls = 'Not Specified'
    # Quality
    if 'careog' in t: lq = 'CareOG'
    elif 'with frame' in t or '(with frame)' in t or ' wf ' in t: lq = 'With Frame'
    else: lq = 'Standard'
    return ls, lq

def extract_models(title):
    if not title or 'Compatible for' not in title: return []
    after = title.split('Compatible for', 1)[1].strip()
    for kw in ['CareOG','Careog','OLED','LCD','Incell','TFT','Amoled','AMOLED','Super OLED',
               'Fingerprint Support','No Fingerprint Support',
               'Display+Touch Screen Combo','Display Screen Replacement Combo',
               'Black','White','Gold']:
        after = re.sub(r'\b' + kw + r'\b', ' ', after, flags=re.IGNORECASE)
    parts = after.split('/')
    models = []
    for part in parts:
        part = part.strip()
        for brand in ['Samsung Galaxy','Samsung','Vivo','Oppo','OnePlus','Apple iPhone','Apple',
                      'Redmi','Xiaomi','POCO','Motorola Moto','Moto','Realme','Infinix',
                      'Honor','Nokia','Asus','Nothing Phone','Nothing','Tecno','itel','iTel']:
            part = re.sub(r'\b' + brand + r'\b', '', part, flags=re.IGNORECASE)
        part = ' '.join(part.split()).strip()
        if part:
            models.append(part.lower())
    return models

def get_stock_model(original):
    model = original
    for skip in ['Realme ','Vivo ','Oppo ','OnePlus ','Apple iPhone ','Apple ',
                 'Samsung Galaxy ','Xiaomi ','Redmi ','Poco ','Moto ','Honor ','Nokia ',
                 'Asus ','Nothing Phone ','Infinix ']:
        model = model.replace(skip, '').replace(skip.lower(), '')
    for skip in ['Incell','OLED','AMOLED','CareOG','Careog','Frame','With','Standard','White','Black','Gold']:
        model = re.sub(r'\b' + skip + r'\b', '', model, flags=re.IGNORECASE)
    return ' '.join(model.split()).strip().lower()

# Build listing index by MODEL+SCREEN+QUALITY
# Key: model_clean + '|' + listing_screen + '|' + listing_quality
listing_index = defaultdict(list)
for row in listings:
    title = row.get('item-name','')
    if not title: continue
    ls, lq = extract_from_title(title)
    models = extract_models(title)
    for m in models:
        key = m.replace(' ','') + '|' + ls + '|' + lq
        listing_index[key].append({
            'row': row,
            'listing_screen': ls,
            'listing_quality': lq,
            'title': title,
        })

# Also build index by model only (loose search)
listing_by_model = defaultdict(list)
for row in listings:
    title = row.get('item-name','')
    if not title: continue
    ls, lq = extract_from_title(title)
    models = extract_models(title)
    for m in models:
        key = m.replace(' ','')
        listing_by_model[key].append({
            'row': row,
            'listing_screen': ls,
            'listing_quality': lq,
            'title': title,
        })

# Match with strict screen+quality first, then loose
def find_matches(stock_item):
    model = get_stock_model(stock_item['original_name'])
    model_key = model.replace(' ','')
    ss = stock_item['stock_screen']
    sq = stock_item['stock_quality']

    # Normalize: Incell LCD <-> LCD are treated as same
    screen_equiv = {'Incell LCD': 'LCD', 'TFT LCD': 'LCD', 'OLED': 'OLED', 'LCD': 'LCD', 'Not Specified': 'Not Specified'}

    # STRICT: exact model + exact screen + exact quality
    strict_key = model_key + '|' + ss + '|' + sq
    matches = listing_index.get(strict_key, [])

    if not matches:
        # LOOSE: exact model + same screen family + same quality
        ss_norm = screen_equiv.get(ss, ss)
        for key, lst in listing_index.items():
            if key.startswith(model_key) and len(model_key) >= 3:
                # Check screen family match
                parts = key.split('|')
                if len(parts) == 3:
                    ls_key, lq_key = parts[1], parts[2]
                    ls_norm = screen_equiv.get(ls_key, ls_key)
                    if ls_norm == ss_norm and lq_key == sq:
                        matches.extend(lst)

    # Remove duplicates by SKU
    seen = {}
    unique = []
    for m in matches:
        sku = m['row']['seller-sku']
        if sku not in seen:
            seen[sku] = m
            unique.append(m)
    return unique

# Categorize
exact_active = []
active_mismatch = []
inactive_only = []
not_listed = []

brand_stats = defaultdict(lambda: {'total':0,'exact_active':0,'active_mismatch':0,'inactive':0,'not_listed':0})

for s in stock:
    matches = find_matches(s)
    active = [m for m in matches if m['row'].get('status') == 'Active']
    inactive = [m for m in matches if m['row'].get('status') != 'Active']
    brand_stats[s['brand']]['total'] += 1

    if active:
        # Check if screen+quality matches
        ss = s['stock_screen']
        sq = s['stock_quality']
        screen_equiv = {'Incell LCD': 'LCD', 'TFT LCD': 'LCD', 'OLED': 'OLED', 'LCD': 'LCD', 'Not Specified': 'Not Specified'}
        ss_norm = screen_equiv.get(ss, ss)

        ok_matches = []
        bad_matches = []
        for a in active:
            ls_norm = screen_equiv.get(a['listing_screen'], a['listing_screen'])
            if ls_norm == ss_norm and a['listing_quality'] == sq:
                ok_matches.append(a)
            else:
                bad_matches.append(a)

        if ok_matches:
            exact_active.append({'stock': s, 'listing': ok_matches[0], 'all_good': ok_matches})
            brand_stats[s['brand']]['exact_active'] += 1
        else:
            active_mismatch.append({'stock': s, 'listings': active, 'mismatch_reason': f'stock={ss}/{sq} vs listing={bad_matches[0]["listing_screen"]}/{bad_matches[0]["listing_quality"]}'})
            brand_stats[s['brand']]['active_mismatch'] += 1

    elif inactive:
        inactive_only.append({'stock': s, 'listings': inactive})
        brand_stats[s['brand']]['inactive'] += 1
    else:
        not_listed.append({'stock': s})
        brand_stats[s['brand']]['not_listed'] += 1

# Output
out = []
out.append('PROPER SCREEN TYPE MAPPING - FINAL RESULTS')
out.append('=' * 140)
out.append('')
out.append(f'TOTAL STOCK: {len(stock)} variants, {sum(s["qty"] for s in stock)} units')
out.append(f'ACTIVE + EXACT MATCH (stock screen/quality = listing screen/quality): {len(exact_active)}')
out.append(f'ACTIVE + MISMATCH (stock screen/quality differs from listing): {len(active_mismatch)}')
out.append(f'ONLY INACTIVE LISTINGS (no active listing for this screen/quality combo): {len(inactive_only)}')
out.append(f'NOT LISTED AT ALL (no listing found for this model): {len(not_listed)}')
out.append('')

out.append('-' * 140)
out.append('ACTIVE + EXACT MATCH:')
out.append('-' * 140)
for item in exact_active:
    st = item['stock']
    lt = item['listing']
    out.append(f'[{st["brand"]}] {st["original_name"]} | qty:{st["qty"]} | STOCK: {st["stock_screen"]} / {st["stock_quality"]}')
    out.append(f'  -> {lt["row"]["seller-sku"]} | listing_qty:{lt["row"].get("quantity","?")} | Rs.{lt["row"].get("price","?")} | LISTING: {lt["listing_screen"]} / {lt["listing_quality"]}')
    out.append(f'    {lt["title"][:100]}')
    out.append('')

out.append('')
out.append('-' * 140)
out.append('ACTIVE + SCREEN/QUALITY MISMATCH:')
out.append('-' * 140)
for item in active_mismatch:
    st = item['stock']
    best = item['listings'][0]
    out.append(f'[{st["brand"]}] {st["original_name"]} | qty:{st["qty"]} | STOCK: {st["stock_screen"]} / {st["stock_quality"]}')
    out.append(f'  -> {best["row"]["seller-sku"]} | LISTING: {best["listing_screen"]} / {best["listing_quality"]} | {best["title"][:90]}')
    if len(item['listings']) > 1:
        out.append(f'  ({len(item["listings"])} active matches for this model - different variants)')
    out.append('')

out.append('')
out.append('-' * 140)
out.append('ONLY INACTIVE LISTINGS:')
out.append('-' * 140)
for item in inactive_only:
    st = item['stock']
    best = item['listings'][0]
    out.append(f'[{st["brand"]}] {st["original_name"]} | qty:{st["qty"]} | STOCK: {st["stock_screen"]} / {st["stock_quality"]}')
    out.append(f'  -> {best["row"]["seller-sku"]} | status:{best["row"].get("status","?")} | LISTING: {best["listing_screen"]} / {best["listing_quality"]} | {best["title"][:90]}')
    out.append('')

out.append('')
out.append('-' * 140)
out.append('NOT LISTED AT ALL:')
out.append('-' * 140)
for item in not_listed:
    st = item['stock']
    out.append(f'[{st["brand"]}] {st["original_name"]} | qty:{st["qty"]} | screen:{st["stock_screen"]} | quality:{st["stock_quality"]}')

out.append('')
out.append('=' * 140)
out.append('BRAND SUMMARY:')
out.append('')
for b, d in sorted(brand_stats.items(), key=lambda x: -x[1]['total']):
    out.append(f'  {b}: {d["total"]} stock | {d["exact_active"]} active match | {d["active_mismatch"]} active mismatch | {d["inactive"]} inactive only | {d["not_listed"]} not listed')

out.append('')
out.append('STOCK SCREEN TYPES:')
sc = defaultdict(int)
for s in stock: sc[s['stock_screen']] += 1
for k,v in sorted(sc.items(), key=lambda x:-x[1]): out.append(f'  {k}: {v}')

out.append('')
out.append('ACTIVE LISTING SCREEN TYPES:')
lc = defaultdict(int)
for row in listings:
    if row.get('status') == 'Active':
        t = row.get('item-name','').lower()
        if 'super oled' in t or 'amoled' in t: lc['OLED'] += 1
        elif 'oled' in t: lc['OLED'] += 1
        elif 'incell' in t: lc['Incell LCD'] += 1
        elif 'tft' in t: lc['TFT LCD'] += 1
        elif 'lcd' in t: lc['LCD'] += 1
        else: lc['Unknown'] += 1
for k,v in sorted(lc.items(), key=lambda x:-x[1]): out.append(f'  {k}: {v}')

with open('final_screen_check.txt','w',encoding='utf-8') as f:
    f.write('\n'.join(out))

# Summary print
print(f'EXACT ACTIVE: {len(exact_active)}')
print(f'ACTIVE MISMATCH: {len(active_mismatch)}')
print(f'INACTIVE ONLY: {len(inactive_only)}')
print(f'NOT LISTED: {len(not_listed)}')
print()
for b, d in sorted(brand_stats.items(), key=lambda x: -x[1]['total']):
    print(f'  {b}: {d["total"]} | {d["exact_active"]} exact | {d["active_mismatch"]} mismatch | {d["inactive"]} inactive | {d["not_listed"]} none')
print()
print('Done. Written to final_screen_check.txt')