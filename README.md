# Nifty 100 Financial Intelligence Platform

Production-focused financial analytics workspace for Nifty 100 equities, with ETL, KPI computation, screening, peer analysis, and dashboard delivery.

Current codebase focus is strong on ETL + analytics + testing. Some API/reporting paths are scaffolded and documented below under "Implementation Status".

## 1) What This Project Does

This repository is designed to:

- Ingest structured Excel datasets for Nifty 100 companies.
- Normalize and validate the data before loading into SQLite.
- Compute financial KPIs and derived metrics (profitability, leverage, efficiency, cash-flow quality, CAGR-based growth).
- Run stock-screening logic using analyst-configurable YAML thresholds and presets.
- Support peer comparison and radar-visual style outputs.
- Expose results in a Streamlit dashboard.
- Maintain quality through an extensive pytest suite.

## 2) High-Level Architecture

1. Data Ingestion
- Input source files in `data/raw/` and `data/supporting/`.
- Loader and normalization utilities in `src/etl/`.

2. Storage
- SQLite schema in `db/schema.sql`.
- Main writable DB used by ETL and analytics (`db/nifty100.db` and/or `output/nifty100.db` depending on runner).

3. Analytics
- Ratio and KPI computation logic in `src/analytics/`.
- Screener engine and presets in `src/screener/` and `config/screener_config.yaml`.

4. Delivery
- Streamlit app shell in `src/dashboard/` with multipage navigation.

5. Quality
- Unit and integration tests in `tests/`.

## 3) Repository Layout

| Path | Purpose |
|------|---------|
| `config/` | Logging and screener configs |
| `data/raw/` | Core Excel inputs (expected header row at index 1 for core files) |
| `data/supporting/` | Supporting Excel inputs (expected header row at index 0) |
| `db/schema.sql` | Canonical SQLite schema (10 legacy/core tables) |
| `src/etl/` | Loaders, normalization, validation, DQ review, audit and exploration tools |
| `src/analytics/` | Financial ratio formulas, KPI runners, CAGR and cash-flow analytics |
| `src/screener/` | Filtering, scoring, exports, presets |
| `src/dashboard/` | Streamlit app entry and pages |
| `src/api/` | API package scaffold (router folder currently present) |
| `src/reports/` | Reporting package scaffold |
| `tests/` | Pytest suite across ETL, analytics, screener, KPI, integration |
| `output/` | Generated outputs, audit CSVs, ETL logs |
| `reports/` | Report artifacts (including pytest HTML report target) |

## 4) Data Contract

Expected source files by loader design:

Core files (`data/raw/`, header row = 1):

1. `companies.xlsx`
2. `profitandloss.xlsx`
3. `balancesheet.xlsx`
4. `cashflow.xlsx`
5. `analysis.xlsx`
6. `documents.xlsx`
7. `prosandcons.xlsx`

Supporting files (`data/supporting/`, header row = 0):

1. `sectors.xlsx`
2. `stock_prices.xlsx`
3. `market_cap.xlsx`
4. `financial_ratios.xlsx`
5. `peer_groups.xlsx`

Notes:

- Company IDs are normalized through shared utilities (`normalize_ticker`).
- Year fields are normalized through shared utilities (`normalize_year`).
- Missing or malformed critical identifiers may be dropped during normalization.

## 5) Prerequisites

- OS: Windows, macOS, or Linux
- Python: 3.10+ recommended
- Pip: latest stable
- Git

Optional but useful:

- Make (Linux/macOS native; Windows via Git Bash/WSL/make binary)
- SQLite tools for manual inspection

## 6) Setup and Installation

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.template .env
```

### Linux/macOS (bash/zsh)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.template .env
```

## 7) Environment Variables

The template file is `.env.template`.

Current keys:

- `DB_PATH=data/nifty100.db`
- `PORT=8000`
- `LOG_LEVEL=INFO`
- `SIMULATED_DATA_FLAG=true`

Keep `.env` local and do not commit secrets.

## 8) Core Workflows

### A) ETL Database Build

Recommended explicit runner:

```bash
python -m src.etl.db_loader
```

What it does:

- Creates schema from `db/schema.sql`.
- Loads sectors and companies.
- Loads core/supporting financial tables with normalization.
- Prints per-table row-load summary.

### B) KPI / Ratio Engine

Recommended engine runner:

```bash
python -m src.analytics.run_ratio_engine
```

What it does:

- Creates/updates `financial_ratios` table.
- Joins available source tables.
- Computes profitability, leverage, coverage, efficiency, cash-flow, and growth KPIs.
- Emits capital allocation CSV output.

### C) Data Quality and Audits

