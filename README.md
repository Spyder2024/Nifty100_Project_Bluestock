# Nifty 100 Financial Intelligence Platform

A production-grade financial analytics system for 92 Nifty 100 companies.

## Quick Start

\`\`\`bash
# 1. Create & activate virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.template .env

# 4. Build database (ETL)
make load

# 5. Compute KPIs
make ratios

# 6. Run tests
make test

# 7. Start dashboard
make dashboard

# 8. Start API
make api
\`\`\`

## Project Structure

| Path | Purpose |
|------|---------|
| `data/raw/` | 7 core Excel files (READ ONLY) |
| `data/supporting/` | 5 supplementary Excel files |
| `data/nifty100.db` | SQLite database (10 tables) |
| `src/etl/` | ETL pipeline: loader, validator, normaliser |
| `src/analytics/` | Ratio engine, screener, peer comparison |
| `src/dashboard/` | Streamlit web application (8 screens) |
| `src/api/` | FastAPI REST server (16 endpoints) |
| `src/reports/` | PDF/Excel report generators |
| `tests/` | pytest test suite (60+ tests) |
| `config/` | YAML configs, .env templates |
| `reports/` | Generated PDF reports |

## Tech Stack

pandas · numpy · scipy · scikit-learn · plotly · streamlit · fastapi · reportlab · pytest · sqlite

## Version

v1.0 | 45-Day Sprint Plan | 6 Sprints × 7 Days
