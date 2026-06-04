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

# Extract from listing title
def extract_from_title(title):
    t = title.lower()
    # Screen type
    if 'super oled' in t or 'amoled' in t or ('oled' in t and 'lcd' not in t and 'incell' not in t):
        listing_screen = 'OLED'
    elif 'incell' in t: listing_screen = 'Incell LCD'
    elif 'tft' in t: listing_screen = 'TFT LCD'
    elif 'lcd' in t: listing_screen = 'LCD'
    else: listing_screen = 'Not Specified'
    # Quality
    if 'careog' in t: listing_quality = 'CareOG'
    elif 'with frame' in t or '(with frame)' in t or ' wf ' in t: listing_quality = 'With Frame'
    else: listing_quality = 'Standard'
    return listing_screen, listing_quality

# Extract model numbers from title
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

# Extract stock model
def get_stock_model(original):
    model = original
    for skip in ['Realme ','Vivo ','Oppo ','OnePlus ','Apple iPhone ','Apple ',
                 'Samsung Galaxy ','Xiaomi ','Redmi ','Poco ','Moto ','Honor ','Nokia ',
                 'Asus ','Nothing Phone ','Infinix ']:
        model = model.replace(skip, '').replace(skip.lower(), '')
    for skip in ['Incell','OLED','AMOLED','CareOG','Careog','Frame','With','Standard','White','Black','Gold']:
        model = re.sub(r'\b' + skip + r'\b', '', model, flags=re.IGNORECASE)
    return ' '.join(model.split()).strip().lower()

# Build listing lookup: model -> list of (listing_row, screen, quality)
listing_by_model = defaultdict(list)
for row in listings:
    title = row.get('item-name','')
    if not title: continue
    ls, lq = extract_from_title(title)
    models = extract_models(title)
    for m in models:
        m_clean = m.replace(' ','')
        if len(m_clean) >= 2:
            listing_by_model[m_clean].append({
                'row': row,
                'listing_screen': ls,
                'listing_quality': lq,
                'title': title,
            })

# Match with screen+quality verification
out_lines = []
out_lines.append('STOCK vs LISTING - PROPER SCREEN TYPE MAPPING')
out_lines.append('=' * 140)
out_lines.append('')

brand_stats = defaultdict(lambda: {'total':0,'exact_match':0,'screen_mismatch':0,'quality_mismatch':0,'both_mismatch':0,'not_listed':0})

final_results = []

for s in stock:
    stock_model = get_stock_model(s['original_name'])
    s['model'] = stock_model

    # Find exact matches
    matches = listing_by_model.get(stock_model.replace(' ',''), [])

    # If no exact, try partial (first 4+ chars)
    if not matches:
        prefix = stock_model.replace(' ','')[:4]
        if len(prefix) >= 4:
            for m, lst in listing_by_model.items():
                if m.startswith(prefix) and len(m) >= 4:
                    matches.extend(lst)
        # Remove duplicates
    seen = {}
    unique = []
    for m in matches:
        sku = m['row']['seller-sku']
        if sku not in seen:
            seen[sku] = m
            unique.append(m)
    matches = unique

    active = [m for m in matches if m['row'].get('status') == 'Active']
    inactive = [m for m in matches if m['row'].get('status') != 'Active']

    result = {
        'stock': s,
        'matches': matches,
        'active': active,
        'inactive': inactive,
    }
    final_results.append(result)

# Categorize
exact_active = []      # stock screen/quality matches active listing
active_screen_mismatch = []  # active but screen/quality differs
inactive_screen_mismatch = []  # inactive and screen/quality differs
not_listed = []        # no listing at all

for r in final_results:
    s = r['stock']
    active = r['active']
    inactive = r['inactive']

    if active:
        # Find best active match (screen + quality match)
        good = []
        bad = []
        for a in active:
            screen_ok = (s['stock_screen'] == a['listing_screen'] or
                        (s['stock_screen'] == 'Incell LCD' and a['listing_screen'] == 'LCD') or
                        (s['stock_screen'] == 'LCD' and a['listing_screen'] == 'Incell LCD'))
            quality_ok = (s['stock_quality'] == a['listing_quality'] or
                         (s['stock_quality'] == 'Standard' and a['listing_quality'] == 'Standard'))

            if screen_ok and quality_ok:
                good.append(a)
            else:
                bad.append(a)

        if good:
            exact_active.append({'stock': s, 'listing': good[0], 'all_good': good})
            brand_stats[s['brand']]['exact_match'] += 1
        else:
            active_screen_mismatch.append({'stock': s, 'listings': active, 'best': bad[0]})
            # Categorize mismatch type
            sc = s['stock_screen']
            bc = bad[0]['listing_screen']
            sq = s['stock_quality']
            bq = bad[0]['listing_quality']
            if sc != bc and sq != bq: brand_stats[s['brand']]['both_mismatch'] += 1
            elif sc != bc: brand_stats[s['brand']]['screen_mismatch'] += 1
            elif sq != bq: brand_stats[s['brand']]['quality_mismatch'] += 1

    elif inactive:
        inactive_screen_mismatch.append({'stock': s, 'listings': inactive})
        brand_stats[s['brand']]['not_listed'] += 1  # no active but has inactive
    else:
        not_listed.append({'stock': s})
        brand_stats[s['brand']]['not_listed'] += 1

