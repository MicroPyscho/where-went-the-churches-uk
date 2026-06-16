"""
extractors/oscr_ccni_extractor.py

OSCR (Office of the Scottish Charity Regulator) and
CCNI (Charity Commission for Northern Ireland) extractors.

Fills the Scotland and Northern Ireland gap — these nations are
severely undercounted because:
  - Historic England NHLE covers England only
  - Charity Commission covers England and Wales only
  - Planning portal covers England only

OSCR API: https://www.oscr.org.uk/about-charities/search-the-register/
CCNI API: https://www.charitycommissionni.org.uk/charity-search/

Both have free public search APIs and bulk download options.

Strategy:
  1. Search for charities with "church", "chapel" etc. in name
  2. Filter for deregistered/wound-up status
  3. Cross-reference with active religious charities at same postcode
  4. Return normalised records with nation = Scotland / Northern Ireland
"""

import logging
import time
import re
import json
import glob
from pathlib import Path
from typing import Optional
import requests
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from constants import MASTER_COLUMNS, SOURCE_CONFIDENCE

logger = logging.getLogger(__name__)

# OSCR endpoints
OSCR_SEARCH = "https://www.oscr.org.uk/umbraco/api/charityregisterapi/search"
OSCR_BULK   = "https://www.oscr.org.uk/about-charities/search-the-register/charity-register-download/"

# CCNI endpoints
CCNI_SEARCH = "https://www.charitycommissionni.org.uk/api/charitySearch/"
CCNI_DETAIL = "https://www.charitycommissionni.org.uk/api/charity/"

HEADERS = {
    "User-Agent": "UKChurchConversionResearch/1.0 (academic project)",
    "Accept": "application/json",
}

CHURCH_KEYWORDS = [
    "church", "chapel", "cathedral", "minster", "abbey",
    "priory", "mission hall", "gospel hall", "congregation",
    "tabernacle", "methodist", "baptist", "presbyterian",
    "parish", "kirk",  # Kirk = Scottish word for church
]

MOSQUE_KEYWORDS = ["mosque", "masjid", "islamic", "muslim"]
OTHER_FAITH_KEYWORDS = ["gurdwara", "sikh", "hindu", "mandir", "buddhist"]


# ─── OSCR (SCOTLAND) ─────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=30))
def search_oscr(keyword: str, status: str = "Removed") -> list[dict]:
    """
    Search OSCR for Scottish charities.
    status: "Removed" for dissolved, "Registered" for active.
    """
    params = {
        "search": keyword,
        "status": status,
        "take": 100,
        "skip": 0,
    }
    resp = requests.get(OSCR_SEARCH, params=params, headers=HEADERS, timeout=20)
    if resp.status_code == 404:
        logger.info("OSCR search endpoint not available — try bulk download")
        return []
    resp.raise_for_status()
    data = resp.json()
    return data.get("charities", []) or data.get("results", []) or []


def normalise_oscr_record(charity: dict) -> dict:
    """Convert OSCR record to pipeline schema."""
    name = charity.get("charity_name") or charity.get("name", "")
    number = str(charity.get("charity_number") or charity.get("sc_number", ""))
    postcode = charity.get("postcode", "")
    dissolved = charity.get("date_dissolved") or charity.get("ceased_date", "")

    year = None
    if dissolved:
        try:
            year = int(str(dissolved)[:4])
        except (ValueError, TypeError):
            pass

    return {
        "id":                 None,
        "church_name":        name,
        "former_denomination":None,
        "address":            charity.get("address", ""),
        "city":               charity.get("town") or charity.get("city", ""),
        "local_authority":    charity.get("local_authority", ""),
        "region":             "Scotland",
        "nation":             "Scotland",
        "latitude":           None,
        "longitude":          None,
        "conversion_type":    "unknown",
        "conversion_subtype": "unknown",
        "current_name":       None,
        "year_converted":     year,
        "decade":             f"{(year//10)*10}s" if year else None,
        "source":             "oscr",
        "source_url":         f"https://www.oscr.org.uk/about-charities/search-the-register/charity-details/?number={number}",
        "confidence_score":   0.72,
        "notes":              f"OSCR charity #{number}. Dissolved: {dissolved}",
    }


def extract_oscr() -> pd.DataFrame:
    """Pull deregistered church charities from OSCR (Scotland)."""
    all_records = []
    seen = set()

    for keyword in CHURCH_KEYWORDS[:6]:
        logger.info("OSCR: searching '%s'", keyword)
        try:
            charities = search_oscr(keyword, status="Removed")
        except Exception as e:
            logger.error("OSCR search failed for '%s': %s", keyword, e)
            continue

        for charity in charities:
            number = str(charity.get("charity_number") or
                        charity.get("sc_number", ""))
            if number in seen:
                continue
            seen.add(number)

            name = charity.get("charity_name") or charity.get("name", "")
            if not any(kw in name.lower() for kw in CHURCH_KEYWORDS):
                continue

            all_records.append(normalise_oscr_record(charity))
        time.sleep(0.5)

    logger.info("OSCR: %d deregistered church charities", len(all_records))
    if not all_records:
        return pd.DataFrame(columns=MASTER_COLUMNS)
    return pd.DataFrame(all_records, columns=MASTER_COLUMNS)


