"""
enrich_charity_commission_islamic.py

Queries the Charity Commission API for Islamic/Muslim charities
and cross-references by postcode against our dataset.

For each match:
- If conversion_type is unknown → updates to 'mosque'
- Adds current_name from charity name
- Adds year_converted from charity registration date
  (only if registration date is AFTER incorporation — 
   meaning this is when they moved into the building,
   not when the organisation was founded)

Also queries for other faith-based charities:
- Sikh (gurdwara)
- Hindu (mandir)  
- Buddhist
- Jewish (synagogue)

Run: python enrich_charity_commission_islamic.py
"""

import time
import glob
import logging
import requests
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CHARITY_API = "https://api.charitycommission.gov.uk/register/api"
HEADERS = {"User-Agent": "SacredSpacesResearch/1.0 (academic research)"}

# Search terms mapped to conversion types
FAITH_SEARCHES = [
    ("mosque",          "mosque",           ["mosque","masjid","islamic","muslim faith","advancement of islam"]),
    ("south_asian_faith","sikh_gurdwara",   ["gurdwara","sikh","advancement of the sikh"]),
    ("south_asian_faith","hindu_mandir",    ["mandir","hindu","advancement of the hindu"]),
    ("eastern_philosophy","buddhist_centre",["buddhist","buddhism","advancement of buddhism"]),
    ("other_faith",     "jewish_synagogue", ["synagogue","jewish","advancement of the jewish"]),
]


def find_latest_csv():
    candidates = sorted(glob.glob("data/output/uk_church_conversions_2*.csv"), reverse=True)
    for c in candidates:
        if "PUBLIC" not in c and "enriched" not in c:
            return Path(c)
    return None


