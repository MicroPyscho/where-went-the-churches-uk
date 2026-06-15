"""
enrich_planning_portal.py

Standalone enrichment script with checkpointing and resume capability.

Features:
  - Tracks which records have already been queried in a checkpoint file
  - Saves progress every batch (default 100 records) so crashes don't lose work
  - Resumes automatically from where it stopped on next run
  - Never re-queries a record that has already been attempted
  - Dry run mode for testing without saving

Usage:
    python enrich_planning_portal.py                    # Run with defaults
    python enrich_planning_portal.py --batch-size 100   # Save every 100 records
    python enrich_planning_portal.py --max-records 1000 # Stop after 1000 queries
    python enrich_planning_portal.py --dry-run          # Test without saving
    python enrich_planning_portal.py --reset            # Clear checkpoint, start fresh

Checkpoint file: data/output/enrichment_checkpoint.json
"""

import argparse
import json
import logging
import time
import re
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

PLANNING_BASE = "https://www.planning.data.gov.uk"
HEADERS = {
    "User-Agent": "UKChurchConversionResearch/1.0 (academic project)",
    "Accept": "application/json",
}

BBOX_DEGREES = 0.001
CHECKPOINT_PATH = Path("data/output/enrichment_checkpoint.json")

USE_CLASS_MAP = {
    "C3": ("residential", "converted_flats"),
    "C3(a)": ("residential", "converted_flats"),
    "C3(b)": ("residential", "converted_flats"),
    "C3(c)": ("residential", "residential_general"),
    "C4": ("residential", "student_housing"),
    "C2": ("residential", "care_home"),
    "C1": ("hospitality", "hotel"),
    "E": ("commercial", "office"),
    "E(a)": ("commercial", "shop"),
    "E(b)": ("hospitality", "restaurant"),
    "E(c)": ("commercial", "office"),
    "E(g)": ("commercial", "office"),
    "F2": ("community", "community_centre"),
    "F2(a)": ("community", "community_centre"),
    "F2(b)": ("community", "community_centre"),
    "F1(a)": ("education", "school"),
    "F1(b)": ("education", "library"),
    "A4": ("hospitality", "pub"),
    "A3": ("hospitality", "restaurant"),
    "A1": ("commercial", "shop"),
    "D2": ("community", "community_centre"),
    "B2": ("commercial", "office"),
    "B8": ("commercial", "storage"),
}

DESCRIPTION_PATTERNS = [
    (r"\b(mosque|masjid|islamic)\b", "mosque", "mosque_general"),
    (r"\b(gurdwara|sikh)\b", "other_faith", "sikh_gurdwara"),
    (r"\b(synagogue|jewish)\b", "other_faith", "jewish_synagogue"),
    (r"\b(flat|apartment|residential|dwelling)\b", "residential", "converted_flats"),
    (r"\b(pub|bar|tavern|inn)\b", "hospitality", "pub"),
    (r"\b(restaurant|cafe)\b", "hospitality", "restaurant"),
    (r"\b(hotel|hostel)\b", "hospitality", "hotel"),
    (r"\b(nightclub|club)\b", "hospitality", "nightclub"),
    (r"\b(office|workspace)\b", "commercial", "office"),
    (r"\b(shop|retail|store)\b", "commercial", "shop"),
    (r"\b(gym|fitness)\b", "commercial", "gym"),
    (r"\b(theatre|theater)\b", "arts_culture", "theatre"),
    (r"\b(cinema)\b", "arts_culture", "cinema"),
    (r"\b(museum|gallery)\b", "arts_culture", "museum"),
    (r"\b(school|academy|nursery)\b", "education", "school"),
    (r"\b(library)\b", "education", "library"),
    (r"\b(community centre|village hall)\b", "community", "community_centre"),
]

APPROVED_DECISIONS = [
    "granted", "approved", "permitted", "prior approval granted",
    "prior approval not required", "lawful",
]


def load_checkpoint() -> set:
    if not CHECKPOINT_PATH.exists():
        return set()
    try:
        with open(CHECKPOINT_PATH) as f:
            data = json.load(f)
            queried = set(data.get("queried_ids", []))
            logger.info("Checkpoint loaded: %d records already queried", len(queried))
            return queried
    except Exception as e:
        logger.warning("Could not load checkpoint: %s — starting fresh", e)
        return set()


