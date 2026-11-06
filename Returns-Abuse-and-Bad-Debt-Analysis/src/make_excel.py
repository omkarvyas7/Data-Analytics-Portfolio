"""Build excel/Returns_Risk_Model.xlsx with openpyxl.

Tabs:
  About            how the workbook works
  Policy What-If   input cells (tier cutoffs, $ threshold, fee, deny rate) driving
                   savings and good-customer-impact formulas (SUMIFS / COUNTIFS)
  Summary          pivot-style tables built with COUNTIFS / SUMIFS / AVERAGEIFS
  Monthly          monthly return rate (formula) + native line chart
  Tier Lookup      XLOOKUP and INDEX/MATCH lookups of a customer's score and tier
  Returns_Data     performance-window returns (Jul-Dec 2025), tier is a live formula
  Customers        one row per customer, tier is a live formula
  Data_Sample      2,000-row sample of the order-level fact table
The formulas recalculate when the file is opened in Excel (openpyxl does not
cache results). Default inputs reproduce sql/11_policy_simulation.sql.
"""
import sqlite3

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

import config as C
from config import DB_PATH, EXCEL_DIR

HDR = PatternFill("solid", fgColor="232F3E")
INPUT = PatternFill("solid", fgColor="FFF2CC")
OUT = PatternFill("solid", fgColor="E2EFDA")
WHITE = Font(color="FFFFFF", bold=True)
BOLD = Font(bold=True)
THIN = Border(*(Side(style="thin", color="BFBFBF"),) * 4)
MONEY = '"$"#,##0'
PCT = "0.0%"


def header(ws, row, cols, start_col=1):
    for i, c in enumerate(cols):
        cell = ws.cell(row=row, column=start_col + i, value=c)
        cell.fill, cell.font = HDR, WHITE
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def write_df(ws, df, start_row=1):
    header(ws, start_row, list(df.columns))
    for r, row in enumerate(df.itertuples(index=False), start=start_row + 1):
        for c, v in enumerate(row, start=1):
            ws.cell(row=r, column=c, value=None if pd.isna(v) else v)
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    for i, col in enumerate(df.columns, start=1):
        ws.column_dimensions[get_column_letter(i)].width = max(11, min(28, len(str(col)) + 3))


