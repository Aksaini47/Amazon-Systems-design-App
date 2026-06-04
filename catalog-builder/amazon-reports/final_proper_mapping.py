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
            if 'oled' in nl or 'amoled' in nl: ss = 'OLED'
            elif 'incell' in nl: ss = 'Incell LCD'
            elif 'tft' in nl: ss = 'TFT LCD'
            elif 'lcd' in nl: ss = 'LCD'
            else: ss = 'Not Specified'
            if 'careog' in nl: sq = 'CareOG'
            elif 'frame' in nl or ' wf ' in nl: sq = 'With Frame'
            else: sq = 'Standard'
            stock.append({'brand': current_brand, 'original_name': clean_name, 'qty': qty, 'stock_screen': ss, 'stock_quality': sq})

with open('All+Listings+Report_05-12-2026.txt','r',encoding='utf-8-sig') as f:
    lines = f.readlines()
hdr_idx = next(i for i,l in enumerate(lines) if 'seller-sku' in l)
hdrs = [c.strip() for c in lines[hdr_idx].split('\t')]
listings = []
for l in lines[hdr_idx+1:]:
    if not l.strip(): continue
    cols = [c.strip() for c in l.split('\t')]
    if len(cols) < len(hdrs): cols += [''] * (len(hdrs) - len(cols))
    listings.append(dict(zip(hdrs, cols)))

# Extract clean base model from listing title
# e.g. "Compatible for Apple iPhone 13 Pro Max GX Amoled..." -> "13promax"
# e.g. "Compatible for Samsung Galaxy A73 (Fingerprint Support) OLED..." -> "a73"
# e.g. "Compatible for Realme C53 CareOG..." -> "c53"
def extract_clean_model(title):
    if not title or 'Compatible for' not in title: return []
    after = title.split('Compatible for', 1)[1].strip()
    # Remove everything after quality/display keywords (simple string replace)
    for kw in ['CareOG', 'Careog', 'OLED', 'LCD', 'Incell', 'TFT', 'Amoled', 'AMOLED', 'Super OLED',
               'Fingerprint Support', 'No Fingerprint Support', 'Display+Touch Screen Combo',
               'Display Screen Replacement Combo', 'Display Screen Combo', 'Screen Combo']:
        after = re.sub(re.escape(kw), ' ', after, flags=re.IGNORECASE)
    # Remove "with Frame" variants
    after = re.sub(r'with\s+frame', ' ', after, flags=re.IGNORECASE)
    # Remove color specs
    for kw in ['Black', 'White', 'Gold']:
        after = after.replace(kw, ' ')
    # Remove brands
    for brand in ['Samsung Galaxy','Samsung','Vivo','Oppo','OnePlus','Apple iPhone','Apple',
                  'Redmi','Xiaomi','POCO','Motorola Moto','Moto','Realme','Infinix',
                  'Honor','Nokia','Asus','Nothing Phone','Nothing','Tecno','itel','iTel']:
        after = re.sub(brand, ' ', after, flags=re.IGNORECASE)
    # Split by / for multi-model
    parts = after.split('/')
    models = []
    for part in parts:
        part = part.strip()
        if not part: continue
        # Remove parenthetical content like "(4G)", "(5G)", "(Fingerprint Support)"
        part = re.sub(r'\([^)]*\)', '', part)
        # Remove "Plus", "Pro", "Max", "GX", "FE" variants for clean match
        # BUT keep them for now, normalize to alphanumeric only
        part = re.sub(r'[^a-z0-9]', '', part.lower())
        if len(part) >= 2:
            # Special: collapse letter+number patterns
            # e.g. "13promax" stays, "j7nxt" stays
            models.append(part)
    return models

def get_clean_stock_model(original):
    # e.g. "Apple iPhone 13 Pro Max OLED" -> "13promax"
    # e.g. "Samsung Galaxy J7 Next Incell" -> "j7next"
    model = original
    for skip in ['Realme ','Vivo ','Oppo ','OnePlus ','Apple iPhone ','Apple ',
                 'Samsung Galaxy ','Xiaomi ','Redmi ','Poco ','Moto ','Honor ','Nokia ',
                 'Asus ','Nothing Phone ','Infinix ']:
        model = model.replace(skip, '').replace(skip.lower(), '')
    # Remove quality/screen keywords
    for skip in ['Incell','OLED','AMOLED','CareOG','Careog','Frame','With','Standard','White','Black','Gold']:
        model = re.sub(r'\b' + skip + r'\b', '', model, flags=re.IGNORECASE)
    # Remove parenthetical and non-alphanumeric
    model = re.sub(r'\([^)]*\)', '', model)
    model = re.sub(r'[^a-z0-9]', '', model.lower())
    return model

def extract_from_title(title):
    t = title.lower()
    if 'super oled' in t or 'amoled' in t or ('oled' in t and 'lcd' not in t and 'incell' not in t): ls = 'OLED'
    elif 'incell' in t: ls = 'Incell LCD'
    elif 'tft' in t: ls = 'TFT LCD'
    elif 'lcd' in t: ls = 'LCD'
    else: ls = 'Not Specified'
    if 'careog' in t: lq = 'CareOG'
    elif 'with frame' in t or '(with frame)' in t or ' wf ' in t: lq = 'With Frame'
    else: lq = 'Standard'
    return ls, lq

# Build listing index by CLEAN model
listing_by_model = defaultdict(list)
for row in listings:
    title = row.get('item-name','')
    if not title: continue
    ls, lq = extract_from_title(title)
    models = extract_clean_model(title)
    for m in models:
        listing_by_model[m].append({'row': row, 'listing_screen': ls, 'listing_quality': lq, 'title': title})

# Also build by partial (first 4+ chars) for fuzzy matching
listing_by_prefix = defaultdict(list)
for row in listings:
    title = row.get('item-name','')
    if not title: continue
    ls, lq = extract_from_title(title)
    models = extract_clean_model(title)
    for m in models:
        if len(m) >= 4:
            listing_by_prefix[m[:4]].append({'row': row, 'listing_screen': ls, 'listing_quality': lq, 'title': title})

# Match
def find_matches(stock_item):
    smodel = get_clean_stock_model(stock_item['original_name'])
    ss = stock_item['stock_screen']
    sq = stock_item['stock_quality']

    # Screen normalization
    def snorm(s):
        if s in ['Incell LCD', 'TFT LCD']: return 'LCD'
        return s

    matches = []
    # Exact model match (both alphanumeric)
    if smodel in listing_by_model:
        for item in listing_by_model[smodel]:
            if snorm(item['listing_screen']) == snorm(ss) and item['listing_quality'] == sq:
                matches.append(item)

    # SUBSTRING MATCH: stock model CONTAINS listing model (brand prefix on stock side)
    # e.g. stock="galaxya324g" matches listing model "a324g"
    # e.g. stock="iphone13promax" matches listing model "13promax"
    if not matches:
        for listing_model, item_list in listing_by_model.items():
            if len(listing_model) >= 4 and listing_model in smodel:
                for item in item_list:
                    if snorm(item['listing_screen']) == snorm(ss) and item['listing_quality'] == sq:
                        matches.append(item)

    # ALSO: listing model CONTAINS stock model (brand prefix on listing side)
    # e.g. listing model "galaxya32" contains stock "a32"
    if not matches:
        for listing_model, item_list in listing_by_model.items():
            if len(smodel) >= 4 and smodel in listing_model:
                for item in item_list:
                    if snorm(item['listing_screen']) == snorm(ss) and item['listing_quality'] == sq:
                        matches.append(item)

    # Deduplicate
    seen = {}
    unique = []
    for m in matches:
        sku = m['row']['seller-sku']
        if sku not in seen:
            seen[sku] = m
            unique.append(m)
    return unique

# Categorize
exact = []  # stock screen+quality matches active listing
active_mm = []  # active but screen/quality differs
inactive_only = []
not_listed = []

brand_stats = defaultdict(lambda: {'total':0,'exact':0,'active_mm':0,'inactive':0,'none':0})

for s in stock:
    matches = find_matches(s)
    active = [m for m in matches if m['row'].get('status') == 'Active']
    inactive = [m for m in matches if m['row'].get('status') != 'Active']

    def snorm(screen):
        return 'LCD' if screen in ['Incell LCD', 'TFT LCD'] else screen

    brand_stats[s['brand']]['total'] += 1

    if active:
        good = [a for a in active if snorm(a['listing_screen']) == snorm(s['stock_screen']) and a['listing_quality'] == s['stock_quality']]
        if good:
            exact.append({'stock': s, 'match': good[0]})
            brand_stats[s['brand']]['exact'] += 1
        else:
            active_mm.append({'stock': s, 'active_listings': active})
            brand_stats[s['brand']]['active_mm'] += 1
    elif inactive:
        inactive_only.append({'stock': s, 'inactive_listings': inactive})
        brand_stats[s['brand']]['inactive'] += 1
    else:
        not_listed.append({'stock': s})
        brand_stats[s['brand']]['none'] += 1

