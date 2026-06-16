"""
extractors/land_registry_extractor.py

HM Land Registry Price Paid Data extractor.

Two functions:
  A) Enrich existing records with sale price, sale date, and buyer name
     by querying the Land Registry API by postcode/address
  B) Build use_history chains by finding multiple transactions at same address

API: https://landregistry.data.gov.uk/
No API key required. Free and open.

Data available:
  - Price paid
  - Transfer date (exact)
  - Property address + postcode
  - Property type (D=detached, S=semi, T=terraced, F=flat, O=other)
  - New build flag
  - Tenure (freehold/leasehold)
  - Buyer/seller names (in SPARQL endpoint)

Coverage: England and Wales only. Scotland uses Registers of Scotland.
Northern Ireland uses Land & Property Services NI.

Usage:
    python extractors/land_registry_extractor.py
    python enrich_land_registry.py --max-records 1000
"""

import logging
import time
import re
from pathlib import Path
from typing import Optional
import requests
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

LR_SPARQL = "https://landregistry.data.gov.uk/landregistry/query"
LR_API    = "https://landregistry.data.gov.uk/data/ppi"

HEADERS = {
    "User-Agent": "UKChurchConversionResearch/1.0 (academic project)",
    "Accept": "application/sparql-results+json",
}

# Property types that indicate former church conversion
# O = Other (most churches will be this)
RELEVANT_TYPES = {"O", "D", "S"}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=30))
def query_by_postcode(postcode: str) -> list[dict]:
    """
    Query Land Registry for all transactions at a postcode.
    Returns list of transactions sorted by date descending.
    """
    postcode_clean = postcode.strip().upper().replace(" ", "%20")
    query = f"""
    PREFIX lrppi: <http://landregistry.data.gov.uk/def/ppi/>
    PREFIX lrcommon: <http://landregistry.data.gov.uk/def/common/>

    SELECT ?date ?price ?paon ?saon ?street ?town ?postcode ?proptype ?tenure
    WHERE {{
      ?transx lrppi:pricePaid ?price ;
              lrppi:transactionDate ?date ;
              lrppi:propertyAddress ?addr .
      ?addr lrcommon:postcode "{postcode.strip().upper()}" ;
            lrcommon:town ?town .
      OPTIONAL {{ ?addr lrcommon:paon ?paon }}
      OPTIONAL {{ ?addr lrcommon:saon ?saon }}
      OPTIONAL {{ ?addr lrcommon:street ?street }}
      OPTIONAL {{ ?transx lrppi:propertyType/rdfs:label ?proptype }}
      OPTIONAL {{ ?transx lrppi:tenure/rdfs:label ?tenure }}
    }}
    ORDER BY DESC(?date)
    LIMIT 20
    """
    resp = requests.get(
        LR_SPARQL,
        params={"query": query},
        headers=HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    results = []
    for row in data.get("results", {}).get("bindings", []):
        results.append({
            "date":     row.get("date", {}).get("value", ""),
            "price":    row.get("price", {}).get("value", ""),
            "address":  " ".join(filter(None, [
                row.get("saon", {}).get("value", ""),
                row.get("paon", {}).get("value", ""),
                row.get("street", {}).get("value", ""),
            ])),
            "town":     row.get("town", {}).get("value", ""),
            "postcode": row.get("postcode", {}).get("value", postcode),
            "proptype": row.get("proptype", {}).get("value", ""),
            "tenure":   row.get("tenure", {}).get("value", ""),
        })
    return results


def extract_postcode_from_record(row: pd.Series) -> Optional[str]:
    """Extract postcode from address, notes, or source_url fields."""
    for field in ["address", "notes", "source_url"]:
        text = str(row.get(field, "") or "")
        match = re.search(
            r'\b([A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2})\b',
            text.upper()
        )
        if match:
            return match.group(1).strip()
    return None


def build_use_history(transactions: list[dict], current_type: str) -> list[dict]:
    """
    From a list of Land Registry transactions (sorted newest first),
    infer a use_history chain.

    Returns list of {use, year, price, notes} dicts.
    """
    history = []
    for tx in transactions:
        year = None
        if tx.get("date"):
            try:
                year = int(tx["date"][:4])
            except (ValueError, TypeError):
                pass
        price = None
        if tx.get("price"):
            try:
                price = int(float(tx["price"]))
            except (ValueError, TypeError):
                pass
        history.append({
            "year":    year,
            "price":   price,
            "address": tx.get("address", ""),
            "tenure":  tx.get("tenure", ""),
            "proptype":tx.get("proptype", ""),
        })
    return history


import json
import glob

CHECKPOINT_PATH = Path("data/output/land_registry_checkpoint.json")


def load_checkpoint() -> set:
    if not CHECKPOINT_PATH.exists():
        return set()
    try:
        with open(CHECKPOINT_PATH) as f:
            return set(json.load(f).get("processed_ids", []))
    except Exception:
        return set()


def save_checkpoint(processed: set, stats: dict):
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_PATH, "w") as f:
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


