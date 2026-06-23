"""
step2_imd_join.py

Joins the Index of Multiple Deprivation (IMD) to the dataset by LSOA code.
Adds deprivation decile (1=most deprived, 10=least deprived) and domain scores.

Downloads the IMD data automatically from ONS if not present.

Run: python step2_imd_join.py

Data source:
  England IMD 2019: https://opendatacommunities.org/resource?uri=http%3A%2F%2Fopendatacommunities.org%2Fdata%2Fsocietal-wellbeing%2Fdeprivation%2Findices-english-imd-2019-lsoa
  Free, Open Government Licence
"""

import glob
import logging
import requests
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Direct download URL for England IMD 2019 by LSOA
IMD_URL = "https://assets.publishing.service.gov.uk/media/5dfb3d93e5274a33703bc88b/File_7_-_All_IoD2019_Scores__Ranks__Deciles_and_Population_Denominators_3.csv"
IMD_PATH = Path("data/raw/imd_2019_lsoa.csv")


def download_imd():
    logger.info("Downloading IMD 2019 data from GOV.UK...")
    IMD_PATH.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(IMD_URL, timeout=60, stream=True)
    resp.raise_for_status()
    with open(IMD_PATH, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    logger.info("IMD downloaded: %s (%.1f MB)", IMD_PATH, IMD_PATH.stat().st_size / 1e6)


def find_latest_csv():
    candidates = sorted(glob.glob("data/output/uk_church_conversions_2*.csv"), reverse=True)
    for c in candidates:
        if "PUBLIC" not in c and "enriched" not in c and "_pre_" not in c and "_backup" not in c:
            return Path(c)
    return None


def main():
    # Download IMD if not present
    if not IMD_PATH.exists():
        try:
            download_imd()
        except Exception as e:
            logger.error("Could not download IMD: %s", e)
            logger.info(
                "Manual download:\n"
                "https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019\n"
                "Save as: data/raw/imd_2019_lsoa.csv"
            )
            return

    logger.info("Loading IMD data...")
    imd = pd.read_csv(IMD_PATH)
    logger.info("IMD columns: %s", imd.columns.tolist()[:10])

    # Standardise IMD columns — the file has long descriptive headers
    # Find the LSOA code column and IMD decile column
    lsoa_col = next((c for c in imd.columns if "lsoa" in c.lower() and "code" in c.lower()), None)
    decile_col = next((c for c in imd.columns if "decile" in c.lower() and "imd" in c.lower()), None)
    rank_col = next((c for c in imd.columns if "rank" in c.lower() and "imd" in c.lower()), None)
    score_col = next((c for c in imd.columns if "score" in c.lower() and "imd" in c.lower()), None)

    # Fallback: use positional columns if headers don't match
    if not lsoa_col:
        lsoa_col = imd.columns[0]
    if not decile_col:
        # Column 38 is typically the IMD decile in the standard ONS file
        decile_col = imd.columns[min(38, len(imd.columns)-1)]

    logger.info("Using LSOA col: %s | Decile col: %s", lsoa_col, decile_col)

    imd_slim = imd[[lsoa_col, decile_col]].copy()
    if rank_col:
        imd_slim[rank_col] = imd[rank_col]
    imd_slim.columns = (
        ["lsoa_code", "imd_decile", "imd_rank"]
        if rank_col else
        ["lsoa_code", "imd_decile"]
    )
    imd_slim["lsoa_code"] = imd_slim["lsoa_code"].str.strip()

    logger.info("IMD: %d LSOA records", len(imd_slim))

    # Load church dataset
    path = find_latest_csv()
    if not path:
        logger.error("No pipeline CSV found.")
        return

    df = pd.read_csv(path, low_memory=False)
    logger.info("Church dataset: %d records", len(df))

    # Drop existing IMD columns if present
    for col in ["imd_decile", "imd_rank", "imd_score"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    # Join
    # Convert LSOA names to codes using Census 2021 lookup
    from pathlib import Path
    lsoa_lookup_path = Path("data/raw/lsoa_name_to_code.csv")
    if lsoa_lookup_path.exists():
        lsoa_lookup = pd.read_csv(lsoa_lookup_path)
        df = df.merge(lsoa_lookup, left_on="lsoa", right_on="lsoa_name", how="left")
        df["lsoa_clean"] = df["lsoa_code"].fillna(df["lsoa"]).str.strip()
        df = df.drop(columns=["lsoa_name", "lsoa_code"], errors="ignore")
    else:
        df["lsoa_clean"] = df["lsoa"].str.strip()
    df = df.merge(imd_slim, left_on="lsoa_clean", right_on="lsoa_code", how="left")
    df = df.drop(columns=["lsoa_clean", "lsoa_code"], errors="ignore")

    matched = df["imd_decile"].notna().sum()
    logger.info("Matched %d records with IMD data", matched)

    print("\n=== IMD JOIN COMPLETE ===")
    print(f"Records with IMD decile: {matched:,} / {len(df):,}")
    print(f"\nIMD decile distribution (1=most deprived, 10=least deprived):")
    print(df["imd_decile"].value_counts().sort_index().to_string())

    print("\nConversion type by deprivation — median IMD decile:")
    print("(Lower = more deprived area)")
    by_type = df.groupby("conversion_type")["imd_decile"].agg(["median","mean","count"])
    by_type.columns = ["median_decile","mean_decile","count"]
    by_type = by_type[by_type["count"] >= 5].sort_values("median_decile")
    for idx, row in by_type.iterrows():
        bar = "█" * int(row["median_decile"])
        print(f"  {idx:<30} {bar:<12} {row['median_decile']:.1f}  (n={int(row['count'])})")

    print("\nKey finding — mosque vs residential deprivation:")
    mosque_med = df[df["conversion_type"]=="mosque"]["imd_decile"].median()
    resi_med = df[df["conversion_type"]=="residential"]["imd_decile"].median()
    print(f"  Mosque conversions median IMD decile:      {mosque_med:.1f}")
    print(f"  Residential conversions median IMD decile: {resi_med:.1f}")
    if mosque_med and resi_med:
        if mosque_med < resi_med:
            print(f"  → Mosque conversions occur in MORE deprived areas than residential")
        else:
            print(f"  → Mosque conversions occur in LESS deprived areas than residential")

    df.to_csv(path, index=False)
    logger.info("Saved with IMD decile: %s", path)


if __name__ == "__main__":
    main()
    