def load(con):
    q = lambda s: pd.read_sql_query(s, con)
    returns = q("""
        SELECT rf.return_id, rf.customer_id, co.risk_score, rf.request_month, rf.category, rf.reason_code,
               rf.refund_issued, rf.refund_amount, rf.instant_refund_flag,
               CASE WHEN rf.bad_debt_flag = 1 OR rf.fraud_return_flag = 1 THEN rf.refund_amount ELSE 0 END AS avoidable_if_receipt_first,
               rf.loss_amt, rf.prior_returns_90d, rf.is_inr, co.address_inr_cluster,
               CASE WHEN co.perf_active = 1 AND co.perf_loss_event = 0 THEN 1 ELSE 0 END AS good_customer
        FROM return_facts rf JOIN customer_outcomes co USING (customer_id)
        WHERE rf.period = 'performance'
        ORDER BY rf.return_id""")
    cust = q("""
        SELECT co.customer_id, co.risk_score, co.region, co.is_member, co.scoring_orders, co.return_rate,
               co.max_roll90_return_rate, co.inr_claims, co.condition_mismatches, co.never_received_refunds,
               co.address_inr_cluster, co.perf_active, co.perf_loss_event,
               CASE WHEN co.perf_active = 1 AND co.perf_loss_event = 0 THEN 1 ELSE 0 END AS good_customer,
               co.perf_loss_dollars
        FROM customer_outcomes co ORDER BY co.customer_id""")
    p = returns[returns["period"] == "performance"] if "period" in returns else returns
    inst = p[(p["instant_refund_flag"] == 1)].groupby("customer_id")["refund_amount"].agg(["count", "max"])
    nln = p[(p["reason_code"] == "no_longer_needed") & (p["refund_issued"] == 1)
            & (p["avoidable_if_receipt_first"] == 0)].groupby("customer_id")["prior_returns_90d"].max()
    inr = p[(p["is_inr"] == 1) & (p["address_inr_cluster"] == 1) & (p["refund_issued"] == 1)].groupby("customer_id").size()
    cust["perf_instant_refunds"] = cust["customer_id"].map(inst["count"]).fillna(0).astype(int)
    cust["max_instant_refund"] = cust["customer_id"].map(inst["max"]).fillna(0).round(2)
    cust["max_prior_returns_nln"] = cust["customer_id"].map(nln).fillna(-1).astype(int)
    cust["inr_cluster_claims"] = cust["customer_id"].map(inr).fillna(0).astype(int)
    monthly = q("""
        SELECT substr(order_date,1,7) AS month, COUNT(*) AS orders FROM clean_orders GROUP BY 1 ORDER BY 1""")
    mret = q("""
        SELECT order_month AS month, SUM(CASE WHEN is_inr=0 THEN 1 ELSE 0 END) AS returns,
               ROUND(SUM(refund_amount),2) AS refund_dollars, ROUND(SUM(loss_amt),2) AS loss_dollars
        FROM return_facts GROUP BY 1""")
    monthly = monthly.merge(mret, on="month", how="left").fillna(0)
    cat_orders = q("""
        SELECT category, COUNT(*) AS perf_orders FROM clean_orders
        WHERE order_date >= (SELECT scoring_cutoff FROM params) GROUP BY 1 ORDER BY 1""")
    sample = q("""
        SELECT return_id, order_id, customer_id, region, is_member, order_date, category, item_price,
               return_request_date, reason_code, instant_refund_flag, refund_amount, return_received_date,
               condition_grade, bad_debt_flag, condition_mismatch_flag, loss_amt
        FROM return_facts ORDER BY return_id""").sample(2000, random_state=C.SEED).sort_values("return_id")
    return returns, cust, monthly, cat_orders, sample


