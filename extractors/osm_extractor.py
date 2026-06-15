"""
extractors/osm_extractor.py

OpenStreetMap Overpass API extractor — UPDATED with denomination parsing.

Added in this version:
  - denomination= tag parsing in classify_osm_element()
  - religion= tag expanded to cover scientology, pagan, jain, taoist
  - sport/leisure amenity tags (climbing, gym, fitness_centre)
  - Historic church queries split into regional bboxes to avoid timeout
  - All /home/claude paths removed
"""

import logging
import time
from typing import Optional
import requests
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from constants import (
    MASTER_COLUMNS,
    SOURCE_CONFIDENCE,
    OSM_RELIGION_MAP,
    OSM_AMENITY_MAP,
    OSM_BUILDING_MAP,
    OSM_DENOMINATION_MAP,
)

logger = logging.getLogger(__name__)

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
HEADERS = {
    "User-Agent": "UKChurchConversionResearch/1.0 (academic project)",
    "Content-Type": "application/x-www-form-urlencoded",
}

UK_BBOX = "49.5,-8.2,61.0,2.2"

# Regional bounding boxes for the historic_church query
# Splits the slow UK-wide query into 6 faster regional queries
REGIONAL_BBOXES = {
    "london":    "51.2,-0.6,51.8,0.4",
    "south":     "50.5,-2.5,51.2,1.8",
    "midlands":  "51.8,-3.0,53.0,0.5",
    "north":     "53.0,-3.5,55.5,0.0",
    "scotland":  "55.5,-6.5,61.0,2.0",
    "wales":     "51.3,-5.5,53.5,-2.7",
}


def _wrap_query(inner: str, bbox: str = None) -> str:
    bb = bbox or UK_BBOX
    return f"""
[out:json][timeout:120][bbox:{bb}];
(
{inner}
);
out body center;
"""


Q1_OTHER_FAITH = _wrap_query("""
  node["building"="church"]["religion"!="christian"]["religion"!~"^$"];
  way["building"="church"]["religion"!="christian"]["religion"!~"^$"];
  node["building"="chapel"]["religion"!="christian"]["religion"!~"^$"];
  way["building"="chapel"]["religion"!="christian"]["religion"!~"^$"];
""")

Q2_HOSPITALITY = _wrap_query("""
  node["building"="church"]["amenity"~"pub|bar|nightclub|restaurant|cafe|fast_food"];
  way["building"="church"]["amenity"~"pub|bar|nightclub|restaurant|cafe|fast_food"];
  node["building"="chapel"]["amenity"~"pub|bar|nightclub|restaurant|cafe|fast_food"];
  way["building"="chapel"]["amenity"~"pub|bar|nightclub|restaurant|cafe|fast_food"];
""")

Q3_RESIDENTIAL = _wrap_query("""
  node["building"="church"]["residential"];
  way["building"="church"]["residential"];
  way["building"="church"]["building:use"="residential"];
  node["building"="chapel"]["building:use"="residential"];
  way["building"="chapel"]["building:use"="residential"];
  way["historic"="church"]["building"="apartments"];
  way["historic"="church"]["building"="residential"];
""")

Q4_MOSQUE_IN_CHURCH = _wrap_query("""
  node["building"="church"]["amenity"="place_of_worship"]["religion"="muslim"];
  way["building"="church"]["amenity"="place_of_worship"]["religion"="muslim"];
  node["building"="chapel"]["religion"="muslim"];
  way["building"="chapel"]["religion"="muslim"];
""")

Q5_ARTS_COMMUNITY = _wrap_query("""
  node["building"="church"]["amenity"~"arts_centre|theatre|cinema|community_centre|library|social_centre"];
  way["building"="church"]["amenity"~"arts_centre|theatre|cinema|community_centre|library|social_centre"];
  node["building"="chapel"]["amenity"~"arts_centre|theatre|cinema|community_centre|library|social_centre"];
  way["building"="chapel"]["amenity"~"arts_centre|theatre|cinema|community_centre|library|social_centre"];
""")

Q6_EXPLICIT = _wrap_query("""
  node["building:was"="church"];
  way["building:was"="church"];
  node["was:building"="church"];
  way["was:building"="church"];
  node["converted_from"="church"];
  way["converted_from"="church"];
""")

Q7_COMMERCIAL = _wrap_query("""
  node["building"="church"]["shop"];
  way["building"="church"]["shop"];
  node["building"="church"]["office"];
  way["building"="church"]["office"];
  node["building"="church"]["amenity"="gym"];
  way["building"="church"]["amenity"="gym"];
  node["building"="chapel"]["shop"];
  way["building"="chapel"]["shop"];
""")

Q8_SPORT = _wrap_query("""
  node["building"="church"]["leisure"~"fitness_centre|sports_centre|climbing|dance"];
  way["building"="church"]["leisure"~"fitness_centre|sports_centre|climbing|dance"];
  node["building"="chapel"]["leisure"~"fitness_centre|sports_centre|climbing"];
  way["building"="chapel"]["leisure"~"fitness_centre|sports_centre|climbing"];
  node["building"="church"]["amenity"="fitness_centre"];
  way["building"="church"]["amenity"="fitness_centre"];
""")

