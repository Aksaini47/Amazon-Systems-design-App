import re
from collections import defaultdict

# Parse actual stock with quantities
with open('amazon-reports/actual stock.txt','r',encoding='utf-8') as f:
    slines = f.readlines()

BRAND_KEYWORDS = ['REALME','VIVO','OPPO','ONEPLUS','APPLE','SAMSUNG','XIAOMI','REDMI','POCO','MIX','MOTO','HONOR','NOKIA','ASUS','NOTHING','INFINIX']
stock = []
current_brand = ''
for line in slines:
    stripped = line.rstrip().strip()
    if not stripped or stripped.lower() == 'actual stock': continue
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

            # Screen type
            if 'oled' in nl: ss = 'OLED'
            elif 'incell' in nl: ss = 'Incell LCD'
            elif 'tft' in nl: ss = 'TFT LCD'
            elif 'lcd' in nl: ss = 'LCD'
            else: ss = 'Not Specified'

            # Quality
            if 'careog' in nl: sq = 'CareOG'
            elif 'frame' in nl or 'with frame' in nl or ' wf ' in nl: sq = 'With Frame'
            else: sq = 'Standard'

            stock.append({
                'brand': current_brand,
                'name': clean_name,
                'qty': qty,
                'screen': ss,
                'quality': sq
            })

# Parse All Listings
with open('amazon-reports/All+Listings+Report_05-12-2026.txt','r',encoding='utf-8-sig') as f:
    lines = f.readlines()

hdr_idx = next(i for i,l in enumerate(lines) if 'seller-sku' in l)
hdrs = [c.strip() for c in lines[hdr_idx].split('\t')]
listings = []
for l in lines[hdr_idx+1:]:
    if not l.strip(): continue
    cols = [c.strip() for c in l.split('\t')]
    if len(cols) < len(hdrs): cols += [''] * (len(hdrs) - len(cols))
    listings.append(dict(zip(hdrs, cols)))

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

def get_brand_from_title(title):
    if not title: return None
    t = title.lower()
    if 'compatible for apple' in t or 'compatible for iphone' in t: return 'APPLE'
    if 'compatible for samsung' in t or 'compatible for galaxy' in t: return 'SAMSUNG'
    if 'compatible for oneplus' in t: return 'ONEPLUS'
    if 'compatible for oppo' in t: return 'OPPO'
    if 'compatible for vivo' in t: return 'VIVO'
    if 'compatible for realme' in t: return 'REALME'
    if 'compatible for xiaomi' in t or 'compatible for redmi' in t or 'compatible for poco' in t: return 'XIAOMI'
    if 'compatible for moto' in t or 'compatible for motorola' in t: return 'MOTO'
    if 'compatible for honor' in t: return 'HONOR'
    if 'compatible for nokia' in t: return 'NOKIA'
    if 'compatible for asus' in t: return 'ASUS'
    if 'compatible for infinix' in t: return 'INFINIX'
    return None

def match_stock_to_listing(stock_item, listings):
    """Match stock item to Amazon listings by product title similarity"""
    name = stock_item['name'].lower()
    brand = stock_item['brand']
    ss = stock_item['screen']
    sq = stock_item['quality']

    # Extract model from stock name
    model_parts = []
    for word in name.split():
        word_clean = re.sub(r'[^a-z0-9]', '', word)
        if len(word_clean) >= 2 and word_clean not in ['incell','lcd','oled','tft','careog','frame','with','standard','gf','gf','5g','4g']:
            model_parts.append(word_clean)

    candidates = []

    for row in listings:
        title = row.get('item-name','')
        if not title: continue

        listing_brand = get_brand_from_title(title)

        # Brand match
        if brand == 'MIX':
            pass  # MIX brand can match many
        elif listing_brand and listing_brand != brand:
            continue  # Skip if brand doesn't match

        # Calculate match score based on title similarity
        title_lower = title.lower()
        score = 0

        # Check each model part
        for mp in model_parts:
            if mp in title_lower:
                score += len(mp) * 2  # Weight by length
            # Also check without "compatible for X "
            for prefix in ['apple iphone', 'samsung galaxy', 'oneplus ', 'oppo ', 'vivo ', 'realme ',
                          'xiaomi ', 'redmi ', 'poco ', 'motorola moto', 'honor ', 'nokia ', 'asus ', 'infinix ']:
                if prefix in title_lower:
                    rest = title_lower.split(prefix, 1)[1]
                    if mp in rest:
                        score += len(mp) * 3  # Higher weight if in model section

        if score > 0:
            ls, lq = extract_from_title(title)
            candidates.append({
                'row': row,
                'score': score,
                'listing_screen': ls,
                'listing_quality': lq,
                'listing_brand': listing_brand,
                'title': title
            })

    # Sort by score descending
    candidates.sort(key=lambda x: -x['score'])
    return candidates

