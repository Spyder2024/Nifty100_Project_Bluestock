# Nifty 100 Financial Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40%2B-FF4B4B.svg)](https://streamlit.io/)
[![SQLite](https://img.shields.io/badge/SQLite-3.40%2B-003B57.svg)](https://www.sqlite.org/)
[![Tests](https://img.shields.io/badge/Tests-667%20Passed-brightgreen.svg)](reports/pytest_report.html)
[![Code Style](https://img.shields.io/badge/Code%20Style-Black%20%7C%20Ruff-000000.svg)](https://github.com/astral-sh/ruff)

An enterprise-grade quantitative equity analysis and financial intelligence platform covering all **92 active constituents of the Nifty 100 index**. The platform integrates multi-year financial statement ETL, 30+ fundamental KPIs, DuPont ROE decomposition, machine learning clustering, automated PDF tearsheet generation, a reactive Streamlit web dashboard, and a high-throughput FastAPI REST backend.

---

## 1. Architectural Overview

```text
┌───────────────────────────────────────────────────────────────────────────────────┐
│                           RAW FINANCIAL INGESTION                                │
│        data/raw/ (Core Excel)        │        data/supporting/ (Supporting)       │
└────────────────────────────────────────┬──────────────────────────────────────────┘
                                         │
                                         ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                         ETL, NORMALIZATION & DATA QUALITY                         │
│   src/etl/normaliser.py  │  src/etl/validator.py  │  src/analytics/data_quality.py │
│   • Multi-tier year format normalization (FY19-24)  • 16 Automated DQ rules       │
└────────────────────────────────────────┬──────────────────────────────────────────┘
                                         │
                                         ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                         INDEXED STORAGE (SQLite 3)                                │
│   output/nifty100.db (10 tables, 92 companies, 6 years, 20 performance indexes)   │
└──────────────────┬─────────────────────────────────────┬──────────────────────────┘
                   │                                     │
                   ▼                                     ▼
┌──────────────────────────────────────┐  ┌─────────────────────────────────────────┐
│         QUANTITATIVE ANALYTICS       │  │        AUTOMATED REPORT GENERATOR       │
│  src/analytics/ratios.py (30+ KPIs)  │  │  src/reports/tearsheet.py (92 Co. PDFs) │
│  src/analytics/cagr.py (3Y/5Y/10Y)   │  │  src/reports/sector_report.py (11 Sec.) │
│  src/analytics/clustering.py (KMeans)│  │  src/reports/portfolio_report.py (92 P.)│
│  src/screener/engine.py (10 metrics) │  │  src/reports/analyst_guide_generator.py │
└──────────────────┬───────────────────┘  └─────────────────────┬───────────────────┘
                   │                                            │
                   ├────────────────────────────────────────────┤
                   ▼                                            ▼
┌──────────────────────────────────────┐  ┌─────────────────────────────────────────┐
│     FASTAPI REST SERVICE (Port 8000) │  │   STREAMLIT DASHBOARD (Port 8501)       │
│  src/api/main.py (20+ REST routes)   │  │   src/dashboard/app.py (9 Pages)        │
│  OpenAPI 3.1.0 Specification         │  │   Interactive Screener, Radar & Trends  │
└──────────────────────────────────────┘  └─────────────────────────────────────────┘
```

---

## 2. Key Features

- **Ingestion & Normalization:** Ingests raw balance sheets, income statements, cash flows, and price histories. Normalizes reporting dates across 11 sectors.
- **Fundamental Ratios & KPIs:** Computes Return on Equity (ROE), ROCE, Operating Profit Margin (OPM), Net Profit Margin (NPM), Debt-to-Equity, Interest Coverage Ratio (ICR), Asset Turnover, and 3Y/5Y/10Y CAGR compounding rates.
- **DuPont Analysis & Capital Allocation:** 3-stage DuPont decomposition, CFO quality scoring ($CFO / EBITDA$), CapEx intensity metrics, and distress early warnings.
- **Machine Learning Clustering:** Unsupervised KMeans clustering ($k=5$) identifying High-Quality Compounders, Defensive Dividend Payers, Emerging Growth, Capital Intensive, and Value Cyclicals.
- **Stock Screener:** 10-metric filtering engine with custom sliders, preset investment strategies (*Quality Compounders*, *Debt-Free Champions*, *Deep Value*, *FCF Machines*), and composite ranking.
- **Peer & Radar Analytics:** Relative percentile benchmarking within 11 sector cohorts with 8-axis radar comparison charts against sector averages and benchmark anchors.
- **Automated PDF Reporting:** Batch-generates publication-ready 2-page company tearsheets, 11 sector research PDFs, a 92-page portfolio summary PDF, and a 12-page comprehensive Analyst Guide.
- **Dual Presentation Interfaces:**
  - **Streamlit Web Dashboard:** 9 rich analytical pages running at `http://localhost:8501`.
  - **FastAPI REST API:** Sub-20ms endpoints running at `http://localhost:8000` with full Swagger UI documentation at `/docs`.
- **Data Governance & Testing:** 16 automated DQ validation rules and **667 automated unit and integration tests (100% pass rate)**.

---

## 3. Directory Layout

```text
.
├── config/                      # YAML configuration files (screener, logging)
├── data/                        # Raw & supporting Excel data sources
│   ├── raw/                     # Core company financial statements (10 tables)
│   └── supporting/              # Sector mappings, Nifty 100 universe metadata
├── docs/                        # API specifications and generated analyst guide
│   ├── analyst_guide.pdf        # 12-page comprehensive Operations Manual
│   ├── openapi.json             # OpenAPI 3.1.0 schema export
│   └── postman_collection.json  # Postman Collection v2.1
├── output/                      # Generated databases, analytics CSVs & archives
│   ├── nifty100.db              # Master SQLite database (20 active indexes)
│   └── final_deliverables/      # Consolidated archive of all 22 project deliverables
├── reports/                     # Generated PDF reports & visualizations
│   ├── tearsheets/              # 92 individual 2-page company tearsheets
│   ├── sector/                  # 11 sector deep-dive PDF reports
│   ├── portfolio/               # 92-page portfolio summary PDF
│   ├── correlation_heatmap.png  # 10x10 Pearson correlation heatmap
│   ├── elbow_plot.png           # KMeans cluster inertia validation curve
│   └── pytest_report.html       # Full HTML test execution report
├── src/                         # Core source code
│   ├── analytics/               # Ratios, CAGR, cashflow, clustering & database optimizer
│   ├── api/                     # FastAPI REST API (main app and routers)
│   ├── dashboard/               # Streamlit multi-page web application
│   ├── etl/                     # Ingestion loaders, normalization, validators
│   ├── nlp/                     # Sentiment & pros/cons text extractor
│   ├── reports/                 # ReportLab PDF report generators
│   └── screener/                # Screener filtering, scoring & export engines
└── tests/                       # Automated pytest suite (667 tests)
    ├── analytics/               # Clustering, profiling, radar, tearsheet tests
    ├── api/                     # Health, companies, screener, sectors, peers API tests
    ├── dq/                      # Data quality rules (DQ-01 to DQ-16) tests
    ├── etl/                     # Loaders, normalization, validation tests
    ├── integration/             # Performance, concurrency & dashboard-API tests
    ├── kpi/                     # Profitability, leverage, cashflow, CAGR tests
    └── screener/                # Filter engine, presets, scoring tests
```

---

## 4. Installation & Setup

### Prerequisites
- Python 3.11 or higher
- Git

### Setup Steps

```bash
# 1. Clone the repository
git clone https://github.com/Spyder2024/Nifty100_Project_Bluestock.git
cd Nifty100_Project_Bluestock

# 2. Create and activate virtual environment
python -m venv .venv

# Windows:
.\.venv\Scripts\activate

# Linux / macOS:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## 5. Execution Guide

### 1. Run the ETL Pipeline & Database Ingestion
Load raw financial datasets, execute normalization, compute KPIs, and populate `output/nifty100.db`:

```bash
python -m src.etl.db_loader
python -m src.analytics.ratio_runner
python -m src.analytics.optimize_db
```

### 2. Run Machine Learning Clustering & Profiling
Execute KMeans clustering ($k=5$), generate the elbow plot, correlation heatmap, and outlier reports:

```bash
python -m src.analytics.clustering
python -m src.analytics.profiling
```

### 3. Start the FastAPI REST Server
Launch the REST API on port 8000:

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```
- **API Base:** `http://localhost:8000/api/v1`
- **Swagger Documentation:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

### 4. Start the Streamlit Dashboard
Launch the interactive 9-page research dashboard on port 8501:

```bash
streamlit run src/dashboard/app.py --server.port 8501
```
- **Dashboard URL:** `http://localhost:8501`

### 5. Generate PDF Tearsheets & Reports
Compile publication-quality research PDFs:

```bash
# Generate 12-page Analyst Guide PDF
python -m src.reports.analyst_guide_generator

# Generate 92 Company Tearsheets
python -m src.reports.tearsheet --all

# Generate 11 Sector Benchmark Reports
python -m src.reports.sector_report

# Generate Portfolio Summary PDF
python -m src.reports.portfolio_report
```

### 6. Run Performance & Concurrency Load Test
Execute the automated concurrency benchmark suite:

```bash
python -m src.analytics.perf_benchmark
```

### 7. Run the Full Pytest Suite
Execute all 667 unit, API, data quality, and integration tests with HTML reporting:

```bash
pytest tests/ --html=reports/pytest_report.html --self-contained-html
```

---

## 6. REST API Endpoint Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Service health status, database table row counts, uptime |
| `GET` | `/api/v1/companies` | List all 92 companies with sector, market cap, and latest KPIs |
| `GET` | `/api/v1/companies/{ticker}` | Full company profile, latest ratios, and 6-year statement history |
| `GET` | `/api/v1/companies/{ticker}/pl` | Multi-year P&L / Income statement history array |
| `GET` | `/api/v1/companies/{ticker}/bs` | Multi-year Balance sheet history array |
| `GET` | `/api/v1/companies/{ticker}/cashflow` | Multi-year Cash flow statement history array |
| `GET` | `/api/v1/companies/{ticker}/ratios` | Computed financial ratios per fiscal year |
| `GET` | `/api/v1/companies/{ticker}/tearsheet` | Stream binary 2-page company tearsheet PDF |
| `GET` | `/api/v1/companies/{ticker}/peers/compare` | 8-Axis radar comparison data vs peer group & benchmark |
| `GET` | `/api/v1/screener` | Multi-metric screening with ranking (`min_roe`, `max_de`, `min_fcf`, etc.) |
| `GET` | `/api/v1/screener/presets` | List built-in strategy presets |
| `GET` | `/api/v1/sectors` | 11 sector overviews with median ROE, PE, and D/E |
| `GET` | `/api/v1/sectors/{sector}/companies` | Constituent companies within specified sector |
| `GET` | `/api/v1/peers/{group_name}` | Peer group members with 10-metric percentile rankings |
| `GET` | `/api/v1/market-cap/{ticker}` | 2019-2024 historical valuation multiples (P/E, P/B, EV/EBITDA, Yield) |

### Example `curl` Commands

```bash
# 1. Health Check
curl -X GET "http://localhost:8000/api/v1/health"

# 2. Screen Quality Compounders (ROE >= 20%, D/E <= 0.5)
curl -X GET "http://localhost:8000/api/v1/screener?min_roe=20.0&max_de=0.5"

# 3. Fetch Company Profile for TCS
curl -X GET "http://localhost:8000/api/v1/companies/TCS"

# 4. Fetch 8-Axis Radar Comparison Data for INFY
curl -X GET "http://localhost:8000/api/v1/companies/INFY/peers/compare"

# 5. Download Binary PDF Tearsheet for RELIANCE
curl -X GET "http://localhost:8000/api/v1/companies/RELIANCE/tearsheet" --output RELIANCE_tearsheet.pdf
```

---

## 7. Performance & Quality Benchmarks

| Metric | Target SLA | Measured Result | Status |
|---|---|---|:---:|
| **10 Concurrent Screener Requests** | < 10.0s wall time | **2.52s** | `PASSED` |
| **Company Profile Load Time** | < 3.0s / ticker | **0.0637s (63.7ms)** | `PASSED` |
| **Pytest Test Suite** | 0 failures | **667 Passed / 0 Failed** | `PASSED` |
| **Code Formatting & Linting** | Zero errors | **Black formatted & Ruff clean** | `PASSED` |
| **Database Performance Indexes** | Core tables indexed | **20 Active SQLite Indexes** | `PASSED` |

---

## 8. Final Deliverables Archive

All project deliverables are consolidated in `output/final_deliverables/`:

- `nifty100.db`: Master SQLite Database (10 tables, 92 companies)
- `analyst_guide.pdf`: 12-page Analyst Operations Guide
- `portfolio_summary.pdf`: 92-page portfolio tear-card summary PDF
- `tearsheets_bundle/`: 92 individual 2-page company tearsheets
- `sector_reports_bundle/`: 11 sector benchmark PDF reports
- `cashflow_intelligence.xlsx`: CapEx intensity & CFO quality matrix
- `analysis_parsed.csv`: Structured CAGR historical growth numbers
- `pros_cons_generated.csv`: NLP-extracted strengths and weaknesses
- `cluster_labels.csv`: Machine Learning KMeans cluster assignments
- `portfolio_stats.csv`: P10-P90 percentiles across 10 KPIs
- `distress_alerts.csv`: Early warning financial distress alerts
- `perf_notes.md`: Concurrency and latency benchmark notes
- `elbow_plot.png` & `correlation_heatmap.png`: Analytical visualizations
- `openapi.json` & `postman_collection.json`: Complete API specifications
- `pytest_report.html`: Self-contained pytest execution report

---

## 9. License & Team Sign-Off

Developed for **Bluestocks Fintech Internship Project**.  
All rights reserved © 2026.
