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
# STEP 3: Extract model identifiers from stock names
# ============================================================
def extract_stock_model(name):
    """Extract the phone model identifier from a stock name."""
    n = name.lower()

    # Remove brand prefixes
    for prefix in ['realme ', 'vivo ', 'oppo ', 'oneplus ', 'apple iphone ',
                   'samsung galaxy ', 'xiaomi ', 'redmi ', 'poco ', 'moto ',
                   'honor ', 'nokia ', 'asus ', 'nothing phone ', 'infinix ']:
        n = n.replace(prefix, '').replace(prefix.upper(), '')

    # Remove iPhone/Galaxy standalone
    n = re.sub(r'^iphone\s+', '', n)
    n = re.sub(r'^galaxy\s+', '', n)

    # Remove quality/screen terms
    for skip in ['incell', 'oled', 'amoled', 'super oled', 'lcd', 'tft',
                 'careog', 'frame', 'with frame', 'standard', 'white',
                 'black', 'gold', 'wf ']:
        n = re.sub(r'\b' + skip + r'\b', '', n, flags=re.IGNORECASE)

    # Extract model core (e.g. "c67" from "realme c67 incell")
    n = re.sub(r'[^a-z0-9]', '', n)
    return n


def extract_models_from_title(title):
    """Extract model identifiers from Amazon listing title."""
    if not title or 'Compatible for' not in title:
        return []

    after = title.split('Compatible for', 1)[1].strip()

    # Remove common descriptive words
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
    """Get brand from listing title."""
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
    """Normalize screen types for comparison."""
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


# Brand mapping
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


def match_listing(stock_item):
    """
    Match a stock item to Amazon listings.
    Strategy:
      1. Find listings in the same brand
      2. Look for model number matches (exact substring or prefix)
      3. Prefer exact screen+quality matches; fall back to screen-only
      4. Return best match with confidence
    """
    sbrand = stock_item['brand']
    smodel = extract_stock_model(stock_item['original_name'])
    ss = stock_item['screen']
    sq = stock_item['quality']

    # Determine which brand keys to search
    search_brands = BRAND_ALIASES.get(sbrand, [sbrand])

    candidates = []
    for brand_key in search_brands:
        for item in listings_by_brand.get(brand_key, []):
            title = item['title']
            listing_models = item['models']
            ls = item['listing_screen']
            lq = item['listing_quality']

            # Model matching: check if stock model appears in listing models
            model_match = False
            for lm in listing_models:
                # Exact match
                if smodel == lm:
                    model_match = True
                    break
                # Stock model is prefix of listing model (stock=a73, listing=a73folder)
                if len(lm) >= len(smodel) and lm.startswith(smodel) and len(smodel) >= 3:
                    model_match = True
                    break
                # Listing model is prefix of stock (stock=j7next, listing=j7)
                if len(smodel) >= len(lm) and smodel.startswith(lm) and len(lm) >= 3:
                    model_match = True
                    break
                # First 4+ chars match (e.g., "y22s" vs "y22")
                if len(smodel) >= 4 and len(lm) >= 4 and smodel[:4] == lm[:4]:
                    model_match = True
                    break

            if not model_match:
                continue

            screen_ok = snorm(ss) == snorm(ls)
            quality_ok = sq == lq

            # Confidence score
            score = 0
            if screen_ok:
                score += 10
            if quality_ok:
                score += 20
            if sq == 'CareOG' and lq == 'CareOG':
                score += 5
            if sq == 'With Frame' and lq == 'With Frame':
                score += 5

            candidates.append({
                'item': item,
                'screen_ok': screen_ok,
                'quality_ok': quality_ok,
                'score': score,
                'match_reason': f'stock_model={smodel} matched listing_models={listing_models}'
            })

    if not candidates:
        return None, 'NO MATCH'

    # Sort by score desc
    candidates.sort(key=lambda x: -x['score'])

    best = candidates[0]
    screen_ok = best['screen_ok']
    quality_ok = best['quality_ok']

    if screen_ok and quality_ok:
        confidence = 'HIGH'
    elif screen_ok:
        confidence = 'MEDIUM'
    else:
        confidence = 'LOW'

    return best, confidence