# Brand display names
BRAND_DISPLAY = {
    'APPLE': 'Apple',
    'SAMSUNG': 'Samsung',
    'ONEPLUS': 'OnePlus',
    'OPPO': 'Oppo',
    'VIVO': 'Vivo',
    'REALME': 'Realme',
    'XIAOMI': 'Xiaomi/Redmi/Poco',
    'MOTO': 'Motorola',
    'HONOR': 'Honor',
    'NOKIA': 'Nokia',
    'ASUS': 'Asus',
    'INFINIX': 'Infinix',
    'MIX': 'Mixed',
    'NOTHING': 'Nothing'
}

def snorm(s):
    return 'LCD' if s in ['Incell LCD', 'TFT LCD'] else s

def quality_match(ss, sq, ls, lq):
    """Check if stock and listing quality match"""
    screen_ok = snorm(ss) == snorm(ls)
    quality_ok = sq == lq
    return screen_ok and quality_ok

# Generate report
out = []
out.append('=' * 100)
out.append('ACTUAL STOCK vs AMAZON INVENTORY - DETAILED ANALYSIS WITH QUANTITIES')
out.append('=' * 100)
out.append(f'Total stock: {len(stock)} variants, {sum(s["qty"] for s in stock)} units')
out.append('')

# Group by brand
from collections import Counter
brand_qty = Counter()
for s in stock:
    brand_qty[s['brand']] += s['qty']

out.append('STOCK SUMMARY BY BRAND:')
out.append('-' * 60)
for b in brand_qty.most_common():
    out.append(f'  {BRAND_DISPLAY.get(b[0], b[0]):<25} {b[1]:>4} units')
out.append('')

# Per-brand detailed analysis
for brand in ['REALME', 'VIVO', 'OPPO', 'ONEPLUS', 'APPLE', 'SAMSUNG', 'XIAOMI', 'MIX']:
    brand_stock = [s for s in stock if s['brand'] == brand]
    brand_total_qty = sum(s['qty'] for s in brand_stock)

    out.append('=' * 100)
    out.append(f'{BRAND_DISPLAY.get(brand, brand)} - {len(brand_stock)} variants, {brand_total_qty} units')
    out.append('-' * 100)

    for s in brand_stock:
        matches = match_stock_to_listing(s, listings)
        active = [m for m in matches if m['row'].get('status') == 'Active']
        inactive = [m for m in matches if m['row'].get('status') != 'Active']

        # Find best match
        best_active = None
        best_inactive = None

        # Look for exact quality match first
        for m in active:
            if quality_match(s['screen'], s['quality'], m['listing_screen'], m['listing_quality']):
                best_active = m
                break

        if not best_active:
            for m in active[:3]:
                best_active = m
                break

        for m in inactive[:2]:
            best_inactive = m
            break

        # Status determination
        if best_active:
            status = 'ACTIVE'
            matched = best_active
        elif best_inactive:
            status = 'INACTIVE'
            matched = best_inactive
        else:
            status = 'NOT LISTED'
            matched = None

        out.append(f'')
        out.append(f'[{s["qty"]}x] {s["name"]}')
        out.append(f'      Screen: {s["screen"]} | Quality: {s["quality"]}')

        if matched:
            screen_ok = snorm(s['screen']) == snorm(matched['listing_screen'])
            quality_ok = s['quality'] == matched['listing_quality']

            out.append(f'  -> {status}: {matched["row"]["seller-sku"]}')
            out.append(f'     Amazon: {matched["listing_screen"]}/{matched["listing_quality"]} | Status: {matched["row"].get("status","?")} | Qty: {matched["row"].get("quantity","?")} | Rs.{matched["row"].get("price","?")}')
            out.append(f'     Title: {matched["title"][:80]}')

            if status == 'ACTIVE':
                if screen_ok and quality_ok:
                    out.append(f'     [OK] QUALITY MATCH - Screen & Quality correctly aligned')
                else:
                    diffs = []
                    if not screen_ok: diffs.append(f'Screen: stock={s["screen"]} vs listing={matched["listing_screen"]}')
                    if not quality_ok: diffs.append(f'Quality: stock={s["quality"]} vs listing={matched["listing_quality"]}')
                    out.append(f'     [WARN] MISMATCH: {" | ".join(diffs)}')
            elif status == 'INACTIVE':
                out.append(f'     [WARN] LISTING INACTIVE - needs reactivation')
        else:
            out.append(f'     [NO MATCH] NO MATCHING AMAZON LISTING')

        out.append('')

