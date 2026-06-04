import re
from collections import defaultdict

# ============================================================
# STEP 1: Parse ACTUAL STOCK with quantities
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

hdr_idx = next(i for i, l in enumerate(lines) if 'seller-sku' in l)
hdrs = [c.strip() for c in lines[hdr_idx].split('\t')]
listings = []
for l in lines[hdr_idx + 1:]:
    if not l.strip():
        continue
    cols = [c.strip() for c in l.split('\t')]
    if len(cols) < len(hdrs):
        cols += [''] * (len(hdrs) - len(cols))
    listings.append(dict(zip(hdrs, cols)))


# ============================================================
# STEP 3: Extract model identifiers
# ============================================================
def extract_stock_model(name):
    n = name.lower()
    for prefix in ['realme ', 'vivo ', 'oppo ', 'oneplus ', 'apple iphone ',
                   'samsung galaxy ', 'xiaomi ', 'redmi ', 'poco ', 'moto ',
                   'honor ', 'nokia ', 'asus ', 'nothing phone ', 'infinix ']:
        n = n.replace(prefix, '').replace(prefix.upper(), '')
    n = re.sub(r'^iphone\s+', '', n)
    n = re.sub(r'^galaxy\s+', '', n)
    for skip in ['incell', 'oled', 'amoled', 'super oled', 'lcd', 'tft',
                 'careog', 'frame', 'with frame', 'standard', 'white',
                 'black', 'gold', 'wf ']:
        n = re.sub(r'\b' + skip + r'\b', '', n, flags=re.IGNORECASE)
    n = re.sub(r'[^a-z0-9]', '', n)
    return n


def extract_models_from_title(title):
    if not title or 'Compatible for' not in title:
        return []

    after = title.split('Compatible for', 1)[1].strip()
    for kw in ['CareOG', 'OLED', 'LCD', 'Incell', 'TFT', 'Amoled', 'AMOLED',
               'Super OLED', 'Fingerprint Support', 'No Fingerprint Support',
               'Display+Touch Screen Combo', 'Display Screen Replacement Combo',
               'Display Screen Combo', 'Screen Combo', 'Display Touch Digitizer',
               'Assembly', 'Replacement', 'with frame', 'Standard', 'White',
               'Black', 'Gold']:
        after = re.sub(re.escape(kw), ' ', after, flags=re.IGNORECASE)

    parts = after.split('/')
    models = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        part = re.sub(r'\([^)]*\)', '', part)
        for brand in ['Samsung Galaxy', 'Samsung', 'Vivo', 'Oppo', 'OnePlus',
                      'Apple iPhone', 'Apple', 'Redmi', 'Xiaomi', 'POCO',
                      'Motorola Moto', 'Moto', 'Realme', 'Infinix', 'Honor',
                      'Nokia', 'Asus', 'Nothing Phone', 'Nothing', 'Tecno']:
            part = re.sub(brand, ' ', part, flags=re.IGNORECASE)
        part = re.sub(r'[^a-z0-9]', '', part.lower())
        if len(part) >= 2:
            models.append(part)
    return models


def extract_listing_brand(title):
    if not title or 'Compatible for' not in title:
        return None
    after = title.split('Compatible for', 1)[1].strip()
    checks = [
        ('Apple iPhone', 'APPLE'), ('Samsung Galaxy', 'SAMSUNG'),
        ('Samsung ', 'SAMSUNG'), ('Xiaomi ', 'XIAOMI'), ('Redmi ', 'REDMI'),
        ('POCO ', 'POCO'), ('Realme ', 'REALME'), ('Vivo ', 'VIVO'),
        ('Oppo ', 'OPPO'), ('OnePlus ', 'ONEPLUS'), ('Motorola Moto', 'MOTO'),
        ('Moto ', 'MOTO'), ('Honor ', 'HONOR'), ('Nokia ', 'NOKIA'),
        ('Asus ', 'ASUS'), ('Nothing Phone', 'NOTHING'), ('Nothing ', 'NOTHING'),
        ('Infinix ', 'INFINIX'),
    ]
    for kw, brand in checks:
        if kw.lower() in after.lower():
            return brand
    return None


def extract_from_title(title):
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


def snorm(screen):
    return 'LCD' if screen in ['Incell LCD', 'TFT LCD', 'LCD'] else screen


