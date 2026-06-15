"""
transforms/loader.py

Writes the clean master DataFrame to:
  1. CSV (for public release on GitHub / Kaggle / data.world)
  2. PostgreSQL (for the web app / Sacred Spaces backend)
  3. Excel with pivot summary sheets (for non-technical stakeholders)
"""

import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

OUTPUT_DIR = Path("data/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d")


# ─── CSV OUTPUT ──────────────────────────────────────────────────────────────

def write_csv(df: pd.DataFrame, filename: Optional[str] = None) -> Path:
    """
    Write master dataset to CSV.
    Produces two files:
      - Full dataset (all records, all columns)
      - Public release (drops internal fields like confidence_score internals)
    """
    if filename is None:
        filename = f"uk_church_conversions_{TIMESTAMP}.csv"

    full_path = OUTPUT_DIR / filename
    df.to_csv(full_path, index=False, encoding="utf-8")
    logger.info("CSV written: %s (%d records)", full_path, len(df))

    # Public release — drop source_url (may contain internal IDs) and keep clean
    public_cols = [
        "id", "church_name", "former_denomination", "city",
        "local_authority", "region", "nation", "latitude", "longitude",
        "conversion_type", "conversion_subtype", "current_name",
        "year_converted", "decade", "source", "confidence_tier",
    ]
    public_path = OUTPUT_DIR / f"uk_church_conversions_PUBLIC_{TIMESTAMP}.csv"
    public_df = df[[c for c in public_cols if c in df.columns]]
    public_df.to_csv(public_path, index=False, encoding="utf-8")
    logger.info("Public CSV written: %s", public_path)

    return full_path


# ─── POSTGRESQL OUTPUT ───────────────────────────────────────────────────────

def get_db_engine():
    """
    Create SQLAlchemy engine from DATABASE_URL in .env
    Expected format: postgresql://user:password@localhost:5432/church_conversions
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.warning(
            "DATABASE_URL not set in .env — skipping PostgreSQL write. "
            "Set it as: postgresql://user:password@host:port/dbname"
        )
        return None
    return create_engine(db_url)


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS church_conversions (
    id                  VARCHAR(12) PRIMARY KEY,
    church_name         TEXT,
    former_denomination TEXT,
    address             TEXT,
    city                TEXT,
    local_authority     TEXT,
    region              TEXT,
    nation              VARCHAR(20),
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    conversion_type     VARCHAR(30),
    conversion_subtype  VARCHAR(50),
    current_name        TEXT,
    year_converted      INTEGER,
    decade              VARCHAR(10),
    source              VARCHAR(50),
    source_url          TEXT,
    confidence_score    FLOAT,
    confidence_tier     VARCHAR(10),
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_conv_type    ON church_conversions(conversion_type);
CREATE INDEX IF NOT EXISTS idx_region       ON church_conversions(region);
CREATE INDEX IF NOT EXISTS idx_nation       ON church_conversions(nation);
CREATE INDEX IF NOT EXISTS idx_decade       ON church_conversions(decade);
CREATE INDEX IF NOT EXISTS idx_latlon       ON church_conversions(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_source       ON church_conversions(source);

-- Spatial index (if PostGIS available)
-- CREATE INDEX IF NOT EXISTS idx_geom ON church_conversions
--   USING GIST(ST_Point(longitude, latitude));
"""

UPSERT_SQL = """
INSERT INTO church_conversions (
    id, church_name, former_denomination, address, city,
    local_authority, region, nation, latitude, longitude,
    conversion_type, conversion_subtype, current_name,
    year_converted, decade, source, source_url,
    confidence_score, confidence_tier, notes, updated_at
) VALUES (
    :id, :church_name, :former_denomination, :address, :city,
    :local_authority, :region, :nation, :latitude, :longitude,
    :conversion_type, :conversion_subtype, :current_name,
    :year_converted, :decade, :source, :source_url,
    :confidence_score, :confidence_tier, :notes, NOW()
)
ON CONFLICT (id) DO UPDATE SET
    church_name         = EXCLUDED.church_name,
    current_name        = EXCLUDED.current_name,
    conversion_type     = EXCLUDED.conversion_type,
    conversion_subtype  = EXCLUDED.conversion_subtype,
    latitude            = EXCLUDED.latitude,
    longitude           = EXCLUDED.longitude,
    region              = EXCLUDED.region,
    nation              = EXCLUDED.nation,
    confidence_score    = EXCLUDED.confidence_score,
    confidence_tier     = EXCLUDED.confidence_tier,
    notes               = EXCLUDED.notes,
    updated_at          = NOW();
"""


def write_postgres(df: pd.DataFrame) -> bool:
    """
    Upsert records into PostgreSQL.
    Uses ON CONFLICT DO UPDATE so re-runs are safe (idempotent).
    """
    engine = get_db_engine()
    if engine is None:
        return False

    try:
        with engine.connect() as conn:
            # Create table if needed
            conn.execute(text(CREATE_TABLE_SQL))
            conn.commit()
            logger.info("PostgreSQL: table ready")

            # Batch upsert
            batch_size = 500
            records = df.where(pd.notna(df), None).to_dict("records")
            total_written = 0

            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                conn.execute(text(UPSERT_SQL), batch)
                conn.commit()
                total_written += len(batch)
                logger.info("PostgreSQL: upserted %d/%d records", total_written, len(records))

        logger.info("PostgreSQL write complete: %d records", total_written)
        return True

    except Exception as e:
        logger.error("PostgreSQL write failed: %s", e)
        return False


