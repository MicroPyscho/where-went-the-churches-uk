"""
extractors/charity_commission_extractor.py

Charity Commission API extractor (England & Wales).

Most active churches are registered charities. When a church building is sold
or the congregation dissolves, the charity is often deregistered. By querying
the Charity Commission API for deregistered charities with church/chapel in
their name AND cross-referencing with active mosques/other uses registered
at the same address, we can infer conversions.

Also covers Wales via the Charity Commission for England and Wales.

API: https://api.charitycommission.gov.uk/
Documentation: https://register-of-charities.charitycommission.gov.uk/api

Strategy:
  1. Pull all REMOVED/DEREGISTERED charities with "church" in name
  2. Pull all active charities that are mosques, gurdwaras, etc.
  3. Attempt address-matching between the two sets
  4. Also flag deregistered churches as "closed" (may be residential etc.)
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

CHARITY_API_BASE = "https://api.charitycommission.gov.uk/register/api"
HEADERS = {
    "User-Agent": "UKChurchConversionResearch/1.0 (academic project)",
    "Accept": "application/json",
    # Note: The Charity Commission API requires a free API key
    # Register at: https://register-of-charities.charitycommission.gov.uk/api
    # Add your key to .env as CHARITY_COMMISSION_API_KEY
}

# Search keywords for church charities
CHURCH_CHARITY_KEYWORDS = [
    "church", "chapel", "parish", "congregation", "tabernacle",
    "minster", "cathedral", "mission hall", "gospel hall",
]

# Keywords for religious conversion target charities
MOSQUE_KEYWORDS = ["mosque", "masjid", "islamic centre", "muslim"]
OTHER_FAITH_KEYWORDS = ["gurdwara", "sikh", "hindu mandir", "buddhist", "synagogue"]


def get_api_key() -> Optional[str]:
    """Load API key from environment."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    key = os.getenv("CHARITY_COMMISSION_API_KEY")
    if not key:
        logger.warning(
            "CHARITY_COMMISSION_API_KEY not set in .env — "
            "Charity Commission requests may fail. "
            "Register free at: https://register-of-charities.charitycommission.gov.uk/api"
        )
    return key


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=30))
def search_charities(
    keyword: str,
    status: str = "RM",  # RM = Removed, R = Registered
    page: int = 1,
    page_size: int = 100,
    api_key: Optional[str] = None,
) -> dict:
    """
    Search Charity Commission API.

    status:
      R  = Registered (active)
      RM = Removed (deregistered/dissolved)
    """
    headers = {**HEADERS}
    if api_key:
        headers["Ocp-Apim-Subscription-Key"] = api_key

    params = {
        "charity_name": keyword,
        "registration_status": status,
        "page_number": page,
        "page_size": page_size,
    }

    resp = requests.get(
        f"{CHARITY_API_BASE}/charities",
        params=params,
        headers=headers,
        timeout=30,
    )

    if resp.status_code == 401:
        logger.warning("Charity Commission: 401 Unauthorized — check your API key")
        return {}

    resp.raise_for_status()
    return resp.json()


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=5, max=20))
def get_charity_detail(charity_number: str, api_key: Optional[str] = None) -> Optional[dict]:
    """Fetch full detail for a single charity including address."""
    headers = {**HEADERS}
    if api_key:
        headers["Ocp-Apim-Subscription-Key"] = api_key

    resp = requests.get(
        f"{CHARITY_API_BASE}/charities/{charity_number}",
        headers=headers,
        timeout=20,
    )
    if resp.status_code in (404, 401):
        return None
    resp.raise_for_status()
    return resp.json()


def extract_address_components(charity_detail: dict) -> dict:
    """Pull address fields from a charity detail record."""
    # The Charity Commission API nests address in several possible locations
    address_obj = (
        charity_detail.get("charity_address") or
        charity_detail.get("principal_address") or
        {}
    )
    return {
        "address": address_obj.get("address_line_1") or address_obj.get("line1"),
        "city":    address_obj.get("town") or address_obj.get("city"),
        "postcode":address_obj.get("postcode"),
        "lat":     charity_detail.get("latitude"),
        "lon":     charity_detail.get("longitude"),
    }


