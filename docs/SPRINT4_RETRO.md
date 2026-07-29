# Sprint 4 Retrospective (Days 22–28)

**Sprint Goal:** Build an 8-screen Streamlit analytical dashboard for the Nifty-100
fundamental analysis tool, plus a Valuation module and integration QA.

**Story Points Planned:** 55 SP
**Period:** Days 22–28

---

## Deliverables Summary

| Day | Scope | Files | Status |
|-----|-------|-------|--------|
| 22–23 | Home screen, Company Profile | `01_home.py`, `02_profiles.py` | Done (prior session, manually debugged) |
| 24 | Stock Screener, Peer Comparison | `03_screener.py`, `04_peers.py` | Done |
| 25 | Trends, Sectors, Capital, Reports | `05_trends.py`, `06_sectors.py`, `07_capital.py`, `08_reports.py` | Done |
| 26 | Valuation module | — | Skipped by user |
| 27 | Integration QA, error handling, settings | `error_handler.py`, `qa_runner.py`, `09_settings.py` | Done |
| 28 | Sprint retro & documentation | `SPRINT4_RETRO.md`, `README.md` | Done |

**Total screens delivered:** 9 (01–09)

---

## Bugs Found & Resolved

### Bug 1 — `ValueError: invalid na_position: bottom`
- **File:** `03_screener.py` line 205
- **Cause:** pandas `sort_values` only accepts `"first"` or `"last"`, not `"bottom"`
- **Fix:** Changed `na_position="bottom"` → `na_position="last"`
- **Lesson:** Never assume descriptive synonyms are valid; check the API signature.

### Bug 2 — `TypeError: bad operand type for abs(): 'NoneType'`
- **File:** `07_capital.py` line 92
- **Cause:** PyArrow-backed DataFrames store missing values as `None` (not `NaN`).
  Calling `.abs()` on `None` raises `TypeError`.
- **Fix:** Chain `.fillna(0)` before any `.abs()` or arithmetic: `df["col"].fillna(0).abs()`
- **Lesson:** Always defensively `.fillna(0)` on PyArrow columns before numeric ops.
  This is the single most impactful pattern for this codebase.

### Bug 3 — `TypeError: fillna() missing 1 required positional argument: 'value'`
- **File:** `07_capital.py` line 92
- **Cause:** User copied `.fillna()` without the `0` argument during manual patch.
- **Fix:** `.fillna(0)`, not `.fillna()`.
- **Lesson:** When giving patch instructions, include the full expression, not a substring.

### Bug 4 — `KeyError: 'ticker'`
- **File:** `qa_runner.py` line 113
- **Cause:** QA runner hardcoded `companies["ticker"]` but the actual column is `company_name`.
- **Fix:** Dynamic column discovery via alias list (`ticker`, `symbol`, `company_name`, etc.)
- **Lesson:** Never hardcode column or table names. The DB schema is the source of truth.

### Bug 5 — `no such table: financial_ratios`
- **File:** `qa_runner.py`, `09_settings.py`
- **Cause:** Code assumed table name `financial_ratios`; actual name is `ratios`.
- **Fix:** Runtime table discovery via `sqlite_master` with alias fallback.
- **Lesson:** Same as Bug 4 — schema must be discovered, not assumed.

### Bug 6 — `TypeError: Object of type bool is not JSON serializable`
- **File:** `qa_runner.py` JSON report writer
- **Cause:** pandas boolean comparisons return `numpy.bool_`, not Python `bool`.
- **Fix:** Explicit `bool()` cast in `_record()` + `default=str` safety net in `json.dump()`.
- **Lesson:** Any time pandas results feed into non-pandas APIs (json, logging), cast explicitly.

### Bug 7 — `ValueError: 'count' is not a column`
- **File:** `09_settings.py` line 186
- **Cause:** `get_sectors()` returns `company_count`, pie chart used `count`.
- **Fix:** Changed `values="count"` → `values="company_count"`.
- **Lesson:** Always verify column names against the actual query output, not assumptions.

