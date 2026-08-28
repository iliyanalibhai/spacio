"""Trains the pricing model and writes a versioned artifact.

Run from `api/` with the venv active:

    python -m app.ml.train_pricing_model

Trains three LightGBM quantile regressors (p15/p50/p85) on the synthetic
comps dataset from `synthetic_pricing_data.py`, evaluates the median model's
MAE against a naive per-ZIP-demand-tier-per-sqft baseline, and writes the
result to `app/ml/artifacts/pricing_model_<VERSION>.joblib`. Bump VERSION
below whenever the feature set or training data generation changes in a way
that makes an old artifact incompatible, so `ai_pricing.py` (which loads a
pinned filename) and this script never silently drift apart.

The whole pipeline is deterministic given SEED — re-running this script
reproduces the exact same artifact byte-for-byte-equivalent predictions,
which is what makes it safe to commit the artifact to the repo instead of
training at deploy time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import joblib  # type: ignore[import-untyped]
import lightgbm as lgb
import pandas as pd
from sklearn.metrics import mean_absolute_error  # type: ignore[import-untyped]
from sklearn.model_selection import train_test_split  # type: ignore[import-untyped]

from app.ml.features import CATEGORICAL_COLUMNS, FEATURE_COLUMNS, SIZE_CATEGORIES, TIER_CATEGORIES
from app.ml.synthetic_pricing_data import generate_synthetic_comps

VERSION = "v1"
SEED = 42
N_ROWS = 8000
QUANTILES = {"p15": 0.15, "p50": 0.5, "p85": 0.85}
ARTIFACT_PATH = Path(__file__).parent / "artifacts" / f"pricing_model_{VERSION}.joblib"


def _to_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df[FEATURE_COLUMNS].copy()
    out["size"] = pd.Categorical(out["size"], categories=SIZE_CATEGORIES)
    out["zip_demand_tier"] = pd.Categorical(out["zip_demand_tier"], categories=TIER_CATEGORIES)
    return out


def _naive_baseline_mae(train_df: pd.DataFrame, test_df: pd.DataFrame) -> float:
    """Naive per-ZIP-demand-tier $/sqft baseline: for each tier, the mean
    training $/sqft rate, applied linearly to the test row's sqft. This is
    the baseline `docs/DOCUMENTATION.md` §6 promises the real model is
    evaluated against — it captures the ZIP/tier signal but none of the
    sqft-scaling, indoor, or interaction effects the trained model can."""
    rate_per_tier = (train_df["price"] / train_df["sizeSqft"]).groupby(train_df["zip_demand_tier"]).mean()
    predicted = test_df["zip_demand_tier"].map(rate_per_tier) * test_df["sizeSqft"]
    return float(mean_absolute_error(test_df["price"], predicted))


def train() -> None:
    df = generate_synthetic_comps(n=N_ROWS, seed=SEED)
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=SEED)

    X_train, y_train = _to_feature_frame(train_df), train_df["price"]
    X_test, y_test = _to_feature_frame(test_df), test_df["price"]

    models: dict[str, lgb.LGBMRegressor] = {}
    for name, alpha in QUANTILES.items():
        model = lgb.LGBMRegressor(
            objective="quantile",
            alpha=alpha,
            n_estimators=300,
            num_leaves=15,
            max_depth=5,
            learning_rate=0.05,
            min_child_samples=20,
            random_state=SEED,
            verbosity=-1,
        )
        model.fit(X_train, y_train, categorical_feature=CATEGORICAL_COLUMNS)
        models[name] = model

    median_predictions = models["p50"].predict(X_test)
    model_mae = float(mean_absolute_error(y_test, median_predictions))
    baseline_mae = _naive_baseline_mae(train_df, test_df)

    metrics = {
        "model_mae": round(model_mae, 4),
        "naive_zip_tier_per_sqft_baseline_mae": round(baseline_mae, 4),
        "improvement_over_baseline_pct": round(100 * (1 - model_mae / baseline_mae), 2),
        "n_train": len(train_df),
        "n_test": len(test_df),
    }

    bundle = {
        "version": VERSION,
        "models": models,
        "feature_columns": FEATURE_COLUMNS,
        "categorical_columns": CATEGORICAL_COLUMNS,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "lightgbm_version": lgb.__version__,
        "metrics": metrics,
    }

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, ARTIFACT_PATH)

    print(f"Wrote {ARTIFACT_PATH}")
    print(f"Trained on {metrics['n_train']} rows, evaluated on {metrics['n_test']} held-out rows.")
    print(f"Model MAE:            ${metrics['model_mae']:.2f}")
    print(f"Naive baseline MAE:   ${metrics['naive_zip_tier_per_sqft_baseline_mae']:.2f}")
    print(f"Improvement:          {metrics['improvement_over_baseline_pct']:.1f}%")


if __name__ == "__main__":
    train()
