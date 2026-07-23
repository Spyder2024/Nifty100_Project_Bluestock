-- db/schema.sql — Full Nifty 100 schema (10 tables)
-- Sprint 2 Day 12: Complete DDL for all source + output tables

-- 1. Companies master
CREATE TABLE IF NOT EXISTS companies (
    id            TEXT PRIMARY KEY,          -- NSE ticker (TCS, RELIANCE, ...)
    company_name  TEXT NOT NULL,
    company_logo  TEXT,
    chart_link    TEXT,
    about_company TEXT,
    website       TEXT,
    nse_profile   TEXT,
    bse_profile   TEXT,
    face_value    REAL DEFAULT 1,
    book_value    REAL,
    roce_percentage REAL,
    roe_percentage REAL
);

-- 2. Income Statement (loaded from profitandloss.xlsx)
CREATE TABLE IF NOT EXISTS income_statement (
    company_id           TEXT NOT NULL,
    year                 TEXT NOT NULL,
    sales                REAL,
    expenses             REAL,
    operating_profit     REAL,
    opm_percentage       REAL,
    other_income         REAL,
    interest             REAL,
    depreciation         REAL,
    profit_before_tax    REAL,
    tax_percentage       REAL,
    net_profit           REAL,
    eps                  REAL,
    dividend_payout      REAL,
    PRIMARY KEY (company_id, year)
);

-- 3. Balance Sheet (loaded from balancesheet.xlsx)
CREATE TABLE IF NOT EXISTS balance_sheet (
    company_id           TEXT NOT NULL,
    year                 TEXT NOT NULL,
    equity_capital       REAL,
    reserves             REAL,
    borrowings           REAL,
    other_liabilities    REAL,
    total_liabilities    REAL,
    fixed_assets         REAL,
    cwip                 REAL,
    investments          REAL,
    other_asset          REAL,
    total_assets         REAL,
    PRIMARY KEY (company_id, year)
);

-- 4. Cash Flow (loaded from cashflow.xlsx)
CREATE TABLE IF NOT EXISTS cash_flow (
    company_id           TEXT NOT NULL,
    year                 TEXT NOT NULL,
    operating_activity   REAL,
    investing_activity   REAL,
    financing_activity   REAL,
    net_cash_flow        REAL,
    PRIMARY KEY (company_id, year)
);

-- 5. Financial Ratios (computed by ratio_runner.py)
CREATE TABLE IF NOT EXISTS financial_ratios (
    company_id                  TEXT NOT NULL,
    year                        TEXT NOT NULL,
    net_profit_margin_pct       REAL,
    operating_profit_margin_pct REAL,
    return_on_equity_pct        REAL,
    return_on_capital_employed_pct REAL,
    return_on_assets_pct        REAL,
    debt_to_equity              REAL,
    interest_coverage           REAL,
    is_high_leverage            INTEGER DEFAULT 0,
    is_low_icr_warning          INTEGER DEFAULT 0,
    net_debt_cr                 REAL,
    asset_turnover              REAL,
    free_cash_flow_cr           REAL,
    capex_intensity             REAL,
    fcf_conversion_rate         REAL,
    cfo_quality_score           REAL,
    capital_allocation_pattern  TEXT,
    earnings_per_share          REAL,
    book_value_per_share        REAL,
    dividend_payout_ratio_pct   REAL,
    total_debt_cr               REAL,
    cash_from_operations_cr     REAL,
    revenue_cagr_3yr            REAL,
    revenue_cagr_5yr            REAL,
    revenue_cagr_10yr           REAL,
    pat_cagr_3yr                REAL,
    pat_cagr_5yr                REAL,
    pat_cagr_10yr               REAL,
    eps_cagr_3yr                REAL,
    eps_cagr_5yr                REAL,
    eps_cagr_10yr               REAL,
    composite_quality_score     REAL,
    PRIMARY KEY (company_id, year)
);

-- 6. Sectors mapping
CREATE TABLE IF NOT EXISTS sectors (
    company_id          TEXT PRIMARY KEY,
    broad_sector        TEXT,
    sub_sector          TEXT,
    index_weight_pct    REAL,
    market_cap_category TEXT
);

-- 7. Stock Prices (monthly OHLCV)
CREATE TABLE IF NOT EXISTS stock_prices (
    company_id     TEXT NOT NULL,
    date           TEXT NOT NULL,
    open_price     REAL,
    high_price     REAL,
    low_price      REAL,
    close_price    REAL,
    volume         INTEGER,
    adjusted_close REAL,
    PRIMARY KEY (company_id, date)
);

-- 8. Market Cap (annual valuation multiples)
CREATE TABLE IF NOT EXISTS market_cap (
    company_id           TEXT NOT NULL,
    year                 INTEGER NOT NULL,
    market_cap_crore     REAL,
    enterprise_value_crore REAL,
    pe_ratio             REAL,
    pb_ratio             REAL,
    ev_ebitda            REAL,
    dividend_yield_pct   REAL,
    PRIMARY KEY (company_id, year)
);

-- 9. Documents (annual report links)
CREATE TABLE IF NOT EXISTS documents (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id     TEXT NOT NULL,
    Year           INTEGER NOT NULL,
    Annual_Report  TEXT
);

-- 10. Pros and Cons
CREATE TABLE IF NOT EXISTS prosandcons (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL,
    pros       TEXT,
    cons       TEXT
);

-- 11. Peer Groups (M:N)
CREATE TABLE IF NOT EXISTS peer_groups (
    peer_group_name TEXT NOT NULL,
    company_id      TEXT NOT NULL,
    is_benchmark    INTEGER DEFAULT 0,
    PRIMARY KEY (peer_group_name, company_id)
);