# ─── EXCEL PIVOT SUMMARY ─────────────────────────────────────────────────────

def write_excel_summary(df: pd.DataFrame, filename: Optional[str] = None) -> Path:
    """
    Write an Excel workbook with multiple analysis sheets:
      1. Master data (full table)
      2. By Conversion Type (pivot)
      3. By Region (pivot)
      4. By Decade (pivot)
      5. By Nation (summary)
      6. Top Cities
    """
    if filename is None:
        filename = f"uk_church_conversions_summary_{TIMESTAMP}.xlsx"
    path = OUTPUT_DIR / filename

    with pd.ExcelWriter(path, engine="openpyxl") as writer:

        # Sheet 1: Master data
        df.drop(columns=["notes", "source_url"], errors="ignore").to_excel(
            writer, sheet_name="All Records", index=False
        )
        logger.info("Excel: 'All Records' sheet written")

        # Sheet 2: Conversion type summary
        type_summary = (
            df.groupby("conversion_type")
            .agg(
                count=("id", "count"),
                with_coords=("latitude", lambda x: x.notna().sum()),
                with_year=("year_converted", lambda x: x.notna().sum()),
                avg_year=("year_converted", "mean"),
                high_confidence=("confidence_tier", lambda x: (x == "high").sum()),
            )
            .reset_index()
            .sort_values("count", ascending=False)
        )
        type_summary["pct_of_total"] = (
            100 * type_summary["count"] / type_summary["count"].sum()
        ).round(1)
        type_summary.to_excel(writer, sheet_name="By Conversion Type", index=False)
        logger.info("Excel: 'By Conversion Type' sheet written")

        # Sheet 3: By Region × Conversion Type pivot
        if "region" in df.columns and df["region"].notna().any():
            region_pivot = pd.pivot_table(
                df,
                values="id",
                index="region",
                columns="conversion_type",
                aggfunc="count",
                fill_value=0,
            )
            region_pivot["TOTAL"] = region_pivot.sum(axis=1)
            region_pivot = region_pivot.sort_values("TOTAL", ascending=False)
            region_pivot.to_excel(writer, sheet_name="By Region")
            logger.info("Excel: 'By Region' sheet written")

        # Sheet 4: By Decade × Conversion Type pivot
        if "decade" in df.columns and df["decade"].notna().any():
            decade_pivot = pd.pivot_table(
                df[df["decade"].notna()],
                values="id",
                index="decade",
                columns="conversion_type",
                aggfunc="count",
                fill_value=0,
            )
            decade_pivot["TOTAL"] = decade_pivot.sum(axis=1)
            decade_pivot = decade_pivot.sort_index()
            decade_pivot.to_excel(writer, sheet_name="By Decade")
            logger.info("Excel: 'By Decade' sheet written")

        # Sheet 5: By Nation
        nation_summary = (
            df.groupby("nation")
            .agg(
                total=("id", "count"),
                mosque=("conversion_type", lambda x: (x == "mosque").sum()),
                other_faith=("conversion_type", lambda x: (x == "other_faith").sum()),
                residential=("conversion_type", lambda x: (x == "residential").sum()),
                hospitality=("conversion_type", lambda x: (x == "hospitality").sum()),
                arts_culture=("conversion_type", lambda x: (x == "arts_culture").sum()),
                commercial=("conversion_type", lambda x: (x == "commercial").sum()),
                unknown=("conversion_type", lambda x: (x == "unknown").sum()),
            )
            .reset_index()
            .sort_values("total", ascending=False)
        )
        nation_summary.to_excel(writer, sheet_name="By Nation", index=False)
        logger.info("Excel: 'By Nation' sheet written")

        # Sheet 6: Top Cities
        top_cities = (
            df.groupby(["city", "nation"])
            .agg(total=("id", "count"))
            .reset_index()
            .sort_values("total", ascending=False)
            .head(50)
        )
        top_cities.to_excel(writer, sheet_name="Top 50 Cities", index=False)
        logger.info("Excel: 'Top 50 Cities' sheet written")

        # Sheet 7: Source quality report
        source_quality = (
            df.groupby("source")
            .agg(
                records=("id", "count"),
                with_coords=("latitude", lambda x: x.notna().sum()),
                with_year=("year_converted", lambda x: x.notna().sum()),
                avg_confidence=("confidence_score", "mean"),
            )
            .reset_index()
        )
        source_quality.to_excel(writer, sheet_name="Source Quality", index=False)
        logger.info("Excel: 'Source Quality' sheet written")

    logger.info("Excel workbook written: %s", path)
    return path


# ─── MAIN LOADER ─────────────────────────────────────────────────────────────

def load(df: pd.DataFrame) -> dict[str, Path]:
    """
    Write all outputs. Returns dict of output paths.
    """
    outputs = {}

    # CSV
    csv_path = write_csv(df)
    outputs["csv"] = csv_path

    # PostgreSQL (optional, skips gracefully if DATABASE_URL not set)
    success = write_postgres(df)
    outputs["postgres"] = "written" if success else "skipped (no DATABASE_URL)"

    # Excel summary
    excel_path = write_excel_summary(df)
    outputs["excel"] = excel_path

    return outputs
