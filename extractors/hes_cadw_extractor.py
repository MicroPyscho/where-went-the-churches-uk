"""
extractors/hes_cadw_extractor.py

Historic Environment Scotland (HES) and Cadw (Wales) listed buildings extractors.

These are the Scottish and Welsh equivalents of the Historic England NHLE.
Together they close the major geographic gap in the dataset.

SCOTLAND — Historic Environment Scotland
  Portal: https://portal.historicenvironment.scot/spatialdownloads
  Dataset: Listed Buildings (GeoJSON or CSV)
  Coverage: ~47,000 listed buildings in Scotland
  Licence: Open Government Licence v3.0
  Attribution: Contains Historic Environment Scotland and Ordnance Survey data
                © Historic Environment Scotland - Scottish Charity No. SC045925

WALES — Cadw via DataMapWales
  Portal: https://datamap.gov.wales/layers/inspire-wg:Cadw_ListedBuildings
  Dataset: Listed Buildings (GeoJSON via WFS)
  Coverage: ~30,000 listed buildings in Wales
  Licence: Open Government Licence v3.0
  Attribution: Designated Historic Asset GIS Data, The Welsh Historic
                Environment Service (Cadw), licensed under OGL v3.0

NORTHERN IRELAND — Historic Environment NI
  Portal: https://www.communities-ni.gov.uk/services/listed-buildings
  Dataset: Listed Buildings Register (CSV/spreadsheet)
  Coverage: ~8,500 listed buildings in NI

Manual download steps (APIs require registration or GIS software):

  SCOTLAND:
  1. Go to https://portal.historicenvironment.scot/spatialdownloads
  2. Click "Listed Buildings"
  3. Download as GeoJSON or CSV
  4. Save to data/raw/hes_listed_buildings.geojson (or .csv)

  WALES:
  1. Go to https://datamap.gov.wales/layers/inspire-wg:Cadw_ListedBuildings
  2. Click Download → GeoJSON
  3. Save to data/raw/cadw_listed_buildings.geojson

  NORTHERN IRELAND:
  1. Go to https://www.communities-ni.gov.uk/services/listed-buildings
  2. Download the register spreadsheet
  3. Save to data/raw/heni_listed_buildings.csv

Once downloaded, run:
  python extractors/hes_cadw_extractor.py

This extractor also queries the HES WFS API directly for church buildings,
which may work without manual download.
"""

import logging
import re
import json
from pathlib import Path
from typing import Optional
import requests
import pandas as pd

try:
    from constants import MASTER_COLUMNS, SOURCE_CONFIDENCE
except ImportError:
    MASTER_COLUMNS = []
    SOURCE_CONFIDENCE = {"hes": 0.88, "cadw": 0.88, "heni": 0.85}

logger = logging.getLogger(__name__)

CHURCH_KEYWORDS = [
    "church", "chapel", "cathedral", "minster", "abbey", "priory",
    "kirk",        # Scottish word for church
    "meeting house", "congregation", "tabernacle", "oratory",
    "mission hall", "gospel hall", "bethel", "ebenezer", "zion",
    "methodist", "baptist", "presbyterian", "reformed",
]

# WFS API endpoints (may work without manual download)
HES_WFS = "https://portal.historicenvironment.scot/arcgis/rest/services/HES/ListedBuildings/MapServer/0/query"
CADW_WFS = "https://datamap.gov.wales/geoserver/inspire-wg/wfs"


# ─── HES (SCOTLAND) ──────────────────────────────────────────────────────────

