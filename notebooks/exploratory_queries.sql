-- Sprint 1: Exploratory SQL Queries on Nifty 100 Financials
-- Query 1: Total companies by sector
SELECT s.sector_name, COUNT(c.company_id) AS company_count
FROM companies c
JOIN sectors s ON c.sector_id = s.sector_id
GROUP BY s.sector_name
ORDER BY company_count DESC;

-- Query 2: Top 10 High Quality Compounders by ROE (FY24)
SELECT r.company_id, c.company_name, s.sector_name, r.roe, r.roce, r.debt_to_equity
FROM ratios r
JOIN companies c ON r.company_id = c.company_id
JOIN sectors s ON c.sector_id = s.sector_id
WHERE r.year = '2024' AND r.roe IS NOT NULL
ORDER BY r.roe DESC
LIMIT 10;

-- Query 3: Low Debt High FCF Champions
SELECT r.company_id, c.company_name, r.debt_to_equity, cf.fcf AS free_cash_flow
FROM ratios r
JOIN companies c ON r.company_id = c.company_id
JOIN cash_flow cf ON r.company_id = cf.company_id AND r.year = cf.year
WHERE r.year = '2024' AND r.debt_to_equity <= 0.1 AND cf.fcf > 1000
ORDER BY cf.fcf DESC;
