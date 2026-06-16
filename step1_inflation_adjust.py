"""
step1_inflation_adjust.py

Adds inflation-adjusted sale prices to the dataset.
Uses Nationwide HPI multipliers to convert all sale prices to 2024 equivalent.
Also flags unreliable price records (peppercorn transfers, 1995 batch entries).

Run: python step1_inflation_adjust.py
"""

import glob
import logging
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# UK House Price Index multipliers — year → multiply to get 2024 equivalent
# Source: Nationwide HPI / ONS, base year 2024
HPI_MULTIPLIERS = {
    1995: 6.5,  1996: 6.1,  1997: 5.8,  1998: 5.3,  1999: 4.9,
    2000: 5.0,  2001: 4.6,  2002: 3.9,  2003: 3.3,  2004: 2.9,
    2005: 2.8,  2006: 2.6,  2007: 2.4,  2008: 2.4,  2009: 2.5,
    2010: 2.2,  2011: 2.1,  2012: 2.1,  2013: 2.0,  2014: 1.9,
    2015: 1.7,  2016: 1.6,  2017: 1.5,  2018: 1.45, 2019: 1.4,
    2020: 1.3,  2021: 1.2,  2022: 1.1,  2023: 1.05, 2024: 1.0,
    2025: 1.0,  2026: 1.0,
}

def find_latest_csv():
    candidates = sorted(glob.glob("data/output/uk_church_conversions_2*.csv"), reverse=True)
    for c in candidates:
        if "PUBLIC" not in c and "enriched" not in c:
            return Path(c)
    return None

def main():
    path = find_latest_csv()
    if not path:
        logger.error("No pipeline CSV found.")
        return

    logger.info("Loading %s", path)
    df = pd.read_csv(path, low_memory=False)
    logger.info("Loaded %d records", len(df))

    df["sale_price"] = pd.to_numeric(df["sale_price"], errors="coerce")
    df["sale_date"]  = pd.to_datetime(df["sale_date"], errors="coerce")
    df["sale_year"]  = df["sale_date"].dt.year

    # Flag unreliable prices
    df["price_flag"] = ""
    df.loc[df["sale_price"] < 1000, "price_flag"] = "peppercorn_transfer"
    df.loc[
        (df["sale_date"].dt.strftime("%Y-%m-%d") == "1995-01-03") &
        (df["sale_price"] <= 10000),
        "price_flag"
    ] = "lr_batch_entry_unreliable"

    # Inflation adjustment
    def adjust(row):
        if pd.isna(row["sale_price"]) or pd.isna(row["sale_year"]):
            return None
        if row.get("price_flag") in ("peppercorn_transfer", "lr_batch_entry_unreliable"):
            return None
        multiplier = HPI_MULTIPLIERS.get(int(row["sale_year"]), 1.0)
        return round(row["sale_price"] * multiplier)

    df["sale_price_2024"] = df.apply(adjust, axis=1)

    clean = df[df["price_flag"] == ""]
    matched = df["sale_price_2024"].notna().sum()

    print("\n=== INFLATION ADJUSTMENT COMPLETE ===")
    print(f"Records with adjusted price:    {matched:,}")
    print(f"Peppercorn transfers flagged:   {(df['price_flag']=='peppercorn_transfer').sum():,}")
    print(f"LR batch entries flagged:       {(df['price_flag']=='lr_batch_entry_unreliable').sum():,}")
    print(f"\nNominal median:       £{clean['sale_price'].dropna().median():,.0f}")
    print(f"2024-adjusted median: £{clean['sale_price_2024'].dropna().median():,.0f}")
    print(f"Nominal average:      £{clean['sale_price'].dropna().mean():,.0f}")
    print(f"2024-adjusted avg:    £{clean['sale_price_2024'].dropna().mean():,.0f}")

    print("\nBy conversion type — 2024 adjusted median (min 5 records):")
    summary = clean.groupby("conversion_type")["sale_price_2024"].agg(["median","mean","count"])
    summary.columns = ["median_2024","avg_2024","count"]
    summary = summary[summary["count"] >= 5].sort_values("median_2024", ascending=False)
    for idx, row in summary.iterrows():
        med = f"£{row['median_2024']:,.0f}" if pd.notna(row["median_2024"]) else "-"
        avg = f"£{row['avg_2024']:,.0f}" if pd.notna(row["avg_2024"]) else "-"
        print(f"  {idx:<30} n:{int(row['count']):>6}  median:{med:>14}  avg:{avg:>14}")

    df.to_csv(path, index=False)
    logger.info("Saved with sale_price_2024 and price_flag columns: %s", path)

if __name__ == "__main__":
    main()