"""
enrich_companies_house.py

Companies House cross-reference enrichment.

For each record where we have a buyer name (from Land Registry) or
a charity name (from Charity Commission), look up the organisation
on Companies House to get:
  - Company type (charity, limited company, LLP, CIC etc.)
  - SIC code (industry — 94910 = religious organisations)
  - Country of incorporation (reveals foreign-origin orgs)
  - Date incorporated
  - Director names and nationalities

API: https://developer.company-information.service.gov.uk/
Free API key required — register at:
https://developer.company-information.service.gov.uk/

SIC codes relevant to this project:
  94910 — Activities of religious organisations
  94990 — Activities of other membership organisations NEC
  85100 — Pre-primary education (nurseries in former churches)
  86210 — General medical practice activities (GP surgeries)
  56101 — Licensed restaurants
  56302 — Public houses and bars
  93110 — Operation of sports facilities
  68100 — Buying and selling of own real estate

Usage:
    python enrich_companies_house.py --max-records 500
"""

import logging
import time
import os
import json
import glob
import re
from pathlib import Path
from typing import Optional
import requests
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

CH_BASE = "https://api.company-information.service.gov.uk"
CHECKPOINT_PATH = Path("data/output/companies_house_checkpoint.json")

# SIC codes → our conversion taxonomy
SIC_TO_TYPE = {
    "94910": ("other_christian", "other_christian_general"),
    "94990": ("community", "community_centre"),
    "56101": ("hospitality", "restaurant"),
    "56102": ("hospitality", "restaurant"),
    "56302": ("hospitality", "pub"),
    "56301": ("hospitality", "bar"),
    "93110": ("sport_leisure", "sport_leisure_general"),
    "93130": ("sport_leisure", "gym_fitness"),
    "85100": ("education", "nursery"),
    "85200": ("education", "school"),
    "86210": ("community", "nhs_health_centre"),
    "68100": ("residential", "converted_flats"),
    "68209": ("residential", "converted_flats"),
    "85590": ("education", "community_education"),
    "88990": ("community", "charity_hub"),
    "90010": ("arts_culture", "theatre"),
    "90020": ("arts_culture", "arts_centre"),
    "59200": ("arts_culture", "recording_studio"),
}

# Country of incorporation → likely denomination/origin
COUNTRY_HINTS = {
    "nigeria":      ("african_diaspora_church", "african_church_general"),
    "ghana":        ("african_diaspora_church", "church_of_pentecost"),
    "brazil":       ("african_diaspora_church", "uckg"),
    "south korea":  ("east_asian_church", "korean_presbyterian"),
    "pakistan":     ("mosque", "sunni_deobandi"),
    "bangladesh":   ("mosque", "sunni_deobandi"),
    "india":        ("south_asian_faith", "south_asian_general"),
    "australia":    ("new_religious_movement", "scientology"),
}


def get_api_key() -> Optional[str]:
    key = os.getenv("COMPANIES_HOUSE_API_KEY")
    if not key:
        logger.warning(
            "COMPANIES_HOUSE_API_KEY not set in .env\n"
            "Register free at: https://developer.company-information.service.gov.uk/"
        )
    return key


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=20))
def search_company(name: str, api_key: str) -> Optional[dict]:
    """Search Companies House for an organisation by name."""
    resp = requests.get(
        f"{CH_BASE}/search/companies",
        params={"q": name, "items_per_page": 5},
        auth=(api_key, ""),
        timeout=15,
    )
    if resp.status_code in (401, 403):
        logger.warning("Companies House: auth failed — check API key")
        return None
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return items[0] if items else None


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=3, max=15))
def get_company_detail(company_number: str, api_key: str) -> Optional[dict]:
    """Get full company detail including SIC codes and officers."""
    resp = requests.get(
        f"{CH_BASE}/company/{company_number}",
        auth=(api_key, ""),
        timeout=15,
    )
    if resp.status_code in (404, 401):
        return None
    resp.raise_for_status()
    return resp.json()


def classify_from_company(detail: dict) -> Optional[tuple[str, str]]:
    """Infer conversion type from Companies House SIC codes."""
    sic_codes = detail.get("sic_codes", [])
    for sic in sic_codes:
        if sic in SIC_TO_TYPE:
            return SIC_TO_TYPE[sic]

    # Check country of incorporation
    country = str(
        detail.get("registered_office_address", {}).get("country", "") or
        detail.get("foreign_company_details", {}).get("originating_registry", {}).get("country", "")
    ).lower()
    for country_key, result in COUNTRY_HINTS.items():
        if country_key in country:
            return result

    return None


def extract_org_name(row: pd.Series) -> Optional[str]:
    """Extract organisation name from current_name, notes, or church_name."""
    for field in ["current_name", "church_name"]:
        name = str(row.get(field, "") or "")
        if name and name not in ("nan", "None", ""):
            return name[:100]
    # Try extracting from notes
    notes = str(row.get("notes", "") or "")
    match = re.search(r"Planning: ([A-Z0-9/]+)", notes)
    if match:
        return None  # Planning ref not a company name
    return None