# Historic church queries — split regionally to avoid timeout
def make_historic_queries() -> dict[str, str]:
    queries = {}
    inner = """
  node["historic"="church"]["building"!~"church|chapel"];
  way["historic"="church"]["building"!~"church|chapel"];
  node["historic"="chapel"]["building"!~"church|chapel"];
  way["historic"="chapel"]["building"!~"church|chapel"];
"""
    for region, bbox in REGIONAL_BBOXES.items():
        queries[f"historic_{region}"] = _wrap_query(inner, bbox=bbox)
    return queries


STANDARD_QUERIES = {
    "other_faith":    Q1_OTHER_FAITH,
    "hospitality":    Q2_HOSPITALITY,
    "residential":    Q3_RESIDENTIAL,
    "mosque_church":  Q4_MOSQUE_IN_CHURCH,
    "arts_community": Q5_ARTS_COMMUNITY,
    "explicit_tags":  Q6_EXPLICIT,
    "commercial":     Q7_COMMERCIAL,
    "sport_leisure":  Q8_SPORT,
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=3, min=10, max=60))
def run_overpass_query(query: str) -> list[dict]:
    resp = requests.post(
        OVERPASS_ENDPOINT,
        data={"data": query},
        headers=HEADERS,
        timeout=120,
    )
    resp.raise_for_status()
    elements = resp.json().get("elements", [])
    logger.info("  → %d OSM elements returned", len(elements))
    return elements


def classify_osm_element(tags: dict) -> tuple[str, str]:
    """
    Classify conversion type from OSM tags.
    Priority: denomination → religion → amenity → leisure → shop → office → building → name
    """
    religion    = tags.get("religion", "")
    denomination= tags.get("denomination", "").lower().strip()
    amenity     = tags.get("amenity", "")
    building    = tags.get("building", "")
    leisure     = tags.get("leisure", "")
    shop        = tags.get("shop", "")
    office      = tags.get("office", "")
    name        = tags.get("name", "").lower()

    # 1. Denomination tag — most specific
    if denomination:
        denom_key = denomination.replace(" ", "_")
        if denom_key in OSM_DENOMINATION_MAP:
            return OSM_DENOMINATION_MAP[denom_key]
        # Partial match
        for key, val in OSM_DENOMINATION_MAP.items():
            if key in denom_key or denom_key in key:
                return val

    # 2. Religion tag
    if religion and religion != "christian":
        if religion in OSM_RELIGION_MAP:
            return OSM_RELIGION_MAP[religion]
        return ("other_christian", "other_christian_general")

    # 3. Amenity tag
    if amenity and amenity in OSM_AMENITY_MAP:
        return OSM_AMENITY_MAP[amenity]

    # 4. Leisure tag
    leisure_map = {
        "fitness_centre":   ("sport_leisure", "gym_fitness"),
        "sports_centre":    ("sport_leisure", "sport_leisure_general"),
        "climbing":         ("sport_leisure", "climbing_wall"),
        "dance":            ("sport_leisure", "dance_studio"),
        "ice_rink":         ("sport_leisure", "sport_leisure_general"),
        "bowling_alley":    ("sport_leisure", "bowling_alley"),
        "escape_game":      ("sport_leisure", "escape_room"),
        "trampoline_park":  ("sport_leisure", "trampoline_park"),
    }
    if leisure and leisure in leisure_map:
        return leisure_map[leisure]

    # 5. Shop
    if shop:
        return ("commercial", "retail_shop")

    # 6. Office
    if office:
        return ("commercial", "office")

    # 7. Building tag
    if building in OSM_BUILDING_MAP:
        return OSM_BUILDING_MAP[building]

    # 8. Name-based inference (fallback)
    # Import and use NAME_DENOMINATION_RULES if available
    try:
        from constants import NAME_DENOMINATION_RULES
        for keywords, conv_type, conv_sub in NAME_DENOMINATION_RULES:
            if any(kw in name for kw in keywords):
                return conv_type, conv_sub
    except ImportError:
        pass

    # Basic name rules
    name_rules = [
        (["mosque", "masjid"],                  ("mosque", "mosque_general")),
        (["gurdwara", "sikh"],                  ("south_asian_faith", "sikh_gurdwara")),
        (["mandir", "hindu"],                   ("south_asian_faith", "hindu_mandir")),
        (["buddhist", "vihara", "sangha"],      ("eastern_philosophy", "buddhist_general")),
        (["rccg", "redeemed"],                  ("african_diaspora_church", "rccg")),
        (["kingdom hall"],                      ("new_religious_movement", "jehovahs_witness")),
        (["scientology", "dianetics"],          ("new_religious_movement", "scientology")),
        (["pub ", " inn", "tavern", " arms"],   ("hospitality", "pub")),
        (["bar", "nightclub"],                  ("hospitality", "bar")),
        (["restaurant", "kitchen", "bistro"],   ("hospitality", "restaurant")),
        (["flat", "apartment"],                 ("residential", "converted_flats")),
        (["climbing", "bouldering"],            ("sport_leisure", "climbing_wall")),
        (["skate"],                             ("sport_leisure", "skate_park")),
        (["trampoline"],                        ("sport_leisure", "trampoline_park")),
        (["escape room"],                       ("sport_leisure", "escape_room")),
        (["arts", "gallery", "theatre"],        ("arts_culture", "arts_centre")),
        (["community", "centre", "hall"],       ("community", "community_centre")),
        (["food bank", "foodbank"],             ("community", "food_bank")),
        (["lgbtq", "lgbt", "pride"],            ("community", "lgbtq_centre")),
        (["school", "academy"],                 ("education", "school")),
        (["library"],                           ("education", "library")),
        (["office", "workspace"],               ("commercial", "office")),
        (["gym", "fitness"],                    ("sport_leisure", "gym_fitness")),
        (["funeral"],                           ("commercial", "funeral_parlour")),
        (["recording studio"],                  ("arts_culture", "recording_studio")),
    ]
    for kws, result in name_rules:
        if any(kw in name for kw in kws):
            return result

    return ("unknown", "unknown")


