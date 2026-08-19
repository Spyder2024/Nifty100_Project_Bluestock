"""src/analytics/clustering.py — Financial Clustering via KMeans (Day 36).

Sprint 6, Day 36

Implements:
1. Feature extraction from SQLite database:
   - return_on_equity_pct
   - debt_to_equity
   - revenue_cagr_5yr
   - fcf_cagr_5yr
   - operating_profit_margin_pct
2. Sector-median imputation for missing values (with global median fallback).
3. StandardScaler feature normalisation (zero mean, unit variance).
4. KMeans clustering with n_clusters=5 and random_state=42.
5. Elbow plot generation (inertia vs k from 2 to 10) saved to reports/elbow_plot.png.
6. Cluster assignment and distance-from-centroid computation saved to output/cluster_labels.csv.

Usage:
    python -m src.analytics.clustering
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Optional, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ── Project Paths ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DB_PATH = PROJECT_ROOT / "output" / "nifty100.db"
DEFAULT_OUTPUT_CSV = PROJECT_ROOT / "output" / "cluster_labels.csv"
DEFAULT_ELBOW_PNG = PROJECT_ROOT / "reports" / "elbow_plot.png"

FEATURE_COLUMNS = [
    "return_on_equity_pct",
    "debt_to_equity",
    "revenue_cagr_5yr",
    "fcf_cagr_5yr",
    "operating_profit_margin_pct",
]


# ===========================================================================
# 1. Feature Extraction
# ===========================================================================

def load_clustering_features(db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Load raw metrics for all 92 companies from database.

    Returns:
        DataFrame with columns: company_id, company_name, sector, and the 5 feature columns.
    """
    if not db_path.exists():
        # Fallback to db/nifty100.db if output/nifty100.db is absent
        fallback = PROJECT_ROOT / "db" / "nifty100.db"
        if fallback.exists():
            db_path = fallback
        else:
            raise FileNotFoundError(f"Database not found at {db_path} or {fallback}")

    conn = sqlite3.connect(str(db_path))

    # Read tables
    df_comps = pd.read_sql(
        """
        SELECT c.company_id, c.company_name, s.sector_name
        FROM companies c
        LEFT JOIN sectors s ON c.sector_id = s.sector_id
        ORDER BY c.company_id ASC
        """,
        conn,
    )

    df_is = pd.read_sql(
        "SELECT company_id, year, revenue, operating_income, net_income FROM income_statement ORDER BY company_id, year ASC",
        conn,
    )
    df_cf = pd.read_sql(
        "SELECT company_id, year, fcf, operating_cf, capex FROM cash_flow ORDER BY company_id, year ASC",
        conn,
    )
    df_rat = pd.read_sql(
        "SELECT company_id, year, roe, debt_to_equity, opm FROM ratios ORDER BY company_id, year DESC",
        conn,
    )
    df_bs = pd.read_sql(
        "SELECT company_id, year, total_equity, borrowings FROM balance_sheet ORDER BY company_id, year DESC",
        conn,
    )
    conn.close()

    records = []
    for _, row in df_comps.iterrows():
        cid = str(row["company_id"]).strip()
        cname = str(row["company_name"]).strip()
        sec = str(row["sector_name"] if pd.notna(row["sector_name"]) else "Unclassified").strip()

        sub_rat = df_rat[df_rat["company_id"] == cid]
        sub_is = df_is[df_is["company_id"] == cid]
        sub_cf = df_cf[df_cf["company_id"] == cid]
        sub_bs = df_bs[df_bs["company_id"] == cid]

        # 1. Return on Equity (ROE %)
        roe = None
        if not sub_rat.empty and pd.notna(sub_rat.iloc[0]["roe"]):
            raw_roe = float(sub_rat.iloc[0]["roe"])
            if -100.0 <= raw_roe <= 150.0:
                roe = raw_roe
        if roe is None and not sub_is.empty and not sub_bs.empty:
            ni = sub_is.iloc[-1]["net_income"]
            eq = sub_bs.iloc[0]["total_equity"]
            if eq and eq > 0 and ni is not None:
                roe = (float(ni) / float(eq)) * 100.0

        # 2. Debt-to-Equity
        de = None
        if not sub_rat.empty and pd.notna(sub_rat.iloc[0]["debt_to_equity"]):
            raw_de = float(sub_rat.iloc[0]["debt_to_equity"])
            if raw_de <= 50.0:
                de = raw_de
        if (de is None or de > 50.0) and not sub_bs.empty:
            eq = sub_bs.iloc[0]["total_equity"]
            borr = sub_bs.iloc[0]["borrowings"]
            if eq and eq > 0 and borr is not None:
                de = float(borr) / float(eq)

        # 3. Operating Profit Margin (OPM %)
        opm = None
        if not sub_is.empty:
            rev = sub_is.iloc[-1]["revenue"]
            oi = sub_is.iloc[-1]["operating_income"]
            if rev and rev > 0 and oi is not None:
                opm = (float(oi) / float(rev)) * 100.0
        if opm is None and not sub_rat.empty and pd.notna(sub_rat.iloc[0]["opm"]):
            raw_opm = float(sub_rat.iloc[0]["opm"])
            if -100.0 <= raw_opm <= 100.0:
                opm = raw_opm

        # 4. Revenue CAGR 5yr (%)
        rev_cagr = None
        if len(sub_is) >= 6:
            s_val = sub_is.iloc[-6]["revenue"]
            e_val = sub_is.iloc[-1]["revenue"]
            if s_val and e_val and s_val > 0 and e_val > 0:
                rev_cagr = ((float(e_val) / float(s_val)) ** (1.0 / 5.0) - 1.0) * 100.0
        elif len(sub_is) >= 2:
            ny = len(sub_is) - 1
            s_val = sub_is.iloc[0]["revenue"]
            e_val = sub_is.iloc[-1]["revenue"]
            if s_val and e_val and s_val > 0 and e_val > 0:
                rev_cagr = ((float(e_val) / float(s_val)) ** (1.0 / ny) - 1.0) * 100.0

        # 5. FCF CAGR 5yr (%)
        fcf_cagr = None
        if len(sub_cf) >= 6:
            s_fcf = sub_cf.iloc[-6]["fcf"]
            if pd.isna(s_fcf) or s_fcf is None:
                s_fcf = (sub_cf.iloc[-6]["operating_cf"] or 0) - (sub_cf.iloc[-6]["capex"] or 0)
            e_fcf = sub_cf.iloc[-1]["fcf"]
            if pd.isna(e_fcf) or e_fcf is None:
                e_fcf = (sub_cf.iloc[-1]["operating_cf"] or 0) - (sub_cf.iloc[-1]["capex"] or 0)
            if s_fcf and e_fcf and s_fcf > 0 and e_fcf > 0:
                fcf_cagr = ((float(e_fcf) / float(s_fcf)) ** (1.0 / 5.0) - 1.0) * 100.0
        elif len(sub_cf) >= 2:
            ny = len(sub_cf) - 1
            s_fcf = sub_cf.iloc[0]["fcf"]
            if pd.isna(s_fcf) or s_fcf is None:
                s_fcf = (sub_cf.iloc[0]["operating_cf"] or 0) - (sub_cf.iloc[0]["capex"] or 0)
            e_fcf = sub_cf.iloc[-1]["fcf"]
            if pd.isna(e_fcf) or e_fcf is None:
                e_fcf = (sub_cf.iloc[-1]["operating_cf"] or 0) - (sub_cf.iloc[-1]["capex"] or 0)
            if s_fcf and e_fcf and s_fcf > 0 and e_fcf > 0:
                fcf_cagr = ((float(e_fcf) / float(s_fcf)) ** (1.0 / ny) - 1.0) * 100.0

        records.append({
            "company_id": cid,
            "company_name": cname,
            "sector": sec,
            "return_on_equity_pct": roe,
            "debt_to_equity": de,
            "revenue_cagr_5yr": rev_cagr,
            "fcf_cagr_5yr": fcf_cagr,
            "operating_profit_margin_pct": opm,
        })

    return pd.DataFrame(records)