def enrich(
    input_path: Optional[str] = None,
    max_records: int = 1000,
    batch_size: int = 100,
    dry_run: bool = False,
):
    """
    Enrich pipeline output with Land Registry data.
    Adds: sale_price, sale_date, use_history (JSON chain of transactions).
    """
    import argparse

    path = Path(input_path) if input_path else find_latest_csv()
    if not path or not path.exists():
        logger.error("No pipeline CSV found.")
        return

    logger.info("Loading %s", path)
    df = pd.read_csv(path, low_memory=False)

    # Add columns if missing
    for col in ["sale_price", "sale_date", "buyer_name", "use_history"]:
        if col not in df.columns:
            df[col] = None

    for col in ["sale_price", "sale_date", "buyer_name", "use_history",
                "conversion_type", "notes"]:
        df[col] = df[col].astype(object)

    logger.info("Loaded %d records", len(df))

    processed = load_checkpoint()

    # Target: England/Wales records with postcodes we can look up
    england_wales = df[
        df["nation"].isin(["England", "Wales"]) |
        df["nation"].isna()
    ].copy()

    remaining = england_wales[
        ~england_wales["id"].astype(str).isin(processed)
    ]
    logger.info(
        "%d England/Wales records | %d already processed | %d remaining",
        len(england_wales), len(processed), len(remaining)
    )

    targets = remaining.head(max_records)
    stats = {
        "price_added": 0, "date_added": 0,
        "history_built": 0, "no_postcode": 0,
        "errors": 0, "queried": 0
    }
    batch_count = 0

    for idx, row in targets.iterrows():
        record_id = str(row.get("id", idx))
        postcode = extract_postcode_from_record(row)

        if not postcode:
            stats["no_postcode"] += 1
            processed.add(record_id)
            batch_count += 1
            continue

        try:
            transactions = query_by_postcode(postcode)
            stats["queried"] += 1
        except Exception as e:
            logger.debug("LR query failed for %s: %s", postcode, e)
            stats["errors"] += 1
            processed.add(record_id)
            time.sleep(1)
            batch_count += 1
            continue

        if not transactions:
            processed.add(record_id)
            batch_count += 1
            continue

        # Most recent transaction = likely conversion/sale
        latest = transactions[0]

        # Add sale price
        if latest.get("price") and pd.isna(df.at[idx, "sale_price"]):
            try:
                df.at[idx, "sale_price"] = int(float(latest["price"]))
                stats["price_added"] += 1
            except (ValueError, TypeError):
                pass

        # Add sale date (more reliable than planning portal decision date)
        if latest.get("date") and pd.isna(df.at[idx, "sale_date"]):
            df.at[idx, "sale_date"] = latest["date"][:10]
            stats["date_added"] += 1
            # Also fill year_converted if missing
            if pd.isna(df.at[idx, "year_converted"]):
                try:
                    df.at[idx, "year_converted"] = int(latest["date"][:4])
                    df.at[idx, "decade"] = f"{(int(latest['date'][:4])//10)*10}s"
                except (ValueError, TypeError):
                    pass

        # Build use_history if multiple transactions
        if len(transactions) > 1:
            history = build_use_history(
                transactions,
                str(row.get("conversion_type", "unknown"))
            )
            df.at[idx, "use_history"] = json.dumps(history)
            stats["history_built"] += 1

        processed.add(record_id)
        batch_count += 1

        if batch_count >= batch_size:
            if not dry_run:
                df.to_csv(path, index=False)
                save_checkpoint(processed, stats)
            logger.info(
                "[%d/%d] Batch saved | price: +%d | date: +%d | history: +%d | errors: %d",
                stats["queried"], len(targets),
                stats["price_added"], stats["date_added"],
                stats["history_built"], stats["errors"]
            )
            batch_count = 0

        time.sleep(0.3)  # Land Registry has no strict rate limit but be polite

    if batch_count > 0 and not dry_run:
        df.to_csv(path, index=False)
        save_checkpoint(processed, stats)

    print("\n=== LAND REGISTRY ENRICHMENT COMPLETE ===")
    print(f"Queried:          {stats['queried']:,}")
    print(f"Prices added:     {stats['price_added']:,}")
    print(f"Dates added:      {stats['date_added']:,}")
    print(f"Histories built:  {stats['history_built']:,}")
    print(f"No postcode:      {stats['no_postcode']:,}")
    print(f"Errors:           {stats['errors']:,}")
    if not dry_run:
        print(f"\nSaved: {path}")
        print("Run again to continue from checkpoint.")


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(
        description="Enrich with Land Registry sale data and use_history chains"
    )
    parser.add_argument("--input", help="Path to CSV")
    parser.add_argument("--max-records", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    if args.reset and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()
        print("Checkpoint cleared.")

    enrich(
        input_path=args.input,
        max_records=args.max_records,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )