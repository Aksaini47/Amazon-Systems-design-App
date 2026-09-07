import re
from collections import defaultdict

# ============================================================
# STEP 1: Parse ACTUAL STOCK
# ============================================================
with open('actual stock.txt', 'r', encoding='utf-8') as f:
    slines = f.readlines()

BRAND_KEYWORDS = ['REALME', 'VIVO', 'OPPO', 'ONEPLUS', 'APPLE', 'SAMSUNG',
                  'XIAOMI', 'REDMI', 'POCO', 'MIX', 'MOTO', 'HONOR',
                  'NOKIA', 'ASUS', 'NOTHING', 'INFINIX']

stock = []
current_brand = ''
for line in slines:
    stripped = line.rstrip().strip()
    if not stripped or stripped.lower() == 'actual stock':
        continue
    is_brand = stripped.isupper() and any(b in stripped for b in BRAND_KEYWORDS)
    if is_brand:
        current_brand = stripped
    else:
        name = stripped
        if name and current_brand:
            qty_match = re.search(r' - (\d+)$', name)
            qty = int(qty_match.group(1)) if qty_match else 1
            clean_name = re.sub(r' - \d+$', '', name).strip()
            nl = clean_name.lower()

            if 'oled' in nl or 'amoled' in nl:
                ss = 'OLED'
            elif 'incell' in nl:
                ss = 'Incell LCD'
            elif 'tft' in nl:
                ss = 'TFT LCD'
            elif 'lcd' in nl:
                ss = 'LCD'
            else:
                ss = 'Not Specified'

            if 'careog' in nl:
                sq = 'CareOG'
            elif 'frame' in nl or 'with frame' in nl or ' wf ' in nl:
                sq = 'With Frame'
            else:
                sq = 'Standard'

            stock.append({
                'brand': current_brand,
                'original_name': clean_name,
                'qty': qty,
                'screen': ss,
                'quality': sq
            })

