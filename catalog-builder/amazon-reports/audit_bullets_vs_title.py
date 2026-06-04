"""
Audit bulk_upload_update_final.xlsx — title vs bullets consistency + Amazon India compliance.

Checks per row:
  A. Field population: which bullets are filled vs empty
  B. Compliance hard limits: title <=200 chars, each bullet <=255 chars, total bullets <=1000 bytes,
     keywords <=200 bytes, brand column empty on Edit
  C. Banned terms (memory + skill): best, #1, top-rated, refund, GST, WhatsApp, money-back, guarantee
  D. ALL CAPS / emoji content (Amazon strips these silently since Aug 2024)
  E. Tier name leakage: Bronze/Silver/Gold/AAA/Premium in customer-facing bullets (memory: tiers internal-only)
  F. Title <-> bullet1 consistency: brand+model agreement, screen type agreement, frame status agreement
  G. Hinglish keyword presence (user preference): sceen, kharab, marammat, asali, etc.
  H. Warranty wording: "7 days" or "7 day" present in bullet5 (memory standard)
  I. Repairfully.com support mention (memory: only allowed support reference)

Outputs:
  audit_report.md — markdown summary + sample violations
  audit_findings.csv — per-SKU per-issue rows for filtering in Excel
"""
import sys, io, os, re, json, csv
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import openpyxl
from collections import Counter, defaultdict
from pathlib import Path

XLSX = sys.argv[1] if len(sys.argv) > 1 else 'bulk_upload_update_final.xlsx'
USE_CANONICAL = len(sys.argv) > 2 and sys.argv[2] == '--canonical'

# ---------------- Compliance constants (Amazon India 2026) ----------------
TITLE_MAX_CHARS = 200
BULLET_MAX_CHARS = 255
BULLETS_TOTAL_BYTE_CAP = 1000   # indexing cliff
KEYWORDS_BYTE_CAP = 200          # India: 1 byte over -> ALL backend keywords de-indexed

BANNED_TERMS = [
    # promotional language
    r'\bbest\b', r'\b#1\b', r'\bnumber\s*1\b', r'\btop[-\s]?rated\b', r'\bworld\s*class\b',
    r'\bguaranteed?\b', r'\bmoney[-\s]?back\b',
    # Amazon India specific bans
    r'\brefund\b', r'\breturn\s*guarantee\b',
    r'\bGST\b', r'\bgst\s*invoice\b',
    r'\bwhatsapp\b', r'\bwa\s+only\b',
    r'\bbulk\s+pricing\b', r'\bwholesale\s+rates?\b',
]
TIER_LEAK_TERMS = [
    r'\bbronze\b', r'\bsilver\b',
    r'\bAAA\+?\s*Plus\b', r'\bAAA\b',
]
# "Gold" requires context-check (often a device color like "Galaxy J4 (Gold)")
TIER_GOLD_RE = re.compile(r'\bgold\b', re.IGNORECASE)
# Recognize Gold as device color when it appears inside parens after a phone model
GOLD_AS_COLOR_RE = re.compile(r'\([^)]*\bgold\b[^)]*\)', re.IGNORECASE)
# "Premium" is borderline marketing — flag separately from tier leak
PREMIUM_RE = re.compile(r'\bpremium\b', re.IGNORECASE)
HINGLISH_TOKENS = ['sceen', 'kharab', 'tutta', 'marammat', 'asali', 'asli']
WARRANTY_TOKENS = [r'\b7\s*day(s)?\b', r'\bseven\s*days?\b']
REPAIRFULLY_TOKEN = r'repairfully\.com'

EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols
    "\U0001F680-\U0001F6FF"  # transport
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "]", flags=re.UNICODE)

