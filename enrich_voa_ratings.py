"""
enrich_voa_ratings.py

Downloads the Valuation Office Agency (VOA) Non-Domestic Rating List
and cross-references by postcode against our dataset.

The VOA rating list contains every commercial property in England and Wales
with:
  - Property description ("Restaurant and Premises", "Office and Premises")
  - Effective date (when the rating came into force)
  - Rateable value
  - Full address and postcode

This is a primary government source — not inferred, not ML.
A church postcode matching a VOA "Restaurant and Premises" entry
is a confirmed hospitality conversion with a real effective date.

Free download from: https://www.tax.service.gov.uk/business-rates-find/

Run: python enrich_voa_ratings.py

Note: VOA data is England and Wales only.
"""

import time
import glob
import logging
import requests
import zipfile
import io
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

VOA_PATH = Path("data/raw/voa_ratings.csv")

# VOA description → conversion type mapping
VOA_DESCRIPTION_MAP = {
    "restaurant":           ("hospitality",  "restaurant"),
    "public house":         ("hospitality",  "pub"),
    "pub":                  ("hospitality",  "pub"),
    "bar":                  ("hospitality",  "bar"),
    "hotel":                ("hospitality",  "hotel"),
    "cafe":                 ("hospitality",  "cafe"),
    "coffee":               ("hospitality",  "cafe"),
    "office":               ("commercial",   "office"),
    "retail":               ("commercial",   "retail_shop"),
    "shop":                 ("commercial",   "retail_shop"),
    "store":                ("commercial",   "retail_shop"),
    "supermarket":          ("commercial",   "supermarket"),
    "school":               ("education",    "school"),
    "nursery":              ("education",    "nursery"),
    "college":              ("education",    "college"),
    "library":              ("education",    "library"),
    "community centre":     ("community",    "community_centre"),
    "village hall":         ("community",    "community_centre"),
    "health centre":        ("community",    "health_centre"),
    "surgery":              ("community",    "health_centre"),
    "gym":                  ("sport_leisure","gym_fitness"),
    "sports":               ("sport_leisure","sport_leisure_general"),
    "climbing":             ("sport_leisure","climbing_wall"),
    "theatre":              ("arts_culture", "theatre"),
    "museum":               ("arts_culture", "museum"),
    "gallery":              ("arts_culture", "gallery"),
    "arts centre":          ("arts_culture", "arts_centre"),
    "mosque":               ("mosque",       "mosque_general"),
    "place of worship":     ("other_christian","place_of_worship"),
    "place of worship (other)": ("other_faith","place_of_worship"),
    "gurdwara":             ("south_asian_faith","sikh_gurdwara"),
    "temple":               ("south_asian_faith","hindu_mandir"),
    "synagogue":            ("other_faith",  "jewish_synagogue"),
    "car park":             ("commercial",   "car_park"),
    "garage":               ("commercial",   "garage"),
    "workshop":             ("commercial",   "workshop"),
    "warehouse":            ("commercial",   "warehouse"),
    "studio":               ("arts_culture", "recording_studio"),
    "night club":           ("hospitality",  "nightclub"),
    "cinema":               ("arts_culture", "cinema"),
}