def normalise_element(element: dict) -> Optional[dict]:
    tags  = element.get("tags", {})
    etype = element.get("type")
    osm_id= element.get("id")

    if etype == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    elif etype == "way":
        center = element.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")
    else:
        return None

    if lat is None or lon is None:
        return None

    name  = tags.get("name")
    old_name = tags.get("old_name") or tags.get("name:en")
    address_parts = [
        tags.get("addr:housenumber", ""),
        tags.get("addr:street", ""),
    ]
    address = " ".join(p for p in address_parts if p) or None
    city    = (tags.get("addr:city") or tags.get("addr:town") or
               tags.get("addr:village"))

    conv_type, conv_sub = classify_osm_element(tags)

    # Include denomination in notes for downstream enrichment
    denom = tags.get("denomination", "")
    denom_note = f" | denomination={denom}" if denom else ""

    return {
        "id":                 None,
        "church_name":        old_name,
        "former_denomination":None,
        "address":            address,
        "city":               city,
        "local_authority":    None,
        "region":             None,
        "nation":             None,
        "latitude":           lat,
        "longitude":          lon,
        "conversion_type":    conv_type,
        "conversion_subtype": conv_sub,
        "current_name":       name,
        "year_converted":     None,
        "decade":             None,
        "source":             "osm",
        "source_url":         f"https://www.openstreetmap.org/{etype}/{osm_id}",
        "confidence_score":   SOURCE_CONFIDENCE["osm"],
        "notes": (
            f"OSM {etype}/{osm_id}"
            f"{denom_note}"
            f" | tags: {dict(list(tags.items())[:6])}"
        ),
    }


def extract(include_historic_regional: bool = True) -> pd.DataFrame:
    """
    Run all OSM Overpass queries and return combined DataFrame.

    Args:
        include_historic_regional: If True, run historic_church queries
            split into 6 regional bboxes (slower but comprehensive).
            If False, skip historic_church entirely (faster).
    """
    all_rows = []
    all_queries = dict(STANDARD_QUERIES)

    if include_historic_regional:
        all_queries.update(make_historic_queries())
        logger.info(
            "Including historic_church split across %d regional bboxes",
            len(REGIONAL_BBOXES)
        )

    for query_name, query in all_queries.items():
        logger.info("=== OSM query: %s ===", query_name)
        try:
            elements = run_overpass_query(query)
            rows = [normalise_element(e) for e in elements]
            rows = [r for r in rows if r is not None]
            all_rows.extend(rows)
            logger.info("  Added %d rows from %s", len(rows), query_name)
            time.sleep(5)
        except Exception as e:
            logger.error("OSM query %s failed: %s", query_name, e)
            continue

    if not all_rows:
        logger.warning("No OSM records retrieved.")
        return pd.DataFrame(columns=MASTER_COLUMNS)

    df = pd.DataFrame(all_rows, columns=MASTER_COLUMNS)

    before = len(df)
    df = df.drop_duplicates(subset=["source_url"])
    logger.info("OSM: %d raw → %d after dedup by OSM ID", before, len(df))

    df = df[
        df["latitude"].between(49.5, 61.0) &
        df["longitude"].between(-8.2, 2.2)
    ]
    logger.info("OSM: %d after UK bounds filter", len(df))

    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = extract(include_historic_regional=True)
    print(df[["current_name", "city", "conversion_type", "conversion_subtype",
               "latitude", "longitude"]].head(20))
    print(f"\nTotal OSM records: {len(df)}")
    df.to_csv("data/raw/osm_raw.csv", index=False)
    