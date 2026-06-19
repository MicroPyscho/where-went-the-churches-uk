"""
overpass_classify_unknowns.py

Classifies unknown records using Overpass API with stepped radius search.
Mirrors the stepped radius approach used for postcode lookup.

Radii: 50m → 100m → 200m → 500m
Stops at first radius that returns a meaningful tagged building.

For each unknown record:
  1. Query Overpass at 50m radius for any tagged building/amenity
  2. If nothing found, expand to 100m
  3. Continue to 200m, then 500m
  4. Extract ALL meaningful tags — amenity, religion, building:use,
     name, old_name, disused:amenity, operator, denomination,
     opening_hours, website
  5. Classify based on tag hierarchy
  6. Record the radius used and all tags found for audit trail

Confidence assigned by radius:
  50m  → 0.88 (almost certainly the exact building)
  100m → 0.82 (same building/curtilage)
  200m → 0.75 (neighbouring building possible)
  500m → 0.65 (street block level)

Two-source rule still applies:
  If Overpass result agrees with existing OSM notes or Charity Commission
  in notes → confidence boosted to 0.90

Run: python overpass_classify_unknowns.py
"""

import pandas as pd
import requests
import time
import re
import glob
from pathlib import Path

HEADERS = {'User-Agent': 'SacredSpacesResearch/1.0 (academic research)'}
OVERPASS_URL = 'https://overpass-api.de/api/interpreter'

RADII = [50, 100, 200, 500]

CONFIDENCE_BY_RADIUS = {
    50:  0.88,
    100: 0.82,
    200: 0.75,
    500: 0.65,
}

# Tag priority hierarchy — checked in order
# First match wins
TAG_CLASSIFICATION = [
    # ── RELIGION ──────────────────────────────────────────────────────────
    ('religion',        'muslim',               'mosque',              'mosque_general'),
    ('religion',        'islamic',              'mosque',              'mosque_general'),
    ('amenity',         'mosque',               'mosque',              'mosque_general'),
    ('building',        'mosque',               'mosque',              'mosque_general'),
    ('religion',        'sikh',                 'south_asian_faith',   'sikh_gurdwara'),
    ('amenity',         'gurdwara',             'south_asian_faith',   'sikh_gurdwara'),
    ('religion',        'hindu',                'south_asian_faith',   'hindu_mandir'),
    ('amenity',         'temple',               'south_asian_faith',   'hindu_mandir'),
    ('religion',        'jewish',               'other_faith',         'jewish_synagogue'),
    ('amenity',         'synagogue',            'other_faith',         'jewish_synagogue'),
    ('religion',        'buddhist',             'eastern_philosophy',  'buddhist_centre'),
    ('religion',        'christian',            'other_christian',     'place_of_worship'),
    ('amenity',         'place_of_worship',     'other_christian',     'place_of_worship'),
    ('amenity',         'church',               'other_christian',     'place_of_worship'),
    ('building',        'church',               'other_christian',     'church_building'),
    ('building',        'chapel',               'other_christian',     'chapel_building'),
    ('building',        'cathedral',            'other_christian',     'cathedral'),
    ('building',        'place_of_worship',     'other_christian',     'place_of_worship'),
    # ── EDUCATION ─────────────────────────────────────────────────────────
    ('amenity',         'school',               'education',           'school'),
    ('amenity',         'college',              'education',           'college'),
    ('amenity',         'university',           'education',           'university'),
    ('amenity',         'kindergarten',         'education',           'nursery'),
    ('amenity',         'childcare',            'education',           'nursery'),
    ('amenity',         'library',              'education',           'library'),
    ('building',        'school',               'education',           'school'),
    ('building',        'university',           'education',           'university'),
    # ── HOSPITALITY ───────────────────────────────────────────────────────
    ('amenity',         'restaurant',           'hospitality',         'restaurant'),
    ('amenity',         'pub',                  'hospitality',         'pub'),
    ('amenity',         'bar',                  'hospitality',         'bar'),
    ('amenity',         'cafe',                 'hospitality',         'cafe'),
    ('amenity',         'fast_food',            'hospitality',         'restaurant'),
    ('amenity',         'food_court',           'hospitality',         'restaurant'),
    ('tourism',         'hotel',                'hospitality',         'hotel'),
    ('tourism',         'hostel',               'hospitality',         'hostel'),
    ('tourism',         'guest_house',          'hospitality',         'hotel'),
    ('amenity',         'nightclub',            'hospitality',         'nightclub'),
    # ── COMMUNITY ─────────────────────────────────────────────────────────
    ('amenity',         'community_centre',     'community',           'community_centre'),
    ('amenity',         'social_facility',      'community',           'community_centre'),
    ('amenity',         'doctors',              'community',           'health_centre'),
    ('amenity',         'pharmacy',             'community',           'health_centre'),
    ('amenity',         'hospital',             'community',           'health_centre'),
    ('amenity',         'clinic',               'community',           'health_centre'),
    ('amenity',         'food_bank',            'community',           'charity_hub'),
    ('building',        'community_centre',     'community',           'community_centre'),
    ('building',        'civic',                'community',           'civic'),
    # ── ARTS/CULTURE ──────────────────────────────────────────────────────
    ('amenity',         'arts_centre',          'arts_culture',        'arts_centre'),
    ('amenity',         'theatre',              'arts_culture',        'theatre'),
    ('amenity',         'cinema',               'arts_culture',        'cinema'),
    ('tourism',         'museum',               'arts_culture',        'museum'),
    ('tourism',         'gallery',              'arts_culture',        'gallery'),
    ('tourism',         'artwork',              'arts_culture',        'arts_centre'),
    ('building',        'arts_centre',          'arts_culture',        'arts_centre'),
    ('building',        'theatre',              'arts_culture',        'theatre'),
    # ── SPORT/LEISURE ─────────────────────────────────────────────────────
    ('leisure',         'sports_centre',        'sport_leisure',       'sport_leisure_general'),
    ('leisure',         'fitness_centre',       'sport_leisure',       'gym_fitness'),
    ('leisure',         'gym',                  'sport_leisure',       'gym_fitness'),
    ('leisure',         'climbing',             'sport_leisure',       'climbing_wall'),
    ('leisure',         'dance',                'sport_leisure',       'dance_studio'),
    ('building',        'sports_centre',        'sport_leisure',       'sport_leisure_general'),
    # ── COMMERCIAL ────────────────────────────────────────────────────────
    ('office',          'yes',                  'commercial',          'office'),
    ('office',          'company',              'commercial',          'office'),
    ('office',          'charity',              'community',           'charity_hub'),
    ('amenity',         'office',               'commercial',          'office'),
    ('shop',            'supermarket',          'commercial',          'supermarket'),
    ('shop',            'convenience',          'commercial',          'retail_shop'),
    ('shop',            'yes',                  'commercial',          'retail_shop'),
    ('building',        'retail',               'commercial',          'retail_shop'),
    ('building',        'commercial',           'commercial',          'office'),
    ('building',        'office',               'commercial',          'office'),
    ('building',        'warehouse',            'commercial',          'warehouse'),
    ('building',        'industrial',           'commercial',          'industrial'),
    # ── RESIDENTIAL ───────────────────────────────────────────────────────
    ('building',        'apartments',           'residential',         'converted_flats'),
    ('building',        'residential',          'residential',         'converted_flats'),
    ('building',        'house',                'residential',         'single_dwelling'),
    ('building:use',    'residential',          'residential',         'converted_flats'),
    ('residential',     'yes',                  'residential',         'converted_flats'),
    # ── DEMOLISHED/DISUSED ────────────────────────────────────────────────
    ('disused:amenity', 'place_of_worship',     'demolished',          'disused_place_of_worship'),
    ('disused:amenity', 'church',               'demolished',          'disused_church'),
    ('historic',        'ruins',                'demolished',          'ruins'),
    ('ruins',           'yes',                  'demolished',          'ruins'),
    ('demolished',      'yes',                  'demolished',          'demolished'),
]

# Tags that indicate active use — boosts confidence
ACTIVE_USE_SIGNALS = ['opening_hours', 'website', 'phone', 'operator', 'contact:website']

# Tags that indicate conversion has happened
CONVERSION_SIGNALS = ['old_name', 'disused:amenity', 'disused:religion',
                      'was:amenity', 'was:religion', 'demolished:amenity']

# Already confirmed from prior sources
STRONG_PRIOR_SIGNALS = ['charitycommission:', 'oscr:', 'ccni:', 'confirmed_mosque',
                        'reclassified_mosque']


def build_overpass_query(lat, lon, radius):
    """Build Overpass QL query for all meaningful tags within radius."""
    return f"""
[out:json][timeout:15];
(
  node(around:{radius},{lat},{lon})
    [~"^(amenity|religion|building|building:use|leisure|
         shop|office|tourism|historic|disused:amenity|
         disused:religion|residential)$"~"."];
  way(around:{radius},{lat},{lon})
    [~"^(amenity|religion|building|building:use|leisure|
         shop|office|tourism|historic|disused:amenity|
         disused:religion|residential)$"~"."];
  relation(around:{radius},{lat},{lon})
    [~"^(amenity|religion|building|building:use|leisure|
         shop|office|tourism|historic|disused:amenity|
         disused:religion|residential)$"~"."];
);
out tags;
"""


