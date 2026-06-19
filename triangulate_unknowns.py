"""
triangulate_unknowns.py

Classifies unknown records using ONLY primary spatial evidence:

  Source 1 — OSM tags already captured in notes column
             (direct observation at the coordinate)

  Source 2 — Charity Commission registered address match
             (legal document at the postcode)

  Source 3 — Nominatim reverse geocode
             (current OSM state at the coordinate)

Rules:
  - Two sources agree  → apply classification, confidence 0.87
  - One strong source  → apply classification, confidence 0.78
  - Sources disagree   → flag for review, do not classify
  - No sources         → stays unknown

Nothing else is used. No ML, no price, no denomination, no IMD.
"""

import pandas as pd
import requests
import zipfile
import time
import re
import glob
from pathlib import Path

HEADERS = {'User-Agent': 'SacredSpacesResearch/1.0'}

OSM_AMENITY_MAP = {
    'mosque':            'mosque',
    'place_of_worship':  'other_christian',
    'school':            'education',
    'college':           'education',
    'university':        'education',
    'kindergarten':      'education',
    'childcare':         'education',
    'library':           'education',
    'restaurant':        'hospitality',
    'pub':               'hospitality',
    'bar':               'hospitality',
    'cafe':              'hospitality',
    'hotel':             'hospitality',
    'fast_food':         'hospitality',
    'community_centre':  'community',
    'social_facility':   'community',
    'doctors':           'community',
    'healthcare':        'community',
    'arts_centre':       'arts_culture',
    'theatre':           'arts_culture',
    'museum':            'arts_culture',
    'gallery':           'arts_culture',
    'cinema':            'arts_culture',
    'sports_centre':     'sport_leisure',
    'gym':               'sport_leisure',
    'climbing':          'sport_leisure',
}

CHARITY_NAME_SIGNALS = [
    (['mosque','masjid','islamic','muslim'],         'mosque'),
    (['gurdwara','sikh'],                            'south_asian_faith'),
    (['mandir','hindu'],                             'south_asian_faith'),
    (['synagogue','jewish'],                         'other_faith'),
    (['buddhist','meditation','dharma'],             'eastern_philosophy'),
    (['school','college','academy','nursery'],       'education'),
    (['theatre','arts','gallery','museum'],          'arts_culture'),
    (['community','centre','welfare','hub'],         'community'),
    (['pub','bar','inn','restaurant','cafe'],        'hospitality'),
    (['church','chapel','cathedral','christian',
      'ministry','gospel','evangelical'],            'other_christian'),
]


def get_osm_signal(notes):
    """Extract classification from OSM tags already in notes."""
    notes_lower = notes.lower()

    if "religion': 'muslim" in notes_lower or "religion=muslim" in notes_lower:
        return 'mosque'

    for amenity, ct in OSM_AMENITY_MAP.items():
        if f"amenity': '{amenity}" in notes_lower:
            return ct

    if "building': 'apartments" in notes_lower:
        return 'residential'
    if "shop=" in notes_lower and len(notes_lower) > 10:
        return 'commercial'

    return None


def get_charity_signal(notes):
    """Extract classification from Charity Commission entries in notes."""
    notes_lower = notes.lower()

    for pattern in ['charitycommission:', 'cc_activities:', 'oscr:', 'ccni:']:
        if pattern in notes_lower:
            matches = re.findall(
                r'(?:charitycommission|cc_activities|oscr|ccni):[^\(]*\(([^)]+)\)',
                notes_lower
            )
            for name in matches:
                for keywords, ct in CHARITY_NAME_SIGNALS:
                    if any(kw in name for kw in keywords):
                        return ct
    return None


def get_nominatim_signal(lat, lon):
    """Query Nominatim for current building use at coordinates."""
    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={
                'lat': lat, 'lon': lon,
                'format': 'json',
                'extratags': 1,
                'zoom': 18,
            },
            headers=HEADERS,
            timeout=10,
        )
        data = resp.json()
        extra = data.get('extratags', {}) or {}

        religion = str(extra.get('religion','') or '').lower()
        if religion == 'muslim':
            return 'mosque', data.get('name','')

        amenity = str(extra.get('amenity','') or '').lower()
        if amenity in OSM_AMENITY_MAP:
            return OSM_AMENITY_MAP[amenity], data.get('name','')

        building = str(extra.get('building','') or '').lower()
        if building in ('apartments','flats','residential'):
            return 'residential', data.get('name','')
        if building in ('retail','commercial'):
            return 'commercial', data.get('name','')

        osm_type = str(data.get('type','') or '').lower()
        if osm_type in OSM_AMENITY_MAP:
            return OSM_AMENITY_MAP[osm_type], data.get('name','')

    except Exception:
        pass
    return None, None


