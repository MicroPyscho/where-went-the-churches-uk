"""
extractors/ofsted_cqc_extractor.py

Ofsted and CQC cross-reference enrichment.

Confirms and upgrades conversion_subtype for:
  - School / nursery conversions → Ofsted registration number, rating
  - Care home / GP surgery conversions → CQC registration, rating

Both are free public APIs with no key required.

Ofsted API: https://api.ofsted.gov.uk/v1/
  Providers registered with Ofsted: schools, nurseries, childminders

CQC API: https://api.cqc.org.uk/public/v1/
  Providers: care homes, GP surgeries, hospitals, dental practices

Strategy:
  For each record with conversion_type = education or community/nhs:
    1. Extract postcode from record
    2. Query Ofsted/CQC by postcode
    3. If provider found → confirm conversion, add registration number and rating
    4. Upgrade conversion_subtype to specific type (school vs nursery etc.)
"""

import logging
import time
import json
import glob
import re
from pathlib import Path
from typing import Optional
import requests
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

OFSTED_BASE = "https://api.ofsted.gov.uk/v1"
CQC_BASE    = "https://api.cqc.org.uk/public/v1"

HEADERS = {
    "User-Agent": "UKChurchConversionResearch/1.0 (academic project)",
    "Accept": "application/json",
}

OFSTED_CHECKPOINT = Path("data/output/ofsted_checkpoint.json")
CQC_CHECKPOINT    = Path("data/output/cqc_checkpoint.json")


