"""
ml_classify_unknowns.py

Machine learning + NLP classification of unknown conversion types.

Three-stage pipeline:
  Stage 1 — TF-IDF + Logistic Regression classifier
             Trained on the 23,725 typed records
             Applied to the 8,714 unknowns
             Outputs: predicted_type, ml_confidence

  Stage 2 — Spatial inference (KNN)
             For each unknown, finds 5 nearest typed neighbours
             Uses majority vote weighted by distance
             Outputs: spatial_predicted_type, spatial_confidence

  Stage 3 — Ensemble
             Combines Stage 1 + Stage 2 predictions
             Only applies prediction where both agree OR confidence > 0.80
             Outputs: final_predicted_type, final_confidence

Importantly: predictions are stored in NEW columns, never overwriting
conversion_type. The researcher decides whether to accept them.

Run: pip install scikit-learn --break-system-packages
     python ml_classify_unknowns.py
"""

import glob
import logging
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def find_latest_csv():
    candidates = sorted(glob.glob("data/output/uk_church_conversions_2*.csv"), reverse=True)
    for c in candidates:
        if "PUBLIC" not in c and "enriched" not in c:
            return Path(c)
    return None


def main():
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import LabelEncoder
        from sklearn.neighbors import KNeighborsClassifier
        from sklearn.metrics import classification_report
    except ImportError:
        print("Install scikit-learn first:")
        print("  pip install scikit-learn --break-system-packages")
        return

    path = find_latest_csv()
    if not path:
        logger.error("No CSV found")
        return

    logger.info("Loading %s", path)
    df = pd.read_csv(path, low_memory=False)
    df["year_converted"] = pd.to_numeric(df["year_converted"], errors="coerce")
    df["sale_price_2024"] = pd.to_numeric(df["sale_price_2024"], errors="coerce")
    logger.info("Loaded %d records", len(df))

    # ── FEATURE ENGINEERING ──────────────────────────────────────────────────
    def build_text_features(row):
        parts = [
            str(row.get("church_name") or ""),
            str(row.get("address") or ""),
            str(row.get("city") or ""),
            str(row.get("notes") or ""),
            str(row.get("current_name") or ""),
            str(row.get("company_type") or ""),
            str(row.get("sic_code") or ""),
            str(row.get("former_denomination") or ""),
            str(row.get("region") or ""),
        ]
        return " ".join(p for p in parts if p and p not in ("nan","None",""))

    logger.info("Building text features...")
    df["_text"] = df.apply(build_text_features, axis=1)

    # ── STAGE 1: TF-IDF + LOGISTIC REGRESSION ────────────────────────────────
    logger.info("Stage 1: TF-IDF + Logistic Regression...")

    # Training set: typed records (not unknown)
    typed = df[df["conversion_type"] != "unknown"].copy()
    # Only use types with enough examples
    type_counts = typed["conversion_type"].value_counts()
    valid_types = type_counts[type_counts >= 10].index
    typed = typed[typed["conversion_type"].isin(valid_types)]

    logger.info("Training on %d typed records across %d categories", len(typed), len(valid_types))

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=5000,
            min_df=2,
            sublinear_tf=True,
        )),
        ("clf", LogisticRegression(
            max_iter=500,
            C=1.0,
            class_weight="balanced",
            random_state=42,
        )),
    ])

    pipeline.fit(typed["_text"], typed["conversion_type"])

    # Evaluate on training data (rough sanity check)
    train_preds = pipeline.predict(typed["_text"])
    logger.info("Training accuracy: %.1f%%", (train_preds == typed["conversion_type"]).mean() * 100)

    # Apply to unknowns
    unknowns = df[df["conversion_type"] == "unknown"].copy()
    logger.info("Classifying %d unknown records...", len(unknowns))

    if len(unknowns) > 0:
        proba = pipeline.predict_proba(unknowns["_text"])
        classes = pipeline.classes_
        preds = classes[proba.argmax(axis=1)]
        confs = proba.max(axis=1)

        df.loc[unknowns.index, "ml_predicted_type"] = preds
        df.loc[unknowns.index, "ml_confidence"] = confs.round(3)

        # Distribution of ML predictions
        pred_counts = pd.Series(preds).value_counts()
        print("\nStage 1 ML predictions for unknowns:")
        for ct, cnt in pred_counts.items():
            pct = cnt / len(unknowns) * 100
            avg_conf = confs[preds == ct].mean()
            print(f"  {ct:<30} {cnt:>6,}  ({pct:.1f}%)  avg_confidence: {avg_conf:.3f}")

        high_conf = (confs >= 0.80).sum()
        print(f"\nHigh confidence predictions (≥0.80): {high_conf:,} ({high_conf/len(unknowns)*100:.1f}%)")

    # ── STAGE 2: SPATIAL KNN ──────────────────────────────────────────────────
    logger.info("Stage 2: Spatial KNN inference...")

    spatial_typed = typed[typed["latitude"].notna() & typed["longitude"].notna()].copy()
    spatial_unknowns = unknowns[unknowns["latitude"].notna() & unknowns["longitude"].notna()].copy()

    if len(spatial_typed) >= 20 and len(spatial_unknowns) > 0:
        knn = KNeighborsClassifier(n_neighbors=5, weights="distance", metric="haversine")
        X_train = np.radians(spatial_typed[["latitude","longitude"]].values)
        knn.fit(X_train, spatial_typed["conversion_type"])

        X_pred = np.radians(spatial_unknowns[["latitude","longitude"]].values)
        knn_preds = knn.predict(X_pred)
        knn_probas = knn.predict_proba(X_pred).max(axis=1)

        df.loc[spatial_unknowns.index, "spatial_predicted_type"] = knn_preds
        df.loc[spatial_unknowns.index, "spatial_confidence"] = knn_probas.round(3)

        print(f"\nStage 2 spatial predictions: {len(spatial_unknowns):,} records with coordinates")
        print(pd.Series(knn_preds).value_counts().head(8).to_string())

    # ── STAGE 3: ENSEMBLE ─────────────────────────────────────────────────────
    logger.info("Stage 3: Ensemble combination...")

    ensemble_applied = 0
    if "ml_predicted_type" in df.columns:
        for idx, row in df[df["conversion_type"] == "unknown"].iterrows():
            ml_type = row.get("ml_predicted_type")
            ml_conf = row.get("ml_confidence", 0)
            sp_type = row.get("spatial_predicted_type")
            sp_conf = row.get("spatial_confidence", 0)

            final_type = None
            final_conf = 0.0

            # Both agree — high trust
            if ml_type and sp_type and ml_type == sp_type:
                final_type = ml_type
                final_conf = max(float(ml_conf or 0), float(sp_conf or 0))
            # Only ML but very high confidence
            elif ml_type and float(ml_conf or 0) >= 0.85:
                final_type = ml_type
                final_conf = float(ml_conf)
            # Only spatial but very high confidence
            elif sp_type and float(sp_conf or 0) >= 0.85:
                final_type = sp_type
                final_conf = float(sp_conf)

            if final_type:
                df.at[idx, "ensemble_predicted_type"] = final_type
                df.at[idx, "ensemble_confidence"] = round(final_conf, 3)
                ensemble_applied += 1

    print(f"\nStage 3 ensemble: {ensemble_applied:,} records with consensus prediction")

    if ensemble_applied > 0 and "ensemble_predicted_type" in df.columns:
        print("\nEnsemble prediction distribution:")
        print(df["ensemble_predicted_type"].value_counts().head(10).to_string())

        print("\nSample high-confidence predictions:")
        sample = df[
            df["ensemble_confidence"].notna() &
            (df["ensemble_confidence"] >= 0.85)
        ][["church_name","postcode","region","conversion_type",
           "ensemble_predicted_type","ensemble_confidence"]].head(15)
        print(sample.to_string())

    # ── HETEROSCEDASTICITY CHECK ──────────────────────────────────────────────
    logger.info("Running heteroscedasticity check on price data...")
    try:
        from statsmodels.stats.diagnostic import het_breuschpagan
        import statsmodels.api as sm

        price_df = df[
            df["sale_price_2024"].notna() &
            df["year_converted"].notna() &
            df["conversion_type"].notna() &
            df["conversion_type"].ne("unknown")
        ].copy()

        if len(price_df) >= 50:
            price_df["log_price"] = np.log(price_df["sale_price_2024"].clip(lower=1))
            price_df["year_c"] = price_df["year_converted"].astype(int)
            X = sm.add_constant(price_df[["year_c"]])
            model = sm.OLS(price_df["log_price"], X).fit()
            bp_stat, bp_p, f_stat, f_p = het_breuschpagan(model.resid, model.model.exog)

            print(f"\nHeteroscedasticity (Breusch-Pagan test):")
            print(f"  LM statistic: {bp_stat:.4f}")
            print(f"  p-value:      {bp_p:.4f}")
            if bp_p < 0.05:
                print(f"  SIGNIFICANT: Heteroscedasticity present — use robust standard errors")
                print(f"  This means price variance changes over time (expected — property market)")
            else:
                print(f"  Not significant — homoscedastic errors")
    except Exception as e:
        logger.warning("Heteroscedasticity test skipped: %s", e)

    # ── SAVE ──────────────────────────────────────────────────────────────────
    df.to_csv(path, index=False)
    logger.info("Saved with ML prediction columns: %s", path)

    print(f"\n{'='*60}")
    print("ML CLASSIFICATION COMPLETE")
    print(f"{'='*60}")
    print("New columns added:")
    print("  ml_predicted_type      — TF-IDF + Logistic Regression prediction")
    print("  ml_confidence          — model confidence (0-1)")
    print("  spatial_predicted_type — KNN spatial neighbour prediction")
    print("  spatial_confidence     — spatial model confidence")
    print("  ensemble_predicted_type — combined consensus prediction")
    print("  ensemble_confidence    — ensemble confidence")
    print()
    print("These are PREDICTIONS stored separately from conversion_type.")
    print("Review and accept with:")
    print("  python accept_ml_predictions.py --min-confidence 0.85")


if __name__ == "__main__":
    main()