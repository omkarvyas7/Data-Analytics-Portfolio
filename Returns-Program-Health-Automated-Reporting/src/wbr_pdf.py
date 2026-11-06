"""Build the 3-page PDF WBR with reportlab (reports/WBR_<week>.pdf)."""
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from xml.sax.saxutils import escape

from config import RAG_COLORS, fmt_kpi, fmt_delta

SS = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=SS["Heading1"], fontSize=15, spaceAfter=2, textColor=colors.HexColor("#232F3E"))
H2 = ParagraphStyle("h2", parent=SS["Heading2"], fontSize=11, spaceBefore=6, spaceAfter=3, textColor=colors.HexColor("#232F3E"))
BODY = ParagraphStyle("b", parent=SS["BodyText"], fontSize=8.6, leading=11, alignment=TA_LEFT)
BUL = ParagraphStyle("bul", parent=BODY, leftIndent=10, bulletIndent=0, spaceAfter=2)
SMALL = ParagraphStyle("s", parent=BODY, fontSize=7, leading=8.6, textColor=colors.HexColor("#555555"))
CELL = ParagraphStyle("c", parent=BODY, fontSize=7, leading=8.4)


def _p(text, style, **kw):
    return Paragraph(escape(str(text)), style, **kw)


def _rag_style(rows, col):
    st = []
    for i, r in enumerate(rows, start=1):
        c = RAG_COLORS.get(r)
        if c:
            st += [("BACKGROUND", (col, i), (col, i), colors.HexColor(c)), ("TEXTCOLOR", (col, i), (col, i), colors.white)]
    return st


