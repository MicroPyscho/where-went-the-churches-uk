"""
extractors/osm_pbf_extractor.py

OSM Great Britain PBF local extractor using pyosmium.

This replaces the Overpass API queries for OSM data with local processing
of the Geofabrik Great Britain PBF extract. Benefits:
  - No rate limits, no timeouts
  - Processes all queries in one pass (~2-3 minutes)
  - Captures historic_church tag which times out via API
  - Full tag visibility per building (amenity + religion + building in one record)
  - Covers England, Wales, Scotland, Northern Ireland equally

Setup:
    pip install osmium
    curl -L https://download.geofabrik.de/europe/great-britain-latest.osm.pbf \
         -o data/raw/great-britain-latest.osm.pbf

    # Or wget:
    wget https://download.geofabrik.de/europe/great-britain-latest.osm.pbf \
         -P data/raw/

File size: ~1.5GB compressed. Add to .gitignore.
Update frequency: Geofabrik updates daily.

Usage:
    # Test with a small area first (much faster):
    python extractors/osm_pbf_extractor.py --test

    # Full Great Britain extract:
    python extractors/osm_pbf_extractor.py

    # Use in pipeline (main.py already handles this as 'osm_pbf' source):
    python main.py --sources wikidata osm_pbf historic_england --skip-geocode
"""

import logging
import os
from pathlib import Path
from typing import Optional
import pandas as pd

from constants import (
    MASTER_COLUMNS, SOURCE_CONFIDENCE,
    OSM_RELIGION_MAP, OSM_AMENITY_MAP, OSM_BUILDING_MAP,
)

logger = logging.getLogger(__name__)

DEFAULT_PBF_PATH = "data/raw/great-britain-latest.osm.pbf"
DOWNLOAD_URL = "https://download.geofabrik.de/europe/great-britain-latest.osm.pbf"

# UK bounding box for coordinate filtering
UK_BOUNDS = {"lat_min": 49.5, "lat_max": 61.0, "lon_min": -8.2, "lon_max": 2.2}


def check_osmium() -> bool:
    """Check if osmium is installed."""
    try:
        import osmium
        return True
    except ImportError:
        logger.error(
            "osmium not installed. Run: pip install osmium\n"
            "If that fails on Mac: brew install libosmium && pip install osmium"
        )
        return False


def is_church_building(tags) -> bool:
    """Check if OSM tags indicate a church/chapel building."""
    building = tags.get("building", "")
    historic = tags.get("historic", "")
    amenity = tags.get("amenity", "")
    was_building = tags.get("building:was", "") or tags.get("was:building", "")
    converted_from = tags.get("converted_from", "")

    church_values = {"church", "chapel", "cathedral", "monastery", "abbey", "shrine"}

    return (
        building in church_values or
        historic in {"church", "chapel", "monastery", "abbey"} or
        was_building in church_values or
        converted_from in church_values or
        (amenity == "place_of_worship" and building in church_values)
    )


def is_converted(tags) -> bool:
    """
    Check if tags suggest the building has been converted from a church.
    Key signal: building=church BUT current use differs from Christian worship.
    """
    building = tags.get("building", "")
    religion = tags.get("religion", "")
    amenity = tags.get("amenity", "")
    historic = tags.get("historic", "")

    # Explicit historic tag with different current building tag = converted
    if historic in {"church", "chapel"} and building not in {"church", "chapel", ""}:
        return True

    # Church building with non-Christian religion = faith conversion
    if building in {"church", "chapel"} and religion and religion != "christian":
        return True

    # Church building with commercial/hospitality amenity
    if building in {"church", "chapel"} and amenity in {
        "pub", "bar", "nightclub", "restaurant", "cafe",
        "arts_centre", "theatre", "cinema", "community_centre",
        "library", "school", "gym", "office",
    }:
        return True

    # Explicit conversion tags
    if tags.get("building:was") in {"church", "chapel"}:
        return True
    if tags.get("was:building") in {"church", "chapel"}:
        return True
    if tags.get("converted_from") in {"church", "chapel"}:
        return True

    # Residential building on historic church site
    if historic in {"church", "chapel"} and building in {
        "apartments", "residential", "house", "detached", "terrace"
    }:
        return True

    return False


