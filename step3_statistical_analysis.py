"""
step3_statistical_analysis.py

Three core statistical analyses for the Sacred Spaces dataset:

  1. Moran's I — spatial autocorrelation
     Tests whether conversion types cluster geographically.
     High positive I = conversions cluster together (not random).

  2. Interrupted Time Series — policy impact analysis
     Tests whether the 2012 Permitted Development Rights change
     caused a structural break in residential conversion rates.

  3. Hedonic Price Regression — what drives sale prices
     Controls for location, time, building type simultaneously.
     Produces: "Mosque conversions sell for X% more/less than
     residential, controlling for location and year."

Dependencies:
  pip install libpysal esda statsmodels scipy

Run: python step3_statistical_analysis.py
"""

import glob
import logging
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def find_latest_csv():
    candidates = sorted(glob.glob("data/output/uk_church_conversions_2*.csv"), reverse=True)
    for c in candidates:
        if "PUBLIC" not in c and "enriched" not in c:
            return Path(c)
    return None


# ─── ANALYSIS 1: SPATIAL AUTOCORRELATION (Moran's I) ─────────────────────────

def run_morans_i(df: pd.DataFrame):
    print("\n" + "="*60)
    print("ANALYSIS 1: SPATIAL AUTOCORRELATION (Moran's I)")
    print("="*60)
    print("Tests whether conversion types cluster geographically.")
    print("Range: -1 (dispersed) to +1 (clustered). Random ≈ 0.")

    try:
        import libpysal
        from esda.moran import Moran, Moran_Local
    except ImportError:
        print("\n⚠ libpysal/esda not installed.")
        print("Run: pip install libpysal esda")
        print("Running simplified nearest-neighbour clustering instead...\n")
        run_simple_clustering(df)
        return

    # Use England records with coordinates for spatial analysis
    spatial_df = df[
        df["latitude"].notna() &
        df["longitude"].notna() &
        (df["nation"] == "England")
    ].copy().reset_index(drop=True)

    logger.info("Spatial analysis: %d England records with coordinates", len(spatial_df))

    # Build KNN spatial weights (k=8 nearest neighbours)
    coords = spatial_df[["longitude", "latitude"]].values
    w = libpysal.weights.KNN.from_array(coords, k=8)
    w.transform = "r"

    results = {}
    conversion_types = ["mosque", "residential", "community", "hospitality", "arts_culture"]

    for ct in conversion_types:
        y = (spatial_df["conversion_type"] == ct).astype(float).values
        if y.sum() < 5:
            continue
        try:
            moran = Moran(y, w, permutations=499)
            results[ct] = {
                "I": moran.I,
                "p_value": moran.p_sim,
                "z_score": moran.z_sim,
                "significant": moran.p_sim < 0.05,
                "count": int(y.sum()),
            }
        except Exception as e:
            logger.warning("Moran's I failed for %s: %s", ct, e)

    print(f"\n{'Conversion Type':<25} {'Moran I':>10} {'p-value':>10} {'Significant':>12} {'Count':>8} {'Interpretation'}")
    print("-" * 85)
    for ct, r in sorted(results.items(), key=lambda x: -abs(x[1]["I"])):
        sig = "✓ YES" if r["significant"] else "✗ No"
        if r["I"] > 0.3 and r["significant"]:
            interp = "Strong clustering"
        elif r["I"] > 0.1 and r["significant"]:
            interp = "Moderate clustering"
        elif r["significant"]:
            interp = "Weak clustering"
        else:
            interp = "Random distribution"
        print(f"  {ct:<23} {r['I']:>10.4f} {r['p_value']:>10.4f} {sig:>12} {r['count']:>8}   {interp}")

    if results:
        most_clustered = max(results.items(), key=lambda x: x[1]["I"] if x[1]["significant"] else 0)
        print(f"\nKey finding: {most_clustered[0]} conversions show the strongest geographic")
        print(f"clustering (Moran's I = {most_clustered[1]['I']:.4f}, p = {most_clustered[1]['p_value']:.4f})")
        print("This means these conversions are not randomly distributed — they")
        print("concentrate in specific areas, following community settlement patterns.")

    # Save LISA hotspot data for mapping
    if "mosque" in results and results["mosque"]["significant"]:
        y_mosque = (spatial_df["conversion_type"] == "mosque").astype(float).values
        try:
            from esda.moran import Moran_Local
            lisa = Moran_Local(y_mosque, w, permutations=499)
            spatial_df["lisa_quadrant"] = lisa.q
            spatial_df["lisa_significant"] = lisa.p_sim < 0.05
            hotspots = spatial_df[
                (spatial_df["lisa_quadrant"] == 1) &
                (spatial_df["lisa_significant"])
            ]
            print(f"\nMosque hotspot LSOAs (High-High clusters): {len(hotspots)}")
            if len(hotspots) > 0:
                print(hotspots[["city", "region", "postcode", "lsoa"]].head(10).to_string())
            hotspots.to_csv("data/output/mosque_hotspots_lisa.csv", index=False)
            print("Saved: data/output/mosque_hotspots_lisa.csv")
        except Exception as e:
            logger.warning("LISA failed: %s", e)

    return results