def build():
    EXCEL_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    returns, cust, monthly, cat_orders, sample = load(con)
    con.close()

    wb = Workbook()
    about = wb.active
    about.title = "About"
    wi = wb.create_sheet("Policy What-If")
    sm = wb.create_sheet("Summary")
    mo = wb.create_sheet("Monthly")
    tl = wb.create_sheet("Tier Lookup")
    rd = wb.create_sheet("Returns_Data")
    cu = wb.create_sheet("Customers")
    ds = wb.create_sheet("Data_Sample")

    # ---------------- Returns_Data (tier = live formula) ----------------
    rcols = ["return_id", "customer_id", "risk_score", "risk_tier", "request_month", "category", "reason_code",
             "refund_issued", "refund_amount", "instant_refund_flag", "avoidable_if_receipt_first", "loss_amt",
             "prior_returns_90d", "is_inr", "address_inr_cluster", "good_customer"]
    rdf = returns.assign(risk_tier="")[rcols]
    write_df(rd, rdf)
    n_r = len(rdf) + 1
    for r in range(2, n_r + 1):
        rd[f"D{r}"] = f"=IF(C{r}>='Policy What-If'!$C$5,\"High\",IF(C{r}>='Policy What-If'!$C$6,\"Medium\",\"Low\"))"
        rd[f"I{r}"].number_format = '"$"#,##0.00'
    R = lambda col: f"Returns_Data!${col}$2:${col}${n_r}"
    rcol = {name: get_column_letter(i + 1) for i, name in enumerate(rcols)}

    # ---------------- Customers (tier + package flag = live formulas) ----------------
    ccols = ["customer_id", "risk_score", "risk_tier", "region", "is_member", "scoring_orders", "return_rate",
             "max_roll90_return_rate", "inr_claims", "condition_mismatches", "never_received_refunds",
             "address_inr_cluster", "perf_active", "perf_loss_event", "good_customer", "perf_loss_dollars",
             "perf_instant_refunds", "max_instant_refund", "max_prior_returns_nln", "inr_cluster_claims",
             "in_recommended_package"]
    cdf = cust.assign(risk_tier="", in_recommended_package="")[ccols]
    write_df(cu, cdf)
    n_c = len(cdf) + 1
    for r in range(2, n_c + 1):
        cu[f"C{r}"] = f"=IF(B{r}>='Policy What-If'!$C$5,\"High\",IF(B{r}>='Policy What-If'!$C$6,\"Medium\",\"Low\"))"
        cu[f"U{r}"] = (f"=IF(OR(AND(C{r}=\"High\",Q{r}>0),S{r}>='Policy What-If'!$C$9,T{r}>0),1,0)")
    K = lambda col: f"Customers!${col}$2:${col}${n_c}"
    cu.conditional_formatting.add(f"C2:C{n_c}", CellIsRule(operator="equal", formula=['"High"'],
                                  fill=PatternFill("solid", fgColor="F8CBAD")))
    cu.conditional_formatting.add(f"C2:C{n_c}", CellIsRule(operator="equal", formula=['"Medium"'],
                                  fill=PatternFill("solid", fgColor="FFE699")))
    rd.conditional_formatting.add(f"D2:D{n_r}", CellIsRule(operator="equal", formula=['"High"'],
                                  fill=PatternFill("solid", fgColor="F8CBAD")))

    # ---------------- Policy What-If ----------------
    wi["A1"] = "Policy What-If: change the yellow input cells and the savings and customer impact recalculate"
    wi["A1"].font = Font(bold=True, size=14)
    wi["A2"] = "Window replayed: performance window Jul-Dec 2025 (returns requested on/after 2025-07-01)."
    inputs = [
        ("High tier cutoff (risk points >=)", C.TIER_HIGH_CUTOFF, "0"),
        ("Medium tier cutoff (risk points >=)", C.TIER_MED_CUTOFF, "0"),
        ("Receipt-before-refund threshold ($ refund >=)", C.HIGH_VALUE_THRESHOLD, MONEY),
        ("Restocking fee rate (no-longer-needed)", C.RESTOCK_FEE_RATE, "0%"),
        ("Repeat returner = prior returns in 90 days >=", C.REPEAT_RETURNS_90D, "0"),
        ("INR cluster claims denied after investigation", C.INR_DENY_RATE, "0%"),
    ]
    header(wi, 4, ["Input", "", "Value"])
    for i, (label, val, fmt) in enumerate(inputs, start=5):
        wi[f"A{i}"] = label
        c = wi[f"C{i}"]
        c.value, c.fill, c.number_format, c.border = val, INPUT, fmt, THIN
    dv = DataValidation(type="whole", operator="between", formula1="0", formula2="20", allow_blank=False)
    wi.add_data_validation(dv)
    dv.add("C5:C6")
    # Inputs: C5 high cutoff, C6 med cutoff, C7 $X, C8 fee, C9 repeat K, C10 deny rate
    wi["A12"] = "Baseline loss $ in window (current policy)"
    wi["C12"] = f"=SUM({R(rcol['loss_amt'])})"
    wi["A13"] = "Good customers in window (active, no loss event)"
    wi["C13"] = f"=COUNTIFS({K('O')},1)"
    wi["A14"] = "Customers by tier (High / Medium / Low)"
    wi["C14"] = f"=COUNTIFS({K('C')},\"High\")"
    wi["D14"] = f"=COUNTIFS({K('C')},\"Medium\")"
    wi["E14"] = f"=COUNTIFS({K('C')},\"Low\")"
    for cell in ["C12"]:
        wi[cell].number_format = MONEY
    for cell in ["C12", "C13", "C14", "D14", "E14"]:
        wi[cell].fill = OUT

    av, tier, inst, amt = R(rcol["avoidable_if_receipt_first"]), R(rcol["risk_tier"]), R(rcol["instant_refund_flag"]), R(rcol["refund_amount"])
    reason, prior, issued = R(rcol["reason_code"]), R(rcol["prior_returns_90d"]), R(rcol["refund_issued"])
    isinr, clus = R(rcol["is_inr"]), R(rcol["address_inr_cluster"])
    ktier, kinst, kmax, kprior, kinr, kgood, kpkg = K("C"), K("Q"), K("R"), K("S"), K("T"), K("O"), K("U")
    scen = [
        ("S1 Disable instant refund for High tier",
         f"=SUMIFS({av},{tier},\"High\",{inst},1)",
         f"=COUNTIFS({ktier},\"High\",{kinst},\">0\",{kgood},1)"),
        ("S2 Receipt-before-refund over $X, all customers",
         f"=SUMIFS({av},{inst},1,{amt},\">=\"&$C$7)",
         f"=COUNTIFS({kmax},\">=\"&$C$7,{kinst},\">0\",{kgood},1)"),
        ("S3 Receipt-before-refund over $X, Medium + High tier",
         f"=SUMIFS({av},{inst},1,{amt},\">=\"&$C$7,{tier},\"High\")+SUMIFS({av},{inst},1,{amt},\">=\"&$C$7,{tier},\"Medium\")",
         f"=COUNTIFS({ktier},\"High\",{kmax},\">=\"&$C$7,{kinst},\">0\",{kgood},1)+COUNTIFS({ktier},\"Medium\",{kmax},\">=\"&$C$7,{kinst},\">0\",{kgood},1)"),
        ("S4 Disable instant refund for everyone",
         f"=SUMIFS({av},{inst},1)",
         f"=COUNTIFS({kinst},\">0\",{kgood},1)"),
        ("S5 Restocking fee on no-longer-needed, repeat returners",
         f"=$C$8*SUMIFS({amt},{reason},\"no_longer_needed\",{prior},\">=\"&$C$9,{issued},1,{av},0)",
         f"=COUNTIFS({kprior},\">=\"&$C$9,{kgood},1)"),
        ("S6 Investigate INR claims at cluster addresses",
         f"=$C$10*SUMIFS({amt},{isinr},1,{clus},1,{issued},1)",
         f"=COUNTIFS({kinr},\">0\",{kgood},1)"),
        ("S7 Recommended package (S1 + S5 + S6)",
         "=D18+D22+D23",
         f"=COUNTIFS({kpkg},1,{kgood},1)"),
    ]
    header(wi, 17, ["Scenario", "", "", "$ saved", "% of baseline loss", "Good customers affected",
                    "% of good customers", "$ saved per good customer affected"])
    for i, (name, saved, good) in enumerate(scen, start=18):
        wi[f"A{i}"] = name
        wi[f"D{i}"] = saved
        wi[f"E{i}"] = f"=IFERROR(D{i}/$C$12,0)"
        wi[f"F{i}"] = good
        wi[f"G{i}"] = f"=IFERROR(F{i}/$C$13,0)"
        wi[f"H{i}"] = f"=IFERROR(D{i}/F{i},0)"
        wi[f"D{i}"].number_format = MONEY
        wi[f"E{i}"].number_format = PCT
        wi[f"G{i}"].number_format = "0.00%"
        wi[f"H{i}"].number_format = MONEY
        for col in "DEFGH":
            wi[f"{col}{i}"].border = THIN
    wi.conditional_formatting.add("G18:G24", CellIsRule(operator="greaterThan", formula=["0.05"],
                                  fill=PatternFill("solid", fgColor="F8CBAD"), font=Font(color="9C0006")))
    wi.conditional_formatting.add("G18:G24", CellIsRule(operator="lessThanOrEqual", formula=["0.02"],
                                  fill=PatternFill("solid", fgColor="C6EFCE"), font=Font(color="006100")))
    wi.conditional_formatting.add("D18:D24", DataBarRule(start_type="min", end_type="max", color="5B9BD5"))
    wi["A26"] = ("Reading the table: a good policy saves a large share of loss while touching < 2% of good "
                 "customers (green). Red = more than 5% of good customers affected.")
    wi["A27"] = ("Receipt-before-refund saves the refund only when the item never arrives or arrives empty / wrong. "
                 "good customers affected wait for receipt (about 11 days instead of same day).")
    wi.column_dimensions["A"].width = 52
    for col, w in zip("BCDEFGH", [2, 14, 14, 14, 16, 14, 18]):
        wi.column_dimensions[col].width = w
    ch = BarChart()
    ch.type = "bar"
    ch.title = "$ saved by policy scenario"
    ch.y_axis.title = "$ saved"
    ch.add_data(Reference(wi, min_col=4, min_row=17, max_row=24), titles_from_data=True)
    ch.set_categories(Reference(wi, min_col=1, min_row=18, max_row=24))
    ch.height, ch.width, ch.legend = 9, 22, None
    wi.add_chart(ch, "J4")

    # ---------------- Summary pivots (formulas over Returns_Data) ----------------
    sm["A1"] = "Performance-window summary (Jul-Dec 2025). Every value below is a formula over Returns_Data."
    sm["A1"].font = Font(bold=True, size=13)
    header(sm, 3, ["Category", "Orders (SQL 03)", "Returns", "Return rate", "Refund $", "Avg refund $",
                   "Loss $", "Loss % of refund $"])
    phys = f"{isinr},0"
    for i, row in enumerate(cat_orders.itertuples(index=False), start=4):
        sm[f"A{i}"], sm[f"B{i}"] = row.category, row.perf_orders
        crit = f"{R(rcol['category'])},A{i}"
        sm[f"C{i}"] = f"=COUNTIFS({crit},{phys})"
        sm[f"D{i}"] = f"=IFERROR(C{i}/B{i},0)"
        sm[f"E{i}"] = f"=SUMIFS({amt},{crit})"
        sm[f"F{i}"] = f"=IFERROR(AVERAGEIFS({amt},{crit},{issued},1),0)"
        sm[f"G{i}"] = f"=SUMIFS({R(rcol['loss_amt'])},{crit})"
        sm[f"H{i}"] = f"=IFERROR(G{i}/E{i},0)"
    last = 3 + len(cat_orders)
    sm[f"A{last + 1}"] = "Total"
    sm[f"A{last + 1}"].font = BOLD
    for col in "BCEG":
        sm[f"{col}{last + 1}"] = f"=SUM({col}4:{col}{last})"
    sm[f"D{last + 1}"] = f"=IFERROR(C{last + 1}/B{last + 1},0)"
    sm[f"H{last + 1}"] = f"=IFERROR(G{last + 1}/E{last + 1},0)"
    for r in range(4, last + 2):
        sm[f"D{r}"].number_format = PCT
        sm[f"H{r}"].number_format = PCT
        for col in "EFG":
            sm[f"{col}{r}"].number_format = MONEY
    sm.conditional_formatting.add(f"D4:D{last}", ColorScaleRule(start_type="min", start_color="FFFFFF",
                                                                end_type="max", end_color="F8696B"))
    sm.conditional_formatting.add(f"H4:H{last}", ColorScaleRule(start_type="min", start_color="FFFFFF",
                                                                end_type="max", end_color="F8696B"))
    bar = BarChart()
    bar.title = "Return rate by category (Jul-Dec 2025)"
    bar.add_data(Reference(sm, min_col=4, min_row=3, max_row=last), titles_from_data=True)
    bar.set_categories(Reference(sm, min_col=1, min_row=4, max_row=last))
    bar.y_axis.numFmt = "0%"
    bar.height, bar.width, bar.legend = 8, 16, None
    sm.add_chart(bar, "J3")

    r0 = last + 4
    header(sm, r0, ["Reason code", "Returns", "Refund $", "Loss $", "Loss % of refund $"])
    reasons = ["no_longer_needed", "size_fit", "defective", "damaged", "wrong_item", "item_not_received", "unknown"]
    for i, rc in enumerate(reasons, start=r0 + 1):
        sm[f"A{i}"] = rc
        crit = f"{reason},A{i}"
        sm[f"B{i}"] = f"=COUNTIFS({crit})"
        sm[f"C{i}"] = f"=SUMIFS({amt},{crit})"
        sm[f"D{i}"] = f"=SUMIFS({R(rcol['loss_amt'])},{crit})"
        sm[f"E{i}"] = f"=IFERROR(D{i}/C{i},0)"
        sm[f"C{i}"].number_format = sm[f"D{i}"].number_format = MONEY
        sm[f"E{i}"].number_format = PCT
    sm.conditional_formatting.add(f"E{r0 + 1}:E{r0 + len(reasons)}",
                                  DataBarRule(start_type="num", start_value=0, end_type="max", color="F4B183"))

    t0 = r0 + len(reasons) + 3
    header(sm, t0, ["Risk tier (live)", "Customers", "Good customers", "Returns", "Loss $", "Loss $ per customer",
                    "Share of loss $"])
    for i, t in enumerate(["High", "Medium", "Low"], start=t0 + 1):
        sm[f"A{i}"] = t
        sm[f"B{i}"] = f"=COUNTIFS({ktier},A{i})"
        sm[f"C{i}"] = f"=COUNTIFS({ktier},A{i},{kgood},1)"
        sm[f"D{i}"] = f"=COUNTIFS({tier},A{i},{phys})"
        sm[f"E{i}"] = f"=SUMIFS({R(rcol['loss_amt'])},{tier},A{i})"
        sm[f"F{i}"] = f"=IFERROR(E{i}/B{i},0)"
        sm[f"G{i}"] = f"=IFERROR(E{i}/SUM($E${t0 + 1}:$E${t0 + 3}),0)"
        sm[f"E{i}"].number_format = sm[f"F{i}"].number_format = MONEY
        sm[f"G{i}"].number_format = PCT
    sm.conditional_formatting.add(f"A{t0 + 1}:A{t0 + 3}", FormulaRule(formula=[f'A{t0 + 1}="High"'],
                                  fill=PatternFill("solid", fgColor="F8CBAD")))
    sm.column_dimensions["A"].width = 22
    for col in "BCDEFGH":
        sm.column_dimensions[col].width = 15

    # ---------------- Monthly ----------------
    mo["A1"] = "Monthly return rate (all 24 months, by order month)"
    mo["A1"].font = Font(bold=True, size=13)
    header(mo, 3, ["Month", "Orders", "Returns", "Return rate", "Refund $", "Loss $", "Loss per order $"])
    for i, row in enumerate(monthly.itertuples(index=False), start=4):
        mo[f"A{i}"], mo[f"B{i}"], mo[f"C{i}"] = row.month, int(row.orders), int(row.returns)
        mo[f"D{i}"] = f"=IFERROR(C{i}/B{i},0)"
        mo[f"E{i}"], mo[f"F{i}"] = float(row.refund_dollars), float(row.loss_dollars)
        mo[f"G{i}"] = f"=IFERROR(F{i}/B{i},0)"
        mo[f"D{i}"].number_format = PCT
        mo[f"E{i}"].number_format = mo[f"F{i}"].number_format = MONEY
        mo[f"G{i}"].number_format = '"$"#,##0.00'
    mlast = 3 + len(monthly)
    mo.conditional_formatting.add(f"D4:D{mlast}", ColorScaleRule(start_type="min", start_color="63BE7B",
                                  mid_type="percentile", mid_value=50, mid_color="FFEB84",
                                  end_type="max", end_color="F8696B"))
    line = LineChart()
    line.title = "Return rate by order month"
    line.add_data(Reference(mo, min_col=4, min_row=3, max_row=mlast), titles_from_data=True)
    line.set_categories(Reference(mo, min_col=1, min_row=4, max_row=mlast))
    line.y_axis.numFmt = "0%"
    line.height, line.width = 8, 20
    mo.add_chart(line, "I3")
    for col, w in zip("ABCDEFG", [10, 10, 10, 12, 14, 12, 14]):
        mo.column_dimensions[col].width = w

    # ---------------- Tier Lookup ----------------
    tl["A1"] = "Customer risk lookup"
    tl["A1"].font = Font(bold=True, size=13)
    tl["A3"] = "Enter customer_id"
    example = cust.sort_values("risk_score", ascending=False)["customer_id"].iloc[0]
    tl["B3"], tl["B3"].fill, tl["B3"].border = example, INPUT, THIN
    rows = [
        ("Risk score (XLOOKUP)", f"=_xlfn.XLOOKUP($B$3,{K('A')},{K('B')},\"not found\")"),
        ("Risk tier (XLOOKUP)", f"=_xlfn.XLOOKUP($B$3,{K('A')},{K('C')},\"not found\")"),
        ("Region (INDEX/MATCH)", f"=INDEX({K('D')},MATCH($B$3,{K('A')},0))"),
        ("Orders in scoring window", f"=INDEX({K('F')},MATCH($B$3,{K('A')},0))"),
        ("Return rate", f"=INDEX({K('G')},MATCH($B$3,{K('A')},0))"),
        ("Max 90-day return rate", f"=INDEX({K('H')},MATCH($B$3,{K('A')},0))"),
        ("INR claims", f"=INDEX({K('I')},MATCH($B$3,{K('A')},0))"),
        ("Condition mismatches", f"=INDEX({K('J')},MATCH($B$3,{K('A')},0))"),
        ("Never-received refunds", f"=INDEX({K('K')},MATCH($B$3,{K('A')},0))"),
        ("Address in INR cluster", f"=INDEX({K('L')},MATCH($B$3,{K('A')},0))"),
        ("Loss $ in performance window", f"=INDEX({K('P')},MATCH($B$3,{K('A')},0))"),
        ("Tier from band table (approximate MATCH)", "=INDEX($F$6:$F$8,MATCH(B5,$E$6:$E$8,1))"),
    ]
    for i, (label, f) in enumerate(rows, start=5):
        tl[f"A{i}"], tl[f"B{i}"] = label, f
        tl[f"B{i}"].fill = OUT
    tl["B9"].number_format = tl["B10"].number_format = PCT
    tl["B15"].number_format = MONEY
    header(tl, 5, ["Points from", "Tier"], start_col=5)
    tl["E6"], tl["F6"] = 0, "Low"
    tl["E7"], tl["F7"] = "='Policy What-If'!C6", "Medium"
    tl["E8"], tl["F8"] = "='Policy What-If'!C5", "High"
    tl["E10"] = "Band table reads the live cutoffs from Policy What-If."
    tl.conditional_formatting.add("B6", CellIsRule(operator="equal", formula=['"High"'],
                                  fill=PatternFill("solid", fgColor="F8CBAD")))
    tl.column_dimensions["A"].width = 40
    tl.column_dimensions["B"].width = 16

    # ---------------- Data sample ----------------
    write_df(ds, sample)

    # ---------------- About ----------------
    notes = [
        "Returns Risk Model. All data is synthetic (made by src/generate_data.py), none of it from Amazon or any employer.",
        "",
        "Policy What-If: edit the yellow cells (tier cutoffs, $ threshold, restocking fee, repeat-returner rule,",
        "INR deny rate). Savings use SUMIFS over Returns_Data, good-customer impact uses COUNTIFS over Customers.",
        "Risk tiers on Returns_Data and Customers are formulas that read the live cutoffs.",
        "Summary: pivot-style tables using COUNTIFS / SUMIFS / AVERAGEIFS with conditional formatting and a chart.",
        "Monthly: return rate formula by month with a color scale and a native line chart.",
        "Tier Lookup: XLOOKUP and INDEX/MATCH for one customer, plus an approximate-match band table.",
        "Default inputs reproduce sql/11_policy_simulation.sql (checked in src/make_excel.py).",
        "Formulas calculate when the workbook is opened in Excel 365 / 2021 (XLOOKUP needs Excel 2021+).",
    ]
    for i, t in enumerate(notes, start=1):
        about[f"A{i}"] = t
    about["A1"].font = Font(bold=True, size=13)
    about.column_dimensions["A"].width = 110

    wb.calculation.fullCalcOnLoad = True  # Excel computes every formula when the file opens
    wb.active = wb.sheetnames.index("Policy What-If")
    path = EXCEL_DIR / "Returns_Risk_Model.xlsx"
    wb.save(path)
    check_against_sql(returns, cust)
    print(f"saved {path}")


