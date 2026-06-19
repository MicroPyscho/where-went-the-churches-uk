"""
nominatim_overnight.py
Reverse geocodes all unknown records using Nominatim (OSM).
Queries by coordinate, extracts current building use from OSM tags.
Rate limit: 1 req/sec (Nominatim policy).
Saves every 200 records — safe to interrupt and resume.
Run: python nominatim_overnight.py
"""
import pandas as pd, requests, time, re, glob, json
from pathlib import Path

path = next(f for f in sorted(glob.glob(
    'data/output/uk_church_conversions_2*.csv'), reverse=True)
    if 'PUBLIC' not in f)
df = pd.read_csv(path, low_memory=False)
df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')

# Target all unknowns with coordinates
targets = df[
    (df['conversion_type'] == 'unknown') &
    df['latitude'].notna() &
    df['longitude'].notna()
].copy()

print(f"Targets: {len(targets):,}")
print(f"Estimated time: {len(targets)//3600:.1f} hours at 1 req/sec")
print()

HEADERS = {'User-Agent': 'SacredSpacesResearch/1.0 (academic research)'}

OSM_TYPE_MAP = {
    # Religion
    'mosque':               ('mosque',           'mosque_general'),
    'place_of_worship':     ('other_christian',  'place_of_worship'),
    'church':               ('other_christian',  'place_of_worship'),
    # Education
    'school':               ('education',        'school'),
    'college':              ('education',        'college'),
    'university':           ('education',        'university'),
    'kindergarten':         ('education',        'nursery'),
    'childcare':            ('education',        'nursery'),
    'library':              ('education',        'library'),
    # Hospitality
    'restaurant':           ('hospitality',      'restaurant'),
    'pub':                  ('hospitality',      'pub'),
    'bar':                  ('hospitality',      'bar'),
    'cafe':                 ('hospitality',      'cafe'),
    'hotel':                ('hospitality',      'hotel'),
    'hostel':               ('hospitality',      'hostel'),
    'fast_food':            ('hospitality',      'restaurant'),
    # Community
    'community_centre':     ('community',        'community_centre'),
    'social_facility':      ('community',        'community_centre'),
    'healthcare':           ('community',        'health_centre'),
    'doctors':              ('community',        'health_centre'),
    'pharmacy':             ('community',        'health_centre'),
    'food_bank':            ('community',        'charity_hub'),
    # Arts
    'arts_centre':          ('arts_culture',     'arts_centre'),
    'theatre':              ('arts_culture',     'theatre'),
    'museum':               ('arts_culture',     'museum'),
    'gallery':              ('arts_culture',     'gallery'),
    'cinema':               ('arts_culture',     'cinema'),
    'nightclub':            ('hospitality',      'nightclub'),
    # Sport
    'sports_centre':        ('sport_leisure',    'sport_leisure_general'),
    'gym':                  ('sport_leisure',    'gym_fitness'),
    'climbing':             ('sport_leisure',    'climbing_wall'),
    # Commercial
    'office':               ('commercial',       'office'),
    'shop':                 ('commercial',       'retail_shop'),
    'supermarket':          ('commercial',       'supermarket'),
    'coworking':            ('commercial',       'office'),
    # Residential
    'apartments':           ('residential',      'converted_flats'),
    'residential':          ('residential',      'converted_flats'),
    'house':                ('residential',      'single_dwelling'),
    'flats':                ('residential',      'converted_flats'),
    # Demolished
    'ruins':                ('demolished',       'ruins'),
    'demolished':           ('demolished',       'demolished'),
    # Faith
    'gurdwara':             ('south_asian_faith','sikh_gurdwara'),
    'temple':               ('south_asian_faith','hindu_mandir'),
    'synagogue':            ('other_faith',      'jewish_synagogue'),
    'buddhist':             ('eastern_philosophy','buddhist_centre'),
}

def classify_from_tags(data):
    """Extract conversion type from Nominatim response."""
    osm_type  = str(data.get('type','') or '').lower()
    osm_class = str(data.get('class','') or '').lower()
    extra     = data.get('extratags', {}) or {}
    amenity   = str(extra.get('amenity','') or '').lower()
    religion  = str(extra.get('religion','') or '').lower()
    building  = str(extra.get('building','') or '').lower()
    leisure   = str(extra.get('leisure','') or '').lower()
    shop      = str(extra.get('shop','') or '').lower()
    office    = str(extra.get('office','') or '').lower()
    tourism   = str(extra.get('tourism','') or '').lower()
    disused   = str(extra.get('disused:amenity','') or '').lower()
    name      = (data.get('name','') or
                 extra.get('name','') or
                 extra.get('official_name','') or '')

    # Special: religion=muslim → mosque
    if religion == 'muslim':
        return 'mosque', 'mosque_general', name

    # Check all tag fields
    for tag in [amenity, osm_type, leisure, shop, tourism, building, office]:
        if tag in OSM_TYPE_MAP:
            ct, cs = OSM_TYPE_MAP[tag]
            return ct, cs, name
        for key, val in OSM_TYPE_MAP.items():
            if key in tag and tag:
                return val[0], val[1], name

    # Disused
    if disused or 'disused' in osm_class:
        return 'demolished', 'disused', name

    return None, None, name

# Resume from checkpoint if exists
checkpoint = Path('data/output/nominatim_checkpoint.txt')
start_from = 0
if checkpoint.exists():
    start_from = int(checkpoint.read_text().strip())
    print(f"Resuming from record {start_from:,}")

resolved = 0
mosque_found = 0
errors = 0

for i, (idx, row) in enumerate(targets.iterrows()):
    if i < start_from:
        continue

    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={
                'lat': row['latitude'],
                'lon': row['longitude'],
                'format': 'json',
                'addressdetails': 1,
                'extratags': 1,
                'zoom': 18,
            },
            headers=HEADERS,
            timeout=10,
        )
        data = resp.json()
        ct, cs, name = classify_from_tags(data)

        if ct:
            df.at[idx, 'conversion_type'] = ct
            df.at[idx, 'conversion_subtype'] = cs
            df.at[idx, 'confidence_score'] = 0.75
            resolved += 1
            if ct == 'mosque':
                mosque_found += 1

        if name and pd.isna(df.at[idx, 'current_name']):
            df.at[idx, 'current_name'] = name

        existing = str(df.at[idx, 'notes'] or '')
        df.at[idx, 'notes'] = (
            existing +
            f" | Nominatim:{ct or 'unresolved'}"
        )

    except Exception:
        errors += 1

    # Save every 200 records
    if (i + 1) % 200 == 0:
        df.to_csv(path, index=False)
        checkpoint.write_text(str(i + 1))
        print(f"[{i+1:,}/{len(targets):,}] Resolved: {resolved:,} | "
              f"Mosques found: {mosque_found} | Errors: {errors}")

    time.sleep(1)

# Final save
df.to_csv(path, index=False)
checkpoint.write_text(str(len(targets)))

print()
print("="*55)
print("NOMINATIM OVERNIGHT RUN COMPLETE")
print("="*55)
print(f"Resolved: {resolved:,}")
print(f"New mosques found: {mosque_found}")
print(f"Errors: {errors}")
print()
print("Conversion type breakdown:")
print(df['conversion_type'].value_counts().head(15).to_string())
