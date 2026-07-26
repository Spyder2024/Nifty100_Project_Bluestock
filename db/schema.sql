-- db/schema.sql - Legacy Nifty 100 schema expected by the test suite

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sectors (
    sector_id   TEXT PRIMARY KEY,
    sector_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS companies (
    company_id   TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    sector_id    TEXT REFERENCES sectors(sector_id),
    nse_symbol   TEXT,
    bse_code     TEXT,
    isin         TEXT,
    series       TEXT DEFAULT 'EQ',
    listed_date  TEXT,
    face_value   REAL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS balance_sheet (
    company_id          TEXT NOT NULL REFERENCES companies(company_id),
    year                TEXT NOT NULL,
    total_assets        REAL,
    total_liabilities   REAL,
    total_equity        REAL,
    current_assets      REAL,
    current_liabilities REAL,
    non_current_assets  REAL,
    non_current_liab    REAL,
    inventories         REAL,
    cash_and_equiv      REAL,
    borrowings          REAL,
    other_current_liab  REAL,
    trade_payables      REAL,
    trade_receivables   REAL,
    fixed_assets        REAL,
    investments         REAL,
    reserves            REAL,
    share_capital       REAL,
    bs_balance          REAL GENERATED ALWAYS AS (
        COALESCE(total_assets, 0) - COALESCE(total_liabilities, 0) - COALESCE(total_equity, 0)
    ) VIRTUAL,
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS income_statement (
    company_id     TEXT NOT NULL REFERENCES companies(company_id),
    year           TEXT NOT NULL,
    revenue        REAL,
    operating_income REAL,
    other_income   REAL,
    total_expenses REAL,
    interest_expense REAL,
    depreciation   REAL,
    tax_expense    REAL,
    net_income     REAL,
    eps            REAL,
    opm            REAL,
    npm            REAL,
    ebitda         REAL,
    ebit           REAL,
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS cash_flow (
    company_id      TEXT NOT NULL REFERENCES companies(company_id),
    year            TEXT NOT NULL,
    operating_cf    REAL,
    investing_cf    REAL,
    financing_cf    REAL,
    net_cash_flow   REAL,
    capex           REAL,
    fcf             REAL,
    dividend_paid   REAL,
    buyback_paid    REAL,
    opening_cash    REAL,
    closing_cash    REAL,
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS ratios (
    company_id            TEXT NOT NULL REFERENCES companies(company_id),
    year                  TEXT NOT NULL,
    roe                   REAL,
    roa                   REAL,
    roce                  REAL,
    debt_to_equity        REAL,
    current_ratio         REAL,
    quick_ratio           REAL,
    interest_coverage     REAL,
    asset_turnover        REAL,
    net_profit_margin     REAL,
    opm                   REAL,
    dividend_payout       REAL,
    earning_yield         REAL,
    book_value_per_share  REAL,
    price_to_book         REAL,
    price_to_earnings     REAL,
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS prices (
    company_id  TEXT NOT NULL REFERENCES companies(company_id),
    year        TEXT NOT NULL,
    price_open  REAL,
    price_high  REAL,
    price_low   REAL,
    price_close REAL,
    volume      INTEGER,
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS market_cap (
    company_id     TEXT NOT NULL REFERENCES companies(company_id),
    year           TEXT NOT NULL,
    market_cap     REAL,
    market_cap_cr  REAL,
    free_float_mcap REAL,
    weight_pct     REAL,
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS shareholding (
    company_id    TEXT NOT NULL REFERENCES companies(company_id),
    year          TEXT NOT NULL,
    promoter_pct  REAL,
    fii_pct       REAL,
    dii_pct       REAL,
    public_pct    REAL,
    govt_pct      REAL DEFAULT 0,
    custodian_pct REAL DEFAULT 0,
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS dividends (
    company_id          TEXT NOT NULL REFERENCES companies(company_id),
    year                TEXT NOT NULL,
    dividend_per_share  REAL,
    dividend_yield_pct  REAL,
    dividend_payout_pct REAL,
    total_dividend      REAL,
    ex_date             TEXT,
    record_date         TEXT,
    PRIMARY KEY (company_id, year)
);