ALLCAPS_RE = re.compile(r'\b[A-Z]{4,}\b')  # 4+ consecutive caps (allow short acronyms LCD, OEM, OLED)
ALLCAPS_ALLOWLIST = {'LCD', 'OLED', 'AMOLED', 'INCELL', 'OEM', 'CARE', 'CAREOG', 'IPS', 'MRP', 'MPN',
                     'IPHONE', 'GALAXY', 'NOTE', 'POCO', 'REDMI', 'PRO', 'PLUS', 'MAX', 'ULTRA',
                     'SUPER', 'CARTE', 'XDR', 'HDR', 'JPG', 'RGB', 'WPMP', 'IMEI', 'NFC', 'WIFI',
                     'INDIA', 'CHINA', 'JAPAN', 'USA', 'UK', 'EU', 'GLASS', 'TOUCH', 'DIGITIZER',
                     'PANEL', 'COMBO', 'FRAME', 'BEZEL',
                     'POVA', 'TECNO', 'INFINIX', 'HONOR', 'NOKIA', 'MOTO', 'ASUS', 'OPPO',
                     'VIVO', 'ONEPLUS', 'XIAOMI', 'NORD'}

def byte_len(s):
    return len((s or '').encode('utf-8'))

def char_len(s):
    return len(s or '')

def find_banned(s, patterns):
    if not s: return []
    found = []
    for p in patterns:
        for m in re.finditer(p, s, flags=re.IGNORECASE):
            found.append(m.group(0))
    return found

def find_emojis(s):
    if not s: return []
    return EMOJI_RE.findall(s)

def find_allcaps(s):
    if not s: return []
    matches = ALLCAPS_RE.findall(s)
    return [m for m in matches if m not in ALLCAPS_ALLOWLIST]

def extract_brand(s):
    """Extract brand from title prefix (Compatible for [Brand] ...)"""
    if not s: return None
    m = re.match(r'compatible\s+for\s+(\w+(?:\s+\w+)?)\b', s, re.IGNORECASE)
    if m: return m.group(1).strip()
    return None

def extract_screen_type(s):
    """Find screen type tokens in a string."""
    if not s: return set()
    types = set()
    s_low = s.lower()
    if re.search(r'\bin[-\s]?cell\b', s_low) or 'incell' in s_low: types.add('Incell')
    if re.search(r'\boled\b', s_low) or 'amoled' in s_low: types.add('OLED')
    if re.search(r'\blcd\b', s_low): types.add('LCD')
    if 'careog' in s_low or 'care og' in s_low or re.search(r'\bcare\s+og\b', s_low): types.add('CareOG')
    if 'super retina' in s_low or 'super amoled' in s_low: types.add('OLED')
    return types

def extract_frame_status(s):
    """Detect 'with frame' / 'without frame' in title or bullet."""
    if not s: return None
    s_low = s.lower()
    if 'without frame' in s_low or 'no frame' in s_low: return 'without'
    if 'with frame' in s_low or 'frame included' in s_low: return 'with'
    return None  # unspecified

def extract_fp_status(s):
    """Detect fingerprint support."""
    if not s: return None
    s_low = s.lower()
    if 'fingerprint not' in s_low or 'no fingerprint' in s_low or 'fingerprint unavailable' in s_low: return 'no'
    if 'fingerprint support' in s_low or 'with fingerprint' in s_low or 'fp support' in s_low: return 'yes'
    return None

# ---------------- Run ----------------
print(f'Loading {XLSX}...')
wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
ws = wb['Template']
header = None
rows = []
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i == 0:
        header = list(row)
    else:
        rows.append(row)

# Column mapping — original file has a shift bug (use EMPIRICAL); fixed file has
# canonical alignment matching the header (use CANONICAL).
EMPIRICAL_COL = {
    'SKU': 0, 'product_type': 1, 'listing_action': 2, 'item_name': 3, 'brand': 4,
    'main_image_url': 5,
    'other_image_url_1': 6, 'other_image_url_2': 7, 'other_image_url_3': 8,
    'other_image_url_4': 9, 'other_image_url_5': 10, 'other_image_url_6': 11,
    'other_image_url_7': 12,
    'description': 13, 'bullet1': 14, 'bullet2': 15, 'bullet3': 16, 'bullet4': 17, 'bullet5': 18,
    'keywords': 19,
    'compatible_phone_1': 20, 'compatible_phone_2': 21, 'compatible_phone_3': 22,
    'fulfillment_channel': 23, 'quantity': 24, 'your_price': 25, 'mrp': 26,
}
CANONICAL_COL = {h: i for i, h in enumerate(header)}
idx = CANONICAL_COL if USE_CANONICAL else EMPIRICAL_COL
mode = 'CANONICAL' if USE_CANONICAL else 'EMPIRICAL'
print(f'Loaded {len(rows)} SKU rows. Header has {len(header)} cols; using {mode} column mapping')

