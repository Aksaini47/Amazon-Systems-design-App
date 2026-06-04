import re, csv
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

            if 'oled' in nl or 'amoled' in nl: screen_type = 'OLED'
            elif 'incell' in nl: screen_type = 'Incell LCD'
            elif 'tft' in nl: screen_type = 'TFT LCD'
            elif 'lcd' in nl: screen_type = 'LCD'
            else: screen_type = 'Unknown'

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

print(f'Stock: {len(stock)} variants, Listings: {len(listings)} SKUs')

def extract_model_from_title(title):
    if not title or 'Compatible for' not in title: return []
    after = title.split('Compatible for', 1)[1].strip()

    # Remove quality keywords
    for kw in ['CareOG','Careog','OLED','LCD','Incell','TFT','Amoled','AMOLED',
               'Fingerprint Support','No Fingerprint Support',
               'Display+Touch Screen Combo Folder','Display+Touch Screen Combo',
               'Display Screen Replacement Combo']:
        after = re.sub(r'\b' + kw + r'\b', ' ', after, flags=re.IGNORECASE)

    # Split by / for multi-model titles
    parts = after.split('/')
    models = []
    for part in parts:
        part = part.strip()
        # Remove brands
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

# Build all listings with extracted models
listing_data = []
for row in listings:
    title = row.get('item-name','')
    models = extract_model_from_title(title) if title else []
    listing_data.append({
        'row': row,
        'title': title,
        'models': models,
        'sku': row.get('seller-sku','').lower(),
    })

# Match each stock item
results = []
for s in stock:
    stock_model = extract_stock_model(s['original_name'])
    s['model'] = stock_model

    # Find listings where stock model appears in listing title OR listing model appears in stock name
    matches = []
    for ld in listing_data:
        title = ld['title'].lower()
        sku = ld['sku']
        orig_lower = s['original_name'].lower().replace(' ','')

        # Method 1: Stock model in listing title
        if stock_model and len(stock_model) >= 2:
            # Check if stock model appears as substring in title
            if stock_model in title:
                matches.append(ld)
                continue

        # Method 2: Listing model in stock original name
        for lm in ld['models']:
            lm_clean = lm.lower().replace(' ','')
            if len(lm_clean) >= 2:
                # Check if listing model appears in stock original name
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

# Output
out_lines = []
out_lines.append('STOCK vs AMAZON LISTING MATCHING (v2)')
out_lines.append('=' * 120)
out_lines.append('')

brand_counts = defaultdict(lambda: {'total':0,'active':0,'inactive':0,'not_listed':0})

for r in results:
    s = r['stock']
    matches = r['matches']
    brand_counts[s['brand']]['total'] += 1

    active = [v for v in matches if v['row'].get('status') == 'Active']
    inactive = [v for v in matches if v['row'].get('status') != 'Active']

    line = f'{s["brand"]}|{s["original_name"]}|qty:{s["qty"]}|screen:{s["screen_type"]}|quality:{s["quality"]}'

    if active:
        brand_counts[s['brand']]['active'] += 1
        for m in active:
            out_lines.append(f'ACTIVE   {line}')
            out_lines.append(f'         -> {m["row"]["seller-sku"]} | qty:{m["row"].get("quantity","?")} | Rs.{m["row"].get("price","?")} | {m["title"][:90]}')
        out_lines.append('')
    elif inactive:
        brand_counts[s['brand']]['inactive'] += 1
        out_lines.append(f'INACTIVE {line}')
        first_inactive = inactive[0]
        out_lines.append(f'         -> {first_inactive["row"]["seller-sku"]} | status:{first_inactive["row"].get("status","?")} | {first_inactive["title"][:80]}')
        if len(inactive) > 1:
            out_lines.append(f'         ({len(inactive)} total inactive matches)')
        out_lines.append('')
    else:
        brand_counts[s['brand']]['not_listed'] += 1
        out_lines.append(f'NOT LISTED {line}')
        out_lines.append('')

active_total = sum(1 for r in results if any(v['row'].get('status')=='Active' for v in r['matches']))
inactive_total = sum(1 for r in results if r['matches'] and not any(v['row'].get('status')=='Active' for v in r['matches']))
not_listed_total = sum(1 for r in results if not r['matches'])

out_lines.append('=' * 120)
out_lines.append('SUMMARY BY BRAND:')
out_lines.append('')
for b, d in sorted(brand_counts.items(), key=lambda x: -x[1]['total']):
    out_lines.append(f'  {b}: {d["total"]} stock | {d["active"]} ACTIVE | {d["inactive"]} INACTIVE | {d["not_listed"]} NOT LISTED')
out_lines.append('')
out_lines.append(f'TOTAL STOCK: {len(results)} variants, {sum(s["qty"] for s in stock)} units')
out_lines.append(f'  ACTIVE on Amazon: {active_total}')
out_lines.append(f'  INACTIVE on Amazon: {inactive_total}')
out_lines.append(f'  NOT LISTED at all: {not_listed_total}')

with open('stock_listing_match_v2.txt','w',encoding='utf-8') as f:
    f.write('\n'.join(out_lines))

print('Written to stock_listing_match_v2.txt')
print()
# Print summary
for b, d in sorted(brand_counts.items(), key=lambda x: -x[1]['total']):
    print(f'  {b}: {d["total"]} stock | {d["active"]} ACTIVE | {d["inactive"]} INACTIVE | {d["not_listed"]} NOT LISTED')
print()
print(f'TOTAL: ACTIVE={active_total} INACTIVE={inactive_total} NOT_LISTED={not_listed_total}')