out.append('=' * 100)
out.append('SUMMARY')
out.append('=' * 100)

# Count by status
status_counts = {'ACTIVE': 0, 'INACTIVE': 0, 'NOT LISTED': 0}
active_units = 0
inactive_units = 0
not_listed_units = 0

for s in stock:
    matches = match_stock_to_listing(s, listings)
    active = [m for m in matches if m['row'].get('status') == 'Active']

    if active:
        status_counts['ACTIVE'] += 1
        active_units += s['qty']
    elif any(m for m in matches if m['row'].get('status') != 'Active'):
        status_counts['INACTIVE'] += 1
        inactive_units += s['qty']
    else:
        status_counts['NOT LISTED'] += 1
        not_listed_units += s['qty']

out.append(f'')
out.append(f'ACTIVE LISTINGS: {status_counts["ACTIVE"]} variants ({active_units} units)')
out.append(f'INACTIVE LISTINGS: {status_counts["INACTIVE"]} variants ({inactive_units} units)')
out.append(f'NOT LISTED AT ALL: {status_counts["NOT LISTED"]} variants ({not_listed_units} units)')
out.append(f'')
out.append(f'TOTAL: {len(stock)} variants, {sum(s["qty"] for s in stock)} units')

# Export to CSV
import csv
csv_rows = []
for s in stock:
    matches = match_stock_to_listing(s, listings)
    active = [m for m in matches if m['row'].get('status') == 'Active']
    inactive = [m for m in matches if m['row'].get('status') != 'Active']

    if active:
        m = active[0]
        csv_rows.append({
            'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
            'Stock Name': s['name'],
            'Qty': s['qty'],
            'Stock Screen': s['screen'],
            'Stock Quality': s['quality'],
            'Status': 'ACTIVE',
            'Amazon SKU': m['row']['seller-sku'],
            'Amazon Qty': m['row'].get('quantity', ''),
            'Amazon Price': m['row'].get('price', ''),
            'Listing Screen': m['listing_screen'],
            'Listing Quality': m['listing_quality'],
            'Title': m['title'][:80]
        })
    elif inactive:
        m = inactive[0]
        csv_rows.append({
            'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
            'Stock Name': s['name'],
            'Qty': s['qty'],
            'Stock Screen': s['screen'],
            'Stock Quality': s['quality'],
            'Status': 'INACTIVE',
            'Amazon SKU': m['row']['seller-sku'],
            'Amazon Qty': m['row'].get('quantity', ''),
            'Amazon Price': m['row'].get('price', ''),
            'Listing Screen': m['listing_screen'],
            'Listing Quality': m['listing_quality'],
            'Title': m['title'][:80]
        })
    else:
        csv_rows.append({
            'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
            'Stock Name': s['name'],
            'Qty': s['qty'],
            'Stock Screen': s['screen'],
            'Stock Quality': s['quality'],
            'Status': 'NOT LISTED',
            'Amazon SKU': '',
            'Amazon Qty': '',
            'Amazon Price': '',
            'Listing Screen': '',
            'Listing Quality': '',
            'Title': ''
        })

with open('amazon-reports/stock_inventory_analysis.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['Brand','Stock Name','Qty','Stock Screen','Stock Quality','Status','Amazon SKU','Amazon Qty','Amazon Price','Listing Screen','Listing Quality','Title'])
    w.writeheader()
    w.writerows(csv_rows)

# Write report to file
with open('amazon-reports/stock_analysis_report.txt', 'w', encoding='utf-8') as f:
    for line in out:
        f.write(line + '\n')

# Print summary to console
for line in out:
    print(line)

print('\nCSV exported to: amazon-reports/stock_inventory_analysis.csv')
print('Report exported to: amazon-reports/stock_analysis_report.txt')