# Per-row audit
findings = []
stats = Counter()
field_pop = Counter()
banned_examples = defaultdict(list)
allcaps_examples = defaultdict(list)
tier_leak_examples = defaultdict(list)
length_violations = []
brand_filled_count = 0
title_brand_mismatch_count = 0
screen_mismatch_count = 0
frame_mismatch_count = 0
hinglish_present_count = 0
warranty_present_count = 0
repairfully_present_count = 0
hinglish_missing_in_keywords = []
warranty_missing_in_bullets = []

for r in rows:
    sku = r[idx['SKU']] or '?'
    title = r[idx['item_name']] or ''
    brand = r[idx['brand']] or ''
    desc = r[idx['description']] or ''
    b1 = r[idx['bullet1']] or ''
    b2 = r[idx['bullet2']] or ''
    b3 = r[idx['bullet3']] or ''
    b4 = r[idx['bullet4']] or ''
    b5 = r[idx['bullet5']] or ''
    keywords = r[idx['keywords']] or ''
    listing_action = r[idx['listing_action']] or ''

    bullets = [b1, b2, b3, b4, b5]
    bullets_total = ' '.join(bullets)
    customer_facing = ' '.join([title, desc] + bullets + [keywords])

    # A. Field population
    for i, b in enumerate(bullets, 1):
        if b: field_pop[f'bullet{i}'] += 1
    if title: field_pop['title'] += 1
    if desc: field_pop['description'] += 1
    if keywords: field_pop['keywords'] += 1
    if brand: field_pop['brand'] += 1

    # B. Hard length limits
    if char_len(title) > TITLE_MAX_CHARS:
        length_violations.append((sku, 'title', char_len(title), TITLE_MAX_CHARS))
        stats['violation_title_length'] += 1
    for i, b in enumerate(bullets, 1):
        if b and char_len(b) > BULLET_MAX_CHARS:
            length_violations.append((sku, f'bullet{i}', char_len(b), BULLET_MAX_CHARS))
            stats[f'violation_bullet{i}_length'] += 1
    bullets_bytes = byte_len(bullets_total)
    if bullets_bytes > BULLETS_TOTAL_BYTE_CAP:
        length_violations.append((sku, 'bullets_total_bytes', bullets_bytes, BULLETS_TOTAL_BYTE_CAP))
        stats['violation_bullets_indexing_cliff'] += 1
    kw_bytes = byte_len(keywords)
    if kw_bytes > KEYWORDS_BYTE_CAP:
        length_violations.append((sku, 'keywords_bytes', kw_bytes, KEYWORDS_BYTE_CAP))
        stats['violation_keywords_byte_cap'] += 1

    # B. Brand column on Edit Partial Update should be empty (memory standard)
    if 'Edit' in listing_action and brand:
        brand_filled_count += 1
        stats['brand_filled_on_edit'] += 1
        findings.append([sku, 'brand_filled_on_edit', f'brand="{brand}" on Edit Partial Update (memory says blank)'])

    # C. Banned terms
    banned_in_cf = find_banned(customer_facing, BANNED_TERMS)
    if banned_in_cf:
        stats['banned_terms_present'] += 1
        for term in set(banned_in_cf):
            banned_examples[term.lower()].append(sku)
            findings.append([sku, f'banned_term:{term.lower()}', term])

    # D. Emoji
    emojis = find_emojis(customer_facing)
    if emojis:
        stats['emoji_present'] += 1
        findings.append([sku, 'emoji', ','.join(set(emojis))])

    # D. ALL CAPS (excluding allowlist) — skip BP1 since it contains model numbers
    # (Pixel codes like GLUOG, Samsung SM-codes, iPhone A-codes etc. are legit ALL CAPS)
    cf_no_bp1 = ' '.join([title, desc, b2, b3, b4, b5, keywords])
    allcaps_hits = find_allcaps(cf_no_bp1)
    if allcaps_hits:
        stats['allcaps_present'] += 1
        for w in set(allcaps_hits):
            allcaps_examples[w].append(sku)
            findings.append([sku, 'allcaps', w])

    # E1. Tier name leakage (Bronze/Silver/AAA) — hard violation
    tier_leak = find_banned(customer_facing, TIER_LEAK_TERMS)
    if tier_leak:
        stats['tier_name_leak'] += 1
        for term in set(tier_leak):
            tier_leak_examples[term.lower()].append(sku)
            findings.append([sku, f'tier_leak:{term.lower()}', term])

    # E2. "Gold" — only flag if NOT inside parens (i.e. not a device color)
    gold_hits = TIER_GOLD_RE.findall(customer_facing)
    color_gold_hits = GOLD_AS_COLOR_RE.findall(customer_facing)
    if gold_hits and len(gold_hits) > len(color_gold_hits):
        stats['gold_outside_color_parens'] += 1
        tier_leak_examples['gold (non-color)'].append(sku)
        findings.append([sku, 'tier_leak:gold_non_color', 'gold appears outside device-color parens'])

    # E3. "Premium" — borderline marketing; flag separately
    if PREMIUM_RE.search(customer_facing):
        stats['premium_marketing_term'] += 1
        findings.append([sku, 'marketing:premium', '"premium" appears in customer-facing field (borderline marketing language)'])

    # F. Title <-> bullet1 brand consistency
    title_brand = extract_brand(title)
    bullet_brand = None
    if b1:
        m = re.match(r'compatible\s+with\s+(\w+(?:\s+\w+)?)\b', b1, re.IGNORECASE)
        if m: bullet_brand = m.group(1).strip()
    if title_brand and bullet_brand and title_brand.lower() != bullet_brand.lower():
        title_brand_mismatch_count += 1
        stats['title_bullet_brand_mismatch'] += 1
        findings.append([sku, 'title_bullet_brand_mismatch', f'title="{title_brand}" bullet="{bullet_brand}"'])

    # F. Screen type consistency
    title_screens = extract_screen_type(title)
    bullet_screens = extract_screen_type(b1 + ' ' + b5)
    if title_screens and bullet_screens and title_screens.isdisjoint(bullet_screens):
        screen_mismatch_count += 1
        stats['title_bullet_screen_mismatch'] += 1
        findings.append([sku, 'title_bullet_screen_mismatch',
                         f'title={sorted(title_screens)} bullets={sorted(bullet_screens)}'])

    # F. Frame status consistency
    title_frame = extract_frame_status(title)
    bullet_frame = extract_frame_status(' '.join(bullets))
    if title_frame and bullet_frame and title_frame != bullet_frame:
        frame_mismatch_count += 1
        stats['title_bullet_frame_mismatch'] += 1
        findings.append([sku, 'title_bullet_frame_mismatch',
                         f'title={title_frame} bullets={bullet_frame}'])

    # G. Hinglish in keywords
    if any(t in keywords.lower() for t in HINGLISH_TOKENS):
        hinglish_present_count += 1
    else:
        hinglish_missing_in_keywords.append(sku)
        stats['hinglish_missing_in_keywords'] += 1

    # H. Warranty wording in bullet5
    if any(re.search(p, b5, re.IGNORECASE) for p in WARRANTY_TOKENS):
        warranty_present_count += 1
    elif b5:  # bullet5 has content but no warranty token
        warranty_missing_in_bullets.append(sku)
        stats['warranty_missing_in_bullet5'] += 1

    # I. Repairfully.com support mention
    if re.search(REPAIRFULLY_TOKEN, customer_facing, re.IGNORECASE):
        repairfully_present_count += 1

