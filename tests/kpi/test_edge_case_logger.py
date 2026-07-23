"""
Day 13 — Tests for edge_case_logger.py
"""

import csv
from pathlib import Path

import pytest

from src.analytics.edge_case_logger import (
    EdgeCaseLogger,
    EdgeCaseRecord,
    EdgeCaseType,
)


class TestEdgeCaseRecord:
    def test_creates_record(self):
        r = EdgeCaseRecord(
            timestamp="2024-01-01T00:00:00",
            company_id="TCS",
            year="2023-03",
            kpi="ROE",
            edge_type="NEGATIVE_EQUITY",
            message="test",
        )
        assert r.company_id == "TCS"
        assert r.edge_type == "NEGATIVE_EQUITY"
        assert r.raw_value == ""


class TestEdgeCaseLoggerInit:
    def test_creates_log_dir(self, tmp_path):
        logger = EdgeCaseLogger(log_dir=str(tmp_path / "logs"))
        assert logger.log_dir.exists()

    def test_creates_log_file_on_first_log(self, tmp_path):
        logger = EdgeCaseLogger(log_dir=str(tmp_path / "logs"))
        logger.log("TCS", "2023-03", "ROE", EdgeCaseType.DIVISION_BY_ZERO, "test")
        assert logger.log_file.exists()


class TestLogMethods:
    def test_log_basic(self, tmp_path):
        logger = EdgeCaseLogger(log_dir=str(tmp_path / "logs"))
        rec = logger.log(
            "TCS", "2023-03", "ROE", EdgeCaseType.DIVISION_BY_ZERO, "denom is zero"
        )
        assert rec.company_id == "TCS"
        assert rec.edge_type == "DIVISION_BY_ZERO"
        assert logger.count == 1

    def test_log_division_by_zero(self, tmp_path):
        logger = EdgeCaseLogger(log_dir=str(tmp_path / "logs"))
        logger.log_division_by_zero("RELIANCE", "2023-03", "ROE", 5000, 0)
        assert logger.count == 1
        assert logger.records[0].raw_value == "num=5000,den=0"

    def test_log_debt_free(self, tmp_path):
        logger = EdgeCaseLogger(log_dir=str(tmp_path / "logs"))
        logger.log_debt_free("TCS", "2023-03", "ICR")
        assert logger.records[0].edge_type == "DEBT_FREE_SUBSTITUTION"

    def test_log_negative_equity(self, tmp_path):
        logger = EdgeCaseLogger(log_dir=str(tmp_path / "logs"))
        logger.log_negative_equity("VODAIDEA", "2023-03", -100, -5000)
        assert logger.records[0].edge_type == "NEGATIVE_EQUITY"
        assert logger.records[0].raw_value == "eq=-100,res=-5000"

    def test_log_cagr_flag(self, tmp_path):
        logger = EdgeCaseLogger(log_dir=str(tmp_path / "logs"))
        logger.log_cagr_flag("TCS", "revenue", 3, "CAGR_TURNAROUND", -100, 500)
        assert logger.records[0].edge_type == "CAGR_TURNAROUND"
        assert logger.records[0].kpi == "revenue_cagr_3yr"

    def test_log_outlier(self, tmp_path):
        logger = EdgeCaseLogger(log_dir=str(tmp_path / "logs"))
        logger.log_outlier("XYZ", "2023-03", "ROE", 500.0, -50, 100)
        assert logger.records[0].edge_type == "OUTLIER_RATIO"
        assert "500.0" in logger.records[0].message


class TestExportCsv:
    def test_writes_csv_with_all_records(self, tmp_path):
        logger = EdgeCaseLogger(log_dir=str(tmp_path / "logs"))
        logger.log("TCS", "2023-03", "ROE", EdgeCaseType.DIVISION_BY_ZERO, "m1")
        logger.log("RELIANCE", "2023-03", "NPM", EdgeCaseType.NULL_RATIO, "m2")
        path = logger.export_csv()
        assert Path(path).exists()
        with open(path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert rows[0]["company_id"] == "TCS"
        assert rows[1]["company_id"] == "RELIANCE"

    def test_custom_path(self, tmp_path):
        logger = EdgeCaseLogger(log_dir=str(tmp_path / "logs"))
        logger.log("A", "2023", "K", EdgeCaseType.DIVISION_BY_ZERO, "m")
        custom = str(tmp_path / "custom.csv")
        returned = logger.export_csv(path=custom)
        assert returned == custom
        assert Path(custom).exists()


class TestSummary:
    def test_counts_by_type(self, tmp_path):
        logger = EdgeCaseLogger(log_dir=str(tmp_path / "logs"))
        logger.log("A", "2023", "K1", EdgeCaseType.DIVISION_BY_ZERO, "m1")
        logger.log("B", "2023", "K2", EdgeCaseType.DIVISION_BY_ZERO, "m2")
        logger.log("C", "2023", "K3", EdgeCaseType.DEBT_FREE_SUBSTITUTION, "m3")
        s = logger.summary()
        assert s["DIVISION_BY_ZERO"] == 2
        assert s["DEBT_FREE_SUBSTITUTION"] == 1
        assert "NEGATIVE_EQUITY" not in s

    def test_empty_summary(self, tmp_path):
        logger = EdgeCaseLogger(log_dir=str(tmp_path / "logs"))
        assert logger.summary() == {}