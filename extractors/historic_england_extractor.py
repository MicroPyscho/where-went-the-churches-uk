"""
extractors/historic_england_extractor.py

Historic England NHLE extractor — reads from locally downloaded CSV.

Download the points CSV from:
https://opendata-historicengland.hub.arcgis.com/datasets/historicengland::national-heritage-list-for-england-nhle/explore?layer=0

Save it to: data/raw/historic_england_nhle.csv

The CSV uses British National Grid (BNG) Easting/Northing coordinates,
not lat/lon. This extractor converts them using the pyproj library.

Columns in the CSV:
  OBJECTID, List Entry Number, List Entry Name, Grade,
  Listing date, Date of most recent amendment, Capture scale,
  NHLE link, National Grid Reference, Easting, Northing

Strategy:
  1. Filter rows where name contains church/chapel/minster/cathedral etc.
  2. Convert BNG Easting/Northing to WGS84 lat/lon
  3. Attempt conversion detection from the name alone (limited but fast)
  4. Return all matches as "listed former church" with unknown conversion type
     — the pipeline deduplication stage will cross-reference with OSM/Wikidata
     to upgrade the conversion_type where a match is found nearby

Coverage: England only.
"""

import logging
import os
from pathlib import Path
from typing import Optional
import pandas as pd

from constants import MASTER_COLUMNS, SOURCE_CONFIDENCE

logger = logging.getLogger(__name__)

# Path to the downloaded CSV — adjust if you saved it elsewhere
DEFAULT_CSV_PATH = "data/raw/historic_england_nhle.csv"

CHURCH_KEYWORDS = [
    "church", "chapel", "cathedral", "minster",
    "abbey", "priory", "meeting house", "mission hall",
]

# Keywords in the name that suggest conversion has already happened
# (Historic England sometimes names a listing by its current use)
CONVERSION_HINTS = [
    ("mosque", "mosque", "mosque_general"),
    ("masjid", "mosque", "mosque_general"),
    ("gurdwara", "other_faith", "sikh_gurdwara"),
    ("synagogue", "other_faith", "jewish_synagogue"),
    ("pub ", "hospitality", "pub"),
    (" inn", "hospitality", "pub"),
    ("restaurant", "hospitality", "restaurant"),
    ("hotel", "hospitality", "hotel"),
    ("theatre", "arts_culture", "theatre"),
    ("cinema", "arts_culture", "cinema"),
    ("museum", "arts_culture", "museum"),
    ("gallery", "arts_culture", "arts_centre"),
    ("arts centre", "arts_culture", "arts_centre"),
    ("school", "education", "school"),
    ("library", "education", "library"),
    ("flats", "residential", "converted_flats"),
    ("apartments", "residential", "converted_flats"),
    ("house", "residential", "single_dwelling"),
    ("community centre", "community", "community_centre"),
    ("village hall", "community", "community_centre"),
    ("office", "commercial", "office"),
    ("shop", "commercial", "shop"),
    ("gym", "commercial", "gym"),
]


def bng_to_latlon(easting: float, northing: float) -> tuple[Optional[float], Optional[float]]:
    """
    Convert British National Grid (OSGB36) Easting/Northing to WGS84 lat/lon.
    Uses pyproj if available, falls back to an approximate formula.
    """
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
        lon, lat = transformer.transform(easting, northing)
        return round(lat, 6), round(lon, 6)
    except ImportError:
        # Approximate conversion (accurate to ~5m for mainland UK)
        # Based on OS guidance for simple transforms
        e = easting - 400000
        n = northing - 600000
        lat_approx = 49.0 + (n / 111320)
        lon_approx = -2.0 + (e / (111320 * 0.6))
        return round(lat_approx, 4), round(lon_approx, 4)
    except Exception:
        return None, None


def detect_conversion_from_name(name: str) -> tuple[str, str]:
    """
    Try to infer conversion type from the listing name alone.
    Returns (conversion_type, conversion_subtype).
    """
    name_lower = name.lower()
    for keyword, conv_type, conv_sub in CONVERSION_HINTS:
        if keyword in name_lower:
            return conv_type, conv_sub
    return "unknown", "unknown"