def load_checkpoint() -> set:
    if not CHECKPOINT_PATH.exists():
        return set()
    try:
        with open(CHECKPOINT_PATH) as f:
            return set(json.load(f).get("processed_ids", []))
    except Exception:
        return set()


def save_checkpoint(processed: set, stats: dict):
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump({
            "processed_ids": list(processed),
            "stats": stats,
            "last_updated": pd.Timestamp.now().isoformat(),
        }, f)


def find_latest_csv() -> Optional[Path]:
    candidates = sorted(
        glob.glob("data/output/uk_church_conversions_2*.csv"),
        reverse=True
    )
    for c in candidates:
        if "PUBLIC" not in c and "enriched" not in c:
            return Path(c)
    return None


def enrich(
    input_path: Optional[str] = None,
    max_records: int = 500,
    batch_size: int = 50,
    dry_run: bool = False,
):
    api_key = get_api_key()
    if not api_key:
        logger.error(
            "Cannot proceed without COMPANIES_HOUSE_API_KEY.\n"
            "Add to .env: COMPANIES_HOUSE_API_KEY=your_key_here"
        )
        return

    path = Path(input_path) if input_path else find_latest_csv()
    if not path or not path.exists():
        logger.error("No pipeline CSV found.")
        return

    logger.info("Loading %s", path)
    df = pd.read_csv(path, low_memory=False)

    for col in ["company_number", "company_type", "sic_code",
                "incorporated_country", "conversion_type",
                "conversion_subtype", "notes"]:
        if col not in df.columns:
            df[col] = None
        df[col] = df[col].astype(object)

    logger.info("Loaded %d records", len(df))
    processed = load_checkpoint()

    # Target records with a name to look up
    targets = df[
        ~df["id"].astype(str).isin(processed) &
        (df["current_name"].notna() | df["church_name"].notna())
    ].head(max_records)

    logger.info("Querying %d records", len(targets))
    stats = {
        "queried": 0, "found": 0, "type_upgraded": 0,
        "not_found": 0, "errors": 0
    }
    batch_count = 0

    for idx, row in targets.iterrows():
        record_id = str(row.get("id", idx))
        org_name = extract_org_name(row)

        if not org_name:
            processed.add(record_id)
            batch_count += 1
            continue

        try:
            company = search_company(org_name, api_key)
            stats["queried"] += 1
        except Exception as e:
            logger.debug("CH search failed for '%s': %s", org_name, e)
            stats["errors"] += 1
            processed.add(record_id)
            time.sleep(1)
            batch_count += 1
            continue

        if not company:
            stats["not_found"] += 1
            processed.add(record_id)
            batch_count += 1
            time.sleep(0.5)
            continue

        company_number = company.get("company_number", "")
        stats["found"] += 1

        # Get full detail for SIC codes
        detail = None
        if company_number:
            try:
                detail = get_company_detail(company_number, api_key)
                time.sleep(0.3)
            except Exception:
                pass

        if detail:
            df.at[idx, "company_number"] = company_number
            df.at[idx, "company_type"] = detail.get("type", "")
            sic_codes = detail.get("sic_codes", [])
            if sic_codes:
                df.at[idx, "sic_code"] = ",".join(sic_codes)

            # Country of incorporation
            country = (
                detail.get("registered_office_address", {}).get("country", "") or
                detail.get("foreign_company_details", {}).get(
                    "originating_registry", {}).get("country", "")
            )
            if country:
                df.at[idx, "incorporated_country"] = country

            # Upgrade conversion type if currently unknown
            if str(row.get("conversion_type", "")) in ("unknown", "", "nan"):
                result = classify_from_company(detail)
                if result:
                    df.at[idx, "conversion_type"] = result[0]
                    df.at[idx, "conversion_subtype"] = result[1]
                    stats["type_upgraded"] += 1

            # Add to notes
            existing = str(df.at[idx, "notes"] or "")
            df.at[idx, "notes"] = (
                existing +
                f" | Companies House: {company_number} "
                f"({detail.get('type','')} SIC:{','.join(sic_codes)})"
            )

        processed.add(record_id)
        batch_count += 1

        if batch_count >= batch_size:
            if not dry_run:
                df.to_csv(path, index=False)
                save_checkpoint(processed, stats)
            logger.info(
                "[%d] Batch saved | found: %d | upgraded: %d | errors: %d",
                stats["queried"], stats["found"],
                stats["type_upgraded"], stats["errors"]
            )
            batch_count = 0

        time.sleep(0.5)

    if batch_count > 0 and not dry_run:
        df.to_csv(path, index=False)
        save_checkpoint(processed, stats)

    print("\n=== COMPANIES HOUSE ENRICHMENT COMPLETE ===")
    print(f"Queried:        {stats['queried']:,}")
    print(f"Found:          {stats['found']:,}")
    print(f"Types upgraded: {stats['type_upgraded']:,}")
    print(f"Not found:      {stats['not_found']:,}")
    print(f"Errors:         {stats['errors']:,}")


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="Path to CSV")
    parser.add_argument("--max-records", type=int, default=500)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    if args.reset and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    enrich(
        input_path=args.input,
        max_records=args.max_records,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )