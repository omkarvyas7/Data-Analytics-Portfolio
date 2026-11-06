"""Build the Excel WBR (excel/Returns_WBR_<week>.xlsx).

The summary tab runs on formulas (INDEX/MATCH and AVERAGEIFS over 'Weekly KPI Data'), so changing
the week or a target on 'Targets & Inputs' recalculates it. Column Q keeps the SQL RAG next to the
Excel RAG so you can check they agree.
"""
from datetime import date

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from config import KPI_ORDER, RAG_FILLS

HDR_FILL = PatternFill("solid", fgColor="232F3E")
HDR_FONT = Font(color="FFFFFF", bold=True)
INPUT_FILL = PatternFill("solid", fgColor="FFF9C4")
THIN = Side(style="thin", color="BDBDBD")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
UNIT_FMT = {"pct": "0.0%", "days": "0.00", "usd": "$#,##0.00", "units": "#,##0", "ratio": "0.000"}


def _header(ws, row, headers, col=1):
    for j, h in enumerate(headers):
        c = ws.cell(row=row, column=col + j, value=h)
        c.fill, c.font, c.border = HDR_FILL, HDR_FONT, BORDER
        c.alignment = Alignment(wrap_text=True, vertical="center")


def _write_df(ws, df, row=1, col=1, formats=None):
    _header(ws, row, list(df.columns), col)
    for i, rec in enumerate(df.itertuples(index=False), start=row + 1):
        for j, v in enumerate(rec):
            if isinstance(v, float) and v != v:
                v = None
            c = ws.cell(row=i, column=col + j, value=v)
            c.border = BORDER
            name = df.columns[j]
            if formats and name in formats:
                c.number_format = formats[name]
    return row + len(df)


def _widths(ws, widths):
    for k, w in widths.items():
        ws.column_dimensions[k].width = w


def _rag_cf(ws, rng):
    for label, fill in RAG_FILLS.items():
        ws.conditional_formatting.add(
            rng, CellIsRule(operator="equal", formula=[f'"{label}"'], fill=PatternFill("solid", fgColor=fill)))


def _axes(chart):
    chart.x_axis.delete = False
    chart.y_axis.delete = False