def classify_tags(tags):
    """
    Apply tag hierarchy to classify a building.
    Returns (conversion_type, conversion_subtype, confidence_modifier)
    """
    tags_lower = {k.lower(): str(v).lower() for k, v in tags.items()}

    for tag_key, tag_value, ct, cs in TAG_CLASSIFICATION:
        actual_value = tags_lower.get(tag_key, '')
        if tag_value == 'yes':
            if actual_value and actual_value not in ('no', ''):
                return ct, cs, 0.0
        elif tag_value in actual_value or actual_value == tag_value:
            return ct, cs, 0.0

    return None, None, 0.0


def extract_key_tags(tags):
    """Extract all meaningful tags for audit trail."""
    key_tags = {}
    for k in ['amenity','religion','building','building:use','leisure',
              'shop','office','tourism','historic','disused:amenity',
              'name','old_name','operator','denomination','opening_hours',
              'website','addr:housenumber','addr:street']:
        if k in tags and tags[k]:
            key_tags[k] = tags[k]
    return key_tags


def query_overpass(lat, lon, radius):
    """Query Overpass API and return classified result."""
    query = build_overpass_query(lat, lon, radius)
    try:
        resp = requests.post(
            OVERPASS_URL,
            data=query,
            headers=HEADERS,
            timeout=20,
        )
        if resp.status_code != 200:
            return None, None, None, {}

        elements = resp.json().get('elements', [])
        if not elements:
            return None, None, None, {}

        # Try each element — prioritise ones with more tags
        elements_sorted = sorted(elements, key=lambda e: len(e.get('tags',{})), reverse=True)

        for element in elements_sorted:
            tags = element.get('tags', {})
            if not tags:
                continue

            ct, cs, mod = classify_tags(tags)
            if ct:
                key_tags = extract_key_tags(tags)
                name = tags.get('name', '')
                return ct, cs, name, key_tags

        return None, None, None, {}

    except Exception:
        return None, None, None, {}


def get_existing_signal(notes):
    """Extract classification from existing notes (Charity Commission/OSM)."""
    notes_lower = notes.lower()

    # Charity Commission
    for pattern in ['charitycommission:', 'cc_activities:', 'oscr:', 'ccni:']:
        if pattern in notes_lower:
            matches = re.findall(
                r'(?:charitycommission|cc_activities|oscr|ccni):[^\(]*\(([^)]+)\)',
                notes_lower
            )
            for name in matches:
                if any(kw in name for kw in ['mosque','masjid','islamic','muslim']):
                    return 'mosque'
                if any(kw in name for kw in ['school','college','academy','nursery']):
                    return 'education'
                if any(kw in name for kw in ['community','centre','welfare']):
                    return 'community'
                if any(kw in name for kw in ['church','chapel','christian','ministry']):
                    return 'other_christian'
                if any(kw in name for kw in ['theatre','arts','gallery','museum']):
                    return 'arts_culture'

    # OSM religion tag already in notes
    if "religion': 'muslim" in notes_lower:
        return 'mosque'

    return None


