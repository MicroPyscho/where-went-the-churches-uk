"""
enrich_all_columns.py

Multi-pass enrichment targeting 90%+ column coverage.
Five passes — all instant (no API calls), purely from existing data:

  Pass 1 — City from local_authority/ward columns
  Pass 2 — Former denomination from church_name/address keywords
  Pass 3 — Conversion type from Companies House SIC codes
  Pass 4 — Conversion type from notes field NLP
  Pass 5 — Current name from notes field pattern extraction

Each pass is strictly additive — only fills null/unknown, never overwrites.
Touches ONLY the target column for each pass.

Run: python enrich_all_columns.py
"""

import re
import glob
import logging
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DENOMINATION_PATTERNS = [
    (r'\b(methodist|wesleyan|primitive methodist|united methodist)\b', 'methodist'),
    (r'\b(baptist)\b', 'baptist'),
    (r'\b(presbyterian)\b', 'presbyterian'),
    (r'\b(congregational)\b', 'congregational'),
    (r'\b(united reformed|urc)\b', 'united_reformed'),
    (r'\b(quaker|friends meeting|society of friends)\b', 'quaker'),
    (r'\b(salvation army)\b', 'salvation_army'),
    (r'\b(roman catholic|catholic(?! university))\b', 'roman_catholic'),
    (r'\b(church of england|anglican|parish church)\b', 'church_of_england'),
    (r'\b(evangelical|gospel hall)\b', 'evangelical'),
    (r'\b(pentecostal|assemblies of god|elim)\b', 'pentecostal'),
    (r'\b(lutheran)\b', 'lutheran'),
    (r'\b(unitarian)\b', 'unitarian'),
    (r'\b(brethren|plymouth brethren)\b', 'brethren'),
    (r'\b(seventh.day adventist)\b', 'seventh_day_adventist'),
    (r'\b(jehovah.s witness|kingdom hall)\b', 'jehovahs_witness'),
    (r'\b(kirk|church of scotland)\b', 'church_of_scotland'),
    (r'\b(abbey|priory|minster|cathedral)\b', 'church_of_england'),
    (r'\b(moravian)\b', 'moravian'),
]

SIC_TO_TYPE = {
    '94910': ('other_christian', 'other_christian_general'),
    '94990': ('community', 'community_centre'),
    '56101': ('hospitality', 'restaurant'),
    '56102': ('hospitality', 'restaurant'),
    '56302': ('hospitality', 'pub'),
    '56301': ('hospitality', 'bar'),
    '93110': ('sport_leisure', 'sport_leisure_general'),
    '93130': ('sport_leisure', 'gym_fitness'),
    '85100': ('education', 'nursery'),
    '85200': ('education', 'school'),
    '68100': ('residential', 'converted_flats'),
    '68209': ('residential', 'converted_flats'),
    '88990': ('community', 'charity_hub'),
    '90010': ('arts_culture', 'theatre'),
    '90020': ('arts_culture', 'arts_centre'),
    '47190': ('commercial', 'retail_shop'),
    '47110': ('commercial', 'supermarket'),
    '82990': ('commercial', 'office'),
    '86210': ('community', 'health_centre'),
    '85590': ('education', 'community_education'),
}

NOTES_PATTERNS = [
    (r'\b(mosque|masjid|islamic centre)\b', 'mosque', 'mosque_general'),
    (r'\b(gurdwara|sikh temple)\b', 'south_asian_faith', 'sikh_gurdwara'),
    (r'\b(hindu|mandir)\b', 'south_asian_faith', 'hindu_mandir'),
    (r'\b(synagogue)\b', 'other_faith', 'jewish_synagogue'),
    (r'\b(buddhist|meditation centre)\b', 'eastern_philosophy', 'buddhist_centre'),
    (r'\b(climbing wall|climbing centre)\b', 'sport_leisure', 'climbing_wall'),
    (r'\b(gym|fitness centre|health club)\b', 'sport_leisure', 'gym_fitness'),
    (r'\b(theatre|theater)\b', 'arts_culture', 'theatre'),
    (r'\b(museum|arts centre|gallery)\b', 'arts_culture', 'arts_centre'),
    (r'\b(nursery|childcare|pre.school)\b', 'education', 'nursery'),
    (r'\b(school|academy|college)\b', 'education', 'school'),
    (r'\b(library)\b', 'education', 'library'),
    (r'\b(pub|bar|tavern|inn|taproom)\b', 'hospitality', 'pub'),
    (r'\b(restaurant|cafe|bistro)\b', 'hospitality', 'restaurant'),
    (r'\b(hotel|hostel)\b', 'hospitality', 'hotel'),
    (r'\b(office|workspace|co.working)\b', 'commercial', 'office'),
    (r'\b(shop|retail|store|supermarket)\b', 'commercial', 'retail_shop'),
    (r'\b(flat|apartment|residential|dwelling|housing)\b', 'residential', 'converted_flats'),
    (r'\b(community centre|village hall|community hub)\b', 'community', 'community_centre'),
    (r'\b(food bank|charity hub)\b', 'community', 'charity_hub'),
    (r'\b(rccg|redeemed christian)\b', 'african_diaspora_church', 'rccg'),
    (r'\b(church of pentecost)\b', 'african_diaspora_church', 'church_of_pentecost'),
    (r'\b(ukrainian|orthodox)\b', 'eastern_european_church', 'ukrainian_orthodox'),
    (r'\b(kingdom hall|jehovah)\b', 'new_religious_movement', 'jehovahs_witness'),
    (r'\b(demolished|demolition)\b', 'demolished', 'demolished'),
]


