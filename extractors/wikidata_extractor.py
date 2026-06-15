"""
extractors/wikidata_extractor.py

Pulls verified church conversion records from Wikidata via SPARQL.
Wikidata is our highest-confidence source because entries are human-curated
and cite references. Covers all UK nations.

Strategy:
  1. Query for buildings that WERE churches/chapels (former type)
     and are now something else (current type) — using replaces/replaced_by
  2. Query for buildings tagged as mosques, pubs, etc. that have
     "formerly known as" or "replaces" a church
  3. Query via Wikipedia category membership (churches converted to mosques etc.)
"""

import time
import logging
from typing import Optional
import requests
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from constants import (
    MASTER_COLUMNS,
    SOURCE_CONFIDENCE,
    WD_CHURCH, WD_CHAPEL, WD_MOSQUE,
)

logger = logging.getLogger(__name__)

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "UKChurchConversionResearch/1.0 (academic data project; contact via github)",
    "Accept": "application/sparql-results+json",
}


# ─── SPARQL QUERIES ─────────────────────────────────────────────────────────

# Query 1: Buildings that "replaced" a church or were "formerly" a church
# Uses P1365 (replaces) and P31 (instance of) to find conversions
QUERY_REPLACES_CHURCH = """
SELECT DISTINCT
  ?item ?itemLabel ?formerLabel ?currentTypeLabel
  ?lat ?lon
  ?address ?cityLabel ?countryLabel
  ?inception ?dissolved
  ?article
WHERE {
  # The current building REPLACED something that was a church or chapel
  ?item p:P1365 ?replStatement .
  ?replStatement ps:P1365 ?former .
  ?former wdt:P31/wdt:P279* wd:Q16970 .  # former was instance of church (or subclass)

  # Must be in the United Kingdom
  ?item wdt:P17 wd:Q145 .

  # Get coordinates
  OPTIONAL { ?item wdt:P625 ?coord .
    BIND(geof:latitude(?coord) AS ?lat)
    BIND(geof:longitude(?coord) AS ?lon)
  }

  # Get current type label
  OPTIONAL { ?item wdt:P31 ?currentType . }

  # Get address fields
  OPTIONAL { ?item wdt:P6375 ?address . }
  OPTIONAL { ?item wdt:P131 ?city . }

  # Get dates
  OPTIONAL { ?item wdt:P571 ?inception . }
  OPTIONAL { ?item wdt:P576 ?dissolved . }

  # Wikipedia article link (for source_url)
  OPTIONAL {
    ?article schema:about ?item ;
             schema:isPartOf <https://en.wikipedia.org/> .
  }

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en" .
  }
}
LIMIT 2000
"""

# Query 2: Buildings tagged as "formerly a church" via P31 historical
QUERY_FORMERLY_CHURCH = """
SELECT DISTINCT
  ?item ?itemLabel ?formerTypeLabel ?currentTypeLabel
  ?lat ?lon
  ?address ?cityLabel
  ?article
WHERE {
  # Item has a former instance-of that is a church
  ?item p:P31 ?stmt .
  ?stmt ps:P31 ?formerType .
  ?stmt pq:P582 ?endTime .         # with an end time (means it's no longer that type)
  ?formerType wdt:P279* wd:Q16970 . # church or subclass

  # Current type is something different
  ?item wdt:P31 ?currentType .
  FILTER(?currentType != ?formerType)
  FILTER(?currentType != wd:Q16970)

  # UK only
  ?item wdt:P17 wd:Q145 .

  # Coordinates
  OPTIONAL { ?item wdt:P625 ?coord .
    BIND(geof:latitude(?coord) AS ?lat)
    BIND(geof:longitude(?coord) AS ?lon)
  }

  OPTIONAL { ?item wdt:P6375 ?address . }
  OPTIONAL { ?item wdt:P131 ?city . }

  OPTIONAL {
    ?article schema:about ?item ;
             schema:isPartOf <https://en.wikipedia.org/> .
  }

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en" .
  }
}
LIMIT 2000
"""

