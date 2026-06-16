"""
enrich_postcodes.py

Reverse geocode coordinates to postcodes using postcodes.io API.

Takes each record's lat/lon and looks up the nearest UK postcode.
Adds postcode to a new 'postcode' column — does NOT remove lat/lon.
Both are kept: lat/lon for spatial analysis, postcode for API lookups.

This unlocks four downstream enrichments:
  - Land Registry (sale price, transaction date)
  - Ofsted (school/nursery confirmation)
  - CQC (care home/GP confirmation)
  - Companies House (buyer identity)

API: https://postcodes.io — free, no key required
Rate limit: 1 request/second (enforced by script)
Bulk endpoint: 100 coordinates per request (used here for speed)

Usage:
    python enrich_postcodes.py                    # Run on latest CSV
    python enrich_postcodes.py --dry-run          # Preview without saving
    python enrich_postcodes.py --reset            # Clear checkpoint
    python enrich_postcodes.py --max-records 1000 # Limit records

At 100 coords per batch request, 23,719 records = ~238 API calls
Estimated runtime: ~5 minutes (much faster than per-record APIs)

Coverage: England, Wales, Scotland, Northern Ireland all covered.
postcodes.io uses ONS postcode data updated quarterly.
"""

import argparse
import json
import logging
import time
import glob
from pathlib import Path
from typing import Optional
import requests
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

POSTCODES_IO_BULK = "https://api.postcodes.io/postcodes"
BATCH_SIZE = 100  # postcodes.io bulk endpoint limit
CHECKPOINT_PATH = Path("data/output/postcode_checkpoint.json")
HEADERS = {
    "User-Agent": "UKChurchConversionResearch/1.0 (academic project)",
    "Content-Type": "application/json",
}


# ─── CHECKPOINT ──────────────────────────────────────────────────────────────

def load_checkpoint() -> set:
    if not CHECKPOINT_PATH.exists():
        return set()
    try:
        with open(CHECKPOINT_PATH) as f:
            data = json.load(f)
            done = set(data.get("processed_ids", []))
            logger.info("Checkpoint: %d records already processed", len(done))
            return done
    except Exception as e:
        logger.warning("Could not load checkpoint: %s", e)
        return set()


def save_checkpoint(processed: set, stats: dict):
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump({
            "processed_ids": list(processed),
            "total_processed": len(processed),
            "stats": stats,
            "last_updated": pd.Timestamp.now().isoformat(),
        }, f)


def reset_checkpoint():
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()
        logger.info("Checkpoint cleared")