# ===========================================================================
# 2. Imputation & Scaling
# ===========================================================================

def impute_features(df: pd.DataFrame, feature_cols: Sequence[str] = FEATURE_COLUMNS) -> pd.DataFrame:
    """Impute missing values with sector median for each metric, with global median fallback."""
    df_clean = df.copy()
    for col in feature_cols:
        sec_median = df_clean.groupby("sector")[col].transform("median")
        df_clean[col] = df_clean[col].fillna(sec_median)
        # Fallback if entire sector had NaNs
        global_median = df_clean[col].median()
        df_clean[col] = df_clean[col].fillna(global_median if pd.notna(global_median) else 0.0)
    return df_clean


def scale_features(df: pd.DataFrame, feature_cols: Sequence[str] = FEATURE_COLUMNS) -> tuple[np.ndarray, StandardScaler]:
    """Standardize features to zero mean and unit variance."""
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df[list(feature_cols)])
    return X_scaled, scaler


# ===========================================================================
# 3. Elbow Analysis & Plotting
# ===========================================================================

def compute_elbow(
    X_scaled: np.ndarray,
    k_range: Sequence[int] = range(2, 11),
    random_state: int = 42,
) -> list[tuple[int, float]]:
    """Calculate inertia for k from 2 to 10."""
    results = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        km.fit(X_scaled)
        results.append((k, float(km.inertia_)))
    return results


