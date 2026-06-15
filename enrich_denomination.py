"""
enrich_denomination.py

Denomination enrichment script — run AFTER enrich_planning_portal.py.

Takes the output CSV and upgrades conversion_subtype to granular
denomination/organisation level using:
  1. OSM denomination= tag (from notes field)
  2. Building name keyword matching (current_name + church_name)
  3. Address-level inference (e.g. "Masjid" in address)

Works on ALL records regardless of source — Wikidata, OSM, Historic England,
planning portal. Writes to conversion_subtype column only; never overwrites
a conversion_type that is already set to something specific.

Checkpoint file: data/output/denomination_checkpoint.json
Resume-safe: can be killed and restarted at any point.

Usage:
    python enrich_denomination.py                    # Run on latest CSV
    python enrich_denomination.py --dry-run          # Preview without saving
    python enrich_denomination.py --reset            # Clear checkpoint
    python enrich_denomination.py --stats            # Show breakdown only
"""

import argparse
import json
import logging
import re
import glob
from pathlib import Path
from typing import Optional
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

CHECKPOINT_PATH = Path("data/output/denomination_checkpoint.json")


# ─── IMPORT RULES FROM CONSTANTS ─────────────────────────────────────────────
# Import from constants.py in the project root.
# If running standalone, fall back to inline rules.

try:
    from constants import (
        NAME_DENOMINATION_RULES,
        OSM_DENOMINATION_MAP,
        SUBTYPE_TO_TYPE,
    )
    logger.info("Loaded rules from constants.py")
except ImportError:
    logger.warning("Could not import constants.py — using inline rules")
    NAME_DENOMINATION_RULES = []
    OSM_DENOMINATION_MAP = {}
    SUBTYPE_TO_TYPE = {}


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


def save_checkpoint(processed_ids: set, stats: dict):
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump({
            "processed_ids": list(processed_ids),
            "total_processed": len(processed_ids),
            "stats": stats,
            "last_updated": pd.Timestamp.now().isoformat(),
        }, f)


def reset_checkpoint():
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()
        logger.info("Checkpoint cleared")
    else:
        logger.info("No checkpoint to clear")


# ─── DETECTION FUNCTIONS ─────────────────────────────────────────────────────

def extract_osm_denomination(notes: str) -> Optional[tuple[str, str]]:
    """
    Pull denomination= tag value from the notes field of OSM records.
    Notes format: "OSM way/123 | tags: {'denomination': 'rccg', ...}"
    """
    if not notes or "denomination" not in str(notes).lower():
        return None
    match = re.search(r"'denomination':\s*'([^']+)'", str(notes), re.IGNORECASE)
    if not match:
        match = re.search(r'"denomination":\s*"([^"]+)"', str(notes), re.IGNORECASE)
    if not match:
        return None

    denom = match.group(1).lower().strip().replace(" ", "_")
    if denom in OSM_DENOMINATION_MAP:
        return OSM_DENOMINATION_MAP[denom]

    # Fuzzy fallback — partial match
    for key, val in OSM_DENOMINATION_MAP.items():
        if key in denom or denom in key:
            return val
    return None


def detect_from_name(name: str) -> Optional[tuple[str, str]]:
    """
    Apply NAME_DENOMINATION_RULES to a building name string.
    Returns (conversion_type, conversion_subtype) or None.
    """
    if not name:
        return None
    name_lower = str(name).lower()
    for keywords, conv_type, conv_sub in NAME_DENOMINATION_RULES:
        if any(kw in name_lower for kw in keywords):
            return conv_type, conv_sub
    return None


def classify_record(row: pd.Series) -> Optional[tuple[str, str, str]]:
    """
    Attempt to classify a record to a granular denomination/subtype.

    Returns (conversion_type, conversion_subtype, method) or None.
    method is one of: 'osm_denomination', 'current_name', 'church_name',
                      'address', 'notes_text'
    """
    # 1. OSM denomination tag from notes (most reliable for OSM records)
    result = extract_osm_denomination(str(row.get("notes", "") or ""))
    if result:
        return result[0], result[1], "osm_denomination"

    # 2. Current name (what the building is now called)
    result = detect_from_name(str(row.get("current_name", "") or ""))
    if result:
        return result[0], result[1], "current_name"

    # 3. Church name (original name — may contain denomination clues)
    result = detect_from_name(str(row.get("church_name", "") or ""))
    if result:
        return result[0], result[1], "church_name"

    # 4. Address field
    result = detect_from_name(str(row.get("address", "") or ""))
    if result:
        return result[0], result[1], "address"

    # 5. Notes field free text
    notes_text = str(row.get("notes", "") or "")
    # Strip the OSM tags dict part, keep free text
    clean_notes = re.sub(r"OSM \w+/\d+.*?tags:.*?}", "", notes_text)
    result = detect_from_name(clean_notes)
    if result:
        return result[0], result[1], "notes_text"

    return None