# ─── CCNI (NORTHERN IRELAND) ─────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=30))
def search_ccni(keyword: str) -> list[dict]:
    """Search CCNI for Northern Ireland charities."""
    params = {
        "searchTerm": keyword,
        "pageNumber": 1,
        "pageSize": 100,
        "regulatoryStatus": "Removed",
    }
    resp = requests.get(CCNI_SEARCH, params=params, headers=HEADERS, timeout=20)
    if resp.status_code == 404:
        logger.info("CCNI API endpoint not available at this URL")
        return []
    resp.raise_for_status()
    data = resp.json()
    return data.get("charities", []) or data.get("results", []) or []


def normalise_ccni_record(charity: dict) -> dict:
    """Convert CCNI record to pipeline schema."""
    name = charity.get("charityName") or charity.get("name", "")
    number = str(charity.get("registrationNumber") or charity.get("id", ""))
    postcode = charity.get("postcode", "")
    dissolved = charity.get("dateDissolved") or charity.get("removedDate", "")

    year = None
    if dissolved:
        try:
            year = int(str(dissolved)[:4])
        except (ValueError, TypeError):
            pass

    return {
        "id":                 None,
        "church_name":        name,
        "former_denomination":None,
        "address":            charity.get("address", ""),
        "city":               charity.get("city") or charity.get("town", ""),
        "local_authority":    charity.get("localAuthority", ""),
        "region":             "Northern Ireland",
        "nation":             "Northern Ireland",
        "latitude":           None,
        "longitude":          None,
        "conversion_type":    "unknown",
        "conversion_subtype": "unknown",
        "current_name":       None,
        "year_converted":     year,
        "decade":             f"{(year//10)*10}s" if year else None,
        "source":             "ccni",
        "source_url":         f"https://www.charitycommissionni.org.uk/charity-details/?regId={number}",
        "confidence_score":   0.72,
        "notes":              f"CCNI charity #{number}. Dissolved: {dissolved}",
    }


def extract_ccni() -> pd.DataFrame:
    """Pull deregistered church charities from CCNI (Northern Ireland)."""
    all_records = []
    seen = set()

    for keyword in CHURCH_KEYWORDS[:6]:
        logger.info("CCNI: searching '%s'", keyword)
        try:
            charities = search_ccni(keyword)
        except Exception as e:
            logger.error("CCNI search failed for '%s': %s", keyword, e)
            continue

        for charity in charities:
            number = str(charity.get("registrationNumber") or
                        charity.get("id", ""))
            if number in seen:
                continue
            seen.add(number)

            name = charity.get("charityName") or charity.get("name", "")
            if not any(kw in name.lower() for kw in CHURCH_KEYWORDS):
                continue

            all_records.append(normalise_ccni_record(charity))
        time.sleep(0.5)

    logger.info("CCNI: %d deregistered church charities", len(all_records))
    if not all_records:
        return pd.DataFrame(columns=MASTER_COLUMNS)
    return pd.DataFrame(all_records, columns=MASTER_COLUMNS)


# ─── COMBINED EXTRACT ─────────────────────────────────────────────────────────

def extract() -> pd.DataFrame:
    """Run both OSCR and CCNI extractions and combine."""
    logger.info("=== OSCR (Scotland) ===")
    df_oscr = extract_oscr()
    logger.info("OSCR: %d records", len(df_oscr))

    logger.info("=== CCNI (Northern Ireland) ===")
    df_ccni = extract_ccni()
    logger.info("CCNI: %d records", len(df_ccni))

    if df_oscr.empty and df_ccni.empty:
        logger.warning(
            "No records from OSCR or CCNI.\n"
            "These APIs may require different endpoints or bulk downloads.\n"
            "Try manual download from:\n"
            "  OSCR: https://www.oscr.org.uk/about-charities/search-the-register/charity-register-download/\n"
            "  CCNI: https://www.charitycommissionni.org.uk/about-nics/manage-data/"
        )
        return pd.DataFrame(columns=MASTER_COLUMNS)

    combined = pd.concat([df_oscr, df_ccni], ignore_index=True)
    logger.info(
        "Scotland + Northern Ireland: %d total records "
        "(%d Scottish, %d NI)",
        len(combined), len(df_oscr), len(df_ccni)
    )
    return combined


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    df = extract()
    print(f"\nTotal Scotland + NI records: {len(df)}")
    if not df.empty:
        print(df[["church_name", "city", "nation", "year_converted"]].head(20))
        df.to_csv("data/raw/oscr_ccni_raw.csv", index=False)
        print("Saved to data/raw/oscr_ccni_raw.csv")