# ─── API ─────────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=3, max=15))
def bulk_reverse_geocode(coords: list[dict]) -> list[Optional[dict]]:
    """
    Send up to 100 coordinates to postcodes.io bulk reverse geocode endpoint.

    coords: list of {"longitude": float, "latitude": float} dicts
    Returns: list of result dicts (or None where no postcode found)
    """
    payload = {"geolocations": coords}
    resp = requests.post(
        POSTCODES_IO_BULK,
        json=payload,
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("result", []):
        if item and item.get("result") and len(item["result"]) > 0:
            # Take nearest result (first in list, sorted by distance)
            nearest = item["result"][0]
            results.append({
                "postcode":         nearest.get("postcode"),
                "district":         nearest.get("admin_district"),
                "county":           nearest.get("admin_county"),
                "region":           nearest.get("region"),
                "nation":           nearest.get("country"),
                "parliamentary_constituency": nearest.get("parliamentary_constituency"),
                "lsoa":             nearest.get("lsoa"),         # Lower Super Output Area
                "msoa":             nearest.get("msoa"),         # Middle Super Output Area
                "ward":             nearest.get("admin_ward"),
                "distance_metres":  nearest.get("distance"),
            })
        else:
            results.append(None)

    return results


# ─── MAIN ────────────────────────────────────────────────────────────────────

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
    max_records: Optional[int] = None,
    dry_run: bool = False,
    save_interval: int = 500,
):
    """
    Reverse geocode all records with coordinates to add postcode.
    Uses bulk API — processes 100 records per request.
    Preserves all existing lat/lon data.
    """
    path = Path(input_path) if input_path else find_latest_csv()
    if not path or not path.exists():
        logger.error("No pipeline CSV found. Run the pipeline first.")
        return

    logger.info("Loading %s", path)
    df = pd.read_csv(path, low_memory=False)

    # Add postcode column if not present (keep lat/lon intact)
    if "postcode" not in df.columns:
        df["postcode"] = None
        logger.info("Added 'postcode' column (lat/lon preserved)")
    else:
        logger.info("'postcode' column already exists — filling blanks only")

    # Add geographic detail columns
    for col in ["ward", "lsoa", "msoa", "parliamentary_constituency",
                "postcode", "region", "nation"]:
        if col not in df.columns:
            df[col] = None
        df[col] = df[col].astype(object)

    logger.info("Loaded %d records", len(df))

    processed = load_checkpoint()

    # Target: records with coordinates but missing postcode
    needs_postcode = (
        df["latitude"].notna() &
        df["longitude"].notna() &
        (df["postcode"].isna() | (df["postcode"] == ""))
    )
    targets = df[needs_postcode & ~df["id"].astype(str).isin(processed)]

    if max_records:
        targets = targets.head(max_records)

    logger.info(
        "%d records need postcode | %d already done | %d to process this run",
        needs_postcode.sum(), len(processed), len(targets)
    )

    if len(targets) == 0:
        logger.info("All records already have postcodes. Use --reset to reprocess.")
        _print_coverage(df)
        return

    stats = {
        "postcodes_added": 0,
        "region_upgraded": 0,
        "nation_upgraded": 0,
        "lsoa_added": 0,
        "not_found": 0,
        "errors": 0,
        "batches": 0,
    }

    # Process in batches of 100
    indices = targets.index.tolist()
    total_batches = (len(indices) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_num in range(total_batches):
        start = batch_num * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(indices))
        batch_indices = indices[start:end]

        # Build coordinate payload
        coords = []
        for idx in batch_indices:
            row = df.loc[idx]
            coords.append({
                "longitude": float(row["longitude"]),
                "latitude":  float(row["latitude"]),
            })

        # Query postcodes.io
        try:
            results = bulk_reverse_geocode(coords)
            stats["batches"] += 1
        except Exception as e:
            logger.error("Batch %d failed: %s", batch_num + 1, e)
            stats["errors"] += 1
            # Mark as processed to avoid retrying same batch
            for idx in batch_indices:
                processed.add(str(df.at[idx, "id"]))
            time.sleep(2)
            continue

        # Apply results
        for idx, result in zip(batch_indices, results):
            record_id = str(df.at[idx, "id"])

            if result and result.get("postcode"):
                # Add postcode
                df.at[idx, "postcode"] = result["postcode"]
                stats["postcodes_added"] += 1

                # Add LSOA/MSOA (valuable for deprivation index joins)
                if result.get("lsoa"):
                    df.at[idx, "lsoa"] = result["lsoa"]
                    stats["lsoa_added"] += 1
                if result.get("msoa"):
                    df.at[idx, "msoa"] = result["msoa"]

                # Add ward
                if result.get("ward"):
                    df.at[idx, "ward"] = result["ward"]

                # Add parliamentary constituency
                if result.get("parliamentary_constituency"):
                    df.at[idx, "parliamentary_constituency"] = result["parliamentary_constituency"]

                # Upgrade region if missing
                if pd.isna(df.at[idx, "region"]) or str(df.at[idx, "region"]) in ("", "nan"):
                    if result.get("region"):
                        df.at[idx, "region"] = result["region"]
                        stats["region_upgraded"] += 1

                # Upgrade nation if missing
                if pd.isna(df.at[idx, "nation"]) or str(df.at[idx, "nation"]) in ("", "nan"):
                    if result.get("nation"):
                        df.at[idx, "nation"] = result["nation"]
                        stats["nation_upgraded"] += 1
            else:
                stats["not_found"] += 1

            processed.add(record_id)

        # Progress logging
        records_done = (batch_num + 1) * BATCH_SIZE
        logger.info(
            "Batch %d/%d | postcodes: +%d | region: +%d | nation: +%d | errors: %d",
            batch_num + 1, total_batches,
            stats["postcodes_added"], stats["region_upgraded"],
            stats["nation_upgraded"], stats["errors"]
        )

        # Save every save_interval records
        if stats["postcodes_added"] % save_interval < BATCH_SIZE:
            if not dry_run:
                df.to_csv(path, index=False)
                save_checkpoint(processed, stats)
                logger.info("Progress saved")

        # Rate limiting — postcodes.io is generous but be polite
        time.sleep(0.5)

    # Final save
    if not dry_run:
        df.to_csv(path, index=False)
        save_checkpoint(processed, stats)
        logger.info("Final save complete")

    print("\n=== POSTCODE ENRICHMENT COMPLETE ===")
    print(f"Postcodes added:    {stats['postcodes_added']:,}")
    print(f"Regions upgraded:   {stats['region_upgraded']:,}")
    print(f"Nations upgraded:   {stats['nation_upgraded']:,}")
    print(f"LSOA codes added:   {stats['lsoa_added']:,}")
    print(f"Not found:          {stats['not_found']:,}")
    print(f"Errors:             {stats['errors']:,}")
    print(f"API batches made:   {stats['batches']:,}")

    _print_coverage(df)

    if not dry_run:
        print(f"\nSaved: {path}")
        print("Lat/lon preserved. Postcode added as new column.")
        print("\nNow run:")
        print("  python extractors/land_registry_extractor.py --max-records 5000")
        print("  python enrich_ofsted_cqc.py --max-records 2000")
    else:
        print("\nDry run — nothing saved.")


def _print_coverage(df: pd.DataFrame):
    total = len(df)
    has_postcode = df["postcode"].notna().sum()
    has_lsoa = df["lsoa"].notna().sum() if "lsoa" in df.columns else 0
    has_nation = df["nation"].notna().sum()
    has_lat = df["latitude"].notna().sum()

    print(f"\n=== COVERAGE AFTER ENRICHMENT ===")
    print(f"Total records:      {total:,}")
    print(f"Has lat/lon:        {has_lat:,} ({has_lat/total*100:.1f}%)")
    print(f"Has postcode:       {has_postcode:,} ({has_postcode/total*100:.1f}%)")
    print(f"Has nation:         {has_nation:,} ({has_nation/total*100:.1f}%)")
    if has_lsoa:
        print(f"Has LSOA:           {has_lsoa:,} ({has_lsoa/total*100:.1f}%)")
    if "nation" in df.columns:
        print(f"\nNation breakdown:")
        print(df["nation"].value_counts().to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Reverse geocode coordinates to postcodes using postcodes.io"
    )
    parser.add_argument("--input", help="Path to CSV (auto-detects latest)")
    parser.add_argument(
        "--max-records", type=int, default=None,
        help="Limit records to process (default: all)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Query but don't save"
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Clear checkpoint and reprocess all records"
    )
    parser.add_argument(
        "--save-interval", type=int, default=500,
        help="Save every N postcodes added (default: 500)"
    )
    args = parser.parse_args()

    if args.reset:
        reset_checkpoint()

    enrich(
        input_path=args.input,
        max_records=args.max_records,
        dry_run=args.dry_run,
        save_interval=args.save_interval,
    )