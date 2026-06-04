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
        if part: models.append(part.lower())
    return models

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

def get_stock_model(original):
    model = original
    for skip in ['Realme ','Vivo ','Oppo ','OnePlus ','Apple iPhone ','Apple ',
                 'Samsung Galaxy ','Xiaomi ','Redmi ','Poco ','Moto ','Honor ','Nokia ',
                 'Asus ','Nothing Phone ','Infinix ']:
        model = model.replace(skip, '').replace(skip.lower(), '')
    for skip in ['Incell','OLED','AMOLED','CareOG','Careog','Frame','With','Standard','White','Black','Gold']:
        model = re.sub(r'\b' + skip + r'\b', '', model, flags=re.IGNORECASE)
    return ' '.join(model.split()).strip().lower()

# Debug: check what models are extracted from Apple listings
print('APPLE LISTINGS - extracted models:')
apple_listings = [r for r in listings if 'iPhone' in r.get('item-name','') and r.get('status') == 'Active']
print(f'Active Apple: {len(apple_listings)}')
for r in apple_listings[:10]:
    models = extract_models(r.get('item-name',''))
    ls, lq = extract_from_title(r.get('item-name',''))
    print(f'  {r["seller-sku"]} | {r["status"]} | models={models} | screen={ls} | quality={lq}')

print()
print('SAMSUNG LISTINGS - extracted models:')
sam_listings = [r for r in listings if 'Samsung' in r.get('item-name','') and r.get('status') == 'Active']
print(f'Active Samsung: {len(sam_listings)}')
for r in sam_listings[:10]:
    models = extract_models(r.get('item-name',''))
    ls, lq = extract_from_title(r.get('item-name',''))
    print(f'  {r["seller-sku"]} | {r["status"]} | models={models} | screen={ls} | quality={lq}')

print()
# Now check what models we get from stock
print('APPLE STOCK models:')
apple_stock = [s for s in stock if s['brand'] == 'APPLE']
for s in apple_stock:
    m = get_stock_model(s['original_name'])
    print(f'  {s["original_name"]} -> model=\"{m}\" | screen={s["stock_screen"]} | quality={s["stock_quality"]}')

print()
print('SAMSUNG STOCK models:')
sam_stock = [s for s in stock if s['brand'] == 'SAMSUNG']
for s in sam_stock:
    m = get_stock_model(s['original_name'])
    print(f'  {s["original_name"]} -> model=\"{m}\" | screen={s["stock_screen"]} | quality={s["stock_quality"]}')