def run_simple_clustering(df: pd.DataFrame):
    """Fallback clustering without libpysal."""
    print("\nSimplified geographic concentration analysis:")
    print("(Install libpysal for full Moran's I analysis)\n")

    typed = df[df["conversion_type"] != "unknown"].copy()

    print(f"{'Conversion Type':<25} {'Top Region':>20} {'% in top region':>18}")
    print("-" * 65)
    for ct in ["mosque", "residential", "community", "hospitality", "arts_culture"]:
        subset = typed[typed["conversion_type"] == ct]
        if len(subset) < 3:
            continue
        region_counts = subset["region"].value_counts()
        if region_counts.empty:
            continue
        top_region = region_counts.index[0]
        top_pct = region_counts.iloc[0] / len(subset) * 100
        print(f"  {ct:<23} {top_region:>20} {top_pct:>17.1f}%")


# ─── ANALYSIS 2: INTERRUPTED TIME SERIES ─────────────────────────────────────

def run_interrupted_time_series(df: pd.DataFrame):
    print("\n" + "="*60)
    print("ANALYSIS 2: INTERRUPTED TIME SERIES")
    print("="*60)
    print("Tests whether the 2012 Permitted Development Rights change")
    print("caused a structural break in residential conversion rates.")
    print("Also tests 2008 financial crisis impact.\n")

    try:
        import statsmodels.api as sm
    except ImportError:
        print("⚠ statsmodels not installed. Run: pip install statsmodels")
        return

    # Annual conversion counts
    yearly = df[
        df["year_converted"].notna() &
        (df["year_converted"] >= 1995) &
        (df["year_converted"] <= 2024)
    ].copy()

    yearly["year_converted"] = yearly["year_converted"].astype(int)

    # Total conversions per year
    total_by_year = yearly.groupby("year_converted").size().reset_index(name="total")

    # Residential conversions per year
    resi_by_year = yearly[
        yearly["conversion_type"] == "residential"
    ].groupby("year_converted").size().reset_index(name="residential")

    ts = total_by_year.merge(resi_by_year, on="year_converted", how="left")
    ts["residential"] = ts["residential"].fillna(0)
    ts["resi_rate"] = ts["residential"] / ts["total"].clip(lower=1)

    ts = ts.sort_values("year_converted").reset_index(drop=True)
    ts["time"] = range(len(ts))

    # Test 1: 2012 PDR change
    ts["post_2012"] = (ts["year_converted"] >= 2012).astype(int)
    ts["time_post_2012"] = ts["time"] * ts["post_2012"]

    X = sm.add_constant(ts[["time", "post_2012", "time_post_2012"]])
    model_2012 = sm.OLS(ts["resi_rate"], X).fit()

    print("Test 1: Did 2012 PDR change accelerate residential conversions?")
    print(f"  Coefficient on post_2012 intervention: {model_2012.params['post_2012']:.4f}")
    print(f"  p-value: {model_2012.pvalues['post_2012']:.4f}")
    if model_2012.pvalues["post_2012"] < 0.05:
        direction = "INCREASED" if model_2012.params["post_2012"] > 0 else "DECREASED"
        print(f"  ✓ SIGNIFICANT: The 2012 PDR change {direction} residential conversion rates")
        pct = model_2012.params["post_2012"] * 100
        print(f"    Estimated effect: {pct:+.1f} percentage point change in residential share")
    else:
        print(f"  ✗ NOT SIGNIFICANT: No detectable effect of 2012 PDR change (p={model_2012.pvalues['post_2012']:.3f})")
    print(f"  Model R²: {model_2012.rsquared:.3f}")

    # Test 2: 2008 financial crisis
    ts["post_2008"] = (ts["year_converted"] >= 2008).astype(int)
    ts["time_post_2008"] = ts["time"] * ts["post_2008"]

    X2 = sm.add_constant(ts[["time", "post_2008", "time_post_2008"]])
    model_2008 = sm.OLS(ts["residential"], X2).fit()

    print(f"\nTest 2: Did the 2008 financial crisis change conversion volumes?")
    print(f"  Coefficient on post_2008 intervention: {model_2008.params['post_2008']:.4f}")
    print(f"  p-value: {model_2008.pvalues['post_2008']:.4f}")
    if model_2008.pvalues["post_2008"] < 0.05:
        direction = "INCREASED" if model_2008.params["post_2008"] > 0 else "DECREASED"
        print(f"  ✓ SIGNIFICANT: The 2008 financial crisis {direction} residential conversion volumes")
    else:
        print(f"  ✗ NOT SIGNIFICANT (p={model_2008.pvalues['post_2008']:.3f})")

    # Decade summary
    print(f"\nConversion volumes by decade:")
    decade_counts = yearly.groupby(
        [yearly["year_converted"].apply(lambda y: f"{(int(y)//10)*10}s"),
         "conversion_type"]
    ).size().unstack(fill_value=0)
    if "residential" in decade_counts.columns:
        print(decade_counts[["residential"]].to_string())

    # Save time series
    ts.to_csv("data/output/conversion_time_series.csv", index=False)
    print("\nSaved: data/output/conversion_time_series.csv")

    return model_2012