# Build listing index by brand
listings_by_brand = defaultdict(list)
for row in listings:
    title = row.get('item-name', '')
    if not title:
        continue
    brand = extract_listing_brand(title)
    ls, lq = extract_from_title(title)
    models = extract_models_from_title(title)
    listings_by_brand[brand].append({
        'row': row, 'title': title,
        'listing_screen': ls, 'listing_quality': lq,
        'models': models
    })


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
}


def find_exact_match(stock_item):
    """
    ONLY return a match if:
      1. Same model number (substring match)
      2. SAME screen type (not normalized - exact match)
      3. SAME quality grade (exact match)
    Otherwise return None.
    """
    sbrand = stock_item['brand']
    smodel = extract_stock_model(stock_item['original_name'])
    ss = stock_item['screen']
    sq = stock_item['quality']

    search_brands = BRAND_ALIASES.get(sbrand, [sbrand])

    candidates = []
    for brand_key in search_brands:
        for item in listings_by_brand.get(brand_key, []):
            listing_models = item['models']
            ls = item['listing_screen']
            lq = item['listing_quality']

            # Model matching
            model_match = False
            for lm in listing_models:
                if smodel == lm:
                    model_match = True
                    break
                if len(lm) >= len(smodel) and lm.startswith(smodel) and len(smodel) >= 3:
                    model_match = True
                    break
                if len(smodel) >= len(lm) and smodel.startswith(lm) and len(lm) >= 3:
                    model_match = True
                    break
                if len(smodel) >= 4 and len(lm) >= 4 and smodel[:4] == lm[:4]:
                    model_match = True
                    break

            if not model_match:
                continue

            # STRICT check: screen AND quality must EXACTLY match
            if ls == ss and lq == sq:
                candidates.append(item)

    if not candidates:
        return None

    # Return best by status (Active > Inactive)
    active = [c for c in candidates if c['row'].get('status') == 'Active']
    if active:
        return active[0]
    return candidates[0]


# ============================================================
# STEP 4: Generate EXACT MATCHES ONLY CSV
# ============================================================
import csv

matched_rows = []
unmatched = []

for s in stock:
    match = find_exact_match(s)
    if match:
        row = match['row']
        matched_rows.append({
            'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
            'Stock Item': s['original_name'],
            'Qty': s['qty'],
            'Stock Screen': s['screen'],
            'Stock Quality': s['quality'],
            'Amazon Status': row.get('status', '?'),
            'Amazon SKU': row['seller-sku'],
            'Amazon Qty': row.get('quantity', ''),
            'Amazon Price': row.get('price', ''),
            'Listing Screen': match['listing_screen'],
            'Listing Quality': match['listing_quality'],
            'Title': match['title'][:80]
        })
    else:
        unmatched.append({
            'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
            'Stock Item': s['original_name'],
            'Qty': s['qty'],
            'Stock Screen': s['screen'],
            'Stock Quality': s['quality'],
            'Issue': 'No exact match on Amazon'
        })

# Write matched CSV
with open('stock_exact_matches.csv', 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['Brand', 'Stock Item', 'Qty', 'Stock Screen', 'Stock Quality',
                  'Amazon Status', 'Amazon SKU', 'Amazon Qty', 'Amazon Price',
                  'Listing Screen', 'Listing Quality', 'Title']
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(matched_rows)

# Write unmatched CSV
with open('stock_not_matched.csv', 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['Brand', 'Stock Item', 'Qty', 'Stock Screen', 'Stock Quality', 'Issue']
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(unmatched)

# Print summary
print('=' * 60)
print('EXACT MATCHES — Screen + Quality both match')
print('=' * 60)
print(f'Total matched: {len(matched_rows)} items, {sum(r["Qty"] for r in matched_rows)} units')
print()

# By brand
from collections import Counter
brand_match = Counter()
for r in matched_rows:
    brand_match[r['Brand']] += r['Qty']

for b, qty in brand_match.most_common():
    items = sum(1 for r in matched_rows if r['Brand'] == b)
    print(f'  {b:<20} {items:>3} items, {qty:>3} units')

print()
print(f'NOT matched: {len(unmatched)} items, {sum(r["Qty"] for r in unmatched)} units')

print()
print('CSV files:')
print('  - amazon-reports/stock_exact_matches.csv  (matched items)')
print('  - amazon-reports/stock_not_matched.csv    (not matched items)')