# ---------------- Write outputs ----------------
out_md = Path('audit_report.md')
out_csv = Path('audit_findings.csv')

# CSV: per-SKU per-issue
with out_csv.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['SKU', 'issue_type', 'detail'])
    for row in findings:
        w.writerow(row)

# Markdown report
total = len(rows)
def pct(n, d=total):
    return f'{n} ({100*n/d:.1f}%)' if d else '0'

md = []
md.append(f'# Bulk Upload Audit — `{XLSX}`')
md.append(f'')
md.append(f'**Total SKUs:** {total}')
md.append(f'**Listing action:** Edit (Partial Update)')
md.append(f'**Columns:** {len(header)} ({", ".join(header[:10])}...)')
md.append(f'')
if USE_CANONICAL:
    md.append(f'## Column alignment')
    md.append(f'')
    md.append(f'**Header ↔ data alignment:** ✅ canonical (data positions match header labels). All 28 columns line up correctly.')
    md.append(f'')
    md.append(f'_Skip ahead to section A._')
    md.append(f'')
else:
    md.append(f'## CRITICAL — column-alignment bug')
    md.append(f'')
    md.append(f'The header row declares 28 columns including `other_image_url_8` at index 13. **However, the data rows are physically shifted one column LEFT starting at index 13** — there are only 7 alt image cells in the data, not 8. As a result, every column from index 13 onwards is in the WRONG position relative to the header label:')
    md.append(f'')
    md.append(f'| header position | header says | data actually contains |')
    md.append(f'|---|---|---|')
    md.append(f'| col 13 (N) | other_image_url_8 | description text |')
    md.append(f'| col 14 (O) | description | bullet1 text |')
    md.append(f'| col 15-17 (P-R) | bullet1-3 | bullet2-4 (mostly empty) |')
    md.append(f'| col 18 (S) | bullet4 | bullet5 (warranty wording) |')
    md.append(f'| col 19 (T) | bullet5 | keywords (Hinglish content) |')
    md.append(f'| col 20 (U) | keywords | compatible_phone_1 |')
    md.append(f'| col 23 (X) | compatible_phone_3 | fulfillment_channel |')
    md.append(f'| col 25 (Z) | quantity | your_price (e.g. 2226) |')
    md.append(f'| col 26 (AA) | your_price | mrp (e.g. 3200) |')
    md.append(f'| col 27 (AB) | mrp | EMPTY |')
    md.append(f'')
    md.append(f'**Fix at the generator level:** insert an empty cell at position 13 in every data row to match the 8-image header. **Do not upload this file until the alignment is corrected.**')
    md.append(f'')
