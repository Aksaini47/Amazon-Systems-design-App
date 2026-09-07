import re
from collections import defaultdict

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

def extract_listing_brand(title):
    if not title or 'Compatible for' not in title: return None
    after = title.split('Compatible for', 1)[1].strip()
    checks = [
        ('Apple iPhone', 'APPLE'), ('Samsung Galaxy', 'SAMSUNG'), ('Samsung ', 'SAMSUNG'),
        ('Xiaomi ', 'XIAOMI'), ('Redmi ', 'REDMI'), ('POCO ', 'POCO'), ('Realme ', 'REALME'),
        ('Vivo ', 'VIVO'), ('Oppo ', 'OPPO'), ('OnePlus ', 'ONEPLUS'),
        ('Motorola Moto', 'MOTO'), ('Moto ', 'MOTO'), ('Honor ', 'HONOR'), ('Nokia ', 'NOKIA'),
        ('Asus ', 'ASUS'), ('Nothing Phone', 'NOTHING'), ('Nothing ', 'NOTHING'),
        ('Infinix ', 'INFINIX'), ('Tecno ', 'TECNO'),
    ]
    for kw, brand in checks:
        if kw.lower() in after.lower(): return brand
    return None

def get_clean_stock_model(original):
    model = original
    for skip in ['Realme ', 'Vivo ', 'Oppo ', 'OnePlus ', 'Apple iPhone ', 'Apple ',
                 'Samsung Galaxy ', 'Xiaomi ', 'Redmi ', 'Poco ', 'Moto ', 'Honor ', 'Nokia ',
                 'Asus ', 'Nothing Phone ', 'Infinix ']:
        model = model.replace(skip, '').replace(skip.lower(), '')
    model = re.sub(r'^iPhone\s+', '', model, flags=re.IGNORECASE)
    model = re.sub(r'^Galaxy\s+', '', model, flags=re.IGNORECASE)
    model = model.replace('iPhone', '').replace('Galaxy', '')
    for skip in ['Incell','OLED','AMOLED','CareOG','Careog','Frame','With','Standard','White','Black','Gold']:
        model = re.sub(r'\b' + skip + r'\b', '', model, flags=re.IGNORECASE)
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

def snorm(screen):
    return 'LCD' if screen in ['Incell LCD', 'TFT LCD'] else screen

listing_by_model = defaultdict(list)
for row in listings:
    title = row.get('item-name','')
    if not title: continue
    ls, lq = extract_from_title(title)
    lbrand = extract_listing_brand(title)
    models = extract_clean_model(title)
    for m in models:
        listing_by_model[m].append({'row': row, 'listing_screen': ls, 'listing_quality': lq, 'listing_brand': lbrand, 'title': title})

def smart_match(stock_brand, stock_model, listing_key):
    s = stock_model
    l = listing_key
    if s == l: return True
    # Substring check: listing contains stock (e.g. stock=a73, listing=a73folder)
    if len(l) >= len(s) and l.startswith(s): return True
    # Substring check: stock contains listing (e.g. stock=j7next, listing=j7)
    if len(s) >= len(l) and s.startswith(l): return True
    # Fallback: first N chars match
    for n in [6, 5, 4]:
        if len(s) >= n and len(l) >= n:
            if s[:n] == l[:n]: return True
    return False

def find_matches(stock_item):
    stock_brand = stock_item['brand']
    smodel = get_clean_stock_model(stock_item['original_name'])
    ss = stock_item['stock_screen']
    sq = stock_item['stock_quality']

    matches = []
    for listing_key, items in listing_by_model.items():
        if not smart_match(stock_brand, smodel, listing_key): continue
        for item in items:
            lb = item['listing_brand']
            if lb is None: continue
            if stock_brand in ['APPLE','SAMSUNG','ONEPLUS','OPPO','VIVO','REALME'] and lb != stock_brand: continue
            if stock_brand in ['XIAOMI','REDMI','POCO'] and lb not in ['XIAOMI','REDMI','POCO']: continue
            if stock_brand == 'MIX' and lb not in ['XIAOMI','REDMI','POCO','REALME','VIVO','OPPO','INFINIX','HONOR','NOKIA','MOTO','ASUS','NOTHING','TECNO']: continue
            if snorm(item['listing_screen']) == snorm(ss) and item['listing_quality'] == sq:
                matches.append(item)

    seen = {}
    unique = []
    for m in matches:
        sku = m['row']['seller-sku']
        if sku not in seen:
            seen[sku] = m
            unique.append(m)
    return unique

# Test specific Samsung items
sam_stock = [s for s in stock if s['brand'] == 'SAMSUNG']
print(f'Total Samsung stock items: {len(sam_stock)}')
for s in sam_stock:
    smodel = get_clean_stock_model(s['original_name'])
    matches = find_matches(s)
    active = [m for m in matches if m['row'].get('status') == 'Active']
    inactive = [m for m in matches if m['row'].get('status') != 'Active']
    status = 'ACTIVE' if active else ('INACTIVE' if inactive else 'NONE')
    print(f'{s["original_name"]:40} model={smodel:10} status={status}')
    if matches and status == 'NONE':
        for m in matches[:2]:
            print(f'  -> {m["row"]["seller-sku"]} {m["listing_screen"]}/{m["listing_quality"]} but stock needs {s["stock_screen"]}/{s["stock_quality"]}')