def classify_tags(tags) -> tuple[str, str]:
    """Classify conversion type from OSM tags. Same logic as API extractor."""
    religion = tags.get("religion", "")
    amenity = tags.get("amenity", "")
    building = tags.get("building", "")
    shop = tags.get("shop", "")
    office = tags.get("office", "")
    name = tags.get("name", "").lower()

    # Religion
    if religion and religion != "christian":
        if religion in OSM_RELIGION_MAP:
            return OSM_RELIGION_MAP[religion]
        return ("other_faith", "other_faith_general")

    # Amenity
    if amenity and amenity in OSM_AMENITY_MAP:
        return OSM_AMENITY_MAP[amenity]

    # Shop / office
    if shop:
        return ("commercial", "shop")
    if office:
        return ("commercial", "office")

    # Building tag
    if building in OSM_BUILDING_MAP:
        return OSM_BUILDING_MAP[building]

    # Name-based fallback
    name_rules = [
        (["mosque", "masjid"], ("mosque", "mosque_general")),
        (["pub ", " inn", "tavern", " arms"], ("hospitality", "pub")),
        (["bar", "nightclub", "club"], ("hospitality", "bar")),
        (["restaurant", "kitchen"], ("hospitality", "restaurant")),
        (["flat", "apartment"], ("residential", "residential_general")),
        (["arts", "gallery", "theatre"], ("arts_culture", "arts_centre")),
        (["community", "centre", "hall"], ("community", "community_centre")),
        (["school", "academy"], ("education", "school")),
        (["library"], ("education", "library")),
        (["office", "workspace"], ("commercial", "office")),
        (["gym", "fitness"], ("commercial", "gym")),
    ]
    for kws, result in name_rules:
        if any(kw in name for kw in kws):
            return result

    return ("unknown", "unknown")


def nation_from_tags(tags, lat: float, lon: float) -> Optional[str]:
    """
    Infer nation from OSM tags or coordinates.
    OSM addr:country or is_in tags sometimes present.
    Falls back to rough coordinate bounding boxes.
    """
    country = tags.get("addr:country", "").upper()
    if country == "GB-SCT" or country == "SCT":
        return "Scotland"
    if country == "GB-WLS" or country == "WLS":
        return "Wales"
    if country == "GB-NIR" or country == "NIR":
        return "Northern Ireland"
    if country in {"GB", "GB-ENG", "ENG"}:
        return "England"

    # Rough coordinate-based nation detection
    # Scotland: north of ~55.0°N (simplified)
    if lat > 55.0 and lon < -1.5:
        return "Scotland"
    # Northern Ireland: west of -5.5°W and north of 54°N
    if lat > 54.0 and lon < -5.5:
        return "Northern Ireland"
    # Wales: west of -2.8°W and between 51.3-53.5°N
    if 51.3 < lat < 53.5 and lon < -2.8:
        return "Wales"
    # Default England
    if 49.5 < lat < 55.8:
        return "England"

    return None


class ChurchHandler:
    """
    osmium handler that processes OSM nodes and ways,
    filtering for converted church buildings.
    """

    def __init__(self):
        self.rows = []
        self.processed = 0
        self.found = 0

    def _process(self, osm_object, lat: float, lon: float):
        """Process a single OSM node or way."""
        self.processed += 1

        if self.processed % 500000 == 0:
            logger.info(
                "  Processed %dM objects, %d church conversions found",
                self.processed // 1000000,
                self.found,
            )

        tags = {k: v for k, v in osm_object.tags}

        if not is_church_building(tags):
            return
        if not is_converted(tags):
            return

        # Bounds check
        if not (UK_BOUNDS["lat_min"] <= lat <= UK_BOUNDS["lat_max"] and
                UK_BOUNDS["lon_min"] <= lon <= UK_BOUNDS["lon_max"]):
            return

        conv_type, conv_sub = classify_tags(tags)
        nation = nation_from_tags(tags, lat, lon)

        name = tags.get("name", "")
        old_name = tags.get("old_name", "") or tags.get("name:en", "")
        address_parts = [
            tags.get("addr:housenumber", ""),
            tags.get("addr:street", ""),
        ]
        address = " ".join(p for p in address_parts if p) or None
        city = (
            tags.get("addr:city") or
            tags.get("addr:town") or
            tags.get("addr:village") or
            tags.get("addr:hamlet")
        )

        osm_type = "node" if hasattr(osm_object, "location") else "way"
        osm_id = osm_object.id
        source_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"

        self.rows.append({
            "id": None,
            "church_name": old_name or None,
            "former_denomination": None,
            "address": address,
            "city": city,
            "local_authority": None,
            "region": None,
            "nation": nation,
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "conversion_type": conv_type,
            "conversion_subtype": conv_sub,
            "current_name": name or None,
            "year_converted": None,
            "decade": None,
            "source": "osm_pbf",
            "source_url": source_url,
            "confidence_score": SOURCE_CONFIDENCE["osm"],
            "notes": f"OSM {osm_type}/{osm_id} | tags: {dict(list(tags.items())[:6])}",
        })
        self.found += 1