def main():
    path = next(f for f in sorted(glob.glob(
        'data/output/uk_church_conversions_2*.csv'), reverse=True)
        if 'PUBLIC' not in f)
    df = pd.read_csv(path, low_memory=False)
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')

    unknowns = df[df['conversion_type']=='unknown'].copy()
    print(f"Unknowns to process: {len(unknowns):,}")
    print()
    print("Sources used:")
    print("  1. OSM tags already in notes (direct observation)")
    print("  2. Charity Commission in notes (legal document)")
    print("  3. Nominatim reverse geocode (current OSM state)")
    print()
    print("Rule: 2 sources agree → conf 0.87 | 1 strong source → conf 0.78")
    print("      Sources disagree → flag for review | None → stays unknown")
    print()

    # Checkpoint for resume
    checkpoint = Path('data/output/triangulate_checkpoint.txt')
    start_from = 0
    if checkpoint.exists():
        start_from = int(checkpoint.read_text().strip())
        print(f"Resuming from record {start_from:,}")

    stats = {
        'two_agree': 0,
        'one_strong': 0,
        'disagree': 0,
        'no_signal': 0,
        'mosque_new': 0,
    }

    for i, (idx, row) in enumerate(unknowns.iterrows()):
        if i < start_from:
            continue

        notes = str(row.get('notes','') or '')
        lat = row.get('latitude')
        lon = row.get('longitude')

        # Source 1: OSM tags in notes
        osm_signal = get_osm_signal(notes)

        # Source 2: Charity Commission in notes
        charity_signal = get_charity_signal(notes)

        # Source 3: Nominatim (only if coords available)
        nominatim_signal = None
        nominatim_name = None
        if pd.notna(lat) and pd.notna(lon):
            nominatim_signal, nominatim_name = get_nominatim_signal(lat, lon)
            time.sleep(1)  # Rate limit

        # Triangulate
        signals = {
            k: v for k, v in {
                'osm_notes':    osm_signal,
                'charity':      charity_signal,
                'nominatim':    nominatim_signal,
            }.items() if v is not None
        }

        final_type = None
        confidence = 0.0
        reason = None

        if len(signals) == 0:
            stats['no_signal'] += 1

        elif len(signals) == 1:
            source, ct = list(signals.items())[0]
            # Only apply single source if it's OSM or Charity (strong sources)
            if source in ('osm_notes', 'charity'):
                final_type = ct
                confidence = 0.78
                reason = f'single_strong:{source}'
                stats['one_strong'] += 1
            else:
                # Nominatim alone is not enough
                stats['no_signal'] += 1

        elif len(signals) >= 2:
            # Check if any two agree
            values = list(signals.values())
            sources = list(signals.keys())

            # Find majority vote
            vote_counts = {}
            for ct in values:
                vote_counts[ct] = vote_counts.get(ct, 0) + 1

            winner = max(vote_counts, key=vote_counts.get)
            winner_count = vote_counts[winner]

            if winner_count >= 2:
                final_type = winner
                confidence = 0.87
                reason = f'two_agree:{",".join(s for s,v in signals.items() if v==winner)}'
                stats['two_agree'] += 1
            else:
                # All three disagree — flag, don't classify
                existing = str(df.at[idx,'notes'] or '')
                df.at[idx,'notes'] = (
                    existing +
                    f" | REVIEW_CONFLICT:osm={osm_signal}"
                    f",charity={charity_signal}"
                    f",nominatim={nominatim_signal}"
                )
                stats['disagree'] += 1
                final_type = None

        # Apply classification
        if final_type and final_type != 'unknown':
            df.at[idx,'conversion_type'] = final_type
            df.at[idx,'conversion_subtype'] = 'spatially_triangulated'
            df.at[idx,'confidence_score'] = confidence

            if final_type == 'mosque':
                stats['mosque_new'] += 1

            # Add current name from Nominatim if available
            if nominatim_name and pd.isna(df.at[idx,'current_name']):
                df.at[idx,'current_name'] = nominatim_name

            existing = str(df.at[idx,'notes'] or '')
            df.at[idx,'notes'] = (
                existing +
                f" | TRIANGULATED:{final_type}"
                f"(conf:{confidence},{reason})"
            )

        # Save every 200 records
        if (i + 1) % 200 == 0:
            df.to_csv(path, index=False)
            checkpoint.write_text(str(i + 1))
            print(
                f"[{i+1:,}/{len(unknowns):,}] "
                f"two_agree:{stats['two_agree']} "
                f"one_strong:{stats['one_strong']} "
                f"disagree:{stats['disagree']} "
                f"no_signal:{stats['no_signal']} "
                f"new_mosques:{stats['mosque_new']}"
            )

    # Final save
    df.to_csv(path, index=False)
    checkpoint.write_text(str(len(unknowns)))

    print()
    print("="*55)
    print("TRIANGULATION COMPLETE")
    print("="*55)
    print(f"Two sources agreed:    {stats['two_agree']:,}")
    print(f"One strong source:     {stats['one_strong']:,}")
    print(f"Sources disagreed:     {stats['disagree']:,}")
    print(f"No signal found:       {stats['no_signal']:,}")
    print(f"New mosques found:     {stats['mosque_new']}")
    print()
    print(f"Unknown remaining: {(df['conversion_type']=='unknown').sum():,}")
    print()
    print("Conversion type breakdown:")
    print(df['conversion_type'].value_counts().head(15).to_string())


if __name__ == '__main__':
    main()