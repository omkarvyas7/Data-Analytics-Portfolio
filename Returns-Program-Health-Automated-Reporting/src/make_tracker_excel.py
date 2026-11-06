"""Build excel/Program_Tracker.xlsx: the cross-functional initiative tracker.

Tabs
  Inputs          as-of date (named range AsOf); change it and every formula re-evaluates
  Initiatives     initiative master (owner role, team, primary KPI)
  Milestones      tracker rows; XLOOKUP pulls initiative / owner / team; formulas compute dependency
                  status, schedule variance, RAG; a Gantt-style weekly timeline is drawn with
                  formula-based conditional formatting (plan vs actual/forecast, coloured by status)
  Status Summary  COUNTIFS initiative x status matrix, AVERAGEIFS % complete, MAXIFS slip,
                  COUNTIFS open High risks, RAG formula, native stacked bar chart
  Risks           risk register with severity / level formulas and colour scale
  Issues          issue log with days-open formula
"""
from datetime import date, timedelta

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName

from config import RAW, EXCEL_DIR, DEFAULT_WEEK, RAG_FILLS

HDR_FILL = PatternFill("solid", fgColor="232F3E")
HDR_FONT = Font(color="FFFFFF", bold=True)
INPUT_FILL = PatternFill("solid", fgColor="FFF9C4")
THIN = Side(style="thin", color="BDBDBD")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
STATUSES = ["Complete", "On Track", "At Risk", "Blocked", "Not Started"]
STATUS_FILL = {"Complete": "90A4AE", "On Track": "66BB6A", "At Risk": "FFB300", "Blocked": "E53935", "Not Started": "CFD8DC"}


def _hdr(ws, row, heads, col=1):
    for j, h in enumerate(heads):
        c = ws.cell(row=row, column=col + j, value=h)
        c.fill, c.font, c.border = HDR_FILL, HDR_FONT, BORDER
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")


def _d(v):
    return None if v in ("", None) or (isinstance(v, float) and v != v) else date.fromisoformat(v)


