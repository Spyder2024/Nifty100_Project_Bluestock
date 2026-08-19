"""
[S5] Day 31 — Cash Flow Intelligence Module
Computes: CFO Quality Score, CapEx Intensity, Distress Signal, Deleveraging Flag
Outputs: output/cashflow_intelligence.xlsx, output/distress_alerts.csv
"""
import sqlite3
import csv
import glob
import sys
import warnings
from pathlib import Path

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# ── ensure UTF-8 output ───────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── resolve project root ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── auto-discover paths ───────────────────────────────────────
DB_CANDIDATES = [
    PROJECT_ROOT / "output" / "nifty100.db",
    PROJECT_ROOT / "data" / "output" / "nifty100.db",
    "output/nifty100.db",
    "data/output/nifty100.db",
    "nifty100.db",
]
CSV_CANDIDATES = [
    PROJECT_ROOT / "data" / "raw" / "cashflow.xlsx",
    PROJECT_ROOT / "data" / "cash_flow.csv",
    "data/raw/cashflow.xlsx",
    "data/cash_flow.csv",
    "cash_flow.csv",
    "output/cash_flow.csv",
]


def _find(paths, pattern=None):
    """Find first existing path, or glob if pattern given."""
    for p in paths:
        if Path(p).exists():
            return Path(p)
    if pattern:
        for f in glob.glob(pattern, recursive=True):
            return Path(f)
    return None


DB_PATH = _find(DB_CANDIDATES)
CF_CSV  = _find(CSV_CANDIDATES, "**/*cash*flow*.xlsx")
OUT_DIR = PROJECT_ROOT / "output"

if not DB_PATH:
    sys.exit("[ERROR] nifty100.db not found.")

# ── column aliases (CSV → canonical) ──────────────────────────
_CF_ALIASES = {
    "operating_activity": "operating_cf",
    "operating_cf": "operating_cf",
    "cash_from_operating_activity": "operating_cf",
    "investing_activity": "investing_cf",
    "investing_cf": "investing_cf",
    "cash_from_investing_activity": "investing_cf",
    "financing_activity": "financing_cf",
    "financing_cf": "financing_cf",
    "cash_from_financing_activity": "financing_cf",
    "net_cash_flow": "net_cash_flow",
    "net_cashflow": "net_cash_flow",
}