def should_upgrade(row: pd.Series, new_type: str, new_sub: str) -> bool:
    """
    Decide whether to apply the detected classification.

    Rules:
    - Never downgrade a specific subtype to a less specific one
    - Never change a type that's already correct and specific
    - Always upgrade 'unknown' subtypes
    - Upgrade 'mosque_general' to specific mosque subtype
    - Upgrade 'other_christian_general' to specific denomination
    - Don't change if new_type conflicts with existing type
      (e.g. don't reclassify 'residential' as 'mosque')
    """
    current_type = str(row.get("conversion_type", "") or "")
    current_sub = str(row.get("conversion_subtype", "") or "")

    # If current type is unknown or empty — always upgrade
    if current_type in ("unknown", "", "nan") or pd.isna(row.get("conversion_type")):
        return True

    # If current subtype is a general/unknown placeholder — upgrade
    general_subs = {
        "unknown", "mosque_general", "other_christian_general",
        "other_faith_general", "residential_general", "community_general",
        "hospitality_general", "commercial_general", "arts_culture_general",
        "education_general", "sport_leisure_general", "tourist_general",
        "civic_general", "eastern_philosophy_general", "african_church_general",
        "caribbean_church_general", "eastern_european_general",
        "middle_eastern_general", "east_asian_general", "south_asian_general",
        "nrm_general", "esoteric_general", "pentecostal_general",
        "evangelical_general",
    }
    if current_sub in general_subs:
        # Only upgrade if new type matches or refines current type
        if new_type == current_type:
            return True
        # Allow upgrading within the faith/religion group
        faith_types = {
            "mosque", "african_diaspora_church", "caribbean_church",
            "eastern_european_church", "middle_eastern_church",
            "east_asian_church", "south_asian_faith", "new_religious_movement",
            "esoteric_occult", "eastern_philosophy", "pentecostal_evangelical",
            "other_christian",
        }
        if current_type in faith_types and new_type in faith_types:
            return True
        return False

    # Don't overwrite an already specific subtype
    return False


# ─── MAIN ────────────────────────────────────────────────────────────────────

def find_latest_csv() -> Optional[Path]:
    candidates = sorted(
        glob.glob("data/output/uk_church_conversions_2*.csv"),
        reverse=True
    )
    for c in candidates:
        if "PUBLIC" not in c and "enriched" not in c:
            return Path(c)
    return Path(candidates[0]) if candidates else None


def show_stats(df: pd.DataFrame):
    """Print denomination breakdown."""
    print("\n=== DENOMINATION BREAKDOWN ===")
    print(f"Total records: {len(df):,}")
    print(f"\nConversion type breakdown:")
    print(df["conversion_type"].value_counts().head(20).to_string())
    print(f"\nTop 30 conversion subtypes:")
    print(df["conversion_subtype"].value_counts().head(30).to_string())
    print(f"\nAfrican diaspora churches:")
    aic = df[df["conversion_type"] == "african_diaspora_church"]
    if not aic.empty:
        print(aic["conversion_subtype"].value_counts().to_string())
    print(f"\nMosque subtypes:")
    mosques = df[df["conversion_type"] == "mosque"]
    if not mosques.empty:
        print(mosques["conversion_subtype"].value_counts().to_string())
    print(f"\nSport & leisure:")
    sport = df[df["conversion_type"] == "sport_leisure"]
    if not sport.empty:
        print(sport["conversion_subtype"].value_counts().to_string())