# ============================================================
# STEP 4: Generate Report
# ============================================================
out = []
out.append('=' * 110)
out.append('ACTUAL STOCK vs AMAZON INVENTORY — PRECISE MODEL MATCHING')
out.append('=' * 110)
total_units = sum(s['qty'] for s in stock)
out.append(f'Total stock: {len(stock)} variants, {total_units} units')
out.append('')

# Brand summary
from collections import Counter
brand_qty = Counter()
for s in stock:
    brand_qty[s['brand']] += s['qty']

out.append('STOCK BY BRAND:')
out.append('-' * 60)
for b, qty in brand_qty.most_common():
    variants = sum(1 for s in stock if s['brand'] == b)
    out.append(f'  {BRAND_DISPLAY.get(b, b):<25} {variants:>3} variants, {qty:>3} units')
out.append('')

# Detailed per-brand analysis
BRAND_ORDER = ['REALME', 'VIVO', 'OPPO', 'ONEPLUS', 'APPLE', 'SAMSUNG', 'XIAOMI', 'MIX']

total_active = 0
total_inactive = 0
total_not_listed = 0
total_active_units = 0
total_inactive_units = 0
total_not_listed_units = 0
mismatch_items = []

for brand in BRAND_ORDER:
    brand_stock = [s for s in stock if s['brand'] == brand]
    if not brand_stock:
        continue

    brand_units = sum(s['qty'] for s in brand_stock)
    out.append('=' * 110)
    out.append(f'{BRAND_DISPLAY.get(brand, brand):} — {len(brand_stock)} variants, {brand_units} units')
    out.append('-' * 110)

    for s in brand_stock:
        best, confidence = match_listing(s)
        smodel = extract_stock_model(s['original_name'])

        if best:
            item = best['item']
            row = item['row']
            status = row.get('status', '?')
            ls = item['listing_screen']
            lq = item['listing_quality']

            if status == 'Active':
                total_active += 1
                total_active_units += s['qty']
            else:
                total_inactive += 1
                total_inactive_units += s['qty']

            screen_ok = best['screen_ok']
            quality_ok = best['quality_ok']

            out.append('')
            out.append(f'[{s["qty"]}x] {s["original_name"]}')
            out.append(f'      Stock: {s["screen"]} | {s["quality"]} | model_key={smodel}')

            title_short = item['title'][:90]
            out.append(f'  -> [{confidence}] {status}: {row["seller-sku"]}')
            out.append(f'     Amazon: {ls}/{lq} | Qty: {row.get("quantity","?")} | Rs.{row.get("price","?")}')
            out.append(f'     Title: {title_short}')

            if confidence == 'HIGH':
                out.append(f'     [OK] MATCH — screen & quality aligned')
            else:
                diffs = []
                if not screen_ok:
                    diffs.append(f'Screen MISMATCH: stock={s["screen"]} vs listing={ls}')
                if not quality_ok:
                    diffs.append(f'Quality MISMATCH: stock={s["quality"]} vs listing={lq}')
                out.append(f'     [WARN] {confidence} CONFIDENCE — ' + ' | '.join(diffs))
                mismatch_items.append({
                    'stock': s['original_name'],
                    'brand': brand,
                    'stock_screen': s['screen'],
                    'stock_quality': s['quality'],
                    'listing': row['seller-sku'],
                    'listing_screen': ls,
                    'listing_quality': lq,
                    'title': item['title'][:60],
                    'issue': ' | '.join(diffs)
                })
        else:
            total_not_listed += 1
            total_not_listed_units += s['qty']
            out.append('')
            out.append(f'[{s["qty"]}x] {s["original_name"]}')
            out.append(f'      Stock: {s["screen"]} | {s["quality"]} | model_key={smodel}')
            out.append(f'  -> [NO MATCH] NO MATCHING AMAZON LISTING FOUND')
            mismatch_items.append({
                'stock': s['original_name'],
                'brand': brand,
                'stock_screen': s['screen'],
                'stock_quality': s['quality'],
                'listing': '',
                'listing_screen': '',
                'listing_quality': '',
                'title': '',
                'issue': 'NOT LISTED ON AMAZON'
            })

        out.append('')