# ============================================================
# STEP 2: Parse AMAZON LISTINGS
# ============================================================
with open('All+Listings+Report_05-12-2026.txt', 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

listings = []
for l in lines[1:]:
    if not l.strip():
        continue
    cols = [c.strip() for c in l.split('\t')]
    if len(cols) < 30:
        cols += [''] * (30 - len(cols))
    listings.append({
        'title': cols[0],
        'sku': cols[3],
        'price': cols[4],
        'quantity': cols[5],
        'status': cols[29]
    })

# ============================================================
# STEP 3: Extract from listing title
# ============================================================
def extract_compatible_model(title):
    if not title or 'Compatible for' not in title:
        return None, None
    after = title.split('Compatible for', 1)[1].strip()
    segment = after.split('/')[0].strip()
    segment = re.sub(r'\([^)]*\)', '', segment)
    for skip in ['CareOG', 'OLED', 'LCD', 'Incell', 'TFT', 'Amoled', 'AMOLED',
                 'Super OLED', 'Fingerprint Support', 'No Fingerprint Support',
                 'Display+Touch Screen Combo', 'Display Screen Replacement Combo',
                 'Display Screen Combo', 'Screen Combo', 'Display Touch Digitizer',
                 'Assembly', 'Replacement', 'with frame', 'Standard', 'White',
                 'Black', 'Gold', 'Folder']:
        segment = re.sub(re.escape(skip), ' ', segment, flags=re.IGNORECASE)
    segment = re.sub(r'\s+', ' ', segment).strip()

    brand = None
    checks = [
        ('Apple iPhone', 'APPLE'), ('Samsung Galaxy', 'SAMSUNG'),
        ('Samsung ', 'SAMSUNG'), ('Xiaomi ', 'XIAOMI'), ('Redmi ', 'REDMI'),
        ('POCO ', 'POCO'), ('Realme ', 'REALME'), ('Vivo ', 'VIVO'),
        ('Oppo ', 'OPPO'), ('OnePlus ', 'ONEPLUS'), ('Motorola Moto', 'MOTO'),
        ('Moto ', 'MOTO'), ('Honor ', 'HONOR'), ('Nokia ', 'NOKIA'),
        ('Asus ', 'ASUS'), ('Nothing Phone', 'NOTHING'), ('Nothing ', 'NOTHING'),
        ('Infinix ', 'INFINIX'),
    ]
    for kw, br in checks:
        if kw.lower() in after.lower():
            brand = br
            break
    return segment, brand


def extract_screen_quality(title):
    t = title.lower()
    if 'super oled' in t or 'amoled' in t or ('oled' in t and 'lcd' not in t and 'incell' not in t):
        ls = 'OLED'
    elif 'incell' in t:
        ls = 'Incell LCD'
    elif 'tft' in t:
        ls = 'TFT LCD'
    elif 'lcd' in t:
        ls = 'LCD'
    else:
        ls = 'Not Specified'

    if 'careog' in t:
        lq = 'CareOG'
    elif 'with frame' in t or '(with frame)' in t or ' wf ' in t:
        lq = 'With Frame'
    else:
        lq = 'Standard'
    return ls, lq


listing_by_model = defaultdict(list)
for row in listings:
    title = row['title']
    if not title:
        continue
    model_name, model_brand = extract_compatible_model(title)
    if model_name:
        ls, lq = extract_screen_quality(title)
        listing_by_model[model_name].append({
            'row': row, 'model_name': model_name, 'brand': model_brand,
            'listing_screen': ls, 'listing_quality': lq
        })

# ============================================================
# STEP 4: Normalize stock model
# ============================================================
BRAND_PREFIX_MAP = {
    'APPLE': ['Apple iPhone '],
    'SAMSUNG': ['Samsung Galaxy '],
    'ONEPLUS': ['OnePlus '],
    'OPPO': ['Oppo '],
    'VIVO': ['Vivo '],
    'REALME': ['Realme '],
    'XIAOMI': ['Xiaomi ', 'Redmi ', 'POCO '],
    'REDMI': ['Xiaomi ', 'Redmi ', 'POCO '],
    'POCO': ['Xiaomi ', 'Redmi ', 'POCO '],
    'MOTO': ['Moto '],
    'HONOR': ['Honor '],
    'NOKIA': ['Nokia '],
    'ASUS': ['Asus '],
    'NOTHING': ['Nothing Phone ', 'Nothing '],
    'INFINIX': ['Infinix '],
    'MIX': ['Infinix ', 'Honor ', 'Nokia ', 'Moto ', 'Asus ', 'Nothing Phone ', 'Nothing '],
}

def get_stock_model(name, brand):
    n = name
    n = re.sub(r'^iPhone\s+', 'Apple iPhone ', n, flags=re.IGNORECASE)
    n = re.sub(r'^Galaxy\s+', 'Samsung Galaxy ', n, flags=re.IGNORECASE)
    prefixes = BRAND_PREFIX_MAP.get(brand, [])
    for prefix in prefixes:
        if n.startswith(prefix):
            return prefix, n[len(prefix):].strip()
    return '', n


def normalize_stock_model_full(name, brand):
    prefix, model = get_stock_model(name, brand)
    n = model
    for skip in ['Incell', 'OLED', 'AMOLED', 'Super OLED', 'LCD', 'TFT',
                 'CareOG', 'Frame', 'With Frame', 'Standard', 'White', 'Black', 'Gold']:
        n = re.sub(r'\b' + re.escape(skip) + r'\b', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\([^)]*\)', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return (prefix + n).strip()


def get_model_num_key(name, brand):
    _, model = get_stock_model(name, brand)
    return re.sub(r'[^a-z0-9]', '', model.lower())


BRAND_DISPLAY = {
    'APPLE': 'Apple', 'SAMSUNG': 'Samsung', 'ONEPLUS': 'OnePlus',
    'OPPO': 'Oppo', 'VIVO': 'Vivo', 'REALME': 'Realme',
    'XIAOMI': 'Xiaomi/Redmi/Poco', 'MOTO': 'Motorola',
    'HONOR': 'Honor', 'NOKIA': 'Nokia', 'ASUS': 'Asus',
    'INFINIX': 'Infinix', 'MIX': 'Mixed', 'NOTHING': 'Nothing',
    'REDMI': 'Redmi', 'POCO': 'Poco'
}

BRAND_ALIASES = {
    'XIAOMI': ['XIAOMI', 'REDMI', 'POCO'],
    'REDMI': ['XIAOMI', 'REDMI', 'POCO'],
    'POCO': ['XIAOMI', 'REDMI', 'POCO'],
    'MIX': ['INFINIX', 'HONOR', 'NOKIA', 'MOTO', 'ASUS', 'NOTHING'],
}


def screen_match(stock_screen, listing_screen):
    s = stock_screen
    l = listing_screen
    if s == l:
        return True
    if s in ['Incell LCD', 'LCD'] and l in ['Incell LCD', 'LCD']:
        return True
    return False


def get_flags(stock_screen, stock_quality, listing_screen, listing_quality):
    """Return list of flag strings."""
    flags = []
    if not screen_match(stock_screen, listing_screen):
        flags.append(f'SCREEN: {stock_screen} -> {listing_screen}')
    if stock_quality != listing_quality:
        flags.append(f'QUALITY: {stock_quality} -> {listing_quality}')
    return ' | '.join(flags)


def find_matches(stock_item):
    """
    Return (exact_matches, loose_matches) where:
    - exact: model + screen + quality all match
    - loose: model matches but screen or quality differs
    """
    sbrand = stock_item['brand']
    sname = stock_item['original_name']
    ss = stock_item['screen']
    sq = stock_item['quality']

    norm_model = normalize_stock_model_full(sname, sbrand)
    model_num = get_model_num_key(sname, sbrand)

    exact = []
    loose = []
    seen = set()

    # Strategy 1: exact model name match
    if norm_model in listing_by_model:
        for item in listing_by_model[norm_model]:
            sku = item['row']['sku']
            if sku in seen:
                continue
            seen.add(sku)
            lb = item['brand']
            if lb and lb != sbrand and sbrand not in BRAND_ALIASES.get(lb, [lb]):
                continue
            if screen_match(ss, item['listing_screen']) and item['listing_quality'] == sq:
                exact.append(item)
            else:
                loose.append(item)

    # Strategy 2: model number substring match
    if model_num and len(model_num) >= 2:
        for listing_model, items in listing_by_model.items():
            listing_key = re.sub(r'[^a-z0-9]', '', listing_model.lower())
            if model_num in listing_key:
                for item in items:
                    sku = item['row']['sku']
                    if sku in seen:
                        continue
                    seen.add(sku)
                    lb = item['brand']
                    if lb and lb != sbrand and sbrand not in BRAND_ALIASES.get(lb, [lb]):
                        continue
                    if screen_match(ss, item['listing_screen']) and item['listing_quality'] == sq:
                        exact.append(item)
                    else:
                        loose.append(item)

    return exact, loose


# ============================================================
# STEP 5: Build three-sheet CSV
# ============================================================
import csv

exact_rows = []
loose_rows = []
not_listed_rows = []

for s in stock:
    exact, loose = find_matches(s)

    # Prefer active
    exact_active = [c for c in exact if c['row']['status'] == 'Active']
    loose_active = [c for c in loose if c['row']['status'] == 'Active']

    if exact_active:
        best = exact_active[0]
        row = best['row']
        exact_rows.append({
            'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
            'Stock Item': s['original_name'],
            'Qty': s['qty'],
            'Stock Screen': s['screen'],
            'Stock Quality': s['quality'],
            'Model Matched': best['model_name'],
            'Amazon Status': row['status'],
            'Amazon SKU': row['sku'],
            'Amazon Qty': row['quantity'],
            'Amazon Price': row['price'],
            'Listing Screen': best['listing_screen'],
            'Listing Quality': best['listing_quality'],
            'Title': best['row']['title'][:90]
        })
    elif exact:
        best = exact[0]
        row = best['row']
        exact_rows.append({
            'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
            'Stock Item': s['original_name'],
            'Qty': s['qty'],
            'Stock Screen': s['screen'],
            'Stock Quality': s['quality'],
            'Model Matched': best['model_name'],
            'Amazon Status': row['status'],
            'Amazon SKU': row['sku'],
            'Amazon Qty': row['quantity'],
            'Amazon Price': row['price'],
            'Listing Screen': best['listing_screen'],
            'Listing Quality': best['listing_quality'],
            'Title': best['row']['title'][:90]
        })
    elif loose_active:
        best = loose_active[0]
        row = best['row']
        loose_rows.append({
            'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
            'Stock Item': s['original_name'],
            'Qty': s['qty'],
            'Stock Screen': s['screen'],
            'Stock Quality': s['quality'],
            'Model Matched': best['model_name'],
            'Flag': get_flags(s['screen'], s['quality'], best['listing_screen'], best['listing_quality']),
            'Amazon Status': row['status'],
            'Amazon SKU': row['sku'],
            'Amazon Qty': row['quantity'],
            'Amazon Price': row['price'],
            'Listing Screen': best['listing_screen'],
            'Listing Quality': best['listing_quality'],
            'Title': best['row']['title'][:90]
        })
    elif loose:
        best = loose[0]
        row = best['row']
        loose_rows.append({
            'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
            'Stock Item': s['original_name'],
            'Qty': s['qty'],
            'Stock Screen': s['screen'],
            'Stock Quality': s['quality'],
            'Model Matched': best['model_name'],
            'Flag': get_flags(s['screen'], s['quality'], best['listing_screen'], best['listing_quality']),
            'Amazon Status': row['status'],
            'Amazon SKU': row['sku'],
            'Amazon Qty': row['quantity'],
            'Amazon Price': row['price'],
            'Listing Screen': best['listing_screen'],
            'Listing Quality': best['listing_quality'],
            'Title': best['row']['title'][:90]
        })
    else:
        not_listed_rows.append({
            'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
            'Stock Item': s['original_name'],
            'Qty': s['qty'],
            'Stock Screen': s['screen'],
            'Stock Quality': s['quality'],
            'Issue': 'Model not listed on Amazon'
        })

# Write all three into one CSV file with sheet indicator
# We'll use a single CSV with an extra column "Sheet"
all_rows = []
for r in exact_rows:
    r2 = dict(r)
    r2['Sheet'] = 'EXACT MATCH'
    all_rows.append(r2)
for r in loose_rows:
    r2 = dict(r)
    r2['Sheet'] = 'LOOSE MATCH'
    all_rows.append(r2)
for r in not_listed_rows:
    r2 = dict(r)
    r2['Sheet'] = 'NOT LISTED'
    r2['Model Matched'] = ''
    r2['Flag'] = ''
    r2['Amazon Status'] = ''
    r2['Amazon SKU'] = ''
    r2['Amazon Qty'] = ''
    r2['Amazon Price'] = ''
    r2['Listing Screen'] = ''
    r2['Listing Quality'] = ''
    r2['Title'] = ''
    all_rows.append(r2)

# Since standard csv doesn't support sheets, write as separate files + summary
# File 1: EXACT MATCH
with open('stock_1_exact_match.csv', 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['Brand', 'Stock Item', 'Qty', 'Stock Screen', 'Stock Quality',
                  'Model Matched', 'Amazon Status', 'Amazon SKU', 'Amazon Qty',
                  'Amazon Price', 'Listing Screen', 'Listing Quality', 'Title']
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(exact_rows)

# File 2: LOOSE MATCH
with open('stock_2_loose_match.csv', 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['Brand', 'Stock Item', 'Qty', 'Stock Screen', 'Stock Quality',
                  'Model Matched', 'Flag', 'Amazon Status', 'Amazon SKU', 'Amazon Qty',
                  'Amazon Price', 'Listing Screen', 'Listing Quality', 'Title']
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(loose_rows)

# File 3: NOT LISTED
with open('stock_3_not_listed.csv', 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['Brand', 'Stock Item', 'Qty', 'Stock Screen', 'Stock Quality', 'Issue']
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(not_listed_rows)

# Also write a combined file
with open('stock_0_combined.csv', 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['Sheet', 'Brand', 'Stock Item', 'Qty', 'Stock Screen', 'Stock Quality',
                  'Model Matched', 'Flag', 'Amazon Status', 'Amazon SKU', 'Amazon Qty',
                  'Amazon Price', 'Listing Screen', 'Listing Quality', 'Title']
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(all_rows)

# Summary
from collections import Counter
exact_units = sum(r['Qty'] for r in exact_rows)
loose_units = sum(r['Qty'] for r in loose_rows)
not_listed_units = sum(r['Qty'] for r in not_listed_rows)

print('=' * 70)
print('STOCK ANALYSIS - 3-WAY BREAKDOWN')
print('=' * 70)
print()
print(f'1. EXACT MATCH  : {len(exact_rows):>3} items, {exact_units:>3} units')
print(f'2. LOOSE MATCH  : {len(loose_rows):>3} items, {loose_units:>3} units')
print(f'3. NOT LISTED   : {len(not_listed_rows):>3} items, {not_listed_units:>3} units')
print(f'TOTAL           : {len(stock):>3} items, {sum(s["qty"] for s in stock):>3} units')
print()
print('Files:')
print('  stock_exact_match.csv  - Model + Screen + Quality match')
print('  stock_loose_match.csv  - Model matches, screen/quality differ')
print('  stock_not_listed.csv   - No matching listing on Amazon')
print('  stock_analysis_combined.csv - All 3 in one file (Sheet column identifies type)')