# ─── OFSTED ──────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=20))
def search_ofsted_by_postcode(postcode: str) -> list[dict]:
    """Search Ofsted register by postcode."""
    resp = requests.get(
        f"{OFSTED_BASE}/providers",
        params={"postcode": postcode, "limit": 10},
        headers=HEADERS,
        timeout=15,
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()
    return data.get("providers", []) or data.get("data", []) or []


def classify_ofsted_provider(provider: dict) -> tuple[str, str]:
    """Map Ofsted provider type to our taxonomy."""
    ptype = str(provider.get("providerType", "") or
                provider.get("type", "")).lower()
    if "childminder" in ptype or "childcare" in ptype:
        return ("education", "nursery")
    if "school" in ptype:
        phase = str(provider.get("schoolType", "") or "").lower()
        if "primary" in phase or "infant" in phase or "junior" in phase:
            return ("education", "school")
        if "secondary" in phase:
            return ("education", "school")
        if "nursery" in phase:
            return ("education", "nursery")
        return ("education", "school")
    if "further" in ptype or "college" in ptype:
        return ("education", "college")
    return ("education", "education_general")


# ─── CQC ─────────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=20))
def search_cqc_by_postcode(postcode: str) -> list[dict]:
    """Search CQC register by postcode."""
    resp = requests.get(
        f"{CQC_BASE}/locations",
        params={"postalCode": postcode, "perPage": 10, "page": 1},
        headers=HEADERS,
        timeout=15,
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()
    return data.get("locations", []) or data.get("data", []) or []


def classify_cqc_provider(location: dict) -> tuple[str, str]:
    """Map CQC location type to our taxonomy."""
    ltype = str(location.get("type", "") or
                location.get("locationType", "")).lower()
    srv = str(location.get("gacServiceTypes", [{}])[0].get("name", "")
               if location.get("gacServiceTypes") else "").lower()

    if "care home" in ltype or "care home" in srv:
        return ("residential", "care_home")
    if "gp" in ltype or "primary medical" in srv:
        return ("community", "nhs_health_centre")
    if "hospital" in ltype:
        return ("community", "nhs_health_centre")
    if "dental" in ltype or "dental" in srv:
        return ("community", "nhs_health_centre")
    if "substance" in srv or "drug" in srv:
        return ("community", "drug_rehabilitation")
    if "mental health" in srv:
        return ("residential", "supported_housing")
    return ("community", "nhs_health_centre")


# ─── SHARED UTILITIES ─────────────────────────────────────────────────────────

def extract_postcode(row: pd.Series) -> Optional[str]:
    """Extract postcode from any field in a record."""
    for field in ["address", "notes", "source_url", "church_name"]:
        text = str(row.get(field, "") or "")
        match = re.search(
            r'\b([A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2})\b',
            text.upper()
        )
        if match:
            return match.group(1).strip()
    return None


def load_checkpoint(path: Path) -> set:
    if not path.exists():
        return set()
    try:
        with open(path) as f:
            return set(json.load(f).get("processed_ids", []))
    except Exception:
        return set()


def save_checkpoint(path: Path, processed: set, stats: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
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


# ─── MAIN ENRICHMENT ─────────────────────────────────────────────────────────

def enrich(
    input_path: Optional[str] = None,
    max_records: int = 2000,
    batch_size: int = 100,
    dry_run: bool = False,
    run_ofsted: bool = True,
    run_cqc: bool = True,
):
    """
    Enrich education and community records using Ofsted and CQC APIs.
    Only processes records where conversion_type is education or community/nhs.
    """
    path = Path(input_path) if input_path else find_latest_csv()
    if not path or not path.exists():
        logger.error("No pipeline CSV found.")
        return

    logger.info("Loading %s", path)
    df = pd.read_csv(path, low_memory=False)

    for col in ["ofsted_urn", "cqc_id", "inspection_rating",
                "conversion_type", "conversion_subtype", "notes"]:
        if col not in df.columns:
            df[col] = None
        df[col] = df[col].astype(object)

    logger.info("Loaded %d records", len(df))

    ofsted_done = load_checkpoint(OFSTED_CHECKPOINT)
    cqc_done    = load_checkpoint(CQC_CHECKPOINT)

    stats = {
        "ofsted_confirmed": 0, "cqc_confirmed": 0,
        "subtypes_upgraded": 0, "errors": 0, "no_postcode": 0
    }

    # ── OFSTED pass (education records) ──────────────────────────────────────
    if run_ofsted:
        edu_targets = df[
            df["conversion_type"].isin(["education", "community"]) &
            ~df["id"].astype(str).isin(ofsted_done)
        ].head(max_records // 2)

        logger.info("Ofsted: querying %d education/community records", len(edu_targets))
        batch_count = 0

        for idx, row in edu_targets.iterrows():
            record_id = str(row.get("id", idx))
            postcode = extract_postcode(row)

            if not postcode:
                stats["no_postcode"] += 1
                ofsted_done.add(record_id)
                continue

            try:
                providers = search_ofsted_by_postcode(postcode)
            except Exception as e:
                logger.debug("Ofsted failed for %s: %s", postcode, e)
                stats["errors"] += 1
                ofsted_done.add(record_id)
                time.sleep(1)
                continue

            if providers:
                provider = providers[0]
                urn = str(provider.get("urn") or provider.get("id", ""))
                rating = str(provider.get("overallEffectiveness") or
                            provider.get("currentRating", {}).get("overall", {}).get("rating", ""))

                df.at[idx, "ofsted_urn"] = urn
                df.at[idx, "inspection_rating"] = rating

                conv_type, conv_sub = classify_ofsted_provider(provider)
                if str(row.get("conversion_subtype", "")) in (
                    "education_general", "school", "unknown", "nan", ""
                ):
                    df.at[idx, "conversion_type"] = conv_type
                    df.at[idx, "conversion_subtype"] = conv_sub
                    stats["subtypes_upgraded"] += 1

                existing = str(df.at[idx, "notes"] or "")
                df.at[idx, "notes"] = (
                    existing +
                    f" | Ofsted URN: {urn} Rating: {rating}"
                )
                stats["ofsted_confirmed"] += 1

            ofsted_done.add(record_id)
            batch_count += 1

            if batch_count >= batch_size:
                if not dry_run:
                    df.to_csv(path, index=False)
                    save_checkpoint(OFSTED_CHECKPOINT, ofsted_done, stats)
                logger.info(
                    "Ofsted batch | confirmed: %d | upgraded: %d",
                    stats["ofsted_confirmed"], stats["subtypes_upgraded"]
                )
                batch_count = 0
            time.sleep(0.4)

        if batch_count > 0 and not dry_run:
            df.to_csv(path, index=False)
            save_checkpoint(OFSTED_CHECKPOINT, ofsted_done, stats)

    # ── CQC pass (residential/community health records) ───────────────────────
    if run_cqc:
        health_targets = df[
            df["conversion_type"].isin(["residential", "community"]) &
            df["conversion_subtype"].isin([
                "care_home", "nhs_health_centre", "supported_housing",
                "residential_general", "community_general", "unknown"
            ]) &
            ~df["id"].astype(str).isin(cqc_done)
        ].head(max_records // 2)

        logger.info("CQC: querying %d residential/community records", len(health_targets))
        batch_count = 0

        for idx, row in health_targets.iterrows():
            record_id = str(row.get("id", idx))
            postcode = extract_postcode(row)

            if not postcode:
                cqc_done.add(record_id)
                continue

            try:
                locations = search_cqc_by_postcode(postcode)
            except Exception as e:
                logger.debug("CQC failed for %s: %s", postcode, e)
                stats["errors"] += 1
                cqc_done.add(record_id)
                time.sleep(1)
                continue

            if locations:
                location = locations[0]
                cqc_id = str(location.get("locationId") or
                            location.get("id", ""))
                rating = str(location.get("currentRatings", {}).get(
                    "overall", {}).get("rating", "") or "")

                df.at[idx, "cqc_id"] = cqc_id
                df.at[idx, "inspection_rating"] = rating

                conv_type, conv_sub = classify_cqc_provider(location)
                if str(row.get("conversion_subtype", "")) in (
                    "residential_general", "community_general", "unknown", "nan", ""
                ):
                    df.at[idx, "conversion_type"] = conv_type
                    df.at[idx, "conversion_subtype"] = conv_sub
                    stats["subtypes_upgraded"] += 1

                existing = str(df.at[idx, "notes"] or "")
                df.at[idx, "notes"] = (
                    existing +
                    f" | CQC: {cqc_id} Rating: {rating}"
                )
                stats["cqc_confirmed"] += 1

            cqc_done.add(record_id)
            batch_count += 1

            if batch_count >= batch_size:
                if not dry_run:
                    df.to_csv(path, index=False)
                    save_checkpoint(CQC_CHECKPOINT, cqc_done, stats)
                logger.info(
                    "CQC batch | confirmed: %d | upgraded: %d",
                    stats["cqc_confirmed"], stats["subtypes_upgraded"]
                )
                batch_count = 0
            time.sleep(0.4)

        if batch_count > 0 and not dry_run:
            df.to_csv(path, index=False)
            save_checkpoint(CQC_CHECKPOINT, cqc_done, stats)

    print("\n=== OFSTED + CQC ENRICHMENT COMPLETE ===")
    print(f"Ofsted confirmed:  {stats['ofsted_confirmed']:,}")
    print(f"CQC confirmed:     {stats['cqc_confirmed']:,}")
    print(f"Subtypes upgraded: {stats['subtypes_upgraded']:,}")
    print(f"No postcode:       {stats['no_postcode']:,}")
    print(f"Errors:            {stats['errors']:,}")
    if not dry_run:
        print(f"\nSaved: {path}")


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(
        description="Enrich with Ofsted and CQC registration data"
    )
    parser.add_argument("--input", help="Path to CSV")
    parser.add_argument("--max-records", type=int, default=2000)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-ofsted", action="store_true")
    parser.add_argument("--no-cqc", action="store_true")
    args = parser.parse_args()

    enrich(
        input_path=args.input,
        max_records=args.max_records,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        run_ofsted=not args.no_ofsted,
        run_cqc=not args.no_cqc,
    )