def main(as_of=None):
    as_of = as_of or (date.fromisoformat(DEFAULT_WEEK) + timedelta(days=6))
    ini = pd.read_csv(RAW / "initiatives.csv", keep_default_na=False)
    ms = pd.read_csv(RAW / "milestones.csv", keep_default_na=False)
    rk = pd.read_csv(RAW / "risks.csv", keep_default_na=False)
    iss = pd.read_csv(RAW / "issues.csv", keep_default_na=False)

    wb = Workbook()
    wi = wb.active
    wi.title = "Inputs"
    wi["A1"] = "Program Tracker: Returns Experience & ReCommerce initiatives"
    wi["A1"].font = Font(size=14, bold=True)
    wi["A3"] = "Status as-of date"
    wi["B3"] = as_of
    wi["B3"].number_format = "yyyy-mm-dd"
    wi["B3"].fill = INPUT_FILL
    wi["A4"] = "Slip threshold Amber (days)"
    wi["B4"] = 7
    wi["A5"] = "Slip threshold Red (days)"
    wi["B5"] = 21
    for c in ("B4", "B5"):
        wi[c].fill = INPUT_FILL
    wi["A7"] = ("Yellow cells are inputs. Change the as-of date to replay the tracker at any point in time; "
                "schedule variance, RAG and the Gantt 'today' marker follow it.")
    wi.column_dimensions["A"].width = 30
    wi.column_dimensions["B"].width = 14
    wb.defined_names["AsOf"] = DefinedName("AsOf", attr_text="Inputs!$B$3")
    wb.defined_names["SlipAmber"] = DefinedName("SlipAmber", attr_text="Inputs!$B$4")
    wb.defined_names["SlipRed"] = DefinedName("SlipRed", attr_text="Inputs!$B$5")

    # ---------------- Initiatives ----------------
    wn = wb.create_sheet("Initiatives")
    cols = list(ini.columns)
    _hdr(wn, 1, cols)
    for i, rec in enumerate(ini.itertuples(index=False), start=2):
        for j, v in enumerate(rec, start=1):
            c = wn.cell(row=i, column=j, value=_d(v) if cols[j - 1].endswith("date") else v)
            c.border = BORDER
            if cols[j - 1].endswith("date"):
                c.number_format = "yyyy-mm-dd"
    for j, w in enumerate([12, 40, 36, 26, 20, 12, 14], start=1):
        wn.column_dimensions[get_column_letter(j)].width = w

    # ---------------- Milestones + Gantt ----------------
    wm = wb.create_sheet("Milestones")
    heads = ["milestone_id", "initiative_id", "Initiative (XLOOKUP)", "Initiative owner (XLOOKUP)", "Team (XLOOKUP)",
             "milestone", "milestone_owner_role", "planned_start", "planned_end", "actual_start", "actual_end",
             "forecast_end", "status", "pct_complete", "depends_on", "Dependency status", "Schedule variance (d)", "RAG"]
    HR = 4
    _hdr(wm, HR, heads)
    wm["A1"] = "Milestone tracker with Gantt timeline (weekly columns; outline = plan window, fill = actual/forecast coloured by status, red border = as-of week)"
    wm["A1"].font = Font(bold=True)
    wm["A2"] = "As of"
    wm["B2"] = "=AsOf"
    wm["B2"].number_format = "yyyy-mm-dd"
    first = HR + 1
    last = first + len(ms) - 1
    for i, r in enumerate(ms.itertuples(index=False), start=first):
        vals = [r.milestone_id, r.initiative_id,
                f'=_xlfn.XLOOKUP(B{i},Initiatives!$A:$A,Initiatives!$B:$B,"not found")',
                f'=_xlfn.XLOOKUP(B{i},Initiatives!$A:$A,Initiatives!$C:$C,"not found")',
                f'=_xlfn.XLOOKUP(B{i},Initiatives!$A:$A,Initiatives!$D:$D,"not found")',
                r.milestone, r.owner_role, _d(r.planned_start), _d(r.planned_end), _d(r.actual_start),
                _d(r.actual_end), _d(r.forecast_end), r.status, int(r.pct_complete) / 100, r.depends_on or None,
                f'=IF(O{i}="","",_xlfn.XLOOKUP(O{i},$A${first}:$A${last},$M${first}:$M${last},"n/a"))',
                f'=IF(K{i}<>"",K{i}-I{i},IF(L{i}<>"",L{i}-I{i},IF(I{i}<AsOf,AsOf-I{i},0)))',
                (f'=IF(M{i}="Complete","Complete",IF(OR(M{i}="Blocked",AND(P{i}<>"",P{i}<>"Complete",H{i}<=AsOf),Q{i}>SlipRed),"Red",'
                 f'IF(OR(M{i}="At Risk",Q{i}>SlipAmber,AND(J{i}="",H{i}<=AsOf)),"Amber","Green")))')]
        for j, v in enumerate(vals, start=1):
            c = wm.cell(row=i, column=j, value=v)
            c.border = BORDER
            if 8 <= j <= 12:
                c.number_format = "yyyy-mm-dd"
                if j in (10, 11, 12):
                    c.fill = INPUT_FILL
            if j == 13:
                c.fill = INPUT_FILL
            if j == 14:
                c.number_format = "0%"
                c.fill = INPUT_FILL
    for j, w in enumerate([10, 9, 34, 30, 22, 38, 30, 11, 11, 11, 11, 11, 11, 8, 9, 12, 11, 10], start=1):
        wm.column_dimensions[get_column_letter(j)].width = w
    for lab, fill in RAG_FILLS.items():
        wm.conditional_formatting.add(f"R{first}:R{last}", CellIsRule(operator="equal", formula=[f'"{lab}"'], fill=PatternFill("solid", fgColor=fill)))
    for st, fill in STATUS_FILL.items():
        wm.conditional_formatting.add(f"M{first}:M{last}", CellIsRule(operator="equal", formula=[f'"{st}"'], fill=PatternFill("solid", fgColor=fill)))
    wm.conditional_formatting.add(f"Q{first}:Q{last}", ColorScaleRule(start_type="num", start_value=0, start_color="FFFFFF",
                                                                      end_type="num", end_value=60, end_color="EF5350"))
    # Gantt timeline: weekly columns
    g0 = len(heads) + 2  # leave one spacer column
    start = date(2026, 1, 5)
    weeks = [start + timedelta(weeks=k) for k in range(56)]
    for k, wk in enumerate(weeks):
        col = g0 + k
        c = wm.cell(row=HR, column=col, value=wk)
        c.number_format = "mmm d"
        c.alignment = Alignment(text_rotation=90, horizontal="center")
        c.fill, c.font = HDR_FILL, Font(color="FFFFFF", size=8)
        wm.column_dimensions[get_column_letter(col)].width = 2.6
    gl = get_column_letter(g0)
    gr = get_column_letter(g0 + len(weeks) - 1)
    rng = f"{gl}{first}:{gr}{last}"
    top = f"{gl}${HR}"
    # bar end = actual_end, else forecast_end, else planned_end; bar start = actual_start, else planned_start
    bar = (f"AND({top}+6>=IF($J{first}<>\"\",$J{first},$H{first}),"
           f"{top}<=IF($K{first}<>\"\",$K{first},IF($L{first}<>\"\",$L{first},$I{first})))")
    plan = f"AND({top}+6>=$H{first},{top}<=$I{first})"
    wm.conditional_formatting.add(rng, FormulaRule(formula=[f"AND({top}<=AsOf,{top}+6>=AsOf)"],
                                                   border=Border(left=Side(style="medium", color="C62828"), right=Side(style="medium", color="C62828"))))
    for st, fill in STATUS_FILL.items():
        wm.conditional_formatting.add(rng, FormulaRule(formula=[f"AND({bar},$M{first}=\"{st}\")"],
                                                       fill=PatternFill("solid", fgColor=fill), stopIfTrue=True))
    wm.conditional_formatting.add(rng, FormulaRule(formula=[plan], fill=PatternFill("lightGray", fgColor="B0BEC5")))
    wm.freeze_panes = f"G{first}"

    # ---------------- Risks ----------------
    wr = wb.create_sheet("Risks")
    rcols = list(rk.columns)
    heads = rcols[:5] + ["severity", "level"] + rcols[5:] + ["days_open"]
    _hdr(wr, 1, heads)
    for i, r in enumerate(rk.itertuples(index=False), start=2):
        vals = [r.risk_id, r.initiative_id, r.risk, int(r.likelihood), int(r.impact), f"=D{i}*E{i}",
                f'=IF(F{i}>=15,"High",IF(F{i}>=8,"Medium","Low"))', r.status, r.owner_role, r.mitigation or None,
                _d(r.opened_date), _d(r.target_close_date), f'=IF(H{i}="Closed","",AsOf-K{i})']
        for j, v in enumerate(vals, start=1):
            c = wr.cell(row=i, column=j, value=v)
            c.border = BORDER
            if j in (11, 12):
                c.number_format = "yyyy-mm-dd"
    rl = len(rk) + 1
    wr.conditional_formatting.add(f"F2:F{rl}", ColorScaleRule(start_type="num", start_value=1, start_color="C8E6C9",
                                                              mid_type="num", mid_value=10, mid_color="FFE082",
                                                              end_type="num", end_value=25, end_color="EF9A9A"))
    wr.conditional_formatting.add(f"A2:M{rl}", FormulaRule(formula=['AND($G2="High",$H2<>"Closed",OR($J2="",$L2<AsOf))'],
                                                           font=Font(bold=True, color="B71C1C")))
    for j, w in enumerate([7, 9, 50, 10, 8, 9, 9, 11, 30, 44, 11, 11, 9], start=1):
        wr.column_dimensions[get_column_letter(j)].width = w

    # ---------------- Issues ----------------
    wv = wb.create_sheet("Issues")
    icols = list(iss.columns) + ["days_open"]
    _hdr(wv, 1, icols)
    for i, r in enumerate(iss.itertuples(index=False), start=2):
        vals = [r.issue_id, _d(r.logged_date), r.initiative_id, r.milestone_id, r.issue, r.status, r.owner_role,
                f'=IF(F{i}="Open",AsOf-B{i},"")']
        for j, v in enumerate(vals, start=1):
            c = wv.cell(row=i, column=j, value=v)
            c.border = BORDER
            if j == 2:
                c.number_format = "yyyy-mm-dd"
    wv.conditional_formatting.add(f"F2:F{len(iss) + 1}", CellIsRule(operator="equal", formula=['"Open"'], fill=PatternFill("solid", fgColor=RAG_FILLS["Amber"])))
    for j, w in enumerate([9, 11, 9, 10, 60, 8, 30, 9], start=1):
        wv.column_dimensions[get_column_letter(j)].width = w

    # ---------------- Status Summary ----------------
    wsu = wb.create_sheet("Status Summary", 1)
    wsu["A1"] = "Status summary (COUNTIFS / AVERAGEIFS / MAXIFS over the Milestones and Risks tabs)"
    wsu["A1"].font = Font(bold=True)
    heads = ["initiative_id", "Initiative"] + STATUSES + ["Total", "Avg % complete", "Max slip (d)", "Red milestones",
                                                          "Open High risks", "Initiative RAG"]
    _hdr(wsu, 3, heads)
    M = "Milestones!"
    for i, r in enumerate(ini.itertuples(index=False), start=4):
        wsu.cell(row=i, column=1, value=r.initiative_id)
        wsu.cell(row=i, column=2, value=f'=_xlfn.XLOOKUP(A{i},Initiatives!$A:$A,Initiatives!$B:$B)')
        for k, st in enumerate(STATUSES):
            col = get_column_letter(3 + k)
            wsu[f"{col}{i}"] = f'=COUNTIFS({M}$B${first}:$B${last},$A{i},{M}$M${first}:$M${last},{col}$3)'
        wsu[f"H{i}"] = f"=SUM(C{i}:G{i})"
        wsu[f"I{i}"] = f"=AVERAGEIFS({M}$N${first}:$N${last},{M}$B${first}:$B${last},$A{i})"
        wsu[f"I{i}"].number_format = "0%"
        wsu[f"J{i}"] = f"=_xlfn.MAXIFS({M}$Q${first}:$Q${last},{M}$B${first}:$B${last},$A{i})"
        wsu[f"K{i}"] = f'=COUNTIFS({M}$B${first}:$B${last},$A{i},{M}$R${first}:$R${last},"Red")'
        wsu[f"L{i}"] = f'=COUNTIFS(Risks!$B:$B,$A{i},Risks!$G:$G,"High",Risks!$H:$H,"<>Closed")'
        wsu[f"M{i}"] = (f'=IF(K{i}>0,"Red",IF(OR(COUNTIFS({M}$B${first}:$B${last},$A{i},{M}$R${first}:$R${last},"Amber")>0,L{i}>0),"Amber","Green"))')
        for j in range(1, 14):
            wsu.cell(row=i, column=j).border = BORDER
    tl = 3 + len(ini)
    tr = tl + 1
    wsu.cell(row=tr, column=2, value="Program total").font = Font(bold=True)
    for k in range(3, 9):
        col = get_column_letter(k)
        wsu[f"{col}{tr}"] = f"=SUM({col}4:{col}{tl})"
    wsu[f"K{tr}"] = f"=SUM(K4:K{tl})"
    wsu[f"L{tr}"] = f"=SUM(L4:L{tl})"
    for lab, fill in RAG_FILLS.items():
        wsu.conditional_formatting.add(f"M4:M{tl}", CellIsRule(operator="equal", formula=[f'"{lab}"'], fill=PatternFill("solid", fgColor=fill)))
    wsu.conditional_formatting.add(f"E4:F{tl}", CellIsRule(operator="greaterThan", formula=["0"], fill=PatternFill("solid", fgColor="FFCDD2")))
    ch = BarChart()
    ch.type = "bar"
    ch.grouping = "stacked"
    ch.overlap = 100
    ch.title = "Milestones by status and initiative"
    ch.add_data(Reference(wsu, min_col=3, max_col=7, min_row=3, max_row=tl), titles_from_data=True)
    ch.set_categories(Reference(wsu, min_col=1, min_row=4, max_row=tl))
    for s, st in zip(ch.series, STATUSES):
        s.graphicalProperties.solidFill = STATUS_FILL[st]
    ch.x_axis.delete = False
    ch.y_axis.delete = False
    ch.height, ch.width = 8, 16
    wsu.add_chart(ch, f"A{tr + 3}")
    for j, w in enumerate([12, 40, 10, 10, 9, 9, 11, 7, 12, 11, 11, 12, 13], start=1):
        wsu.column_dimensions[get_column_letter(j)].width = w

    wb.calculation.fullCalcOnLoad = True
    EXCEL_DIR.mkdir(parents=True, exist_ok=True)
    out = EXCEL_DIR / "Program_Tracker.xlsx"
    wb.save(out)
    print(f"make_tracker_excel: {out.name} ({len(ms)} milestones, {len(rk)} risks, {len(iss)} issues)")


if __name__ == "__main__":
    main()