# Output
out = []
out.append('STOCK vs AMAZON LISTING - PROPER MAPPING (Clean Model)')
out.append('=' * 140)
out.append(f'Total stock: {len(stock)} variants, {sum(s["qty"] for s in stock)} units')
out.append(f'ACTIVE + EXACT (screen+quality match): {len(exact)}')
out.append(f'ACTIVE + MISMATCH: {len(active_mm)}')
out.append(f'ONLY INACTIVE: {len(inactive_only)}')
out.append(f'NOT LISTED: {len(not_listed)}')
out.append('')
out.append('-' * 140)
out.append('ACTIVE + EXACT MATCH:')
out.append('-' * 140)
for item in exact:
    st = item['stock']
    mt = item['match']
    out.append(f'[{st["brand"]}] {st["original_name"]} | qty:{st["qty"]} | STOCK:{st["stock_screen"]}/{st["stock_quality"]} -> {mt["row"]["seller-sku"]} | LIST:{mt["listing_screen"]}/{mt["listing_quality"]} | qty:{mt["row"].get("quantity","?")} | Rs.{mt["row"].get("price","?")}')
    out.append(f'  {mt["title"][:100]}')
    out.append('')
out.append('-' * 140)
out.append('ACTIVE + SCREEN/QUALITY MISMATCH:')
out.append('-' * 140)
for item in active_mm:
    st = item['stock']
    best = item['active_listings'][0]
    out.append(f'[{st["brand"]}] {st["original_name"]} | STOCK:{st["stock_screen"]}/{st["stock_quality"]} | {best["row"]["seller-sku"]} | LIST:{best["listing_screen"]}/{best["listing_quality"]} | {best["title"][:90]}')
    out.append('')
out.append('-' * 140)
out.append('ONLY INACTIVE:')
out.append('-' * 140)
for item in inactive_only:
    st = item['stock']
    best = item['inactive_listings'][0]
    out.append(f'[{st["brand"]}] {st["original_name"]} | STOCK:{st["stock_screen"]}/{st["stock_quality"]} | {best["row"]["seller-sku"]} | status:{best["row"].get("status","?")} | LIST:{best["listing_screen"]}/{best["listing_quality"]}')
    out.append('')
out.append('-' * 140)
out.append('NOT LISTED AT ALL:')
out.append('-' * 140)
for item in not_listed:
    st = item['stock']
    out.append(f'[{st["brand"]}] {st["original_name"]} | qty:{st["qty"]} | {st["stock_screen"]}/{st["stock_quality"]}')
out.append('')
out.append('=' * 140)
out.append('BRAND SUMMARY:')
for b, d in sorted(brand_stats.items(), key=lambda x: -x[1]['total']):
    out.append(f'  {b}: {d["total"]} stock | {d["exact"]} exact | {d["active_mm"]} mismatch | {d["inactive"]} inactive | {d["none"]} none')
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
        if 'super oled' in t or 'amoled' in t or ('oled' in t): lc['OLED'] += 1
        elif 'incell' in t: lc['Incell LCD'] += 1
        elif 'tft' in t: lc['TFT LCD'] += 1
        elif 'lcd' in t: lc['LCD'] += 1
        else: lc['Unknown'] += 1
for k,v in sorted(lc.items(), key=lambda x:-x[1]): out.append(f'  {k}: {v}')

with open('final_proper_mapping.txt','w',encoding='utf-8') as f:
    f.write('\n'.join(out))

print(f'EXACT: {len(exact)}, MISMATCH: {len(active_mm)}, INACTIVE: {len(inactive_only)}, NONE: {len(not_listed)}')
print()
for b, d in sorted(brand_stats.items(), key=lambda x: -x[1]['total']):
    print(f'  {b}: {d["total"]} | {d["exact"]} exact | {d["active_mm"]} mm | {d["inactive"]} inact | {d["none"]} none')
print()
print('Written to final_proper_mapping.txt')