def infer_conversion_from_name(charity_name: str) -> Optional[tuple[str, str]]:
    """
    If a mosque/gurdwara charity is registered at the same address as
    a former church, we know the conversion type. This function classifies
    the NEW charity's purpose.
    """
    name_lower = charity_name.lower()
    if any(kw in name_lower for kw in MOSQUE_KEYWORDS):
        return ("mosque", "mosque_general")
    if "gurdwara" in name_lower or "sikh" in name_lower:
        return ("other_faith", "sikh_gurdwara")
    if "hindu" in name_lower or "mandir" in name_lower:
        return ("other_faith", "hindu_temple")
    if "buddhist" in name_lower:
        return ("other_faith", "buddhist_temple")
    if "synagogue" in name_lower or "jewish" in name_lower:
        return ("other_faith", "jewish_synagogue")
    return None


def postcode_prefix(postcode: Optional[str]) -> Optional[str]:
    """Extract postcode outward code for fuzzy matching: 'SW1A 2AA' → 'SW1A'"""
    if not postcode:
        return None
    return postcode.strip().upper().split(" ")[0]


def fetch_deregistered_churches(api_key: Optional[str]) -> list[dict]:
    """
    Fetch all deregistered church charities from the Charity Commission.
    Returns list of enriched records with address info.
    """
    all_records = []
    seen = set()

    for keyword in CHURCH_CHARITY_KEYWORDS:
        logger.info("Charity Commission: searching deregistered charities, keyword='%s'", keyword)
        page = 1

        while True:
            try:
                data = search_charities(keyword, status="RM", page=page, api_key=api_key)
            except Exception as e:
                logger.error("Charity search failed for '%s': %s", keyword, e)
                break

            charities = data.get("charities", []) or data.get("data", [])
            if not charities:
                break

            for charity in charities:
                number = str(charity.get("charity_number") or charity.get("registered_charity_number", ""))
                if number in seen:
                    continue
                seen.add(number)

                name = charity.get("charity_name", "")
                # Double-check it's a church (keyword search can return false positives)
                if not any(kw in name.lower() for kw in CHURCH_CHARITY_KEYWORDS):
                    continue

                # Get removal date
                removal_date = charity.get("date_of_removal") or charity.get("removed_date")
                year = None
                if removal_date:
                    try:
                        year = int(str(removal_date)[:4])
                    except (ValueError, TypeError):
                        pass

                record = {
                    "charity_number": number,
                    "charity_name":   name,
                    "removal_year":   year,
                    "postcode":       charity.get("postcode"),
                    "address":        charity.get("address"),
                    "city":           charity.get("town") or charity.get("city"),
                    "lat":            charity.get("latitude"),
                    "lon":            charity.get("longitude"),
                }
                all_records.append(record)

            total = data.get("total_results", data.get("totalResults", 0))
            if page * 100 >= total:
                break
            page += 1
            time.sleep(0.5)

    logger.info("Charity Commission: %d deregistered church charities found", len(all_records))
    return all_records


def fetch_active_religious_charities(api_key: Optional[str]) -> list[dict]:
    """
    Fetch active mosque/gurdwara/temple charities to cross-reference addresses.
    """
    all_records = []
    seen = set()
    target_keywords = MOSQUE_KEYWORDS + OTHER_FAITH_KEYWORDS

    for keyword in target_keywords:
        try:
            data = search_charities(keyword, status="R", page=1, page_size=100, api_key=api_key)
        except Exception as e:
            logger.error("Active religious charity search failed for '%s': %s", keyword, e)
            continue

        charities = data.get("charities", []) or data.get("data", [])
        for charity in charities:
            number = str(charity.get("charity_number", ""))
            if number in seen:
                continue
            seen.add(number)

            conversion = infer_conversion_from_name(charity.get("charity_name", ""))
            if not conversion:
                continue

            all_records.append({
                "charity_number":  number,
                "charity_name":    charity.get("charity_name", ""),
                "conversion_type": conversion[0],
                "conversion_sub":  conversion[1],
                "postcode":        charity.get("postcode"),
                "lat":             charity.get("latitude"),
                "lon":             charity.get("longitude"),
            })

        time.sleep(0.3)

    logger.info("Charity Commission: %d active religious charities for cross-reference", len(all_records))
    return all_records