def check_against_sql(returns, cust):
    """Recompute the what-if formulas in pandas with default inputs and compare with SQL 11."""
    hi, med, X, fee, k, deny = (C.TIER_HIGH_CUTOFF, C.TIER_MED_CUTOFF, C.HIGH_VALUE_THRESHOLD,
                                C.RESTOCK_FEE_RATE, C.REPEAT_RETURNS_90D, C.INR_DENY_RATE)
    tier = lambda s: pd.cut(s, [-1, med - 1, hi - 1, 99], labels=["Low", "Medium", "High"]).astype(str)
    r, c = returns.assign(t=tier(returns["risk_score"])), cust.assign(t=tier(cust["risk_score"]))
    av = r["avoidable_if_receipt_first"]
    saved = {
        1: av[(r.t == "High") & (r.instant_refund_flag == 1)].sum(),
        2: av[(r.instant_refund_flag == 1) & (r.refund_amount >= X)].sum(),
        3: av[(r.instant_refund_flag == 1) & (r.refund_amount >= X) & r.t.isin(["High", "Medium"])].sum(),
        4: av[r.instant_refund_flag == 1].sum(),
        5: fee * r.refund_amount[(r.reason_code == "no_longer_needed") & (r.prior_returns_90d >= k)
                                 & (r.refund_issued == 1) & (av == 0)].sum(),
        6: deny * r.refund_amount[(r.is_inr == 1) & (r.address_inr_cluster == 1) & (r.refund_issued == 1)].sum(),
    }
    saved[7] = saved[1] + saved[5] + saved[6]
    g = c.good_customer == 1
    good = {
        1: ((c.t == "High") & (c.perf_instant_refunds > 0) & g).sum(),
        2: ((c.max_instant_refund >= X) & (c.perf_instant_refunds > 0) & g).sum(),
        3: ((c.t.isin(["High", "Medium"])) & (c.max_instant_refund >= X) & (c.perf_instant_refunds > 0) & g).sum(),
        4: ((c.perf_instant_refunds > 0) & g).sum(),
        5: ((c.max_prior_returns_nln >= k) & g).sum(),
        6: ((c.inr_cluster_claims > 0) & g).sum(),
        7: ((((c.t == "High") & (c.perf_instant_refunds > 0)) | (c.max_prior_returns_nln >= k)
             | (c.inr_cluster_claims > 0)) & g).sum(),
    }
    sql = pd.read_csv(C.PROCESSED / "11_policy_simulation.csv").set_index("scenario_id")
    for sid in range(1, 8):
        assert abs(saved[sid] - sql.loc[sid, "dollars_saved"]) < 1, (sid, saved[sid], sql.loc[sid, "dollars_saved"])
        assert good[sid] == sql.loc[sid, "good_customers_affected"], (sid, good[sid], sql.loc[sid, "good_customers_affected"])
    print("excel what-if logic matches sql/11_policy_simulation.sql for all 7 scenarios")


if __name__ == "__main__":
    build()
