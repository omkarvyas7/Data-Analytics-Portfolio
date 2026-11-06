"""Build excel/Disney_Genre_Performance.xlsx. Calculated cells are live Excel formulas.

Sheets
  About          how to use the workbook
  Data           148 cleaned films, ROI as a formula column
  Genre_Summary  KPIs per genre (COUNTIFS / AVERAGEIFS / SUMIFS), conditional formatting, bar charts,
                 Action vs non-Action table
  Title_Lookup   pick a title, XLOOKUP (with an INDEX/MATCH fallback) returns its metrics
  What_If        budget, score, star power and Action inputs give expected gross from model M2
"""
from __future__ import annotations

import json

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from common import EXCEL_DIR, PROCESSED, RESULTS_JSON

HDR = PatternFill("solid", fgColor="1F3B73")
INPUT = PatternFill("solid", fgColor="FFF2CC")
CALC = PatternFill("solid", fgColor="E2EFDA")
WHITE_B = Font(bold=True, color="FFFFFF")
BOLD = Font(bold=True)
THIN = Border(*(Side(style="thin", color="BFBFBF"),) * 4)
USD_M = '"$"#,##0.0,,"M"'


def header(ws, row, values, col=1):
    for i, v in enumerate(values):
        c = ws.cell(row=row, column=col + i, value=v)
        c.fill, c.font, c.alignment = HDR, WHITE_B, Alignment(wrap_text=True, vertical="center")


def widths(ws, w):
    for i, x in enumerate(w, 1):
        ws.column_dimensions[get_column_letter(i)].width = x


