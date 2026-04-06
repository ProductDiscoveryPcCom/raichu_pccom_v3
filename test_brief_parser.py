# -*- coding: utf-8 -*-
import sys
import os

# Add project root to path
sys.path.append(r'c:\Users\maximo.sanchez\OneDrive - PcComponentes\Escritorio\claude projects\raichu_pccom_v3')

from utils.brief_parser import parse_cannibalization_brief

brief_path = r'C:\Users\maximo.sanchez\Downloads\brief_mejores-smart-tv-de-55-pulgadas (3).md'

if not os.path.exists(brief_path):
    print(f"Error: {brief_path} not found.")
    sys.exit(1)

with open(brief_path, 'r', encoding='utf-8') as f:
    content = f.read()

data = parse_cannibalization_brief(content)

print(f"Keyword: {data.get('keyword')}")
print(f"URL: {data.get('url')}")
print(f"Action: {data.get('action')}")
print(f"Keywords Found: {len(data['keywords'])}")
print(f"Headings Found: {len(data['headings'])}")
print(f"Instructions Add: {len(data['instructions']['add'])}")
print(f"Instructions Maintain: {len(data['instructions']['maintain'])}")
print(f"Instructions Remove: {len(data['instructions']['remove'])}")
print(f"Internal Links Found: {len(data['internal_links'])}")

import json
print("\nJSON Output (first 500 chars):")
print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
