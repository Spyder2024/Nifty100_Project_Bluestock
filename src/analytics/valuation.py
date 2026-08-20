"""Intrinsic value estimation using multiple valuation models.

Models:
    1. Graham Number       — √(22.5 × EPS × BVPS)
    2. DCF (two-stage)     — FCF-based with net-debt adjustment
    3. DDM (Gordon Growth)  — dividend discount model
    4. Relative Valuation  — sector-median P/E and P/B multiples

Results are persisted to a ``valuation`` SQLite table.

Usage:
    python -m src.analytics.run_valuation --year 2024
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

# ═══════════════════════════════════════════════════════════════════════
#  Constants (Indian-market defaults)
# ═══════════════════════════════════════════════════════════════════════

DEFAULT_WACC = 0.12  # 12 % typical for large-cap Indian equities
DEFAULT_TERMINAL_GROWTH = 0.05  # 5 %  long-term GDP-adjacent
DEFAULT_DDM_RETURN = 0.12
PROJECTION_YEARS = 10
FACE_VALUE = 10.0  # ₹10 standard face value


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════


def _f(val) -> float | None:
    """Coerce *val* to plain Python float or ``None``.

    Shields against PyArrow scalars, pandas NA, and infinity
    that break numpy / math operations.
    """
    if val is None:
        return None
    try:
        v = float(val)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


# ═══════════════════════════════════════════════════════════════════════
#  1. Graham Number
# ═══════════════════════════════════════════════════════════════════════


def graham_number(eps: float | None, bvps: float | None) -> float | None:
    """Graham Number = √(22.5 × EPS × BVPS).

    Both inputs must be strictly positive.
    """
    eps, bvps = _f(eps), _f(bvps)
    if eps is None or bvps is None or eps <= 0 or bvps <= 0:
        return None
    return round(float(np.sqrt(22.5 * eps * bvps)), 2)


# ═══════════════════════════════════════════════════════════════════════
#  2. DCF (two-stage, FCF-based)
# ═══════════════════════════════════════════════════════════════════════


def _empty_dcf() -> dict:
    return {
        "enterprise_value": None,
        "pv_of_fcfs": None,
        "pv_of_terminal": None,
        "equity_value": None,
        "intrinsic_value_per_share": None,
    }


def dcf_valuation(
    fcf: float | None,
    growth_rate: float,
    net_debt: float | None = None,
    total_shares: float | None = None,
    wacc: float = DEFAULT_WACC,
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
    years: int = PROJECTION_YEARS,
) -> dict:
    """Two-stage DCF: projected FCFs → terminal value → equity value.

    Stage 1 projects FCF forward with growth linearly decaying
    from *growth_rate* to *terminal_growth*.
    Stage 2 applies Gordon Growth for the terminal value.
    Net debt is subtracted to arrive at equity value.
    """
    fcf = _f(fcf)
    if fcf is None or fcf <= 0:
        return _empty_dcf()

    # Clamp growth so it stays strictly below WACC
    g = max(min(growth_rate, wacc - 0.01), terminal_growth)

    # Stage 1: projected FCFs with decaying growth
    pv_fcfs = 0.0
    for yr in range(1, years + 1):
        t = yr / years
        yr_g = g * (1 - t) + terminal_growth * t
        proj_fcf = fcf * (1 + yr_g)
        pv_fcfs += proj_fcf / ((1 + wacc) ** yr)

    # Stage 2: terminal value (Gordon Growth)
    denom = wacc - terminal_growth
    pv_terminal = 0.0
    if denom > 0:
        terminal_fcf = fcf * (1 + terminal_growth)
        tv = terminal_fcf / denom
        pv_terminal = tv / ((1 + wacc) ** years)

    ev = pv_fcfs + pv_terminal
    nd = _f(net_debt)
    equity = ev - (nd if nd is not None else 0.0)

    result = {
        "enterprise_value": round(ev, 2),
        "pv_of_fcfs": round(pv_fcfs, 2),
        "pv_of_terminal": round(pv_terminal, 2),
        "equity_value": round(equity, 2),
        "intrinsic_value_per_share": None,
    }

    ts = _f(total_shares)
    if ts is not None and ts > 0:
        result["intrinsic_value_per_share"] = round(equity / ts, 2)

    return result


# ═══════════════════════════════════════════════════════════════════════
#  3. DDM (Gordon Growth Model)
# ═══════════════════════════════════════════════════════════════════════


def ddm_valuation(
    dps: float | None,
    growth_rate: float,
    required_return: float = DEFAULT_DDM_RETURN,
) -> float | None:
    """V = DPS × (1 + g) / (r − g)."""
    dps = _f(dps)
    if dps is None or dps <= 0:
        return None
    denom = required_return - growth_rate
    if denom <= 0:
        return None
    return round(dps * (1 + growth_rate) / denom, 2)


# ═══════════════════════════════════════════════════════════════════════
#  4. Relative Valuation (sector-median multiples)
# ═══════════════════════════════════════════════════════════════════════


def relative_valuation(
    eps: float | None,
    bvps: float | None,
    sector_median_pe: float | None,
    sector_median_pb: float | None,
) -> dict:
    """Intrinsic value from sector-median P/E and P/B multiples."""
    eps, bvps = _f(eps), _f(bvps)
    s_pe, s_pb = _f(sector_median_pe), _f(sector_median_pb)

    pe_val = None
    pb_val = None

    if eps is not None and eps > 0 and s_pe is not None and s_pe > 0:
        pe_val = round(eps * s_pe, 2)

    if bvps is not None and bvps > 0 and s_pb is not None and s_pb > 0:
        pb_val = round(bvps * s_pb, 2)

    vals = [v for v in (pe_val, pb_val) if v is not None]
    avg = round(float(np.mean(vals)), 2) if vals else None

    return {
        "pe_based_value": pe_val,
        "pb_based_value": pb_val,
        "average_relative_value": avg,
    }


# ═══════════════════════════════════════════════════════════════════════
#  DB layer
# ═══════════════════════════════════════════════════════════════════════


def create_valuation_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS valuation (
            company_id              TEXT    NOT NULL,
            year                    TEXT,
            graham_number           REAL,
            dcf_intrinsic_value     REAL,
            ddm_intrinsic_value     REAL,
            relative_pe_value       REAL,
            relative_pb_value       REAL,
            relative_avg_value      REAL,
            sector_median_pe        REAL,
            sector_median_pb        REAL,
            fcf_used                REAL,
            growth_rate_used        REAL,
            wacc_used               REAL,
            eps_used                REAL,
            bvps_used               REAL,
            PRIMARY KEY (company_id, year)
        );
    """)
    conn.commit()


