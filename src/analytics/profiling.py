"""src/analytics/profiling.py — Cluster Profiling & Portfolio Statistics (Day 37).

Sprint 6, Day 37

Implements:
1. Cluster profiling: Compute mean and median of all 5 input features per cluster.
2. Descriptive naming of the 5 clusters based on financial profiles and constituent companies.
3. 10-KPI correlation matrix heatmap using seaborn with annotations (reports/correlation_heatmap.png).
4. Sector-level Z-score outlier detection (|Z| > 3) saved to output/outlier_report.csv.
5. Portfolio distribution statistics (P10, P25, P50, P75, P90, Mean, Std) saved to output/portfolio_stats.csv.

Usage:
    python -m src.analytics.profiling
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
import seaborn as sns

from src.analytics.clustering import (
    DEFAULT_DB_PATH,
    FEATURE_COLUMNS,
    impute_features,
    load_clustering_features,
    run_clustering,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ── Paths ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_HEATMAP_PNG = PROJECT_ROOT / "reports" / "correlation_heatmap.png"
DEFAULT_OUTLIER_CSV = PROJECT_ROOT / "output" / "outlier_report.csv"
DEFAULT_STATS_CSV = PROJECT_ROOT / "output" / "portfolio_stats.csv"
DEFAULT_CLUSTER_LABELS_CSV = PROJECT_ROOT / "output" / "cluster_labels.csv"

# ── 10 Key Performance Indicators for Portfolio Analytics ───────────
KPI_10_COLUMNS = [
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "operating_profit_margin_pct",
    "net_profit_margin_pct",
    "debt_to_equity",
    "interest_coverage_ratio",
    "asset_turnover",
    "dividend_payout_pct",
    "revenue_cagr_5yr",
    "fcf_cagr_5yr",
]

KPI_DISPLAY_NAMES = {
    "return_on_equity_pct": "ROE (%)",
    "return_on_capital_employed_pct": "ROCE (%)",
    "operating_profit_margin_pct": "OPM (%)",
    "net_profit_margin_pct": "NPM (%)",
    "debt_to_equity": "Debt / Equity",
    "interest_coverage_ratio": "Interest Coverage",
    "asset_turnover": "Asset Turnover",
    "dividend_payout_pct": "Dividend Payout (%)",
    "revenue_cagr_5yr": "Revenue CAGR 5Y (%)",
    "fcf_cagr_5yr": "FCF CAGR 5Y (%)",
}

CLUSTER_DESCRIPTIVE_NAMES = {
    0: "High-Quality Core Compounders",
    1: "Defensive High-ROE Leaders",
    2: "Emerging Growth & High Margin FinTech",
    3: "Financial Expansion & High-Leverage Growth",
    4: "Capital-Efficient Value Cyclicals",
}


# ===========================================================================
# 1. 10-KPI Extraction
# ===========================================================================

def load_10_kpis_data(db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Extract 10 core financial KPIs across all 92 companies for the latest year."""
    if not db_path.exists():
        fallback = PROJECT_ROOT / "db" / "nifty100.db"
        if fallback.exists():
            db_path = fallback
        else:
            raise FileNotFoundError(f"Database not found at {db_path} or {fallback}")

    conn = sqlite3.connect(str(db_path))

    df_comps = pd.read_sql(
        """
        SELECT c.company_id, c.company_name, s.sector_name
        FROM companies c
        LEFT JOIN sectors s ON c.sector_id = s.sector_id
        ORDER BY c.company_id ASC
        """,
        conn,
    )

    df_r = pd.read_sql("SELECT * FROM ratios ORDER BY company_id, year DESC", conn)
    df_is = pd.read_sql("SELECT * FROM income_statement ORDER BY company_id, year ASC", conn)
    df_bs = pd.read_sql("SELECT * FROM balance_sheet ORDER BY company_id, year DESC", conn)
    df_cf = pd.read_sql("SELECT * FROM cash_flow ORDER BY company_id, year ASC", conn)
    conn.close()

    rows = []
    for _, crow in df_comps.iterrows():
        cid = str(crow["company_id"]).strip()
        cname = str(crow["company_name"]).strip()
        sec = str(crow["sector_name"] if pd.notna(crow["sector_name"]) else "Unclassified").strip()

        sub_r = df_r[df_r["company_id"] == cid]
        sub_is = df_is[df_is["company_id"] == cid]
        sub_bs = df_bs[df_bs["company_id"] == cid]
        sub_cf = df_cf[df_cf["company_id"] == cid]

        # 1. Return on Equity (ROE %)
        roe = sub_r.iloc[0]["roe"] if not sub_r.empty and pd.notna(sub_r.iloc[0]["roe"]) else None
        if roe is not None and (roe < -100.0 or roe > 150.0):
            roe = None
        if roe is None and not sub_is.empty and not sub_bs.empty:
            ni = sub_is.iloc[-1]["net_income"]
            eq = sub_bs.iloc[0]["total_equity"]
            if eq and eq > 0 and ni is not None:
                roe = (float(ni) / float(eq)) * 100.0

        # 2. Return on Capital Employed (ROCE %)
        roce = sub_r.iloc[0]["roce"] if not sub_r.empty and pd.notna(sub_r.iloc[0]["roce"]) else None
        if roce is not None and (roce < -100.0 or roce > 150.0):
            roce = None
        if roce is None and not sub_is.empty and not sub_bs.empty:
            ebit = sub_is.iloc[-1]["ebit"] if pd.notna(sub_is.iloc[-1]["ebit"]) else sub_is.iloc[-1]["operating_income"]
            cap_emp = (sub_bs.iloc[0]["total_equity"] or 0) + (sub_bs.iloc[0]["borrowings"] or 0)
            if cap_emp and cap_emp > 10.0 and ebit is not None:
                calc_roce = (float(ebit) / float(cap_emp)) * 100.0
                if -100.0 <= calc_roce <= 150.0:
                    roce = calc_roce

        # 3. Operating Profit Margin (OPM %)
        opm = None
        if not sub_is.empty:
            rev = sub_is.iloc[-1]["revenue"]
            oi = sub_is.iloc[-1]["operating_income"]
            if rev and rev > 0 and oi is not None:
                opm = (float(oi) / float(rev)) * 100.0
        if opm is None and not sub_r.empty and pd.notna(sub_r.iloc[0]["opm"]):
            raw_opm = float(sub_r.iloc[0]["opm"])
            if -100.0 <= raw_opm <= 100.0:
                opm = raw_opm

        # 4. Net Profit Margin (NPM %)
        npm = None
        if not sub_is.empty:
            rev = sub_is.iloc[-1]["revenue"]
            ni = sub_is.iloc[-1]["net_income"]
            if rev and rev > 0 and ni is not None:
                calc_npm = (float(ni) / float(rev)) * 100.0
                if -100.0 <= calc_npm <= 100.0:
                    npm = calc_npm

        # 5. Debt to Equity
        de = sub_r.iloc[0]["debt_to_equity"] if not sub_r.empty and pd.notna(sub_r.iloc[0]["debt_to_equity"]) else None
        if (de is None or de > 50.0) and not sub_bs.empty:
            eq = sub_bs.iloc[0]["total_equity"]
            borr = sub_bs.iloc[0]["borrowings"]
            if eq and eq > 0 and borr is not None:
                de = float(borr) / float(eq)

        # 6. Interest Coverage Ratio
        icr = sub_r.iloc[0]["interest_coverage"] if not sub_r.empty and pd.notna(sub_r.iloc[0]["interest_coverage"]) else None
        if (icr is None or icr < -100.0 or icr > 150.0) and not sub_is.empty:
            ebit = sub_is.iloc[-1]["ebit"] if pd.notna(sub_is.iloc[-1]["ebit"]) else sub_is.iloc[-1]["operating_income"]
            ie = sub_is.iloc[-1]["interest_expense"]
            if ie and ie > 0 and ebit is not None:
                calc_icr = float(ebit) / float(ie)
                if -100.0 <= calc_icr <= 150.0:
                    icr = calc_icr
            elif ie == 0 and ebit is not None:
                icr = 50.0
        if icr is not None and icr > 150.0:
            icr = 150.0

        # 7. Asset Turnover
        at = sub_r.iloc[0]["asset_turnover"] if not sub_r.empty and pd.notna(sub_r.iloc[0]["asset_turnover"]) else None
        if (at is None or at > 10.0) and not sub_is.empty and not sub_bs.empty:
            rev = sub_is.iloc[-1]["revenue"]
            ta = sub_bs.iloc[0]["total_assets"]
            if ta and ta > 0 and rev is not None:
                calc_at = float(rev) / float(ta)
                if 0.0 <= calc_at <= 10.0:
                    at = calc_at

        # 8. Dividend Payout Ratio (%)
        div_payout = sub_r.iloc[0]["dividend_payout"] if not sub_r.empty and pd.notna(sub_r.iloc[0]["dividend_payout"]) else None
        if div_payout is not None and (div_payout < 0 or div_payout > 200.0):
            div_payout = None
        if div_payout is None and not sub_cf.empty and not sub_is.empty:
            div_paid = abs(sub_cf.iloc[-1]["dividend_paid"] or 0)
            ni = sub_is.iloc[-1]["net_income"]
            if ni and ni > 0 and div_paid > 0:
                div_payout = (float(div_paid) / float(ni)) * 100.0

        # 9. Revenue CAGR 5yr (%)
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

        # 10. FCF CAGR 5yr (%)
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

        rows.append({
            "company_id": cid,
            "company_name": cname,
            "sector": sec,
            "return_on_equity_pct": roe,
            "return_on_capital_employed_pct": roce,
            "operating_profit_margin_pct": opm,
            "net_profit_margin_pct": npm,
            "debt_to_equity": de,
            "interest_coverage_ratio": icr,
            "asset_turnover": at,
            "dividend_payout_pct": div_payout,
            "revenue_cagr_5yr": rev_cagr,
            "fcf_cagr_5yr": fcf_cagr,
        })

    return pd.DataFrame(rows)


# ===========================================================================
# 2. Cluster Profiling & Detailed Statistics
# ===========================================================================

def profile_clusters(
    df_clustered: pd.DataFrame,
    feature_cols: Sequence[str] = FEATURE_COLUMNS,
) -> pd.DataFrame:
    """Compute mean and median of all 5 input features per cluster.

    Returns:
        DataFrame with cluster profile statistics and constituent counts.
    """
    profiles = []
    for cluster_id in sorted(df_clustered["cluster_id"].unique()):
        sub = df_clustered[df_clustered["cluster_id"] == cluster_id]
        cname = CLUSTER_DESCRIPTIVE_NAMES.get(cluster_id, f"Cluster {cluster_id}")

        profile = {
            "cluster_id": cluster_id,
            "cluster_name": cname,
            "company_count": len(sub),
            "sample_companies": ", ".join(sub["company_id"].head(6).tolist()),
        }

        for col in feature_cols:
            vals = sub[col].dropna()
            profile[f"{col}_mean"] = round(vals.mean(), 2) if not vals.empty else 0.0
            profile[f"{col}_median"] = round(vals.median(), 2) if not vals.empty else 0.0

        profiles.append(profile)

    return pd.DataFrame(profiles)


# ===========================================================================
# 3. Correlation Matrix Heatmap
# ===========================================================================

def generate_correlation_heatmap(
    df_kpis: pd.DataFrame,
    output_path: Path = DEFAULT_HEATMAP_PNG,
    kpi_cols: Sequence[str] = KPI_10_COLUMNS,
) -> Path:
    """Compute Pearson correlation matrix of 10 KPIs and generate a seaborn heatmap."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Impute missing values with sector median for correlation computation
    df_clean = impute_features(df_kpis, feature_cols=kpi_cols)

    # Calculate Pearson correlation
    corr_matrix = df_clean[list(kpi_cols)].corr(method="pearson")

    # Rename index and columns for display
    display_labels = [KPI_DISPLAY_NAMES.get(col, col) for col in kpi_cols]
    corr_matrix.index = display_labels
    corr_matrix.columns = display_labels

    # Plot
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    # Mask upper triangle for clean half-matrix or full view
    cmap = sns.diverging_palette(220, 10, as_cmap=True)

    sns.heatmap(
        corr_matrix,
        annot=True,
        fmt=".2f",
        cmap=cmap,
        vmin=-1.0,
        vmax=1.0,
        center=0.0,
        square=True,
        linewidths=0.75,
        linecolor="#E2E8F0",
        cbar_kws={"shrink": 0.8, "label": "Pearson Correlation Coefficient (r)"},
        annot_kws={"size": 8.5, "weight": "bold"},
        ax=ax,
    )

    ax.set_title(
        "Nifty 100 Financial KPI Correlation Matrix (10 Core Metrics)",
        fontsize=13,
        fontweight="bold",
        pad=16,
        color="#0F172A",
    )
    plt.xticks(rotation=45, ha="right", fontsize=9, fontweight="bold", color="#334155")
    plt.yticks(rotation=0, fontsize=9, fontweight="bold", color="#334155")

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)

    logger.info("Generated correlation heatmap -> %s", output_path)
    return output_path


# ===========================================================================
# 4. Sector-Level Z-Score Outlier Detection
# ===========================================================================

def detect_sector_outliers(
    df_kpis: pd.DataFrame,
    metric_cols: Sequence[str] = KPI_10_COLUMNS,
    threshold: float = 3.0,
    output_path: Optional[Path] = DEFAULT_OUTLIER_CSV,
) -> pd.DataFrame:
    """Detect company outliers with |Z-score| > 3.0 grouped by sector."""
    df_clean = impute_features(df_kpis, feature_cols=metric_cols)

    outlier_records = []
    for sector, grp in df_clean.groupby("sector"):
        for col in metric_cols:
            vals = grp[col].dropna()
            if len(vals) < 2:
                continue

            sec_mean = vals.mean()
            sec_std = vals.std(ddof=1)

            if sec_std == 0 or pd.isna(sec_std):
                continue

            for _, r in grp.iterrows():
                val = r[col]
                if pd.isna(val):
                    continue

                z_score = (val - sec_mean) / sec_std
                if abs(z_score) > threshold:
                    outlier_records.append({
                        "company_id": r["company_id"],
                        "company_name": r["company_name"],
                        "sector": sector,
                        "metric_name": col,
                        "metric_value": round(float(val), 2),
                        "sector_mean": round(float(sec_mean), 2),
                        "sector_std": round(float(sec_std), 2),
                        "z_score": round(float(z_score), 2),
                        "outlier_type": "HIGH" if z_score > 0 else "LOW",
                    })

    df_outliers = pd.DataFrame(outlier_records)
    if not df_outliers.empty:
        df_outliers = df_outliers.sort_values(by=["sector", "metric_name", "z_score"], ascending=[True, True, False])

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df_outliers.to_csv(output_path, index=False)
        logger.info("Saved outlier report to: %s (%d outliers)", output_path, len(df_outliers))

    return df_outliers


# ===========================================================================
# 5. Portfolio Distribution Statistics (P10, P25, P50, P75, P90, Mean, Std)
# ===========================================================================

def compute_portfolio_stats(
    df_kpis: pd.DataFrame,
    metric_cols: Sequence[str] = KPI_10_COLUMNS,
    output_path: Optional[Path] = DEFAULT_STATS_CSV,
) -> pd.DataFrame:
    """Compute distribution statistics (P10, P25, P50, P75, P90, Mean, Std) across all 92 companies."""
    df_clean = impute_features(df_kpis, feature_cols=metric_cols)

    stats_list = []
    for col in metric_cols:
        series = df_clean[col].dropna()
        if series.empty:
            continue

        stats_list.append({
            "metric_name": col,
            "display_name": KPI_DISPLAY_NAMES.get(col, col),
            "P10": round(float(series.quantile(0.10)), 2),
            "P25": round(float(series.quantile(0.25)), 2),
            "P50": round(float(series.quantile(0.50)), 2),
            "P75": round(float(series.quantile(0.75)), 2),
            "P90": round(float(series.quantile(0.90)), 2),
            "Mean": round(float(series.mean()), 2),
            "Std": round(float(series.std()), 2),
        })

    df_stats = pd.DataFrame(stats_list)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df_stats.to_csv(output_path, index=False)
        logger.info("Saved portfolio statistics to: %s", output_path)

    return df_stats


# ===========================================================================
# 6. Main Orchestrator
# ===========================================================================

def run_profiling_and_stats(
    db_path: Path = DEFAULT_DB_PATH,
    heatmap_png: Path = DEFAULT_HEATMAP_PNG,
    outlier_csv: Path = DEFAULT_OUTLIER_CSV,
    stats_csv: Path = DEFAULT_STATS_CSV,
    cluster_labels_csv: Path = DEFAULT_CLUSTER_LABELS_CSV,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Execute complete Day 37 cluster profiling, correlation, outlier detection, and statistics."""
    # 1. Run KMeans Clustering & Extract Raw Features
    df_clustered, kmeans_model, elbow_data = run_clustering(db_path=db_path, output_csv=cluster_labels_csv)

    # 2. Update cluster labels with agreed descriptive names
    df_clustered["cluster_name"] = df_clustered["cluster_id"].map(CLUSTER_DESCRIPTIVE_NAMES)
    output_clusters = df_clustered[["company_id", "cluster_id", "cluster_name", "distance_from_centroid"]].copy()
    output_clusters.to_csv(cluster_labels_csv, index=False)

    # 3. Cluster Profiling Statistics
    df_profiles = profile_clusters(df_clustered, feature_cols=FEATURE_COLUMNS)

    # 4. Load 10 KPIs
    df_10kpis = load_10_kpis_data(db_path=db_path)

    # 5. Correlation Heatmap
    generate_correlation_heatmap(df_10kpis, output_path=heatmap_png, kpi_cols=KPI_10_COLUMNS)

    # 6. Sector Outlier Detection (|Z| > 3)
    df_outliers = detect_sector_outliers(df_10kpis, metric_cols=KPI_10_COLUMNS, threshold=3.0, output_path=outlier_csv)

    # 7. Portfolio Distribution Statistics
    df_stats = compute_portfolio_stats(df_10kpis, metric_cols=KPI_10_COLUMNS, output_path=stats_csv)

    return df_profiles, df_10kpis, df_outliers, df_stats


# ===========================================================================
# CLI Main
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Day 37 — Cluster Profiling & Financial Statistics.")
    parser.add_argument("--db", type=str, default=str(DEFAULT_DB_PATH), help="Database path.")
    parser.add_argument("--heatmap", type=str, default=str(DEFAULT_HEATMAP_PNG), help="Correlation heatmap path.")
    parser.add_argument("--outliers", type=str, default=str(DEFAULT_OUTLIER_CSV), help="Outlier report CSV path.")
    parser.add_argument("--stats", type=str, default=str(DEFAULT_STATS_CSV), help="Portfolio stats CSV path.")
    args = parser.parse_args()

    print("=" * 75)
    print("Day 37 — Cluster Profiling & Portfolio Statistics Engine")
    print("=" * 75)

    df_prof, df_kpis, df_out, df_stats = run_profiling_and_stats(
        db_path=Path(args.db),
        heatmap_png=Path(args.heatmap),
        outlier_csv=Path(args.outliers),
        stats_csv=Path(args.stats),
    )

    print("\n[1] CLUSTER PROFILES (MEAN & MEDIAN PER CLUSTER):")
    for _, row in df_prof.iterrows():
        print(f"\n  Cluster {row['cluster_id']}: {row['cluster_name']} ({row['company_count']} companies)")
        print(f"    • Sample: {row['sample_companies']}")
        print(f"    • ROE (%):        Mean = {row['return_on_equity_pct_mean']:5.2f}%, Median = {row['return_on_equity_pct_median']:5.2f}%")
        print(f"    • Debt/Equity:    Mean = {row['debt_to_equity_mean']:5.2f}x,  Median = {row['debt_to_equity_median']:5.2f}x")
        print(f"    • Revenue CAGR 5Y:Mean = {row['revenue_cagr_5yr_mean']:5.2f}%, Median = {row['revenue_cagr_5yr_median']:5.2f}%")
        print(f"    • FCF CAGR 5Y:    Mean = {row['fcf_cagr_5yr_mean']:5.2f}%, Median = {row['fcf_cagr_5yr_median']:5.2f}%")
        print(f"    • OPM (%):        Mean = {row['operating_profit_margin_pct_mean']:5.2f}%, Median = {row['operating_profit_margin_pct_median']:5.2f}%")

    print("\n[2] OUTLIER DETECTION (|Z-Score| > 3 by Sector):")
    if not df_out.empty:
        print(df_out[["company_id", "sector", "metric_name", "metric_value", "z_score", "outlier_type"]].to_string(index=False))
    else:
        print("  No extreme outliers (|Z| > 3) found.")

    print("\n[3] PORTFOLIO DISTRIBUTION STATISTICS:")
    print(df_stats[["display_name", "P10", "P25", "P50", "P75", "P90", "Mean", "Std"]].to_string(index=False))

    print("\n[SUCCESS] All Day 37 deliverables generated:")
    print(f"  • Heatmap:  {args.heatmap}")
    print(f"  • Outliers: {args.outliers}")
    print(f"  • Stats:    {args.stats}")


if __name__ == "__main__":
    main()