# Query 3: Specifically mosques in UK that were formerly churches
# (High specificity, used as cross-check)
QUERY_MOSQUES_FROM_CHURCHES = """
SELECT DISTINCT
  ?item ?itemLabel
  ?lat ?lon
  ?address ?cityLabel
  ?inceptionYear
  ?article
WHERE {
  ?item wdt:P31/wdt:P279* wd:Q32815 .   # mosque or subclass
  ?item wdt:P17 wd:Q145 .                # UK

  # Was formerly a church
  { ?item wdt:P1365 ?former . ?former wdt:P31/wdt:P279* wd:Q16970 . }
  UNION
  { ?item wdt:P31 ?t . ?t wdt:P279* wd:Q16970 .
    ?item p:P31 ?s . ?s pq:P582 ?end . }

  OPTIONAL { ?item wdt:P625 ?coord .
    BIND(geof:latitude(?coord) AS ?lat)
    BIND(geof:longitude(?coord) AS ?lon)
  }

  OPTIONAL { ?item wdt:P6375 ?address . }
  OPTIONAL { ?item wdt:P131 ?city . }

  OPTIONAL {
    ?item wdt:P571 ?inception .
    BIND(YEAR(?inception) AS ?inceptionYear)
  }

  OPTIONAL {
    ?article schema:about ?item ;
             schema:isPartOf <https://en.wikipedia.org/> .
  }

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en" .
  }
}
LIMIT 500
"""

# Query 4: Wikipedia category-based — catches things the property graph misses
QUERY_CATEGORY_CONVERTED = """
SELECT DISTINCT ?item ?itemLabel ?lat ?lon ?cityLabel ?article
WHERE {
  # Member of Wikipedia categories about converted churches
  {
    ?article schema:about ?item ;
             schema:isPartOf <https://en.wikipedia.org/> ;
             schema:name ?catName .
    FILTER(CONTAINS(LCASE(?catName), "converted") && CONTAINS(LCASE(?catName), "church"))
  }
  UNION
  {
    ?article schema:about ?item ;
             schema:isPartOf <https://en.wikipedia.org/> ;
             schema:name ?catName .
    FILTER(CONTAINS(LCASE(?catName), "former") && CONTAINS(LCASE(?catName), "church"))
  }

  ?item wdt:P17 wd:Q145 .

  OPTIONAL { ?item wdt:P625 ?coord .
    BIND(geof:latitude(?coord) AS ?lat)
    BIND(geof:longitude(?coord) AS ?lon)
  }
  OPTIONAL { ?item wdt:P131 ?city . }

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en" .
  }
}
LIMIT 1000
"""


# ─── CONVERSION TYPE CLASSIFIER ─────────────────────────────────────────────

# Maps Wikidata Q-IDs to our taxonomy
# Extend this as new Q-IDs appear in results
QTYPE_TO_CONVERSION = {
    # Religious — other faiths
    "Q32815":  ("mosque",      "mosque_general"),
    "Q193727": ("other_faith", "sikh_gurdwara"),
    "Q44539":  ("other_faith", "hindu_temple"),
    "Q1128397":("other_faith", "buddhist_temple"),
    "Q34627":  ("other_faith", "jewish_synagogue"),
    # Residential
    "Q11755880": ("residential", "converted_flats"),
    "Q3947":     ("residential", "single_dwelling"),
    "Q22811":    ("residential", "care_home"),
    # Hospitality
    "Q212198":   ("hospitality", "pub"),
    "Q622425":   ("hospitality", "nightclub"),
    "Q11707":    ("hospitality", "restaurant"),
    "Q27686":    ("hospitality", "hotel"),
    # Arts & Culture
    "Q483110":   ("arts_culture", "theatre"),
    "Q41253":    ("arts_culture", "cinema"),
    "Q23413":    ("arts_culture", "arts_centre"),
    "Q33506":    ("arts_culture", "museum"),
    # Education
    "Q3914":     ("education",   "school"),
    "Q7075":     ("education",   "library"),
    # Community
    "Q2012352":  ("community",   "community_centre"),
    # Commercial
    "Q175002":   ("commercial",  "office"),
    "Q570116":   ("commercial",  "supermarket"),
    "Q40357":    ("commercial",  "gym"),
    # Demolished
    "Q811534":   ("demolished",  "demolished_cleared"),
}

