"""
accept_ml_predictions.py

Reviews and accepts ML predictions from ml_classify_unknowns.py.
Only promotes ensemble_predicted_type → conversion_type where
confidence meets the threshold.

Usage:
  python accept_ml_predictions.py --min-confidence 0.85  (conservative)
  python accept_ml_predictions.py --min-confidence 0.70  (liberal)
  python accept_ml_predictions.py --dry-run              (preview only)
"""

import argparse
import glob
import logging
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def find_latest_csv():
    candidates = sorted(glob.glob("data/output/uk_church_conversions_2*.csv"), reverse=True)
    for c in candidates:
        if "PUBLIC" not in c and "enriched" not in c:
            return Path(c)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-confidence", type=float, default=0.85)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    path = find_latest_csv()
    df = pd.read_csv(path, low_memory=False)

    if "ensemble_predicted_type" not in df.columns:
        print("No ML predictions found. Run ml_classify_unknowns.py first.")
        return

    df["ensemble_confidence"] = pd.to_numeric(df["ensemble_confidence"], errors="coerce")

    # Only accept for records that are still unknown
    candidates = df[
        (df["conversion_type"] == "unknown") &
        df["ensemble_predicted_type"].notna() &
        (df["ensemble_confidence"] >= args.min_confidence)
    ]

    print(f"\nML predictions meeting confidence ≥ {args.min_confidence}:")
    print(f"  Eligible records: {len(candidates):,}")
    print(f"\nBreakdown by predicted type:")
    print(candidates["ensemble_predicted_type"].value_counts().to_string())

    if args.dry_run:
        print("\nDry run — no changes made.")
        return

    # Apply
    accepted = 0
    for idx, row in candidates.iterrows():
        df.at[idx, "conversion_type"] = row["ensemble_predicted_type"]
        df.at[idx, "conversion_subtype"] = "ml_predicted"
        df.at[idx, "confidence_score"] = round(float(row["ensemble_confidence"]) * 0.9, 3)
        accepted += 1

    df.to_csv(path, index=False)

    print(f"\nAccepted {accepted:,} ML predictions")
    print(f"Unknown remaining: {(df['conversion_type']=='unknown').sum():,}")
    print(f"Conversion type breakdown:")
    print(df["conversion_type"].value_counts().head(12).to_string())


if __name__ == "__main__":
    main()