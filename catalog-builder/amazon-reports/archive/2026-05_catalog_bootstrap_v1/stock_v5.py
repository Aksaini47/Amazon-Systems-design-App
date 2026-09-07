import re
import pandas as pd
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
        'title': cols[0], 'sku': cols[3],
        'price': cols[4], 'quantity': cols[5], 'status': cols[29]
    })

# ============================================================
# STEP 3: Extract from Amazon listing title
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
# STEP 4: Parse SUNSKY database
# ============================================================
sunsky_df = pd.read_excel(
    r'C:\Users\DELL\Claude Repairfully.com\Sunsky Products data\AllImages_cleaned\Sunsky_MatchedProducts_R41_20260508.xlsx'
)

# Build Sunsky index: normalized model key -> list of entries
sunsky_models = defaultdict(list)
sunsky_primary = defaultdict(list)  # primary model only

for i, row in sunsky_df.iterrows():
    brand = str(row['Compatible Brand']).strip() if pd.notna(row['Compatible Brand']) else ''
    primary = str(row['Primary Model']).strip() if pd.notna(row['Primary Model']) else ''
    crossfit = str(row['Cross-fit Models']).strip() if pd.notna(row['Cross-fit Models']) else ''
    item_no = str(row['Item Number']).strip() if pd.notna(row['Item Number']) else ''
    price_inr = str(row['Price (INR)']).strip() if pd.notna(row['Price (INR)']) else ''
    product_type = str(row['Product Type']).strip() if pd.notna(row['Product Type']) else ''

    if not primary:
        continue

    pkey = re.sub(r'[^a-z0-9]', '', primary.lower())
    if len(pkey) >= 1:
        sunsky_primary[pkey].append({
            'primary': primary,
            'brand': brand,
            'crossfit': crossfit,
            'item_no': item_no,
            'price_inr': price_inr,
            'product_type': product_type
        })

    # Also index all cross-fit models
    if crossfit:
        for cf in crossfit.split('/'):
            cf = cf.strip()
            if not cf:
                continue
            cfkey = re.sub(r'[^a-z0-9]', '', cf.lower())
            if len(cfkey) >= 1 and cfkey != pkey:
                sunsky_models[cfkey].append({
                    'primary': primary,
                    'brand': brand,
                    'crossfit': crossfit,
                    'item_no': item_no,
                    'price_inr': price_inr,
                    'product_type': product_type
                })

# ============================================================
# STEP 5: Stock model normalization helpers
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
    """Model number WITHOUT brand prefix - for Sunsky matching."""
    _, model = get_stock_model(name, brand)
    # Remove screen/quality words first
    n = model
    for skip in ['Incell', 'OLED', 'AMOLED', 'Super OLED', 'LCD', 'TFT',
                 'CareOG', 'Frame', 'With Frame', 'Standard', 'White', 'Black', 'Gold']:
        n = re.sub(r'\b' + re.escape(skip) + r'\b', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\([^)]*\)', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return re.sub(r'[^a-z0-9]', '', n.lower())


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
    flags = []
    if not screen_match(stock_screen, listing_screen):
        flags.append(f'SCREEN: {stock_screen}->{listing_screen}')
    if stock_quality != listing_quality:
        flags.append(f'QUALITY: {stock_quality}->{listing_quality}')
    return ' | '.join(flags)


def find_amazon_match(stock_item):
    sbrand = stock_item['brand']
    sname = stock_item['original_name']
    ss = stock_item['screen']
    sq = stock_item['quality']

    norm_model = normalize_stock_model_full(sname, sbrand)
    model_num = get_model_num_key(sname, sbrand)

    exact = []
    loose = []
    seen = set()

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

    if model_num and len(model_num) >= 1:
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

    exact_active = [c for c in exact if c['row']['status'] == 'Active']
    loose_active = [c for c in loose if c['row']['status'] == 'Active']

    if exact_active:
        return exact_active[0], 'EXACT'
    if exact:
        return exact[0], 'EXACT'
    if loose_active:
        return loose_active[0], 'LOOSE'
    if loose:
        return loose[0], 'LOOSE'
    return None, 'NOT LISTED'


