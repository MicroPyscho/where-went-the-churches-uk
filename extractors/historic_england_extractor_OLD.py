"""
extractors/historic_england_extractor.py

Historic England National Heritage List for England (NHLE) extractor.

The NHLE API is the official government register of listed buildings.
Church buildings in the list often have detailed descriptions mentioning
their current use if they've been converted. We:

1. Query the NHLE API for all listed buildings with "church" or "chapel"
   in their name or description
2. Parse the description text to detect conversion keywords
3. Cross-reference with planning.data.gov.uk for change-of-use records

Coverage: England only (Historic England does not cover Wales, Scotland, NI)
API docs: https://historicengland.org.uk/listing/the-list/data-downloads/
"""

import logging
import time
import re
from typing import Optional
import requests
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from constants import MASTER_COLUMNS, SOURCE_CONFIDENCE

logger = logging.getLogger(__name__)

# Historic England List Entry search API
NHLE_SEARCH_URL = "https://historicengland.org.uk/listing/the-list/list-entry/search-results/"
NHLE_DETAIL_URL = "https://historicengland.org.uk/listing/the-list/list-entry/"

# planning.data.gov.uk API (DLUHC) — change of use applications
PLANNING_DATA_URL = "https://www.planning.data.gov.uk/entity.json"

HEADERS = {
    "User-Agent": "UKChurchConversionResearch/1.0 (academic project)",
    "Accept": "application/json",
}

# ─── NHLE API PARAMETERS ─────────────────────────────────────────────────────
# The NHLE search supports keyword search + type filters

NHLE_BASE_PARAMS = {
    "pageSize": 100,
    "listentry": "LB",      # Listed Building
    "grade": "",            # All grades (I, II*, II)
    "county": "",
}

CHURCH_KEYWORDS = [
    "church", "chapel", "cathedral", "minster",
    "abbey", "priory", "meeting house",
]

# ─── CONVERSION DETECTION IN DESCRIPTION TEXT ────────────────────────────────

# Patterns that indicate a conversion has occurred
CONVERSION_PATTERNS = [
    # Mosques / Islamic
    (r"\b(mosque|masjid|islamic centre|muslim community)\b",
     "mosque", "mosque_general"),

    # Other faiths
    (r"\b(gurdwara|sikh temple)\b",
     "other_faith", "sikh_gurdwara"),
    (r"\b(hindu temple|mandir)\b",
     "other_faith", "hindu_temple"),
    (r"\b(synagogue|jewish)\b",
     "other_faith", "jewish_synagogue"),
    (r"\b(pentecostal|evangelical church|new church)\b",
     "other_faith", "other_christian"),

    # Residential
    (r"\b(converted to (flats|apartments|residential|houses?|dwellings?))\b",
     "residential", "converted_flats"),
    (r"\b(now (used as|a) (residential|dwelling|flat|apartment))\b",
     "residential", "residential_general"),
    (r"\b(luxury (flat|apartment|home))\b",
     "residential", "luxury_apartments"),

    # Hospitality
    (r"\b(public house|pub|inn|tavern)\b",
     "hospitality", "pub"),
    (r"\b(night ?club|discotheque)\b",
     "hospitality", "nightclub"),
    (r"\b(restaurant|brasserie|bistro)\b",
     "hospitality", "restaurant"),
    (r"\b(hotel|hostel)\b",
     "hospitality", "hotel"),

    # Arts & Culture
    (r"\b(theatre|theater|playhouse)\b",
     "arts_culture", "theatre"),
    (r"\b(cinema|movie)\b",
     "arts_culture", "cinema"),
    (r"\b(arts centre|art center|gallery|exhibition)\b",
     "arts_culture", "arts_centre"),
    (r"\b(museum)\b",
     "arts_culture", "museum"),

    # Education
    (r"\b(school|academy|college|university|nursery)\b",
     "education", "school"),
    (r"\b(library)\b",
     "education", "library"),

    # Community
    (r"\b(community centre|community hall|youth centre|sports hall)\b",
     "community", "community_centre"),

    # Commercial
    (r"\b(offices?|workspace|co-?working)\b",
     "commercial", "office"),
    (r"\b(supermarket|shop|retail|store)\b",
     "commercial", "shop"),
    (r"\b(gym|fitness centre|climbing)\b",
     "commercial", "gym"),
]

# Phrases indicating still in use as a church (to exclude these)
STILL_CHURCH_PATTERNS = [
    r"\b(currently in use|in use as a church|active church|open for worship)\b",
    r"\b(parish church|church of england in use)\b",
]


def detect_conversion(description: str) -> Optional[tuple[str, str]]:
    """
    Scan a building description for evidence of conversion.
    Returns (conversion_type, conversion_subtype) or None if still a church.
    """
    if not description:
        return None

    desc_lower = description.lower()

    # If it's clearly still a church, skip
    for pattern in STILL_CHURCH_PATTERNS:
        if re.search(pattern, desc_lower):
            return None

    # Look for conversion evidence
    for pattern, conv_type, conv_sub in CONVERSION_PATTERNS:
        if re.search(pattern, desc_lower, re.IGNORECASE):
            return (conv_type, conv_sub)

    return None


