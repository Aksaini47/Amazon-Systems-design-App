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
def extract_clean_model(title):
    if not title or 'Compatible for' not in title: return []
    after = title.split('Compatible for', 1)[1].strip()
    for kw in ['CareOG', 'Careog', 'OLED', 'LCD', 'Incell', 'TFT', 'Amoled', 'AMOLED', 'Super OLED',
               'Fingerprint Support', 'No Fingerprint Support', 'Display+Touch Screen Combo',
               'Display Screen Replacement Combo', 'Display Screen Combo', 'Screen Combo']:
        after = re.sub(re.escape(kw), ' ', after, flags=re.IGNORECASE)
    after = re.sub(r'with\s+frame', ' ', after, flags=re.IGNORECASE)
    for kw in ['Black', 'White', 'Gold']:
        after = after.replace(kw, ' ')
    parts = after.split('/')
    models = []
    for part in parts:
        part = part.strip()
        if not part: continue
        part = re.sub(r'\([^)]*\)', '', part)
        for brand in ['Samsung Galaxy', 'Samsung', 'Vivo', 'Oppo', 'OnePlus', 'Apple iPhone', 'Apple',
                      'Redmi', 'Xiaomi', 'POCO', 'Motorola Moto', 'Moto', 'Realme', 'Infinix',
                      'Honor', 'Nokia', 'Asus', 'Nothing Phone', 'Nothing', 'Tecno', 'itel', 'iTel']:
            part = re.sub(brand, ' ', part, flags=re.IGNORECASE)
        part = re.sub(r'[^a-z0-9]', '', part.lower())
        if len(part) >= 2:
            models.append(part)
    return models

# FIXED: also strip "iphone" and "galaxy" prefixes from stock model
# because stock names like "iPhone 13 Pro Max OLED" start with "iPhone" not "Apple iPhone "
# and listing extraction strips "Apple iPhone " leaving "13promax"
def get_clean_stock_model(original):
    model = original
    # Strip brand prefixes at start
    for skip in ['Realme ', 'Vivo ', 'Oppo ', 'OnePlus ', 'Apple iPhone ', 'Apple ',
                 'Samsung Galaxy ', 'Xiaomi ', 'Redmi ', 'Poco ', 'Moto ', 'Honor ', 'Nokia ',
                 'Asus ', 'Nothing Phone ', 'Infinix ']:
        model = model.replace(skip, '').replace(skip.lower(), '')
    # ALSO strip "iPhone " and "Galaxy " at start (stock may say "iPhone 13 Pro Max" not "Apple iPhone 13 Pro Max")
    # And strip "iPhone" from anywhere for Apple, "Galaxy" from anywhere for Samsung
    model = re.sub(r'^iPhone\s+', '', model, flags=re.IGNORECASE)
    model = re.sub(r'^Galaxy\s+', '', model, flags=re.IGNORECASE)
    model = model.replace('iPhone', '').replace('Galaxy', '')
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

# Build listing index
listing_by_model = defaultdict(list)
for row in listings:
    title = row.get('item-name','')
    if not title: continue
    ls, lq = extract_from_title(title)
    models = extract_clean_model(title)
    for m in models:
        listing_by_model[m].append({'row': row, 'listing_screen': ls, 'listing_quality': lq, 'title': title})

# Verify Apple/Samsung models after fix
print('=== AFTER FIX ===')
print()
print('Apple stock models after get_clean_stock_model:')
for s in stock:
    if s['brand'] == 'APPLE':
        m = get_clean_stock_model(s['original_name'])
        print(f'  "{s["original_name"]}" -> "{m}"')

print()
print('Samsung stock models after get_clean_stock_model:')
for s in stock:
    if s['brand'] == 'SAMSUNG':
        m = get_clean_stock_model(s['original_name'])
        print(f'  "{s["original_name"]}" -> "{m}"')

print()
print('Listing keys for Apple (13/11/14/8/XS):')
all_keys = sorted(listing_by_model.keys())
apple_list_keys = [k for k in all_keys if any(x in k for x in ['13','11','14','8','xs','7','6','se','x'])]
print('  ', apple_list_keys[:30])

print()
print('Listing keys for Samsung A-series:')
sam_a_keys = [k for k in all_keys if k.startswith('a') and len(k) <= 6]
print('  ', sam_a_keys)

print()
print('Listing keys for Samsung J-series:')
sam_j_keys = [k for k in all_keys if k.startswith('j') and len(k) <= 6]
print('  ', sam_j_keys)

print()
print('Listing keys with "galaxy":')
galaxy_keys = [k for k in all_keys if 'galaxy' in k]
print('  ', galaxy_keys[:20])

# Now test actual matching
print()
print('=== MATCHING TEST ===')
for s in stock:
    smodel = get_clean_stock_model(s['original_name'])
    if s['brand'] in ['APPLE', 'SAMSUNG']:
        # Check if this stock model matches any listing key
        matches = [k for k in listing_by_model.keys() if k == smodel or smodel == k or k in smodel or smodel in k]
        if matches:
            print(f'  MATCH: stock="{smodel}" -> listing keys: {matches}')
        else:
            # Check partial - first 4 chars
            partial = [k for k in listing_by_model.keys() if len(k) >= 4 and (k[:4] == smodel[:4] or smodel[:4] == k[:4])]
            print(f'  NO EXACT: stock="{smodel}" | partial matches: {partial[:5]}')