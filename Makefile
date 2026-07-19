.PHONY: load ratios test report dashboard api clean help

# Default target
help:
    @echo "Nifty 100 Financial Intelligence Platform"
    @echo "========================================="
    @echo "make load       — Run ETL: load all 12 files into nifty100.db"
    @echo "make ratios     — Run Ratio Engine: compute 50+ KPIs"
    @echo "make test       — Run full pytest suite with HTML report"
    @echo "make report     — Generate all PDF reports"
    @echo "make dashboard  — Start Streamlit dashboard on port 8501"
    @echo "make api        — Start FastAPI server on port 8000"
    @echo "make clean      — Remove __pycache__, .pyc, test artifacts"

load:
    @echo "[S1] Running ETL pipeline..."
    python src/etl/loader.py

ratios:
    @echo "[S2] Computing financial ratios..."
    python src/analytics/ratios.py

test:
    @echo "[TEST] Running pytest suite..."
    pytest tests/ --html=reports/pytest_report.html --tb=short -v

report:
    @echo "[S5] Generating PDF reports..."
    python src/reports/tearsheet.py
    python src/reports/sector_report.py
    python src/reports/portfolio_report.py

dashboard:
    @echo "[DASH] Starting Streamlit..."
    streamlit run src/dashboard/app.py

api:
    @echo "[API] Starting FastAPI server..."
    uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

clean:
    @echo "[CLEAN] Removing build artifacts..."
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
    rm -f tests/reports/*.html 2>/dev/null || true
    @echo "Done. Database and reports preserved."