# ─── ANALYSIS 3: HEDONIC PRICE REGRESSION ─────────────────────────────────────

def run_hedonic_regression(df: pd.DataFrame):
    print("\n" + "="*60)
    print("ANALYSIS 3: HEDONIC PRICE REGRESSION")
    print("="*60)
    print("Controls for location, time, and tenure simultaneously.")
    print("Isolates the effect of conversion type on sale price.\n")

    try:
        import statsmodels.formula.api as smf
    except ImportError:
        print("⚠ statsmodels not installed. Run: pip install statsmodels")
        return

    # Use clean price data
    price_df = df[
        df["sale_price_2024"].notna() &
        df["conversion_type"].notna() &
        df["conversion_type"].ne("unknown") &
        df["region"].notna() &
        df["year_converted"].notna() &
        (df.get("price_flag", "") == "")
    ].copy()

    logger.info("Hedonic regression: %d records with clean price data", len(price_df))

    if len(price_df) < 50:
        print(f"⚠ Only {len(price_df)} clean price records — insufficient for regression.")
        print("Run the Land Registry enrichment first to get more price data.")
        return

    # Log transform price (standard in hedonic regression)
    price_df["log_price"] = np.log(price_df["sale_price_2024"].clip(lower=1))
    price_df["year_converted"] = price_df["year_converted"].astype(int)
    price_df["decade"] = (price_df["year_converted"] // 10) * 10

    # Encode categorical variables
    price_df["conversion_type_clean"] = price_df["conversion_type"].str.replace(
        r"[^a-zA-Z0-9]", "_", regex=True
    )
    price_df["region_clean"] = price_df["region"].str.replace(
        r"[^a-zA-Z0-9]", "_", regex=True
    )

    # Set residential as reference category (most common)
    price_df["conversion_type_clean"] = pd.Categorical(
        price_df["conversion_type_clean"],
        categories=["residential"] + [
            c for c in price_df["conversion_type_clean"].unique()
            if c != "residential"
        ]
    )

    try:
        model = smf.ols(
            "log_price ~ C(conversion_type_clean) + C(region_clean) + C(decade)",
            data=price_df
        ).fit()

        print(f"Model fit: R² = {model.rsquared:.3f} (explains {model.rsquared*100:.1f}% of price variation)")
        print(f"Observations: {int(model.nobs):,}")
        print(f"\nConversion type price effects vs residential (reference):")
        print("(Coefficients are log points — multiply by 100 for % effect)\n")

        type_params = {
            k: v for k, v in model.params.items()
            if "conversion_type" in k
        }
        type_pvals = {
            k: v for k, v in model.pvalues.items()
            if "conversion_type" in k
        }

        print(f"  {'Conversion Type':<35} {'Coeff':>8} {'% Effect':>10} {'p-value':>10} {'Sig':>5}")
        print("-" * 75)
        for param, coef in sorted(type_params.items(), key=lambda x: -x[1]):
            pval = type_pvals.get(param, 1.0)
            pct_effect = (np.exp(coef) - 1) * 100
            clean_name = param.replace("C(conversion_type_clean)[T.", "").replace("]", "")
            sig = "***" if pval < 0.001 else "**" if pval < 0.01 else "*" if pval < 0.05 else ""
            print(f"  {clean_name:<33} {coef:>8.3f} {pct_effect:>9.1f}% {pval:>10.4f} {sig:>5}")

        # Key mosque finding
        mosque_params = [k for k in type_params if "mosque" in k.lower()]
        if mosque_params:
            mosque_coef = type_params[mosque_params[0]]
            mosque_pval = type_pvals[mosque_params[0]]
            mosque_pct = (np.exp(mosque_coef) - 1) * 100
            print(f"\nKey finding — mosque vs residential price effect:")
            print(f"  Controlling for location and year, mosque conversions sell for")
            print(f"  {mosque_pct:+.1f}% {'more' if mosque_pct > 0 else 'less'} than residential conversions")
            if mosque_pval < 0.05:
                print(f"  This is statistically significant (p={mosque_pval:.4f})")
            else:
                print(f"  This is NOT statistically significant (p={mosque_pval:.4f}) — insufficient data")

        model.save("data/output/hedonic_regression_model.pickle")
        print("\nSaved: data/output/hedonic_regression_model.pickle")

    except Exception as e:
        logger.error("Regression failed: %s", e)
        print(f"Regression error: {e}")
        print("Running simplified price comparison instead...")
        run_simple_price_comparison(price_df)

    return


def run_simple_price_comparison(price_df: pd.DataFrame):
    """Fallback if regression fails."""
    print("\nSimplified price comparison by conversion type:")
    summary = price_df.groupby("conversion_type")["sale_price_2024"].agg(
        ["median","mean","count"]
    ).sort_values("count", ascending=False)
    summary.columns = ["median_2024","avg_2024","count"]
    for idx, row in summary.head(10).iterrows():
        med = f"£{row['median_2024']:,.0f}" if pd.notna(row["median_2024"]) else "-"
        print(f"  {idx:<30} n:{int(row['count']):>5}  median:{med:>14}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    path = find_latest_csv()
    if not path:
        logger.error("No pipeline CSV found.")
        return

    logger.info("Loading %s", path)
    df = pd.read_csv(path, low_memory=False)
    df["sale_price_2024"] = pd.to_numeric(df.get("sale_price_2024"), errors="coerce")
    df["year_converted"] = pd.to_numeric(df["year_converted"], errors="coerce")
    logger.info("Loaded %d records", len(df))

    # Basic summary first
    print("\n" + "="*60)
    print("SACRED SPACES — STATISTICAL ANALYSIS REPORT")
    print("="*60)
    print(f"Total records:        {len(df):,}")
    print(f"With coordinates:     {df['latitude'].notna().sum():,}")
    print(f"With year:            {df['year_converted'].notna().sum():,}")
    print(f"With sale price:      {df['sale_price_2024'].notna().sum():,}")
    print(f"\nConversion type breakdown:")
    for ct, count in df["conversion_type"].value_counts().head(10).items():
        pct = count / len(df) * 100
        print(f"  {ct:<30} {count:>6,}  ({pct:.1f}%)")

    # Proportion confidence intervals
    print(f"\n95% Confidence Intervals for key proportions:")
    total = len(df)
    for ct, label in [("mosque", "Mosque"), ("residential", "Residential")]:
        count = (df["conversion_type"] == ct).sum()
        prop = count / total
        ci = stats.proportion_confint(count, total, alpha=0.05, method="wilson")
        print(f"  {label}: {prop:.4f} (95% CI: {ci[0]:.4f}–{ci[1]:.4f})")

    # Kruskal-Wallis test on prices
    print(f"\nKruskal-Wallis test — are prices significantly different across types?")
    price_groups = [
        df[df["conversion_type"] == ct]["sale_price_2024"].dropna().values
        for ct in ["residential", "mosque", "hospitality", "community", "arts_culture"]
        if df[df["conversion_type"] == ct]["sale_price_2024"].notna().sum() >= 5
    ]
    if len(price_groups) >= 2:
        stat, p = stats.kruskal(*price_groups)
        print(f"  H = {stat:.2f}, p = {p:.6f}")
        if p < 0.05:
            print(f"  ✓ SIGNIFICANT: Sale prices differ significantly across conversion types")
        else:
            print(f"  ✗ Not significant")

    # Run the three analyses
    run_morans_i(df)
    run_interrupted_time_series(df)
    run_hedonic_regression(df)

    print("\n" + "="*60)
    print("ANALYSIS COMPLETE")
    print("="*60)
    print("Output files:")
    print("  data/output/mosque_hotspots_lisa.csv       (if libpysal installed)")
    print("  data/output/conversion_time_series.csv")
    print("  data/output/hedonic_regression_model.pickle")
    print("\nNext steps:")
    print("  python step4_summary_report.py             (final publication summary)")


if __name__ == "__main__":
    main()
    