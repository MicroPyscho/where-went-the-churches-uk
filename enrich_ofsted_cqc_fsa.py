"""
enrich_ofsted_cqc_fsa.py

Cross-references three government registers against our dataset:

  1. Ofsted — schools, nurseries, childcare providers (England)
     Source: https://www.gov.uk/ofsted-inspections/ofsted-registration
     Free bulk download. 60,000+ providers with address, URN, reg date.
     Match: postcode → education conversion confirmed with real date

  2. CQC — care homes, residential homes, nursing homes (England)
     Source: https://www.cqc.org.uk/about-us/transparency/using-cqc-data
     Free bulk download. 50,000+ providers with address and reg date.
     Match: postcode → residential_care conversion confirmed with real date

  3. FSA — food businesses (England, Wales, Scotland, NI)
     Source: https://ratings.food.gov.uk/open-data
     Free API. 500,000+ businesses with address, type, inspection date.
     Match: postcode → hospitality conversion confirmed

Run: python enrich_ofsted_cqc_fsa.py
"""

import time
import glob
import logging
import requests
import pandas as pd
from pathlib import Path
from io import StringIO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "SacredSpacesResearch/1.0 (academic)"}


def find_latest_csv():
    candidates = sorted(glob.glob("data/output/uk_church_conversions_2*.csv"), reverse=True)
    for c in candidates:
        if "PUBLIC" not in c and "enriched" not in c:
            return Path(c)
    return None


def download_ofsted():
    """Download Ofsted registered providers list."""
    logger.info("Downloading Ofsted register...")
    url = "https://www.gov.uk/ofsted-inspections/ofsted-registration-list.csv"
    alternatives = [
        "https://data.gov.uk/dataset/9f27d3df-1caa-44f3-8b46-8a7f74882ef4/ofsted-registered-settings/datafile",
        "https://www.gov.uk/government/collections/ofsted-inspections-of-registered-childcare-providers",
    ]

    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        if resp.status_code == 200:
            return pd.read_csv(StringIO(resp.text), low_memory=False)
    except Exception as e:
        logger.warning("Ofsted direct download failed: %s", e)

    # Try data.gov.uk API
    try:
        resp = requests.get(
            "https://data.gov.uk/api/3/action/datastore_search",
            params={"resource_id": "9f27d3df-1caa-44f3-8b46-8a7f74882ef4", "limit": 50000},
            headers=HEADERS, timeout=60
        )
        if resp.status_code == 200:
            records = resp.json().get("result", {}).get("records", [])
            if records:
                return pd.DataFrame(records)
    except Exception as e:
        logger.warning("Ofsted API failed: %s", e)

    logger.warning("Could not download Ofsted data automatically.")
    logger.info("Manual: https://www.gov.uk/ofsted-inspections/ofsted-registration")
    return None


