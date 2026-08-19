# Sprint 5 Retrospective (Days 29–35)

**Sprint Goal:** Build NLP Parsing & Automated Pros/Cons Engine, Cash Flow & Distress Intelligence, and Enterprise-Grade PDF Reporting Suite (2-Page Tearsheets for 92 companies, 11 Sector Benchmark Reports, and 92-page Portfolio Summary PDF).

**Period:** Days 29–35  
**Status:** Completed (100% of deliverables & exit criteria met)

---

## Deliverables Summary

| Day | Scope | Deliverables / Files | Status |
|-----|-------|----------------------|--------|
| **29** | NLP Financial Notes & Analysis Parser | `src/nlp/parser.py`, `output/analysis_parsed.csv` | Done |
| **30** | Automated Pros & Cons Rule Engine (24 Rules) | `src/nlp/pros_cons_generator.py`, `output/pros_cons_generated.csv` | Done |
| **31–32** | Cash Flow Intelligence & Distress Alerts | `src/analytics/cashflow_kpis.py`, `output/cashflow_intelligence.xlsx`, `output/distress_alerts.csv` | Done |
| **33–34** | 2-Page Company Financial Tearsheets (92 Companies) | `src/reports/tearsheet.py`, `reports/tearsheets/*.pdf` (92 PDFs) | Done |
| **34** | Sector Intelligence & Constituent Benchmark Reports | `src/reports/sector_report.py`, `reports/sector/*.pdf` (11 PDFs) | Done |
| **35** | Nifty 100 Portfolio Summary PDF & Sprint Review | `src/reports/portfolio_report.py`, `reports/portfolio/portfolio_summary.pdf` (92 pages) | Done |

---

## Exit Criteria & Definition of Done Audit

| Exit Criterion | Target | Actual Result | Verification Status |
|----------------|--------|---------------|---------------------|
| **Pros/Cons Coverage** | At least 1 pro and 1 con for every company | 92 of 92 companies have both (248 total rules fired) | PASS |
| **Tearsheet Existence & Size** | 92 tearsheets exist in `reports/tearsheets/` and are ≥ 30 KB | 92 PDFs exist, size range: 94.1 KB – 193.7 KB (0 files < 30 KB) | PASS |
| **Tearsheet Visual Quality** | 2 pages each, no text overflow, no blank pages | Verified via PDF canvas parser: exactly 2 pages for all 92 PDFs | PASS |
| **Cashflow Intelligence** | 92 rows with all required columns | 92 rows × 17 columns in `output/cashflow_intelligence.xlsx` | PASS |
| **Sector Reports** | 11 Sector Benchmark PDFs | 11 PDFs generated in `reports/sector/` (10 Sectors + Overview) | PASS |
| **Portfolio Summary PDF** | 1 page per company in alphabetical order by ticker with 6 KPIs & trend arrows | 92 pages in `reports/portfolio/portfolio_summary.pdf` (302.5 KB) | PASS |

---

## Technical Highlights & Key Innovations

### 1. Robust Multi-Table Financial Engine
- Dynamically discovers tables (`companies`, `sectors`, `income_statement`, `balance_sheet`, `cash_flow`, `ratios`, `market_cap`) across heterogeneous SQLite databases.
- Defensive handling for companies with partial historical periods (e.g. `ATGL`, `JIOFIN`, `SBIN`) with zero unhandled exceptions.

### 2. Auto Pros & Cons Generation (24 Financial Rules)
- Evaluates 12 positive investment rules and 12 negative risk rules covering Profitability, Margins, Leverage, Cash Generation, and Dividend History.
- Provides fallback rationale when balance-sheet data is non-standard, guaranteeing 100% complete coverage for all 92 Nifty 100 constituents.

### 3. Cash Flow Quality & Distress Flagging
- Classifies capital allocation patterns (e.g., *Self-Funded Compounder*, *Growth Funded by Debt*, *Capital Returner*).
- Calculates CFO Quality Scores, CapEx Intensity profiles, and Distress Signals (`GREEN`, `AMBER`, `RED`) to identify cash-burn risks.

### 4. Precision ReportLab PDF Generation
- Custom `NumberedCanvas` implementations for dynamic `"Page X of Y"` footers.
- Strict typography and tabular geometry avoiding layout overflow and maintaining clean visual aesthetics across 92 tearsheets and the portfolio summary.
- Trend arrows (`▲`, `▼`, `▶`) with 2% tolerance threshold comparing latest vs prior fiscal year metrics.

---

## Sprint Review & Demo Checklist for Team Lead

1. **3 Sample Tearsheet PDFs:**
   - [TCS Tearsheet (180.3 KB)](file:///d:/COEP%20TECH/COURSE%20WORK/Programming/Bluestocks%20Fintech%20Internship/Nifty100%20Project/reports/tearsheets/TCS_tearsheet.pdf)
   - [HDFCBANK Tearsheet (175.0 KB)](file:///d:/COEP%20TECH/COURSE%20WORK/Programming/Bluestocks%20Fintech%20Internship/Nifty100%20Project/reports/tearsheets/HDFCBANK_tearsheet.pdf)
   - [RELIANCE Tearsheet (171.3 KB)](file:///d:/COEP%20TECH/COURSE%20WORK/Programming/Bluestocks%20Fintech%20Internship/Nifty100%20Project/reports/tearsheets/RELIANCE_tearsheet.pdf)

2. **Cashflow Intelligence Analysis:**
   - [cashflow_intelligence.xlsx (92 companies)](file:///d:/COEP%20TECH/COURSE%20WORK/Programming/Bluestocks%20Fintech%20Internship/Nifty100%20Project/output/cashflow_intelligence.xlsx)
   - [distress_alerts.csv (13 flagged alerts)](file:///d:/COEP%20TECH/COURSE%20WORK/Programming/Bluestocks%20Fintech%20Internship/Nifty100%20Project/output/distress_alerts.csv)

3. **NLP Generated Pros and Cons:**
   - [pros_cons_generated.csv (248 insights)](file:///d:/COEP%20TECH/COURSE%20WORK/Programming/Bluestocks%20Fintech%20Internship/Nifty100%20Project/output/pros_cons_generated.csv)

4. **Sector Intelligence Reports (11 PDFs):**
   - [reports/sector/](file:///d:/COEP%20TECH/COURSE%20WORK/Programming/Bluestocks%20Fintech%20Internship/Nifty100%20Project/reports/sector/)

5. **Portfolio Summary Report (92 pages):**
   - [portfolio_summary.pdf (302.5 KB)](file:///d:/COEP%20TECH/COURSE%20WORK/Programming/Bluestocks%20Fintech%20Internship/Nifty100%20Project/reports/portfolio/portfolio_summary.pdf)