# Print detailed results
out_lines.append('SECTION 1: ACTIVE LISTINGS WITH SCREEN/QUALITY MATCH')
out_lines.append(f'Count: {len(exact_active)}')
out_lines.append('-' * 140)
for item in exact_active:
    st = item['stock']
    lt = item['listing']
    out_lines.append(f'[{st["brand"]}] {st["original_name"]} | qty:{st["qty"]} | screen:{st["stock_screen"]} | quality:{st["stock_quality"]}')
    out_lines.append(f'  MATCHED -> {lt["row"]["seller-sku"]} | qty:{lt["row"].get("quantity","?")} | Rs.{lt["row"].get("price","?")} | {lt["title"][:90]}')
    out_lines.append('')

out_lines.append('')
out_lines.append('SECTION 2: ACTIVE LISTINGS WITH SCREEN/QUALITY MISMATCH')
out_lines.append(f'Count: {len(active_screen_mismatch)}')
out_lines.append('-' * 140)
for item in active_screen_mismatch:
    st = item['stock']
    best = item['best']
    out_lines.append(f'[{st["brand"]}] {st["original_name"]} | qty:{st["qty"]} | STOCK: screen={st["stock_screen"]}, quality={st["stock_quality"]}')
    out_lines.append(f'  LISTING: {best["row"]["seller-sku"]} | screen={best["listing_screen"]}, quality={best["listing_quality"]} | {best["title"][:80]}')
    out_lines.append('')

out_lines.append('')
out_lines.append('SECTION 3: STOCK WITH ONLY INACTIVE LISTINGS')
out_lines.append(f'Count: {len(inactive_screen_mismatch)}')
out_lines.append('-' * 140)
for item in inactive_screen_mismatch:
    st = item['stock']
    best = item['listings'][0]
    out_lines.append(f'[{st["brand"]}] {st["original_name"]} | qty:{st["qty"]} | STOCK: screen={st["stock_screen"]}, quality={st["stock_quality"]}')
    out_lines.append(f'  INACTIVE: {best["row"]["seller-sku"]} | screen={best["listing_screen"]}, quality={best["listing_quality"]} | status:{best["row"].get("status","?")}')
    if len(item['listings']) > 1:
        out_lines.append(f'  ({len(item["listings"])} total inactive matches)')
    out_lines.append('')

out_lines.append('')
out_lines.append('SECTION 4: STOCK WITH NO LISTING AT ALL')
out_lines.append(f'Count: {len(not_listed)}')
out_lines.append('-' * 140)
for item in not_listed:
    st = item['stock']
    out_lines.append(f'[{st["brand"]}] {st["original_name"]} | qty:{st["qty"]} | screen:{st["stock_screen"]} | quality:{st["stock_quality"]}')

out_lines.append('')
out_lines.append('=' * 140)
out_lines.append('BRAND SUMMARY:')
out_lines.append('')
for b, d in sorted(brand_stats.items(), key=lambda x: -x[1]['total']):
    out_lines.append(f'  {b}: {d["total"]} variants | {d["exact_match"]} exact match | {d["screen_mismatch"]} screen mismatch | {d["quality_mismatch"]} quality mismatch | {d["both_mismatch"]} both mismatch | {d["not_listed"]} not listed/only inactive')

out_lines.append('')
out_lines.append(f'TOTAL: {len(stock)} variants')
out_lines.append(f'  Active + Exact Match: {len(exact_active)}')
out_lines.append(f'  Active + Mismatch: {len(active_screen_mismatch)}')
out_lines.append(f'  Inactive Only: {len(inactive_screen_mismatch)}')
out_lines.append(f'  Not Listed: {len(not_listed)}')

# Also show stock screen type distribution
out_lines.append('')
out_lines.append('STOCK SCREEN TYPES:')
st_counts = defaultdict(int)
for s in stock:
    st_counts[s['stock_screen']] += 1
for k,v in sorted(st_counts.items(), key=lambda x:-x[1]):
    out_lines.append(f'  {k}: {v}')

out_lines.append('')
out_lines.append('LISTING SCREEN TYPES (active):')
lt_counts = defaultdict(int)
for row in listings:
    if row.get('status') == 'Active':
        t = row.get('item-name','')
        if 'super oled' in t.lower() or 'amoled' in t.lower(): lt_counts['OLED'] += 1
        elif 'oled' in t.lower(): lt_counts['OLED'] += 1
        elif 'incell' in t.lower(): lt_counts['Incell LCD'] += 1
        elif 'tft' in t.lower(): lt_counts['TFT LCD'] += 1
        elif 'lcd' in t.lower(): lt_counts['LCD'] += 1
        else: lt_counts['Not Specified'] += 1
for k,v in sorted(lt_counts.items(), key=lambda x:-x[1]):
    out_lines.append(f'  {k}: {v}')

with open('proper_screen_check.txt','w',encoding='utf-8') as f:
    f.write('\n'.join(out_lines))

# Print summary
print(f'Active + Exact Match: {len(exact_active)}')
print(f'Active + Mismatch: {len(active_screen_mismatch)}')
print(f'Inactive Only: {len(inactive_screen_mismatch)}')
print(f'Not Listed: {len(not_listed)}')
print()
for b, d in sorted(brand_stats.items(), key=lambda x: -x[1]['total']):
    print(f'  {b}: {d["total"]} | {d["exact_match"]} exact | {d["screen_mismatch"]} screen mismatch | {d["quality_mismatch"]} quality mismatch | {d["not_listed"]} not/only inactive')
print()
print('Written to proper_screen_check.txt')