def plot_elbow(
    elbow_data: list[tuple[int, float]],
    output_path: Path = DEFAULT_ELBOW_PNG,
    chosen_k: int = 5,
) -> Path:
    """Generate and save the elbow plot visualization."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ks, inertias = zip(*elbow_data)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    # Plot line
    ax.plot(
        ks,
        inertias,
        marker="o",
        color="#2563EB",
        linewidth=2.2,
        markersize=7,
        label="Inertia (WCSS)",
    )

    # Highlight chosen k
    chosen_inertia = [inert for k, inert in elbow_data if k == chosen_k][0]
    ax.scatter(
        [chosen_k],
        [chosen_inertia],
        color="#DC2626",
        s=140,
        zorder=5,
        label=f"Selected k={chosen_k} (Optimal Elbow)",
    )
    ax.axvline(x=chosen_k, color="#DC2626", linestyle="--", linewidth=1.2, alpha=0.7)

    # Annotate
    ax.annotate(
        f"Elbow Point (k={chosen_k})\nInertia = {chosen_inertia:.1f}",
        xy=(chosen_k, chosen_inertia),
        xytext=(chosen_k + 0.6, chosen_inertia + 25),
        arrowprops=dict(facecolor="#0F172A", shrink=0.08, width=1, headwidth=6),
        fontsize=9,
        fontweight="bold",
        color="#0F172A",
        bbox=dict(boxstyle="round,pad=0.4", fc="#FFFFFF", ec="#CBD5E1", lw=0.8),
    )

    ax.set_title("Nifty 100 KMeans Clustering — Elbow Curve Analysis", fontsize=12, fontweight="bold", pad=12, color="#0F172A")
    ax.set_xlabel("Number of Clusters (k)", fontsize=10, fontweight="bold", color="#334155")
    ax.set_ylabel("Inertia / Within-Cluster Sum of Squares (WCSS)", fontsize=10, fontweight="bold", color="#334155")
    ax.set_xticks(list(ks))
    ax.grid(True, linestyle=":", alpha=0.6, color="#CBD5E1")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0", loc="upper right")

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)

    logger.info("Saved elbow plot to: %s", output_path)
    return output_path


# ===========================================================================
# 4. KMeans Fitting & Intuitive Cluster Naming
# ===========================================================================

def assign_cluster_names(centroid_df: pd.DataFrame) -> dict[int, str]:
    """Generate meaningful business names for each cluster based on centroid metrics."""
    names = {}
    for cluster_id, row in centroid_df.iterrows():
        roe = row["return_on_equity_pct"]
        de = row["debt_to_equity"]
        rev_g = row["revenue_cagr_5yr"]
        fcf_g = row["fcf_cagr_5yr"]
        opm = row["operating_profit_margin_pct"]

        if de >= 3.5:
            name = "High Leverage Financials & Expansion"
        elif roe >= 35.0:
            name = "High ROE Capital Efficient Leaders"
        elif rev_g >= 100.0 or (opm >= 75.0 and de <= 0.2):
            name = "Newly Listed Hyper-Growth & High Margin"
        elif opm >= 65.0:
            name = "High Margin Asset-Efficient Cash Generators"
        elif opm <= 30.0 and de <= 1.5:
            name = "Stable Quality & Moderate Margin Compounders"
        else:
            name = f"Cluster {cluster_id} Core Performers"

        names[int(cluster_id)] = name

    # Ensure all names are unique
    seen = set()
    for cid in sorted(names.keys()):
        base_name = names[cid]
        if base_name in seen:
            names[cid] = f"{base_name} (Group {cid})"
        seen.add(names[cid])

    return names


def fit_kmeans(
    X_scaled: np.ndarray,
    n_clusters: int = 5,
    random_state: int = 42,
) -> tuple[KMeans, np.ndarray, np.ndarray]:
    """Fit KMeans model and compute Euclidean distance of each sample from its cluster centroid."""
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = kmeans.fit_predict(X_scaled)
    centroids = kmeans.cluster_centers_

    # Distance from centroid
    distances = np.linalg.norm(X_scaled - centroids[labels], axis=1)
    return kmeans, labels, distances


# ===========================================================================
# 5. End-to-End Orchestrator
# ===========================================================================

def run_clustering(
    db_path: Path = DEFAULT_DB_PATH,
    output_csv: Path = DEFAULT_OUTPUT_CSV,
    elbow_png: Path = DEFAULT_ELBOW_PNG,
    n_clusters: int = 5,
    random_state: int = 42,
) -> tuple[pd.DataFrame, KMeans, list[tuple[int, float]]]:
    """Execute complete clustering workflow and save deliverables."""
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    elbow_png.parent.mkdir(parents=True, exist_ok=True)

    # 1. Load Features
    df_raw = load_clustering_features(db_path=db_path)
    logger.info("Loaded features for %d companies.", len(df_raw))

    # 2. Impute missing values with sector median
    df_clean = impute_features(df_raw, feature_cols=FEATURE_COLUMNS)

    # 3. Standardize features
    X_scaled, scaler = scale_features(df_clean, feature_cols=FEATURE_COLUMNS)

    # 4. Elbow Plot (k=2..10)
    elbow_data = compute_elbow(X_scaled, k_range=range(2, 11), random_state=random_state)
    plot_elbow(elbow_data, output_path=elbow_png, chosen_k=n_clusters)

    # 5. Fit KMeans with k=5
    kmeans, labels, distances = fit_kmeans(X_scaled, n_clusters=n_clusters, random_state=random_state)
    df_clean["cluster_id"] = labels
    df_clean["distance_from_centroid"] = np.round(distances, 4)

    # 6. Assign intuitive cluster names
    centroids_orig = scaler.inverse_transform(kmeans.cluster_centers_)
    centroid_df = pd.DataFrame(centroids_orig, columns=FEATURE_COLUMNS)
    cluster_names = assign_cluster_names(centroid_df)
    df_clean["cluster_name"] = df_clean["cluster_id"].map(cluster_names)

    # 7. Write output/cluster_labels.csv
    output_df = df_clean[["company_id", "cluster_id", "cluster_name", "distance_from_centroid"]].copy()
    output_df.to_csv(output_csv, index=False)
    logger.info("Saved cluster labels to: %s (%d rows)", output_csv, len(output_df))

    return df_clean, kmeans, elbow_data


# ===========================================================================
# CLI Entrypoint
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Run KMeans Clustering on Nifty 100 constituents.")
    parser.add_argument("--db", type=str, default=str(DEFAULT_DB_PATH), help="Path to SQLite database.")
    parser.add_argument("--output-csv", type=str, default=str(DEFAULT_OUTPUT_CSV), help="Output path for cluster CSV.")
    parser.add_argument("--elbow-png", type=str, default=str(DEFAULT_ELBOW_PNG), help="Output path for elbow plot.")
    parser.add_argument("--k", type=int, default=5, help="Number of clusters (default: 5).")
    parser.add_argument("--seed", type=int, default=42, help="Random state seed.")
    args = parser.parse_args()

    print("=" * 70)
    print("Day 36 — KMeans Financial Clustering Engine")
    print("=" * 70)

    df_res, km, elbow = run_clustering(
        db_path=Path(args.db),
        output_csv=Path(args.output_csv),
        elbow_png=Path(args.elbow_png),
        n_clusters=args.k,
        random_state=args.seed,
    )

    print("\n[ELBOW CURVE RESULTS]")
    for k_val, inert in elbow:
        marker = " <--- (CHOSEN K)" if k_val == args.k else ""
        print(f"  k={k_val:2d}: Inertia = {inert:8.2f}{marker}")

    print("\n[CLUSTER DISTRIBUTION]")
    counts = df_res.groupby(["cluster_id", "cluster_name"]).size()
    for (cid, cname), count in counts.items():
        print(f"  Cluster {cid} [{cname}]: {count} companies")

    print("\n[SAMPLE ASSIGNMENTS]")
    sample_df = df_res[["company_id", "sector", "cluster_id", "cluster_name", "distance_from_centroid"]].head(12)
    print(sample_df.to_string(index=False))

    print(f"\n[DONE] Deliverables created:")
    print(f"  • CSV: {args.output_csv}")
    print(f"  • PNG: {args.elbow_png}")


if __name__ == "__main__":
    main()