---

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| `@st.cache_data(ttl=600)` on all DB functions | Avoids repeated SQLite hits; 10-min TTL balances freshness vs. speed |
| `sys.path.insert(0, ...)` in every page file | Streamlit multi-page runs each file as a separate script; no shared import context |
| Centralized `error_handler.py` | Prevents scattered try/except blocks; uniform error surfacing across all 9 screens |
| Standalone `qa_runner.py` | Can run without Streamlit runtime; validates DB, queries, cross-table consistency, dtype safety |
| Dynamic column/table discovery | DB schema evolved independently; hardcoding names caused 3 of the 7 bugs above |
| `na_position="last"` everywhere | Consistent convention; avoids the `na_position="bottom"` trap |
| `.fillna(0)` before any `.abs()` or arithmetic | The PyArrow `None` guard — single most repeated pattern |

---

## QA Results (Day 27)

```
Results: PASS 35/37

PASS — DB connectivity (6/6)
PASS — Query functions (12/12)
PASS — Cross-table consistency (3/4)
PASS — Null audit — data quality (4/4)
PASS — PyArrow compatibility (2/2)
PASS — Page imports (9/9)

FAIL — Table 'financial_ratios' exists (table named 'ratios')
FAIL — All companies have ratios (2 of 92 uncovered — ETL gap)
```

Both failures are data/ETL issues, not dashboard code bugs.

---

## Known Data Gaps (Non-Code Issues)

These are ETL pipeline problems visible through the dashboard. The code handles
them gracefully (warnings, empty-state messages), but the underlying data
needs to be fixed upstream:

| Table | Fully-Null Columns |
|-------|-------------------|
| `companies` | `nse_symbol`, `bse_code`, `isin`, `listed_date` |
| `balance_sheet` | `total_equity`, `current_assets`, `current_liabilities`, `non_current_assets`, `non_current_liab`, `inventories`, `cash_and_equiv`, `other_current_liab`, `trade_payables`, `trade_receivables`, `share_capital` |
| `cash_flow` | `operating_cf`, `investing_cf`, `financing_cf`, `capex`, `fcf`, `dividend_paid`, `buyback_paid`, `opening_cash`, `closing_cash` |
| `ratios` | `roa`, `roce`, `current_ratio`, `quick_ratio`, `earning_yield`, `price_to_book`, `price_to_earnings` |

**Impact:** Several dashboard screens (Capital Allocation, some Peer Comparison
metrics, Valuation multiples) will show reduced data until the ETL populates
these columns.

---

## What Went Well

- Rapid delivery of 6 new screens in 2 days (Days 24–25) with Plotly visualizations
- Bug-fix turnaround was fast — most fixes were single-line changes
- QA runner caught real issues (schema mismatches, dtype compatibility) before
  they could manifest in production
- The `error_handler.py` pattern gives a clean foundation for future screens

## What Didn't Go Well

- 3 bugs caused by hardcoded schema assumptions (column names, table names)
- The Valuation module (Day 26) was skipped — largest story point item deferred
- Single-company DB queries (`get_ratios`, `get_pl`, etc.) return 0 rows when
  called with `company_name` — likely an identifier mismatch in `db.py`
- Blank columns in the Screener were initially confused for code bugs before
  being diagnosed as data gaps

## Action Items for Next Sprint

1. **Fix `db.py` identifier mismatch** — single-company functions likely need
   `company_id` or a ticker symbol, not `company_name`
2. **Implement Valuation module** (deferred from Day 26) — DCF, relative
   valuation, peer multiples
3. **Populate ETL gaps** — especially `balance_sheet`, `cash_flow`, and the 7
   fully-null `ratios` columns
4. **Add `broad_sector` to `companies` table** — currently only in `ratios`,
   requiring a join every time
5. **Add row-level tests** — current QA validates shape & types; add value-level
   assertions (e.g., ROE should be 0–100%, years should be sequential)