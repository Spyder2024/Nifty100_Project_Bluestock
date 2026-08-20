"""src/reports/sector_report.py — Sector Intelligence & Constituent Benchmark Reports.

Sprint 5, Day 34

Generates 11 sector PDF reports in reports/sector/{SECTOR}_report.pdf:
    - 10 Sector Reports (Financials, Energy, Industrials, Materials, Healthcare,
      Consumer Discretionary, Consumer Staples, Information Technology,
      Communication Services, Real Estate).
    - 1 Nifty 100 All-Sectors Overview Report (NIFTY100_OVERVIEW).

Each Sector PDF contains:
    - Executive Header with sector name and constituent count.
    - 6-8 Sector Median & Aggregate KPI tiles (Median ROE, ROCE, OPM, NPM, D/E, P/E, Total Revenue, Total PAT).
    - Sector constituent revenue / market-share visual distribution chart.
    - Full Constituent Table listing all companies in the sector with 8 financial metrics:
        1. Revenue (₹ Cr)
        2. Net Profit (₹ Cr)
        3. Operating Profit Margin (OPM %)
        4. Return on Equity (ROE %)
        5. Return on Capital Employed (ROCE %)
        6. Debt-to-Equity (D/E)
        7. Price-to-Earnings (P/E)
        8. Operating Cash Flow (CFO ₹ Cr)

Usage:
    python -m src.reports.sector_report
"""

from __future__ import annotations

import argparse
import io
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker_fmt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

# ── project root resolution ───────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DB_PATH = PROJECT_ROOT / "output" / "nifty100.db"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "sector"

# Colors
NAVY = colors.HexColor("#0F172A")
NAVY_LIGHT = colors.HexColor("#1E293B")
NAVY_BLUE = colors.HexColor("#1E3A8A")
ACCENT_BLUE = colors.HexColor("#2563EB")
EMERALD_GREEN = colors.HexColor("#059669")
GREEN_BG = colors.HexColor("#ECFDF5")
ROSE_RED = colors.HexColor("#DC2626")
RED_BG = colors.HexColor("#FEF2F2")
SLATE_GREY = colors.HexColor("#64748B")
LIGHT_BG = colors.HexColor("#F8FAFC")
BORDER_COLOR = colors.HexColor("#E2E8F0")
WHITE = colors.HexColor("#FFFFFF")
AMBER = colors.HexColor("#D97706")


# ===========================================================================
# Numbered Canvas for Sector Reports
# ===========================================================================


class SectorNumberedCanvas(canvas.Canvas):
    """Canvas that prints dynamic 'Page X of Y' on sector reports."""

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
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#94A3B8"))

        # Footer
        footer_text = (
            "Nifty 100 Sector Intelligence Report  |  Confidential & Proprietary"
        )
        self.drawString(25, 14, footer_text)
        page_num_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(A4[0] - 25, 14, page_num_str)

        # Footer line
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(25, 24, A4[0] - 25, 24)

        self.restoreState()


# ===========================================================================
# Sector Data Extraction
# ===========================================================================


def _format_cr(val: Optional[float]) -> str:
    if val is None or pd.isna(val):
        return "-"
    try:
        v = float(val)
        if abs(v) >= 100000:
            return f"₹{v / 100000:.2f}L Cr"
        elif abs(v) >= 1000:
            return f"₹{v:,.0f} Cr"
        else:
            return f"₹{v:.1f} Cr"
    except (ValueError, TypeError):
        return "-"


def _format_pct(val: Optional[float]) -> str:
    if val is None or pd.isna(val):
        return "-"
    try:
        return f"{float(val):.1f}%"
    except (ValueError, TypeError):
        return "-"


def _format_num(val: Optional[float], suffix: str = "") -> str:
    if val is None or pd.isna(val):
        return "-"
    try:
        return f"{float(val):.2f}{suffix}"
    except (ValueError, TypeError):
        return "-"


