"""src/reports/analyst_guide_generator.py — Nifty 100 Financial Intelligence Analyst Guide Generator.

Sprint 7, Day 44

Generates docs/analyst_guide.pdf (at least 10 pages) containing:
1. Cover Page & Executive Overview
2. Table of Contents & Architectural Overview
3. Streamlit Dashboard Navigation & Page Walkthrough
4. Stock Screener Engine, Sliders & Strategy Presets
5. Deep-Dive Company Profiles & 6-Year Financials
6. Peer Group Analytics & 8-Axis Radar Chart Interpretation
7. Machine Learning Clustering & Anomaly Profiling
8. Automated PDF Tearsheet & Sector Report Generation
9. FastAPI REST API Integration & curl Commands
10. Data Quality Governance (16 Rules) & Validation
11. Troubleshooting Common Errors, FAQ & System Ops

Usage:
    python -m src.reports.analyst_guide_generator
"""

from __future__ import annotations

import logging
from pathlib import Path
import time
from typing import Any, List

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = PROJECT_ROOT / "docs"
OUTPUT_PDF_PATH = DOCS_DIR / "analyst_guide.pdf"

# ── Color Palette ─────────────────────────────────────────────────────────────
NAVY = colors.HexColor("#0f172a")
SLATE_BLUE = colors.HexColor("#1e293b")
ACCENT_BLUE = colors.HexColor("#2563eb")
TEAL = colors.HexColor("#0d9488")
LIGHT_BG = colors.HexColor("#f8fafc")
CARD_BG = colors.HexColor("#f1f5f9")
BORDER_COLOR = colors.HexColor("#cbd5e1")
TEXT_DARK = colors.HexColor("#0f172a")
TEXT_MUTED = colors.HexColor("#475569")
WHITE = colors.HexColor("#ffffff")
CODE_BG = colors.HexColor("#1e1e2e")
CODE_TEXT = colors.HexColor("#a6accd")