def find_sunsky_match(stock_name, stock_brand):
    """
    Match stock model to Sunsky. Try primary model match first,
    then cross-fit model match. Return best match.
    """
    norm_model = normalize_stock_model_full(stock_name, stock_brand)
    model_num = get_model_num_key(stock_name, stock_brand)

    # Strategy 1: exact normalized model match
    if norm_model in sunsky_primary:
        return sunsky_primary[norm_model][0], 'primary_exact'

    # Strategy 2: model number in primary model index OR cross-fit index
    if model_num and len(model_num) >= 1:
        # Check primary model index first (most reliable)
        if model_num in sunsky_primary:
            return sunsky_primary[model_num][0], 'primary_fuzzy'
        # Then check cross-fit index
        if model_num in sunsky_models:
            return sunsky_models[model_num][0], 'crossfit_match'

    # Strategy 3: partial match (model_num is substring of key or vice versa)
    if model_num and len(model_num) >= 2:
        for key in sunsky_primary:
            if len(key) >= 3:
                if model_num in key or key in model_num:
                    return sunsky_primary[key][0], 'partial_match'
        for key in sunsky_models:
            if len(key) >= 3:
                if model_num in key or key in model_num:
                    return sunsky_models[key][0], 'partial_match'

    return None, None


# ============================================================
# STEP 6: Build all 3 sheets with cross-fit data
# ============================================================
import csv

exact_rows = []
loose_rows = []
not_listed_rows = []

for s in stock:
    amazon_match, match_type = find_amazon_match(s)
    sunsky_match, sunsky_type = find_sunsky_match(s['original_name'], s['brand'])

    # Sunsky data
    if sunsky_match:
        sunsky_primary_model = sunsky_match['primary']
        sunsky_crossfit = sunsky_match['crossfit']
        sunsky_item_no = sunsky_match['item_no']
        sunsky_price_inr = sunsky_match['price_inr']
        sunsky_product_type = sunsky_match['product_type']
    else:
        sunsky_primary_model = ''
        sunsky_crossfit = ''
        sunsky_item_no = ''
        sunsky_price_inr = ''
        sunsky_product_type = ''

    base = {
        'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
        'Stock Item': s['original_name'],
        'Qty': s['qty'],
        'Stock Screen': s['screen'],
        'Stock Quality': s['quality'],
        'Sunsky Primary Model': sunsky_primary_model,
        'Sunsky Cross-fit Models': sunsky_crossfit,
        'Sunsky Item No': sunsky_item_no,
        'Sunsky Price (INR)': sunsky_price_inr,
        'Sunsky Product Type': sunsky_product_type,
    }

    if amazon_match:
        row_data = dict(base)
        row_data.update({
            'Amazon Model Matched': amazon_match['model_name'],
            'Amazon Status': amazon_match['row']['status'],
            'Amazon SKU': amazon_match['row']['sku'],
            'Amazon Qty': amazon_match['row']['quantity'],
            'Amazon Price': amazon_match['row']['price'],
            'Listing Screen': amazon_match['listing_screen'],
            'Listing Quality': amazon_match['listing_quality'],
            'Amazon Title': amazon_match['row']['title'][:90]
        })

        if match_type == 'EXACT':
            exact_rows.append(row_data)
        else:
            row_data['Flag'] = get_flags(
                s['screen'], s['quality'],
                amazon_match['listing_screen'], amazon_match['listing_quality']
            )
            loose_rows.append(row_data)
    else:
        row_data = dict(base)
        row_data.update({
            'Amazon Model Matched': '',
            'Amazon Status': '',
            'Amazon SKU': '',
            'Amazon Qty': '',
            'Amazon Price': '',
            'Listing Screen': '',
            'Listing Quality': '',
            'Amazon Title': '',
            'Flag': ''
        })
        not_listed_rows.append(row_data)