def main():
    path = next(f for f in sorted(glob.glob(
        'data/output/uk_church_conversions_2*.csv'), reverse=True)
        if 'PUBLIC' not in f)
    df = pd.read_csv(path, low_memory=False)
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')

    unknowns = df[df['conversion_type']=='unknown'].copy()
    total = len(unknowns)

    print(f"Unknown records to process: {total:,}")
    print(f"Radii: {RADII}m (stepped, stops at first result)")
    print(f"Estimated time: {total*1.5/3600:.1f} hours")
    print()
    print("Confidence by radius:")
    for r, c in CONFIDENCE_BY_RADIUS.items():
        print(f"  {r}m → {c}")
    print()
    print("Two-source boost: if Overpass agrees with Charity/OSM notes → +0.05")
    print()

    # Resume from checkpoint
    checkpoint = Path('data/output/overpass_checkpoint.txt')
    start_from = 0
    if checkpoint.exists():
        try:
            start_from = int(checkpoint.read_text().strip())
            print(f"Resuming from record {start_from:,}")
        except ValueError:
            pass

    stats = {
        'resolved_50m':   0,
        'resolved_100m':  0,
        'resolved_200m':  0,
        'resolved_500m':  0,
        'two_source':     0,
        'no_result':      0,
        'mosque_new':     0,
        'errors':         0,
    }

    # Track radius distribution
    type_counts = {}

    for i, (idx, row) in enumerate(unknowns.iterrows()):
        if i < start_from:
            continue

        lat = row.get('latitude')
        lon = row.get('longitude')
        notes = str(row.get('notes','') or '')

        if pd.isna(lat) or pd.isna(lon):
            stats['no_result'] += 1
            continue

        # Get existing signal from notes (Charity Commission / prior OSM)
        prior_signal = get_existing_signal(notes)

        # Stepped radius Overpass query
        final_ct = None
        final_cs = None
        final_name = None
        final_radius = None
        final_tags = {}

        for radius in RADII:
            ct, cs, name, tags = query_overpass(lat, lon, radius)
            time.sleep(0.2)  # Overpass rate limit

            if ct:
                # Skip generic church/chapel building tags at larger radii
                # unless we have corroborating evidence
                if radius >= 200 and ct == 'other_christian' and \
                   cs in ('church_building', 'chapel_building') and \
                   not prior_signal:
                    continue  # Too vague at 200m+ without corroboration

                final_ct = ct
                final_cs = cs
                final_name = name
                final_radius = radius
                final_tags = tags
                break

        if not final_ct:
            stats['no_result'] += 1
            continue

        # Calculate confidence
        base_confidence = CONFIDENCE_BY_RADIUS[final_radius]

        # Two-source boost: if Overpass agrees with prior signal
        two_source = False
        if prior_signal and prior_signal == final_ct:
            base_confidence = min(0.95, base_confidence + 0.05)
            two_source = True
            stats['two_source'] += 1

        # Active use boost: if building has opening hours / website
        active_signals = [k for k in ACTIVE_USE_SIGNALS if k in final_tags]
        if active_signals:
            base_confidence = min(0.95, base_confidence + 0.02)

        # Apply classification
        df.at[idx, 'conversion_type'] = final_ct
        df.at[idx, 'conversion_subtype'] = final_cs
        df.at[idx, 'confidence_score'] = round(base_confidence, 3)

        # Add current name if not already set
        if final_name and pd.isna(df.at[idx, 'current_name']):
            df.at[idx, 'current_name'] = final_name

        # Build audit note
        tag_summary = ', '.join(f"{k}={v}" for k, v in list(final_tags.items())[:5])
        two_src_note = '_two_source' if two_source else ''
        existing = str(df.at[idx, 'notes'] or '')
        df.at[idx, 'notes'] = (
            existing +
            f" | Overpass:{final_ct}(r={final_radius}m"
            f",conf={base_confidence:.2f}{two_src_note})"
            f" tags:[{tag_summary[:80]}]"
        )

        # Update stats
        stats[f'resolved_{final_radius}m'] += 1
        type_counts[final_ct] = type_counts.get(final_ct, 0) + 1
        if final_ct == 'mosque':
            stats['mosque_new'] += 1

        # Save every 200 records
        if (i + 1) % 200 == 0:
            df.to_csv(path, index=False)
            checkpoint.write_text(str(i + 1))
            resolved_total = sum(stats[f'resolved_{r}m'] for r in RADII)
            print(
                f"[{i+1:,}/{total:,}] "
                f"resolved:{resolved_total:,} "
                f"(50m:{stats['resolved_50m']} "
                f"100m:{stats['resolved_100m']} "
                f"200m:{stats['resolved_200m']} "
                f"500m:{stats['resolved_500m']}) "
                f"two_src:{stats['two_source']} "
                f"mosques:{stats['mosque_new']} "
                f"no_result:{stats['no_result']}"
            )

    # Final save
    df.to_csv(path, index=False)
    checkpoint.write_text(str(total))

    resolved_total = sum(stats[f'resolved_{r}m'] for r in RADII)

    print()
    print("="*60)
    print("OVERPASS CLASSIFICATION COMPLETE")
    print("="*60)
    print(f"Total processed:       {total:,}")
    print(f"Total resolved:        {resolved_total:,} ({resolved_total/total*100:.1f}%)")
    print(f"  At 50m:              {stats['resolved_50m']:,}")
    print(f"  At 100m:             {stats['resolved_100m']:,}")
    print(f"  At 200m:             {stats['resolved_200m']:,}")
    print(f"  At 500m:             {stats['resolved_500m']:,}")
    print(f"Two-source confirmed:  {stats['two_source']:,}")
    print(f"New mosques found:     {stats['mosque_new']}")
    print(f"No result found:       {stats['no_result']:,}")
    print()
    print("Resolved by type:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:<30} {c:>5,}")
    print()
    print("Final conversion breakdown:")
    print(df['conversion_type'].value_counts().head(15).to_string())


if __name__ == '__main__':
    main()