def _base_table(data, widths, extra=None):
    t = Table(data, colWidths=widths, repeatRows=1)
    st = [("FONT", (0, 0), (-1, -1), "Helvetica", 7.2),
          ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.2),
          ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#232F3E")),
          ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
          ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BDBDBD")),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")])]
    t.setStyle(TableStyle(st + (extra or [])))
    return t


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.drawString(0.5 * inch, 0.35 * inch, "Synthetic data from src/generate_data.py. Built by src/run_wbr.py, and every number comes from sql/01-10.")
    canvas.drawRightString(8.0 * inch, 0.35 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build_wbr_pdf(res, narrative, charts, week, path):
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                            topMargin=0.45 * inch, bottomMargin=0.55 * inch,
                            title=f"Returns Program WBR {week}", author="Returns Program Health pipeline")
    s = res["kpi_summary"].set_index("kpi")
    r = res["kpi_rag"]
    story = []
    # ---------------- Page 1: headline + KPI table ----------------
    story.append(Paragraph("Returns Program: Weekly Business Review", H1))
    story.append(Paragraph(f"Week of {narrative['week_start']} to {narrative['week_end']} &nbsp;|&nbsp; generated "
                           f"{date.today().isoformat()} &nbsp;|&nbsp; scope: US, UK, DE, CA; all categories and return channels", SMALL))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Headline", H2))
    for line in narrative["headline"]:
        story.append(_p(line, BUL, bulletText="-"))
    story.append(Paragraph("KPI scorecard", H2))
    hdr = ["KPI", "Current", "Prior wk", "WoW", "Last year", "YoY %", "T4W avg", "Target", "Var %\n(unfav +)", "RAG", "Missed\nlast 4"]
    rows = [hdr]
    rags = []
    for _, x in r.iterrows():
        u = x["unit"]
        sx = s.loc[x["kpi"]]
        rows.append([_p(x["display_name"], CELL), fmt_kpi(x["actual"], u), fmt_kpi(sx["prior_week"], u),
                     fmt_delta(sx["wow_abs"], u), fmt_kpi(sx["last_year"], u),
                     f"{sx['yoy_pct'] * 100:+.1f}%", fmt_kpi(sx["t4w_avg"], u), fmt_kpi(x["target"], u),
                     f"{x['variance_pct'] * 100:+.1f}%", x["rag"], int(x["weeks_missed_last_4"])])
        rags.append(x["rag"])
    widths = [1.75, 0.68, 0.68, 0.68, 0.68, 0.5, 0.68, 0.68, 0.62, 0.48, 0.45]
    story.append(_base_table(rows, [w * inch for w in widths], _rag_style(rags, 9) + [("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
    c = narrative["counts"]
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Status: {c['green']} Green, {c['amber']} Amber, {c['red']} Red. RAG rule: Green = at or better than target; "
        f"Amber = worse than target but within the KPI's tolerance band (3-5%); Red = outside the band. "
        f"WoW = vs prior week; YoY = vs the same week 52 weeks earlier; T4W = mean of the last 4 weekly values. "
        f"Percent KPIs show WoW in percentage points.", SMALL))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Program health at a glance", H2))
    ph = res["program_health"]
    rows = [["Initiative", "Team", "Done", "At risk", "Blocked", "Max slip (d)", "Open High risks", "RAG"]]
    for _, x in ph.iterrows():
        rows.append([_p(x["initiative"], CELL), _p(x["team"], CELL), f"{x['milestones_complete']}/{x['milestones_total']}",
                     x["milestones_at_risk"], x["blocked_by_dependency"], x["max_slip_days"], x["open_high_risks"], x["program_rag"]])
    story.append(_base_table(rows, [w * inch for w in [2.3, 1.6, 0.55, 0.55, 0.6, 0.8, 0.9, 0.6]],
                             _rag_style(list(ph["program_rag"]), 7) + [("ALIGN", (2, 0), (-1, -1), "CENTER")]))
    story.append(PageBreak())

    # ---------------- Page 2: charts ----------------
    story.append(Paragraph("KPI trends (26 weeks)", H2))
    story.append(Image(str(charts["trends"]), width=7.15 * inch, height=3.1 * inch))
    story.append(Paragraph("Why refund cycle time is Red: driver decomposition", H2))
    story.append(Image(str(charts["driver"]), width=7.0 * inch, height=2.8 * inch))
    story.append(Paragraph("Top movers by category (YoY)", H2))
    story.append(Image(str(charts["movers"]), width=6.0 * inch, height=2.4 * inch))
    story.append(PageBreak())

    # ---------------- Page 3: program detail + asks ----------------
    story.append(Paragraph("Milestones at risk", H2))
    ms = res["milestones"]
    ms = ms[ms["at_risk_flag"] == 1]
    rows = [["ID", "Milestone", "Owner role", "Planned end", "Forecast", "Status", "Slip (d)", "RAG"]]
    for _, x in ms.iterrows():
        rows.append([x["milestone_id"], _p(x["milestone"], CELL), _p(x["owner_role"], CELL), x["planned_end"],
                     x["forecast_end"] if isinstance(x["forecast_end"], str) else "-", x["status"],
                     x["schedule_variance_days"], x["milestone_rag"]])
    story.append(_base_table(rows, [w * inch for w in [0.45, 2.2, 1.6, 0.75, 0.75, 0.75, 0.5, 0.5]],
                             _rag_style(list(ms["milestone_rag"]), 7)))
    story.append(Paragraph("Open High risks", H2))
    rk = res["risks"]
    rk = rk[rk["risk_level"] == "High"]
    rows = [["ID", "Risk", "Sev.", "Owner role", "Mitigation", "Close by"]]
    for _, x in rk.iterrows():
        rows.append([x["risk_id"], _p(x["risk"], CELL), x["severity"], _p(x["owner_role"], CELL),
                     _p(x["mitigation"], CELL), x["target_close_date"]])
    esc = [("TEXTCOLOR", (0, i), (-1, i), colors.HexColor("#B71C1C")) for i, v in enumerate(rk["needs_escalation"], start=1) if v == 1]
    story.append(_base_table(rows, [w * inch for w in [0.4, 2.3, 0.4, 1.5, 2.1, 0.8]], esc))
    story.append(Paragraph("Rows in red need escalation (no mitigation recorded or past target close date).", SMALL))
    story.append(Paragraph("Asks and escalations (P1, due before next WBR)", H2))
    for a in narrative["asks"]:
        story.append(_p(a, BUL, bulletText="-"))
    p2 = res["gap_list"]
    p2 = p2[p2["priority"] == "P2"]
    if len(p2):
        story.append(_p("Watch items (P2): " + "; ".join(f"{g['item']} ({g['team']})" for _, g in p2.iterrows()) + ".", BODY))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Refresh: the pipeline runs Monday 06:00 local after the Sunday data load (Task Scheduler or cron, "
                           "see src/schedule/), so this pre-read is out well before the Tuesday review.", SMALL))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return path