def get_sector_data(sector_id: str, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    """Load constituent data and compute benchmark statistics for a sector."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Check if sector is NIFTY100 overview
    is_overview = sector_id.upper() in ("ALL_SECTORS", "NIFTY100_OVERVIEW", "NIFTY100")

    if is_overview:
        sector_name = "Nifty 100 All-Sectors Benchmark Overview"
        query_co = """
            SELECT c.company_id, c.company_name, c.sector_id, s.sector_name
            FROM companies c
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            ORDER BY c.company_name
        """
        co_rows = conn.execute(query_co).fetchall()
    else:
        sec_row = conn.execute(
            "SELECT * FROM sectors WHERE sector_id = ?", (sector_id,)
        ).fetchone()
        sector_name = (
            sec_row["sector_name"]
            if sec_row and "sector_name" in sec_row.keys()
            else sector_id.replace("_", " ").title()
        )
        query_co = """
            SELECT c.company_id, c.company_name, c.sector_id, s.sector_name
            FROM companies c
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            WHERE c.sector_id = ?
            ORDER BY c.company_name
        """
        co_rows = conn.execute(query_co, (sector_id,)).fetchall()

    constituents = []
    for r in co_rows:
        cid = r["company_id"]
        cname = r["company_name"]

        # Latest IS
        is_row = conn.execute(
            "SELECT year, revenue, net_income, opm FROM income_statement WHERE company_id = ? ORDER BY year DESC LIMIT 1",
            (cid,),
        ).fetchone()

        # Latest Ratios
        r_row = conn.execute(
            "SELECT year, roe, roce, debt_to_equity, price_to_earnings, net_profit_margin, opm FROM ratios WHERE company_id = ? ORDER BY year DESC LIMIT 1",
            (cid,),
        ).fetchone()

        # Latest Cash Flow
        cf_row = conn.execute(
            "SELECT year, operating_cf FROM cash_flow WHERE company_id = ? ORDER BY year DESC LIMIT 1",
            (cid,),
        ).fetchone()

        rev = is_row["revenue"] if is_row and "revenue" in is_row.keys() else None
        pat = is_row["net_income"] if is_row and "net_income" in is_row.keys() else None
        opm = (
            r_row["opm"]
            if r_row and "opm" in r_row.keys() and r_row["opm"] is not None
            else (is_row["opm"] if is_row and "opm" in is_row.keys() else None)
        )
        roe = r_row["roe"] if r_row and "roe" in r_row.keys() else None
        roce = r_row["roce"] if r_row and "roce" in r_row.keys() else None
        de = (
            r_row["debt_to_equity"]
            if r_row and "debt_to_equity" in r_row.keys()
            else None
        )
        pe = (
            r_row["price_to_earnings"]
            if r_row and "price_to_earnings" in r_row.keys()
            else None
        )
        npm = (
            r_row["net_profit_margin"]
            if r_row and "net_profit_margin" in r_row.keys()
            else None
        )
        cfo = (
            cf_row["operating_cf"]
            if cf_row and "operating_cf" in cf_row.keys()
            else None
        )

        constituents.append(
            {
                "company_id": cid,
                "company_name": cname,
                "sector_id": r["sector_id"],
                "revenue": rev,
                "net_profit": pat,
                "opm": opm,
                "npm": npm,
                "roe": roe,
                "roce": roce,
                "de": de,
                "pe": pe,
                "cfo": cfo,
            }
        )

    conn.close()

    df_const = pd.DataFrame(constituents)

    # Compute Median and Aggregate Metrics
    med_roe = df_const["roe"].median() if not df_const.empty else None
    med_roce = df_const["roce"].median() if not df_const.empty else None
    med_opm = df_const["opm"].median() if not df_const.empty else None
    med_npm = df_const["npm"].median() if not df_const.empty else None
    med_de = df_const["de"].median() if not df_const.empty else None
    med_pe = df_const["pe"].median() if not df_const.empty else None
    total_rev = df_const["revenue"].sum() if not df_const.empty else None
    total_pat = df_const["net_profit"].sum() if not df_const.empty else None

    return {
        "sector_id": sector_id,
        "sector_name": sector_name,
        "is_overview": is_overview,
        "constituent_count": len(df_const),
        "constituents": df_const,
        "med_roe": med_roe,
        "med_roce": med_roce,
        "med_opm": med_opm,
        "med_npm": med_npm,
        "med_de": med_de,
        "med_pe": med_pe,
        "total_rev": total_rev,
        "total_pat": total_pat,
    }


# ===========================================================================
# Matplotlib Sector Charts
# ===========================================================================


def render_sector_distribution_chart(
    df_const: pd.DataFrame,
    is_overview: bool = False,
    width_in=7.3,
    height_in=2.5,
    dpi=180,
) -> io.BytesIO:
    """Render revenue distribution or top constituent contribution chart."""
    fig, ax = plt.subplots(figsize=(width_in, height_in), dpi=dpi)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FAFAFC")

    if df_const.empty or "revenue" not in df_const.columns:
        ax.text(
            0.5,
            0.5,
            "Sector Chart Data Unavailable",
            ha="center",
            va="center",
            color="#64748B",
            fontsize=10,
        )
        ax.axis("off")
    else:
        # Sort by revenue descending
        df_sorted = (
            df_const.dropna(subset=["revenue"])
            .sort_values("revenue", ascending=False)
            .copy()
        )

        if is_overview:
            # Top 10 across Nifty 100
            plot_df = df_sorted.head(10)
            title = "Top 10 Constituents by Revenue (₹ Cr) — Nifty 100"
        else:
            plot_df = df_sorted.head(8)
            title = "Top Sector Constituents by Revenue (₹ Cr)"

        tickers = plot_df["company_id"].tolist()
        revs = plot_df["revenue"].tolist()

        x = np.arange(len(tickers))
        bars = ax.bar(x, revs, 0.48, color="#1E3A8A", alpha=0.9, zorder=3)

        # Annotate values
        for bar, val in zip(bars, revs):
            label = f"₹{val/1000:.0f}k" if val >= 10000 else f"₹{val:,.0f}"
            ax.annotate(
                label,
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7,
                fontweight="bold",
                color="#0F172A",
            )

        ax.set_xticks(x)
        ax.set_xticklabels(
            tickers, fontsize=8, fontweight="bold", color="#334155", rotation=0
        )
        ax.yaxis.set_major_formatter(
            ticker_fmt.FuncFormatter(lambda y, _: f"₹{y:,.0f}")
        )
        ax.tick_params(axis="y", labelsize=7.5, colors="#475569")
        ax.tick_params(axis="x", colors="#475569")

        ax.grid(axis="y", linestyle="--", alpha=0.5, color="#E2E8F0", zorder=0)
        ax.set_title(title, fontsize=9.5, fontweight="bold", color="#0F172A", pad=6)

        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        for spine in ["left", "bottom"]:
            ax.spines[spine].set_color("#CBD5E1")

    plt.tight_layout(pad=0.6)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ===========================================================================
# ReportLab Sector PDF Builder
# ===========================================================================


def build_sector_pdf(data: dict[str, Any], output_pdf_path: Path) -> Path:
    """Compile a professional sector benchmark PDF report."""
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_pdf_path),
        pagesize=A4,
        leftMargin=25,
        rightMargin=25,
        topMargin=25,
        bottomMargin=30,
    )

    getSampleStyleSheet()

    style_header_left = ParagraphStyle(
        "SecHL", fontName="Helvetica", textColor=WHITE, leading=14
    )
    style_header_right = ParagraphStyle(
        "SecHR", fontName="Helvetica", textColor=WHITE, alignment=2, leading=10
    )

    style_kpi_title = ParagraphStyle(
        "SecKPIT",
        fontName="Helvetica",
        fontSize=7,
        leading=8,
        textColor=SLATE_GREY,
        alignment=1,
    )
    style_kpi_val = ParagraphStyle(
        "SecKPIV",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=NAVY,
        alignment=1,
    )
    style_kpi_sub = ParagraphStyle(
        "SecKPIS",
        fontName="Helvetica",
        fontSize=6.5,
        leading=8,
        textColor=ACCENT_BLUE,
        alignment=1,
    )

    style_th = ParagraphStyle(
        "SecTH",
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=WHITE,
        alignment=1,
    )
    style_td = ParagraphStyle(
        "SecTD",
        fontName="Helvetica",
        fontSize=6.5,
        leading=8,
        textColor=NAVY,
        alignment=1,
    )
    style_td_name = ParagraphStyle(
        "SecTDName",
        fontName="Helvetica-Bold",
        fontSize=6.5,
        leading=8,
        textColor=NAVY,
        alignment=0,
    )

    story = []
    page_width = A4[0] - 50  # 545.27 pt

    # 1. Navy Header Bar
    header_left = Paragraph(
        f"<font size=13 color='#FFFFFF'><b>{data['sector_name'].upper()}</b></font><br/>"
        f"<font size=8.5 color='#94A3B8'>Nifty 100 Sector Intelligence & Constituent Benchmark</font>",
        style_header_left,
    )
    header_right = Paragraph(
        f"<font size=8 color='#94A3B8'>CONSTITUENTS</font><br/>"
        f"<font size=11 color='#FFFFFF'><b>{data['constituent_count']} Companies</b></font><br/>"
        f"<font size=7 color='#38BDF8'>{datetime.now().strftime('%B %Y')}</font>",
        style_header_right,
    )
    header_table = Table(
        [[header_left, header_right]], colWidths=[page_width * 0.75, page_width * 0.25]
    )
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 8))

    # 2. Sector Median & Total KPI Tiles (2 rows of 4)
    def _make_kpi_tile(title: str, val: str, sub: str) -> list:
        return [
            Paragraph(title.upper(), style_kpi_title),
            Spacer(1, 1),
            Paragraph(val, style_kpi_val),
            Spacer(1, 1),
            Paragraph(sub, style_kpi_sub),
        ]

    w4 = page_width / 4.0
    kpi_matrix = [
        [
            _make_kpi_tile(
                "Median ROE", _format_pct(data["med_roe"]), "Sector Target > 15%"
            ),
            _make_kpi_tile(
                "Median ROCE", _format_pct(data["med_roce"]), "Capital Efficiency"
            ),
            _make_kpi_tile(
                "Median OPM", _format_pct(data["med_opm"]), "Operating Margin"
            ),
            _make_kpi_tile(
                "Median Net Margin", _format_pct(data["med_npm"]), "PAT Margin"
            ),
        ],
        [
            _make_kpi_tile(
                "Median D/E", _format_num(data["med_de"], "x"), "Sector Leverage"
            ),
            _make_kpi_tile(
                "Median P/E", _format_num(data["med_pe"], "x"), "Valuation Multiple"
            ),
            _make_kpi_tile(
                "Total Revenue", _format_cr(data["total_rev"]), "Combined Sales"
            ),
            _make_kpi_tile(
                "Total Net Profit", _format_cr(data["total_pat"]), "Combined Earnings"
            ),
        ],
    ]
    kpi_grid = Table(kpi_matrix, colWidths=[w4, w4, w4, w4])
    kpi_grid.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 1, BORDER_COLOR),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(kpi_grid)
    story.append(Spacer(1, 8))

    # 3. Revenue Contribution Chart
    chart_buf = render_sector_distribution_chart(
        data["constituents"],
        is_overview=data["is_overview"],
        width_in=7.3,
        height_in=2.2,
    )
    story.append(Image(chart_buf, width=page_width, height=140))
    story.append(Spacer(1, 8))

    # 4. Constituent Table (8 Metrics Per Company)
    # Header: Company | Revenue | PAT | OPM | ROE | ROCE | D/E | P/E | CFO
    col_widths = [
        page_width * 0.22,  # Company Name/Ticker
        page_width * 0.11,  # Revenue
        page_width * 0.10,  # Net Profit
        page_width * 0.09,  # OPM
        page_width * 0.09,  # ROE
        page_width * 0.09,  # ROCE
        page_width * 0.09,  # D/E
        page_width * 0.09,  # P/E
        page_width * 0.12,  # CFO
    ]

    table_data = [
        [
            Paragraph("<b>Company / Ticker</b>", style_th),
            Paragraph("<b>Revenue</b>", style_th),
            Paragraph("<b>Net Profit</b>", style_th),
            Paragraph("<b>OPM (%)</b>", style_th),
            Paragraph("<b>ROE (%)</b>", style_th),
            Paragraph("<b>ROCE (%)</b>", style_th),
            Paragraph("<b>D/E (x)</b>", style_th),
            Paragraph("<b>P/E (x)</b>", style_th),
            Paragraph("<b>Op CF (CFO)</b>", style_th),
        ]
    ]

    df_const = data["constituents"]
    for idx, row in df_const.iterrows():
        co_label = f"<b>{row['company_id']}</b><br/><font color='#64748B' size=5.5>{row['company_name'][:20]}</font>"
        table_data.append(
            [
                Paragraph(co_label, style_td_name),
                Paragraph(_format_cr(row["revenue"]), style_td),
                Paragraph(_format_cr(row["net_profit"]), style_td),
                Paragraph(_format_pct(row["opm"]), style_td),
                Paragraph(_format_pct(row["roe"]), style_td),
                Paragraph(_format_pct(row["roce"]), style_td),
                Paragraph(_format_num(row["de"], "x"), style_td),
                Paragraph(_format_num(row["pe"], "x"), style_td),
                Paragraph(_format_cr(row["cfo"]), style_td),
            ]
        )

    constituent_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    table_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY_LIGHT),
        ("BOX", (0, 0), (-1, -1), 1, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    # Alternating row background
    for i in range(1, len(table_data)):
        bg = LIGHT_BG if i % 2 == 1 else WHITE
        table_styles.append(("BACKGROUND", (0, i), (-1, i), bg))

    constituent_table.setStyle(TableStyle(table_styles))
    story.append(constituent_table)

    # Build Document with SectorNumberedCanvas
    doc.build(story, canvasmaker=SectorNumberedCanvas)
    logger.info(
        "Generated Sector Report for %s → %s", data["sector_id"], output_pdf_path
    )
    return output_pdf_path


# ===========================================================================
# Public API & Batch Runner
# ===========================================================================


def generate_sector_report(
    sector_id: str,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    db_path: Path = DEFAULT_DB_PATH,
) -> Path:
    """Generate a single sector report PDF."""
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_sec = sector_id.strip().upper()
    out_pdf = output_dir / f"{clean_sec}_report.pdf"
    data = get_sector_data(clean_sec, db_path=db_path)
    return build_sector_pdf(data, out_pdf)


def generate_all_sector_reports(
    output_dir: Path = DEFAULT_OUTPUT_DIR, db_path: Path = DEFAULT_DB_PATH
) -> list[Path]:
    """Generate all 11 Sector Benchmark Reports (10 Sectors + 1 All-Sectors Overview)."""
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT sector_id FROM sectors ORDER BY sector_id").fetchall()
    conn.close()

    sector_ids = [r[0] for r in rows]
    # Ensure 11th overview is included
    if "NIFTY100_OVERVIEW" not in sector_ids and "ALL_SECTORS" not in sector_ids:
        sector_ids.append("NIFTY100_OVERVIEW")

    generated: list[Path] = []
    for sec in sector_ids:
        try:
            pdf_path = generate_sector_report(
                sec, output_dir=output_dir, db_path=db_path
            )
            generated.append(pdf_path)
        except Exception as exc:
            logger.error("Failed generating sector report for %s: %s", sec, exc)

    return generated


def main():
    parser = argparse.ArgumentParser(
        description="Generate Sector Benchmark Reports using ReportLab."
    )
    parser.add_argument(
        "--sectors",
        nargs="+",
        default=None,
        help="List of sector IDs to generate reports for (default: all 11).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for generated sector PDFs.",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)

    print("=" * 70)
    print("Day 34 — Sector Intelligence & Benchmark Report Generator")
    print("=" * 70)
    print(f"[INFO] Output Directory: {out_dir}")

    if args.sectors:
        results = [generate_sector_report(s, output_dir=out_dir) for s in args.sectors]
    else:
        results = generate_all_sector_reports(output_dir=out_dir)

    print(
        f"\n[SUMMARY] Successfully generated {len(results)} sector reports in {out_dir}"
    )
    for p in results:
        print(f"  • {p.name}")


if __name__ == "__main__":
    main()