Available utilities:

```bash
python -m src.etl.dq_review
python -m src.etl.load_audit
python -m src.etl.explore
```

### D) Dashboard

```bash
streamlit run src/dashboard/app.py
```

Default URL: `http://localhost:8501`

### E) Tests

```bash
pytest tests/ -v --tb=short
```

With HTML report:

```bash
pytest tests/ --html=reports/pytest_report.html -v --tb=short
```

## 9) Makefile Commands

The project contains a Makefile with targets:

- `make load`
- `make ratios`
- `make test`
- `make report`
- `make dashboard`
- `make api`
- `make clean`

Important status note:

- Some Make targets currently point to entry files that are scaffolded or not fully aligned with present module inventory (see Implementation Status below). For reliability, prefer the explicit Python module commands in Section 8.

## 10) Implementation Status (Current Repository Snapshot)

Fully implemented and test-backed areas:

- ETL utilities and loaders
- Normalization and validation helpers
- Financial ratio formulas and KPI computation modules
- Screener config + engine utilities
- Broad pytest coverage across ETL, analytics, screener, KPI, and integration paths

Partially implemented or scaffolded areas:

- API package exists (`src/api/`) but currently lacks an executable FastAPI app entry module expected by Makefile (`src.api.main:app`).
- Reports package exists (`src/reports/`) but target scripts referenced in Makefile are not present in current tree.
- Dashboard multipage skeleton is present; at least some pages are placeholders while the framework and navigation are in place.

## 11) Logging and Configuration

- Logging config file: `config/logging_config.yaml`
  - Console handler (INFO)
  - Rotating file handler to `output/etl.log` (DEBUG)
- Screener thresholds and presets: `config/screener_config.yaml`
  - Analyst-editable filters
  - Sector-aware skip logic (for leverage filters)
  - Built-in preset bundles

## 12) Testing Strategy

Tests are organized by domain:

- `tests/etl/`: ETL normalization/validation tests
- `tests/analytics/`: analytics-level tests (peer, radar, data quality)
- `tests/kpi/`: KPI function and integration tests
- `tests/screener/`: screener filters, scoring, exports, presets
- `tests/integration/`: broader spot checks
- root tests: schema, DQ review, explore, load audit

Recommended execution order for contributors:

1. `pytest tests/test_schema.py -v`
2. `pytest tests/etl -v`
3. `pytest tests/kpi -v`
4. `pytest tests/ -v --tb=short`

## 13) Troubleshooting

### 1. Module import errors (src.*)

- Run commands from repository root.
- Ensure virtual environment is active.

### 2. Missing Excel file errors

- Verify all expected files exist in `data/raw/` and `data/supporting/`.
- Ensure filenames match exactly (case and spelling).

### 3. No rows loaded into a table

- Check column header naming drift in Excel.
- Review mapping dictionaries in `src/etl/db_loader.py`.

### 4. Dashboard starts but pages are sparse

- This is expected for pages still under build; app shell and navigation are functional.

### 5. Makefile command fails

- Use explicit module command from Section 8.
- Treat Makefile target as convenience wrapper pending alignment.

## 14) Development Standards

- Code style tooling in dependencies: Black and Ruff
- Keep business logic pure and testable
- Prefer explicit module entrypoints (`python -m ...`) over implicit script assumptions
- Add/adjust tests with every data-contract or KPI behavior change

## 15) Suggested Contributor Flow

1. Create branch from `main`.
2. Implement change in ETL/analytics/screener/dashboard area.
3. Run focused tests first, then full suite.
4. Update docs/config as needed.
5. Open PR with before/after behavior summary and test evidence.

## 16) Tech Stack

- Data: pandas, numpy, openpyxl
- Analytics: scipy, scikit-learn
- Visualization: matplotlib, plotly
- App layer: streamlit
- API layer: fastapi, uvicorn (scaffolded in current snapshot)
- Reporting: reportlab
- Testing: pytest, pytest-html
- Config: python-dotenv, pyyaml
- Tooling: black, ruff, notebook, pre-commit

## 17) Version Context

- Release train: v1.0
- Execution plan reference: 45-day sprint (6 x 7-day cadence)

## 18) Quick Command Reference

```bash
# Environment
python -m venv .venv

# Activate (Windows)
.\.venv\Scripts\Activate.ps1

# Activate (Linux/macOS)
source .venv/bin/activate

# Install
pip install -r requirements.txt

# ETL build
python -m src.etl.db_loader

# KPI engine
python -m src.analytics.run_ratio_engine

# Tests
pytest tests/ -v --tb=short

# Dashboard
streamlit run src/dashboard/app.py
```