def find_latest_csv():
    candidates = sorted(glob.glob("data/output/uk_church_conversions_2*.csv"), reverse=True)
    for c in candidates:
        if "PUBLIC" not in c and "enriched" not in c:
            return Path(c)
    return None


def main():
    path = find_latest_csv()
    if not path:
        logger.error("No CSV found")
        return

    logger.info("Loading %s", path)
    df = pd.read_csv(path, low_memory=False)
    for col in ["city","former_denomination","conversion_type","conversion_subtype",
                "current_name","notes","company_type","sic_code","church_name",
                "address","ward","local_authority"]:
        if col not in df.columns:
            df[col] = None
        df[col] = df[col].astype(object)

    total = len(df)
    logger.info("Loaded %d records", total)

    def pct(col, typed=False):
        if col not in df.columns: return 0, 0.0
        if typed:
            n = (df[col] != "unknown").sum()
        else:
            n = df[col].notna().sum()
        return int(n), n/total*100

    print(f"\n{'='*60}")
    print("COVERAGE BEFORE ENRICHMENT")
    print(f"{'='*60}")
    for col, typed in [("city",False),("former_denomination",False),
                       ("conversion_type",True),("current_name",False)]:
        n, p = pct(col, typed)
        print(f"  {col:<30} {n:>7,}  ({p:.1f}%)")

    # ── PASS 1: CITY ──────────────────────────────────────────────────────────
    logger.info("Pass 1: City from local_authority / ward...")
    p1 = 0
    for idx, row in df[df["city"].isna()].iterrows():
        la = str(row.get("local_authority") or "")
        if la and la not in ("nan","None",""):
            city = re.sub(
                r'\s*(council|district|borough|city|metropolitan|county)\s*$',
                '', la, flags=re.IGNORECASE
            ).strip()
            if city:
                df.at[idx, "city"] = city
                p1 += 1
                continue
        ward = str(row.get("ward") or "")
        if ward and ward not in ("nan","None",""):
            parts = ward.split()
            if parts and len(parts[0]) > 2:
                df.at[idx, "city"] = parts[0]
                p1 += 1
    logger.info("Pass 1: %d city values added", p1)

    # ── PASS 2: DENOMINATION ──────────────────────────────────────────────────
    logger.info("Pass 2: Former denomination from name/address keywords...")
    p2 = 0
    for idx, row in df[df["former_denomination"].isna()].iterrows():
        text = " ".join([
            str(row.get("church_name") or ""),
            str(row.get("address") or ""),
            str(row.get("notes") or ""),
        ]).lower()
        for pattern, denom in DENOMINATION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                df.at[idx, "former_denomination"] = denom
                p2 += 1
                break
    logger.info("Pass 2: %d denominations added", p2)

    # ── PASS 3: TYPE FROM SIC CODES ───────────────────────────────────────────
    logger.info("Pass 3: Conversion type from SIC codes...")
    p3 = 0
    mask = df["conversion_type"] == "unknown"
    for idx, row in df[mask & df["sic_code"].notna()].iterrows():
        for sic in str(row["sic_code"]).split(","):
            sic = sic.strip()
            if sic in SIC_TO_TYPE:
                ct, cs = SIC_TO_TYPE[sic]
                df.at[idx, "conversion_type"] = ct
                df.at[idx, "conversion_subtype"] = cs
                p3 += 1
                break
    logger.info("Pass 3: %d types from SIC codes", p3)

    # ── PASS 4: TYPE FROM NOTES NLP ───────────────────────────────────────────
    logger.info("Pass 4: Conversion type from notes NLP...")
    p4 = 0
    mask = df["conversion_type"] == "unknown"
    for idx, row in df[mask].iterrows():
        text = " ".join([
            str(row.get("notes") or ""),
            str(row.get("current_name") or ""),
            str(row.get("church_name") or ""),
        ]).lower()
        for pattern, ct, cs in NOTES_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                df.at[idx, "conversion_type"] = ct
                df.at[idx, "conversion_subtype"] = cs
                p4 += 1
                break
    logger.info("Pass 4: %d types from notes NLP", p4)

    # ── PASS 5: CURRENT NAME FROM NOTES ──────────────────────────────────────
    logger.info("Pass 5: Current name from notes field...")
    p5 = 0
    name_re = re.compile(
        r'(?:now|currently|converted to|known as|renamed to?)\s+["\']?([A-Z][^|.\n"\']{3,50})',
        re.IGNORECASE
    )
    for idx, row in df[df["current_name"].isna() & df["notes"].notna()].iterrows():
        m = name_re.search(str(row["notes"]))
        if m:
            name = m.group(1).strip().rstrip(".,;)")
            if 3 < len(name) < 60:
                df.at[idx, "current_name"] = name
                p5 += 1
    logger.info("Pass 5: %d current names extracted", p5)

    # ── SAVE ──────────────────────────────────────────────────────────────────
    df.to_csv(path, index=False)

    print(f"\n{'='*60}")
    print("COVERAGE AFTER ENRICHMENT")
    print(f"{'='*60}")
    for col, typed in [("city",False),("former_denomination",False),
                       ("conversion_type",True),("current_name",False)]:
        n, p = pct(col, typed)
        print(f"  {col:<30} {n:>7,}  ({p:.1f}%)")

    print(f"\nPass results:")
    print(f"  Pass 1 city:              +{p1:,}")
    print(f"  Pass 2 denomination:      +{p2:,}")
    print(f"  Pass 3 type (SIC):        +{p3:,}")
    print(f"  Pass 4 type (NLP):        +{p4:,}")
    print(f"  Pass 5 current name:      +{p5:,}")
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()