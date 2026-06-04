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
# STEP 3: Extract COMPATIBLE MODEL NAME from listing title
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


# Build listing index: model name -> items
listing_by_model = defaultdict(list)
for row in listings:
    title = row['title']
    if not title:
        continue
    model_name, model_brand = extract_compatible_model(title)
    if model_name:
        ls, lq = extract_screen_quality(title)
        listing_by_model[model_name].append({
            'row': row,
            'model_name': model_name,
            'brand': model_brand,
            'listing_screen': ls,
            'listing_quality': lq
        })


# ============================================================
# STEP 4: Normalize stock model name — KEEP BRAND PREFIX
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
    """Extract raw model part from stock name (without removing it)."""
    n = name
    n = re.sub(r'^iPhone\s+', 'Apple iPhone ', n, flags=re.IGNORECASE)
    n = re.sub(r'^Galaxy\s+', 'Samsung Galaxy ', n, flags=re.IGNORECASE)

    prefixes = BRAND_PREFIX_MAP.get(brand, [])
    for prefix in prefixes:
        if n.startswith(prefix):
            return prefix, n[len(prefix):].strip()
    return '', n


def normalize_stock_model_full(name, brand):
    """Full model name for listing index lookup."""
    prefix, model = get_stock_model(name, brand)
    n = model
    for skip in ['Incell', 'OLED', 'AMOLED', 'Super OLED', 'LCD', 'TFT',
                 'CareOG', 'Frame', 'With Frame', 'Standard', 'White', 'Black', 'Gold']:
        n = re.sub(r'\b' + re.escape(skip) + r'\b', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\([^)]*\)', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return (prefix + n).strip()


def get_model_key(name, brand):
    """Normalized model key."""
    full = normalize_stock_model_full(name, brand)
    return re.sub(r'[^a-z0-9]', '', full.lower())


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


def find_best_match(stock_item):
    sbrand = stock_item['brand']
    sname = stock_item['original_name']
    ss = stock_item['screen']
    sq = stock_item['quality']

    # Get the normalized full model name
    norm_model = normalize_stock_model_full(sname, sbrand)
    norm_key = get_model_key(sname, sbrand)

    # Extract just the model number part (e.g. "C67" from "Realme C67")
    _, model_part = get_stock_model(sname, sbrand)
    model_num_key = re.sub(r'[^a-z0-9]', '', model_part.lower())

    candidates = []

    # Strategy 1: exact model name match in listing index
    if norm_model in listing_by_model:
        for item in listing_by_model[norm_model]:
            lb = item['brand']
            if lb and lb != sbrand and sbrand not in BRAND_ALIASES.get(lb, [lb]):
                continue
            if screen_match(ss, item['listing_screen']) and item['listing_quality'] == sq:
                candidates.append(item)

    # Strategy 2: Substring match on model number
    # Stock model number must appear WITHIN listing model name (not just share brand prefix)
    if not candidates:
        for listing_model, items in listing_by_model.items():
            listing_key = re.sub(r'[^a-z0-9]', '', listing_model.lower())
            # Does the stock model number appear in the listing model?
            if model_num_key and len(model_num_key) >= 2:
                if model_num_key in listing_key:
                    for item in items:
                        lb = item['brand']
                        if lb and lb != sbrand and sbrand not in BRAND_ALIASES.get(lb, [lb]):
                            continue
                        if screen_match(ss, item['listing_screen']) and item['listing_quality'] == sq:
                            if item not in candidates:
                                candidates.append(item)

    if not candidates:
        return None

    active = [c for c in candidates if c['row']['status'] == 'Active']
    return active[0] if active else candidates[0]


# ============================================================
# STEP 5: Build CSV
# ============================================================
import csv

matched = []
not_matched = []

for s in stock:
    match = find_best_match(s)
    if match:
        row = match['row']
        matched.append({
            'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
            'Stock Item': s['original_name'],
            'Qty': s['qty'],
            'Stock Screen': s['screen'],
            'Stock Quality': s['quality'],
            'Model Matched': match['model_name'],
            'Amazon Status': row['status'],
            'Amazon SKU': row['sku'],
            'Amazon Qty': row['quantity'],
            'Amazon Price': row['price'],
            'Listing Screen': match['listing_screen'],
            'Listing Quality': match['listing_quality'],
            'Title': match['row']['title'][:90]
        })
    else:
        not_matched.append({
            'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
            'Stock Item': s['original_name'],
            'Qty': s['qty'],
            'Stock Screen': s['screen'],
            'Stock Quality': s['quality'],
            'Issue': 'No exact match (model+screen+quality)'
        })

with open('stock_exact_match.csv', 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['Brand', 'Stock Item', 'Qty', 'Stock Screen', 'Stock Quality',
                  'Model Matched', 'Amazon Status', 'Amazon SKU', 'Amazon Qty',
                  'Amazon Price', 'Listing Screen', 'Listing Quality', 'Title']
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(matched)

with open('stock_not_matched.csv', 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['Brand', 'Stock Item', 'Qty', 'Stock Screen', 'Stock Quality', 'Issue']
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(not_matched)

from collections import Counter
brand_match = Counter()
for r in matched:
    brand_match[r['Brand']] += r['Qty']

print('=' * 70)
print('MATCHED — exact model + screen + quality')
print('=' * 70)
for b, qty in brand_match.most_common():
    items = sum(1 for r in matched if r['Brand'] == b)
    print(f'  {b:<20} {items:>3} items, {qty:>3} units')

print()
print(f'Total matched: {len(matched)} items, {sum(r["Qty"] for r in matched)} units')
print(f'Not matched: {len(not_matched)} items, {sum(r["Qty"] for r in not_matched)} units')
print()
print('CSV: stock_exact_match.csv | stock_not_matched.csv')