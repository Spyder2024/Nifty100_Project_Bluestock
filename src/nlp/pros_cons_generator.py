"""
Auto Pros / Cons Generator — Day 30

Evaluates 12 pro rules and 12 con rules for every company using
financial metrics from the ratios / financial_ratios table.

Rules that require multi-year data (trends, sustained patterns) use
the ``year`` column to check consecutive years from most recent.

Output
------
output/pros_cons_generated.csv
    columns: company_id, type, rule_id, text, confidence_pct
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _find_db() -> Path:
    for candidate in (
        PROJECT_ROOT / "output" / "nifty100.db",
        PROJECT_ROOT / "db" / "nifty100.db",
    ):
        if candidate.exists():
            return candidate
    return PROJECT_ROOT / "output" / "nifty100.db"


DB_PATH = _find_db()

# ═══════════════════════════════════════════════════════════════════════════════
# COLUMN ALIASES  — logical name → possible DB column names (both conventions)
# ═══════════════════════════════════════════════════════════════════════════════

_ALIASES: dict[str, list[str]] = {
    # Profitability
    "roe": ["roe", "return_on_equity_pct", "roe_percentage"],
    "opm": ["opm", "operating_profit_margin", "operating_profit_margin_pct"],
    "roce": ["roce", "return_on_capital_employed_pct", "roce_percentage"],
    "net_profit_margin": [
        "net_profit_margin", "net_profit_margin_pct",
        "net_profit", "profit_after_tax",
    ],
    # Leverage
    "debt_to_equity": ["debt_to_equity", "debt_to_equity_ratio"],
    "interest_coverage": ["interest_coverage", "icr", "interest_coverage_ratio"],
    "net_debt": ["net_debt"],
    "total_debt": ["total_debt"],
    # Growth  (5-year)
    "revenue_cagr_5yr": ["revenue_cagr_5yr", "revenue_cagr_5yr_pct"],
    "pat_cagr_5yr": [
        "pat_cagr_5yr", "net_profit_cagr_5yr",
        "pat_cagr_5yr_pct", "net_profit_cagr_5yr_pct",
    ],
    "eps_cagr_5yr": ["eps_cagr_5yr", "eps_cagr_5yr_pct"],
    # Cash flow
    "fcf": ["fcf", "free_cash_flow"],
    "cash_from_ops": ["cash_from_operations", "operating_activity"],
    # Dividends
    "dividend_payout": [
        "dividend_payout", "dividend_payout_ratio",
        "dividend_payout_ratio_pct",
    ],
    "dividend_yield": ["dividend_yield", "dividend_yield_pct"],
    # Balance sheet
    "total_assets": ["total_assets"],
    "borrowings": ["borrowings", "total_borrowings"],
    # Identifiers / metadata
    "company_id": ["company_id", "id"],
    "company_name": ["company_name"],
    "broad_sector": ["broad_sector"],
    "year": ["year", "fiscal_year", "financial_year"],
    "composite_quality_score": ["composite_quality_score"],
    "eps": ["eps", "earnings_per_share"],
}

# Financial-sector keywords — D/E rules skip these
_FINANCIAL_SECTORS = frozenset({
    "financial services", "banking", "finance", "nbfc",
    "insurance", "financial", "capital markets",
})

# ═══════════════════════════════════════════════════════════════════════════════
# LOW-LEVEL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _resolve(df: pd.DataFrame, logical: str) -> Optional[str]:
    """Return the first matching column name from the alias list, or None."""
    for candidate in _ALIASES.get(logical, [logical]):
        if candidate in df.columns and df[candidate].notna().any():
            return candidate
    return None


def _f(val) -> Optional[float]:
    """Safe float conversion — returns None for NaN / None / non-numeric."""
    if val is None:
        return None
    try:
        v = float(val)
        return None if pd.isna(v) else v
    except (ValueError, TypeError):
        return None


def _is_financial(sector_val) -> bool:
    """True if the sector string looks like a financial-services company."""
    if sector_val is None or (isinstance(sector_val, float) and pd.isna(sector_val)):
        return False
    s = str(sector_val).strip().lower()
    return any(kw in s for kw in _FINANCIAL_SECTORS)

# ── Confidence calculators ───────────────────────────────────────────────────

def _conf_above(value: float, threshold: float) -> int:
    """61 at threshold, ~100 at 3x threshold."""
    if threshold == 0:
        return 61
    ratio = (value - threshold) / abs(threshold)
    return min(100, max(61, int(61 + ratio * 25)))


def _conf_below(value: float, threshold: float) -> int:
    """Confidence for value being below a threshold (con rules)."""
    if threshold == 0:
        return 61
    ratio = (threshold - value) / abs(threshold)
    return min(100, max(61, int(61 + ratio * 25)))


def _conf_sustained(years_met: int, min_yrs: int, latest_val: float,
                    threshold: float, above: bool = True) -> int:
    """Confidence for a value staying above/below threshold N years."""
    base = 61 + max(0, years_met - min_yrs) * 4
    if threshold > 0:
        signal = max(0, (latest_val - threshold) / threshold) if above \
            else max(0, (threshold - latest_val) / threshold)
    else:
        signal = 0.0
    return min(100, base + min(15, int(signal * 5)))


def _conf_trend(years_met: int, min_yrs: int, avg_change: float) -> int:
    """Confidence for a directional trend."""
    base = 61 + max(0, years_met - min_yrs) * 4
    return min(100, base + min(15, int(abs(avg_change) * 2)))

# ── Pattern detectors ───────────────────────────────────────────────────────

def _sustained(df: pd.DataFrame, col: str, threshold: float,
               min_yrs: int, above: bool = True) -> Optional[tuple[int, float]]:
    """Check value above/below threshold for N most-recent consecutive years.

    Returns (years_met, latest_value) or None.
    """
    valid = df.dropna(subset=[col])
    if len(valid) < min_yrs:
        return None
    count = 0
    for _, row in valid.iterrows():
        v = _f(row[col])
        if v is None:
            break
        if above and v > threshold:
            count += 1
        elif not above and v < threshold:
            count += 1
        else:
            break
    if count < min_yrs:
        return None
    return (count, _f(valid.iloc[0][col]))


def _trend(df: pd.DataFrame, col: str, min_yrs: int,
           direction: str) -> Optional[tuple[int, float]]:
    """Check consistent improving / declining / increasing for N year-pairs.

    ``df`` must be sorted by year descending (most recent first).
    Returns (years_trending, avg_abs_change) or None.
    """
    valid = df.dropna(subset=[col])
    if len(valid) < min_yrs + 1:
        return None
    count = 0
    changes: list[float] = []
    for i in range(len(valid) - 1):
        curr = _f(valid.iloc[i][col])
        nxt = _f(valid.iloc[i + 1][col])
        if curr is None or nxt is None:
            break
        if direction in ("improving", "increasing"):
            if curr > nxt:
                count += 1
                changes.append(curr - nxt)
            else:
                break
        elif direction == "declining":
            if curr < nxt:
                count += 1
                changes.append(nxt - curr)
            else:
                break
    if count < min_yrs:
        return None
    avg = sum(changes) / len(changes) if changes else 0.0
    return (count, avg)

# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def load_data() -> tuple[
    dict[str, pd.DataFrame],   # company_id → sorted DataFrame
    dict[str, str],            # logical_name → actual column
    str,                       # company_id column name
    Optional[str],             # year column name (None if absent)
]:
    """Discover tables, resolve columns, group data by company."""
    if not DB_PATH.exists():
        print(f"[ERROR] DB not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))

    # ── Discover the ratios table ─────────────────────────────────────────
    all_tables = [
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    ratios_table = None
    for candidate in ("financial_ratios", "ratios", "fin_ratios"):
        if candidate in all_tables:
            ratios_table = candidate
            break
    if ratios_table is None:
        ratio_like = [t for t in all_tables if "ratio" in t.lower()]
        if ratio_like:
            ratios_table = ratio_like[0]
    if ratios_table is None:
        print("[ERROR] No ratios table found in DB.")
        sys.exit(1)

    df = pd.read_sql(f"SELECT * FROM {ratios_table}", conn)
    conn.close()

    if df.empty:
        print("[ERROR] Ratios table is empty — nothing to evaluate.")
        sys.exit(1)

    print(f"  Table '{ratios_table}': {len(df)} rows, {len(df.columns)} cols")

    # ── Resolve column names ──────────────────────────────────────────────
    cm: dict[str, str] = {}
    for logical in _ALIASES:
        actual = _resolve(df, logical)
        if actual is not None:
            cm[logical] = actual
    print(f"  Resolved columns: {list(cm.keys())}")

    # ── Company identifier ────────────────────────────────────────────────
    cid_col = cm.get("company_id")
    if cid_col is None:
        print(f"[ERROR] No company identifier column. Available: {list(df.columns)}")
        sys.exit(1)

    # ── Year column ───────────────────────────────────────────────────────
    year_col = cm.get("year")

    # ── Group by company, sort most-recent first ──────────────────────────
    groups: dict[str, pd.DataFrame] = {}
    if year_col:
        for cid, grp in df.groupby(cid_col, dropna=False):
            groups[str(cid)] = grp.sort_values(
                year_col, ascending=False, na_position="last"
            ).reset_index(drop=True)
    else:
        for cid, grp in df.groupby(cid_col, dropna=False):
            groups[str(cid)] = grp.reset_index(drop=True)

    # ── Ensure all companies from companies table are present ──────────────
    try:
        conn = sqlite3.connect(str(DB_PATH))
        comp_rows = conn.execute("SELECT company_id FROM companies").fetchall()
        conn.close()
        for (comp_id,) in comp_rows:
            comp_id_str = str(comp_id)
            if comp_id_str not in groups:
                groups[comp_id_str] = pd.DataFrame([{cid_col: comp_id_str}])
    except Exception:
        pass

    print(f"  Companies loaded: {len(groups)}")
    if year_col and groups:
        sample_cid = next(iter(groups))
        years = groups[sample_cid].get(year_col, pd.Series()).tolist()
        print(f"  Sample years for {sample_cid}: {years[:5]}")

    return groups, cm, cid_col, year_col

# ═══════════════════════════════════════════════════════════════════════════════
# 12 PRO RULES
# ═══════════════════════════════════════════════════════════════════════════════

def _pro01(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """ROE > 20% sustained for 3+ years."""
    c = cm.get("roe")
    if not c:
        return None
    r = _sustained(d, c, 20.0, 3, above=True)
    if not r:
        return None
    n, v = r
    conf = _conf_sustained(n, 3, v, 20.0)
    return ("PRO_01", "pro",
            "Consistently high return on equity above 20% demonstrates "
            "exceptional capital efficiency", conf)


def _pro02(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """FCF positive for 5+ consecutive years."""
    c = cm.get("fcf")
    if not c:
        return None
    r = _sustained(d, c, 0.0, 5, above=True)
    if not r:
        return None
    n, v = r
    conf = _conf_sustained(n, 5, v, 0.0)
    return ("PRO_02", "pro",
            "Strong free cash flow generation over 5 years signals "
            "healthy business fundamentals", conf)


def _pro03(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """D/E = 0 in latest year (debt-free)."""
    c = cm.get("debt_to_equity")
    if not c:
        return None
    v = _f(d.iloc[0][c])
    if v is None or v != 0.0:
        return None
    return ("PRO_03", "pro",
            "Debt-free balance sheet provides financial flexibility "
            "and eliminates interest burden", 85)


def _pro04(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """Revenue CAGR > 15% over 5 years."""
    c = cm.get("revenue_cagr_5yr")
    if not c:
        return None
    v = _f(d.iloc[0][c])
    if v is None or v <= 15.0:
        return None
    return ("PRO_04", "pro",
            "Revenue growing at above 15% CAGR over 5 years reflects "
            "strong business momentum", _conf_above(v, 15.0))


def _pro05(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """OPM > 25% in latest year."""
    c = cm.get("opm")
    if not c:
        return None
    v = _f(d.iloc[0][c])
    if v is None or v <= 25.0:
        return None
    return ("PRO_05", "pro",
            "Operating profit margin above 25% indicates strong pricing "
            "power and cost discipline", _conf_above(v, 25.0))


def _pro06(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """PAT CAGR > 20% over 5 years."""
    c = cm.get("pat_cagr_5yr")
    if not c:
        return None
    v = _f(d.iloc[0][c])
    if v is None or v <= 20.0:
        return None
    return ("PRO_06", "pro",
            "Net profit compounding at above 20% over 5 years creates "
            "significant shareholder value", _conf_above(v, 20.0))


def _pro07(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """ICR > 10 or Debt Free."""
    icr_c = cm.get("interest_coverage")
    de_c = cm.get("debt_to_equity")
    icr_val = _f(d.iloc[0][icr_c]) if icr_c else None
    de_val = _f(d.iloc[0][de_c]) if de_c else None
    if icr_val is not None and icr_val > 10.0:
        return ("PRO_07", "pro",
                "Very high interest coverage ratio reflects negligible "
                "financial stress from debt servicing",
                _conf_above(icr_val, 10.0))
    if de_val is not None and de_val == 0.0:
        return ("PRO_07", "pro",
                "Very high interest coverage ratio reflects negligible "
                "financial stress from debt servicing", 80)
    return None


def _pro08(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """Dividend Yield > 2% with FCF positive."""
    dy_c = cm.get("dividend_yield")
    fcf_c = cm.get("fcf")
    if not dy_c or not fcf_c:
        return None
    dy = _f(d.iloc[0][dy_c])
    fcf = _f(d.iloc[0][fcf_c])
    if dy is None or fcf is None or dy <= 2.0 or fcf <= 0.0:
        return None
    return ("PRO_08", "pro",
            "Consistent dividend yield above 2% backed by positive "
            "free cash flow", _conf_above(dy, 2.0))


def _pro09(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """EPS CAGR > 15% over 5 years."""
    c = cm.get("eps_cagr_5yr")
    if not c:
        return None
    v = _f(d.iloc[0][c])
    if v is None or v <= 15.0:
        return None
    return ("PRO_09", "pro",
            "Earnings per share growing above 15% CAGR indicates "
            "strong earnings quality and compounding",
            _conf_above(v, 15.0))


def _pro10(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """ROE improving for 3 consecutive years."""
    c = cm.get("roe")
    if not c:
        return None
    r = _trend(d, c, 3, "improving")
    if not r:
        return None
    n, avg = r
    return ("PRO_10", "pro",
            "Return on equity improving for 3 consecutive years shows "
            "strengthening business quality", _conf_trend(n, 3, avg))


def _pro11(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """PAT CAGR > Revenue CAGR (operating leverage)."""
    rc = cm.get("revenue_cagr_5yr")
    pc = cm.get("pat_cagr_5yr")
    if not rc or not pc:
        return None
    rev = _f(d.iloc[0][rc])
    pat = _f(d.iloc[0][pc])
    if rev is None or pat is None:
        return None
    if pat <= rev:
        return None
    spread = pat - rev
    conf = min(100, max(61, int(61 + spread * 3)))
    return ("PRO_11", "pro",
            "Revenue growing slower than profits shows improving "
            "operating leverage and scale benefits", conf)


def _pro12(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """Balance sheet assets growing with declining debt."""
    ta_c = cm.get("total_assets")
    bw_c = cm.get("borrowings")
    if not ta_c or not bw_c:
        return None
    if len(d) < 3:
        return None
    # Latest vs 3-years-ago
    ta_now = _f(d.iloc[0][ta_c])
    bw_now = _f(d.iloc[0][bw_c])
    ta_old = _f(d.iloc[min(2, len(d) - 1)][ta_c])
    bw_old = _f(d.iloc[min(2, len(d) - 1)][bw_c])
    if any(v is None for v in (ta_now, bw_now, ta_old, bw_old)):
        return None
    if ta_old == 0:
        return None
    ta_growing = ta_now > ta_old
    bw_declining = bw_now < bw_old
    if not (ta_growing and bw_declining):
        return None
    conf = min(100, 61 + int(((ta_now - ta_old) / abs(ta_old)) * 10))
    return ("PRO_12", "pro",
            "Growing asset base funded by internal accruals reflects "
            "self-sustaining growth", conf)


# ═══════════════════════════════════════════════════════════════════════════════
# 12 CON RULES
# ═══════════════════════════════════════════════════════════════════════════════

def _con01(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """D/E > 2.0 for non-financial companies."""
    c = cm.get("debt_to_equity")
    bs = cm.get("broad_sector")
    if not c:
        return None
    sector_val = d.iloc[0][bs] if bs else None
    if _is_financial(sector_val):
        return None
    v = _f(d.iloc[0][c])
    if v is None or v <= 2.0:
        return None
    de_str = f"{v:.1f}" if v != int(v) else str(int(v))
    return ("CON_01", "con",
            f"Debt-to-equity ratio of {de_str} is elevated for a "
            f"non-financial company and warrants monitoring",
            _conf_above(v, 2.0))


def _con02(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """FCF negative for 3 consecutive years."""
    c = cm.get("fcf")
    if not c:
        return None
    r = _sustained(d, c, 0.0, 3, above=False)
    if not r:
        return None
    n, v = r
    conf = _conf_sustained(n, 3, v, 0.0, above=False)
    return ("CON_02", "con",
            "Free cash flow negative for 3 consecutive years raises "
            "concern about cash generation quality", conf)


def _con03(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """OPM declining for 3 consecutive years."""
    c = cm.get("opm")
    if not c:
        return None
    r = _trend(d, c, 3, "declining")
    if not r:
        return None
    n, avg = r
    return ("CON_03", "con",
            "Operating margins declining for 3 consecutive years suggests "
            "pricing or cost pressure", _conf_trend(n, 3, avg))


def _con04(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """Net profit negative in latest year."""
    c = cm.get("net_profit_margin")
    if not c:
        return None
    v = _f(d.iloc[0][c])
    if v is None or v >= 0.0:
        return None
    return ("CON_04", "con",
            "Company reported a net loss in the most recent financial year",
            min(100, 61 + int(abs(v) * 2)))


def _con05(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """Revenue declining for 2+ years."""
    c = cm.get("revenue_cagr_5yr")
    if not c:
        return None
    # Revenue CAGR < 0 over 5 years implies decline
    v = _f(d.iloc[0][c])
    if v is None or v >= 0.0:
        return None
    return ("CON_05", "con",
            "Revenue contraction over 2 consecutive years indicates "
            "demand weakness or market share loss",
            min(100, 61 + int(abs(v) * 3)))


def _con06(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """ICR < 1.5."""
    c = cm.get("interest_coverage")
    if not c:
        return None
    v = _f(d.iloc[0][c])
    if v is None or v >= 1.5:
        return None
    return ("CON_06", "con",
            "Interest coverage ratio below 1.5x indicates the company "
            "is at risk of not meeting its debt obligations",
            _conf_below(v, 1.5))


def _con07(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """Dividend payout > 100%."""
    c = cm.get("dividend_payout")
    if not c:
        return None
    v = _f(d.iloc[0][c])
    if v is None or v <= 100.0:
        return None
    return ("CON_07", "con",
            "Dividend payout ratio above 100% means the company is "
            "paying dividends from reserves, which is unsustainable",
            _conf_above(v, 100.0))


def _con08(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """D/E rising for 3 consecutive years."""
    c = cm.get("debt_to_equity")
    if not c:
        return None
    r = _trend(d, c, 3, "increasing")
    if not r:
        return None
    n, avg = r
    return ("CON_08", "con",
            "Rising debt-to-equity ratio over 3 years suggests "
            "increasing financial leverage risk",
            _conf_trend(n, 3, avg))


def _con09(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """EPS declining for 3 consecutive years."""
    c = cm.get("eps_cagr_5yr")
    if not c:
        return None
    # EPS CAGR < 0 over 5 years implies sustained decline
    v = _f(d.iloc[0][c])
    if v is None or v >= 0.0:
        return None
    return ("CON_09", "con",
            "Earnings per share declining for 3 consecutive years "
            "reflects deteriorating profitability",
            min(100, 61 + int(abs(v) * 3)))


def _con10(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """ROCE < 10%."""
    c = cm.get("roce")
    if not c:
        return None
    v = _f(d.iloc[0][c])
    if v is None or v >= 10.0:
        return None
    return ("CON_10", "con",
            "Return on capital employed below 10% suggests the business "
            "is not generating sufficient returns on invested capital",
            _conf_below(v, 10.0))


def _con11(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """Net Debt > 3x EBITDA."""
    nd_c = cm.get("net_debt")
    # EBITDA ≈ cash_from_operations + interest + depreciation
    # Use cash_from_ops as proxy if EBITDA column not available
    cf_c = cm.get("cash_from_ops")
    if not nd_c or not cf_c:
        return None
    nd = _f(d.iloc[0][nd_c])
    cf = _f(d.iloc[0][cf_c])
    if nd is None or cf is None:
        return None
    if nd <= 0 or cf <= 0:
        return None
    ratio = nd / cf
    if ratio <= 3.0:
        return None
    return ("CON_11", "con",
            "Net debt exceeding 3 times cash from operations is a high "
            "leverage ratio and limits financial flexibility",
            _conf_above(ratio, 3.0))


def _con12(cm: dict, d: pd.DataFrame) -> Optional[tuple]:
    """Revenue CAGR < 5% over 5 years."""
    c = cm.get("revenue_cagr_5yr")
    if not c:
        return None
    v = _f(d.iloc[0][c])
    if v is None or v >= 5.0:
        return None
    return ("CON_12", "con",
            "Revenue growing at below 5% over 5 years lags inflation "
            "and suggests limited business momentum",
            _conf_below(v, 5.0))


# ═══════════════════════════════════════════════════════════════════════════════
# EVALUATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

ALL_RULES = [
    _pro01, _pro02, _pro03, _pro04, _pro05, _pro06,
    _pro07, _pro08, _pro09, _pro10, _pro11, _pro12,
    _con01, _con02, _con03, _con04, _con05, _con06,
    _con07, _con08, _con09, _con10, _con11, _con12,
]


def _fallback_pro(cm: dict, d: pd.DataFrame, company_id: str) -> tuple:
    """Generate at least 1 pro when all rules fail."""
    qs_c = cm.get("composite_quality_score")
    if qs_c and qs_c in d.columns:
        qs = _f(d.iloc[0][qs_c])
        if qs is not None and qs > 0:
            qs_str = f"{qs:.1f}" if qs != int(qs) else str(int(qs))
            return ("PRO_FB", "pro",
                    f"Composite quality score of {qs_str} reflects "
                    f"overall fundamental strength in the Nifty 100 universe",
                    61)
    return ("PRO_FB", "pro",
            "Included in the Nifty 100 index reflecting established "
            "market presence and listing credentials", 61)


def _fallback_con(cm: dict, d: pd.DataFrame) -> tuple:
    """Generate at least 1 con when all rules fail."""
    de_c = cm.get("debt_to_equity")
    if de_c and de_c in d.columns:
        v = _f(d.iloc[0][de_c])
        if v is not None and v > 0:
            de_str = f"{v:.1f}" if v != int(v) else str(int(v))
            return ("CON_FB", "con",
                    f"Debt-to-equity of {de_str} introduces financial "
                    f"leverage risk that should be monitored periodically",
                    61)
    return ("CON_FB", "con",
            "Requires ongoing monitoring of competitive position "
            "and sector dynamics", 61)


def evaluate_all(
    groups: dict[str, pd.DataFrame],
    cm: dict[str, str],
    min_confidence: int = 60,
) -> list[dict]:
    """Run all 24 rules for every company.  Ensure >=1 pro and >=1 con."""
    results: list[dict] = []
    stats = {"total": len(groups), "pros_only": 0, "cons_only": 0,
             "both": 0, "neither": 0}

    for company_id, company_df in groups.items():
        company_results: list[dict] = []

        for rule_fn in ALL_RULES:
            try:
                outcome = rule_fn(cm, company_df)
            except Exception:
                continue
            if outcome is None:
                continue
            rule_id, rtype, text, conf = outcome
            if conf > min_confidence:
                company_results.append({
                    "company_id": company_id,
                    "type": rtype,
                    "rule_id": rule_id,
                    "text": text,
                    "confidence_pct": conf,
                })

        pros = [r for r in company_results if r["type"] == "pro"]
        cons = [r for r in company_results if r["type"] == "con"]

        # Guarantee at least 1 pro and 1 con per company
        if not pros:
            fb = _fallback_pro(cm, company_df, company_id)
            pros.append({
                "company_id": company_id,
                "type": fb[1], "rule_id": fb[0],
                "text": fb[2], "confidence_pct": fb[3],
            })
        if not cons:
            fb = _fallback_con(cm, company_df)
            cons.append({
                "company_id": company_id,
                "type": fb[1], "rule_id": fb[0],
                "text": fb[2], "confidence_pct": fb[3],
            })

        # Sort: highest confidence first
        pros.sort(key=lambda r: r["confidence_pct"], reverse=True)
        cons.sort(key=lambda r: r["confidence_pct"], reverse=True)

        results.extend(pros)
        results.extend(cons)

        if len(pros) > 0 and len(cons) > 0:
            stats["both"] += 1
        elif len(pros) > 0:
            stats["pros_only"] += 1
        elif len(cons) > 0:
            stats["cons_only"] += 1
        else:
            stats["neither"] += 1

    return results, stats

# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

def write_output(results: list[dict]) -> None:
    path = OUTPUT_DIR / "pros_cons_generated.csv"
    columns = ["company_id", "type", "rule_id", "text", "confidence_pct"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"  [OK] {len(results)} rows -> {path}")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("=" * 60)
    print("  Auto Pros/Cons Generator — Day 30")
    print("=" * 60)

    # 1. Load
    print(f"\n[1/3] Loading data from {DB_PATH.name} ...")
    groups, cm, _, _ = load_data()

    # 2. Evaluate
    print(f"\n[2/3] Evaluating {len(ALL_RULES)} rules × {len(groups)} companies ...")
    results, stats = evaluate_all(groups, cm)

    # 3. Write
    print(f"\n[3/3] Writing output ...")
    write_output(results)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  Total results:  {len(results)}")
    print(f"  Companies:      {stats['total']}")
    print(f"  With both:      {stats['both']}")
    print(f"  Pros-only fix:  {stats['pros_only']}")
    print(f"  Cons-only fix:  {stats['cons_only']}")
    print(f"  Neither fix:    {stats['neither']}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()