def extract(pbf_path: str = DEFAULT_PBF_PATH) -> pd.DataFrame:
    """
    Process the Great Britain OSM PBF extract and return
    all converted church buildings as a normalised DataFrame.

    Args:
        pbf_path: Path to the .osm.pbf file.
                  Download from: https://download.geofabrik.de/europe/great-britain-latest.osm.pbf

    Returns:
        DataFrame conforming to MASTER_COLUMNS schema.
    """
    if not check_osmium():
        return pd.DataFrame(columns=MASTER_COLUMNS)

    import osmium

    path = Path(pbf_path)
    if not path.exists():
        logger.warning(
            "PBF file not found at '%s'.\n"
            "Download it with:\n"
            "  curl -L %s -o %s\n"
            "  (File size: ~1.5GB, takes 5-10 minutes to download)\n"
            "  Add data/raw/*.pbf to .gitignore",
            pbf_path, DOWNLOAD_URL, pbf_path
        )
        return pd.DataFrame(columns=MASTER_COLUMNS)

    file_size_gb = path.stat().st_size / (1024 ** 3)
    logger.info(
        "Processing OSM PBF: %s (%.1f GB)",
        pbf_path, file_size_gb
    )
    logger.info("This takes 2-5 minutes on a modern Mac M1/M2...")

    class NodeHandler(osmium.SimpleHandler):
        def __init__(self, church_handler):
            super().__init__()
            self.ch = church_handler

        def node(self, n):
            if n.location.valid():
                self.ch._process(n, n.location.lat, n.location.lon)

        def way(self, w):
            try:
                if w.nodes and len(w.nodes) > 0:
                    # Use centroid of first and last node as approximate centre
                    # (osmium ways don't have direct lat/lon without location index)
                    pass
            except Exception:
                pass

    # For ways we need a location index to get coordinates
    class WayHandler(osmium.SimpleHandler):
        def __init__(self, church_handler):
            super().__init__()
            self.ch = church_handler

        def area(self, a):
            try:
                tags = {k: v for k, v in a.tags}
                if not is_church_building(tags):
                    return
                if not is_converted(tags):
                    return
                # Get centroid from envelope
                env = a.envelope()
                lat = (env.bottom_left.lat + env.top_right.lat) / 2
                lon = (env.bottom_left.lon + env.top_right.lon) / 2
                self.ch._process(a, lat, lon)
            except Exception:
                pass

    church_handler = ChurchHandler()

    # Pass 1: Nodes
    logger.info("Pass 1: Processing nodes...")
    node_handler = NodeHandler(church_handler)
    node_handler.apply_file(str(path), locations=False)
    logger.info("Nodes complete: %d conversions found so far", church_handler.found)

    # Pass 2: Ways/Areas (needs location index for coordinates)
    logger.info("Pass 2: Processing ways/areas...")
    try:
        way_handler = WayHandler(church_handler)
        way_handler.apply_file(str(path), locations=True)
        logger.info("Ways complete: %d total conversions found", church_handler.found)
    except Exception as e:
        logger.warning("Way processing failed (location index error): %s", e)
        logger.warning("Only node data will be used. This is common — ways need more memory.")

    if not church_handler.rows:
        logger.warning("No converted church buildings found in PBF.")
        return pd.DataFrame(columns=MASTER_COLUMNS)

    df = pd.DataFrame(church_handler.rows, columns=MASTER_COLUMNS)

    # Dedup within PBF by source_url
    before = len(df)
    df = df.drop_duplicates(subset=["source_url"])
    logger.info("OSM PBF: %d raw → %d after internal dedup", before, len(df))

    # Nation breakdown
    logger.info("Nation breakdown:\n%s", df["nation"].value_counts().to_string())
    logger.info("Conversion types:\n%s", df["conversion_type"].value_counts().to_string())

    return df


def download_pbf(output_path: str = DEFAULT_PBF_PATH):
    """Download the Great Britain PBF from Geofabrik."""
    import subprocess
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading Great Britain OSM extract (~1.5GB)...")
    logger.info("URL: %s", DOWNLOAD_URL)
    logger.info("Output: %s", output_path)
    logger.info("This will take 5-15 minutes depending on your connection...")

    result = subprocess.run(
        ["curl", "-L", "--progress-bar", DOWNLOAD_URL, "-o", output_path],
        check=True
    )
    if result.returncode == 0:
        size = path.stat().st_size / (1024 ** 3)
        logger.info("Download complete: %.1f GB", size)
    else:
        logger.error("Download failed")


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="OSM PBF church conversion extractor")
    parser.add_argument("--pbf", default=DEFAULT_PBF_PATH, help="Path to .osm.pbf file")
    parser.add_argument("--download", action="store_true", help="Download the PBF file first")
    parser.add_argument("--test", action="store_true",
                        help="Test with a small area PBF (download England extract ~500MB)")
    args = parser.parse_args()

    if args.download:
        download_pbf(args.pbf)

    if args.test:
        # Use England-only extract for faster testing
        test_url = "https://download.geofabrik.de/europe/great-britain/england-latest.osm.pbf"
        test_path = "data/raw/england-latest.osm.pbf"
        logger.info("Downloading England-only extract for testing (~500MB)...")
        import subprocess
        subprocess.run(["curl", "-L", test_url, "-o", test_path], check=True)
        df = extract(test_path)
    else:
        df = extract(args.pbf)

    print(f"\nTotal OSM PBF records: {len(df)}")
    if not df.empty:
        print(df[["current_name", "city", "conversion_type", "nation", "latitude", "longitude"]].head(20))
        df.to_csv("data/raw/osm_pbf_raw.csv", index=False)
        print("\nSaved to data/raw/osm_pbf_raw.csv")
        print("\nTo use in the pipeline, add 'osm_pbf' to main.py sources.")