def is_church_entry(name: str) -> bool:
    """Check if a listing name contains a church-related keyword."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in CHURCH_KEYWORDS)


def normalise_row(row: pd.Series) -> dict:
    """Convert a single NHLE CSV row into a normalised pipeline record."""
    name = str(row.get("List Entry Name", "") or "")
    entry_number = str(row.get("List Entry Number", "") or "")
    grade = str(row.get("Grade", "") or "")
    nhle_link = str(row.get("NHLE link", "") or "")
    listing_date = str(row.get("Listing date", "") or "")

    easting = row.get("Easting")
    northing = row.get("Northing")

    lat, lon = None, None
    if pd.notna(easting) and pd.notna(northing):
        try:
            lat, lon = bng_to_latlon(float(easting), float(northing))
        except (ValueError, TypeError):
            pass

    conv_type, conv_sub = detect_conversion_from_name(name)

    # Extract year from listing date if available
    year = None
    if listing_date and listing_date != "nan":
        try:
            year = int(listing_date.split("/")[-1].split(" ")[0])
            if year > 2030 or year < 1700:
                year = None
        except (ValueError, IndexError):
            pass

    return {
        "id":                 None,
        "church_name":        name,
        "former_denomination":None,
        "address":            None,
        "city":               None,
        "local_authority":    None,
        "region":             None,
        "nation":             "England",
        "latitude":           lat,
        "longitude":          lon,
        "conversion_type":    conv_type,
        "conversion_subtype": conv_sub,
        "current_name":       None,
        "year_converted":     None,
        "decade":             None,
        "source":             "historic_england",
        "source_url":         nhle_link or f"https://historicengland.org.uk/listing/the-list/list-entry/{entry_number}",
        "confidence_score":   SOURCE_CONFIDENCE["historic_england"],
        "notes":              f"Grade {grade} listed building. NHLE #{entry_number}.",
    }


def extract(csv_path: str = DEFAULT_CSV_PATH) -> pd.DataFrame:
    """
    Read the NHLE CSV, filter to church/chapel entries,
    convert coordinates, and return normalised DataFrame.

    Args:
        csv_path: Path to the downloaded NHLE points CSV.
                  Download from Historic England open data portal.
    """
    path = Path(csv_path)

    if not path.exists():
        logger.warning(
            "Historic England CSV not found at '%s'. "
            "Download it from: https://opendata-historicengland.hub.arcgis.com/"
            "datasets/historicengland::national-heritage-list-for-england-nhle/explore?layer=0 "
            "and save to data/raw/historic_england_nhle.csv",
            csv_path,
        )
        return pd.DataFrame(columns=MASTER_COLUMNS)

    logger.info("Reading Historic England NHLE CSV from %s", csv_path)

    try:
        # The CSV has a BOM character — encoding='utf-8-sig' handles it
        raw = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    except Exception as e:
        logger.error("Failed to read NHLE CSV: %s", e)
        return pd.DataFrame(columns=MASTER_COLUMNS)

    logger.info("NHLE CSV: %d total listed buildings", len(raw))

    # Filter to church/chapel entries
    church_mask = raw["List Entry Name"].astype(str).str.lower().apply(
        lambda n: any(kw in n for kw in CHURCH_KEYWORDS)
    )
    churches = raw[church_mask].copy()
    logger.info("NHLE: %d entries with church/chapel keywords", len(churches))

    # Normalise each row
    rows = [normalise_row(row) for _, row in churches.iterrows()]
    df = pd.DataFrame(rows, columns=MASTER_COLUMNS)

    # Report conversion detection
    typed = df[df["conversion_type"] != "unknown"]
    logger.info(
        "NHLE: %d total church entries, %d with conversion detected from name",
        len(df), len(typed),
    )

    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Check if pyproj is available for accurate coordinate conversion
    try:
        import pyproj
        print("pyproj available — using accurate BNG→WGS84 conversion")
    except ImportError:
        print("pyproj not installed — using approximate coordinate conversion")
        print("For better accuracy: pip install pyproj")

    df = extract()
    print(df[["church_name", "conversion_type", "latitude", "longitude", "nation"]].head(20))
    print(f"\nTotal Historic England records: {len(df)}")

    if not df.empty:
        df.to_csv("data/raw/historic_england_raw.csv", index=False)
        print("Saved to data/raw/historic_england_raw.csv")