class NumberedCanvas(canvas.Canvas):
    """Canvas that performs two passes to compute total page count and draw running headers/footers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count: int):
        if self._pageNumber == 1:
            return  # Skip cover page

        self.saveState()

        # Header
        self.setStrokeColor(BORDER_COLOR)
        self.setLineWidth(0.5)
        self.line(40, A4[1] - 40, A4[0] - 40, A4[1] - 40)

        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(SLATE_BLUE)
        self.drawString(
            40,
            A4[1] - 34,
            "BLUESTOCKS FINTECH  |  NIFTY 100 FINANCIAL INTELLIGENCE PLATFORM",
        )
        self.setFont("Helvetica-Oblique", 8)
        self.setFillColor(TEXT_MUTED)
        self.drawRightString(
            A4[0] - 40, A4[1] - 34, "Analyst & Engineering Operations Guide"
        )

        # Footer
        self.line(40, 45, A4[0] - 40, 45)
        self.setFont("Helvetica", 8)
        self.drawString(
            40, 32, "CONFIDENTIAL  |  Internal Equity Research & API Manual"
        )
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(A4[0] - 40, 32, page_str)

        self.restoreState()


def build_styles():
    """Create custom stylesheet for clean typography."""
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            "CoverTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=32,
            textColor=WHITE,
            alignment=TA_LEFT,
        )
    )

    styles.add(
        ParagraphStyle(
            "CoverSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#93c5fd"),
            alignment=TA_LEFT,
        )
    )

    styles.add(
        ParagraphStyle(
            "CoverMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=14,
            textColor=colors.HexColor("#cbd5e1"),
            alignment=TA_LEFT,
        )
    )

    styles.add(
        ParagraphStyle(
            "DocHeading1",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=NAVY,
            spaceBefore=14,
            spaceAfter=8,
            keepWithNext=True,
        )
    )

    styles.add(
        ParagraphStyle(
            "DocHeading2",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=ACCENT_BLUE,
            spaceBefore=10,
            spaceAfter=6,
            keepWithNext=True,
        )
    )

    styles.add(
        ParagraphStyle(
            "DocHeading3",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            textColor=SLATE_BLUE,
            spaceBefore=6,
            spaceAfter=4,
            keepWithNext=True,
        )
    )

    styles.add(
        ParagraphStyle(
            "DocBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12.5,
            textColor=TEXT_DARK,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        )
    )

    styles.add(
        ParagraphStyle(
            "DocBodyBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=12.5,
            textColor=TEXT_DARK,
        )
    )

    styles.add(
        ParagraphStyle(
            "BulletText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=TEXT_DARK,
            leftIndent=12,
            spaceAfter=3,
        )
    )

    styles.add(
        ParagraphStyle(
            "CodeText",
            parent=styles["Normal"],
            fontName="Courier",
            fontSize=7.5,
            leading=10.5,
            textColor=CODE_TEXT,
        )
    )

    styles.add(
        ParagraphStyle(
            "CalloutBoxText",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=12,
            textColor=SLATE_BLUE,
        )
    )

    styles.add(
        ParagraphStyle(
            "TableHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=WHITE,
            alignment=TA_LEFT,
        )
    )

    styles.add(
        ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=TEXT_DARK,
        )
    )

    return styles


def create_callout(text: str, styles, title: str = "PRO TIP") -> Table:
    """Create a formatted callout card."""
    content = [
        Paragraph(f"<b>{title}:</b> {text}", styles["CalloutBoxText"]),
    ]
    t = Table([[content]], colWidths=[515])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
                ("BOX", (0, 0), (-1, -1), 1, ACCENT_BLUE),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return t


def create_code_block(code_str: str, styles) -> Table:
    """Create a formatted terminal/code box."""
    code_lines = [
        Paragraph(line.replace(" ", "&nbsp;"), styles["CodeText"])
        for line in code_str.strip().split("\n")
    ]
    t = Table([[code_lines]], colWidths=[515])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def build_analyst_guide_pdf(output_path: Path = OUTPUT_PDF_PATH) -> Path:
    """Compile the complete 11-page analyst guide PDF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=50,
        bottomMargin=50,
    )

    styles = build_styles()
    story: List[Any] = []

    # =========================================================================
    # PAGE 1: COVER PAGE
    # =========================================================================
    cover_data = [
        [Spacer(1, 30)],
        [Paragraph("BLUESTOCKS FINTECH RESEARCH", styles["CoverSubtitle"])],
        [Spacer(1, 10)],
        [
            Paragraph(
                "NIFTY 100 FINANCIAL INTELLIGENCE<br/>ANALYST & ENGINEERING GUIDE",
                styles["CoverTitle"],
            )
        ],
        [Spacer(1, 15)],
        [
            Paragraph(
                "Comprehensive Operations Manual for Financial Screening, Multi-Year Valuation, Machine Learning Clustering, Automated PDF Tearsheets, and High-Throughput REST APIs.",
                styles["CoverSubtitle"],
            )
        ],
        [Spacer(1, 80)],
        [HRFlowable(width="100%", thickness=2, color=ACCENT_BLUE, spaceAfter=20)],
        [Paragraph("<b>Version:</b> 1.0.0 (Production Release)", styles["CoverMeta"])],
        [
            Paragraph(
                "<b>Author:</b> Quantitative Systems & Financial Engineering Group",
                styles["CoverMeta"],
            )
        ],
        [Paragraph(f"<b>Published:</b> {time.strftime('%B %Y')}", styles["CoverMeta"])],
        [
            Paragraph(
                "<b>Target Audience:</b> Equity Analysts, Portfolio Managers, Data Engineers & API Consumers",
                styles["CoverMeta"],
            )
        ],
        [Spacer(1, 40)],
    ]
    cover_table = Table(cover_data, colWidths=[515])
    cover_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 30),
                ("RIGHTPADDING", (0, 0), (-1, -1), 30),
                ("TOPPADDING", (0, 0), (-1, -1), 20),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
            ]
        )
    )
    story.append(cover_table)
    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: TABLE OF CONTENTS & ARCHITECTURAL OVERVIEW
    # =========================================================================
    story.append(
        Paragraph("Table of Contents & Architecture Overview", styles["DocHeading1"])
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=10)
    )

    toc_data = [
        [
            Paragraph("<b>Section</b>", styles["TableHeader"]),
            Paragraph("<b>Module Description</b>", styles["TableHeader"]),
            Paragraph("<b>Page</b>", styles["TableHeader"]),
        ],
        [
            Paragraph("1. System Architecture", styles["TableCell"]),
            Paragraph(
                "Data pipeline, normalization, analytical engine & dual interfaces",
                styles["TableCell"],
            ),
            Paragraph("Page 2", styles["TableCell"]),
        ],
        [
            Paragraph("2. Streamlit Dashboard Guide", styles["TableCell"]),
            Paragraph(
                "Comprehensive UI breakdown: 9 screens, navigation & workflow",
                styles["TableCell"],
            ),
            Paragraph("Page 3", styles["TableCell"]),
        ],
        [
            Paragraph("3. Stock Screener Engine", styles["TableCell"]),
            Paragraph(
                "10-metric filtering, preset strategies, custom thresholds & export",
                styles["TableCell"],
            ),
            Paragraph("Page 4", styles["TableCell"]),
        ],
        [
            Paragraph("4. Company Financial Profiles", styles["TableCell"]),
            Paragraph(
                "6-year P&L, balance sheet, cash flow statements & DuPont ratios",
                styles["TableCell"],
            ),
            Paragraph("Page 5", styles["TableCell"]),
        ],
        [
            Paragraph("5. Peer Group & Radar Analytics", styles["TableCell"]),
            Paragraph(
                "11 sector peer groups, percentile ranks & 8-axis radar comparison",
                styles["TableCell"],
            ),
            Paragraph("Page 6", styles["TableCell"]),
        ],
        [
            Paragraph("6. Machine Learning Clustering", styles["TableCell"]),
            Paragraph(
                "KMeans 5-cluster profiling, elbow curve analysis & Z-score outliers",
                styles["TableCell"],
            ),
            Paragraph("Page 7", styles["TableCell"]),
        ],
        [
            Paragraph("7. Automated PDF Reporting", styles["TableCell"]),
            Paragraph(
                "Batch generation: 92 company tearsheets, 11 sector PDFs & summary",
                styles["TableCell"],
            ),
            Paragraph("Page 8", styles["TableCell"]),
        ],
        [
            Paragraph("8. FastAPI REST Reference", styles["TableCell"]),
            Paragraph(
                "REST endpoints, OpenAPI schema, authentication & curl examples",
                styles["TableCell"],
            ),
            Paragraph("Page 9", styles["TableCell"]),
        ],
        [
            Paragraph("9. Data Quality Framework", styles["TableCell"]),
            Paragraph(
                "16 automated DQ validation rules, severity tiers & quarantine audits",
                styles["TableCell"],
            ),
            Paragraph("Page 10", styles["TableCell"]),
        ],
        [
            Paragraph("10. Troubleshooting & Operations", styles["TableCell"]),
            Paragraph(
                "Common operational errors, port configuration, FAQ & system startup",
                styles["TableCell"],
            ),
            Paragraph("Page 11", styles["TableCell"]),
        ],
    ]
    t_toc = Table(toc_data, colWidths=[120, 335, 60])
    t_toc.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_toc)
    story.append(Spacer(1, 12))

    story.append(Paragraph("System Architecture Overview", styles["DocHeading2"]))
    story.append(
        Paragraph(
            "The Nifty 100 Financial Intelligence Platform is engineered as an enterprise-grade equity analysis "
            "and quantitative research environment. It ingests raw multi-year financial statements across all 92 active "
            "Nifty 100 constituents, normalizes disparate accounting conventions across 11 sectors, computes 30+ fundamental "
            "KPIs, applies machine learning clustering, and serves the structured knowledge through a Streamlit Web Application "
            "and a high-performance FastAPI REST server.",
            styles["DocBody"],
        )
    )

    arch_rows = [
        [
            Paragraph("<b>Layer</b>", styles["TableHeader"]),
            Paragraph("<b>Components & Technologies</b>", styles["TableHeader"]),
            Paragraph("<b>Core Responsibility</b>", styles["TableHeader"]),
        ],
        [
            Paragraph("Data Storage", styles["TableCell"]),
            Paragraph(
                "SQLite 3 (<code>output/nifty100.db</code>) with 20 performance indexes",
                styles["TableCell"],
            ),
            Paragraph(
                "ACID-compliant storage of statements, ratios, prices and metadata",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Analytics Core", styles["TableCell"]),
            Paragraph("Pandas, NumPy, Scikit-Learn, SciPy", styles["TableCell"]),
            Paragraph(
                "KPI ratios, CAGR growth, KMeans clustering, percentile rankings",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Reporting Engine", styles["TableCell"]),
            Paragraph("ReportLab, Matplotlib, Seaborn", styles["TableCell"]),
            Paragraph(
                "Automated 2-page tearsheets, sector deep-dives, correlation heatmaps",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("API Gateway", styles["TableCell"]),
            Paragraph("FastAPI, Starlette, Uvicorn (Port 8000)", styles["TableCell"]),
            Paragraph(
                "Sub-15ms REST API serving JSON and streaming binary PDF assets",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Interactive UI", styles["TableCell"]),
            Paragraph("Streamlit Multi-Page App (Port 8501)", styles["TableCell"]),
            Paragraph(
                "Dynamic screening, radar visualisations, and financial statement exploration",
                styles["TableCell"],
            ),
        ],
    ]
    t_arch = Table(arch_rows, colWidths=[85, 215, 215])
    t_arch.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_arch)
    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: STREAMLIT DASHBOARD GUIDE
    # =========================================================================
    story.append(
        Paragraph("Streamlit Dashboard Navigation Guide", styles["DocHeading1"])
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=10)
    )
    story.append(
        Paragraph(
            "The Streamlit dashboard offers an intuitive, reactive web interface designed for research analysts. "
            "Accessible locally at <code>http://localhost:8501</code>, the interface is split into 9 specialized pages "
            "accessible via the left sidebar.",
            styles["DocBody"],
        )
    )

    screens_data = [
        [
            Paragraph("<b>Screen Name</b>", styles["TableHeader"]),
            Paragraph("<b>Primary Capabilities</b>", styles["TableHeader"]),
            Paragraph("<b>Key Visualizations & Outputs</b>", styles["TableHeader"]),
        ],
        [
            Paragraph("<b>01_home.py</b><br/>Executive Overview", styles["TableCell"]),
            Paragraph(
                "High-level market snapshot, Nifty 100 coverage, broad sector breakdowns, aggregate median ROE, P/E, and D/E metrics.",
                styles["TableCell"],
            ),
            Paragraph(
                "KPI summary cards, sector distribution bar chart, top 5 ROE leaders table.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>02_profiles.py</b><br/>Company Profile", styles["TableCell"]),
            Paragraph(
                "Deep-dive company tearsheet view. Select any company ticker to view multi-year financial statements, ratios, and summary metrics.",
                styles["TableCell"],
            ),
            Paragraph(
                "P&L table, balance sheet, cash flows, DuPont ROE breakdown, CAGR growth charts.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>03_screener.py</b><br/>Stock Screener", styles["TableCell"]),
            Paragraph(
                "Multi-metric filtering engine across 10 KPI dimensions with preset investment strategies and customizable sliders.",
                styles["TableCell"],
            ),
            Paragraph(
                "Filtered results table, composite score ranking, direct CSV export button.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<b>04_peers.py</b><br/>Peer Group Analysis", styles["TableCell"]
            ),
            Paragraph(
                "Compare companies within any of the 11 sector peer groups with relative percentile rankings.",
                styles["TableCell"],
            ),
            Paragraph(
                "8-Axis interactive Radar comparison chart vs sector average and benchmark.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>05_trends.py</b><br/>Historical Trends", styles["TableCell"]),
            Paragraph(
                "Longitudinal time-series analysis (FY2019 to FY2024) of operating margins, revenue compounding, and free cash flow generation.",
                styles["TableCell"],
            ),
            Paragraph(
                "Interactive Plotly line charts, CAGR acceleration markers, margin expansion bars.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>06_sectors.py</b><br/>Sector Deep-Dive", styles["TableCell"]),
            Paragraph(
                "Cross-sector benchmark comparison comparing median valuations, leverage ratios, and capital expenditure intensities.",
                styles["TableCell"],
            ),
            Paragraph(
                "Sector P/E vs ROE scatter plots, median leverage boxplots, constituent tables.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<b>07_capital.py</b><br/>Capital Allocation", styles["TableCell"]
            ),
            Paragraph(
                "Analysis of cash conversion, free cash flow generation, CFO quality scores, and debt servicing safety margins.",
                styles["TableCell"],
            ),
            Paragraph(
                "CFO vs PAT reconciliation waterfall, CapEx reinvestment rate bar charts.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>08_reports.py</b><br/>Report Center", styles["TableCell"]),
            Paragraph(
                "Central repository to download generated PDF company tearsheets, sector reports, and portfolio summaries.",
                styles["TableCell"],
            ),
            Paragraph(
                "Instant PDF downloads, batch report generation trigger, file status matrix.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<b>09_settings.py</b><br/>Settings & Audit", styles["TableCell"]
            ),
            Paragraph(
                "System diagnostics, database health metrics, cache invalidation, and data quality rule validation audit logs.",
                styles["TableCell"],
            ),
            Paragraph(
                "Table row counts, cache clear button, DQ violation tables, environment status.",
                styles["TableCell"],
            ),
        ],
    ]
    t_screens = Table(screens_data, colWidths=[110, 205, 200])
    t_screens.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_screens)
    story.append(Spacer(1, 10))

    story.append(
        create_callout(
            "To quickly navigate between company profiles, use the search dropdown on <code>02_profiles.py</code>. "
            "The application leverages Streamlit's <code>@st.cache_data</code> with a 10-minute TTL to ensure instantaneous tab switching.",
            styles,
            title="DASHBOARD PRODUCTIVITY TIP",
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 4: STOCK SCREENER ENGINE
    # =========================================================================
    story.append(
        Paragraph("Stock Screener Engine & Strategy Presets", styles["DocHeading1"])
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=10)
    )
    story.append(
        Paragraph(
            "The Stock Screener (<code>03_screener.py</code>) allows analysts to filter all 92 companies simultaneously "
            "across 10 fundamental metrics. The screener computes a composite rank score to identify the most compelling ideas.",
            styles["DocBody"],
        )
    )

    story.append(Paragraph("10 Supported Filtering Dimensions", styles["DocHeading2"]))
    metrics_info = [
        [
            Paragraph("<b>Metric Name</b>", styles["TableHeader"]),
            Paragraph("<b>Default Range</b>", styles["TableHeader"]),
            Paragraph("<b>Direction</b>", styles["TableHeader"]),
            Paragraph(
                "<b>Financial Rationale & Significance</b>", styles["TableHeader"]
            ),
        ],
        [
            Paragraph("Return on Equity (ROE)", styles["TableCell"]),
            Paragraph("0% to 100%", styles["TableCell"]),
            Paragraph("Min (Floor)", styles["TableCell"]),
            Paragraph(
                "Measures profitability on shareholders' equity base.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Return on Capital Employed (ROCE)", styles["TableCell"]),
            Paragraph("0% to 100%", styles["TableCell"]),
            Paragraph("Min (Floor)", styles["TableCell"]),
            Paragraph(
                "Measures operating efficiency of total capital allocated.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Debt-to-Equity (D/E)", styles["TableCell"]),
            Paragraph("0.0 to 5.0", styles["TableCell"]),
            Paragraph("Max (Ceiling)", styles["TableCell"]),
            Paragraph(
                "Filters balance sheet solvency and financial leverage risk.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Price-to-Earnings (P/E)", styles["TableCell"]),
            Paragraph("0.0 to 150.0", styles["TableCell"]),
            Paragraph("Max (Ceiling)", styles["TableCell"]),
            Paragraph(
                "Identifies valuation multiples relative to trailing earnings.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Price-to-Book (P/B)", styles["TableCell"]),
            Paragraph("0.0 to 50.0", styles["TableCell"]),
            Paragraph("Max (Ceiling)", styles["TableCell"]),
            Paragraph(
                "Assesses market valuation against net asset value.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Net Profit Margin (NPM)", styles["TableCell"]),
            Paragraph("-20% to 50%", styles["TableCell"]),
            Paragraph("Min (Floor)", styles["TableCell"]),
            Paragraph(
                "Ensures pricing power and bottom-line margin strength.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Current Ratio", styles["TableCell"]),
            Paragraph("0.0 to 10.0", styles["TableCell"]),
            Paragraph("Min (Floor)", styles["TableCell"]),
            Paragraph(
                "Validates short-term liquidity and working capital coverage.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Revenue CAGR 5-Year", styles["TableCell"]),
            Paragraph("-10% to 50%", styles["TableCell"]),
            Paragraph("Min (Floor)", styles["TableCell"]),
            Paragraph(
                "Ensures sustained multi-year top-line business growth.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Dividend Payout", styles["TableCell"]),
            Paragraph("0% to 100%", styles["TableCell"]),
            Paragraph("Min (Floor)", styles["TableCell"]),
            Paragraph(
                "Evaluates cash returned to shareholders via dividends.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("Earnings Yield", styles["TableCell"]),
            Paragraph("0% to 25%", styles["TableCell"]),
            Paragraph("Min (Floor)", styles["TableCell"]),
            Paragraph(
                "Inverse P/E metric reflecting baseline earnings return.",
                styles["TableCell"],
            ),
        ],
    ]
    t_metrics = Table(metrics_info, colWidths=[120, 75, 65, 255])
    t_metrics.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ]
        )
    )
    story.append(t_metrics)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Built-in Strategy Presets", styles["DocHeading2"]))
    presets_table = [
        [
            Paragraph("<b>Preset Strategy</b>", styles["TableHeader"]),
            Paragraph("<b>Filter Configuration</b>", styles["TableHeader"]),
            Paragraph("<b>Ideal Investment Objective</b>", styles["TableHeader"]),
        ],
        [
            Paragraph("<b>Quality Compounders</b>", styles["TableCell"]),
            Paragraph("ROE >= 15%, D/E <= 0.5, Rev CAGR >= 10%", styles["TableCell"]),
            Paragraph(
                "Long-term wealth creation in blue-chip market leaders.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>Debt-Free Champions</b>", styles["TableCell"]),
            Paragraph("D/E == 0.0, ROE >= 15%, NPM >= 12%", styles["TableCell"]),
            Paragraph(
                "Zero solvency risk compounders resilient to rate cycles.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>High-Growth Momentum</b>", styles["TableCell"]),
            Paragraph("Rev CAGR >= 15%, PAT CAGR >= 15%", styles["TableCell"]),
            Paragraph(
                "Rapidly scaling mid/large caps with high earnings momentum.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>Deep Value / Safety Margin</b>", styles["TableCell"]),
            Paragraph("P/E <= 25, FCF >= 100 Cr, D/E <= 1.0", styles["TableCell"]),
            Paragraph(
                "Undervalued cash generators with substantial margin of safety.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>Free Cash Flow Machines</b>", styles["TableCell"]),
            Paragraph("FCF >= 1,000 Cr, ROE >= 12%", styles["TableCell"]),
            Paragraph(
                "Cash-rich defensive businesses with strong capital return.",
                styles["TableCell"],
            ),
        ],
    ]
    t_presets = Table(presets_table, colWidths=[130, 185, 200])
    t_presets.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_presets)
    story.append(PageBreak())

    # =========================================================================
    # PAGE 5: COMPANY FINANCIAL PROFILES
    # =========================================================================
    story.append(
        Paragraph("Company Financial Profiles & Statements", styles["DocHeading1"])
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=10)
    )
    story.append(
        Paragraph(
            "The Company Profile screen (<code>02_profiles.py</code>) provides complete financial transparency for every "
            "company across 6 fiscal years (FY2019 to FY2024). The interface combines normalized financial statements with "
            "calculated financial ratios.",
            styles["DocBody"],
        )
    )

    story.append(Paragraph("1. Normalized Statement Structure", styles["DocHeading2"]))
    story.append(
        Paragraph(
            "Disparate accounting disclosures have been harmonized into canonical financial tables in SQLite:",
            styles["DocBody"],
        )
    )

    stmts_summary = [
        [
            Paragraph("<b>Statement</b>", styles["TableHeader"]),
            Paragraph("<b>Key Extracted Line Items</b>", styles["TableHeader"]),
            Paragraph("<b>Analytical Insights</b>", styles["TableHeader"]),
        ],
        [
            Paragraph("<b>Income Statement</b><br/>(P&L)", styles["TableCell"]),
            Paragraph(
                "Revenue (Net Sales), Operating Income, Total Expenses, EBITDA, EBIT, Interest Expense, Depreciation, Tax Expense, Net Income (PAT), EPS.",
                styles["TableCell"],
            ),
            Paragraph(
                "Operating margin trend, operating leverage, tax efficiency, and bottom-line earnings quality.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>Balance Sheet</b>", styles["TableCell"]),
            Paragraph(
                "Total Equity, Share Capital, Reserves & Surplus, Total Debt (Long + Short Term), Total Assets, Current Assets, Current Liabilities, Net Fixed Assets.",
                styles["TableCell"],
            ),
            Paragraph(
                "Solvency, working capital intensity, net debt trajectory, and asset base expansion.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>Cash Flow Statement</b>", styles["TableCell"]),
            Paragraph(
                "Operating Cash Flow (CFO), Capital Expenditure (CapEx), Investing Cash Flow (CFI), Financing Cash Flow (CFF), Free Cash Flow (FCF = CFO - CapEx).",
                styles["TableCell"],
            ),
            Paragraph(
                "Cash conversion ratio (CFO / PAT), organic FCF yield, dividend sustainability.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>Valuation & Multiples</b>", styles["TableCell"]),
            Paragraph(
                "Market Capitalisation, Enterprise Value (EV), P/E Ratio, P/B Ratio, EV/EBITDA, Dividend Yield.",
                styles["TableCell"],
            ),
            Paragraph(
                "Historical multiple expansion/compression across market cycles.",
                styles["TableCell"],
            ),
        ],
    ]
    t_stmts = Table(stmts_summary, colWidths=[110, 205, 200])
    t_stmts.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_stmts)
    story.append(Spacer(1, 10))

    story.append(Paragraph("2. DuPont ROE Decomposition Model", styles["DocHeading2"]))
    story.append(
        Paragraph(
            "To diagnose whether high Return on Equity is driven by operating efficiency or balance sheet leverage, "
            "the profile screen evaluates the classic 3-Stage DuPont Decomposition formula:",
            styles["DocBody"],
        )
    )

    dupont_code = """ROE = (Net Profit Margin) x (Asset Turnover) x (Equity Multiplier)
    = (Net Profit / Revenue) x (Revenue / Total Assets) x (Total Assets / Total Equity)

Interpretation:
• High NPM: Superior pricing power and cost control (e.g. IT & FMCG).
• High Asset Turnover: Efficient capital utilisation (e.g. Retail & FMCG).
• High Equity Multiplier: Leverage-driven ROE (e.g. Financials & Real Estate)."""
    story.append(create_code_block(dupont_code, styles))
    story.append(Spacer(1, 10))

    story.append(
        create_callout(
            "Look for companies with expanding ROE driven by Net Profit Margin or Asset Turnover rather than "
            "increasing Equity Multiplier (Debt). Leverage-driven ROE expansion carries heightened vulnerability during rate hikes.",
            styles,
            title="FINANCIAL ANALYSIS HEURISTIC",
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 6: PEER GROUP & RADAR ANALYTICS
    # =========================================================================
    story.append(
        Paragraph("Peer Group Analytics & 8-Axis Radar Charts", styles["DocHeading1"])
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=10)
    )
    story.append(
        Paragraph(
            "The Peer Comparison module (<code>04_peers.py</code>) allows relative valuation and operational benchmarking "
            "against sector competitors. Every company is benchmarked across 10 percentile-ranked dimensions.",
            styles["DocBody"],
        )
    )

    story.append(Paragraph("8-Axis Radar Chart Interpretation", styles["DocHeading2"]))
    story.append(
        Paragraph(
            "The 8-axis radar visualization provides a normalized 0-to-100 percentile profile comparing a target company "
            "against its peer group average and the designated sector benchmark company:",
            styles["DocBody"],
        )
    )

    radar_axes = [
        [
            Paragraph("<b>Radar Axis Metric</b>", styles["TableHeader"]),
            Paragraph("<b>Metric Type</b>", styles["TableHeader"]),
            Paragraph("<b>Higher Percentile Meaning</b>", styles["TableHeader"]),
        ],
        [
            Paragraph("1. ROE (%)", styles["TableCell"]),
            Paragraph("Profitability", styles["TableCell"]),
            Paragraph(
                "Top-tier return on equity relative to industry peers.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("2. ROCE (%)", styles["TableCell"]),
            Paragraph("Capital Efficiency", styles["TableCell"]),
            Paragraph(
                "Optimal operating earnings generated per unit of total capital.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("3. Operating Profit Margin (OPM)", styles["TableCell"]),
            Paragraph("Core Efficiency", styles["TableCell"]),
            Paragraph(
                "Widest gross operating spread before financing costs.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("4. Net Profit Margin (NPM)", styles["TableCell"]),
            Paragraph("Bottom-Line Power", styles["TableCell"]),
            Paragraph(
                "Resilient net earnings after all taxes and overheads.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("5. Interest Coverage Ratio (ICR)", styles["TableCell"]),
            Paragraph("Solvency Buffer", styles["TableCell"]),
            Paragraph(
                "Substantial earnings cushion to service debt obligations.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("6. Asset Turnover", styles["TableCell"]),
            Paragraph("Asset Efficiency", styles["TableCell"]),
            Paragraph(
                "Superior asset productivity generating top-line revenue.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("7. Revenue CAGR 5-Year", styles["TableCell"]),
            Paragraph("Growth Velocity", styles["TableCell"]),
            Paragraph(
                "Sector-leading compounding of annual revenue.", styles["TableCell"]
            ),
        ],
        [
            Paragraph("8. Low Leverage (1 / D/E)", styles["TableCell"]),
            Paragraph("Balance Sheet Health", styles["TableCell"]),
            Paragraph(
                "Lowest relative debt-to-equity ratio in the peer group.",
                styles["TableCell"],
            ),
        ],
    ]
    t_radar = Table(radar_axes, colWidths=[140, 95, 280])
    t_radar.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_radar)
    story.append(Spacer(1, 10))

    story.append(
        Paragraph("Peer Groups Across 11 Nifty Sectors", styles["DocHeading2"])
    )
    story.append(
        Paragraph(
            "Companies are grouped into 11 canonical sector cohorts, each with a designated benchmark anchor:",
            styles["DocBody"],
        )
    )

    peers_summary = [
        [
            Paragraph("<b>Peer Group Name</b>", styles["TableHeader"]),
            Paragraph("<b>Company Count</b>", styles["TableHeader"]),
            Paragraph("<b>Sector Benchmark Anchor</b>", styles["TableHeader"]),
            Paragraph("<b>Key Industry Constituents</b>", styles["TableHeader"]),
        ],
        [
            Paragraph("Information Technology", styles["TableCell"]),
            Paragraph("5", styles["TableCell"]),
            Paragraph("TCS", styles["TableCell"]),
            Paragraph("TCS, INFY, HCLTECH, LTIM, TECHM", styles["TableCell"]),
        ],
        [
            Paragraph("Financial Services", styles["TableCell"]),
            Paragraph("22", styles["TableCell"]),
            Paragraph("HDFCBANK", styles["TableCell"]),
            Paragraph(
                "HDFCBANK, ICICIBANK, SBIN, KOTAKBANK, BAJFINANCE", styles["TableCell"]
            ),
        ],
        [
            Paragraph("Consumer Discretionary", styles["TableCell"]),
            Paragraph("15", styles["TableCell"]),
            Paragraph("TITAN", styles["TableCell"]),
            Paragraph(
                "TITAN, MARUTI, TATAMOTORS, M&M, BAJAJ-AUTO", styles["TableCell"]
            ),
        ],
        [
            Paragraph("Consumer Staples (FMCG)", styles["TableCell"]),
            Paragraph("12", styles["TableCell"]),
            Paragraph("HINDUNILVR", styles["TableCell"]),
            Paragraph(
                "HINDUNILVR, ITC, NESTLEIND, BRITANNIA, TATACONSUM", styles["TableCell"]
            ),
        ],
        [
            Paragraph("Energy & Oil/Gas", styles["TableCell"]),
            Paragraph("8", styles["TableCell"]),
            Paragraph("RELIANCE", styles["TableCell"]),
            Paragraph(
                "RELIANCE, ONGC, NTPC, POWERGRID, BPCL, IOC", styles["TableCell"]
            ),
        ],
        [
            Paragraph("Healthcare & Pharma", styles["TableCell"]),
            Paragraph("10", styles["TableCell"]),
            Paragraph("SUNPHARMA", styles["TableCell"]),
            Paragraph(
                "SUNPHARMA, CIPLA, DRREDDY, DIVISLAB, APOLLOHOSP", styles["TableCell"]
            ),
        ],
    ]
    t_peers = Table(peers_summary, colWidths=[120, 60, 110, 225])
    t_peers.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_peers)
    story.append(PageBreak())

    # =========================================================================
    # PAGE 7: MACHINE LEARNING CLUSTERING
    # =========================================================================
    story.append(
        Paragraph(
            "Machine Learning Clustering & Outlier Profiling", styles["DocHeading1"]
        )
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=10)
    )
    story.append(
        Paragraph(
            "To discover objective peer cohorts beyond conventional industrial sector classifications, "
            "the analytics engine (<code>src/analytics/clustering.py</code>) applies unsupervised KMeans clustering (k=5) "
            "and multi-dimensional Z-score outlier detection.",
            styles["DocBody"],
        )
    )

    story.append(Paragraph("1. KMeans Clustering Pipeline", styles["DocHeading2"]))
    story.append(
        Paragraph(
            "Clustering is executed on 5 standardized financial features across all 92 companies:",
            styles["DocBody"],
        )
    )

    cluster_features = """1. Return on Equity (%)         [return_on_equity_pct]
2. Debt-to-Equity                [debt_to_equity]
3. Revenue 5Y CAGR (%)           [revenue_cagr_5yr]
4. Free Cash Flow 5Y CAGR (%)    [fcf_cagr_5yr]
5. Operating Profit Margin (%)   [operating_profit_margin_pct]

Methodology:
• Missing value imputation using sector median.
• Feature normalization using StandardScaler (zero mean, unit variance).
• KMeans execution with k=5, random_state=42 for deterministic clustering."""
    story.append(create_code_block(cluster_features, styles))
    story.append(Spacer(1, 10))

    story.append(Paragraph("2. Cluster Profiles & Typology", styles["DocHeading2"]))
    clusters_table = [
        [
            Paragraph("<b>Cluster ID & Name</b>", styles["TableHeader"]),
            Paragraph("<b>Financial Characteristics</b>", styles["TableHeader"]),
            Paragraph("<b>Representative Companies</b>", styles["TableHeader"]),
        ],
        [
            Paragraph(
                "<b>Cluster 0</b><br/>High-Quality Compounders", styles["TableCell"]
            ),
            Paragraph(
                "High ROE (>25%), low D/E (<0.3), strong OPM (>20%), stable double-digit CAGR.",
                styles["TableCell"],
            ),
            Paragraph("TCS, INFY, TITAN, HINDUNILVR", styles["TableCell"]),
        ],
        [
            Paragraph(
                "<b>Cluster 1</b><br/>Defensive Dividend Payers", styles["TableCell"]
            ),
            Paragraph(
                "Moderate ROE (12-18%), healthy dividend payout, high cash conversion, low beta.",
                styles["TableCell"],
            ),
            Paragraph("ITC, POWERGRID, NTPC, COALINDIA", styles["TableCell"]),
        ],
        [
            Paragraph("<b>Cluster 2</b><br/>Emerging High Growth", styles["TableCell"]),
            Paragraph(
                "Rapid revenue CAGR (>18%), high reinvestment rate, moderate margins.",
                styles["TableCell"],
            ),
            Paragraph("TRENT, ZOMATO, BEL, HAL", styles["TableCell"]),
        ],
        [
            Paragraph(
                "<b>Cluster 3</b><br/>Leveraged / Capital Intensive",
                styles["TableCell"],
            ),
            Paragraph(
                "Higher debt-to-equity (>1.5), substantial CapEx, cyclical margins.",
                styles["TableCell"],
            ),
            Paragraph("TATASTEEL, JSWSTEEL, ADANIENT", styles["TableCell"]),
        ],
        [
            Paragraph(
                "<b>Cluster 4</b><br/>Turnaround / Value Cyclicals", styles["TableCell"]
            ),
            Paragraph(
                "Low valuation multiples, recovering margins, cash flow inflection.",
                styles["TableCell"],
            ),
            Paragraph("TATAMOTORS, VEDL, HINDALCO", styles["TableCell"]),
        ],
    ]
    t_clusters = Table(clusters_table, colWidths=[120, 205, 190])
    t_clusters.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_clusters)
    story.append(Spacer(1, 10))

    story.append(Paragraph("3. Multi-Metric Outlier Detection", styles["DocHeading2"]))
    story.append(
        Paragraph(
            "Outliers are flagged when a company's metric deviates by more than 3 standard deviations (|Z-score| > 3.0) "
            "from its broad sector median. Outlier reports are generated at <code>output/outlier_report.csv</code>.",
            styles["DocBody"],
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 8: AUTOMATED PDF REPORTING
    # =========================================================================
    story.append(
        Paragraph(
            "Automated PDF Reporting & Tearsheet Generation", styles["DocHeading1"]
        )
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=10)
    )
    story.append(
        Paragraph(
            "The automated reporting engine (<code>src/reports/</code>) builds publication-ready PDF equity research reports "
            "with pixel-perfect vector graphics, DuPont analysis tables, and CAGR trajectory charts.",
            styles["DocBody"],
        )
    )

    story.append(Paragraph("Report Catalog & Directory Layout", styles["DocHeading2"]))
    reports_data = [
        [
            Paragraph("<b>Report Type</b>", styles["TableHeader"]),
            Paragraph("<b>Output Location</b>", styles["TableHeader"]),
            Paragraph("<b>Page Count</b>", styles["TableHeader"]),
            Paragraph("<b>Contents & Structure</b>", styles["TableHeader"]),
        ],
        [
            Paragraph("<b>Company Tearsheets</b>", styles["TableCell"]),
            Paragraph(
                "<code>reports/tearsheets/{TICKER}.pdf</code>", styles["TableCell"]
            ),
            Paragraph("2 Pages / Co.", styles["TableCell"]),
            Paragraph(
                "Page 1: Profile, KPIs, DuPont analysis, valuation.<br/>Page 2: 6-year P&L, balance sheet & cash flow history.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>Sector Summaries</b>", styles["TableCell"]),
            Paragraph("<code>reports/sector/{SECTOR}.pdf</code>", styles["TableCell"]),
            Paragraph("3-5 Pages", styles["TableCell"]),
            Paragraph(
                "Sector median comparisons, constituent ranking, CapEx intensity, valuation scatter plots.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>Portfolio Summary</b>", styles["TableCell"]),
            Paragraph(
                "<code>reports/portfolio/portfolio_summary.pdf</code>",
                styles["TableCell"],
            ),
            Paragraph("92 Pages", styles["TableCell"]),
            Paragraph(
                "One-page executive tear card per company in alphabetical order with trend directional arrows.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>Correlation Matrix</b>", styles["TableCell"]),
            Paragraph(
                "<code>reports/correlation_heatmap.png</code>", styles["TableCell"]
            ),
            Paragraph("Graphic Image", styles["TableCell"]),
            Paragraph(
                "10x10 Pearson correlation heatmap across all KPIs.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>Elbow Curve Plot</b>", styles["TableCell"]),
            Paragraph("<code>reports/elbow_plot.png</code>", styles["TableCell"]),
            Paragraph("Graphic Image", styles["TableCell"]),
            Paragraph(
                "Inertia vs k (2-10) validating optimal cluster count.",
                styles["TableCell"],
            ),
        ],
    ]
    t_reports = Table(reports_data, colWidths=[110, 175, 60, 170])
    t_reports.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_reports)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Batch Tearsheet Generation via CLI", styles["DocHeading2"]))
    story.append(
        Paragraph(
            "Analysts can generate tearsheets on demand via Python scripts or API requests:",
            styles["DocBody"],
        )
    )

    gen_commands = """# 1. Generate tearsheet for single company (e.g. TCS)
python -c "from src.reports.tearsheet import generate_company_tearsheet; generate_company_tearsheet('TCS')"

# 2. Batch generate all 92 tearsheets
python src/reports/generate_all_tearsheets.py

# 3. Generate portfolio summary PDF
python src/reports/portfolio_summary.py"""
    story.append(create_code_block(gen_commands, styles))
    story.append(Spacer(1, 10))

    story.append(
        create_callout(
            "All generated PDFs are automatically made available for instant one-click download in the Streamlit UI "
            "under the <code>08_reports.py</code> page or via the <code>/api/v1/companies/{ticker}/tearsheet</code> API endpoint.",
            styles,
            title="STREAMLINED REPORT ACCESS",
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 9: FASTAPI REST REFERENCE & CURL EXAMPLES
    # =========================================================================
    story.append(
        Paragraph("FastAPI REST Reference & curl Examples", styles["DocHeading1"])
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=10)
    )
    story.append(
        Paragraph(
            "The platform exposes a high-throughput REST API powered by FastAPI on port 8000. "
            "Interactive Swagger documentation is available at <code>http://localhost:8000/docs</code>.",
            styles["DocBody"],
        )
    )

    api_endpoints = [
        [
            Paragraph("<b>Endpoint Method & Path</b>", styles["TableHeader"]),
            Paragraph("<b>Key Query Parameters</b>", styles["TableHeader"]),
            Paragraph("<b>Response Summary & Status Codes</b>", styles["TableHeader"]),
        ],
        [
            Paragraph("<code>GET /api/v1/health</code>", styles["TableCell"]),
            Paragraph("None", styles["TableCell"]),
            Paragraph(
                "HTTP 200: <code>{status: 'ok', db_row_counts: {...}, uptime: 120}</code>",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<code>GET /api/v1/companies</code>", styles["TableCell"]),
            Paragraph(
                "<code>sector</code>, <code>market_cap_category</code>, <code>search</code>, <code>limit</code>",
                styles["TableCell"],
            ),
            Paragraph(
                "HTTP 200: Paginated list of 92 companies with sector and latest KPIs.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<code>GET /api/v1/companies/{ticker}</code>", styles["TableCell"]
            ),
            Paragraph("<code>ticker</code> (path)", styles["TableCell"]),
            Paragraph(
                "HTTP 200: Full profile with latest ratios, P&L, BS, CF. (HTTP 404 if not found)",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<code>GET /api/v1/companies/{ticker}/pl</code>", styles["TableCell"]
            ),
            Paragraph(
                "<code>from_year</code>, <code>to_year</code>", styles["TableCell"]
            ),
            Paragraph(
                "HTTP 200: Multi-year income statement time series.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<code>GET /api/v1/screener</code>", styles["TableCell"]),
            Paragraph(
                "<code>min_roe</code>, <code>max_de</code>, <code>min_fcf</code>, <code>sector</code>, <code>max_pe</code>",
                styles["TableCell"],
            ),
            Paragraph(
                "HTTP 200: Ranked screener result list. (HTTP 400 on invalid param bounds)",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<code>GET /api/v1/sectors</code>", styles["TableCell"]),
            Paragraph("None", styles["TableCell"]),
            Paragraph(
                "HTTP 200: 11 sectors with company counts, median ROE, PE, and D/E.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<code>GET /api/v1/peers/{group_name}</code>", styles["TableCell"]
            ),
            Paragraph("<code>group_name</code> (path)", styles["TableCell"]),
            Paragraph(
                "HTTP 200: Peer group constituent metrics and percentile ranks.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<code>GET /api/v1/market-cap/{ticker}</code>", styles["TableCell"]
            ),
            Paragraph("<code>ticker</code> (path)", styles["TableCell"]),
            Paragraph(
                "HTTP 200: 2019-2024 valuation history (P/E, P/B, EV/EBITDA, Div Yield).",
                styles["TableCell"],
            ),
        ],
    ]
    t_api = Table(api_endpoints, colWidths=[150, 150, 215])
    t_api.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_api)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Practical curl Command Recipes", styles["DocHeading2"]))
    curl_examples = """# 1. Health Check
curl -X GET "http://localhost:8000/api/v1/health"

# 2. Screener: Quality Compounders (ROE >= 20%, D/E <= 0.5)
curl -X GET "http://localhost:8000/api/v1/screener?min_roe=20.0&max_de=0.5"

# 3. Company Financial Profile (TCS)
curl -X GET "http://localhost:8000/api/v1/companies/TCS"

# 4. Peer Radar Comparison (INFY)
curl -X GET "http://localhost:8000/api/v1/companies/INFY/peers/compare"

# 5. Download Binary PDF Tearsheet (RELIANCE)
curl -X GET "http://localhost:8000/api/v1/companies/RELIANCE/tearsheet" --output RELIANCE_tearsheet.pdf"""
    story.append(create_code_block(curl_examples, styles))
    story.append(PageBreak())

    # =========================================================================
    # PAGE 10: DATA QUALITY FRAMEWORK
    # =========================================================================
    story.append(
        Paragraph(
            "Data Quality Framework & Integrity Governance", styles["DocHeading1"]
        )
    )
    story.append(
        HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=10)
    )
    story.append(
        Paragraph(
            "To ensure zero garbage in financial models, the ingestion pipeline runs an automated 16-rule Data Quality (DQ) "
            "validation suite (<code>src/analytics/data_quality.py</code>). Data anomalies are categorized by severity.",
            styles["DocBody"],
        )
    )

    dq_rules = [
        [
            Paragraph("<b>Rule ID</b>", styles["TableHeader"]),
            Paragraph("<b>Rule Name & Description</b>", styles["TableHeader"]),
            Paragraph("<b>Severity Tier</b>", styles["TableHeader"]),
            Paragraph("<b>Corrective Action</b>", styles["TableHeader"]),
        ],
        [
            Paragraph("<b>DQ-01</b>", styles["TableCell"]),
            Paragraph(
                "Completeness: Mandatory financial statement fields must not be NULL.",
                styles["TableCell"],
            ),
            Paragraph("CRITICAL", styles["TableCell"]),
            Paragraph(
                "Quarantines row to <code>output/dq_violations.csv</code>",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>DQ-02</b>", styles["TableCell"]),
            Paragraph(
                "Ticker Uniqueness: No duplicate company tickers within a fiscal year.",
                styles["TableCell"],
            ),
            Paragraph("CRITICAL", styles["TableCell"]),
            Paragraph(
                "Deduplicates based on latest updated timestamp", styles["TableCell"]
            ),
        ],
        [
            Paragraph("<b>DQ-03</b>", styles["TableCell"]),
            Paragraph(
                "Balance Sheet Balance: Total Assets == Total Liabilities + Equity.",
                styles["TableCell"],
            ),
            Paragraph("CRITICAL", styles["TableCell"]),
            Paragraph(
                "Flags accounting mismatch if difference > 1 Cr", styles["TableCell"]
            ),
        ],
        [
            Paragraph("<b>DQ-04</b>", styles["TableCell"]),
            Paragraph(
                "Non-Negative Revenue: Net sales must be strictly > 0.",
                styles["TableCell"],
            ),
            Paragraph("CRITICAL", styles["TableCell"]),
            Paragraph("Rejects negative revenue entries", styles["TableCell"]),
        ],
        [
            Paragraph("<b>DQ-05</b>", styles["TableCell"]),
            Paragraph(
                "Positive Share Capital: Issued equity capital must be > 0.",
                styles["TableCell"],
            ),
            Paragraph("CRITICAL", styles["TableCell"]),
            Paragraph(
                "Flags potential data corruption in share ledger", styles["TableCell"]
            ),
        ],
        [
            Paragraph("<b>DQ-06</b>", styles["TableCell"]),
            Paragraph(
                "OPM Range Check: Operating margin must lie within [-100%, 100%].",
                styles["TableCell"],
            ),
            Paragraph("WARNING", styles["TableCell"]),
            Paragraph(
                "Emits warning log for manual analyst review", styles["TableCell"]
            ),
        ],
        [
            Paragraph("<b>DQ-07</b>", styles["TableCell"]),
            Paragraph(
                "ROE Extreme Check: ROE > 150% flagged for high leverage verification.",
                styles["TableCell"],
            ),
            Paragraph("WARNING", styles["TableCell"]),
            Paragraph(
                "Verifies whether high ROE stems from thin equity", styles["TableCell"]
            ),
        ],
        [
            Paragraph("<b>DQ-08</b>", styles["TableCell"]),
            Paragraph(
                "Negative Equity Handled: Prevents nonsensical positive ROE on negative net worth.",
                styles["TableCell"],
            ),
            Paragraph("CRITICAL", styles["TableCell"]),
            Paragraph(
                "Sets ROE to None and triggers distress flag", styles["TableCell"]
            ),
        ],
        [
            Paragraph("<b>DQ-09</b>", styles["TableCell"]),
            Paragraph(
                "Zero Interest Coverage: Handles debt-free zero interest expense.",
                styles["TableCell"],
            ),
            Paragraph("INFO", styles["TableCell"]),
            Paragraph(
                "Sets ICR to None or safe sentinel without zero-division error",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<b>DQ-10</b>", styles["TableCell"]),
            Paragraph(
                "Non-Financial D/E Limit: Flags non-banking companies with D/E > 5.0.",
                styles["TableCell"],
            ),
            Paragraph("WARNING", styles["TableCell"]),
            Paragraph(
                "Triggers high financial leverage risk flag", styles["TableCell"]
            ),
        ],
        [
            Paragraph("<b>DQ-11</b>", styles["TableCell"]),
            Paragraph(
                "CAGR Base Sign Check: Prevents invalid CAGR calculation on negative base year.",
                styles["TableCell"],
            ),
            Paragraph("WARNING", styles["TableCell"]),
            Paragraph("Marks turnaround or loss-to-profit status", styles["TableCell"]),
        ],
        [
            Paragraph("<b>DQ-12</b>", styles["TableCell"]),
            Paragraph(
                "Cash Flow Reconciliation: CFO vs Operating Income reconciliation.",
                styles["TableCell"],
            ),
            Paragraph("WARNING", styles["TableCell"]),
            Paragraph(
                "Calculates CFO Quality Score (CFO / EBITDA)", styles["TableCell"]
            ),
        ],
    ]
    t_dq = Table(dq_rules, colWidths=[55, 220, 80, 160])
    t_dq.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ]
        )
    )
    story.append(t_dq)
    story.append(Spacer(1, 10))

    story.append(
        create_callout(
            "To re-run the full data quality validation suite against the active database, execute "
            "<code>pytest tests/dq/ -v</code>. All 15 automated DQ unit tests must pass with 0 failures.",
            styles,
            title="DATA GOVERNANCE COMMAND",
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # PAGE 11: TROUBLESHOOTING & OPERATIONS
    # =========================================================================
    story.append(Paragraph("Troubleshooting, Operations & FAQ", styles["DocHeading1"]))
    story.append(
        HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=10)
    )
    story.append(
        Paragraph(
            "This section documents operational procedures, common troubleshooting scenarios, and solutions "
            "for running the Nifty 100 platform in development and staging environments.",
            styles["DocBody"],
        )
    )

    troubleshoot_data = [
        [
            Paragraph("<b>Symptom / Error</b>", styles["TableHeader"]),
            Paragraph("<b>Root Cause</b>", styles["TableHeader"]),
            Paragraph("<b>Step-by-Step Resolution</b>", styles["TableHeader"]),
        ],
        [
            Paragraph(
                "<code>sqlite3.OperationalError: database is locked</code>",
                styles["TableCell"],
            ),
            Paragraph(
                "Multiple write processes attempting to access SQLite file simultaneously.",
                styles["TableCell"],
            ),
            Paragraph(
                "All API routers use read-only queries with <code>check_same_thread=False</code>. For writes, ensure background ETL runs sequentially.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<code>Port 8000 / 8501 already in use</code>", styles["TableCell"]
            ),
            Paragraph(
                "Previous Uvicorn or Streamlit instance was not cleanly terminated.",
                styles["TableCell"],
            ),
            Paragraph(
                "Kill process using port:<br/><code>netstat -ano | findstr :8000</code><br/><code>taskkill /PID {PID} /F</code>",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<code>HTTP 404: Ticker not found</code>", styles["TableCell"]),
            Paragraph(
                "Requested company ticker is not present in the 92 active Nifty 100 constituents.",
                styles["TableCell"],
            ),
            Paragraph(
                "Verify ticker against <code>GET /api/v1/companies</code>. Tickers are case-insensitive and auto-capitalized.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<code>HTTP 400: Invalid screener parameter</code>", styles["TableCell"]
            ),
            Paragraph(
                "Filter parameter value was out of allowable bounds (e.g. <code>min_roe=150</code>).",
                styles["TableCell"],
            ),
            Paragraph(
                "Ensure <code>min_roe</code> in [0, 100], <code>max_de</code> in [0, 50], <code>max_pe</code> in [0, 500]. Refer to OpenAPI documentation.",
                styles["TableCell"],
            ),
        ],
        [
            Paragraph("<code>ReportLab font missing</code>", styles["TableCell"]),
            Paragraph(
                "System fonts unavailable during PDF compilation.", styles["TableCell"]
            ),
            Paragraph(
                "The reporting engine uses standard built-in PostScript fonts (<code>Helvetica</code>, <code>Courier</code>) for universal portability.",
                styles["TableCell"],
            ),
        ],
    ]
    t_trouble = Table(troubleshoot_data, colWidths=[120, 165, 230])
    t_trouble.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_trouble)
    story.append(Spacer(1, 10))

    story.append(
        Paragraph("System Startup & Operations Checklist", styles["DocHeading2"])
    )
    ops_commands = """# 1. Activate Python Virtual Environment
.\\.venv\\Scripts\\activate

# 2. Run Full Automated Test Suite (667 tests)
pytest tests/ --html=reports/pytest_report.html --self-contained-html

# 3. Start FastAPI REST Backend (Port 8000)
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# 4. Start Streamlit Frontend Dashboard (Port 8501)
streamlit run src/dashboard/app.py --server.port 8501"""
    story.append(create_code_block(ops_commands, styles))
    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            "<b>Bluestocks Fintech Quantitative Research Team</b> — All rights reserved. "
            "For support or API key access, contact <code>support@bluestocks.in</code>.",
            styles["DocBody"],
        )
    )

    # Build the document with two-pass NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    logger.info("Successfully generated %s", output_path)
    return output_path


if __name__ == "__main__":
    pdf_file = build_analyst_guide_pdf()
    print("=" * 60)
    print(f"Generated Analyst Guide PDF at: {pdf_file}")
    print(f"File Size: {pdf_file.stat().st_size / 1024:.2f} KB")
    print("=" * 60)