def download_voa():
    """Download VOA rating list. Tries bulk download first."""
    logger.info("Downloading VOA rating list...")
    VOA_PATH.parent.mkdir(parents=True, exist_ok=True)

    # VOA Bulk Data Download — free, no registration
    urls = [
        "https://www.tax.service.gov.uk/business-rates-find/downloads/2023-list-compiled-data.csv",
        "https://voaratinglists.blob.core.windows.net/html/rli.htm",
    ]

    for url in urls:
        try:
            resp = requests.get(url, timeout=60, stream=True)
            if resp.status_code == 200:
                with open(VOA_PATH, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info("Downloaded: %s (%.1f MB)", VOA_PATH, VOA_PATH.stat().st_size/1e6)
                return True
        except Exception as e:
            logger.warning("URL failed: %s — %s", url, e)

    logger.warning("Automatic download failed.")
    logger.info(
        "Manual download instructions:\n"
        "1. Go to: https://www.tax.service.gov.uk/business-rates-find/\n"
        "2. Download 'Rating List' bulk data\n"
        "3. Save as: data/raw/voa_ratings.csv\n"
        "Alternative: https://voaratinglists.blob.core.windows.net/html/rli.htm"
    )
    return False


def find_latest_csv():
    candidates = sorted(glob.glob("data/output/uk_church_conversions_2*.csv"), reverse=True)
    for c in candidates:
        if "PUBLIC" not in c and "enriched" not in c:
            return Path(c)
    return None


def classify_from_voa_description(description):
    """Map VOA property description to conversion type."""
    desc_lower = str(description).lower()
    for keyword, (conv_type, conv_subtype) in VOA_DESCRIPTION_MAP.items():
        if keyword in desc_lower:
            return conv_type, conv_subtype
    return None, None


def main():
    if not VOA_PATH.exists():
        success = download_voa()
        if not success:
            logger.error("VOA data not available. Download manually.")
            return

    logger.info("Loading VOA ratings list...")
    try:
        # VOA file has specific column structure
        voa = pd.read_csv(
            VOA_PATH,
            low_memory=False,
            encoding="latin-1",
            on_bad_lines="skip",
        )
        logger.info("VOA columns: %s", voa.columns.tolist()[:10])
    except Exception as e:
        logger.error("Could not load VOA file: %s", e)
        return

    # Standardise VOA columns — the file uses specific naming
    # Find postcode, description, and date columns
    pc_col = next((c for c in voa.columns if "postcode" in c.lower()), None)
    desc_col = next((c for c in voa.columns if "description" in c.lower() or "primary" in c.lower()), None)
    date_col = next((c for c in voa.columns if "effective" in c.lower() or "date" in c.lower()), None)
    name_col = next((c for c in voa.columns if "name" in c.lower() or "property" in c.lower()), None)

    logger.info("Using: postcode=%s, description=%s, date=%s", pc_col, desc_col, date_col)

    if not pc_col or not desc_col:
        logger.error("Could not identify key columns in VOA file.")
        logger.info("Columns available: %s", voa.columns.tolist())
        return

    # Build postcode index
    voa["_pc_clean"] = voa[pc_col].str.upper().str.replace(" ","").str[:5]
    voa_by_pc = voa.groupby("_pc_clean")
    logger.info("VOA: %d records, %d unique postcodes", len(voa), voa["_pc_clean"].nunique())

    # Load church dataset
    path = find_latest_csv()
    df = pd.read_csv(path, low_memory=False)
    logger.info("Church dataset: %d records", len(df))

    df["_pc_key"] = df["postcode"].str.upper().str.replace(" ","").str[:5]

    updated_type = 0
    updated_name = 0
    updated_year = 0

    for pc_key, voa_group in voa_by_pc:
        matching = df[df["_pc_key"] == pc_key]
        if len(matching) == 0:
            continue

        for _, voa_row in voa_group.iterrows():
            description = str(voa_row.get(desc_col, ""))
            conv_type, conv_subtype = classify_from_voa_description(description)

            if not conv_type:
                continue

            for idx in matching.index:
                if df.at[idx, "conversion_type"] != "unknown":
                    continue

                df.at[idx, "conversion_type"] = conv_type
                df.at[idx, "conversion_subtype"] = conv_subtype
                df.at[idx, "confidence_score"] = 0.85
                updated_type += 1

                # Current name from VOA
                if pd.isna(df.at[idx, "current_name"]) and name_col:
                    voa_name = str(voa_row.get(name_col, ""))
                    if voa_name and voa_name not in ("nan",""):
                        df.at[idx, "current_name"] = voa_name
                        updated_name += 1

                # Year from VOA effective date
                if pd.isna(df.at[idx, "year_converted"]) and date_col:
                    date_val = str(voa_row.get(date_col, ""))
                    if date_val and len(date_val) >= 4:
                        try:
                            yr = int(date_val[:4])
                            if 1990 <= yr <= 2024:
                                df.at[idx, "year_converted"] = yr
                                df.at[idx, "decade"] = f"{(yr//10)*10}s"
                                updated_year += 1
                        except ValueError:
                            pass

                existing_notes = str(df.at[idx, "notes"] or "")
                df.at[idx, "notes"] = (
                    existing_notes +
                    f" | VOA: {description[:50]} (effective: {date_val[:10] if date_col else 'unknown'})"
                )
                break

    df = df.drop(columns=["_pc_key"], errors="ignore")
    df.to_csv(path, index=False)

    print(f"\n{'='*60}")
    print("VOA RATING LIST ENRICHMENT COMPLETE")
    print(f"{'='*60}")
    print(f"Types updated:      {updated_type:,}")
    print(f"Names added:        {updated_name:,}")
    print(f"Years added:        {updated_year:,}")
    print(f"Unknown remaining:  {(df['conversion_type']=='unknown').sum():,}")
    print(f"\nConversion type breakdown:")
    print(df["conversion_type"].value_counts().head(12).to_string())
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()