def classify_from_label(label: str) -> tuple[str, str]:
    """
    Fallback classifier using the current-type label text when
    we don't have a Q-ID match.
    """
    label_lower = label.lower()

    rules = [
        (["mosque", "masjid", "islamic centre", "muslim"],    ("mosque", "mosque_general")),
        (["gurdwara", "sikh"],                                 ("other_faith", "sikh_gurdwara")),
        (["hindu temple", "mandir"],                           ("other_faith", "hindu_temple")),
        (["synagogue", "jewish"],                              ("other_faith", "jewish_synagogue")),
        (["buddhist"],                                         ("other_faith", "buddhist_temple")),
        (["pentecostal", "evangelical", "new apostolic",
          "jehovah", "latter-day", "seventh-day"],             ("other_faith", "other_christian")),
        (["flat", "apartment", "residential", "housing",
          "dwelling", "home", "house"],                        ("residential", "residential_general")),
        (["pub", "tavern", "inn", "ale house"],                ("hospitality", "pub")),
        (["nightclub", "club", "bar", "disco"],                ("hospitality", "nightclub")),
        (["restaurant", "brasserie", "bistro"],                ("hospitality", "restaurant")),
        (["hotel", "hostel", "b&b", "bed and breakfast"],      ("hospitality", "hotel")),
        (["theatre", "theater", "playhouse"],                  ("arts_culture", "theatre")),
        (["cinema", "movie"],                                  ("arts_culture", "cinema")),
        (["arts centre", "art center", "gallery",
          "creative", "exhibition"],                           ("arts_culture", "arts_centre")),
        (["museum", "heritage"],                               ("arts_culture", "museum")),
        (["school", "academy", "college", "university",
          "nursery"],                                          ("education", "school")),
        (["library"],                                          ("education", "library")),
        (["community centre", "community hall",
          "community hub", "youth centre"],                    ("community", "community_centre")),
        (["office", "workspace", "co-working"],                ("commercial", "office")),
        (["supermarket", "shop", "retail", "store"],           ("commercial", "shop")),
        (["gym", "fitness", "climbing"],                       ("commercial", "gym")),
        (["demolished", "cleared", "removed"],                 ("demolished", "demolished_cleared")),
        (["derelict", "vacant", "empty", "unused"],            ("vacant", "derelict")),
        (["tourist", "visitor centre", "attraction"],          ("tourist", "heritage_attraction")),
    ]

    for keywords, result in rules:
        if any(kw in label_lower for kw in keywords):
            return result

    return ("unknown", "unknown")


# ─── API CALL WITH RETRY ─────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
def run_sparql_query(query: str) -> list[dict]:
    """Execute a SPARQL query against the Wikidata endpoint."""
    logger.info("Running SPARQL query (%d chars)", len(query))
    resp = requests.get(
        WIKIDATA_ENDPOINT,
        params={"query": query, "format": "json"},
        headers=HEADERS,
        timeout=60,
    )
    resp.raise_for_status()
    results = resp.json()
    bindings = results.get("results", {}).get("bindings", [])
    logger.info("  → %d results returned", len(bindings))
    return bindings


def _safe_value(binding: dict, key: str) -> Optional[str]:
    """Safely extract a value from a SPARQL binding."""
    return binding.get(key, {}).get("value")


def _extract_qid(uri: Optional[str]) -> Optional[str]:
    """Extract Q12345 from a Wikidata URI."""
    if uri and "wikidata.org/entity/" in uri:
        return uri.split("/entity/")[-1]
    return None


def _year_from_xsd(xsd_date: Optional[str]) -> Optional[int]:
    """Parse '2003-01-01T00:00:00Z' → 2003"""
    if not xsd_date:
        return None
    try:
        return int(xsd_date[:4])
    except (ValueError, IndexError):
        return None


# ─── NORMALISE SPARQL RESULTS ────────────────────────────────────────────────

