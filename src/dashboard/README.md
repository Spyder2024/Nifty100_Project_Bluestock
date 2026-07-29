
# Nifty-100 Analytical Dashboard

A 9-screen Streamlit dashboard for fundamental analysis of NSE Nifty-100
companies. Built with Python 3.11, Streamlit, Plotly, pandas, and SQLite.

---

## Quick Start

```bash
# Activate virtual environment
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/macOS

# Run the dashboard
streamlit run src/dashboard/Home.py
```

The app opens at `http://localhost:8501`.

---

## Screen Map

| # | File | Screen | What It Does |
|---|------|--------|-------------|
| 01 | `01_home.py` | Home | KPI overview cards, sector breakdown, top movers |
| 02 | `02_profiles.py` | Company Profile | Detailed single-company view — ratios, P&L, BS, CF |
| 03 | `03_screener.py` | Stock Screener | 10-metric slider filters, 6 presets, sortable table, CSV export |
| 04 | `04_peers.py` | Peer Comparison | Radar chart (company vs. sector avg), percentile breakdown |
| 05 | `05_trends.py` | Trends | 12-metric multi-year trend lines with hover details |
| 06 | `06_sectors.py` | Sectors | Bubble chart (ROE vs P/E), bar charts, median KPI table |
| 07 | `07_capital.py` | Capital Allocation | CF grouped bars, FCF vs CapEx, BS structure, treemap, ratios |
| 08 | `08_reports.py` | Reports & Links | External links (NSE, Screener.in, TradingView, etc.), data audit |
| 09 | `09_settings.py` | Settings & QA | Cache management, null audit, DB schema reference, session reset |

---

## Architecture

```
src/dashboard/
├── Home.py                  # Entry point (streamlit run target)
├── utils/
│   ├── db.py                # 10+ @st.cache_data query functions
│   ├── error_handler.py     # Centralized error handling & validation
│   └── qa_runner.py         # Standalone integration QA script
└── pages/
    ├── 01_home.py
    ├── 02_profiles.py
    ├── 03_screener.py
    ├── 04_peers.py
    ├── 05_trends.py
    ├── 06_sectors.py
    ├── 07_capital.py
    ├── 08_reports.py
    └── 09_settings.py
```

### Data Flow

```
SQLite (output/nifty100.db)
    ↓  @st.cache_data(ttl=600)
db.py query functions
    ↓  pandas DataFrames
Page files (Plotly charts + st.dataframe)
    ↓
Streamlit browser UI
```

### Key Design Patterns

- **Every page** adds `sys.path.insert(0, ...)` for multi-page compatibility
- **All DB reads** go through `@st.cache_data(ttl=600)` in `db.py`
- **Error handling** uses `safe_execute()` and `validate_dataframe()` from
  `error_handler.py` instead of raw try/except
- **NaN safety**: Every numeric operation chains `.fillna(0)` before `.abs()`
  or arithmetic (PyArrow `None` guard)
- **Sorting**: Always `na_position="last"` — never `"bottom"`

---

## Database Schema

All data lives in `output/nifty100.db` (SQLite).

| Table | Key Columns |
|-------|------------|
| `companies` | `company_id`, `company_name`, `sector_id`, `sector_name`, `broad_sector` |
| `ratios` | `company_id`, `company_name`, `broad_sector`, `roe`, `net_profit_margin`, `pe_ratio`, `debt_to_equity`, `composite_quality_score`, + more |
| `balance_sheet` | `year`, `company_id`, `total_assets`, `borrowings`, `reserves` |
| `cash_flow` | `year`, `company_id`, `operating_cf`, `investing_cf`, `financing_cf`, `net_cash_flow`, `fcf`, `capex`, `dividend_paid`, `buyback_paid` |

> **Note:** Several columns in `balance_sheet` and `cash_flow` are currently
> unpopulated (ETL gap). See `SPRINT4_RETRO.md` for the full list.

---

## Running the QA Suite

```bash
python src/dashboard/utils/qa_runner.py
```

Tests DB connectivity, all query functions, cross-table consistency,
null coverage, PyArrow dtype safety, and page syntax. Writes a JSON
report to `output/qa_report.json`.

---

## Cache Management

- All DB queries are cached with a 10-minute TTL.
- Press **`C`** on any page to clear all caches.
- Use the **Settings** screen (09) for one-click cache clear and session reset.

---

## Known Gotchas

1. **PyArrow `None` ≠ NaN** — `.abs()` throws `TypeError` on `None`.
   Always chain `.fillna(0)` before numeric ops.
2. **`na_position`** — Only `"first"` or `"last"` are valid. `"bottom"` raises `ValueError`.
3. **`broad_sector`** — Only exists in the `ratios` table, not `companies`.
4. **Table name** — The ratios table is named `ratios`, not `financial_ratios`.
5. **Company identifier** — The `companies` table uses `company_name` as the
   primary text identifier (no `ticker` or `symbol` column).
6. **Percentile method** — Average-rank: `(below + 0.5 * equal) / n * 100`.
   Invert for D/E: `100 - percentile`.