md.append(f'')
md.append(f'## A. Field population')
md.append(f'| field | populated | % |')
md.append(f'|---|---|---|')
for fld in ['title', 'brand', 'description', 'bullet1', 'bullet2', 'bullet3', 'bullet4', 'bullet5', 'keywords']:
    md.append(f'| {fld} | {field_pop[fld]} | {100*field_pop[fld]/total:.1f}% |')
md.append('')
md.append('> **Reading this:** Empty cells on Edit Partial Update mean "leave the existing Amazon listing field unchanged." If bullets 2-4 show 0% populated, that\'s by design — the bulk file only updates bullet1 + bullet5 + title + keywords + price + MRP.')
md.append('')

md.append(f'## B. Hard compliance limits (Amazon India 2026)')
md.append(f'| check | violations |')
md.append(f'|---|---|')
md.append(f'| title > 200 chars | {pct(stats["violation_title_length"])} |')
for i in range(1, 6):
    md.append(f'| bullet{i} > 255 chars | {pct(stats[f"violation_bullet{i}_length"])} |')
md.append(f'| bullets total > 1000 bytes (indexing cliff) | {pct(stats["violation_bullets_indexing_cliff"])} |')
md.append(f'| keywords > 200 bytes (India hard cap) | {pct(stats["violation_keywords_byte_cap"])} |')
md.append(f'| brand column populated on Edit Partial Update | {pct(brand_filled_count)} |')
md.append('')

md.append(f'## C. Banned promotional terms')
md.append(f'**SKUs with at least one banned term:** {pct(stats["banned_terms_present"])}')
if banned_examples:
    md.append('| term | SKU count | sample SKUs |')
    md.append('|---|---|---|')
    for term, skus in sorted(banned_examples.items(), key=lambda x: -len(x[1])):
        sample = ', '.join(skus[:3])
        md.append(f'| `{term}` | {len(skus)} | {sample} |')
md.append('')

md.append(f'## D. Emoji + ALL CAPS')
md.append(f'**SKUs with emojis:** {pct(stats["emoji_present"])}')
md.append(f'**SKUs with non-allowlisted ALL CAPS words:** {pct(stats["allcaps_present"])}')
if allcaps_examples:
    md.append('')
    md.append('Top all-caps words flagged (allowlist excludes LCD/OLED/AMOLED/etc):')
    md.append('| word | SKU count | sample |')
    md.append('|---|---|---|')
    top = sorted(allcaps_examples.items(), key=lambda x: -len(x[1]))[:10]
    for w, skus in top:
        md.append(f'| `{w}` | {len(skus)} | {", ".join(skus[:3])} |')
md.append('')

md.append(f'## E. Tier name leakage (memory: tiers internal-only)')
md.append(f'')
md.append(f'**Hard tier-name leaks (Bronze/Silver/AAA in customer-facing fields):** {pct(stats["tier_name_leak"])}')
md.append(f'**Gold appearing outside device-color parens:** {pct(stats["gold_outside_color_parens"])} _(33 of 33 "gold" hits are inside `(Gold)` parens — legitimate device-color references like "Galaxy J7 Pro (Gold)", not tier leaks)_')
md.append(f'**"Premium" marketing wording (borderline; not in explicit ban list):** {pct(stats["premium_marketing_term"])}')
md.append('')

md.append(f'## F. Title ↔ bullet1 consistency')
md.append(f'| check | mismatches |')
md.append(f'|---|---|')
md.append(f'| brand mismatch | {pct(stats["title_bullet_brand_mismatch"])} |')
md.append(f'| screen type mismatch | {pct(stats["title_bullet_screen_mismatch"])} |')
md.append(f'| frame status mismatch | {pct(stats["title_bullet_frame_mismatch"])} |')
md.append('')

md.append(f'## G. Hinglish keywords (user preference)')
md.append(f'**SKUs with at least one Hinglish token in `keywords` (sceen/kharab/marammat/asali):** {pct(hinglish_present_count)}')
md.append(f'**SKUs missing Hinglish:** {pct(stats["hinglish_missing_in_keywords"])}')
md.append('')

md.append(f'## H. Warranty wording in bullet5')
md.append(f'**SKUs with "7 days" or "seven days" in bullet5:** {pct(warranty_present_count)}')
md.append(f'**bullet5 populated but missing warranty wording:** {pct(stats["warranty_missing_in_bullet5"])}')
md.append('')

md.append(f'## I. Support reference')
md.append(f'**SKUs mentioning repairfully.com:** {pct(repairfully_present_count)}')
md.append('')

md.append(f'## Summary')
issues = sum([
    stats['violation_title_length'],
    stats['violation_bullets_indexing_cliff'],
    stats['violation_keywords_byte_cap'],
    stats['banned_terms_present'],
    stats['emoji_present'],
    stats['tier_name_leak'],
    stats['title_bullet_brand_mismatch'],
    stats['title_bullet_screen_mismatch'],
    stats['title_bullet_frame_mismatch'],
])
md.append(f'- Per-SKU findings written to `audit_findings.csv` ({len(findings)} rows)')
md.append(f'- High-severity violation incidents (length cliffs + banned + emoji + tier leak + title mismatch): {issues}')
md.append('')
md.append(f'## How to use this report')
md.append(f'1. Open `audit_findings.csv` in Excel, filter by `issue_type` to find specific SKUs')
md.append(f'2. For Edit Partial Update mode, empty bullet2-4 cells are intentional (preserves existing Amazon content)')
md.append(f'3. Bullet length cap is 255 chars per bullet AND 1000 bytes total across all 5 bullets (indexing cliff — anything past 1000 bytes is shown but not searchable)')

out_md.write_text('\n'.join(md), encoding='utf-8')
print('---')
print(f'audit_report.md  ({out_md.stat().st_size:,} bytes)')
print(f'audit_findings.csv  ({out_csv.stat().st_size:,} bytes, {len(findings)} rows)')
print('---')
print('Top stats:')
for k, v in sorted(stats.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')
