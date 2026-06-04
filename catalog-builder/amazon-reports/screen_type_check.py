import re
from collections import defaultdict

# Parse actual stock with proper screen type extraction
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

            # Screen type from stock file keywords
            if 'oled' in nl or 'amoled' in nl: screen_type = 'OLED'
            elif 'incell' in nl: screen_type = 'Incell LCD'
            elif 'tft' in nl: screen_type = 'TFT LCD'
            elif 'lcd' in nl: screen_type = 'LCD'
            else: screen_type = 'Not Specified'

            # Quality variant from stock file
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

print(f'Stock: {len(stock)} variants')
print()

# Extract screen type from listing title
def extract_screen_from_title(title):
    t = title.lower()
    if 'oled' in t or 'amoled' in t or 'super oled' in t: return 'OLED'
    if 'incell' in t: return 'Incell LCD'
    if 'tft' in t: return 'TFT LCD'
    if 'lcd' in t: return 'LCD'
    return 'Unknown'

# Extract quality from listing title
def extract_quality_from_title(title):
    t = title.lower()
    if 'careog' in t: return 'CareOG'
    if 'with frame' in t or ' wf ' in t or '(with frame)' in t: return 'With Frame'
    return 'Standard'

# Extract model from listing title
def extract_model_from_title(title):
    if not title or 'Compatible for' not in title: return []
    after = title.split('Compatible for', 1)[1].strip()
    for kw in ['CareOG','Careog','OLED','LCD','Incell','TFT','Amoled','AMOLED','Super OLED',
               'Fingerprint Support','No Fingerprint Support',
               'Display+Touch Screen Combo Folder','Display+Touch Screen Combo',
               'Display Screen Replacement Combo']:
        after = re.sub(r'\b' + kw + r'\b', ' ', after, flags=re.IGNORECASE)
    parts = after.split('/')
    models = []
    for part in parts:
        part = part.strip()
        for brand in ['Samsung Galaxy','Samsung','Vivo','Oppo','OnePlus','Apple iPhone','Apple',
                      'Redmi','Xiaomi','POCO','Motorola Moto','Moto','Realme','Infinix',
                      'Honor','Nokia','Asus','Nothing Phone','Nothing','Tecno']:
            part = re.sub(r'\b' + brand + r'\b', '', part, flags=re.IGNORECASE)
        part = ' '.join(part.split()).strip()
        if part and len(part) >= 1:
            models.append(part)
    return models

def extract_stock_model(original_name):
    model = original_name
    for skip in ['Realme ','Vivo ','Oppo ','OnePlus ','Apple iPhone ','Apple ',
                 'Samsung Galaxy ','Xiaomi ','Redmi ','Poco ','Moto ','Honor ','Nokia ',
                 'Asus ','Nothing Phone ','Infinix ']:
        model = model.replace(skip, '')
        model = model.replace(skip.lower(), '')
    for skip in ['Incell','OLED','AMOLED','CareOG','Careog','Frame','With','Standard','White','Black','Gold']:
        model = re.sub(r'\b' + skip + r'\b', '', model, flags=re.IGNORECASE)
    model = ' '.join(model.split()).strip()
    return model.lower()

# Build listing lookup by model
listing_data = []
for row in listings:
    title = row.get('item-name','')
    if not title: continue
    models = extract_model_from_title(title)
    listing_data.append({
        'row': row,
        'title': title,
        'models': models,
        'listing_screen': extract_screen_from_title(title),
        'listing_quality': extract_quality_from_title(title),
    })

# Match and compare screen types
results = []
for s in stock:
    stock_model = extract_stock_model(s['original_name'])
    s['model'] = stock_model

    matches = []
    for ld in listing_data:
        title = ld['title'].lower()
        orig_lower = s['original_name'].lower().replace(' ','')

        if stock_model and len(stock_model) >= 2:
            if stock_model in title:
                matches.append(ld)
                continue

        for lm in ld['models']:
            lm_clean = lm.lower().replace(' ','')
            if len(lm_clean) >= 2:
                if lm_clean in orig_lower or lm_clean[:4] in orig_lower:
                    matches.append(ld)
                    break

    # Deduplicate by SKU
    seen = set()
    unique_matches = []
    for m in matches:
        sku = m['row']['seller-sku']
        if sku not in seen:
            seen.add(sku)
            unique_matches.append(m)

    results.append({'stock': s, 'matches': unique_matches})

# Output with SCREEN TYPE MISMATCH detection
out_lines = []
out_lines.append('STOCK vs LISTING - SCREEN TYPE VERIFICATION')
out_lines.append('=' * 120)
out_lines.append('')