def search_charities(keyword, max_results=500):
    """Search Charity Commission for charities matching keyword."""
    charities = []
    try:
        # Use the public search endpoint
        resp = requests.get(
            "https://api.charitycommission.gov.uk/register/api/allcharities",
            params={
                "q": keyword,
                "size": min(max_results, 500),
                "from": 0,
            },
            headers=HEADERS,
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            charities = data.get("charities", data.get("hits", []))
        else:
            # Try alternative endpoint
            resp2 = requests.get(
                f"https://api.charitycommission.gov.uk/register/api/charitySearch/{keyword}",
                headers=HEADERS,
                timeout=30,
            )
            if resp2.status_code == 200:
                charities = resp2.json().get("charities", [])
    except Exception as e:
        logger.warning("Search failed for '%s': %s", keyword, e)
    return charities


def get_charity_details(regno):
    """Get detailed charity info including registered address."""
    try:
        resp = requests.get(
            f"https://api.charitycommission.gov.uk/register/api/charity/{regno}",
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning("Detail fetch failed for %s: %s", regno, e)
    return None


def main():
    path = find_latest_csv()
    if not path:
        logger.error("No CSV found")
        return

    logger.info("Loading %s", path)
    df = pd.read_csv(path, low_memory=False)
    logger.info("Loaded %d records", len(df))

    # Build postcode lookup for fast matching
    # Key: first 5 chars of postcode (outward + first inward digit)
    df["_pc_key"] = df["postcode"].str.upper().str.replace(" ","").str[:5]
    pc_lookup = df[df["_pc_key"].notna()].groupby("_pc_key").indices

    total_updated = 0
    results_log = []

    for conv_type, conv_subtype, keywords in FAITH_SEARCHES:
        logger.info("Searching for %s charities...", conv_type)
        charity_records = []

        for keyword in keywords:
            charities = search_charities(keyword, max_results=500)
            logger.info("  '%s': %d results", keyword, len(charities))
            charity_records.extend(charities)
            time.sleep(0.5)

        if not charity_records:
            logger.warning("No charities found for %s", conv_type)
            continue

        logger.info("Processing %d %s charity records...", len(charity_records), conv_type)
        matched = 0

        for charity in charity_records:
            # Extract postcode from charity record
            # Different API versions use different field names
            charity_postcode = (
                charity.get("postcode") or
                charity.get("registered_address", {}).get("postcode") or
                charity.get("contact_address", {}).get("postcode") or ""
            )
            charity_name = (
                charity.get("charity_name") or
                charity.get("name") or ""
            )
            charity_regno = (
                charity.get("registered_charity_number") or
                charity.get("regno") or
                charity.get("charity_number") or ""
            )
            reg_date = (
                charity.get("date_of_registration") or
                charity.get("registration_date") or ""
            )

            if not charity_postcode:
                continue

            # Normalise postcode for matching
            pc_key = charity_postcode.upper().replace(" ","")[:5]

            if pc_key not in pc_lookup:
                continue

            # Check matching records in our dataset
            matching_indices = pc_lookup[pc_key]
            for idx in matching_indices:
                row = df.iloc[idx]

                # Only update unknowns OR confirm existing mosque records
                if row["conversion_type"] not in ("unknown", conv_type):
                    continue

                # Validate: charity name should suggest religious use
                name_lower = charity_name.lower()
                if not any(kw in name_lower for kw in [
                    "mosque","masjid","islamic","muslim","gurdwara","sikh",
                    "mandir","hindu","buddhist","synagogue","jewish","temple",
                    "faith","worship","prayer","religious"
                ]):
                    continue

                # Update conversion type
                real_idx = df.index[idx]
                if df.at[real_idx, "conversion_type"] == "unknown":
                    df.at[real_idx, "conversion_type"] = conv_type
                    df.at[real_idx, "conversion_subtype"] = conv_subtype
                    df.at[real_idx, "confidence_score"] = 0.88

                # Add current name if missing
                if pd.isna(df.at[real_idx, "current_name"]) and charity_name:
                    df.at[real_idx, "current_name"] = charity_name

                # Add registration date as year_converted ONLY if:
                # 1. year_converted is currently null
                # 2. reg_date is a plausible conversion year (1960-2024)
                # NOTE: reg_date is when charity registered at THIS address,
                # not when the organisation was founded — more reliable
                if pd.isna(df.at[real_idx, "year_converted"]) and reg_date:
                    try:
                        yr = int(str(reg_date)[:4])
                        if 1960 <= yr <= 2024:
                            df.at[real_idx, "year_converted"] = yr
                            df.at[real_idx, "decade"] = f"{(yr//10)*10}s"
                    except (ValueError, TypeError):
                        pass

                # Add charity number to notes
                existing_notes = str(df.at[real_idx, "notes"] or "")
                df.at[real_idx, "notes"] = (
                    existing_notes +
                    f" | CharityCommission: {charity_regno} ({charity_name[:40]})"
                )

                matched += 1
                results_log.append({
                    "postcode": charity_postcode,
                    "charity_name": charity_name,
                    "charity_regno": charity_regno,
                    "conv_type": conv_type,
                    "reg_date": reg_date,
                })

                break  # One match per charity

        logger.info("Matched %d %s records", matched, conv_type)
        total_updated += matched
        time.sleep(1)

    # Save
    df = df.drop(columns=["_pc_key"], errors="ignore")
    df.to_csv(path, index=False)

    print(f"\n{'='*60}")
    print(f"CHARITY COMMISSION ENRICHMENT COMPLETE")
    print(f"{'='*60}")
    print(f"Total records updated: {total_updated:,}")
    print(f"\nMosque records now: {(df['conversion_type']=='mosque').sum()}")
    print(f"South Asian faith records: {(df['conversion_type']=='south_asian_faith').sum()}")
    print(f"Unknown remaining: {(df['conversion_type']=='unknown').sum():,}")

    if results_log:
        log_df = pd.DataFrame(results_log)
        log_df.to_csv("data/output/charity_commission_matches.csv", index=False)
        print(f"\nMatch log saved: data/output/charity_commission_matches.csv")
        print(f"\nSample matches:")
        print(log_df.head(10).to_string())

    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()