VALUATION_WRITE_COLS = [
    "company_id",
    "year",
    "graham_number",
    "dcf_intrinsic_value",
    "ddm_intrinsic_value",
    "relative_pe_value",
    "relative_pb_value",
    "relative_avg_value",
    "sector_median_pe",
    "sector_median_pb",
    "fcf_used",
    "growth_rate_used",
    "wacc_used",
    "eps_used",
    "bvps_used",
]


def compute_all_valuations(
    conn: sqlite3.Connection,
    year: str | None = None,
    wacc: float = DEFAULT_WACC,
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
) -> int:
    """Compute valuations for every company (optionally for one year).

    Returns the number of rows written to the ``valuation`` table.
    """
    # ── Pick the right ratios table ─────────────────────────────────
    has_fr = bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE name='financial_ratios' AND type='table'"
        ).fetchone()
    )

    if has_fr:
        ratio_tbl = "financial_ratios"
        fr_cols = (
            "company_id, company_name, year, pe_ratio, price_to_book, "
            "book_value_per_share, dividend_payout, "
            "revenue_cagr_5yr, net_profit_cagr_5yr, broad_sector"
        )
    else:
        ratio_tbl = "ratios"
        fr_cols = (
            "company_id, year, pe_ratio, price_to_book, "
            "book_value_per_share, dividend_payout, "
            "revenue_cagr_5yr, net_profit_cagr_5yr"
        )

    # ── Build joined dataset ─────────────────────────────────────────
    query = f"""
        SELECT
            fr.{fr_cols.replace('company_id, ', '').split(',')[0].strip()},
            fr.*
        FROM {ratio_tbl} fr
    """
    # Simpler approach — just SELECT * and work with available columns
    query = f"SELECT * FROM {ratio_tbl}"
    params: list = []
    if year:
        query += " WHERE year LIKE ?"
        params.append(f"{year}%")
    query += " ORDER BY company_id, year"

    fr = pd.read_sql_query(query, conn, params=params)
    if fr.empty:
        return 0

    # ── Sector medians (only if broad_sector column exists) ──────────
    sector_med_df = pd.DataFrame()
    if "broad_sector" in fr.columns:
        sector_med_df = (
            fr.groupby(["year", "broad_sector"])
            .agg(
                sector_median_pe=("pe_ratio", "median"),
                sector_median_pb=("price_to_book", "median"),
            )
            .reset_index()
        )

    # ── Load auxiliary tables per company (for shares & net debt) ───
    # We collect balance-sheet data to compute shares and net debt
    bs_all = pd.read_sql_query("SELECT * FROM balance_sheet", conn)
    cf_all = pd.read_sql_query(
        "SELECT company_id, year, fcf, dividend_paid, "
        "operating_cf, capex FROM cash_flow",
        conn,
    )

    records: list[dict] = []

    for _, row in fr.iterrows():
        ticker = str(row["company_id"])
        yr = str(row.get("year", ""))

        # ── Get balance-sheet for this company (latest year) ───────
        co_bs = bs_all[bs_all["company_id"] == ticker].copy()
        if co_bs.empty:
            shares = None
            net_debt = None
        else:
            latest_bs = co_bs.iloc[-1]
            sc = _f(latest_bs.get("share_capital"))
            shares = (sc / FACE_VALUE) if (sc and sc > 0) else None

            borrowings = _f(latest_bs.get("borrowings")) or 0.0
            cash = _f(latest_bs.get("cash_and_equiv")) or 0.0
            net_debt = borrowings - cash

        # ── Get cash-flow for this company (latest year FCF + DPS) ─
        co_cf = cf_all[cf_all["company_id"] == ticker].copy()
        fcf_val = None
        dividend_raw = None
        if not co_cf.empty:
            latest_cf = co_cf.iloc[-1]
            fcf_val = _f(latest_cf.get("fcf"))
            # dividend_paid is typically a negative outflow
            dividend_raw = _f(latest_cf.get("dividend_paid"))
            if dividend_raw is not None:
                dividend_raw = abs(dividend_raw)

        # ── Get income-statement for EPS ─────────────────────────────
        eps = None
        try:
            is_row = conn.execute(
                "SELECT eps FROM income_statement "
                "WHERE company_id = ? ORDER BY year DESC LIMIT 1",
                (ticker,),
            ).fetchone()
            if is_row:
                eps = _f(is_row[0])
        except Exception:
            pass

        # ── Growth rate (prefer revenue CAGR, else PAT CAGR) ────────
        growth = _f(row.get("revenue_cagr_5yr"))
        if growth is None:
            growth = _f(row.get("net_profit_cagr_5yr"))
        if growth is None:
            growth = 8.0
        growth_decimal = growth / 100.0

        # ── DPS estimation ───────────────────────────────────────────
        dps = None
        if dividend_raw and dividend_raw > 0 and shares and shares > 0:
            dps = dividend_raw / shares

        # ── Sector medians for this row ──────────────────────────────
        s_pe = None
        s_pb = None
        if not sector_med_df.empty and "broad_sector" in row.index:
            bs_val = row.get("broad_sector")
            if pd.notna(bs_val):
                match = sector_med_df[
                    (sector_med_df["year"] == yr)
                    & (sector_med_df["broad_sector"] == bs_val)
                ]
                if not match.empty:
                    s_pe = _f(match.iloc[0].get("sector_median_pe"))
                    s_pb = _f(match.iloc[0].get("sector_median_pb"))

        # ── Compute all four models ──────────────────────────────────
        bvps = _f(row.get("book_value_per_share"))

        gn = graham_number(eps, bvps)

        dcf = dcf_valuation(
            fcf=fcf_val,
            growth_rate=growth_decimal,
            net_debt=net_debt,
            total_shares=shares,
            wacc=wacc,
            terminal_growth=terminal_growth,
        )

        ddm = ddm_valuation(dps, growth_decimal)

        rel = relative_valuation(eps, bvps, s_pe, s_pb)

        records.append(
            {
                "company_id": ticker,
                "year": yr,
                "graham_number": gn,
                "dcf_intrinsic_value": dcf["intrinsic_value_per_share"],
                "ddm_intrinsic_value": ddm,
                "relative_pe_value": rel["pe_based_value"],
                "relative_pb_value": rel["pb_based_value"],
                "relative_avg_value": rel["average_relative_value"],
                "sector_median_pe": s_pe,
                "sector_median_pb": s_pb,
                "fcf_used": fcf_val,
                "growth_rate_used": round(growth_decimal * 100, 2),
                "wacc_used": wacc,
                "eps_used": eps,
                "bvps_used": bvps,
            }
        )

    # ── Persist ────────────────────────────────────────────────────
    create_valuation_table(conn)

    if year:
        conn.execute("DELETE FROM valuation WHERE year LIKE ?", (f"{year}%",))
    else:
        conn.execute("DELETE FROM valuation")

    val_df = pd.DataFrame(records)
    write_cols = [c for c in VALUATION_WRITE_COLS if c in val_df.columns]
    val_df[write_cols].to_sql("valuation", conn, if_exists="append", index=False)
    conn.commit()

    return len(val_df)


# ═══════════════════════════════════════════════════════════════════════
#  Query helpers
# ═══════════════════════════════════════════════════════════════════════


def load_valuations(
    conn: sqlite3.Connection,
    company_id: str | None = None,
    year: str | None = None,
) -> pd.DataFrame:
    """Read the ``valuation`` table with optional filters."""
    clauses: list[str] = []
    params: list = []

    if company_id is not None:
        clauses.append("company_id = ?")
        params.append(company_id)
    if year is not None:
        clauses.append("year LIKE ?")
        params.append(f"{year}%")

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return pd.read_sql_query(
        f"SELECT * FROM valuation{where} ORDER BY company_id, year",
        conn,
        params=params,
    )