# Write 3 separate files
# Exact match
exact_fields = ['Brand', 'Stock Item', 'Qty', 'Stock Screen', 'Stock Quality',
                'Sunsky Primary Model', 'Sunsky Cross-fit Models', 'Sunsky Item No',
                'Sunsky Price (INR)', 'Sunsky Product Type',
                'Amazon Model Matched', 'Amazon Status', 'Amazon SKU', 'Amazon Qty',
                'Amazon Price', 'Listing Screen', 'Listing Quality', 'Amazon Title']

with open('stock_1_exact_match.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=exact_fields, extrasaction='ignore')
    w.writeheader()
    w.writerows(exact_rows)

# Loose match
loose_fields = exact_fields + ['Flag']
with open('stock_2_loose_match.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=loose_fields, extrasaction='ignore')
    w.writeheader()
    w.writerows(loose_rows)

# Not listed
not_listed_fields = ['Brand', 'Stock Item', 'Qty', 'Stock Screen', 'Stock Quality',
                     'Sunsky Primary Model', 'Sunsky Cross-fit Models', 'Sunsky Item No',
                     'Sunsky Price (INR)', 'Sunsky Product Type',
                     'Amazon Model Matched', 'Amazon Status', 'Amazon SKU', 'Amazon Qty',
                     'Amazon Price', 'Listing Screen', 'Listing Quality', 'Amazon Title', 'Flag']

with open('stock_3_not_listed.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=not_listed_fields, extrasaction='ignore')
    w.writeheader()
    w.writerows(not_listed_rows)

# Combined
all_rows = []
for r in exact_rows:
    r2 = dict(r)
    r2['Match Type'] = 'EXACT MATCH'
    all_rows.append(r2)
for r in loose_rows:
    r2 = dict(r)
    r2['Match Type'] = 'LOOSE MATCH'
    all_rows.append(r2)
for r in not_listed_rows:
    r2 = dict(r)
    r2['Match Type'] = 'NOT LISTED'
    r2['Flag'] = r2.get('Flag', '')
    all_rows.append(r2)

combined_fields = ['Match Type'] + not_listed_fields
with open('stock_A_combined.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=combined_fields, extrasaction='ignore')
    w.writeheader()
    w.writerows(all_rows)

# Summary
exact_units = sum(r['Qty'] for r in exact_rows)
loose_units = sum(r['Qty'] for r in loose_rows)
not_listed_units = sum(r['Qty'] for r in not_listed_rows)

sunsky_found = sum(1 for s in stock if find_sunsky_match(s['original_name'], s['brand'])[0] is not None)
sunsky_not_found = len(stock) - sunsky_found

print('=' * 70)
print('STOCK ANALYSIS WITH SUNSKY CROSS-FIT')
print('=' * 70)
print()
print(f'1. EXACT MATCH  : {len(exact_rows):>3} items, {exact_units:>3} units')
print(f'2. LOOSE MATCH  : {len(loose_rows):>3} items, {loose_units:>3} units')
print(f'3. NOT LISTED   : {len(not_listed_rows):>3} items, {not_listed_units:>3} units')
print(f'TOTAL           : {len(stock):>3} items, {sum(s["qty"] for s in stock):>3} units')
print()
print(f'Sunsky Match    : {sunsky_found} items found in Sunsky database')
print(f'Sunsky No Match : {sunsky_not_found} items not in Sunsky database')
print()
print('Files:')
print('  stock_A_combined.csv  - All 3 sheets combined (Match Type column)')
print('  stock_1_exact_match.csv')
print('  stock_2_loose_match.csv')
print('  stock_3_not_listed.csv')
print()
print('Sunsky columns added: Sunsky Primary Model | Sunsky Cross-fit Models | Sunsky Item No | Sunsky Price (INR) | Sunsky Product Type')