def enrich(
    input_path: Optional[str] = None,
    dry_run: bool = False,
    batch_size: int = 500,
    stats_only: bool = False,
):
    # Load data
    path = Path(input_path) if input_path else find_latest_csv()
    if not path or not path.exists():
        logger.error("No pipeline output CSV found.")
        return

    logger.info("Loading %s", path)
    df = pd.read_csv(path, low_memory=False)

    for col in ["conversion_type", "conversion_subtype", "notes"]:
        df[col] = df[col].astype(object)

    logger.info("Loaded %d records", len(df))

    if stats_only:
        show_stats(df)
        return

    # Load checkpoint
    processed_ids = load_checkpoint()

    # All records eligible — denomination can be applied to any record
    remaining = df[~df["id"].astype(str).isin(processed_ids)]
    logger.info(
        "%d total | %d already processed | %d remaining",
        len(df), len(processed_ids), len(remaining)
    )

    if len(remaining) == 0:
        logger.info("All records already processed. Use --reset to rerun.")
        show_stats(df)
        return

    stats = {
        "type_upgraded": 0,
        "subtype_upgraded": 0,
        "osm_denomination": 0,
        "current_name": 0,
        "church_name": 0,
        "address": 0,
        "notes_text": 0,
        "no_match": 0,
    }
    batch_count = 0

    for idx, row in remaining.iterrows():
        record_id = str(row.get("id", idx))
        result = classify_record(row)

        if result:
            new_type, new_sub, method = result
            if should_upgrade(row, new_type, new_sub):
                old_type = str(df.at[idx, "conversion_type"] or "")
                old_sub = str(df.at[idx, "conversion_subtype"] or "")

                df.at[idx, "conversion_subtype"] = new_sub
                stats["subtype_upgraded"] += 1
                stats[method] = stats.get(method, 0) + 1

                if new_type != old_type and old_type in ("unknown", "", "nan"):
                    df.at[idx, "conversion_type"] = new_type
                    stats["type_upgraded"] += 1

                # Add method note
                existing = str(df.at[idx, "notes"] or "")
                df.at[idx, "notes"] = (
                    existing + f" | Denomination: {new_sub} (via {method})"
                )
            else:
                stats["no_match"] += 1
        else:
            stats["no_match"] += 1

        processed_ids.add(record_id)
        batch_count += 1

        # Save every batch_size records
        if batch_count >= batch_size:
            if not dry_run:
                df.to_csv(path, index=False)
                save_checkpoint(processed_ids, stats)
            logger.info(
                "Batch saved | subtypes: +%d | types: +%d | methods: osm=%d name=%d church=%d",
                stats["subtype_upgraded"], stats["type_upgraded"],
                stats.get("osm_denomination", 0),
                stats.get("current_name", 0),
                stats.get("church_name", 0),
            )
            batch_count = 0

    # Final save
    if batch_count > 0 and not dry_run:
        df.to_csv(path, index=False)
        save_checkpoint(processed_ids, stats)
        logger.info("Final batch saved")

    print("\n=== DENOMINATION ENRICHMENT COMPLETE ===")
    print(f"Subtypes upgraded:     {stats['subtype_upgraded']:,}")
    print(f"Types upgraded:        {stats['type_upgraded']:,}")
    print(f"  via OSM denomination:{stats.get('osm_denomination',0):,}")
    print(f"  via current name:    {stats.get('current_name',0):,}")
    print(f"  via church name:     {stats.get('church_name',0):,}")
    print(f"  via address:         {stats.get('address',0):,}")
    print(f"  via notes text:      {stats.get('notes_text',0):,}")
    print(f"No match:              {stats['no_match']:,}")

    show_stats(df)

    if not dry_run:
        print(f"\nSaved: {path}")
        print("Run again to process any remaining records.")
    else:
        print("\nDry run — nothing saved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enrich conversion_subtype with denomination/organisation detail"
    )
    parser.add_argument("--input", help="Path to CSV (auto-detects latest)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset", action="store_true",
                        help="Clear checkpoint and reprocess all records")
    parser.add_argument("--stats", action="store_true",
                        help="Show denomination breakdown only, no enrichment")
    parser.add_argument("--batch-size", type=int, default=500,
                        help="Save every N records (default: 500)")
    args = parser.parse_args()

    if args.reset:
        reset_checkpoint()

    enrich(
        input_path=args.input,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        stats_only=args.stats,
    )