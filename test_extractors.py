"""
test_extractors.py

Run this BEFORE the full pipeline to verify each extractor works individually.
Pulls a small sample from each source and prints results.

Usage:
    python test_extractors.py
    python test_extractors.py --source wikidata
    python test_extractors.py --source osm
"""

import sys
import time
import argparse
import logging

# Silence verbose logs during testing
logging.basicConfig(level=logging.WARNING)

# Rich for nice output (falls back to plain print if not installed)
try:
    from rich.console import Console
    from rich.table import Table
    from rich import print as rprint
    console = Console()
    USE_RICH = True
except ImportError:
    USE_RICH = False
    console = None

import requests


def header(text):
    if USE_RICH:
        console.rule(f"[bold blue]{text}[/bold blue]")
    else:
        print(f"\n{'='*60}")
        print(f"  {text}")
        print('='*60)


def ok(msg):
    print(f"  ✓  {msg}")


def warn(msg):
    print(f"  ⚠  {msg}")


def fail(msg):
    print(f"  ✗  {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: Wikidata
# ─────────────────────────────────────────────────────────────────────────────

def test_wikidata():
    header("Test 1: Wikidata SPARQL")

    # Minimal query — just 5 UK converted church records
    query = """
    SELECT ?item ?itemLabel ?lat ?lon WHERE {
      ?item wdt:P31/wdt:P279* wd:Q32815 .
      ?item wdt:P17 wd:Q145 .
      ?item p:P1365 ?s . ?s ps:P1365 ?former .
      ?former wdt:P31/wdt:P279* wd:Q16970 .
      OPTIONAL { ?item wdt:P625 ?coord .
        BIND(geof:latitude(?coord) AS ?lat)
        BIND(geof:longitude(?coord) AS ?lon)
      }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
    }
    LIMIT 5
    """

    try:
        resp = requests.get(
            "https://query.wikidata.org/sparql",
            params={"query": query, "format": "json"},
            headers={"User-Agent": "UKChurchConversionTest/1.0"},
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("results", {}).get("bindings", [])

        if results:
            ok(f"Wikidata reachable — {len(results)} sample records returned")
            for r in results:
                name = r.get("itemLabel", {}).get("value", "unknown")
                lat  = r.get("lat", {}).get("value", "no coords")
                print(f"      → {name}  (lat: {lat})")
            return True
        else:
            warn("Wikidata reachable but returned 0 results — query may need adjustment")
            return False

    except requests.exceptions.Timeout:
        fail("Wikidata timed out (30s) — check your internet connection")
        return False
    except Exception as e:
        fail(f"Wikidata failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: OpenStreetMap Overpass
# ─────────────────────────────────────────────────────────────────────────────

def test_osm():
    header("Test 2: OpenStreetMap Overpass API")

    # Tiny query — just churches with non-Christian religion tag in London
    query = """
[out:json][timeout:30][bbox:51.3,-0.5,51.7,0.3];
(
  way["building"="church"]["religion"!="christian"]["religion"!~"^$"];
  node["building"="church"]["religion"!="christian"]["religion"!~"^$"];
);
out body center;
"""

    try:
        resp = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            headers={"User-Agent": "UKChurchConversionTest/1.0"},
            timeout=45,
        )
        resp.raise_for_status()
        elements = resp.json().get("elements", [])

        if elements:
            ok(f"OSM Overpass reachable — {len(elements)} sample elements returned (London only)")
            for e in elements[:3]:
                name = e.get("tags", {}).get("name", "unnamed")
                religion = e.get("tags", {}).get("religion", "unknown")
                print(f"      → {name}  (religion: {religion})")
            return True
        else:
            warn("OSM reachable but no results in London sample — this is OK, try a wider area")
            return True  # Still counts as a pass — API works

    except requests.exceptions.Timeout:
        fail("OSM Overpass timed out — the server may be under load. Try again in a minute.")
        return False
    except Exception as e:
        fail(f"OSM failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: Historic England NHLE
# ─────────────────────────────────────────────────────────────────────────────

def test_historic_england():
    header("Test 3: Historic England NHLE API")

    try:
        # Try the open data download endpoint first
        resp = requests.get(
            "https://historicengland.org.uk/listing/the-list/list-entry/search-results/",
            params={
                "searchQuery": "church",
                "listentry": "LB",
                "pageSize": 5,
                "page": 1,
            },
            headers={
                "User-Agent": "UKChurchConversionTest/1.0",
                "Accept": "application/json",
            },
            timeout=20,
        )

        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            total = data.get("totalResults", 0)
            ok(f"Historic England reachable — {total:,} total listed church buildings")
            for r in results[:3]:
                name = r.get("name") or r.get("title", "unknown")
                grade = r.get("grade", "?")
                print(f"      → {name}  (Grade {grade})")
            return True

        elif resp.status_code == 404:
            warn("Historic England search endpoint returned 404 — API structure may have changed")
            warn("Check: https://historicengland.org.uk/listing/the-list/data-downloads/")
            return False

        else:
            warn(f"Historic England returned status {resp.status_code}")
            print(f"      Response: {resp.text[:200]}")
            return False

    except Exception as e:
        fail(f"Historic England failed: {e}")
        print(f"      This source may require manual data download from:")
        print(f"      https://historicengland.org.uk/listing/the-list/data-downloads/")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: Charity Commission
# ─────────────────────────────────────────────────────────────────────────────

def test_charity_commission():
    header("Test 4: Charity Commission API")

    import os
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.getenv("CHARITY_COMMISSION_API_KEY", "")

    if not api_key:
        warn("No CHARITY_COMMISSION_API_KEY in .env — testing without key (may get 401)")
        warn("Register free at: https://register-of-charities.charitycommission.gov.uk/api")

    headers = {
        "User-Agent": "UKChurchConversionTest/1.0",
        "Accept": "application/json",
    }
    if api_key:
        headers["Ocp-Apim-Subscription-Key"] = api_key

    try:
        resp = requests.get(
            "https://api.charitycommission.gov.uk/register/api/charities",
            params={
                "charity_name": "church",
                "registration_status": "RM",
                "page_number": 1,
                "page_size": 5,
            },
            headers=headers,
            timeout=20,
        )

        if resp.status_code == 200:
            data = resp.json()
            charities = data.get("charities", []) or data.get("data", [])
            total = data.get("total_results", data.get("totalResults", "unknown"))
            ok(f"Charity Commission reachable — {total} total deregistered church charities")
            for c in charities[:3]:
                name = c.get("charity_name", "unknown")
                num  = c.get("charity_number", "?")
                print(f"      → {name}  (#{num})")
            return True

        elif resp.status_code == 401:
            warn("Charity Commission: 401 Unauthorized")
            warn("Add your API key to .env as CHARITY_COMMISSION_API_KEY")
            warn("Register free: https://register-of-charities.charitycommission.gov.uk/api")
            return False

        else:
            warn(f"Charity Commission returned {resp.status_code}")
            return False

    except Exception as e:
        fail(f"Charity Commission failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: Python environment check
# ─────────────────────────────────────────────────────────────────────────────

def test_environment():
    header("Test 0: Python Environment")

    packages = {
        "pandas":       "Data processing",
        "requests":     "HTTP calls",
        "geopy":        "Geocoding",
        "tenacity":     "Retry logic",
        "rich":         "Terminal output",
        "typer":        "CLI framework",
        "openpyxl":     "Excel output",
        "sqlalchemy":   "PostgreSQL",
        "fuzzywuzzy":   "Fuzzy deduplication",
        "dotenv":       "Environment variables",
    }

    all_ok = True
    for pkg, purpose in packages.items():
        try:
            __import__(pkg)
            ok(f"{pkg:<15} {purpose}")
        except ImportError:
            fail(f"{pkg:<15} MISSING — run: pip install -r requirements.txt")
            all_ok = False

    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Test UK Church Conversion Pipeline extractors")
    parser.add_argument(
        "--source",
        choices=["env", "wikidata", "osm", "historic_england", "charity_commission", "all"],
        default="all",
        help="Which test to run (default: all)",
    )
    args = parser.parse_args()

    print("\n" + "━"*60)
    print("  UK Church Conversion Pipeline — Extractor Tests")
    print("━"*60 + "\n")

    results = {}

    if args.source in ("env", "all"):
        results["environment"] = test_environment()
        time.sleep(0.5)

    if args.source in ("wikidata", "all"):
        results["wikidata"] = test_wikidata()
        time.sleep(1)

    if args.source in ("osm", "all"):
        results["osm"] = test_osm()
        time.sleep(1)

    if args.source in ("historic_england", "all"):
        results["historic_england"] = test_historic_england()
        time.sleep(0.5)

    if args.source in ("charity_commission", "all"):
        results["charity_commission"] = test_charity_commission()

    # Summary
    print("\n" + "━"*60)
    print("  SUMMARY")
    print("━"*60)
    passed = sum(1 for v in results.values() if v)
    total  = len(results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}  {name}")

    print(f"\n  {passed}/{total} tests passed")

    if passed == total:
        print("\n  All good. Run the pipeline:")
        print("  python main.py --sources wikidata --skip-geocode --dry-run\n")
    elif results.get("environment") and results.get("wikidata"):
        print("\n  Core sources working. You can start with:")
        print("  python main.py --sources wikidata osm --skip-geocode\n")
    else:
        print("\n  Fix the failing tests above before running the pipeline.\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