# ─── NHLE API CALLS ──────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=30))
def search_nhle(keyword: str, page: int = 1) -> dict:
    """Search the NHLE for listed buildings matching a keyword."""
    params = {
        **NHLE_BASE_PARAMS,
        "searchQuery": keyword,
        "page": page,
    }
    resp = requests.get(
        NHLE_SEARCH_URL,
        params=params,
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=30))
def get_nhle_detail(list_entry_id: str) -> Optional[dict]:
    """Fetch full detail for a single NHLE list entry."""
    url = f"{NHLE_DETAIL_URL}{list_entry_id}/"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def fetch_all_church_entries() -> list[dict]:
    """
    Paginate through NHLE search for all church/chapel listed buildings.
    Returns raw list of summary entries.
    """
    all_entries = []
    seen_ids = set()

    for keyword in CHURCH_KEYWORDS:
        logger.info("NHLE search: keyword='%s'", keyword)
        page = 1

        while True:
            try:
                data = search_nhle(keyword, page)
            except Exception as e:
                logger.error("NHLE search failed for '%s' page %d: %s", keyword, page, e)
                break

            entries = data.get("results", [])
            if not entries:
                break

            for entry in entries:
                entry_id = entry.get("id") or entry.get("listEntry")
                if entry_id and entry_id not in seen_ids:
                    seen_ids.add(entry_id)
                    all_entries.append(entry)

            total = data.get("totalResults", 0)
            fetched_so_far = page * NHLE_BASE_PARAMS["pageSize"]
            logger.info("  keyword='%s' page %d: %d/%d total entries",
                        keyword, page, min(fetched_so_far, total), total)

            if fetched_so_far >= total:
                break

            page += 1
            time.sleep(1)

    logger.info("NHLE: %d unique church entries found", len(all_entries))
    return all_entries


def normalise_nhle_entry(entry: dict, detail: Optional[dict] = None) -> Optional[dict]:
    """
    Convert an NHLE entry (+ optional detail) to a normalised row.
    Only returns rows where we detect a conversion.
    """
    # Summary fields (always available)
    name     = entry.get("name") or entry.get("title", "")
    grade    = entry.get("grade", "")
    county   = entry.get("county", "")
    district = entry.get("district", "")
    parish   = entry.get("parish", "")
    lat      = entry.get("latitude") or entry.get("lat")
    lon      = entry.get("longitude") or entry.get("lon")
    entry_id = entry.get("id") or entry.get("listEntry")

    # Detail fields (if we fetched full record)
    description = ""
    if detail:
        description = (
            detail.get("description", "") or
            detail.get("listEntryDescription", "") or
            detail.get("summary", "")
        )

    # Detect conversion from name or description
    combined_text = f"{name} {description}"
    conversion = detect_conversion(combined_text)

    if conversion is None:
        # No conversion detected — skip
        return None

    conv_type, conv_sub = conversion
    source_url = f"https://historicengland.org.uk/listing/the-list/list-entry/{entry_id}"

    try:
        lat_f = float(lat) if lat else None
        lon_f = float(lon) if lon else None
    except (ValueError, TypeError):
        lat_f, lon_f = None, None

    return {
        "id":                 None,
        "church_name":        name,
        "former_denomination":None,
        "address":            parish or None,
        "city":               district or county,
        "local_authority":    district or None,
        "region":             None,
        "nation":             "England",  # NHLE is England-only
        "latitude":           lat_f,
        "longitude":          lon_f,
        "conversion_type":    conv_type,
        "conversion_subtype": conv_sub,
        "current_name":       None,
        "year_converted":     None,
        "decade":             None,
        "source":             "historic_england",
        "source_url":         source_url,
        "confidence_score":   SOURCE_CONFIDENCE["historic_england"],
        "notes":              f"Grade {grade} listed building. {description[:200] if description else ''}",
    }


# ─── MAIN EXTRACTOR ──────────────────────────────────────────────────────────

def extract(fetch_details: bool = False) -> pd.DataFrame:
    """
    Pull all church-related NHLE entries and filter to those
    showing evidence of conversion.

    Args:
        fetch_details: If True, fetch full description for each entry
                       (much slower but more accurate conversion detection).
                       Set False for quick first pass.
    """
    entries = fetch_all_church_entries()
    rows = []

    for i, entry in enumerate(entries):
        detail = None

        if fetch_details:
            entry_id = entry.get("id") or entry.get("listEntry")
            if entry_id:
                try:
                    detail = get_nhle_detail(str(entry_id))
                    time.sleep(0.3)  # Rate limit — be polite
                except Exception as e:
                    logger.debug("Could not fetch detail for %s: %s", entry_id, e)

        row = normalise_nhle_entry(entry, detail)
        if row:
            rows.append(row)

        if (i + 1) % 100 == 0:
            logger.info("NHLE: processed %d/%d entries, %d conversions found",
                        i + 1, len(entries), len(rows))

    if not rows:
        logger.warning("No NHLE conversions detected.")
        return pd.DataFrame(columns=MASTER_COLUMNS)

    df = pd.DataFrame(rows, columns=MASTER_COLUMNS)
    logger.info("NHLE: %d conversion records extracted", len(df))
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = extract(fetch_details=False)  # Quick mode
    print(df[["church_name", "city", "conversion_type", "nation"]].head(20))
    print(f"\nTotal Historic England records: {len(df)}")
    df.to_csv("/home/claude/church_conversion_pipeline/data/raw/historic_england_raw.csv", index=False)