def fetch_hes_via_api(max_records: int = 5000) -> list[dict]:
    """
    Try to fetch HES listed buildings via ArcGIS REST API.
    Filters for church/chapel keywords in the name.
    """
    records = []
    offset = 0
    batch = 1000

    logger.info("Querying HES ArcGIS REST API...")

    while offset < max_records:
        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": batch,
        }
        try:
            resp = requests.get(HES_WFS, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features", [])
            if not features:
                break
            for f in features:
                attrs = f.get("attributes", {})
                geom = f.get("geometry", {})
                name = str(attrs.get("NAME") or attrs.get("ADDRESS") or "")
                if any(kw in name.lower() for kw in CHURCH_KEYWORDS):
                    records.append({
                        "name": name,
                        "category": attrs.get("CATEGORY", ""),
                        "listing_date": attrs.get("LISTDATE", ""),
                        "listing_grade": attrs.get("GRADE", ""),
                        "address": attrs.get("ADDRESS", ""),
                        "local_authority": attrs.get("LA_NAME", ""),
                        "lat": geom.get("y"),
                        "lon": geom.get("x"),
                        "ref": str(attrs.get("LB_REFERENCE") or attrs.get("OBJECTID", "")),
                    })
            offset += batch
            logger.info("HES API: %d church records so far (offset %d)", len(records), offset)
        except Exception as e:
            logger.warning("HES API failed at offset %d: %s", offset, e)
            break

    return records


def load_hes_from_file(filepath: str) -> list[dict]:
    """Load HES data from manually downloaded GeoJSON or CSV."""
    path = Path(filepath)
    if not path.exists():
        return []

    logger.info("Loading HES data from %s", filepath)

    if filepath.endswith(".geojson") or filepath.endswith(".json"):
        with open(filepath) as f:
            data = json.load(f)
        features = data.get("features", [])
        records = []
        for f in features:
            props = f.get("properties", {})
            geom = f.get("geometry", {})
            name = str(props.get("NAME") or props.get("ADDRESS") or "")
            if not any(kw in name.lower() for kw in CHURCH_KEYWORDS):
                continue
            coords = geom.get("coordinates", [None, None])
            records.append({
                "name": name,
                "category": props.get("CATEGORY", ""),
                "listing_date": props.get("LISTDATE", ""),
                "listing_grade": props.get("GRADE", ""),
                "address": props.get("ADDRESS", ""),
                "local_authority": props.get("LA_NAME", ""),
                "lat": coords[1] if len(coords) > 1 else None,
                "lon": coords[0] if len(coords) > 0 else None,
                "ref": str(props.get("LB_REFERENCE") or ""),
            })
        return records

    elif filepath.endswith(".csv"):
        df = pd.read_csv(filepath, low_memory=False)
        # Try common column name patterns
        name_col = next((c for c in df.columns if "name" in c.lower() or "address" in c.lower()), None)
        lat_col = next((c for c in df.columns if "lat" in c.lower() or "y" == c.lower()), None)
        lon_col = next((c for c in df.columns if "lon" in c.lower() or "x" == c.lower() or "lng" in c.lower()), None)

        if not name_col:
            logger.warning("Could not identify name column in HES CSV. Columns: %s", df.columns.tolist())
            return []

        mask = df[name_col].str.lower().str.contains("|".join(CHURCH_KEYWORDS), na=False)
        filtered = df[mask]
        records = []
        for _, row in filtered.iterrows():
            records.append({
                "name": str(row.get(name_col, "")),
                "lat": float(row[lat_col]) if lat_col and pd.notna(row.get(lat_col)) else None,
                "lon": float(row[lon_col]) if lon_col and pd.notna(row.get(lon_col)) else None,
                "local_authority": str(row.get("LA_NAME") or row.get("local_authority") or ""),
                "listing_grade": str(row.get("GRADE") or row.get("grade") or ""),
                "ref": str(row.get("LB_REFERENCE") or row.get("ref") or ""),
            })
        return records

    return []


def normalise_hes(records: list[dict]) -> pd.DataFrame:
    """Convert HES records to pipeline schema."""
    rows = []
    for r in records:
        lat = r.get("lat")
        lon = r.get("lon")
        if not lat or not lon:
            continue
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        # Scotland bounds check
        if not (54.5 < lat < 61.0 and -8.2 < lon < -0.5):
            continue

        name = r.get("name", "")
        ref = r.get("ref", "")

        rows.append({
            "id": None,
            "church_name": name,
            "former_denomination": None,
            "address": r.get("address", ""),
            "city": None,
            "local_authority": r.get("local_authority", ""),
            "region": "Scotland",
            "nation": "Scotland",
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "conversion_type": "unknown",
            "conversion_subtype": "unknown",
            "current_name": None,
            "year_converted": None,
            "decade": None,
            "source": "hes",
            "source_url": f"https://portal.historicenvironment.scot/designation/LB{ref}" if ref else "",
            "confidence_score": SOURCE_CONFIDENCE.get("hes", 0.88),
            "notes": f"HES Listed Building #{ref} | Grade: {r.get('listing_grade','')}",
        })

    if not rows:
        return pd.DataFrame(columns=MASTER_COLUMNS) if MASTER_COLUMNS else pd.DataFrame()

    df = pd.DataFrame(rows)
    if MASTER_COLUMNS:
        for col in MASTER_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[MASTER_COLUMNS]
    return df


# ─── CADW (WALES) ────────────────────────────────────────────────────────────

def fetch_cadw_via_wfs(max_features: int = 5000) -> list[dict]:
    """
    Fetch Cadw listed buildings via WFS API from DataMapWales.
    Filters for church/chapel keywords.
    """
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": "inspire-wg:Cadw_ListedBuildings",
        "outputFormat": "application/json",
        "count": max_features,
        "srsName": "EPSG:4326",
    }

    logger.info("Querying Cadw WFS API...")
    try:
        resp = requests.get(CADW_WFS, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        logger.info("Cadw WFS returned %d total features", len(features))

        records = []
        for f in features:
            props = f.get("properties", {})
            geom = f.get("geometry", {})

            name = str(
                props.get("BUILDING_NAME") or
                props.get("NAME") or
                props.get("address") or
                props.get("BUILDING_ADDRESS") or ""
            )

            if not any(kw in name.lower() for kw in CHURCH_KEYWORDS):
                # Also check description/notes fields
                desc = str(props.get("DESCRIPTION") or props.get("NOTES") or "")
                if not any(kw in desc.lower() for kw in CHURCH_KEYWORDS):
                    continue

            coords = []
            if geom:
                gt = geom.get("type", "")
                if gt == "Point":
                    coords = geom.get("coordinates", [])
                elif gt == "MultiPoint":
                    coords = geom.get("coordinates", [[]])[0]
                elif gt in ("Polygon", "MultiPolygon"):
                    # Use centroid approximation
                    all_coords = []
                    raw = geom.get("coordinates", [])
                    if gt == "Polygon" and raw:
                        all_coords = raw[0]
                    elif gt == "MultiPolygon" and raw:
                        all_coords = raw[0][0]
                    if all_coords:
                        coords = [
                            sum(c[0] for c in all_coords) / len(all_coords),
                            sum(c[1] for c in all_coords) / len(all_coords),
                        ]

            records.append({
                "name": name,
                "grade": props.get("GRADE") or props.get("ListingGrade", ""),
                "ref": str(props.get("CADW_REF") or props.get("LB_REF") or props.get("OBJECTID", "")),
                "address": props.get("ADDRESS") or props.get("BUILDING_ADDRESS", ""),
                "local_authority": props.get("LA_NAME") or props.get("LOCAL_AUTHORITY", ""),
                "lat": coords[1] if len(coords) > 1 else None,
                "lon": coords[0] if len(coords) > 0 else None,
            })

        return records

    except Exception as e:
        logger.error("Cadw WFS API failed: %s", e)
        logger.info("Try manual download from: https://datamap.gov.wales/layers/inspire-wg:Cadw_ListedBuildings")
        return []


def load_cadw_from_file(filepath: str) -> list[dict]:
    """Load Cadw data from manually downloaded GeoJSON."""
    path = Path(filepath)
    if not path.exists():
        return []

    logger.info("Loading Cadw data from %s", filepath)

    with open(filepath) as f:
        data = json.load(f)

    features = data.get("features", [])
    records = []
    for f in features:
        props = f.get("properties", {})
        geom = f.get("geometry", {})
        name = str(props.get("BUILDING_NAME") or props.get("NAME") or "")
        if not any(kw in name.lower() for kw in CHURCH_KEYWORDS):
            continue
        coords = geom.get("coordinates", [None, None])
        records.append({
            "name": name,
            "grade": props.get("GRADE", ""),
            "ref": str(props.get("CADW_REF") or ""),
            "address": str(props.get("ADDRESS") or ""),
            "local_authority": str(props.get("LA_NAME") or ""),
            "lat": coords[1] if len(coords) > 1 else None,
            "lon": coords[0] if len(coords) > 0 else None,
        })
    return records


def normalise_cadw(records: list[dict]) -> pd.DataFrame:
    """Convert Cadw records to pipeline schema."""
    rows = []
    for r in records:
        lat = r.get("lat")
        lon = r.get("lon")
        if not lat or not lon:
            continue
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        # Wales bounds check
        if not (51.3 < lat < 53.5 and -5.5 < lon < -2.6):
            continue

        ref = r.get("ref", "")
        rows.append({
            "id": None,
            "church_name": r.get("name", ""),
            "former_denomination": None,
            "address": r.get("address", ""),
            "city": None,
            "local_authority": r.get("local_authority", ""),
            "region": "Wales",
            "nation": "Wales",
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "conversion_type": "unknown",
            "conversion_subtype": "unknown",
            "current_name": None,
            "year_converted": None,
            "decade": None,
            "source": "cadw",
            "source_url": f"https://cadw.gov.wales/advice-support/cof-cymru/find-historic-assets?ref={ref}" if ref else "",
            "confidence_score": SOURCE_CONFIDENCE.get("cadw", 0.88),
            "notes": f"Cadw Listed Building #{ref} | Grade: {r.get('grade','')}",
        })

    if not rows:
        return pd.DataFrame(columns=MASTER_COLUMNS) if MASTER_COLUMNS else pd.DataFrame()

    df = pd.DataFrame(rows)
    if MASTER_COLUMNS:
        for col in MASTER_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[MASTER_COLUMNS]
    return df


# ─── NORTHERN IRELAND ────────────────────────────────────────────────────────

def load_heni_from_file(filepath: str) -> pd.DataFrame:
    """
    Load Historic Environment NI listed buildings from downloaded CSV/spreadsheet.

    Download from:
    https://www.communities-ni.gov.uk/services/listed-buildings
    or via the NI Open Data portal:
    https://www.opendatani.gov.uk/dataset/listed-buildings
    """
    path = Path(filepath)
    if not path.exists():
        logger.warning("HENI file not found: %s", filepath)
        return pd.DataFrame(columns=MASTER_COLUMNS) if MASTER_COLUMNS else pd.DataFrame()

    logger.info("Loading HENI data from %s", filepath)

    if filepath.endswith(".csv"):
        df_raw = pd.read_csv(filepath, low_memory=False)
    else:
        df_raw = pd.read_excel(filepath)

    # Identify columns
    name_col = next((c for c in df_raw.columns if "name" in c.lower()), None)
    lat_col = next((c for c in df_raw.columns if "lat" in c.lower()), None)
    lon_col = next((c for c in df_raw.columns if "lon" in c.lower() or "lng" in c.lower()), None)

    if not name_col:
        logger.error("Could not find name column in HENI file. Columns: %s", df_raw.columns.tolist())
        return pd.DataFrame()

    # Filter for church keywords
    mask = df_raw[name_col].str.lower().str.contains("|".join(CHURCH_KEYWORDS), na=False)
    filtered = df_raw[mask]
    logger.info("HENI: %d church buildings found", len(filtered))

    rows = []
    for _, row in filtered.iterrows():
        lat = float(row[lat_col]) if lat_col and pd.notna(row.get(lat_col)) else None
        lon = float(row[lon_col]) if lon_col and pd.notna(row.get(lon_col)) else None

        if not lat or not lon:
            continue
        if not (54.0 < lat < 55.4 and -8.2 < lon < -5.3):
            continue

        rows.append({
            "id": None,
            "church_name": str(row.get(name_col, "")),
            "former_denomination": None,
            "address": str(row.get("address") or row.get("Address") or ""),
            "city": str(row.get("town") or row.get("Town") or ""),
            "local_authority": str(row.get("district") or row.get("District") or ""),
            "region": "Northern Ireland",
            "nation": "Northern Ireland",
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "conversion_type": "unknown",
            "conversion_subtype": "unknown",
            "current_name": None,
            "year_converted": None,
            "decade": None,
            "source": "heni",
            "source_url": "",
            "confidence_score": SOURCE_CONFIDENCE.get("heni", 0.85),
            "notes": f"Historic Environment NI listed building",
        })

    if not rows:
        return pd.DataFrame(columns=MASTER_COLUMNS) if MASTER_COLUMNS else pd.DataFrame()

    df = pd.DataFrame(rows)
    if MASTER_COLUMNS:
        for col in MASTER_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[MASTER_COLUMNS]
    return df


# ─── COMBINED EXTRACT ─────────────────────────────────────────────────────────

def extract(
    hes_file: str = "data/raw/hes_listed_buildings.geojson",
    cadw_file: str = "data/raw/cadw_listed_buildings.geojson",
    heni_file: str = "data/raw/heni_listed_buildings.csv",
    try_api: bool = True,
) -> pd.DataFrame:
    """
    Extract church buildings from HES (Scotland), Cadw (Wales), and HENI (Northern Ireland).

    Tries file downloads first, falls back to API where available.
    """
    dfs = []

    # ── Scotland (HES) ────────────────────────────────────────────────────────
    logger.info("=== Historic Environment Scotland ===")
    hes_records = load_hes_from_file(hes_file)
    if not hes_records and try_api:
        logger.info("No HES file found — trying API...")
        hes_records = fetch_hes_via_api()
    if hes_records:
        df_hes = normalise_hes(hes_records)
        logger.info("HES: %d church records", len(df_hes))
        dfs.append(df_hes)
    else:
        logger.warning(
            "No HES data obtained.\n"
            "Manual download: https://portal.historicenvironment.scot/spatialdownloads\n"
            "Save as: data/raw/hes_listed_buildings.geojson"
        )

    # ── Wales (Cadw) ──────────────────────────────────────────────────────────
    logger.info("=== Cadw (Wales) ===")
    cadw_records = load_cadw_from_file(cadw_file)
    if not cadw_records and try_api:
        logger.info("No Cadw file found — trying WFS API...")
        cadw_records = fetch_cadw_via_wfs()
    if cadw_records:
        df_cadw = normalise_cadw(cadw_records)
        logger.info("Cadw: %d church records", len(df_cadw))
        dfs.append(df_cadw)
    else:
        logger.warning(
            "No Cadw data obtained.\n"
            "Manual download: https://datamap.gov.wales/layers/inspire-wg:Cadw_ListedBuildings\n"
            "Save as: data/raw/cadw_listed_buildings.geojson"
        )

    # ── Northern Ireland (HENI) ───────────────────────────────────────────────
    logger.info("=== Historic Environment NI ===")
    df_heni = load_heni_from_file(heni_file)
    if not df_heni.empty:
        logger.info("HENI: %d church records", len(df_heni))
        dfs.append(df_heni)
    else:
        logger.warning(
            "No HENI data obtained.\n"
            "Download from: https://www.opendatani.gov.uk/dataset/listed-buildings\n"
            "Save as: data/raw/heni_listed_buildings.csv"
        )

    if not dfs:
        logger.error("No data from any source. Check downloads.")
        return pd.DataFrame(columns=MASTER_COLUMNS) if MASTER_COLUMNS else pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)

    logger.info(
        "Combined: %d records (Scotland: %d, Wales: %d, NI: %d)",
        len(combined),
        len(combined[combined["nation"] == "Scotland"]),
        len(combined[combined["nation"] == "Wales"]),
        len(combined[combined["nation"] == "Northern Ireland"]),
    )

    return combined


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(
        description="Extract HES (Scotland), Cadw (Wales), and HENI (NI) church buildings"
    )
    parser.add_argument("--hes-file", default="data/raw/hes_listed_buildings.geojson")
    parser.add_argument("--cadw-file", default="data/raw/cadw_listed_buildings.geojson")
    parser.add_argument("--heni-file", default="data/raw/heni_listed_buildings.csv")
    parser.add_argument("--no-api", action="store_true",
                        help="Don't try API fallback, only use local files")
    args = parser.parse_args()

    df = extract(
        hes_file=args.hes_file,
        cadw_file=args.cadw_file,
        heni_file=args.heni_file,
        try_api=not args.no_api,
    )

    print(f"\nTotal records: {len(df)}")
    if not df.empty:
        print(df[["church_name", "city", "nation", "latitude", "longitude"]].head(20).to_string())
        df.to_csv("data/raw/hes_cadw_heni_raw.csv", index=False)
        print("\nSaved to data/raw/hes_cadw_heni_raw.csv")
        print("\nTo use in the pipeline, add 'hes_cadw' to main.py sources list.")