def save_checkpoint(queried_ids: set, stats: dict):
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "queried_ids": list(queried_ids),
        "total_queried": len(queried_ids),
        "stats": stats,
        "last_updated": pd.Timestamp.now().isoformat(),
    }
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(data, f)


def reset_checkpoint():
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()
        logger.info("Checkpoint cleared — will start from beginning")
    else:
        logger.info("No checkpoint to clear")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=20))
def query_planning_by_bbox(lat: float, lon: float) -> list[dict]:
    params = {
        "dataset": "planning-application",
        "bb-lat-min": lat - BBOX_DEGREES,
        "bb-lon-min": lon - BBOX_DEGREES,
        "bb-lat-max": lat + BBOX_DEGREES,
        "bb-lon-max": lon + BBOX_DEGREES,
        "limit": 10,
        "field": [
            "reference", "description", "development-description",
            "existing-use-class", "proposed-use-class",
            "decision", "decision-date", "entry-date",
            "latitude", "longitude", "address",
        ],
    }
    resp = requests.get(
        f"{PLANNING_BASE}/entity.json",
        params=params,
        headers=HEADERS,
        timeout=20,
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()
    return data.get("entities", []) or data.get("results", [])


def classify_from_entity(entity: dict) -> tuple[Optional[str], Optional[str]]:
    proposed = str(entity.get("proposed-use-class", "") or "").strip()
    if proposed in USE_CLASS_MAP:
        return USE_CLASS_MAP[proposed]
    text = " ".join([
        str(entity.get("description", "") or ""),
        str(entity.get("development-description", "") or ""),
    ])
    for pattern, ct, cs in DESCRIPTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return ct, cs
    return None, None


def extract_year(entity: dict) -> Optional[int]:
    for field in ["decision-date", "entry-date"]:
        val = entity.get(field, "")
        if val:
            try:
                yr = int(str(val)[:4])
                if 1960 <= yr <= 2030:
                    return yr
            except (ValueError, TypeError):
                pass
    return None


def is_approved(entity: dict) -> bool:
    decision = str(entity.get("decision", "") or "").lower()
    if not decision:
        return True
    return any(d in decision for d in APPROVED_DECISIONS)


def find_latest_output_csv() -> Optional[Path]:
    candidates = sorted(
        glob.glob("data/output/uk_church_conversions_2*.csv"),
        reverse=True
    )
    for c in candidates:
        if "PUBLIC" not in c and "enriched" not in c:
            return Path(c)
    return Path(candidates[0]) if candidates else None


def enrich(
    input_path: Optional[str] = None,
    max_records: int = 1000,
    batch_size: int = 100,
    dry_run: bool = False,
    england_only: bool = True,
):
    # Load data
    path = Path(input_path) if input_path else find_latest_output_csv()
    if not path or not path.exists():
        logger.error("No pipeline output CSV found. Run the pipeline first.")
        return

    logger.info("Loading %s", path)
    df = pd.read_csv(path, low_memory=False)

    for col in ["region", "nation", "conversion_type", "conversion_subtype", "decade", "notes"]:
        df[col] = df[col].astype(object)
    df["year_converted"] = pd.to_numeric(df["year_converted"], errors="coerce")
    df["confidence_score"] = pd.to_numeric(df["confidence_score"], errors="coerce")

    logger.info("Loaded %d records", len(df))

    # Load checkpoint — set of record IDs already queried
    already_queried = load_checkpoint()

    # Identify records needing enrichment
    needs_enrichment = (
        df["latitude"].notna() &
        df["longitude"].notna() &
        (
            (df["conversion_type"] == "unknown") |
            df["year_converted"].isna()
        )
    )
    if england_only:
        england_mask = (
            df["nation"].isna() |
            (df["nation"] == "England") |
            (df["nation"] == "")
        )
        needs_enrichment = needs_enrichment & england_mask

    all_targets = df[needs_enrichment].copy()

    # Remove already-queried records
    remaining = all_targets[~all_targets["id"].astype(str).isin(already_queried)]
    skipped = len(all_targets) - len(remaining)

    logger.info(
        "%d need enrichment | %d already done | %d remaining",
        len(all_targets), skipped, len(remaining)
    )

    if len(remaining) == 0:
        logger.info("All eligible records already enriched. Use --reset to start over.")
        return

    targets = remaining.head(max_records)
    logger.info(
        "Querying %d records this run | batch saves every %d",
        len(targets), batch_size
    )

    stats = {"types_resolved": 0, "years_added": 0, "errors": 0, "queried": 0}
    batch_count = 0

    for i, (idx, row) in enumerate(targets.iterrows()):
        record_id = str(row.get("id", idx))
        lat = row["latitude"]
        lon = row["longitude"]

        try:
            entities = query_planning_by_bbox(float(lat), float(lon))
            stats["queried"] += 1
            already_queried.add(record_id)
        except Exception as e:
            logger.debug("Query failed for %s: %s", record_id, e)
            stats["errors"] += 1
            already_queried.add(record_id)
            time.sleep(2)
            continue

        best_year = None
        best_type = None
        best_sub = None
        best_ref = None

        for entity in entities:
            if not is_approved(entity):
                continue
            yr = extract_year(entity)
            ct, cs = classify_from_entity(entity)
            if yr and not best_year:
                best_year = yr
                best_ref = entity.get("reference", "")
            if ct and not best_type:
                best_type = ct
                best_sub = cs
            if best_year and best_type:
                break

        changed = False

        if best_year and pd.isna(df.at[idx, "year_converted"]):
            df.at[idx, "year_converted"] = best_year
            df.at[idx, "decade"] = f"{(best_year // 10) * 10}s"
            stats["years_added"] += 1
            changed = True

        if best_type and df.at[idx, "conversion_type"] == "unknown":
            df.at[idx, "conversion_type"] = best_type
            df.at[idx, "conversion_subtype"] = best_sub or "unknown"
            stats["types_resolved"] += 1
            changed = True

        if changed and best_ref:
            existing = str(df.at[idx, "notes"] or "")
            df.at[idx, "notes"] = existing + f" | Planning: {best_ref} ({best_year or 'no date'})"
            df.at[idx, "confidence_score"] = min(
                float(df.at[idx, "confidence_score"] or 0.7) + 0.05, 0.90
            )

        batch_count += 1

        # Save every batch_size records
        if batch_count >= batch_size:
            if not dry_run:
                df.to_csv(path, index=False)
                save_checkpoint(already_queried, stats)
            logger.info(
                "[%d/%d] Batch saved | types +%d | years +%d | errors %d",
                stats["queried"], len(targets),
                stats["types_resolved"], stats["years_added"], stats["errors"]
            )
            batch_count = 0

        time.sleep(0.7)

    # Save final partial batch
    if batch_count > 0 and not dry_run:
        df.to_csv(path, index=False)
        save_checkpoint(already_queried, stats)
        logger.info("Final batch saved")

    print("\n=== ENRICHMENT COMPLETE ===")
    print(f"Queried this run:          {stats['queried']:,}")
    print(f"Conversion types resolved: {stats['types_resolved']:,}")
    print(f"Years added:               {stats['years_added']:,}")
    print(f"Errors:                    {stats['errors']:,}")
    print(f"Total in checkpoint:       {len(already_queried):,}")
    print(f"\nConversion type breakdown:")
    print(df["conversion_type"].value_counts().head(10).to_string())
    print(f"\nYear coverage: {df['year_converted'].notna().sum():,} / {len(df):,} records")
    if not dry_run:
        print(f"\nSaved: {path}")
        print(f"Checkpoint: {CHECKPOINT_PATH}")
        print(f"\nRun again to continue from where this stopped.")
    else:
        print("\nDry run — nothing saved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enrich pipeline output with planning portal data"
    )
    parser.add_argument("--input", help="Path to CSV (auto-detects latest)")
    parser.add_argument("--max-records", type=int, default=1000,
                        help="Records to query per run (default: 1000)")
    parser.add_argument("--batch-size", type=int, default=100,
                        help="Save every N records (default: 100)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Query but don't save")
    parser.add_argument("--reset", action="store_true",
                        help="Clear checkpoint and start fresh")
    parser.add_argument("--all-nations", action="store_true",
                        help="Include Wales/Scotland/NI (API covers England only)")
    args = parser.parse_args()

    if args.reset:
        reset_checkpoint()

    enrich(
        input_path=args.input,
        max_records=args.max_records,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        england_only=not args.all_nations,
    )