# ── load cash flow data ───────────────────────────────────────
def _load_cashflow_csv():
    """Load cash flow data from DB table cash_flow or Excel/CSV source file."""
    # 1. Prefer database table if available & populated
    if DB_PATH and Path(DB_PATH).exists():
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cash_flow'")
            if cur.fetchone():
                df_db = pd.read_sql_query("SELECT * FROM cash_flow", conn)
                conn.close()
                if not df_db.empty and "operating_cf" in df_db.columns and df_db["operating_cf"].notna().any():
                    print(f"[INFO] Loaded {len(df_db)} cash flow rows directly from DB (nifty100.db)")
                    co_col = "company_name" if "company_name" in df_db.columns else "company_id"
                    df_db.rename(columns={co_col: "company_name"}, inplace=True)
                    df_db["company_name"] = df_db["company_name"].astype(str).str.strip()
                    df_db["year"] = df_db["year"].astype(str).str.strip()
                    for c in ("operating_cf", "investing_cf", "financing_cf", "net_cash_flow"):
                        if c in df_db.columns:
                            df_db[c] = pd.to_numeric(df_db[c], errors="coerce")
                    return df_db
            conn.close()
        except Exception as err:
            print(f"[WARN] Error reading cash_flow table from DB: {err}")

    if not CF_CSV:
        sys.exit("[ERROR] cash_flow data source not found.")

    # 2. Fallback to file (.xlsx or .csv)
    str_path = str(CF_CSV).lower()
    if str_path.endswith((".xlsx", ".xls")):
        try:
            preview = pd.read_excel(CF_CSV, nrows=2)
            col0 = str(preview.columns[0]).lower() if len(preview.columns) > 0 else ""
            if "cash flow" in col0:
                df = pd.read_excel(CF_CSV, skiprows=1)
            else:
                df = pd.read_excel(CF_CSV)
        except Exception as err:
            sys.exit(f"[ERROR] Failed to read Excel file {CF_CSV}: {err}")
    else:
        try:
            df = pd.read_csv(CF_CSV)
        except (UnicodeDecodeError, pd.errors.ParserError):
            df = pd.read_excel(CF_CSV, skiprows=1)

    # detect company column
    company_col = None
    for ck in ("company_name", "company_id", "company_", "name", "company"):
        if ck in df.columns:
            company_col = ck
            break
    if company_col is None:
        sys.exit(f"[ERROR] No company column in file. Columns: {list(df.columns)}")

    df.rename(columns={company_col: "company_name"}, inplace=True)

    # rename cash flow columns to canonical names
    rename_map = {}
    for col in df.columns:
        cl = str(col).strip().lower()
        if cl in _CF_ALIASES:
            rename_map[col] = _CF_ALIASES[cl]
    df.rename(columns=rename_map, inplace=True)

    # coerce numeric
    for c in ("operating_cf", "investing_cf", "financing_cf", "net_cash_flow"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df["company_name"] = df["company_name"].astype(str).str.strip()

    # normalize year if module available
    try:
        from src.etl.normaliser import normalize_year
        df["year"] = df["year"].apply(lambda y: normalize_year(str(y)) or str(y).strip())
    except Exception:
        df["year"] = df["year"].astype(str).str.strip()

    return df


# ── load helper data from DB ──────────────────────────────────
def _load_db_data():
    """Load ratios and balance_sheet for cross-referencing."""
    conn = sqlite3.connect(DB_PATH)

    # discover ratios table
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name IN ('ratios','financial_ratios') LIMIT 1"
    )
    row = cur.fetchone()
    ratios_table = row[0] if row else None

    ratios_df = pd.DataFrame()
    if ratios_table:
        ratios_df = pd.read_sql_query(f"SELECT * FROM {ratios_table}", conn)

    # balance_sheet
    bs_df = pd.DataFrame()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='balance_sheet' LIMIT 1"
    )
    if cur.fetchone():
        bs_df = pd.read_sql_query("SELECT * FROM balance_sheet", conn)
        for c in ("borrowings", "total_assets", "reserves"):
            if c in bs_df.columns:
                bs_df[c] = pd.to_numeric(bs_df[c], errors="coerce")

    conn.close()

    # normalize company column and year
    for df in (ratios_df, bs_df):
        if df is not None and not df.empty:
            co_col = "company_name" if "company_name" in df.columns else ("company_id" if "company_id" in df.columns else None)
            if co_col:
                df.rename(columns={co_col: "company_name"}, inplace=True)
                df["company_name"] = df["company_name"].astype(str).str.strip()
            if "year" in df.columns:
                df["year"] = df["year"].astype(str).str.strip()

    return ratios_df, bs_df


# ── safe float ────────────────────────────────────────────────
def _f(val):
    if val is None:
        return None
    try:
        v = float(val)
        return v if np.isfinite(v) else None
    except (ValueError, TypeError):
        return None