def match_by_postcode(churches: list[dict], active_religious: list[dict]) -> list[dict]:
    """
    Match deregistered churches to active religious charities by postcode prefix.
    Where a mosque/gurdwara is in the same postcode district as a deregistered church,
    flag as a probable conversion.
    """
    # Build postcode → active religious charity map
    postcode_to_religious: dict[str, list[dict]] = {}
    for ar in active_religious:
        prefix = postcode_prefix(ar.get("postcode"))
        if prefix:
            postcode_to_religious.setdefault(prefix, []).append(ar)

    matched_rows = []
    for church in churches:
        prefix = postcode_prefix(church.get("postcode"))
        if prefix and prefix in postcode_to_religious:
            matches = postcode_to_religious[prefix]
            # Take the first match (closest conversion type)
            best = matches[0]
            matched_rows.append({
                **church,
                "conversion_type": best["conversion_type"],
                "conversion_sub":  best["conversion_sub"],
                "current_name":    best["charity_name"],
                "confidence":      0.65,  # Lower — postcode match is imprecise
                "match_method":    "postcode_district",
            })

    logger.info("Charity Commission: %d postcode-matched church→religious conversions", len(matched_rows))
    return matched_rows


def normalise_record(record: dict) -> dict:
    """Convert a matched record into a normalised pipeline row."""
    year = record.get("removal_year")
    try:
        lat = float(record["lat"]) if record.get("lat") else None
        lon = float(record["lon"]) if record.get("lon") else None
    except (ValueError, TypeError):
        lat, lon = None, None

    return {
        "id":                 None,
        "church_name":        record.get("charity_name"),
        "former_denomination":None,
        "address":            record.get("address"),
        "city":               record.get("city"),
        "local_authority":    None,
        "region":             None,
        "nation":             None,  # Could be England or Wales
        "latitude":           lat,
        "longitude":          lon,
        "conversion_type":    record.get("conversion_type", "unknown"),
        "conversion_subtype": record.get("conversion_sub", "unknown"),
        "current_name":       record.get("current_name"),
        "year_converted":     year,
        "decade":             f"{(year // 10) * 10}s" if year else None,
        "source":             "charity_commission",
        "source_url":         f"https://register-of-charities.charitycommission.gov.uk/charity-search/-/charity-details/{record.get('charity_number')}",
        "confidence_score":   record.get("confidence", SOURCE_CONFIDENCE["charity_commission"]),
        "notes":              f"Deregistered charity #{record.get('charity_number')}. Match method: {record.get('match_method', 'direct')}",
    }


# ─── MAIN EXTRACTOR ──────────────────────────────────────────────────────────

def extract() -> pd.DataFrame:
    """
    Pull Charity Commission data, cross-reference churches with
    active religious charities, and return normalised DataFrame.
    """
    api_key = get_api_key()

    # Fetch both sets
    deregistered_churches = fetch_deregistered_churches(api_key)
    active_religious = fetch_active_religious_charities(api_key)

    if not deregistered_churches:
        logger.warning("No deregistered church charities retrieved (check API key).")
        return pd.DataFrame(columns=MASTER_COLUMNS)

    # Match by postcode
    matched = match_by_postcode(deregistered_churches, active_religious)

    # Also include unmatched deregistered churches as "closed/unknown"
    matched_charity_nums = {r["charity_number"] for r in matched}
    unmatched = [
        {**c, "conversion_type": "unknown", "conversion_sub": "unknown",
         "current_name": None, "confidence": 0.5, "match_method": "deregistered_only"}
        for c in deregistered_churches
        if c["charity_number"] not in matched_charity_nums
    ]

    all_records = matched + unmatched
    rows = [normalise_record(r) for r in all_records]

    df = pd.DataFrame(rows, columns=MASTER_COLUMNS)
    logger.info("Charity Commission: %d total records (%d matched, %d unmatched/closed)",
                len(df), len(matched), len(unmatched))
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = extract()
    print(df[["church_name", "city", "conversion_type", "year_converted"]].head(20))
    print(f"\nTotal Charity Commission records: {len(df)}")
    df.to_csv("/home/claude/church_conversion_pipeline/data/raw/charity_commission_raw.csv", index=False)