out.append('=' * 110)
out.append('SUMMARY')
out.append('=' * 110)
out.append('')
out.append(f'ACTIVE LISTINGS:    {total_active} variants ({total_active_units} units)')
out.append(f'INACTIVE LISTINGS: {total_inactive} variants ({total_inactive_units} units)')
out.append(f'NOT LISTED:        {total_not_listed} variants ({total_not_listed_units} units)')
out.append(f'TOTAL:             {len(stock)} variants, {total_units} units')
out.append('')

# MISMATCH REPORT
if mismatch_items:
    out.append('=' * 110)
    out.append('ITEMS NEEDING ATTENTION')
    out.append('=' * 110)
    for mi in mismatch_items:
        out.append(f'{mi["brand"]:10} | {mi["stock"]:30} | {mi["stock_screen"]:12} | {mi["stock_quality"]:12} | {mi["issue"]}')
    out.append('')

# Write report
with open('stock_match_v2_report.txt', 'w', encoding='utf-8') as f:
    for line in out:
        f.write(line + '\n')

# Write CSV
import csv
csv_rows = []
for s in stock:
    best, confidence = match_listing(s)
    if best:
        item = best['item']
        row = item['row']
        csv_rows.append({
            'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
            'Stock Name': s['original_name'],
            'Qty': s['qty'],
            'Stock Screen': s['screen'],
            'Stock Quality': s['quality'],
            'Confidence': confidence,
            'Amazon Status': row.get('status', '?'),
            'Amazon SKU': row['seller-sku'],
            'Amazon Qty': row.get('quantity', ''),
            'Amazon Price': row.get('price', ''),
            'Listing Screen': item['listing_screen'],
            'Listing Quality': item['listing_quality'],
            'Match Issue': '' if confidence == 'HIGH' else ('Screen' if not best['screen_ok'] else 'Quality') if confidence == 'MEDIUM' else 'Multiple',
            'Title': item['title'][:80]
        })
    else:
        csv_rows.append({
            'Brand': BRAND_DISPLAY.get(s['brand'], s['brand']),
            'Stock Name': s['original_name'],
            'Qty': s['qty'],
            'Stock Screen': s['screen'],
            'Stock Quality': s['quality'],
            'Confidence': 'NONE',
            'Amazon Status': '',
            'Amazon SKU': '',
            'Amazon Qty': '',
            'Amazon Price': '',
            'Listing Screen': '',
            'Listing Quality': '',
            'Match Issue': 'NOT LISTED',
            'Title': ''
        })

with open('stock_match_v2.csv', 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['Brand', 'Stock Name', 'Qty', 'Stock Screen', 'Stock Quality',
                  'Confidence', 'Amazon Status', 'Amazon SKU', 'Amazon Qty',
                  'Amazon Price', 'Listing Screen', 'Listing Quality', 'Match Issue', 'Title']
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(csv_rows)

print('Report written to: amazon-reports/stock_match_v2_report.txt')
print('CSV written to: amazon-reports/stock_match_v2.csv')
print()
print(f'HIGH confidence matches: {sum(1 for r in csv_rows if r["Confidence"] == "HIGH")}')
print(f'MEDIUM confidence: {sum(1 for r in csv_rows if r["Confidence"] == "MEDIUM")}')
print(f'LOW confidence: {sum(1 for r in csv_rows if r["Confidence"] == "LOW")}')
print(f'NO MATCH: {sum(1 for r in csv_rows if r["Confidence"] == "NONE")}')
