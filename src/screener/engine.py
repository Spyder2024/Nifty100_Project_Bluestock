"""Screener Filter Engine — Sprint 3 Day 15.

Loads thresholds from screener_config.yaml and applies them to a
financial_ratios DataFrame. Supports:
  - 15 filterable metrics (min/max threshold)
  - D/E auto-skip for Financials sector
  - ICR debt-free = infinity (always passes)
  - Composite quality score (basic version; enhanced in Day 17)
  - Sorted output by composite_quality_score descending
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import yaml

# Default config path
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "screener_config.yaml"

# Columns that indicate sector identity
SECTOR_COLUMNS = ["broad_sector", "sector_id", "sector"]

# All 15 filterable metric column names
FILTERABLE_COLUMNS = {
    "roe", "debt_to_equity", "free_cash_flow",
    "revenue_cagr_5yr", "pat_cagr_5yr", "operating_profit_margin",
    "pe_ratio", "pb_ratio", "dividend_yield", "interest_coverage_ratio",
    "market_cap", "net_profit", "eps_cagr_5yr", "asset_turnover", "net_sales",
}

# Dividend payout ratio — used by Dividend Champion preset
DIVIDEND_PAYOUT_COL = "dividend_payout_ratio"


class FilterEngine:
    """Config-driven screener that applies threshold filters to financial_ratios.

    Usage::
        engine = FilterEngine()                      # loads default config
        engine = FilterEngine(config_path=custom)    # or custom path
        result = engine.apply(df)                    # apply default filters
        result = engine.apply(df, roe=15, pe_ratio=20)  # override specific filters
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._raw: dict[str, Any] = {}
        self.filters: dict[str, dict[str, Any]] = {}
        self.presets: dict[str, dict[str, Any]] = {}
        self.financial_sectors: list[str] = []
        self._load_config()

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        """Load and parse screener_config.yaml."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Screener config not found: {self.config_path}"
            )
        with open(self.config_path, "r", encoding="utf-8") as fh:
            self._raw = yaml.safe_load(fh)

        self.filters = self._raw.get("filters", {})
        self.presets = self._raw.get("presets", {})
        self.financial_sectors = self._raw.get("financial_sectors", [])

    def reload(self) -> None:
        """Re-load config from disk (hot reload for analyst edits)."""
        self._load_config()

    # ------------------------------------------------------------------
    # Preset helpers
    # ------------------------------------------------------------------

    def get_preset(self, name: str) -> dict[str, float]:
        """Return {column: threshold} dict for a named preset.

        Raises:
            KeyError: if preset name not found in config.
        """
        if name not in self.presets:
            raise KeyError(
                f"Preset '{name}' not found. "
                f"Available: {list(self.presets.keys())}"
            )
        preset_def = self.presets[name]
        result: dict[str, float] = {}
        for filter_name, threshold in preset_def.get("filters", {}).items():
            if filter_name in self.filters:
                col = self.filters[filter_name]["column"]
                result[col] = float(threshold)
            else:
                # Handle special columns like dividend_payout_ratio
                col_alias = {
                    "dividend_payout_ratio": DIVIDEND_PAYOUT_COL,
                }
                if filter_name in col_alias:
                    result[col_alias[filter_name]] = float(threshold)
                else:
                    result[filter_name] = float(threshold)
        return result

    # ------------------------------------------------------------------
    # Sector detection
    # ------------------------------------------------------------------

    def _get_all_sectors(self, row: pd.Series) -> list[str]:
        """Extract all non-null sector values from a DataFrame row."""
        sectors = []
        for col in SECTOR_COLUMNS:
            if col in row.index and pd.notna(row[col]):
                sectors.append(str(row[col]).strip())
        return sectors

    def _get_sector(self, row: pd.Series) -> Optional[str]:
        """Extract primary sector value from a DataFrame row."""
        sectors = self._get_all_sectors(row)
        return sectors[0] if sectors else None

    def _is_any_financial_sector(self, row: pd.Series) -> bool:
        """Check if ANY sector column value matches a financial sector.

        This is more robust than _is_financial_sector because it checks
        broad_sector, sector_id, and sector — whichever is present.
        """
        sectors = self._get_all_sectors(row)
        for sector in sectors:
            if any(fs.lower() == sector.lower() for fs in self.financial_sectors):
                return True
        return False

    def _is_financial_sector(self, sector: Optional[str]) -> bool:
        """Check if a single sector string is a financial sector."""
        if sector is None:
            return False
        return any(
            fs.lower() == sector.lower()
            for fs in self.financial_sectors
        )

    # ------------------------------------------------------------------
    # Composite quality score (basic version — Day 17 enhances this)
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_col(df: pd.DataFrame, col: str) -> pd.Series:
        """Return df[col] as float Series, or all-NaN if column missing."""
        if col not in df.columns:
            return pd.Series(np.nan, index=df.index, dtype=float)
        return pd.to_numeric(df[col], errors="coerce")

    @classmethod
    def compute_composite_score(cls, df: pd.DataFrame) -> pd.Series:
        """Compute a basic composite quality score (0-100) for each row.

        Day 15 version: simple weighted average of available metrics.
        Day 17 will replace this with P10/P90 winsorised sector-relative scoring.

        Weights:
            Profitability (35%): ROE 15% + ROCE 10% + NPM 10%
            Cash Quality  (30%): FCF positive flag 10% + CFO/PAT 10% + FCF conv 10%
            Growth       (20%): Revenue CAGR 5yr 10% + PAT CAGR 5yr 10%
            Leverage     (15%): D/E score 10% + ICR score 5%

        Gracefully handles DataFrames missing metric columns (returns NaN).
        """
        scores = pd.Series(np.nan, index=df.index)

        # --- Profitability (35%) ---
        roe_pts = cls._safe_col(df, "roe").clip(0, 40) / 40 * 15
        roce_pts = cls._safe_col(df, "roce").clip(0, 30) / 30 * 10
        npm_pts = cls._safe_col(df, "net_profit_margin").clip(0, 25) / 25 * 10

        profitability = roe_pts.fillna(0) + roce_pts.fillna(0) + npm_pts.fillna(0)

        # --- Cash Quality (30%) ---
        fcf = cls._safe_col(df, "free_cash_flow")
        fcf_flag = (fcf > 0).astype(float) * 10

        cfo_q = cls._safe_col(df, "cfo_quality_score").clip(50, 150)
        cfo_q_pts = (cfo_q - 50) / 100 * 10

        fcf_conv = cls._safe_col(df, "fcf_conversion_rate").clip(0, 100)
        fcf_conv_pts = fcf_conv / 100 * 10

        cash_quality = (
            fcf_flag.fillna(0)
            + cfo_q_pts.fillna(0)
            + fcf_conv_pts.fillna(0)
        )

        # --- Growth (20%) ---
        rev_cagr = cls._safe_col(df, "revenue_cagr_5yr").clip(0, 30)
        rev_cagr_pts = rev_cagr / 30 * 10

        pat_cagr = cls._safe_col(df, "pat_cagr_5yr").clip(0, 30)
        pat_cagr_pts = pat_cagr / 30 * 10

        growth = rev_cagr_pts.fillna(0) + pat_cagr_pts.fillna(0)

        # --- Leverage (15%) ---
        de = cls._safe_col(df, "debt_to_equity")
        de_score = (1 - de.clip(0, 2) / 2) * 10

        icr = cls._safe_col(df, "interest_coverage_ratio")
        icr_pts = icr.clip(0, 15) / 15 * 5

        leverage = de_score.fillna(0) + icr_pts.fillna(0)

        # --- Total ---
        scores = (profitability + cash_quality + growth + leverage).round(2)

        # Count how many metrics were available (only columns that exist)
        metric_cols = [
            c for c in [
                "roe", "roce", "net_profit_margin", "free_cash_flow",
                "cfo_quality_score", "fcf_conversion_rate",
                "revenue_cagr_5yr", "pat_cagr_5yr",
                "debt_to_equity", "interest_coverage_ratio",
            ]
            if c in df.columns
        ]
        if metric_cols:
            available = df[metric_cols].notna().sum(axis=1)
            min_metrics = 3
            scores = scores.where(available >= min_metrics, np.nan)
        else:
            scores[:] = np.nan

        return scores

    # ------------------------------------------------------------------
    # Core filter logic
    # ------------------------------------------------------------------

    def apply(
        self,
        df: pd.DataFrame,
        sort_by: str = "composite_quality_score",
        ascending: bool = False,
        add_score: bool = True,
        **overrides: float,
    ) -> pd.DataFrame:
        """Apply screener filters to financial_ratios DataFrame.

        Args:
            df: DataFrame with financial_ratios columns.
            sort_by: Column to sort results by. Default: composite_quality_score.
            ascending: Sort direction. Default: False (descending).
            add_score: Whether to add/compute composite_quality_score column.
            **overrides: Override specific filter thresholds, e.g. roe=15, pe_ratio=20.

        Returns:
            Filtered and sorted DataFrame copy.
        """
        if df.empty:
            return df.copy()

        result = df.copy()

        # Add composite quality score if requested or if sorting by it
        if add_score or sort_by == "composite_quality_score":
            if "composite_quality_score" not in result.columns or add_score:
                result["composite_quality_score"] = self.compute_composite_score(result)

        # Build effective filter set: config defaults + overrides
        effective_filters = self._build_effective_filters(overrides)

        # Apply each filter
        for col, (direction, threshold) in effective_filters.items():
            result = self._apply_single_filter(result, col, direction, threshold)

        # Sort
        if sort_by in result.columns:
            result = result.sort_values(
                by=sort_by, ascending=ascending, na_position="last"
            )

        return result.reset_index(drop=True)

    def _build_effective_filters(
        self, overrides: dict[str, float]
    ) -> dict[str, tuple[str, float]]:
        """Merge config defaults with caller overrides.

        Returns:
            {column_name: (direction, threshold)} for all active filters.
        """
        effective: dict[str, tuple[str, float]] = {}

        # Map override keys that use filter names (e.g. 'roe') to column names
        override_col_map: dict[str, str] = {}
        for fname, fdef in self.filters.items():
            override_col_map[fname] = fdef["column"]
        # Add aliases
        override_col_map["debt_to_equity"] = "debt_to_equity"
        override_col_map["dividend_payout_ratio"] = DIVIDEND_PAYOUT_COL

        # Process overrides first (they take precedence)
        for key, value in overrides.items():
            if value is None:
                continue
            col = override_col_map.get(key, key)
            # Determine direction from config or heuristics
            direction = self._get_direction(col)
            effective[col] = (direction, float(value))

        return effective

    def _get_direction(self, col: str) -> str:
        """Determine filter direction for a column from config."""
        for fname, fdef in self.filters.items():
            if fdef["column"] == col:
                return fdef["direction"]
        # Default heuristics
        max_cols = {"debt_to_equity", "pe_ratio", "pb_ratio", "dividend_payout_ratio"}
        return "max" if col in max_cols else "min"

    def _apply_single_filter(
        self,
        df: pd.DataFrame,
        column: str,
        direction: str,
        threshold: float,
    ) -> pd.DataFrame:
        """Apply a single threshold filter to the DataFrame.

        Handles special cases:
        - D/E: auto-skips Financials sector
        - ICR: debt-free companies always pass
        """
        if column not in df.columns:
            return df

        # --- D/E special: auto-skip Financials ---
        if column == "debt_to_equity":
            return self._apply_de_filter(df, direction, threshold)

        # --- ICR special: debt-free = infinity ---
        if column == "interest_coverage_ratio":
            return self._apply_icr_filter(df, direction, threshold)

        # --- Standard filter ---
        mask = pd.Series(True, index=df.index)

        if direction == "min":
            # Keep rows where column >= threshold
            mask = df[column] >= threshold
        elif direction == "max":
            # Keep rows where column <= threshold
            mask = df[column] <= threshold

        # Rows with None/NaN in the filter column don't pass
        mask = mask.fillna(False)

        return df.loc[mask]

    def _apply_de_filter(
        self,
        df: pd.DataFrame,
        direction: str,
        threshold: float,
    ) -> pd.DataFrame:
        """Apply D/E filter with Financials sector auto-skip.

        Financials sector companies are exempt from D/E filtering
        because their business model inherently uses high leverage.
        """
        is_financial = df.apply(self._is_any_financial_sector, axis=1)

        mask = pd.Series(True, index=df.index)

        if direction == "max":
            # Keep rows where D/E <= threshold (or Financials)
            mask = (df["debt_to_equity"] <= threshold) | is_financial
        elif direction == "min":
            mask = (df["debt_to_equity"] >= threshold) | is_financial

        # None/NaN in D/E: only pass if Financials
        mask = mask | (df["debt_to_equity"].isna() & is_financial)

        return df.loc[mask]

    def _apply_icr_filter(
        self,
        df: pd.DataFrame,
        direction: str,
        threshold: float,
    ) -> pd.DataFrame:
        """Apply ICR filter with debt-free = infinity handling.

        Companies marked as debt-free (is_debt_free == 1 or D/E == 0)
        always pass any ICR minimum threshold.
        """
        is_debt_free = (
            (df.get("is_debt_free") == 1)
            | (df.get("debt_to_equity") == 0)
        )

        mask = pd.Series(True, index=df.index)

        if direction == "min":
            # Keep rows where ICR >= threshold (or debt-free)
            mask = (df["interest_coverage_ratio"] >= threshold) | is_debt_free
        elif direction == "max":
            mask = (df["interest_coverage_ratio"] <= threshold) | is_debt_free

        # None/NaN in ICR: only pass if debt-free
        mask = mask | (df["interest_coverage_ratio"].isna() & is_debt_free)

        return df.loc[mask]

    def apply_preset(
        self,
        df: pd.DataFrame,
        preset_name: str,
        sort_by: str = "composite_quality_score",
        ascending: bool = False,
    ) -> pd.DataFrame:
        """Apply a named preset screener to the DataFrame.

        Args:
            df: financial_ratios DataFrame.
            preset_name: Key from screener_config.yaml presets section.
            sort_by: Column to sort by.
            ascending: Sort direction.

        Returns:
            Filtered and sorted DataFrame.
        """
        overrides = self.get_preset(preset_name)
        return self.apply(df, sort_by=sort_by, ascending=ascending, **overrides)

    def list_presets(self) -> list[str]:
        """Return list of available preset names."""
        return list(self.presets.keys())

    def list_filters(self) -> list[dict[str, str]]:
        """Return list of available filter definitions."""
        result = []
        for name, fdef in self.filters.items():
            result.append({
                "name": name,
                "column": fdef["column"],
                "display_name": fdef.get("display_name", name),
                "direction": fdef["direction"],
                "default": fdef.get("default"),
                "unit": fdef.get("unit", ""),
            })
        return result


# ==================================================================
# Convenience functions (module-level API)
# ==================================================================


def apply_filters(
    df: pd.DataFrame,
    config_path: Optional[Path] = None,
    sort_by: str = "composite_quality_score",
    ascending: bool = False,
    **overrides: float,
) -> pd.DataFrame:
    """One-shot filter application — creates engine internally.

    Args:
        df: financial_ratios DataFrame.
        config_path: Optional path to screener_config.yaml.
        sort_by: Column to sort by.
        ascending: Sort direction.
        **overrides: Filter overrides, e.g. roe=15, pe_ratio=20.

    Returns:
        Filtered, sorted DataFrame with composite_quality_score.
    """
    engine = FilterEngine(config_path=config_path)
    return engine.apply(df, sort_by=sort_by, ascending=ascending, **overrides)


def load_preset(
    preset_name: str,
    config_path: Optional[Path] = None,
) -> dict[str, float]:
    """Load a preset's filter thresholds as {column: value} dict.

    Args:
        preset_name: Preset key from config.
        config_path: Optional path to screener_config.yaml.

    Returns:
        {column_name: threshold_value} dict.
    """
    engine = FilterEngine(config_path=config_path)
    return engine.get_preset(preset_name)
