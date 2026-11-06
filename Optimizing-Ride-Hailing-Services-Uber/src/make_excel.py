"""Build excel/Dispatch_KPI_Model.xlsx (results, summary, sensitivity, what-if).

KPIs on Summary / Sensitivity / WhatIf are live formulas over Results, so swapping in new
Results data recalculates everything.
"""
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

from common import DATA_PROCESSED, EXCEL_DIR, PROTOCOLS
from simulate import MDR_OPTIONS, SUPPLY_RATIOS

OUT = EXCEL_DIR / "Dispatch_KPI_Model.xlsx"
HDR_FILL = PatternFill("solid", fgColor="1F3A5F")
HDR_FONT = Font(bold=True, color="FFFFFF")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
TITLE = Font(bold=True, size=14, color="1F3A5F")
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def header(ws, row, values, col=1):
    for j, v in enumerate(values):
        c = ws.cell(row=row, column=col + j, value=v)
        c.fill, c.font, c.border = HDR_FILL, HDR_FONT, BOX
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def widths(ws, w):
    for i, x in enumerate(w, start=1):
        ws.column_dimensions[get_column_letter(i)].width = x


def main():
    res = pd.read_csv(DATA_PROCESSED / "simulation_results.csv")
    cols = list(res.columns)
    n = len(res)
    wb = Workbook()

    # ---------------- About ----------------
    ab = wb.active
    ab.title = "About"
    lines = [
        ("Dispatch KPI Model (simulation study)", TITLE),
        ("Source: data/processed/simulation_results.csv (1,000 seeded batching windows x 5 protocols).", None),
        ("All data is synthetic (numpy seed 42). None of it comes from Uber or any employer.", None),
        ("Tabs: Results (data) | Summary (KPI by protocol) | Sensitivity (MDR and supply) | "
         "Grid (lookup table) | WhatIf (scenario inputs).", None),
        ("Yellow cells on WhatIf are inputs. Every other number is a formula over Results.", None),
        ("avg ETA = SUM(total en-route min) / SUM(matched riders), rider-weighted to match sql/01.", None),
        ("Contribution ($) = modelled fare minus $0.65 per unpaid en-route mile. An assumption, not a P&L.", None),
    ]
    for i, (t, f) in enumerate(lines, start=1):
        c = ab.cell(row=i, column=1, value=t)
        if f:
            c.font = f
    ab.column_dimensions["A"].width = 120

    # ---------------- Results ----------------
    rs = wb.create_sheet("Results")
    header(rs, 1, cols)
    for r in res.itertuples(index=False):
        rs.append(list(r))
    last = n + 1
    tab = Table(displayName="tblResults", ref=f"A1:{get_column_letter(len(cols))}{last}")
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
    rs.add_table(tab)
    rs.freeze_panes = "A2"
    widths(rs, [10, 26] + [13] * (len(cols) - 2))
    col = {c: get_column_letter(i + 1) for i, c in enumerate(cols)}
    rng = lambda c: f"Results!${col[c]}$2:${col[c]}${last}"   # noqa: E731

    # ---------------- Summary ----------------
    sm = wb.create_sheet("Summary")
    sm["A1"], sm["A1"].font = "KPI scorecard by dispatch protocol (formulas over Results)", TITLE
    heads = ["Protocol", "Windows", "Riders requested", "Riders matched", "Match rate",
             "Avg ETA (min)", "Avg window p90 ETA (min)", "Avg en-route min / window",
             "Drivers matched %", "Avg contribution $ / window", "Avg ETA vs greedy (no MDR)",
             "Contribution vs greedy MDR"]
    header(sm, 3, heads)
    P = rng("protocol")
    for i, p in enumerate(PROTOCOLS):
        r = 4 + i
        sm.cell(r, 1, p)
        sm.cell(r, 2, f"=COUNTIFS({P},$A{r})")
        sm.cell(r, 3, f"=SUMIFS({rng('riders')},{P},$A{r})")
        sm.cell(r, 4, f"=SUMIFS({rng('matched')},{P},$A{r})")
        sm.cell(r, 5, f"=D{r}/C{r}")
        sm.cell(r, 6, f"=SUMIFS({rng('total_enroute_min')},{P},$A{r})/D{r}")
        sm.cell(r, 7, f"=AVERAGEIFS({rng('p90_eta_min')},{P},$A{r})")
        sm.cell(r, 8, f"=AVERAGEIFS({rng('total_enroute_min')},{P},$A{r})")
        sm.cell(r, 9, f"=D{r}/SUMIFS({rng('drivers')},{P},$A{r})")
        sm.cell(r, 10, f"=AVERAGEIFS({rng('profit_usd')},{P},$A{r})")
        sm.cell(r, 11, f'=F{r}/INDEX($F$4:$F$8,MATCH("greedy_first_dispatch",$A$4:$A$8,0))-1')
        sm.cell(r, 12, f'=J{r}/INDEX($J$4:$J$8,MATCH("greedy_first_dispatch_mdr",$A$4:$A$8,0))-1')
        for c, fmt in zip(range(2, 13), ["#,##0", "#,##0", "#,##0", "0.0%", "0.00", "0.00", "0.0",
                                         "0.0%", "$#,##0.00", "+0.0%;-0.0%;0.0%", "+0.0%;-0.0%;0.0%"]):
            sm.cell(r, c).number_format = fmt
            sm.cell(r, c).border = BOX
    sm.conditional_formatting.add("F4:F8", ColorScaleRule(start_type="min", start_color="63BE7B",
                                                          mid_type="percentile", mid_value=50, mid_color="FFEB84",
                                                          end_type="max", end_color="F8696B"))
    sm.conditional_formatting.add("J4:J8", DataBarRule(start_type="min", end_type="max", color="5B9BD5"))
    for rngs in ("K4:K8",):
        sm.conditional_formatting.add(rngs, CellIsRule(operator="lessThan", formula=["0"],
                                                       font=Font(color="006100"),
                                                       fill=PatternFill("solid", fgColor="C6EFCE")))
        sm.conditional_formatting.add(rngs, CellIsRule(operator="greaterThan", formula=["0"],
                                                       font=Font(color="9C0006"),
                                                       fill=PatternFill("solid", fgColor="FFC7CE")))
    sm.conditional_formatting.add("L4:L8", CellIsRule(operator="greaterThan", formula=["0"],
                                                      fill=PatternFill("solid", fgColor="C6EFCE")))
    sm.conditional_formatting.add("L4:L8", CellIsRule(operator="lessThan", formula=["0"],
                                                      fill=PatternFill("solid", fgColor="FFC7CE")))
    widths(sm, [28, 10, 12, 12, 10, 11, 13, 13, 11, 14, 14, 14])
    ch = BarChart()
    ch.type, ch.title, ch.y_axis.title = "bar", "Average rider ETA by protocol (min)", "minutes"
    ch.add_data(Reference(sm, min_col=6, min_row=3, max_row=8), titles_from_data=True)
    ch.set_categories(Reference(sm, min_col=1, min_row=4, max_row=8))
    ch.height, ch.width, ch.legend = 8, 18, None
    sm.add_chart(ch, "A11")
    ch2 = BarChart()
    ch2.title, ch2.y_axis.title = "Match rate by protocol", "share of riders matched"
    ch2.add_data(Reference(sm, min_col=5, min_row=3, max_row=8), titles_from_data=True)
    ch2.set_categories(Reference(sm, min_col=1, min_row=4, max_row=8))
    ch2.height, ch2.width, ch2.legend = 8, 18, None
    sm.add_chart(ch2, "H11")

    # ---------------- Sensitivity ----------------
    se = wb.create_sheet("Sensitivity")
    se["A1"], se["A1"].font = "Sensitivity to max dispatch radius and driver supply", TITLE
    mdr_protos = ["greedy_first_dispatch_mdr", "batched_min_eta_mdr", "batched_max_profit_mdr", "batched_min_eta"]
    M = rng("mdr_miles")
    blocks = [("Match rate by MDR (miles)", "match"), ("Avg ETA (min) by MDR (miles)", "eta"),
              ("Avg contribution $ / window by MDR (miles)", "profit")]
    row = 3
    line_anchor = {}
    for title, kind in blocks:
        se.cell(row, 1, title).font = Font(bold=True)
        header(se, row + 1, ["MDR miles"] + mdr_protos)
        for i, m in enumerate(MDR_OPTIONS):
            r = row + 2 + i
            se.cell(r, 1, m).border = BOX
            for j, p in enumerate(mdr_protos):
                pc = get_column_letter(2 + j)
                hdr = f"{pc}${row + 1}"
                if kind == "match":
                    f = (f"=SUMIFS({rng('matched')},{P},{hdr},{M},$A{r})/"
                         f"SUMIFS({rng('riders')},{P},{hdr},{M},$A{r})")
                    fmt = "0.0%"
                elif kind == "eta":
                    f = (f"=SUMIFS({rng('total_enroute_min')},{P},{hdr},{M},$A{r})/"
                         f"SUMIFS({rng('matched')},{P},{hdr},{M},$A{r})")
                    fmt = "0.00"
                else:
                    f = f"=AVERAGEIFS({rng('profit_usd')},{P},{hdr},{M},$A{r})"
                    fmt = "$#,##0.00"
                c = se.cell(r, 2 + j, f)
                c.number_format, c.border = fmt, BOX
        area = f"B{row + 2}:E{row + 1 + len(MDR_OPTIONS)}"
        good_high = kind != "eta"
        se.conditional_formatting.add(area, ColorScaleRule(
            start_type="min", start_color="F8696B" if good_high else "63BE7B",
            end_type="max", end_color="63BE7B" if good_high else "F8696B"))
        line_anchor[kind] = row + 1
        row += len(MDR_OPTIONS) + 4
    # supply ratio block (no-radius protocols)
    se.cell(row, 1, "Avg ETA (min) by design supply ratio (drivers per rider)").font = Font(bold=True)
    sup_protos = ["greedy_first_dispatch", "batched_min_eta", "greedy_first_dispatch_mdr", "batched_min_eta_mdr"]
    header(se, row + 1, ["Supply ratio"] + sup_protos + ["Batching ETA reduction (no MDR)"])
    S = rng("supply_ratio_design")
    for i, s in enumerate(SUPPLY_RATIOS):
        r = row + 2 + i
        se.cell(r, 1, s).border = BOX
        for j, p in enumerate(sup_protos):
            pc = get_column_letter(2 + j)
            c = se.cell(r, 2 + j, f"=SUMIFS({rng('total_enroute_min')},{P},{pc}${row + 1},{S},$A{r})/"
                                  f"SUMIFS({rng('matched')},{P},{pc}${row + 1},{S},$A{r})")
            c.number_format, c.border = "0.00", BOX
        c = se.cell(r, 6, f"=1-C{r}/B{r}")
        c.number_format, c.border = "0.0%", BOX
    sup_first = row + 2
    se.conditional_formatting.add(f"F{sup_first}:F{sup_first + len(SUPPLY_RATIOS) - 1}",
                                  DataBarRule(start_type="num", start_value=0, end_type="max", color="63BE7B"))
    widths(se, [14, 26, 22, 24, 22, 18])
    lc = LineChart()
    lc.title, lc.y_axis.title, lc.x_axis.title = "Match rate vs max dispatch radius", "match rate", "MDR (miles)"
    hr = line_anchor["match"]
    lc.add_data(Reference(se, min_col=2, max_col=5, min_row=hr, max_row=hr + len(MDR_OPTIONS)), titles_from_data=True)
    lc.set_categories(Reference(se, min_col=1, min_row=hr + 1, max_row=hr + len(MDR_OPTIONS)))
    lc.height, lc.width = 8, 18
    se.add_chart(lc, "H3")
    lc2 = LineChart()
    lc2.title, lc2.y_axis.title, lc2.x_axis.title = "Avg ETA vs driver supply ratio", "minutes", "drivers per rider"
    hr2 = sup_first - 1
    lc2.add_data(Reference(se, min_col=2, max_col=3, min_row=hr2, max_row=hr2 + len(SUPPLY_RATIOS)), titles_from_data=True)
    lc2.set_categories(Reference(se, min_col=1, min_row=hr2 + 1, max_row=hr2 + len(SUPPLY_RATIOS)))
    lc2.height, lc2.width = 8, 18
    se.add_chart(lc2, "H22")

    # ---------------- Grid (lookup table) ----------------
    gr = wb.create_sheet("Grid")
    header(gr, 1, ["Key", "Supply ratio", "MDR miles", "Protocol", "Windows", "Match rate",
                   "Avg ETA (min)", "Avg p90 ETA (min)", "Avg contribution $ / window"])
    r = 2
    for s in SUPPLY_RATIOS:
        for m in MDR_OPTIONS:
            for p in PROTOCOLS:
                gr.cell(r, 1, f'=TEXT(B{r},"0.0")&"|"&TEXT(C{r},"0.0")&"|"&D{r}')
                gr.cell(r, 2, s), gr.cell(r, 3, m), gr.cell(r, 4, p)
                crit = f"{P},$D{r},{S},$B{r},{M},$C{r}"
                gr.cell(r, 5, f"=COUNTIFS({crit})")
                gr.cell(r, 6, f"=IFERROR(SUMIFS({rng('matched')},{crit})/SUMIFS({rng('riders')},{crit}),NA())").number_format = "0.0%"
                gr.cell(r, 7, f"=IFERROR(SUMIFS({rng('total_enroute_min')},{crit})/SUMIFS({rng('matched')},{crit}),NA())").number_format = "0.00"
                gr.cell(r, 8, f"=IFERROR(AVERAGEIFS({rng('p90_eta_min')},{crit}),NA())").number_format = "0.00"
                gr.cell(r, 9, f"=IFERROR(AVERAGEIFS({rng('profit_usd')},{crit}),NA())").number_format = "$#,##0.00"
                r += 1
    grid_last = r - 1
    widths(gr, [40, 12, 10, 28, 10, 11, 12, 14, 16])
    gr.freeze_panes = "A2"

    # ---------------- WhatIf ----------------
    wi = wb.create_sheet("WhatIf")
    wi["A1"], wi["A1"].font = "What-if: pick a driver-supply ratio and dispatch radius", TITLE
    inputs = [("Driver supply ratio (drivers per rider)", 0.8, '"' + ",".join(str(x) for x in SUPPLY_RATIOS) + '"'),
              ("Max dispatch radius (miles)", 3.0, '"' + ",".join(str(x) for x in MDR_OPTIONS) + '"'),
              ("Batching windows per day (assumption for scaling)", 10000, None)]
    for i, (label, val, lst) in enumerate(inputs):
        r = 3 + i
        wi.cell(r, 1, label).font = Font(bold=True)
        c = wi.cell(r, 2, val)
        c.fill, c.border = INPUT_FILL, BOX
        if lst:
            dv = DataValidation(type="list", formula1=lst, allow_blank=False)
            wi.add_data_validation(dv)
            dv.add(c)
    wi["B5"].number_format = "#,##0"
    wi["C3"] = "Choose from list (0.6, 0.8, 1.0, 1.2, 1.5)"
    wi["C4"] = "Choose from list (1.5, 2, 3, 4)"
    header(wi, 7, ["Protocol", "Lookup key", "Windows in segment", "Match rate", "Avg ETA (min)",
                   "Avg p90 ETA (min)", "Contribution $ / window"])
    G = lambda c: f"Grid!${c}$2:${c}${grid_last}"   # noqa: E731
    for i, p in enumerate(PROTOCOLS):
        r = 8 + i
        wi.cell(r, 1, p).border = BOX
        wi.cell(r, 2, f'=TEXT($B$3,"0.0")&"|"&TEXT($B$4,"0.0")&"|"&A{r}').border = BOX
        for j, (gc, fmt) in enumerate([("E", "#,##0"), ("F", "0.0%"), ("G", "0.00"), ("H", "0.00"), ("I", "$#,##0.00")]):
            c = wi.cell(r, 3 + j, f"=INDEX({G(gc)},MATCH($B{r},{G('A')},0))")
            c.number_format, c.border = fmt, BOX
    wi.cell(14, 1, "Decision view: batched min-ETA (with MDR) vs greedy first-dispatch (with MDR)").font = Font(bold=True)
    header(wi, 15, ["Metric", "Greedy MDR", "Batched MDR", "Change"])
    rows = [("Match rate", "D", "0.0%", "pp"), ("Avg ETA (min)", "E", "0.00", "abs"),
            ("Avg p90 ETA (min)", "F", "0.00", "abs"), ("Contribution $ / window", "G", "$#,##0.00", "abs")]
    for i, (label, c_, fmt, kind) in enumerate(rows):
        r = 16 + i
        wi.cell(r, 1, label).border = BOX
        g = wi.cell(r, 2, f'=INDEX(${c_}$8:${c_}$12,MATCH("greedy_first_dispatch_mdr",$A$8:$A$12,0))')
        b = wi.cell(r, 3, f'=INDEX(${c_}$8:${c_}$12,MATCH("batched_min_eta_mdr",$A$8:$A$12,0))')
        d = wi.cell(r, 4, f"=C{r}-B{r}")
        for x in (g, b):
            x.number_format, x.border = fmt, BOX
        d.number_format = "+0.0%;-0.0%" if kind == "pp" else ("+$#,##0.00;-$#,##0.00" if "$" in fmt else "+0.00;-0.00")
        d.border = BOX
    wi.cell(20, 1, "Modelled contribution uplift per day").font = Font(bold=True)
    c = wi.cell(20, 4, "=D19*$B$5")
    c.number_format, c.border = "+$#,##0;-$#,##0", BOX
    # green when batching is better: higher match / contribution, lower ETA
    green = PatternFill("solid", fgColor="C6EFCE")
    red = PatternFill("solid", fgColor="FFC7CE")
    for ref, better in (("D16", "greaterThan"), ("D19", "greaterThan"), ("D20", "greaterThan"),
                        ("D17", "lessThan"), ("D18", "lessThan")):
        worse = "lessThan" if better == "greaterThan" else "greaterThan"
        wi.conditional_formatting.add(ref, CellIsRule(operator=better, formula=["0"], fill=green))
        wi.conditional_formatting.add(ref, CellIsRule(operator=worse, formula=["0"], fill=red))
    wi.cell(22, 1, "Note: segment values come from simulated windows with that design supply ratio and MDR "
                   "(see Grid). Windows per day is a user assumption; the uplift is illustrative.")
    widths(wi, [44, 26, 16, 12, 12, 14, 18])
    bc = BarChart()
    bc.title, bc.y_axis.title = "Selected scenario: avg ETA by protocol", "minutes"
    bc.add_data(Reference(wi, min_col=5, min_row=7, max_row=12), titles_from_data=True)
    bc.set_categories(Reference(wi, min_col=1, min_row=8, max_row=12))
    bc.height, bc.width, bc.legend = 8, 16, None
    wi.add_chart(bc, "I3")

    wb.move_sheet("WhatIf", offset=-(len(wb.sheetnames) - 2))
    wb.save(OUT)
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