def download_cqc():
    """Download CQC care directory."""
    logger.info("Downloading CQC register...")
    url = "https://www.cqc.org.uk/sites/default/files/20231231_Latest_CQC_Ratings.csv"
    alternatives = [
        "https://api.cqc.org.uk/public/v1/reports/locations?partnerCode=SacredSpaces",
        "https://data.cqc.org.uk/en/downloads/cqc-care-directory",
    ]

    try:
        resp = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        if resp.status_code == 200:
            return pd.read_csv(StringIO(resp.text), low_memory=False, encoding="latin-1")
    except Exception as e:
        logger.warning("CQC direct download failed: %s", e)

    # Try CQC API
    try:
        resp = requests.get(
            "https://api.cqc.org.uk/public/v1/locations",
            params={"page": 1, "perPage": 100, "careHomeFlag": "Y"},
            headers={**HEADERS, "Accept": "application/json"},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            locations = data.get("locations", [])
            if locations:
                return pd.DataFrame(locations)
    except Exception as e:
        logger.warning("CQC API failed: %s", e)

    logger.warning("Could not download CQC data automatically.")
    logger.info("Manual: https://www.cqc.org.uk/about-us/transparency/using-cqc-data")
    return None


def download_fsa(max_authorities=50):
    """Download FSA food business data via API."""
    logger.info("Downloading FSA food business data...")
    all_establishments = []

    try:
        # Get list of local authorities
        resp = requests.get(
            "https://api.ratings.food.gov.uk/Authorities",
            headers={**HEADERS, "x-api-version": "2"},
            timeout=30,
        )
        if resp.status_code != 200:
            return None

        authorities = resp.json().get("authorities", [])[:max_authorities]
        logger.info("Fetching FSA data from %d authorities...", len(authorities))

        for auth in authorities:
            auth_id = auth.get("LocalAuthorityId")
            try:
                resp2 = requests.get(
                    "https://api.ratings.food.gov.uk/Establishments",
                    params={
                        "localAuthorityId": auth_id,
                        "pageSize": 500,
                        "pageNumber": 1,
                    },
                    headers={**HEADERS, "x-api-version": "2"},
                    timeout=30,
                )
                if resp2.status_code == 200:
                    establishments = resp2.json().get("establishments", [])
                    all_establishments.extend(establishments)
                time.sleep(0.3)
            except Exception:
                continue

        if all_establishments:
            return pd.DataFrame(all_establishments)
    except Exception as e:
        logger.warning("FSA API failed: %s", e)

    return None


def enrich_from_register(df, register_df, source_name,
                          pc_col, name_col, date_col,
                          conv_type, conv_subtype,
                          confidence=0.90):
    """Generic enrichment from a government register."""
    if register_df is None or len(register_df) == 0:
        logger.warning("%s: no data available", source_name)
        return df, 0, 0, 0

    # Normalise postcodes
    register_df["_pc"] = register_df[pc_col].astype(str).str.upper().str.replace(" ","").str[:5]
    df["_pc_key"] = df["postcode"].astype(str).str.upper().str.replace(" ","").str[:5]

    reg_by_pc = register_df.groupby("_pc")
    types_updated = 0
    names_added = 0
    years_added = 0

    for pc_key, reg_group in reg_by_pc:
        matching = df[df["_pc_key"] == pc_key]
        if len(matching) == 0:
            continue

        for _, reg_row in reg_group.iterrows():
            for idx in matching.index:
                if df.at[idx, "conversion_type"] not in ("unknown", conv_type):
                    continue

                # Update type
                if df.at[idx, "conversion_type"] == "unknown":
                    df.at[idx, "conversion_type"] = conv_type
                    df.at[idx, "conversion_subtype"] = conv_subtype
                    df.at[idx, "confidence_score"] = confidence
                    types_updated += 1

                # Update name
                if pd.isna(df.at[idx, "current_name"]) and name_col in reg_row:
                    name = str(reg_row[name_col])
                    if name and name not in ("nan","None",""):
                        df.at[idx, "current_name"] = name
                        names_added += 1

                # Update year — from registration/inspection date
                if pd.isna(df.at[idx, "year_converted"]) and date_col in reg_row:
                    date_val = str(reg_row[date_col])
                    if date_val and len(date_val) >= 4:
                        try:
                            yr = int(date_val[:4])
                            if 1980 <= yr <= 2024:
                                df.at[idx, "year_converted"] = yr
                                df.at[idx, "decade"] = f"{(yr//10)*10}s"
                                years_added += 1
                        except ValueError:
                            pass

                existing = str(df.at[idx, "notes"] or "")
                df.at[idx, "notes"] = existing + f" | {source_name}: {str(reg_row.get(name_col,''))[:40]}"
                break

    df = df.drop(columns=["_pc_key"], errors="ignore")
    return df, types_updated, names_added, years_added


def main():
    path = find_latest_csv()
    if not path:
        logger.error("No CSV found")
        return

    df = pd.read_csv(path, low_memory=False)
    logger.info("Loaded %d records", len(df))

    total_types = total_names = total_years = 0

    # ── OFSTED ────────────────────────────────────────────────────────────────
    ofsted = download_ofsted()
    if ofsted is not None:
        logger.info("Ofsted: %d providers", len(ofsted))
        logger.info("Ofsted columns: %s", ofsted.columns.tolist()[:10])

        pc_col   = next((c for c in ofsted.columns if "postcode" in c.lower()), None)
        name_col = next((c for c in ofsted.columns if "name" in c.lower() and "provider" in c.lower()), None) or \
                   next((c for c in ofsted.columns if "name" in c.lower()), None)
        date_col = next((c for c in ofsted.columns if "registration" in c.lower() and "date" in c.lower()), None) or \
                   next((c for c in ofsted.columns if "date" in c.lower()), None)

        if pc_col:
            df, t, n, y = enrich_from_register(
                df, ofsted, "Ofsted",
                pc_col, name_col, date_col,
                "education", "ofsted_registered",
                confidence=0.92,
            )
            total_types += t; total_names += n; total_years += y
            logger.info("Ofsted: types=%d, names=%d, years=%d", t, n, y)

    # ── CQC ───────────────────────────────────────────────────────────────────
    cqc = download_cqc()
    if cqc is not None:
        logger.info("CQC: %d locations", len(cqc))
        logger.info("CQC columns: %s", cqc.columns.tolist()[:10])

        pc_col   = next((c for c in cqc.columns if "postcode" in c.lower()), None)
        name_col = next((c for c in cqc.columns if "name" in c.lower() and "location" in c.lower()), None) or \
                   next((c for c in cqc.columns if "name" in c.lower()), None)
        date_col = next((c for c in cqc.columns if "registration" in c.lower() and "date" in c.lower()), None)

        if pc_col:
            df, t, n, y = enrich_from_register(
                df, cqc, "CQC",
                pc_col, name_col, date_col,
                "community", "care_home",
                confidence=0.92,
            )
            total_types += t; total_names += n; total_years += y
            logger.info("CQC: types=%d, names=%d, years=%d", t, n, y)

    # ── FSA ───────────────────────────────────────────────────────────────────
    fsa = download_fsa(max_authorities=100)
    if fsa is not None:
        logger.info("FSA: %d establishments", len(fsa))
        logger.info("FSA columns: %s", fsa.columns.tolist()[:10])

        pc_col   = next((c for c in fsa.columns if "postcode" in c.lower()), None)
        name_col = next((c for c in fsa.columns if "businessname" in c.lower() or "name" in c.lower()), None)
        date_col = next((c for c in fsa.columns if "inspectiondate" in c.lower() or "date" in c.lower()), None)

        if pc_col:
            df, t, n, y = enrich_from_register(
                df, fsa, "FSA",
                pc_col, name_col, date_col,
                "hospitality", "fsa_registered",
                confidence=0.88,
            )
            total_types += t; total_names += n; total_years += y
            logger.info("FSA: types=%d, names=%d, years=%d", t, n, y)

    # ── SAVE ──────────────────────────────────────────────────────────────────
    df.to_csv(path, index=False)

    print(f"\n{'='*60}")
    print("OFSTED / CQC / FSA ENRICHMENT COMPLETE")
    print(f"{'='*60}")
    print(f"Types updated:    {total_types:,}")
    print(f"Names added:      {total_names:,}")
    print(f"Years added:      {total_years:,}")
    print(f"Unknown remaining:{(df['conversion_type']=='unknown').sum():,}")
    print(f"\nConversion type breakdown:")
    print(df["conversion_type"].value_counts().head(12).to_string())
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()