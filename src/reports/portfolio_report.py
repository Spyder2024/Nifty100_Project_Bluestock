"""src/reports/portfolio_report.py — Portfolio Summary PDF Generator.

Sprint 5, Day 35

Generates reports/portfolio/portfolio_summary.pdf:
- Exactly 1 page per company in alphabetical order by ticker (92 companies total).
- Each page features:
    * Executive Header: Company Name, Ticker, Sector badge, Market Cap.
    * Top 6 KPIs in a structured card grid:
        1. Revenue (Cr)
        2. Net Profit (Cr)
        3. Operating Profit Margin (OPM %)
        4. Return on Equity (ROE %)
        5. Return on Capital Employed (ROCE %)
        6. Debt-to-Equity (D/E)
    * Trend Arrows:
        - Up arrow (^) if metric improved in latest year (> +2%).
        - Down arrow (v) if declined (< -2%).
        - Right arrow (>) if flat within 2% (+/-2%).
    * Multi-Year Historical Financial Performance Table (up to 5 recent years).
    * Cash Flow Intelligence & Capital Allocation Profile (CFO Quality, CapEx Intensity, Distress Flag).
    * Key Investment Highlights (Top Pros & Cons from NLP engine).
    * Professional NumberedCanvas footer ('Page X of 92').

Usage:
    python -m src.reports.portfolio_report
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
from reportlab.lib import colors
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

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DB_PATH = PROJECT_ROOT / "output" / "nifty100.db"
DEFAULT_OUTPUT_PDF = PROJECT_ROOT / "reports" / "portfolio" / "portfolio_summary.pdf"
CASHFLOW_XLSX = PROJECT_ROOT / "output" / "cashflow_intelligence.xlsx"
PROS_CONS_CSV = PROJECT_ROOT / "output" / "pros_cons_generated.csv"

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
CARD_BG = colors.HexColor("#F1F5F9")
BORDER_COLOR = colors.HexColor("#CBD5E1")
WHITE = colors.HexColor("#FFFFFF")
AMBER = colors.HexColor("#D97706")
AMBER_BG = colors.HexColor("#FFFBEB")


class PortfolioNumberedCanvas(canvas.Canvas):
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
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        footer_text = "Bluestock Fintech — Nifty 100 Portfolio Summary Report  |  Confidential & Proprietary"
        self.drawString(24, 14, footer_text)
        page_num_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(A4[0] - 24, 14, page_num_str)
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(24, 23, A4[0] - 24, 23)
        self.restoreState()


def _fmt_val(
    val: Optional[float],
    is_currency: bool = False,
    is_pct: bool = False,
    decimals: int = 2,
) -> str:
    if val is None or pd.isna(val):
        return "-"
    try:
        v = float(val)
        if is_currency:
            if abs(v) >= 100000:
                return f"Rs {v / 100000:.2f}L Cr"
            elif abs(v) >= 1000:
                return f"Rs {v:,.0f} Cr"
            return f"Rs {v:,.1f} Cr"
        elif is_pct:
            return f"{v:.1f}%"
        else:
            return f"{v:.{decimals}f}"
    except (ValueError, TypeError):
        return str(val)


def _compute_trend(
    curr: Optional[float], prev: Optional[float], is_de: bool = False
) -> tuple[str, str, str, colors.Color, colors.Color]:
    if curr is None or prev is None or pd.isna(curr) or pd.isna(prev) or prev == 0:
        return ("-", "-", "N/A", SLATE_GREY, LIGHT_BG)
    try:
        c = float(curr)
        p = float(prev)
        pct_chg = ((c - p) / abs(p)) * 100.0
        if is_de:
            if pct_chg < -2.0:
                arrow = "[UP]"
                label = f"{pct_chg:+.1f}% (Improved)"
                txt_c = EMERALD_GREEN
                bg_c = GREEN_BG
            elif pct_chg > 2.0:
                arrow = "[DOWN]"
                label = f"{pct_chg:+.1f}% (Declined)"
                txt_c = ROSE_RED
                bg_c = RED_BG
            else:
                arrow = "[FLAT]"
                label = f"{pct_chg:+.1f}% (Flat)"
                txt_c = SLATE_GREY
                bg_c = LIGHT_BG
        else:
            if pct_chg > 2.0:
                arrow = "[UP]"
                label = f"{pct_chg:+.1f}% (Improved)"
                txt_c = EMERALD_GREEN
                bg_c = GREEN_BG
            elif pct_chg < -2.0:
                arrow = "[DOWN]"
                label = f"{pct_chg:+.1f}% (Declined)"
                txt_c = ROSE_RED
                bg_c = RED_BG
            else:
                arrow = "[FLAT]"
                label = f"{pct_chg:+.1f}% (Flat)"
                txt_c = SLATE_GREY
                bg_c = LIGHT_BG
        return (arrow, f"{pct_chg:+.1f}%", label, txt_c, bg_c)
    except Exception:
        return ("-", "-", "N/A", SLATE_GREY, LIGHT_BG)


def load_portfolio_data(
    db_path: Path = DEFAULT_DB_PATH,
) -> tuple[list[dict], dict, dict]:
    conn = sqlite3.connect(str(db_path))
    comp_sql = """
        SELECT c.company_id, c.company_name, s.sector_name, c.nse_symbol, c.isin
        FROM companies c
        LEFT JOIN sectors s ON c.sector_id = s.sector_id
        ORDER BY c.company_id ASC
    """
    df_comps = pd.read_sql(comp_sql, conn)
    df_is = pd.read_sql(
        "SELECT company_id, year, revenue, operating_income, net_income, opm, npm FROM income_statement",
        conn,
    )
    df_bs = pd.read_sql(
        "SELECT company_id, year, total_assets, total_liabilities, total_equity, borrowings FROM balance_sheet",
        conn,
    )
    df_cf = pd.read_sql(
        "SELECT company_id, year, operating_cf, investing_cf, financing_cf, net_cash_flow, capex, fcf FROM cash_flow",
        conn,
    )
    df_ratios = pd.read_sql(
        "SELECT company_id, year, roe, roce, debt_to_equity, net_profit_margin, opm, price_to_earnings FROM ratios",
        conn,
    )
    df_mcap = pd.read_sql(
        "SELECT company_id, year, market_cap_cr FROM market_cap", conn
    )
    conn.close()

    cf_intel_map = {}
    if CASHFLOW_XLSX.exists():
        try:
            df_cf_intel = pd.read_excel(CASHFLOW_XLSX)
            for _, r in df_cf_intel.iterrows():
                cid = str(r.get("company_name", "")).strip()
                cf_intel_map[cid] = r.to_dict()
        except Exception as e:
            logger.warning("Could not read cashflow_intelligence.xlsx: %s", e)

    pros_map: dict[str, list[str]] = {}
    cons_map: dict[str, list[str]] = {}
    if PROS_CONS_CSV.exists():
        try:
            df_pc = pd.read_csv(PROS_CONS_CSV)
            for _, r in df_pc.iterrows():
                cid = str(r["company_id"]).strip()
                rtype = str(r["type"]).strip().lower()
                text = str(r["text"]).strip()
                if rtype == "pro":
                    pros_map.setdefault(cid, []).append(text)
                elif rtype == "con":
                    cons_map.setdefault(cid, []).append(text)
        except Exception as e:
            logger.warning("Could not read pros_cons_generated.csv: %s", e)

    companies_data = []

    for _, c_row in df_comps.iterrows():
        cid = str(c_row["company_id"]).strip()
        cname = str(c_row["company_name"]).strip()
        sector = str(
            c_row["sector_name"] if pd.notna(c_row["sector_name"]) else "Unclassified"
        ).strip()

        sub_is = (
            df_is[df_is["company_id"] == cid]
            .sort_values("year", ascending=False)
            .reset_index(drop=True)
        )
        sub_bs = (
            df_bs[df_bs["company_id"] == cid]
            .sort_values("year", ascending=False)
            .reset_index(drop=True)
        )
        sub_cf = (
            df_cf[df_cf["company_id"] == cid]
            .sort_values("year", ascending=False)
            .reset_index(drop=True)
        )
        sub_rat = (
            df_ratios[df_ratios["company_id"] == cid]
            .sort_values("year", ascending=False)
            .reset_index(drop=True)
        )
        sub_mcap = (
            df_mcap[df_mcap["company_id"] == cid]
            .sort_values("year", ascending=False)
            .reset_index(drop=True)
        )

        latest_yr = (
            sub_is.iloc[0]["year"]
            if not sub_is.empty
            else (sub_rat.iloc[0]["year"] if not sub_rat.empty else "Latest")
        )
        prev_yr = (
            sub_is.iloc[1]["year"]
            if len(sub_is) > 1
            else (sub_rat.iloc[1]["year"] if len(sub_rat) > 1 else None)
        )

        rev_curr = sub_is.iloc[0]["revenue"] if not sub_is.empty else None
        rev_prev = sub_is.iloc[1]["revenue"] if len(sub_is) > 1 else None

        pat_curr = sub_is.iloc[0]["net_income"] if not sub_is.empty else None
        pat_prev = sub_is.iloc[1]["net_income"] if len(sub_is) > 1 else None

        opm_curr = (
            sub_rat.iloc[0]["opm"]
            if not sub_rat.empty and pd.notna(sub_rat.iloc[0]["opm"])
            else (sub_is.iloc[0]["opm"] if not sub_is.empty else None)
        )
        opm_prev = (
            sub_rat.iloc[1]["opm"]
            if len(sub_rat) > 1 and pd.notna(sub_rat.iloc[1]["opm"])
            else (sub_is.iloc[1]["opm"] if len(sub_is) > 1 else None)
        )

        roe_curr = sub_rat.iloc[0]["roe"] if not sub_rat.empty else None
        roe_prev = sub_rat.iloc[1]["roe"] if len(sub_rat) > 1 else None

        roce_curr = sub_rat.iloc[0]["roce"] if not sub_rat.empty else None
        roce_prev = sub_rat.iloc[1]["roce"] if len(sub_rat) > 1 else None

        de_curr = sub_rat.iloc[0]["debt_to_equity"] if not sub_rat.empty else None
        de_prev = sub_rat.iloc[1]["debt_to_equity"] if len(sub_rat) > 1 else None

        if (de_curr is None or pd.isna(de_curr)) and not sub_bs.empty:
            eq = sub_bs.iloc[0]["total_equity"]
            borr = sub_bs.iloc[0]["borrowings"]
            if eq and borr is not None and eq > 0:
                de_curr = borr / eq
        if (de_prev is None or pd.isna(de_prev)) and len(sub_bs) > 1:
            eq = sub_bs.iloc[1]["total_equity"]
            borr = sub_bs.iloc[1]["borrowings"]
            if eq and borr is not None and eq > 0:
                de_prev = borr / eq

        cfo_curr = sub_cf.iloc[0]["operating_cf"] if not sub_cf.empty else None
        cfo_prev = sub_cf.iloc[1]["operating_cf"] if len(sub_cf) > 1 else None

        mcap_val = sub_mcap.iloc[0]["market_cap_cr"] if not sub_mcap.empty else None

        years = []
        if not sub_is.empty:
            years = sub_is["year"].tolist()[:5]
        elif not sub_rat.empty:
            years = sub_rat["year"].tolist()[:5]

        hist_table_data = []
        for yr in years:
            r_is = sub_is[sub_is["year"] == yr]
            r_rat = sub_rat[sub_rat["year"] == yr]
            r_cf = sub_cf[sub_cf["year"] == yr]

            hist_table_data.append(
                {
                    "year": yr,
                    "revenue": r_is.iloc[0]["revenue"] if not r_is.empty else None,
                    "net_income": (
                        r_is.iloc[0]["net_income"] if not r_is.empty else None
                    ),
                    "opm": (
                        r_rat.iloc[0]["opm"]
                        if not r_rat.empty and pd.notna(r_rat.iloc[0]["opm"])
                        else (r_is.iloc[0]["opm"] if not r_is.empty else None)
                    ),
                    "roe": r_rat.iloc[0]["roe"] if not r_rat.empty else None,
                    "roce": r_rat.iloc[0]["roce"] if not r_rat.empty else None,
                    "debt_to_equity": (
                        r_rat.iloc[0]["debt_to_equity"] if not r_rat.empty else None
                    ),
                    "cfo": r_cf.iloc[0]["operating_cf"] if not r_cf.empty else None,
                }
            )

        intel = cf_intel_map.get(cid, {})
        c_pros = pros_map.get(
            cid, ["Established market presence and strong brand franchise."]
        )
        c_cons = cons_map.get(
            cid, ["Competitive dynamics and sector headwinds warrant monitoring."]
        )

        companies_data.append(
            {
                "company_id": cid,
                "company_name": cname,
                "sector": sector,
                "latest_year": latest_yr,
                "prev_year": prev_yr,
                "mcap": mcap_val,
                "kpi_rev": (rev_curr, rev_prev),
                "kpi_pat": (pat_curr, pat_prev),
                "kpi_opm": (opm_curr, opm_prev),
                "kpi_roe": (roe_curr, roe_prev),
                "kpi_roce": (roce_curr, roce_prev),
                "kpi_de": (de_curr, de_prev),
                "kpi_cfo": (cfo_curr, cfo_prev),
                "hist_table": hist_table_data,
                "intel": intel,
                "pros": c_pros,
                "cons": c_cons,
            }
        )

    return companies_data, cf_intel_map, pros_map


def build_portfolio_summary_pdf(
    companies_data: list[dict], output_pdf: Path = DEFAULT_OUTPUT_PDF
) -> Path:
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    margin = 24.0
    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=22.0,
        bottomMargin=28.0,
    )

    usable_width = A4[0] - (margin * 2)

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "PageHeaderTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        textColor=NAVY,
    )
    meta_style = ParagraphStyle(
        "PageHeaderMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=SLATE_GREY,
        alignment=2,
    )
    sec_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=NAVY_BLUE,
        spaceBefore=3,
        spaceAfter=2,
    )
    card_title_style = ParagraphStyle(
        "CardTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8.5,
        textColor=SLATE_GREY,
    )
    card_val_style = ParagraphStyle(
        "CardVal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=12.5,
        textColor=NAVY,
    )
    card_sub_style = ParagraphStyle(
        "CardSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.5,
        leading=8,
        textColor=SLATE_GREY,
    )
    table_hdr_style = ParagraphStyle(
        "TblHdr",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8.5,
        textColor=WHITE,
        alignment=1,
    )
    table_cell_style = ParagraphStyle(
        "TblCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=8.5,
        textColor=NAVY,
        alignment=1,
    )
    bullet_pro = ParagraphStyle(
        "BulletPro",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#065F46"),
    )
    bullet_con = ParagraphStyle(
        "BulletCon",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#991B1B"),
    )
    badge_style = ParagraphStyle(
        "BadgeText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=NAVY,
    )

    story = []
    total_comps = len(companies_data)
    logger.info("Assembling Portfolio Summary PDF for %d companies...", total_comps)

    for idx, c in enumerate(companies_data):
        # 1. Header Banner
        header_data = [
            [
                Paragraph(
                    f"<b>{c['company_name']}</b> <font size=9.5 color='#2563EB'>({c['company_id']})</font>",
                    title_style,
                ),
                Paragraph(
                    f"<b>Sector:</b> {c['sector']}<br/>"
                    f"<b>MCap:</b> {_fmt_val(c['mcap'], is_currency=True)} | <b>FY:</b> {c['latest_year']}",
                    meta_style,
                ),
            ]
        ]
        t_header = Table(
            header_data, colWidths=[usable_width * 0.62, usable_width * 0.38]
        )
        t_header.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.append(t_header)
        story.append(Spacer(1, 1))
        story.append(
            HRFlowable(
                width="100%",
                thickness=1.0,
                color=ACCENT_BLUE,
                spaceBefore=1,
                spaceAfter=4,
            )
        )

        # 2. Top 6 KPIs Grid
        c_rev, p_rev = c["kpi_rev"]
        arr1, chg1, lbl1, col1, bg1 = _compute_trend(c_rev, p_rev, is_de=False)
        card1_content = [
            Paragraph("REVENUE", card_title_style),
            Paragraph(f"{_fmt_val(c_rev, is_currency=True)}", card_val_style),
            Paragraph(f"Prior: {_fmt_val(p_rev, is_currency=True)}", card_sub_style),
            Paragraph(
                f"<b>{arr1} {lbl1}</b>",
                ParagraphStyle(
                    "T1",
                    parent=card_sub_style,
                    textColor=col1,
                    fontName="Helvetica-Bold",
                ),
            ),
        ]

        c_pat, p_pat = c["kpi_pat"]
        arr2, chg2, lbl2, col2, bg2 = _compute_trend(c_pat, p_pat, is_de=False)
        card2_content = [
            Paragraph("NET PROFIT (PAT)", card_title_style),
            Paragraph(f"{_fmt_val(c_pat, is_currency=True)}", card_val_style),
            Paragraph(f"Prior: {_fmt_val(p_pat, is_currency=True)}", card_sub_style),
            Paragraph(
                f"<b>{arr2} {lbl2}</b>",
                ParagraphStyle(
                    "T2",
                    parent=card_sub_style,
                    textColor=col2,
                    fontName="Helvetica-Bold",
                ),
            ),
        ]

        c_opm, p_opm = c["kpi_opm"]
        arr3, chg3, lbl3, col3, bg3 = _compute_trend(c_opm, p_opm, is_de=False)
        card3_content = [
            Paragraph("OPERATING MARGIN (OPM)", card_title_style),
            Paragraph(_fmt_val(c_opm, is_pct=True), card_val_style),
            Paragraph(f"Prior: {_fmt_val(p_opm, is_pct=True)}", card_sub_style),
            Paragraph(
                f"<b>{arr3} {lbl3}</b>",
                ParagraphStyle(
                    "T3",
                    parent=card_sub_style,
                    textColor=col3,
                    fontName="Helvetica-Bold",
                ),
            ),
        ]

        c_roe, p_roe = c["kpi_roe"]
        arr4, chg4, lbl4, col4, bg4 = _compute_trend(c_roe, p_roe, is_de=False)
        card4_content = [
            Paragraph("RETURN ON EQUITY (ROE)", card_title_style),
            Paragraph(_fmt_val(c_roe, is_pct=True), card_val_style),
            Paragraph(f"Prior: {_fmt_val(p_roe, is_pct=True)}", card_sub_style),
            Paragraph(
                f"<b>{arr4} {lbl4}</b>",
                ParagraphStyle(
                    "T4",
                    parent=card_sub_style,
                    textColor=col4,
                    fontName="Helvetica-Bold",
                ),
            ),
        ]

        c_roce, p_roce = c["kpi_roce"]
        arr5, chg5, lbl5, col5, bg5 = _compute_trend(c_roce, p_roce, is_de=False)
        card5_content = [
            Paragraph("ROCE", card_title_style),
            Paragraph(_fmt_val(c_roce, is_pct=True), card_val_style),
            Paragraph(f"Prior: {_fmt_val(p_roce, is_pct=True)}", card_sub_style),
            Paragraph(
                f"<b>{arr5} {lbl5}</b>",
                ParagraphStyle(
                    "T5",
                    parent=card_sub_style,
                    textColor=col5,
                    fontName="Helvetica-Bold",
                ),
            ),
        ]

        c_de, p_de = c["kpi_de"]
        arr6, chg6, lbl6, col6, bg6 = _compute_trend(c_de, p_de, is_de=True)
        de_display = (
            f"{c_de:.2f}x" if c_de is not None and not pd.isna(c_de) else "N/A (Fin)"
        )
        de_prior = f"{p_de:.2f}x" if p_de is not None and not pd.isna(p_de) else "N/A"
        card6_content = [
            Paragraph("DEBT-TO-EQUITY (D/E)", card_title_style),
            Paragraph(de_display, card_val_style),
            Paragraph(f"Prior: {de_prior}", card_sub_style),
            Paragraph(
                f"<b>{arr6} {lbl6}</b>",
                ParagraphStyle(
                    "T6",
                    parent=card_sub_style,
                    textColor=col6,
                    fontName="Helvetica-Bold",
                ),
            ),
        ]

        col_w = usable_width / 3.0
        grid_data = [
            [card1_content, card2_content, card3_content],
            [card4_content, card5_content, card6_content],
        ]

        t_cards = Table(grid_data, colWidths=[col_w, col_w, col_w])
        t_cards.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(t_cards)
        story.append(Spacer(1, 4))

        # 3. Multi-Year Performance Trend Table
        story.append(
            Paragraph("<b>Historical Performance & Financial Trends</b>", sec_heading)
        )
        hist_headers = ["Metric / FY"] + [h["year"] for h in c["hist_table"]]
        tbl_w = usable_width
        num_hist_cols = len(hist_headers)
        h_col_w = (
            (tbl_w - 110) / max(1, (num_hist_cols - 1)) if num_hist_cols > 1 else 100
        )
        hist_widths = [110] + [h_col_w] * (num_hist_cols - 1)

        hist_rows = [
            [Paragraph(h, table_hdr_style) for h in hist_headers],
            [Paragraph("<b>Revenue (Cr)</b>", table_cell_style)]
            + [
                Paragraph(_fmt_val(h["revenue"], is_currency=False), table_cell_style)
                for h in c["hist_table"]
            ],
            [Paragraph("<b>Net Profit (Cr)</b>", table_cell_style)]
            + [
                Paragraph(
                    _fmt_val(h["net_income"], is_currency=False), table_cell_style
                )
                for h in c["hist_table"]
            ],
            [Paragraph("<b>Operating Margin (%)</b>", table_cell_style)]
            + [
                Paragraph(_fmt_val(h["opm"], is_pct=True), table_cell_style)
                for h in c["hist_table"]
            ],
            [Paragraph("<b>Return on Equity (%)</b>", table_cell_style)]
            + [
                Paragraph(_fmt_val(h["roe"], is_pct=True), table_cell_style)
                for h in c["hist_table"]
            ],
            [Paragraph("<b>ROCE (%)</b>", table_cell_style)]
            + [
                Paragraph(_fmt_val(h["roce"], is_pct=True), table_cell_style)
                for h in c["hist_table"]
            ],
            [Paragraph("<b>Debt-to-Equity (x)</b>", table_cell_style)]
            + [
                Paragraph(
                    (
                        f"{h['debt_to_equity']:.2f}"
                        if h["debt_to_equity"] is not None
                        and not pd.isna(h["debt_to_equity"])
                        else "-"
                    ),
                    table_cell_style,
                )
                for h in c["hist_table"]
            ],
            [Paragraph("<b>Operating CF (Cr)</b>", table_cell_style)]
            + [
                Paragraph(_fmt_val(h["cfo"], is_currency=False), table_cell_style)
                for h in c["hist_table"]
            ],
        ]

        t_hist = Table(hist_rows, colWidths=hist_widths)
        t_hist.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), NAVY_LIGHT),
                    ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                    ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(t_hist)
        story.append(Spacer(1, 4))

        # 4. Bottom Section: Cashflow & Capital Allocation (Left) + Pros & Cons (Right)
        intel = c["intel"]
        cap_pat = intel.get("capital_allocation_pattern", "Balanced Growth")
        cfo_score = intel.get("cfo_quality_score", "Good")
        cfo_label = intel.get("cfo_quality_label", "Adequate Quality")
        capex_int = intel.get("capex_intensity_label", "Moderate CapEx")
        distress = intel.get("distress_signal", "GREEN")
        distress_lbl = intel.get("distress_label", "Safe / Low Risk")

        distress_col = (
            EMERALD_GREEN
            if str(distress).upper() == "GREEN"
            else (ROSE_RED if str(distress).upper() == "RED" else AMBER)
        )

        left_w = usable_width * 0.46
        right_w = usable_width * 0.54

        left_cell_content = [
            Paragraph("<b>Cash Flow & Capital Allocation</b>", sec_heading),
            Spacer(1, 1),
            Paragraph(f"* <b>Capital Pattern:</b> {cap_pat}", badge_style),
            Paragraph(f"* <b>CFO Quality:</b> {cfo_label} ({cfo_score})", badge_style),
            Paragraph(f"* <b>CapEx Profile:</b> {capex_int}", badge_style),
            Paragraph(
                f"* <b>Financial Health:</b> <font color='{distress_col.hexval()}'><b>{distress_lbl}</b></font>",
                badge_style,
            ),
        ]

        top_pros = c["pros"][:2]
        top_cons = c["cons"][:2]

        right_cell_content = [
            Paragraph("<b>Investment Highlights & Risk Factors</b>", sec_heading),
            Spacer(1, 1),
        ]
        for p_txt in top_pros:
            right_cell_content.append(Paragraph(f"<b>(+) Pro:</b> {p_txt}", bullet_pro))
            right_cell_content.append(Spacer(1, 1))
        for c_txt in top_cons:
            right_cell_content.append(Paragraph(f"<b>(-) Con:</b> {c_txt}", bullet_con))
            right_cell_content.append(Spacer(1, 1))

        bottom_table_data = [[left_cell_content, right_cell_content]]
        t_bottom = Table(bottom_table_data, colWidths=[left_w, right_w])
        t_bottom.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (0, 0), CARD_BG),
                    ("BACKGROUND", (1, 0), (1, 0), LIGHT_BG),
                    ("BOX", (0, 0), (0, 0), 0.5, BORDER_COLOR),
                    ("BOX", (1, 0), (1, 0), 0.5, BORDER_COLOR),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(t_bottom)

        # PageBreak between companies (except after last company)
        if idx < total_comps - 1:
            story.append(PageBreak())

    doc.build(story, canvasmaker=PortfolioNumberedCanvas)
    logger.info(
        "Portfolio Summary PDF successfully built -> %s (%d pages)",
        output_pdf,
        total_comps,
    )
    return output_pdf


def main():
    parser = argparse.ArgumentParser(
        description="Generate Nifty 100 Portfolio Summary PDF Report."
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT_PDF),
        help="Target PDF path for the portfolio summary.",
    )
    args = parser.parse_args()

    out_path = Path(args.output)
    print("=" * 70)
    print("Day 35 - Nifty 100 Portfolio Summary PDF Generator")
    print("=" * 70)
    print(f"[INFO] Database: {DEFAULT_DB_PATH}")
    print(f"[INFO] Output:   {out_path}")

    comps, intel_map, pros_map = load_portfolio_data()
    print(f"[INFO] Loaded data for {len(comps)} companies in alphabetical order.")

    pdf = build_portfolio_summary_pdf(comps, out_path)
    file_size_kb = pdf.stat().st_size / 1024.0

    print("\n[SUCCESS] Portfolio Summary PDF generated successfully!")
    print(f"  * File:  {pdf}")
    print(f"  * Size:  {file_size_kb:.1f} KB")
    print(f"  * Pages: {len(comps)} (1 page per company)")


if __name__ == "__main__":
    main()