# ── KPI computations ──────────────────────────────────────────
def compute_cfo_quality(group):
    """
    CFO Quality Score = mean(operating_cf / PAT) over available years.
    PAT approximated from ratios: if net_profit_margin and revenue available.
    Fallback: label as 'Data Unavailable' if PAT missing.
    """
    ocf_vals = group["operating_cf"].dropna()
    if ocf_vals.empty:
        return None, "Data Unavailable"

    # We need PAT. Check if ratios merged in.
    pat_col = None
    for c in ("net_profit", "pat", "profit_after_tax"):
        if c in group.columns:
            pat_col = c
            break

    if pat_col is None:
        # Try to derive from net_profit_margin * revenue if available
        if "net_profit_margin" in group.columns and "revenue" in group.columns:
            group["_pat"] = group["net_profit_margin"] * group["revenue"] / 100.0
            pat_col = "_pat"
        else:
            # No PAT available — use raw CFO as proxy indicator
            # Score based on CFO trend positivity instead
            ocf_recent = ocf_vals.tail(3).mean()
            ocf_older = ocf_vals.head(3).mean() if len(ocf_vals) > 3 else ocf_recent
            if ocf_recent is None or pd.isna(ocf_recent):
                return None, "Data Unavailable"
            if ocf_recent > 0:
                return round(min(ocf_recent / (abs(ocf_older) + 1), 1.5), 2), "Proxy (no PAT)"
            return round(ocf_recent / (abs(ocf_older) + 1), 2), "Proxy (no PAT)"

    ratios = []
    for _, r in group.iterrows():
        ocf = _f(r.get("operating_cf"))
        pat = _f(r.get(pat_col))
        if ocf is not None and pat is not None and pat != 0:
            ratios.append(ocf / pat)

    if not ratios:
        return None, "Data Unavailable"

    avg_ratio = np.mean(ratios)
    avg_ratio = round(avg_ratio, 2)

    if avg_ratio > 1.0:
        label = "High Quality"
    elif avg_ratio >= 0.5:
        label = "Moderate"
    else:
        label = "Accrual Risk"

    return avg_ratio, label


def compute_capex_intensity(group):
    """
    CapEx Intensity = mean(|investing_cf| / revenue * 100).
    Investing activity is a proxy for capex (negative = cash outflow for investments).
    """
    inv_vals = group["investing_cf"].dropna()
    if inv_vals.empty:
        return None, "Data Unavailable"

    # Try to get revenue
    rev_col = None
    for c in ("revenue", "sales", "net_sales", "total_revenue"):
        if c in group.columns:
            rev_col = c
            break

    if rev_col is None:
        # Use absolute investing_cf magnitude as raw indicator
        avg_abs_inv = inv_vals.abs().mean()
        return round(avg_abs_inv, 2), "No Revenue Data"

    intensities = []
    for _, r in group.iterrows():
        inv = _f(r.get("investing_cf"))
        rev = _f(r.get(rev_col))
        if inv is not None and rev is not None and rev != 0:
            intensities.append(abs(inv) / rev * 100)

    if not intensities:
        return None, "Data Unavailable"

    avg_intensity = round(np.mean(intensities), 2)

    if avg_intensity < 3:
        label = "Asset Light"
    elif avg_intensity <= 8:
        label = "Moderate"
    else:
        label = "Capital Intensive"

    return avg_intensity, label


def check_distress_signal(group):
    """
    Distress Signal: operating_cf < 0 AND financing_cf > 0 in the latest year.
    Means company burning cash from ops and relying on financing to survive.
    """
    latest = group.sort_values("year", ascending=False).head(1)
    if latest.empty:
        return False, "N/A"

    row = latest.iloc[0]
    ocf = _f(row.get("operating_cf"))
    fcf_fin = _f(row.get("financing_cf"))

    if ocf is None or fcf_fin is None:
        return None, "Data Unavailable"

    if ocf < 0 and fcf_fin > 0:
        return True, "ALERT"
    return False, "Healthy"


def check_deleveraging(group, bs_df=None):
    """
    Deleveraging: financing_cf < 0 (paying down debt) AND borrowings declining YoY.
    """
    latest = group.sort_values("year", ascending=False).head(1)
    if latest.empty:
        return None, "N/A"

    row = latest.iloc[0]
    fin_cf = _f(row.get("financing_cf"))
    if fin_cf is None:
        return None, "Data Unavailable"

    if fin_cf >= 0:
        return False, "Not Deleveraging"

    # Check borrowings YoY decline if balance_sheet available
    company = row.get("company_name", "")
    year = row.get("year", "")

    if bs_df is not None and not bs_df.empty and "borrowings" in bs_df.columns:
        co_bs = bs_df[bs_df["company_name"].str.lower() == str(company).lower()]
        if len(co_bs) >= 2:
            co_bs = co_bs.sort_values("year", ascending=False)
            latest_borrow = _f(co_bs.iloc[0].get("borrowings"))
            prev_borrow = _f(co_bs.iloc[1].get("borrowings"))
            if latest_borrow is not None and prev_borrow is not None:
                if latest_borrow < prev_borrow:
                    return True, "Deleveraging"
                return False, "Paying but Borrowings Up"
            return True, "Likely Deleveraging"  # fin_cf < 0 but can't verify

    return True, "Likely Deleveraging (no BS data)"


# ── main ──────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("[S5] Day 31 — Cash Flow Intelligence Module")
    print("=" * 60)

    # Load data
    cf_df = _load_cashflow_csv()
    ratios_df, bs_df = _load_db_data()

    print(f"[INFO] Cash flow CSV : {len(cf_df)} rows")
    print(f"[INFO] Ratios DB     : {len(ratios_df)} rows")
    print(f"[INFO] Balance sheet  : {len(bs_df)} rows")

    # Data availability check
    cf_cols_present = [c for c in ("operating_cf", "investing_cf", "financing_cf")
                       if c in cf_df.columns and cf_df[c].notna().any()]
    print(f"[INFO] Available CF columns: {cf_cols_present}")
    if not cf_cols_present:
        print("[WARN] No cash flow detail columns found — output will have limited data.")
        print("[WARN] Run scripts/fix_cashflow_schema.py first if DB columns are NULL.")

    # Merge ratios for PAT proxy
    if not ratios_df.empty and "company_name" in ratios_df.columns:
        merge_cols = ["company_name", "year"]
        # check for common merge columns
        if "year" in ratios_df.columns:
            # standardize year format
            for df in (cf_df, ratios_df):
                df["year"] = df["year"].astype(str).str.strip()
            cf_df = cf_df.merge(
                ratios_df[["company_name", "year", "net_profit_margin", "roe"] + 
                          [c for c in ratios_df.columns if "revenue" in c.lower() or "sales" in c.lower()]],
                on=merge_cols,
                how="left",
                suffixes=("", "_ratio"),
            )
            print(f"[INFO] Merged ratios -> {len(cf_df)} rows")

    # ── compute KPIs per company ──────────────────────────────
    results = []
    distress_rows = []

    for company, group in cf_df.groupby("company_name"):
        group = group.sort_values("year").copy()
        if len(group) < 1:
            continue

        # CFO Quality
        cfo_score, cfo_label = compute_cfo_quality(group)

        # CapEx Intensity
        capex_int, capex_label = compute_capex_intensity(group)

        # Distress Signal
        is_distress, distress_label = check_distress_signal(group)

        # Deleveraging
        is_delev, delev_label = check_deleveraging(group, bs_df)

        # Latest year metrics
        latest = group.iloc[-1]
        latest_ocf = _f(latest.get("operating_cf"))
        latest_inv = _f(latest.get("investing_cf"))
        latest_fin = _f(latest.get("financing_cf"))
        latest_ncf = _f(latest.get("net_cash_flow"))
        latest_year = latest.get("year", "")

        # 5-year trend of operating CF
        ocf_series = group["operating_cf"].dropna()
        ocf_trend = "N/A"
        if len(ocf_series) >= 2:
            recent_avg = ocf_series.tail(3).mean()
            older_avg = ocf_series.head(max(1, len(ocf_series) - 3)).mean()
            if pd.notna(recent_avg) and pd.notna(older_avg) and older_avg != 0:
                change = (recent_avg - older_avg) / abs(older_avg) * 100
                ocf_trend = f"{'↑' if change > 0 else '↓'} {abs(change):.1f}%"

        row = {
            "company_name": company,
            "latest_year": latest_year,
            "operating_cf": latest_ocf,
            "investing_cf": latest_inv,
            "financing_cf": latest_fin,
            "net_cash_flow": latest_ncf,
            "cfo_quality_score": cfo_score,
            "cfo_quality_label": cfo_label,
            "capex_intensity_pct": capex_int,
            "capex_intensity_label": capex_label,
            "distress_signal": is_distress,
            "distress_label": distress_label,
            "deleveraging_flag": is_delev,
            "deleveraging_label": delev_label,
            "ocf_5yr_trend": ocf_trend,
            "data_years": len(group),
        }
        results.append(row)

        if is_distress is True:
            distress_rows.append({
                "company_name": company,
                "latest_year": latest_year,
                "operating_cf": latest_ocf,
                "financing_cf": latest_fin,
                "signal": "DISTRESS",
                "reason": f"CFO={latest_ocf}, CFF={latest_fin}",
            })

    if not results:
        sys.exit("[ERROR] No results generated. Check data availability.")

    result_df = pd.DataFrame(results)

    # Sort: distress first, then by CFO quality descending
    result_df["_distress_sort"] = result_df["distress_signal"].apply(
        lambda x: 0 if x is True else 1
    )
    result_df = result_df.sort_values(
        ["_distress_sort", "cfo_quality_score"],
        ascending=[True, False],
        na_position="last",
    ).drop(columns=["_distress_sort"]).reset_index(drop=True)

    # ── write outputs ──────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    xlsx_path = OUT_DIR / "cashflow_intelligence.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        result_df.to_excel(writer, sheet_name="Cashflow Intelligence", index=False)

        # Summary sheet
        summary_data = {
            "Metric": [
                "Total Companies",
                "High Quality CFO",
                "Moderate CFO",
                "Accrual Risk",
                "Asset Light",
                "Capital Intensive",
                "Distress Alerts",
                "Deleveraging",
            ],
            "Count": [
                len(result_df),
                len(result_df[result_df["cfo_quality_label"] == "High Quality"]),
                len(result_df[result_df["cfo_quality_label"] == "Moderate"]),
                len(result_df[result_df["cfo_quality_label"] == "Accrual Risk"]),
                len(result_df[result_df["capex_intensity_label"] == "Asset Light"]),
                len(result_df[result_df["capex_intensity_label"] == "Capital Intensive"]),
                len(result_df[result_df["distress_signal"] == True]),
                len(result_df[result_df["deleveraging_flag"] == True]),
            ],
        }
        pd.DataFrame(summary_data).to_excel(
            writer, sheet_name="Summary", index=False
        )

    print(f"\n[OUTPUT] {xlsx_path}")

    # Distress alerts CSV
    if distress_rows:
        distress_df = pd.DataFrame(distress_rows)
        csv_path = OUT_DIR / "distress_alerts.csv"
        distress_df.to_csv(csv_path, index=False)
        print(f"[OUTPUT] {csv_path} ({len(distress_df)} alerts)")
    else:
        print("[INFO] No distress alerts found — all companies healthy on this metric.")

    # ── print summary ─────────────────────────────────────────
    print(f"\n{'─' * 50}")
    print(f"Companies analysed : {len(result_df)}")
    print(f"CFO High Quality   : {len(result_df[result_df['cfo_quality_label'] == 'High Quality'])}")
    print(f"CFO Accrual Risk   : {len(result_df[result_df['cfo_quality_label'] == 'Accrual Risk'])}")
    print(f"Distress Signals   : {len(distress_rows)}")
    print(f"Deleveraging       : {len(result_df[result_df['deleveraging_flag'] == True])}")
    print(f"{'─' * 50}")
    print("[DONE]")


if __name__ == "__main__":
    main()