def main() -> None:
    df = pd.read_csv(PROCESSED / "disney_clean.csv")
    res = json.loads(RESULTS_JSON.read_text())
    wb = Workbook()

    # About -----------------------------------------------------------------
    ab = wb.active
    ab.title = "About"
    lines = [("Disney Genre Performance workbook", BOLD),
             (f"{len(df)} Disney releases {res['year_min']}-{res['year_max']}; gross is domestic box office, inflation-adjusted (source: Disney gross file + IMDb movies file).", None),
             ("Data: one row per film. ROI column is a live formula (gross / budget).", None),
             ("Genre_Summary: KPIs per genre built with COUNTIFS, AVERAGEIFS and SUMIFS. Colour scale on ROI, data bars on gross.", None),
             ("Title_Lookup: type a title in the yellow cell; XLOOKUP and INDEX/MATCH return its metrics.", None),
             ("What_If: change the yellow inputs; expected gross uses the fitted log-log OLS coefficients (model M2).", None),
             ("Yellow = input, green = formula output. XLOOKUP needs Excel 2021/365; the INDEX/MATCH column works in older versions.", None)]
    for i, (t, f) in enumerate(lines, 1):
        c = ab.cell(row=i, column=1, value=t)
        if f:
            c.font = Font(bold=True, size=14)
    ab.column_dimensions["A"].width = 120

    # Data ------------------------------------------------------------------
    ws = wb.create_sheet("Data")
    cols = ["Title", "Release year", "Decade", "Genre (Disney)", "Company", "Lead star", "Star power",
            "IMDb score", "Adj. budget", "Adj. gross", "ROI (gross/budget)", "Is Action", "Is Marvel"]
    header(ws, 1, cols)
    n = len(df)
    for r, row in enumerate(df.itertuples(index=False), start=2):
        vals = [row.title, row.release_year, row.decade, row.disney_genre, row.company, row.star,
                row.star_power, row.imdb_score, round(row.inflation_budget), row.inflation_adjusted_gross,
                f"=J{r}/I{r}", row.is_action, row.is_marvel]
        for c, v in enumerate(vals, 1):
            ws.cell(row=r, column=c, value=v)
        ws.cell(row=r, column=9).number_format = USD_M
        ws.cell(row=r, column=10).number_format = USD_M
        ws.cell(row=r, column=11).number_format = "0.00x"
    last = n + 1
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:M{last}"
    widths(ws, [34, 8, 8, 16, 26, 20, 9, 8, 12, 12, 10, 8, 8])
    ws.conditional_formatting.add(f"K2:K{last}", FormulaRule(formula=[f"K2<1"], fill=PatternFill("solid", fgColor="F8CBAD")))
    ws.conditional_formatting.add(f"A2:M{last}", FormulaRule(formula=["$L2=1"], font=Font(bold=True, color="9C5700")))

    rng = lambda col: f"Data!${col}$2:${col}${last}"  # noqa: E731
    G, B, S, R, A = rng("D"), rng("I"), rng("J"), rng("K"), rng("L")

    # Genre summary ----------------------------------------------------------
    gs = wb.create_sheet("Genre_Summary")
    gs["A1"] = "Genre KPIs (live formulas on the Data sheet)"
    gs["A1"].font = Font(bold=True, size=13)
    header(gs, 3, ["Genre", "Films", "Avg adj. gross", "Avg adj. budget", "Pooled ROI", "Avg ROI",
                   "% films ROI >= 1", "Share of total gross"])
    genres = df.groupby("disney_genre").inflation_adjusted_gross.mean().sort_values(ascending=False).index
    for i, g in enumerate(genres, start=4):
        gs.cell(row=i, column=1, value=g)
        gs.cell(row=i, column=2, value=f"=COUNTIFS({G},A{i})")
        gs.cell(row=i, column=3, value=f"=AVERAGEIFS({S},{G},A{i})").number_format = USD_M
        gs.cell(row=i, column=4, value=f"=AVERAGEIFS({B},{G},A{i})").number_format = USD_M
        gs.cell(row=i, column=5, value=f"=SUMIFS({S},{G},A{i})/SUMIFS({B},{G},A{i})").number_format = "0.00x"
        gs.cell(row=i, column=6, value=f"=AVERAGEIFS({R},{G},A{i})").number_format = "0.00x"
        gs.cell(row=i, column=7, value=f'=COUNTIFS({G},A{i},{R},">=1")/B{i}').number_format = "0%"
        gs.cell(row=i, column=8, value=f"=SUMIFS({S},{G},A{i})/SUM({S})").number_format = "0.0%"
    end = 3 + len(genres)
    tot = end + 1
    gs.cell(row=tot, column=1, value="All films").font = BOLD
    gs.cell(row=tot, column=2, value=f"=SUM(B4:B{end})").font = BOLD
    gs.cell(row=tot, column=3, value=f"=AVERAGE({S})").number_format = USD_M
    gs.cell(row=tot, column=4, value=f"=AVERAGE({B})").number_format = USD_M
    gs.cell(row=tot, column=5, value=f"=SUM({S})/SUM({B})").number_format = "0.00x"
    gs.cell(row=tot, column=6, value=f"=AVERAGE({R})").number_format = "0.00x"
    gs.conditional_formatting.add(f"E4:E{end}", ColorScaleRule(start_type="min", start_color="F8696B",
                                                               mid_type="num", mid_value=1, mid_color="FFEB84",
                                                               end_type="max", end_color="63BE7B"))
    gs.conditional_formatting.add(f"C4:C{end}", DataBarRule(start_type="min", end_type="max", color="5B9BD5"))
    gs.conditional_formatting.add(f"A4:H{end}", FormulaRule(formula=['$A4="Action"'], fill=PatternFill("solid", fgColor="FCE4D6")))

    a0 = tot + 3
    gs.cell(row=a0 - 1, column=1, value="Action vs non-Action").font = Font(bold=True, size=12)
    header(gs, a0, ["Segment", "Films", "Avg adj. gross", "Avg adj. budget", "Pooled ROI", "Avg ROI"])
    for j, (lab, flag) in enumerate([("Action", 1), ("Non-Action", 0)], start=a0 + 1):
        gs.cell(row=j, column=1, value=lab)
        gs.cell(row=j, column=2, value=f"=COUNTIFS({A},{flag})")
        gs.cell(row=j, column=3, value=f"=AVERAGEIFS({S},{A},{flag})").number_format = USD_M
        gs.cell(row=j, column=4, value=f"=AVERAGEIFS({B},{A},{flag})").number_format = USD_M
        gs.cell(row=j, column=5, value=f"=SUMIFS({S},{A},{flag})/SUMIFS({B},{A},{flag})").number_format = "0.00x"
        gs.cell(row=j, column=6, value=f"=AVERAGEIFS({R},{A},{flag})").number_format = "0.00x"
    gs.cell(row=a0 + 3, column=1, value="Action gross premium (raw)")
    gs.cell(row=a0 + 3, column=3, value=f"=C{a0+1}/C{a0+2}-1").number_format = "0%"
    gs.cell(row=a0 + 4, column=1, value="Action budget premium (raw)")
    gs.cell(row=a0 + 4, column=3, value=f"=D{a0+1}/D{a0+2}-1").number_format = "0%"
    gs.cell(row=a0 + 5, column=1,
            value=f"With budget, score and star power controlled, the Action premium is {res['m2_action_pct']:+.1%} (p = {res['m2_p']['is_action']:.2f}), not significant.")
    widths(gs, [24, 8, 15, 15, 11, 9, 13, 14])

    ch = BarChart()
    ch.type = "bar"
    ch.title = "Average inflation-adjusted gross by genre"
    ch.y_axis.title = "Gross ($)"
    ch.add_data(Reference(gs, min_col=3, min_row=3, max_row=end), titles_from_data=True)
    ch.set_categories(Reference(gs, min_col=1, min_row=4, max_row=end))
    ch.height, ch.width = 9, 16
    gs.add_chart(ch, "J3")
    ch2 = BarChart()
    ch2.title = "Pooled ROI by genre"
    ch2.add_data(Reference(gs, min_col=5, min_row=3, max_row=end), titles_from_data=True)
    ch2.set_categories(Reference(gs, min_col=1, min_row=4, max_row=end))
    ch2.height, ch2.width = 9, 16
    gs.add_chart(ch2, "J22")

    # Title lookup -----------------------------------------------------------
    tl = wb.create_sheet("Title_Lookup")
    tl["A1"] = "Title lookup"
    tl["A1"].font = Font(bold=True, size=13)
    tl["A3"], tl["B3"] = "Enter title:", "Frozen"
    tl["B3"].fill = INPUT
    dv = DataValidation(type="list", formula1=f"=Data!$A$2:$A${last}", allow_blank=False)
    tl.add_data_validation(dv)
    dv.add("B3")
    fields = [("Genre (Disney)", "D", None), ("Release year", "B", "0"), ("Company", "E", None),
              ("Lead star", "F", None), ("IMDb score", "H", "0.0"), ("Adj. budget", "I", USD_M),
              ("Adj. gross", "J", USD_M), ("ROI (gross/budget)", "K", "0.00x")]
    header(tl, 5, ["Field", "XLOOKUP result", "INDEX/MATCH fallback"])
    for i, (lab, col, fmt) in enumerate(fields, start=6):
        tl.cell(row=i, column=1, value=lab)
        x = tl.cell(row=i, column=2, value=f'=_xlfn.XLOOKUP($B$3,Data!$A$2:$A${last},Data!${col}$2:${col}${last},"not found")')
        m = tl.cell(row=i, column=3, value=f"=IFERROR(INDEX(Data!${col}$2:${col}${last},MATCH($B$3,Data!$A$2:$A${last},0)),\"not found\")")
        for c in (x, m):
            c.fill = CALC
            if fmt:
                c.number_format = fmt
    r0 = 6 + len(fields) + 1
    tl.cell(row=r0, column=1, value="Rank in genre by gross")
    tl.cell(row=r0, column=2, value=f'=COUNTIFS({G},B6,{S},">"&B12)+1').fill = CALC
    tl.cell(row=r0 + 1, column=1, value="Genre average gross")
    c = tl.cell(row=r0 + 1, column=2, value=f"=AVERAGEIFS({S},{G},B6)")
    c.fill, c.number_format = CALC, USD_M
    tl.cell(row=r0 + 2, column=1, value="Gross vs genre average")
    c = tl.cell(row=r0 + 2, column=2, value=f"=B12/B{r0+1}-1")
    c.fill, c.number_format = CALC, "+0%;-0%"
    widths(tl, [26, 30, 30])

    # What-if ----------------------------------------------------------------
    wi = wb.create_sheet("What_If")
    co = res["m2_coef"]
    wi["A1"] = "What-if: expected domestic gross for a proposed film (model M2, log-log OLS, HC3)"
    wi["A1"].font = Font(bold=True, size=13)
    inputs = [("Production budget ($)", 150_000_000, '"$"#,##0'), ("Expected IMDb score (1-10)", 6.8, "0.0"),
              ("Lead star power rating", 800, "0"), ("Action film? (1 = yes, 0 = no)", 1, "0")]
    header(wi, 3, ["Input", "Value"])
    for i, (lab, v, fmt) in enumerate(inputs, start=4):
        wi.cell(row=i, column=1, value=lab)
        c = wi.cell(row=i, column=2, value=v)
        c.fill, c.number_format, c.border = INPUT, fmt, THIN
    dv2 = DataValidation(type="list", formula1='"0,1"')
    wi.add_data_validation(dv2)
    dv2.add("B7")
    header(wi, 9, ["Model coefficient (editable)", "Value", "p-value"])
    coef_rows = [("Intercept", "Intercept"), ("Action (1/0)", "is_action"), ("ln(budget)", "log_budget"),
                 ("Star power", "star_power"), ("IMDb score", "imdb_score")]
    for i, (lab, k) in enumerate(coef_rows, start=10):
        wi.cell(row=i, column=1, value=lab)
        c = wi.cell(row=i, column=2, value=round(co[k], 6))
        c.fill, c.number_format = INPUT, "0.000000"
        wi.cell(row=i, column=3, value=round(res["m2_p"][k], 4)).number_format = "0.0000"
    wi.cell(row=15, column=1, value="Smearing factor (log back-transform)")
    c = wi.cell(row=15, column=2, value=round(res["smearing_factor"], 4))
    c.fill = INPUT
    wi.cell(row=16, column=1, value=f"Model fit: R-squared {res['m2_r2']:.3f}, n = {res['m2_n']}. A budget typed in current dollars is treated as inflation-adjusted.")

    header(wi, 18, ["Output", "Value"])
    pred = "EXP($B$10+$B$11*{a}+$B$12*LN({b})+$B$13*$B$6+$B$14*$B$5)*$B$15"
    outs = [("Expected domestic gross", "=" + pred.format(a="$B$7", b="$B$4"), USD_M),
            ("Expected ROI (gross / budget)", "=B19/B4", "0.00x"),
            ("Same film as non-Action", "=" + pred.format(a="0", b="$B$4"), USD_M),
            ("Same film as Action", "=" + pred.format(a="1", b="$B$4"), USD_M),
            ("Action minus non-Action", "=B22-B21", '"$"#,##0.0,,"M";-"$"#,##0.0,,"M"'),
            ("Gross gain from +0.5 IMDb score", "=B19*(EXP($B$14*0.5)-1)", USD_M)]
    for i, (lab, f, fmt) in enumerate(outs, start=19):
        wi.cell(row=i, column=1, value=lab)
        c = wi.cell(row=i, column=2, value=f)
        c.fill, c.number_format, c.border = CALC, fmt, THIN
    wi["B19"].font = Font(bold=True, size=12)
    wi.conditional_formatting.add("B20", FormulaRule(formula=["B20<1"], fill=PatternFill("solid", fgColor="F8CBAD")))
    wi.conditional_formatting.add("B20", FormulaRule(formula=["B20>=1"], fill=PatternFill("solid", fgColor="C6EFCE")))

    header(wi, 27, ["Budget scenario ($)", "Expected gross", "Expected ROI"])
    for i, bud in enumerate([25e6, 50e6, 100e6, 150e6, 200e6, 250e6], start=28):
        wi.cell(row=i, column=1, value=bud).number_format = '"$"#,##0'
        c = wi.cell(row=i, column=2, value="=" + pred.format(a="$B$7", b=f"A{i}"))
        c.number_format, c.fill = USD_M, CALC
        c = wi.cell(row=i, column=3, value=f"=B{i}/A{i}")
        c.number_format, c.fill = "0.00x", CALC
    wi.conditional_formatting.add("C28:C33", ColorScaleRule(start_type="min", start_color="F8696B",
                                                            end_type="max", end_color="63BE7B"))
    ch3 = BarChart()
    ch3.title = "Expected gross by budget scenario"
    ch3.add_data(Reference(wi, min_col=2, min_row=27, max_row=33), titles_from_data=True)
    ch3.set_categories(Reference(wi, min_col=1, min_row=28, max_row=33))
    ch3.height, ch3.width = 8, 14
    wi.add_chart(ch3, "E3")
    widths(wi, [42, 20, 12])

    EXCEL_DIR.mkdir(exist_ok=True)
    out = EXCEL_DIR / "Disney_Genre_Performance.xlsx"
    wb.save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
