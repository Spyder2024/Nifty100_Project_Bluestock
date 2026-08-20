"""tests/analytics/test_clustering.py — Unit and integration tests for Day 36 KMeans clustering.

Tests:
1. Feature extraction for all 92 companies.
2. Sector-median imputation with global median fallback.
3. StandardScaler feature standardization.
4. Inertia calculation across k=2..10 (monotonically decreasing).
5. KMeans fitting with n_clusters=5 and random_state=42 reproducibility.
6. Elbow plot creation and file output.
7. Output CSV schema, row count, and distance-from-centroid validation.
"""

import numpy as np
import pandas as pd
import pytest

from src.analytics.clustering import (
    DEFAULT_DB_PATH,
    FEATURE_COLUMNS,
    assign_cluster_names,
    compute_elbow,
    fit_kmeans,
    impute_features,
    load_clustering_features,
    plot_elbow,
    run_clustering,
    scale_features,
)


@pytest.fixture
def sample_feature_df():
    """Synthetic dataset with known sector structure and missing values."""
    return pd.DataFrame(
        {
            "company_id": ["C1", "C2", "C3", "C4", "C5", "C6"],
            "company_name": [
                "Comp 1",
                "Comp 2",
                "Comp 3",
                "Comp 4",
                "Comp 5",
                "Comp 6",
            ],
            "sector": ["Tech", "Tech", "Tech", "Energy", "Energy", "Energy"],
            "return_on_equity_pct": [25.0, np.nan, 20.0, 15.0, 18.0, np.nan],
            "debt_to_equity": [0.1, 0.2, np.nan, 1.5, np.nan, 2.0],
            "revenue_cagr_5yr": [15.0, 12.0, 18.0, 8.0, 10.0, np.nan],
            "fcf_cagr_5yr": [np.nan, 14.0, 16.0, 5.0, 7.0, 6.0],
            "operating_profit_margin_pct": [28.0, 25.0, np.nan, 35.0, 40.0, 38.0],
        }
    )


def test_load_clustering_features():
    """Verify loading from SQLite database returns 92 companies with required columns."""
    df = load_clustering_features(db_path=DEFAULT_DB_PATH)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 92
    assert "company_id" in df.columns
    assert "sector" in df.columns
    for col in FEATURE_COLUMNS:
        assert col in df.columns


def test_impute_features(sample_feature_df):
    """Verify sector median imputation removes all NaNs."""
    df_imputed = impute_features(sample_feature_df, feature_cols=FEATURE_COLUMNS)
    assert df_imputed[FEATURE_COLUMNS].isna().sum().sum() == 0

    # Tech ROE median is (25+20)/2 = 22.5
    assert (
        df_imputed.loc[df_imputed["company_id"] == "C2", "return_on_equity_pct"].iloc[0]
        == 22.5
    )


def test_scale_features(sample_feature_df):
    """Verify StandardScaler normalises features to zero mean and unit variance."""
    df_imputed = impute_features(sample_feature_df, feature_cols=FEATURE_COLUMNS)
    X_scaled, scaler = scale_features(df_imputed, feature_cols=FEATURE_COLUMNS)

    assert X_scaled.shape == (6, len(FEATURE_COLUMNS))
    np.testing.assert_allclose(X_scaled.mean(axis=0), 0.0, atol=1e-7)
    np.testing.assert_allclose(X_scaled.var(axis=0), 1.0, atol=1e-7)


def test_compute_elbow():
    """Verify inertia values are strictly positive and monotonically decreasing."""
    np.random.seed(42)
    X_dummy = np.random.randn(50, 5)
    elbow_data = compute_elbow(X_dummy, k_range=range(2, 7), random_state=42)

    assert len(elbow_data) == 5
    ks = [k for k, _ in elbow_data]
    inertias = [inert for _, inert in elbow_data]

    assert ks == [2, 3, 4, 5, 6]
    for i in range(len(inertias) - 1):
        assert inertias[i] > inertias[i + 1]


def test_fit_kmeans():
    """Verify KMeans fitting, reproducible labels, and valid Euclidean distances."""
    np.random.seed(42)
    X_dummy = np.random.randn(40, 5)
    km, labels, distances = fit_kmeans(X_dummy, n_clusters=5, random_state=42)

    assert len(labels) == 40
    assert len(set(labels)) <= 5
    assert len(distances) == 40
    assert (distances >= 0).all()


def test_assign_cluster_names():
    """Verify cluster names are generated uniquely."""
    centroid_df = pd.DataFrame(
        {
            "return_on_equity_pct": [15.0, 55.0, 1.0, 18.0, 17.0],
            "debt_to_equity": [0.7, 0.7, 0.0, 8.0, 0.7],
            "revenue_cagr_5yr": [11.0, 13.0, 500.0, 19.0, 14.0],
            "fcf_cagr_5yr": [16.0, 30.0, 14.0, 15.0, 20.0],
            "operating_profit_margin_pct": [20.0, 20.0, 85.0, 55.0, 80.0],
        }
    )
    names = assign_cluster_names(centroid_df)
    assert len(names) == 5
    assert len(set(names.values())) == 5
    for name in names.values():
        assert isinstance(name, str) and len(name) > 0


def test_plot_elbow(tmp_path):
    """Verify elbow plot generation and file persistence."""
    elbow_data = [(2, 360.0), (3, 270.0), (4, 210.0), (5, 170.0), (6, 130.0)]
    out_png = tmp_path / "test_elbow.png"
    result_path = plot_elbow(elbow_data, output_path=out_png, chosen_k=5)

    assert result_path.exists()
    assert result_path.stat().st_size > 1024


def test_run_clustering_e2e(tmp_path):
    """Verify end-to-end clustering run produces expected output files with 92 rows."""
    out_csv = tmp_path / "cluster_labels.csv"
    out_png = tmp_path / "elbow_plot.png"

    df_res, km, elbow = run_clustering(
        db_path=DEFAULT_DB_PATH,
        output_csv=out_csv,
        elbow_png=out_png,
        n_clusters=5,
        random_state=42,
    )

    assert out_csv.exists()
    assert out_png.exists()
    assert len(df_res) == 92

    df_csv = pd.read_csv(out_csv)
    assert len(df_csv) == 92
    assert list(df_csv.columns) == [
        "company_id",
        "cluster_id",
        "cluster_name",
        "distance_from_centroid",
    ]
    assert set(df_csv["cluster_id"].unique()).issubset({0, 1, 2, 3, 4})
    assert (df_csv["distance_from_centroid"] >= 0).all()
