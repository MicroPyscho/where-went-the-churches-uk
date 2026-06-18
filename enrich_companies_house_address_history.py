"""
enrich_companies_house_address_history.py

Queries Companies House API for registered address change history.
Uses the date a company FIRST registered at a church address —
not the company incorporation date — as a proxy for conversion year.

Key distinction (as flagged by researcher):
  - Incorporation date = when company was FOUNDED (unreliable for conversion year)
  - Address registration date = when company MOVED TO this address (reliable)

Only fills year_converted where currently null.
Only uses address dates that post-date the company incorporation
by at least 1 year (filtering out companies that registered at
this address from the very start — those are ambiguous).

Run: python enrich_companies_house_address_history.py
"""

import time
import glob
import logging
import requests
import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY", "")
BASE_URL = "https://api.company-information.service.gov.uk"


def find_latest_csv():
    candidates = sorted(glob.glob("data/output/uk_church_conversions_2*.csv"), reverse=True)
    for c in candidates:
        if "PUBLIC" not in c and "enriched" not in c:
            return Path(c)
    return None


def get_address_history(company_number, api_key):
    """
    Get registered address filing history for a company.
    Returns list of (date, address) tuples sorted oldest first.
    """
    try:
        resp = requests.get(
            f"{BASE_URL}/company/{company_number}/filing-history",
            params={"category": "address", "items_per_page": 10},
            auth=(api_key, ""),
            timeout=15,
        )
        if resp.status_code != 200:
            return []

        items = resp.json().get("items", [])
        address_changes = []
        for item in items:
            date = item.get("date", "")
            desc = item.get("description", "")
            if date and ("address" in desc.lower() or "registered office" in desc.lower()):
                address_changes.append(date)

        return sorted(address_changes)

    except Exception:
        return []


def get_company_details(company_number, api_key):
    """Get company incorporation date and current address."""
    try:
        resp = requests.get(
            f"{BASE_URL}/company/{company_number}",
            auth=(api_key, ""),
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "incorporated": data.get("date_of_creation",""),
                "postcode": data.get("registered_office_address",{}).get("postal_code",""),
                "status": data.get("company_status",""),
            }
    except Exception:
        pass
    return {}


def main():
    if not API_KEY:
        logger.error("No COMPANIES_HOUSE_API_KEY in .env file")
        return

    path = find_latest_csv()
    if not path:
        logger.error("No CSV found")
        return

    logger.info("Loading %s", path)
    df = pd.read_csv(path, low_memory=False)
    df["year_converted"] = pd.to_numeric(df["year_converted"], errors="coerce")
    logger.info("Loaded %d records", len(df))

    # Target: has company_number but no year_converted
    targets = df[
        df["company_number"].notna() &
        df["year_converted"].isna()
    ].copy()

    logger.info("Records with company number but no year: %d", len(targets))

    years_added = 0
    errors = 0
    skipped_ambiguous = 0

    for i, (idx, row) in enumerate(targets.iterrows()):
        company_num = str(row["company_number"]).strip()
        if not company_num or company_num in ("nan","None",""):
            continue

        try:
            # Get company details
            details = get_company_details(company_num, API_KEY)
            incorporated = details.get("incorporated","")
            company_postcode = details.get("postcode","").upper().replace(" ","")
            record_postcode = str(row.get("postcode","") or "").upper().replace(" ","")

            # Verify postcode still matches (company may have moved)
            if company_postcode and record_postcode:
                if company_postcode[:5] != record_postcode[:5]:
                    # Company has moved away from church address
                    skipped_ambiguous += 1
                    continue

            # Get address change history
            address_changes = get_address_history(company_num, API_KEY)

            best_year = None

            if address_changes:
                # Use the FIRST address change date after incorporation
                # This is when they moved TO this address
                for change_date in address_changes:
                    try:
                        yr = int(str(change_date)[:4])
                        incorp_yr = int(str(incorporated)[:4]) if incorporated else 0

                        # Only use if:
                        # 1. Plausible conversion year
                        # 2. Address change is at least 1 year after incorporation
                        #    (ruling out companies founded at this address)
                        if 1980 <= yr <= 2024 and (yr - incorp_yr) >= 1:
                            best_year = yr
                            break
                    except ValueError:
                        continue

            if best_year:
                df.at[idx, "year_converted"] = best_year
                df.at[idx, "decade"] = f"{(best_year//10)*10}s"
                existing = str(df.at[idx, "notes"] or "")
                df.at[idx, "notes"] = (
                    existing +
                    f" | CH_address_change:{best_year} (incorporated:{incorporated[:4] if incorporated else '?'})"
                )
                years_added += 1
            else:
                skipped_ambiguous += 1

        except Exception as e:
            errors += 1
            logger.debug("Error for %s: %s", company_num, e)

        # Save every 200 records
        if (i + 1) % 200 == 0:
            df.to_csv(path, index=False)
            logger.info(
                "[%d/%d] Years added: %d | Skipped ambiguous: %d | Errors: %d",
                i+1, len(targets), years_added, skipped_ambiguous, errors
            )

        time.sleep(0.5)  # CH API rate limit

    df.to_csv(path, index=False)

    print(f"\n{'='*60}")
    print("COMPANIES HOUSE ADDRESS HISTORY COMPLETE")
    print(f"{'='*60}")
    print(f"Years added:          {years_added:,}")
    print(f"Skipped (ambiguous):  {skipped_ambiguous:,}")
    print(f"Errors:               {errors:,}")
    print(f"\nYear coverage now: {df['year_converted'].notna().sum():,} / {len(df):,}")
    print(f"\nYear distribution (top 15):")
    real = df[df["year_converted"].notna()]
    print(real["year_converted"].value_counts().sort_index().head(15).to_string())
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()