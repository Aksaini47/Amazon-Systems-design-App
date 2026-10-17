#!/usr/bin/env python3
"""
Match Amazon Ads ad-groups against physical inventory stock list.
Identifies:
- Stock models with no matching ad-group (NO_ADGROUP)
- Stock models with paused ad-groups (COVERED_PAUSED)
- Stock models with enabled ad-groups (COVERED_ENABLED)
"""

import re
import csv
from pathlib import Path
from difflib import SequenceMatcher

# Physical inventory models (extracted from master inventory file)
STOCK_MODELS = {
    'REALME': [
        'Realme C67', 'Realme 7i', 'Realme 9', 'Realme C33', 'Realme 11 Pro',
        'Realme 9i', 'Realme C21', 'Realme C30', 'Realme C53', 'Realme 8i',
        'Realme 13 Pro', 'Realme 3 Pro', 'Realme 7 Pro'
    ],
    'VIVO': [
        'Vivo Y33s', 'Vivo Y22', 'Vivo T1', 'Vivo T2x', 'Vivo X70 Pro Plus',
        'Vivo V17', 'Vivo V15', 'Vivo Y71'
    ],
    'OPPO': [
        'Oppo F17 Pro', 'Oppo A53', 'Oppo A57', 'Oppo F19', 'Oppo A54',
        'Oppo F27', 'Oppo Reno 10 Pro Plus', 'Oppo Reno 13 Pro Plus',
        'Oppo F5'
    ],
    'ONEPLUS': [
        'OnePlus Nord', 'OnePlus 8', 'OnePlus 10 Pro', 'OnePlus 8 Pro',
        'OnePlus 9RT', 'OnePlus 9', 'OnePlus 7'
    ],
    'SAMSUNG': [
        'Galaxy J7 Next', 'Galaxy A73', 'Galaxy S21 FE', 'Galaxy A23',
        'Galaxy A32', 'Galaxy J7', 'Galaxy A30s', 'Galaxy J7 Max', 'Galaxy S20 FE'
    ],
    'APPLE': [
        'iPhone 13 Pro Max', 'iPhone 13', 'iPhone 13 Pro', 'iPhone 8',
        'iPhone 11', 'iPhone 8 Plus', 'iPhone XS', 'iPhone 14 Pro Max'
    ],
    'XIAOMI': [
        'Mi 11X', 'Mi A3', 'Redmi Note 5', 'Redmi 4A', 'Redmi Note 10T',
        'Redmi 12', 'Redmi 12 5G', 'Redmi Note 13 Pro Plus', 'Redmi K20',
        'Redmi 10 Power', 'Redmi Note 6 Pro', 'Redmi Note 7', 'Redmi 6 Pro',
        'Poco X3', 'Poco M4'
    ],
    'MIX': [
        'Nothing Phone 1', 'Infinix Note 10', 'Infinix Hot 9', 'Infinix Note 11S',
        'Honor 7X', 'Honor 8C', 'Honor X9B', 'Nokia G10', 'Nokia G20',
        'Nokia G21', 'Nokia C3', 'Moto G9', 'Moto G40 Fusion',
        'Moto Edge 50 Fusion', 'Moto G34', 'Asus Zenfone Max M2', 'Asus ROG Phone 2'
    ]
}

def normalize_name(name):
    """Normalize brand name for matching."""
    name = name.strip()
    # Handle special brand shorthand
    if name.startswith('1+'):
        name = 'OnePlus' + name[2:]
    return name.lower()

def fuzzy_match(stock_model, ad_group_name, threshold=0.7):
    """Check if stock model matches ad-group name with fuzzy matching."""
    stock_norm = normalize_name(stock_model)
    adgroup_norm = ad_group_name.lower()

    # Exact substring match
    if stock_norm in adgroup_norm or adgroup_norm in stock_norm:
        return True

    # Fuzzy match
    ratio = SequenceMatcher(None, stock_norm, adgroup_norm).ratio()
    if ratio >= threshold:
        return True

    # Handle variations like "4G/5G" - match base model
    base_stock = re.sub(r'\s*(4G|5G|OLED|Incell|CareOG|With Frame|White|Gold|Black)\b.*', '', stock_norm)
    base_adgroup = re.sub(r'\s*(4G|5G|OLED|Incell|CareOG|With Frame|White|Gold|Black)\b.*', '', adgroup_norm)

    if base_stock and base_adgroup:
        if base_stock in base_adgroup or base_adgroup in base_stock:
            return True
        ratio = SequenceMatcher(None, base_stock, base_adgroup).ratio()
        if ratio >= threshold:
            return True

    return False

def analyze_coverage(adgroups_data, stock_models):
    """
    Analyze which stock models are covered by ad-groups.
    Returns: covered_enabled, covered_paused, no_adgroup
    """
    covered_enabled = {}
    covered_paused = {}
    no_adgroup = {}

    # Flatten all stock models
    all_stock = {}
    for brand, models in stock_models.items():
        for model in models:
            all_stock[model] = brand

    # Match each stock model
    for model, brand in all_stock.items():
        matched = False
        for adgroup_name, status in adgroups_data.items():
            if fuzzy_match(model, adgroup_name):
                matched = True
                entry = {'brand': brand, 'model': model, 'adgroup': adgroup_name}
                if status == 'ENABLED':
                    covered_enabled[model] = entry
                else:
                    covered_paused[model] = entry
                break

        if not matched:
            no_adgroup[model] = {'brand': brand, 'model': model}

    return covered_enabled, covered_paused, no_adgroup

def main():
    """Load ad-groups and analyze coverage."""
    # Try to read ad-groups from temp list file
    adgroups_file = Path('C:\\Projects\\Amazon Systems Design\\catalog-builder\\amazon-reports\\adgroups_temp_list.txt')

    if not adgroups_file.exists():
        print(f"Error: Ad-groups list file not found at {adgroups_file}")
        print("Waiting for agent to complete collection...")
        return None

    # Load ad-groups
    adgroups_data = {}
    with open(adgroups_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Format: "AdGroupName,STATUS"
                parts = line.split(',', 1)
                if len(parts) == 2:
                    adgroups_data[parts[0]] = parts[1]
                else:
                    # Assume ENABLED if status not specified
                    adgroups_data[line] = 'ENABLED'

    print(f"Loaded {len(adgroups_data)} ad-groups")

    # Analyze coverage
    covered_en, covered_ps, no_adg = analyze_coverage(adgroups_data, STOCK_MODELS)

    print(f"\nCoverage Summary:")
    print(f"  COVERED_ENABLED: {len(covered_en)}")
    print(f"  COVERED_PAUSED: {len(covered_ps)}")
    print(f"  NO_ADGROUP: {len(no_adg)}")

    # Print no_adgroup models
    if no_adg:
        print(f"\nStock models with NO ad-group:")
        for model, info in sorted(no_adg.items()):
            print(f"  {info['brand']:15} {model}")

    # Print paused ad-groups
    if covered_ps:
        print(f"\nStock models with PAUSED ad-group:")
        for model, info in sorted(covered_ps.items()):
            print(f"  {info['brand']:15} {model:40} -> {info['adgroup']}")

    return covered_en, covered_ps, no_adg

if __name__ == '__main__':
    main()