def normalise_results(
    bindings: list[dict],
    query_name: str,
    fixed_conversion: Optional[tuple] = None,
) -> list[dict]:
    """
    Convert raw SPARQL bindings into normalised rows matching MASTER_COLUMNS.

    Args:
        bindings: Raw SPARQL result bindings
        query_name: Label for logging/source tracking
        fixed_conversion: If this query is specific to one type (e.g. mosque),
                          pass (conversion_type, conversion_subtype) directly.
    """
    rows = []

    for b in bindings:
        item_uri    = _safe_value(b, "item")
        item_label  = _safe_value(b, "itemLabel")
        current_lbl = _safe_value(b, "currentTypeLabel") or _safe_value(b, "formerTypeLabel") or ""
        city_label  = _safe_value(b, "cityLabel")
        article_url = _safe_value(b, "article")
        address     = _safe_value(b, "address")

        lat_str = _safe_value(b, "lat")
        lon_str = _safe_value(b, "lon")
        try:
            lat = float(lat_str) if lat_str else None
            lon = float(lon_str) if lon_str else None
        except ValueError:
            lat, lon = None, None

        # Year
        year = _year_from_xsd(_safe_value(b, "inception") or _safe_value(b, "inceptionYear"))

        # Classify conversion
        if fixed_conversion:
            conv_type, conv_subtype = fixed_conversion
        else:
            # Try Q-ID first
            current_qid = _extract_qid(_safe_value(b, "currentType"))
            if current_qid and current_qid in QTYPE_TO_CONVERSION:
                conv_type, conv_subtype = QTYPE_TO_CONVERSION[current_qid]
            else:
                conv_type, conv_subtype = classify_from_label(current_lbl or item_label or "")

        row = {
            "id":                 None,   # assigned at load stage
            "church_name":        None,   # we don't know the former name from these queries
            "former_denomination":None,
            "address":            address,
            "city":               city_label,
            "local_authority":    None,   # enriched later
            "region":             None,   # enriched later
            "nation":             None,   # enriched later
            "latitude":           lat,
            "longitude":          lon,
            "conversion_type":    conv_type,
            "conversion_subtype": conv_subtype,
            "current_name":       item_label,
            "year_converted":     year,
            "decade":             f"{(year // 10) * 10}s" if year else None,
            "source":             f"wikidata_{query_name}",
            "source_url":         article_url or item_uri,
            "confidence_score":   SOURCE_CONFIDENCE["wikidata"],
            "notes":              f"Wikidata: {item_uri}",
        }
        rows.append(row)

    return rows


# ─── MAIN EXTRACTOR ──────────────────────────────────────────────────────────

def extract() -> pd.DataFrame:
    """
    Run all Wikidata queries and return a combined, deduplicated DataFrame.
    """
    all_rows = []

    queries = [
        ("replaces_church",      QUERY_REPLACES_CHURCH,      None),
        ("formerly_church",      QUERY_FORMERLY_CHURCH,      None),
        ("mosques_from_churches",QUERY_MOSQUES_FROM_CHURCHES,("mosque", "mosque_general")),
        ("category_converted",   QUERY_CATEGORY_CONVERTED,   None),
    ]

    for name, query, fixed in queries:
        logger.info("=== Running Wikidata query: %s ===", name)
        try:
            bindings = run_sparql_query(query)
            rows = normalise_results(bindings, name, fixed)
            all_rows.extend(rows)
            logger.info("  Added %d rows from %s", len(rows), name)
            time.sleep(2)  # Be polite to Wikidata servers
        except Exception as e:
            logger.error("Query %s failed: %s", name, e)
            continue

    if not all_rows:
        logger.warning("No Wikidata records retrieved.")
        return pd.DataFrame(columns=MASTER_COLUMNS)

    df = pd.DataFrame(all_rows, columns=MASTER_COLUMNS)

    # Basic dedup within Wikidata: same current_name + lat/lon
    before = len(df)
    df = df.drop_duplicates(subset=["current_name", "latitude", "longitude"])
    logger.info("Wikidata: %d raw → %d after internal dedup", before, len(df))

    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = extract()
    print(df[["current_name", "city", "conversion_type", "year_converted"]].head(20))
    print(f"\nTotal Wikidata records: {len(df)}")
    df.to_csv("/home/claude/church_conversion_pipeline/data/raw/wikidata_raw.csv", index=False)