# Check for screen type mismatches
screen_mismatch = []
not_listed = []
active_ok = []
inactive_ok = []
inactive_no_stock = []
not_listed_at_all = []

for r in results:
    s = r['stock']
    matches = r['matches']

    active = [v for v in matches if v['row'].get('status') == 'Active']
    inactive = [v for v in matches if v['row'].get('status') != 'Active']

    if active:
        # Check screen type match
        for m in active:
            listing_screen = m['listing_screen']
            stock_screen = s['screen_type']
            listing_quality = m['listing_quality']
            stock_quality = s['quality']

            screen_ok = (stock_screen == listing_screen or
                        (stock_screen == 'Incell LCD' and listing_screen == 'LCD') or
                        (stock_screen == 'LCD' and listing_screen == 'Incell LCD') or
                        (stock_screen == 'OLED' and listing_screen == 'OLED'))
            quality_ok = (stock_quality == listing_quality or
                        (stock_quality == 'Standard' and listing_quality == 'Standard'))

            if not screen_ok or not quality_ok:
                screen_mismatch.append({
                    'stock': s,
                    'listing': m,
                    'stock_screen': stock_screen,
                    'listing_screen': listing_screen,
                    'stock_quality': stock_quality,
                    'listing_quality': listing_quality,
                })
            else:
                active_ok.append(s)

    elif inactive:
        for m in inactive:
            screen_mismatch.append({
                'stock': s,
                'listing': m,
                'stock_screen': s['screen_type'],
                'listing_screen': m['listing_screen'],
                'stock_quality': s['quality'],
                'listing_quality': m['listing_quality'],
            })
    else:
        not_listed_at_all.append(s)

out_lines.append('SCREEN TYPE MISMATCHES (Stock vs Listing):')
out_lines.append(f'(Total: {len(screen_mismatch)})')
out_lines.append('')
for item in screen_mismatch:
    s = item['stock']
    m = item['listing']
    out_lines.append(f'STOCK: [{s["brand"]}] {s["original_name"]} | qty:{s["qty"]} | screen:{s["screen_type"]} | quality:{s["quality"]}')
    out_lines.append(f'LIST: {m["row"]["seller-sku"]} | status:{m["row"]["status"]} | screen:{m["listing_screen"]} | quality:{m["listing_quality"]} | {m["title"][:80]}')
    out_lines.append('')

out_lines.append('=' * 120)
out_lines.append('SUMMARY:')
out_lines.append(f'  SCREEN TYPE MISMATCHES: {len(screen_mismatch)}')
out_lines.append(f'  ACTIVE + MATCHED OK: {len(active_ok)}')
out_lines.append(f'  NOT LISTED AT ALL: {len(not_listed_at_all)}')

# Also show what screen types are in the data
out_lines.append('')
out_lines.append('STOCK SCREEN TYPES:')
st_counts = defaultdict(int)
for s in stock:
    st_counts[s['screen_type']] += 1
for k,v in sorted(st_counts.items(), key=lambda x:-x[1]):
    out_lines.append(f'  {k}: {v}')

out_lines.append('')
out_lines.append('LISTING SCREEN TYPES (active only):')
lt_counts = defaultdict(int)
for row in listings:
    if row.get('status') == 'Active':
        t = row.get('item-name','')
        if 'oled' in t.lower() or 'amoled' in t.lower(): lt_counts['OLED'] += 1
        elif 'incell' in t.lower(): lt_counts['Incell LCD'] += 1
        elif 'tft' in t.lower(): lt_counts['TFT LCD'] += 1
        elif 'lcd' in t.lower(): lt_counts['LCD'] += 1
        else: lt_counts['Unknown'] += 1
for k,v in sorted(lt_counts.items(), key=lambda x:-x[1]):
    out_lines.append(f'  {k}: {v}')

with open('screen_type_check.txt','w',encoding='utf-8') as f:
    f.write('\n'.join(out_lines))

print(f'Screen mismatches: {len(screen_mismatch)}')
print(f'Active + matched ok: {len(active_ok)}')
print(f'Not listed at all: {len(not_listed_at_all)}')
print()
print('First 30 mismatches:')
count = 0
for line in open('screen_type_check.txt',encoding='utf-8').read().split('\n'):
    if 'STOCK: [' in line:
        count += 1
        if count <= 30:
            print(line)
    elif 'LIST:' in line and count <= 30:
        print(line)
        print()
print()
print('Written to screen_type_check.txt')