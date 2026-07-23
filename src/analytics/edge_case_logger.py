"""
Day 13 — Edge Case Logger
Structured logging for ratio computation edge cases:
CAGR flags, division-by-zero, debt-free substitutions, negative equity, outliers.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class EdgeCaseType(Enum):
    """Enumeration of all edge case categories."""
    CAGR_TURNAROUND = "CAGR_TURNAROUND"
    CAGR_ZERO_BASE = "CAGR_ZERO_BASE"
    CAGR_DECLINE_TO_LOSS = "CAGR_DECLINE_TO_LOSS"
    CAGR_BOTH_NEGATIVE = "CAGR_BOTH_NEGATIVE"
    CAGR_INSUFFICIENT = "CAGR_INSUFFICIENT"
    DIVISION_BY_ZERO = "DIVISION_BY_ZERO"
    DEBT_FREE_SUBSTITUTION = "DEBT_FREE_SUBSTITUTION"
    NEGATIVE_EQUITY = "NEGATIVE_EQUITY"
    OPM_CROSS_CHECK_MISMATCH = "OPM_CROSS_CHECK_MISMATCH"
    NULL_RATIO = "NULL_RATIO"
    OUTLIER_RATIO = "OUTLIER_RATIO"


@dataclass
class EdgeCaseRecord:
    """Single edge case event."""
    timestamp: str
    company_id: str
    year: str
    kpi: str
    edge_type: str
    message: str
    raw_value: str = ""


class EdgeCaseLogger:
    """Structured logger for ratio edge cases.

    Writes to both a log file and an in-memory record list.
    Supports CSV export for analysis.
    """

    def __init__(self, log_dir: Optional[str] = None) -> None:
        if log_dir is None:
            log_dir = str(
                Path(__file__).resolve().parent.parent.parent / "logs"
            )
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "ratio_edge_cases.log"
        self.records: list[EdgeCaseRecord] = []

        # Python stdlib logger
        self._logger = logging.getLogger("ratio_edge_cases")
        self._logger.setLevel(logging.DEBUG)
        for handler in list(self._logger.handlers):
            self._logger.removeHandler(handler)
            handler.close()

        fh = logging.FileHandler(str(self.log_file), encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        )
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)
        self._logger.addHandler(fh)
        self._logger.addHandler(ch)

    # ------------------------------------------------------------------
    # Generic log
    # ------------------------------------------------------------------
    def log(
        self,
        company_id: str,
        year: str,
        kpi: str,
        edge_type: EdgeCaseType,
        message: str,
        raw_value: str = "",
    ) -> EdgeCaseRecord:
        """Record a single edge case event. Returns the created record."""
        record = EdgeCaseRecord(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            company_id=company_id,
            year=year,
            kpi=kpi,
            edge_type=edge_type.value,
            message=message,
            raw_value=str(raw_value),
        )
        self.records.append(record)
        self._logger.debug(
            "[%s] %s %s %s: %s",
            edge_type.value,
            company_id,
            year,
            kpi,
            message,
        )
        return record

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------
    def log_cagr_flag(
        self,
        company_id: str,
        metric: str,
        window: int,
        flag: str,
        start_val: Optional[float],
        end_val: Optional[float],
    ) -> None:
        """Log a CAGR computation flag."""
        # Resolve flag to EdgeCaseType; fall back to INSUFFICIENT
        valid_flags = {e.value: e for e in EdgeCaseType}
        etype = valid_flags.get(flag, EdgeCaseType.CAGR_INSUFFICIENT)
        self.log(
            company_id=company_id,
            year="N/A",
            kpi=f"{metric}_cagr_{window}yr",
            edge_type=etype,
            message=(
                f"{metric} {window}yr CAGR flagged: {flag} "
                f"(start={start_val}, end={end_val})"
            ),
            raw_value=f"start={start_val},end={end_val},flag={flag}",
        )

    def log_division_by_zero(
        self,
        company_id: str,
        year: str,
        kpi: str,
        numerator: Optional[float],
        denominator: Optional[float],
    ) -> None:
        """Log a skipped ratio due to zero / None denominator."""
        self.log(
            company_id=company_id,
            year=year,
            kpi=kpi,
            edge_type=EdgeCaseType.DIVISION_BY_ZERO,
            message=f"Skipped {kpi}: denominator is zero or None",
            raw_value=f"num={numerator},den={denominator}",
        )

    def log_debt_free(
        self, company_id: str, year: str, kpi: str
    ) -> None:
        """Log a debt-free substitution."""
        self.log(
            company_id=company_id,
            year=year,
            kpi=kpi,
            edge_type=EdgeCaseType.DEBT_FREE_SUBSTITUTION,
            message=f"{kpi} substituted for debt-free company",
        )

    def log_negative_equity(
        self,
        company_id: str,
        year: str,
        equity_capital: float,
        reserves: float,
    ) -> None:
        """Log negative total equity warning."""
        self.log(
            company_id=company_id,
            year=year,
            kpi="ROE/ROCE",
            edge_type=EdgeCaseType.NEGATIVE_EQUITY,
            message=(
                f"Negative total equity: equity_capital={equity_capital}, "
                f"reserves={reserves}"
            ),
            raw_value=f"eq={equity_capital},res={reserves}",
        )

    def log_outlier(
        self,
        company_id: str,
        year: str,
        kpi: str,
        value: float,
        low: float,
        high: float,
    ) -> None:
        """Log a ratio value outside expected range."""
        self.log(
            company_id=company_id,
            year=year,
            kpi=kpi,
            edge_type=EdgeCaseType.OUTLIER_RATIO,
            message=f"{kpi}={value} outside expected range [{low}, {high}]",
            raw_value=str(value),
        )

    # ------------------------------------------------------------------
    # Export / summary
    # ------------------------------------------------------------------
    def export_csv(self, path: Optional[str] = None) -> str:
        """Export all records to CSV. Returns the file path written."""
        if path is None:
            path = str(self.log_dir / "ratio_edge_cases.csv")
        fields = list(EdgeCaseRecord.__dataclass_fields__.keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in self.records:
                writer.writerow(asdict(r))
        return path

    @property
    def count(self) -> int:
        """Number of records logged so far."""
        return len(self.records)

    def summary(self) -> dict[str, int]:
        """Count records grouped by edge type."""
        counts: dict[str, int] = {}
        for r in self.records:
            counts[r.edge_type] = counts.get(r.edge_type, 0) + 1
        return counts