def build_wbr_workbook(res, weekly, targets, narrative, week, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "WBR Summary"
    wt = wb.create_sheet("Targets & Inputs")
    wd = wb.create_sheet("Weekly KPI Data")

    # ---------------- Weekly KPI Data ----------------
    data_cols = ["week_start"] + KPI_ORDER + ["units_shipped", "return_units", "refund_usd", "recovered_usd"]
    w = weekly[data_cols].copy()
    w["week_start"] = pd.to_datetime(w["week_start"])
    _header(wd, 1, data_cols)
    t_units = dict(zip(targets["kpi"], targets["unit"]))
    for i, rec in enumerate(w.itertuples(index=False), start=2):
        for j, v in enumerate(rec, start=1):
            c = wd.cell(row=i, column=j, value=v.to_pydatetime() if j == 1 else float(v))
            name = data_cols[j - 1]
            c.number_format = "yyyy-mm-dd" if j == 1 else UNIT_FMT.get(t_units.get(name, ""), "#,##0")
    wd.freeze_panes = "B2"
    for j in range(1, len(data_cols) + 1):
        wd.column_dimensions[get_column_letter(j)].width = 16
    last_data_row = len(w) + 1
    kpi_last_col = get_column_letter(1 + len(KPI_ORDER))  # I

    # ---------------- Targets & Inputs ----------------
    wt["A1"] = "Targets & Inputs (yellow cells are inputs: edit a target, the amber band or the report week and the WBR Summary recalculates)"
    wt["A1"].font = Font(bold=True)
    tcols = ["kpi", "display_name", "unit", "direction", "target", "amber_band", "owner_team", "initiative_id"]
    _header(wt, 3, tcols)
    for i, rec in enumerate(targets[tcols].itertuples(index=False), start=4):
        for j, v in enumerate(rec, start=1):
            c = wt.cell(row=i, column=j, value=v)
            c.border = BORDER
            if tcols[j - 1] == "target":
                c.number_format = UNIT_FMT[rec[2]]
                c.fill = INPUT_FILL
            if tcols[j - 1] == "amber_band":
                c.number_format = "0.0%"
                c.fill = INPUT_FILL
    wt["A14"] = "Report week (Monday)"
    wt["A14"].font = Font(bold=True)
    wt["C14"] = date.fromisoformat(week)
    wt["C14"].number_format = "yyyy-mm-dd"
    wt["C14"].fill = INPUT_FILL
    wt["A15"] = "Valid weeks"
    wt["C15"] = f"=TEXT(MIN('Weekly KPI Data'!A2:A{last_data_row}),\"yyyy-mm-dd\")&\" to \"&TEXT(MAX('Weekly KPI Data'!A2:A{last_data_row}),\"yyyy-mm-dd\")"
    _widths(wt, {"A": 22, "B": 40, "C": 12, "D": 10, "E": 12, "F": 12, "G": 26, "H": 12})

    # ---------------- WBR Summary ----------------
    ws["A1"] = "Returns Program: Weekly Business Review"
    ws["A1"].font = Font(size=16, bold=True)
    ws["A2"] = "Week starting"
    ws["B2"] = "='Targets & Inputs'!C14"
    ws["B2"].number_format = "yyyy-mm-dd"
    ws["C2"] = "Week ending"
    ws["D2"] = "=B2+6"
    ws["D2"].number_format = "yyyy-mm-dd"
    ws["A3"] = "Headline (written by src/narrative.py from the SQL results)"
    ws["A3"].font = Font(bold=True, italic=True)
    r0 = 4
    for i, line in enumerate(narrative["headline"]):
        c = ws.cell(row=r0 + i, column=1, value=f"- {line}")
        ws.merge_cells(start_row=r0 + i, start_column=1, end_row=r0 + i, end_column=17)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r0 + i].height = 30
    hr = r0 + len(narrative["headline"]) + 1
    heads = ["kpi", "KPI", "Unit", "Better", "Current", "Prior wk", "WoW chg", "WoW %", "Last year", "YoY %",
             "T4W avg", "Target", "Amber band", "Variance", "Variance % (unfav +)", "RAG (Excel)", "RAG (SQL)"]
    _header(ws, hr, heads)
    data_rng = f"'Weekly KPI Data'!$B:${kpi_last_col}"
    hdr_rng = f"'Weekly KPI Data'!$B$1:${kpi_last_col}$1"
    date_rng = "'Weekly KPI Data'!$A:$A"
    sql_rag = dict(zip(res["kpi_rag"]["kpi"], res["kpi_rag"]["rag"]))
    first = hr + 1
    for i, t in enumerate(targets.sort_values("sort_order").itertuples(index=False), start=first):
        col_match = f"MATCH($A{i},{hdr_rng},0)"

        def pick(offset):
            return f"=IFERROR(INDEX({data_rng},MATCH($B$2{offset},{date_rng},0),{col_match}),\"\")"
        vals = {
            "A": t.kpi, "B": t.display_name, "C": t.unit, "D": t.direction,
            "E": pick(""), "F": pick("-7"), "G": f"=IFERROR(E{i}-F{i},\"\")", "H": f"=IFERROR(G{i}/F{i},\"\")",
            "I": pick("-364"), "J": f"=IFERROR((E{i}-I{i})/I{i},\"\")",
            "K": f"=AVERAGEIFS(INDEX({data_rng},0,{col_match}),{date_rng},\">=\"&($B$2-21),{date_rng},\"<=\"&$B$2)",
            "L": f"=INDEX('Targets & Inputs'!$E:$E,MATCH($A{i},'Targets & Inputs'!$A:$A,0))",
            "M": f"=INDEX('Targets & Inputs'!$F:$F,MATCH($A{i},'Targets & Inputs'!$A:$A,0))",
            "N": f"=E{i}-L{i}",
            "O": f"=IF(D{i}=\"lower\",(E{i}-L{i})/L{i},(L{i}-E{i})/L{i})",
            "P": (f"=IF(D{i}=\"lower\",IF(E{i}<=L{i},\"Green\",IF(E{i}<=L{i}*(1+M{i}),\"Amber\",\"Red\")),"
                  f"IF(E{i}>=L{i},\"Green\",IF(E{i}>=L{i}*(1-M{i}),\"Amber\",\"Red\")))"),
            "Q": sql_rag[t.kpi],
        }
        for col, v in vals.items():
            c = ws[f"{col}{i}"]
            c.value = v
            c.border = BORDER
        fmt = UNIT_FMT[t.unit]
        for col in ["E", "F", "G", "I", "K", "L", "N"]:
            ws[f"{col}{i}"].number_format = fmt
        for col in ["H", "J", "M", "O"]:
            ws[f"{col}{i}"].number_format = "0.0%"
    last = first + len(targets) - 1
    _rag_cf(ws, f"P{first}:Q{last}")
    ws.conditional_formatting.add(f"O{first}:O{last}", ColorScaleRule(
        start_type="num", start_value=-0.1, start_color="C8E6C9", mid_type="num", mid_value=0,
        mid_color="FFFFFF", end_type="num", end_value=0.15, end_color="EF9A9A"))
    sr = last + 2
    ws[f"A{sr}"] = "KPI status count"
    ws[f"A{sr}"].font = Font(bold=True)
    for k, lab in enumerate(["Green", "Amber", "Red"]):
        ws.cell(row=sr + 1 + k, column=1, value=lab)
        ws.cell(row=sr + 1 + k, column=2, value=f"=COUNTIF($P${first}:$P${last},\"{lab}\")")
        ws.cell(row=sr + 1 + k, column=3, value=f"=COUNTIF($Q${first}:$Q${last},\"{lab}\")")
    ws.cell(row=sr, column=2, value="Excel")
    ws.cell(row=sr, column=3, value="SQL")
    _rag_cf(ws, f"A{sr + 1}:A{sr + 3}")
    ar = sr + 5
    ws[f"A{ar}"] = "Asks and escalations (P1)"
    ws[f"A{ar}"].font = Font(bold=True)
    for i, a in enumerate(narrative["asks"], start=ar + 1):
        ws.cell(row=i, column=1, value=f"- {a}")
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=17)
        ws.cell(row=i, column=1).alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[i].height = 30
    ws.freeze_panes = f"A{first}"
    _widths(ws, {"A": 20, "B": 34, "C": 7, "D": 8, "E": 11, "F": 11, "G": 10, "H": 9, "I": 11, "J": 9,
                 "K": 11, "L": 11, "M": 9, "N": 10, "O": 12, "P": 12, "Q": 11})

    # ---------------- Trends (native line charts, 26 weeks) ----------------
    wtr = wb.create_sheet("Trends", 1)
    tr = res["kpi_trend"].copy()
    tr["week_start"] = pd.to_datetime(tr["week_start"])
    wide = tr.pivot(index="week_start", columns="kpi", values="value")[KPI_ORDER].tail(26)
    tgt = tr.pivot(index="week_start", columns="kpi", values="target")[KPI_ORDER].tail(26)
    wtr["A1"] = "Last 26 weeks: weekly value and target per KPI (charts below the table)"
    wtr["A1"].font = Font(bold=True)
    heads = ["week_start"] + [f"{k}" for k in KPI_ORDER] + [f"{k}_target" for k in KPI_ORDER]
    _header(wtr, 2, heads)
    for i, (wk, row) in enumerate(wide.iterrows(), start=3):
        wtr.cell(row=i, column=1, value=wk.to_pydatetime()).number_format = "mm-dd"
        for j, k in enumerate(KPI_ORDER):
            c1 = wtr.cell(row=i, column=2 + j, value=float(row[k]))
            c2 = wtr.cell(row=i, column=2 + len(KPI_ORDER) + j, value=float(tgt.loc[wk, k]))
            c1.number_format = c2.number_format = UNIT_FMT[t_units[k]]
    n = len(wide)
    labels = dict(zip(targets["kpi"], targets["display_name"]))
    for j, k in enumerate(KPI_ORDER):
        ch = LineChart()
        ch.title = labels[k]
        ch.height, ch.width = 6.5, 11.5
        ch.add_data(Reference(wtr, min_col=2 + j, min_row=2, max_row=2 + n), titles_from_data=True)
        ch.add_data(Reference(wtr, min_col=2 + len(KPI_ORDER) + j, min_row=2, max_row=2 + n), titles_from_data=True)
        ch.set_categories(Reference(wtr, min_col=1, min_row=3, max_row=2 + n))
        ch.series[1].graphicalProperties.line.dashStyle = "dash"
        ch.y_axis.number_format = UNIT_FMT[t_units[k]]
        ch.x_axis.number_format = "mm-dd"
        _axes(ch)
        anchor_row = 3 + n + 2 + (j // 2) * 14
        anchor_col = "A" if j % 2 == 0 else "J"
        wtr.add_chart(ch, f"{anchor_col}{anchor_row}")
    wtr.column_dimensions["A"].width = 11

    # ---------------- Top Movers ----------------
    wm = wb.create_sheet("Top Movers")
    mv = res["top_movers"].copy()
    wm["A1"] = "Top movers by category (rank 1 = largest absolute WoW % move within the KPI)"
    wm["A1"].font = Font(bold=True)
    end = _write_df(wm, mv, row=3, formats={"current_week": "0.000", "prior_week": "0.000", "last_year": "0.000",
                                           "wow_abs": "0.000", "wow_pct": "0.0%", "yoy_abs": "0.000", "yoy_pct": "0.0%"})
    wm.conditional_formatting.add(f"I4:I{end}", DataBarRule(start_type="min", end_type="max", color="5C6BC0"))
    wm.conditional_formatting.add(f"J4:J{end}", CellIsRule(operator="equal", formula=['"Unfavourable"'], fill=PatternFill("solid", fgColor=RAG_FILLS["Red"])))
    wm.conditional_formatting.add(f"J4:J{end}", CellIsRule(operator="equal", formula=['"Favourable"'], fill=PatternFill("solid", fgColor=RAG_FILLS["Green"])))
    rc = mv[mv["kpi"] == "refund_cycle_days"].index
    if len(rc):
        bc = BarChart()
        bc.type = "bar"
        bc.title = "Refund cycle time YoY % by category"
        bc.add_data(Reference(wm, min_col=9, min_row=4 + rc.min(), max_row=4 + rc.max()), titles_from_data=False)
        bc.set_categories(Reference(wm, min_col=1, min_row=4 + rc.min(), max_row=4 + rc.max()))
        bc.legend = None
        bc.y_axis.number_format = "0%"
        _axes(bc)
        bc.height, bc.width = 7, 13
        wm.add_chart(bc, f"M3")
    _widths(wm, {"A": 13, "B": 20, "J": 13})

    # ---------------- Refund Cycle Drivers ----------------
    wr = wb.create_sheet("Refund Cycle Drivers")
    wr["A1"] = "Refund cycle time decomposition: current week vs 4-week pre-incident baseline (rate + mix = total effect, days)"
    wr["A1"].font = Font(bold=True)
    dv = res["cycle_driver"].copy()
    dv.insert(0, "segment", dv["marketplace"] + " " + dv["channel"])
    end = _write_df(wr, dv, row=3, formats={c: "0.000" for c in dv.columns if c not in ("segment", "marketplace", "channel", "driver_rank")}
                    | {"share_base": "0.0%", "share_cur": "0.0%"})
    wr.conditional_formatting.add(f"M4:M{end}", ColorScaleRule(start_type="min", start_color="C8E6C9", mid_type="num",
                                                               mid_value=0, mid_color="FFFFFF", end_type="max", end_color="EF9A9A"))
    wr.cell(row=end + 1, column=1, value="Total (= program change, days)").font = Font(bold=True)
    for col in ["K", "L", "M"]:
        c = wr[f"{col}{end + 1}"]
        c.value = f"=SUM({col}4:{col}{end})"
        c.number_format = "0.000"
        c.font = Font(bold=True)
    bc = BarChart()
    bc.type = "bar"
    bc.title = "Total effect by segment (days)"
    bc.add_data(Reference(wr, min_col=13, min_row=3, max_row=min(end, 11)), titles_from_data=True)
    bc.set_categories(Reference(wr, min_col=1, min_row=4, max_row=min(end, 11)))
    bc.legend = None
    _axes(bc)
    bc.height, bc.width = 7, 13
    wr.add_chart(bc, f"A{end + 4}")
    _widths(wr, {"A": 20, "B": 12, "C": 16})

    # ---------------- Program Health ----------------
    wp = wb.create_sheet("Program Health")
    wp["A1"] = "Program health by initiative (RAG rules documented in sql/06_program_health_initiative.sql)"
    wp["A1"].font = Font(bold=True)
    ph = res["program_health"].copy()
    end = _write_df(wp, ph, row=3)
    rag_col = get_column_letter(list(ph.columns).index("program_rag") + 1)
    _rag_cf(wp, f"{rag_col}4:{rag_col}{end}")
    ms = res["milestones"]
    risk_ms = ms[ms["at_risk_flag"] == 1][["initiative_id", "milestone_id", "milestone", "owner_role", "planned_end",
                                            "forecast_end", "status", "pct_complete", "schedule_variance_days",
                                            "blocked_by_dependency", "milestone_rag"]]
    r2 = end + 3
    wp.cell(row=r2 - 1, column=1, value="Milestones at risk").font = Font(bold=True)
    end2 = _write_df(wp, risk_ms, row=r2)
    _rag_cf(wp, f"K{r2 + 1}:K{end2}")
    wp.conditional_formatting.add(f"I{r2 + 1}:I{end2}", DataBarRule(start_type="num", start_value=0, end_type="max", color="E57373"))
    r3 = end2 + 3
    wp.cell(row=r3 - 1, column=1, value="Blocked by dependency").font = Font(bold=True)
    _write_df(wp, res["blocked"], row=r3)
    for j in range(1, 18):
        wp.column_dimensions[get_column_letter(j)].width = 18
    wp.column_dimensions["B"].width = 36
    wp.column_dimensions["C"].width = 36

    # ---------------- Risks ----------------
    wk = wb.create_sheet("Risks")
    wk["A1"] = "Open risks (severity = likelihood x impact; High >= 15)"
    wk["A1"].font = Font(bold=True)
    rk = res["risks"].copy()
    end = _write_df(wk, rk, row=3)
    sev_col = get_column_letter(list(rk.columns).index("severity") + 1)
    wk.conditional_formatting.add(f"{sev_col}4:{sev_col}{end}", ColorScaleRule(
        start_type="num", start_value=1, start_color="C8E6C9", mid_type="num", mid_value=10,
        mid_color="FFE082", end_type="num", end_value=25, end_color="EF9A9A"))
    esc_col = get_column_letter(list(rk.columns).index("needs_escalation") + 1)
    wk.conditional_formatting.add(f"A4:{get_column_letter(len(rk.columns))}{end}", FormulaRule(
        formula=[f"${esc_col}4=1"], font=Font(bold=True, color="B71C1C")))
    _widths(wk, {"C": 34, "D": 50, "K": 44})

    # ---------------- Gap List ----------------
    wg = wb.create_sheet("Gap List")
    wg["A1"] = "Gap list routed to partner teams (due before the next WBR)"
    wg["A1"].font = Font(bold=True)
    gl = res["gap_list"].copy()
    end = _write_df(wg, gl, row=3)
    wg.conditional_formatting.add(f"A4:A{end}", CellIsRule(operator="equal", formula=['"P1"'], fill=PatternFill("solid", fgColor=RAG_FILLS["Red"])))
    wg.conditional_formatting.add(f"A4:A{end}", CellIsRule(operator="equal", formula=['"P2"'], fill=PatternFill("solid", fgColor=RAG_FILLS["Amber"])))
    tr0 = end + 3
    wg.cell(row=tr0, column=1, value="Gaps by team").font = Font(bold=True)
    _header(wg, tr0 + 1, ["team", "P1", "P2", "Total"])
    for i, team in enumerate(sorted(gl["team"].unique()), start=tr0 + 2):
        wg.cell(row=i, column=1, value=team)
        wg.cell(row=i, column=2, value=f"=COUNTIFS($C$4:$C${end},A{i},$A$4:$A${end},\"P1\")")
        wg.cell(row=i, column=3, value=f"=COUNTIFS($C$4:$C${end},A{i},$A$4:$A${end},\"P2\")")
        wg.cell(row=i, column=4, value=f"=B{i}+C{i}")
    _widths(wg, {"A": 9, "B": 22, "C": 26, "D": 34, "E": 48, "F": 70, "G": 60, "H": 12})
    for row in wg.iter_rows(min_row=4, max_row=end):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")

    wb.calculation.fullCalcOnLoad = True
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path
