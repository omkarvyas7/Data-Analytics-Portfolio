"""Write the README, BRD, policy memo and status note from data/processed/metrics.json.

Numbers come from metrics.json, so the docs can't drift from the query outputs.
"""
import re

from docx import Document
from docx.shared import Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import metrics
from config import DOCS_DIR, ROOT


def usd(x, d=0):
    return f"${x:,.{d}f}"


def k(x):
    return f"${x / 1000:,.1f}k"


# ---------------------------------------------------------------- converters
def md_to_docx(md, path):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name, style.font.size = "Calibri", Pt(10.5)
    lines = md.splitlines()
    i = 0

    def add_runs(par, text):
        for j, part in enumerate(re.split(r"\*\*", text)):
            if part:
                run = par.add_run(part.replace("`", ""))
                run.bold = j % 2 == 1

    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[\s\-:|]+\|$", lines[i].strip()):
                    block.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            t = doc.add_table(rows=len(block), cols=len(block[0]))
            t.style = "Light Grid Accent 1"
            for r, row in enumerate(block):
                for c, val in enumerate(row):
                    cell = t.cell(r, c)
                    cell.text = ""
                    add_runs(cell.paragraphs[0], val)
                    for run in cell.paragraphs[0].runs:
                        run.font.size = Pt(9)
                        if r == 0:
                            run.bold = True
            doc.add_paragraph()
            continue
        m = re.match(r"^(#{1,4}) (.*)", ln)
        if m:
            doc.add_heading(m.group(2), level=len(m.group(1)) - 1 if len(m.group(1)) > 1 else 0)
        elif ln.startswith("![") or ln.startswith("<"):
            pass
        elif re.match(r"^\s*[-*] ", ln):
            add_runs(doc.add_paragraph(style="List Bullet"), re.sub(r"^\s*[-*] ", "", ln))
        elif re.match(r"^\d+\. ", ln):
            add_runs(doc.add_paragraph(style="List Number"), re.sub(r"^\d+\. ", "", ln))
        else:
            add_runs(doc.add_paragraph(), ln)
        i += 1
    doc.save(path)


def md_to_pdf(md, path):
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=12.5, spaceAfter=4)
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=15, spaceAfter=6, textColor=colors.HexColor("#232F3E"))
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11.5, spaceBefore=6, spaceAfter=3,
                        textColor=colors.HexColor("#232F3E"))
    bullet = ParagraphStyle("bl", parent=body, leftIndent=12, bulletIndent=2)

    def fmt(t):
        t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("`", "")
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)

    story, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[\s\-:|]+\|$", lines[i].strip()):
                    block.append([Paragraph(fmt(c.strip()), ParagraphStyle("t", parent=body, fontSize=8, leading=10))
                                  for c in lines[i].strip().strip("|").split("|")])
                i += 1
            t = Table(block, repeatRows=1, hAlign="LEFT")
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8ECF1")),
                                   ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFBFBF")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story += [t, Spacer(1, 6)]
            continue
        if ln.startswith("# "):
            story.append(Paragraph(fmt(ln[2:]), h1))
        elif ln.startswith("## ") or ln.startswith("### "):
            story.append(Paragraph(fmt(ln.split(" ", 1)[1]), h2))
        elif re.match(r"^\s*[-*] ", ln):
            story.append(Paragraph(fmt(re.sub(r"^\s*[-*] ", "", ln)), bullet, bulletText="•"))
        elif re.match(r"^\d+\. ", ln):
            n = ln.split(".")[0]
            story.append(Paragraph(fmt(re.sub(r"^\d+\. ", "", ln)), bullet, bulletText=f"{n}."))
        else:
            story.append(Paragraph(fmt(ln), body))
        i += 1
    SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                      topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                      title="Policy Recommendation Memo", author="Omkar Vyas").build(story)


# ---------------------------------------------------------------- content
def policy_table(m):
    rows = ["| Scenario | $ saved (Jul-Dec 2025) | % of loss $ | Good customers affected | % of good customers |",
            "|---|---|---|---|---|"]
    for p in m["policy"]:
        if p["scenario_id"] == 0:
            continue
        rows.append(f"| {p['scenario']} | {usd(p['dollars_saved'])} | {p['pct_of_baseline_loss']:.1f}% | "
                    f"{int(p['good_customers_affected']):,} | {p['pct_good_customers_affected']:.2f}% |")
    return "\n".join(rows)


def pattern_table(m):
    rows = ["| Pattern | Events | Customers | Est. loss $ (24 months) |", "|---|---|---|---|"]
    for p in m["patterns"]:
        rows.append(f"| {p['pattern']} | {int(p['events']):,} | {int(p['customers']):,} | {usd(p['est_loss_dollars'])} |")
    return "\n".join(rows)


def brd(m):
    P = m["params"]
    return f"""# Business Requirements Document: Returns Risk & Bad Debt Dashboard

Version 1.0 | Owner: Returns Analytics (Data Analyst) | Status: Draft for review

## 1. Background
Most members get instant refunds, meaning the refund is issued before the item arrives back. It keeps returns fast for the customer. Over 24 months of synthetic program data, customers returned {m['returns']:,} of {m['orders']:,} orders ({m['return_rate'] * 100:.1f}%) and filed {m['inr_claims']:,} item-not-received (INR) claims. Refunds where the item never came back within {P['BAD_DEBT_DAYS']} days add up to {usd(m['bad_debt_dollars'])} ({m['bad_debt_pct']:.2f}% of refund dollars), and {m['bad_debt_instant_share'] * 100:.0f}% of that is on instant refunds. There is no shared view today that ties return behavior and refund type to loss, so policy discussions run on anecdotes.

## 2. Problem statement
Returns Operations, Finance and the ReCommerce team can't see which customers and behaviors drive refund abuse and bad debt. They also can't see what a policy change would save against how many good customers it would slow down. Decisions on instant-refund eligibility, receipt-before-refund thresholds and restocking fees are being made without a sized trade-off.

## 3. Goals and non-goals
Goals
- G1. One dashboard, refreshed daily, that tracks return rate, refund cycle time, bad debt $ and % and INR concessions by category, region, refund type and risk tier.
- G2. A rule-based customer risk tier (Low / Medium / High) that operations can audit and explain to a customer.
- G3. A policy what-if view that sizes $ saved and good customers affected for each candidate policy before launch.
- G4. Cut loss dollars by at least 15% while affecting no more than 2% of good customers.

Non-goals
- Real-time fraud blocking at the point of return (a separate risk service owns this).
- Black-box machine-learning scoring. This phase sticks to rules a non-technical reviewer can follow.
- Changes to carrier contracts or warehouse grading standards.

## 4. Stakeholders (RACI)
| Stakeholder | Role in this project | R | A | C | I |
|---|---|---|---|---|---|
| Returns Analytics (Data Analyst) | Requirements, SQL, metric definitions, dashboard build | X | | | |
| Returns Operations Manager | Business owner, approves policy changes | | X | | |
| ReCommerce Program Manager | Resale recovery and grading inputs | | | X | |
| Finance partner | Bad debt accounting, savings sign-off | | | X | |
| Customer Experience lead | Good-customer impact, messaging | | | X | |
| Data engineer | Data pipeline, scheduled refresh | X | | | |
| Risk and Abuse Investigator | Reviews High-tier and INR cluster queues | | | | X |

## 5. Functional requirements
| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR-1 | Show return rate by month, category, region and reason code. | Monthly return rate matches sql/03 output to 0.1 pt for every month and category. |
| FR-2 | Show refund cycle time (request to refund) for instant and standard refunds, mean and p50 / p90. | Values match sql/05, and the quarter filter changes all three statistics. |
| FR-3 | Show bad debt $ and % of refund $ by refund month and refund type, using the {P['BAD_DEBT_DAYS']}-day rule. | TOTAL row equals {usd(m['bad_debt_dollars'])} on the current extract, with the rule documented on the sheet. |
| FR-4 | Show customer risk tier mix and each tier's share of loss $. | Tier counts match sql/08 and tier shares sum to 100%. |
| FR-5 | Show top abuse patterns with events, customers and estimated loss $. | Six patterns from sql/12 with definitions in a tooltip. |
| FR-6 | Provide a policy what-if with editable inputs: tier cutoffs, receipt-before-refund $ threshold, restocking fee rate, repeat-returner rule, INR deny rate. | Default inputs reproduce sql/11 for all seven scenarios; changing an input updates $ saved and good customers affected. |
| FR-7 | Allow filters for region, category, member flag, payment type, refund type and risk tier. | Every sheet responds to the global filters. |
| FR-8 | Customer lookup: enter a customer ID to see score, tier and the rule points behind it. | Lookup returns the same score as customer_risk for a 20-customer spot check. |
| FR-9 | Refresh daily by 08:00 local time with a data-quality panel. | Refresh log shows success and the DQ panel lists duplicates, null reasons and negative prices (sql/01). |
| FR-10 | Restrict customer-level views to approved roles. | Access test with a non-approved role returns no customer rows. |

## 6. Metric definitions
| Metric | Formula | Grain | Source | Owner |
|---|---|---|---|---|
| Return rate | physical returns / orders, by order month | month x category | clean_orders, return_facts | Returns Analytics |
| INR claims | count of returns with reason item_not_received | month | return_facts | Returns Analytics |
| Refund cycle time | refund_issued_date - return_request_date (days) | refund | return_facts | Returns Operations |
| Instant-refund exposure | return_received_date - refund_issued_date for instant refunds | refund | return_facts | Finance |
| Bad debt $ | sum of refunds (non-INR) with no item received within {P['BAD_DEBT_DAYS']} days of refund | refund month | return_facts | Finance |
| Bad debt % | bad debt $ / refund $ judged | refund month | return_facts | Finance |
| Condition mismatch rate | graded returns whose condition is worse than the stated reason allows / graded returns | reason code | return_facts | ReCommerce |
| Recovery rate | resale recovery value / item price of graded returns | condition | return_facts | ReCommerce |
| Loss $ | bad debt + empty-box / wrong-item refunds + INR refunds + (refund - recovery) on other mismatches | return | return_facts | Finance |
| Risk score / tier | sum of rule points, High >= {P['TIER_HIGH_CUTOFF']}, Medium >= {P['TIER_MED_CUTOFF']} | customer | customer_risk | Returns Analytics |
| Good customer | active in window with no loss event | customer | customer_outcomes | Returns Analytics |
| Good customers affected | distinct good customers touched by a policy / all good customers | scenario | sql/11 | Customer Experience |

## 7. Data requirements
- Sources: customers, orders, returns, refunds, carrier scans (daily snapshots). Keys: customer_id, order_id, return_id, refund_id.
- History: at least 24 months, so two Q4 peaks are covered. Features use an 18-month scoring window and a 6-month performance window.
- Quality rules (sql/01): drop exact duplicates, exclude non-positive prices, map null reason codes to "unknown", exclude orphan returns.
- Extract: dashboard/tableau_extract.csv, one row per return, refreshed daily.

## 8. Assumptions
- Receipt-before-refund prevents the full refund only when the item never arrives or arrives empty / wrong.
- {P['INR_DENY_RATE'] * 100:.0f}% of INR claims from flagged cluster addresses are denied after investigation.
- Restocking fee of {P['RESTOCK_FEE_RATE'] * 100:.0f}% applies only to "no longer needed" returns by customers with {P['REPEAT_RETURNS_90D']}+ returns in the prior 90 days.
- Resale recovery rates by condition: new 90%, open-box 70%, used 35%, damaged 10%, wrong item 5%, empty box 0%.

## 9. Risks
| Risk | Impact | Mitigation |
|---|---|---|
| Good customers lose instant refund and complain | CX and retention | Cap affected good customers at 2%, offer an appeal path, watch contact rate weekly |
| Abusers adapt (new accounts, new addresses) | Savings decay | Re-score monthly, keep the new-account and address-cluster rules |
| Synthetic assumptions differ from live data | Wrong sizing | Pilot in one region with a holdout before full launch |
| Restocking fee seen as unfair | Brand risk | Limit to repeat "no longer needed" returns, write clear policy text |

## 10. Open questions
1. What contact-rate increase is acceptable for customers moved off instant refund?
2. Should High-tier status expire after 6 months without a loss event?
3. Who owns the INR cluster investigation queue and its SLA?
4. Is the {P['BAD_DEBT_DAYS']}-day bad debt rule aligned with Finance write-off timing?

## 11. Timeline and milestones
| Milestone | Target | Exit criteria |
|---|---|---|
| Requirements sign-off | Week 1 | BRD approved by Returns Operations Manager and Finance partner |
| Data pipeline and extract | Week 2-3 | Daily extract passes DQ checks |
| Dashboard v1 (FR-1 to FR-5) | Week 4 | Stakeholder walkthrough, numbers reconciled to SQL |
| Policy what-if (FR-6, FR-8) | Week 5 | Finance validates savings logic |
| Pilot recommended policy | Week 6-13 | One-region pilot with control group |
| Readout and scale decision | Week 14 | Pilot results versus G4 |
"""


def memo(m):
    P = m["params"]
    pats = sorted(m["patterns"], key=lambda p: -p["est_loss_dollars"])
    return f"""# Policy Recommendation Memo: Reducing Refund Abuse and Bad Debt

To: Returns Operations Manager, Finance partner, Customer Experience lead | From: Returns Analytics | Data: synthetic, Jan 2024 to Dec 2025

## Recommendation
We recommend a targeted package instead of a blanket change. It has three parts. High-risk customers move from instant refund to refund-on-receipt. Repeat returners pay a {P['RESTOCK_FEE_RATE'] * 100:.0f}% restocking fee on "no longer needed" returns. Item-not-received claims from flagged multi-account addresses go to investigation before they are paid. Replayed on July to December 2025, the package would have saved **{usd(m['s7_saved'])} ({m['s7_pct_loss']:.1f}% of loss dollars)** and affected **{m['s7_good_affected']:,} good customers ({m['s7_pct_good']:.2f}%)**. Ending instant refunds for everyone saves more ({usd(m['s4_saved'])}), but it slows refunds for {m['s4_pct_good']:.1f}% of good customers. We don't think that trade is worth making.

## What is driving the losses
- Most bad debt sits on instant refunds. {usd(m['bad_debt_dollars'])} was refunded on items that never came back ({m['bad_debt_pct']:.2f}% of refund dollars), and {m['bad_debt_instant_share'] * 100:.0f}% of it was instant. Instant refunds pay out in {m['avg_days_instant']:.1f} days on average against {m['avg_days_standard']:.1f} days for standard refunds, so the money is out for about {m['instant_exposure_days']:.0f} days before the item arrives.
- Losses are concentrated in a small group. High-tier customers are {m['high_active_share']:.1f}% of active customers and {m['high_loss_share']:.1f}% of loss dollars. In the test period {m['high_loss_event_rate']:.1f}% of them had a loss event, compared with {m['low_loss_event_rate']:.1f}% in the Low tier ({m['stats']['lift_high_vs_low']:.1f}x, statistically significant).
- The three largest patterns over 24 months were {pats[0]['pattern']} at {usd(pats[0]['est_loss_dollars'])}, {pats[1]['pattern']} at {usd(pats[1]['est_loss_dollars'])}, and {pats[2]['pattern']} at {usd(pats[2]['est_loss_dollars'])}. Serial returning is mainly a cost-to-serve problem, so the package handles it with a restocking fee instead of blocking those customers.
- The stated reason is a weak guide to condition. {m['nln_mismatch_rate']:.1f}% of graded "no longer needed" returns came back used, damaged, empty or wrong, compared with {m['defective_mismatch_rate']:.1f}% for "defective".
- Newer accounts cost more. Accounts opened since 2024 lose {usd(m['cohort_new_loss_per_1k'])} per 1,000 orders, against {usd(m['cohort_old_loss_per_1k'])} for accounts opened before 2022.

## Options considered
{policy_table(m)}

## How the risk tier works
Customers earn points for behavior we can see in the prior 18 months: a 90-day return rate of 50% or more, a high share of order dollars returned, condition mismatches, INR claims, refunds where the item never arrived, an address shared with clustered INR claims, and a new account. High is {P['TIER_HIGH_CUTOFF']}+ points and Medium is {P['TIER_MED_CUTOFF']}-{P['TIER_HIGH_CUTOFF'] - 1}. A logistic regression on the following six months shows each rule adds risk. The strongest are a clustered INR address ({m['or_address_cluster']:.1f}x odds), a condition mismatch ({m['or_mismatch']:.1f}x) and a high 90-day return rate ({m['or_roll90']:.1f}x).

## Customer impact and safeguards
- Affected good customers still get a full refund. It arrives about {m['avg_days_standard']:.0f} days later instead of the same day.
- Tiers are reviewed monthly. A customer with no loss event for six months goes back to Low.
- Every policy has an appeal path through customer service.

## Decision requested and next steps
1. Approve a 12-week pilot of the package in one region with a matched control region.
2. Finance to confirm the {P['BAD_DEBT_DAYS']}-day bad debt rule and the savings method.
3. Customer Experience to set the acceptable contact-rate increase (guardrail) before launch.

All figures come from a synthetic dataset built for this analysis, so treat the dollar values as illustrative. The method is the part that carries over to real data.
"""


def status(m):
    return f"""# Weekly Status: Returns Risk & Bad Debt Dashboard

Subject: [Status] Returns Risk & Bad Debt Dashboard, week 4 | Overall: GREEN

Hi team,

Quick update on the returns risk and bad debt work.

## Summary
Dashboard v1 and the policy what-if model are done, and both reconcile to the SQL outputs. In the July to December 2025 replay, the recommended package would have saved {usd(m['s7_saved'])} ({m['s7_pct_loss']:.1f}% of loss dollars) and affected {m['s7_pct_good']:.2f}% of good customers. We'd like a pilot decision next week.

## Done this week
- Wrote 12 SQL queries: data quality, return rate, cycle time, bad debt, risk features, risk tiers, cohorts and the policy simulation.
- Checked the risk tiers on held-out months. High tier had a {m['high_loss_event_rate']:.1f}% loss-event rate against {m['low_loss_event_rate']:.1f}% for Low (chi-square p < 0.001).
- Shared the Excel what-if model (excel/Returns_Risk_Model.xlsx) so Finance can change thresholds and see the savings move.
- Cleaned {m['dirty_rows_flagged']:,} flagged raw records (duplicates, null reasons, negative prices) across {m['dq_checks']} checks.

## Numbers
| Metric | Value |
|---|---|
| Return rate (24 months) | {m['return_rate'] * 100:.1f}% |
| Bad debt $ / % of refund $ | {usd(m['bad_debt_dollars'])} / {m['bad_debt_pct']:.2f}% |
| Share of bad debt on instant refunds | {m['bad_debt_instant_share'] * 100:.0f}% |
| High tier: share of customers / share of loss $ | {m['high_active_share']:.1f}% / {m['high_loss_share']:.1f}% |
| Recommended package savings (6-month replay) | {usd(m['s7_saved'])} |

## Next week
- Walk Finance through the savings method and the {m['params']['BAD_DEBT_DAYS']}-day bad debt rule (Finance partner).
- Agree on the customer-contact guardrail for the pilot (Customer Experience lead).
- Scope the daily refresh job with the data engineer.

## Risks and asks
- Decision needed by next Friday: pilot region and start date (Returns Operations Manager).
- Risk: abusers may move to new accounts. Monthly re-scoring and the new-account rule cover this.

Thanks,
Returns Analytics
"""


def readme(m):
    pats = sorted(m["patterns"], key=lambda p: -p["est_loss_dollars"])
    return f"""# Returns Abuse and Bad Debt Analysis

I wanted to know which return behaviors actually cost an e-commerce returns program money, and whether those losses can be cut without making things worse for the customers who aren't doing anything wrong. Instant refunds were the obvious suspect. They are part of the story, but it turns out a small group of customers matters more than the refund type.

Built with SQL (SQLite, CTEs, window functions), Python (pandas, statsmodels, scipy, matplotlib) and Excel (SUMIFS, COUNTIFS, XLOOKUP, INDEX/MATCH, a what-if sheet). There's also a Tableau-ready extract and a few Word/PDF write-ups.

![Returns Risk & Bad Debt Dashboard](screenshots/dashboard.png)

## What I found
- Bad debt lands mostly on instant refunds. {usd(m['bad_debt_dollars'])} was refunded on items that still hadn't come back 30 days later ({m['bad_debt_pct']:.2f}% of refund dollars). {m['bad_debt_instant_share'] * 100:.0f}% of that was instant refunds, which go bad at {m['bad_debt_pct_instant']:.2f}% compared with {m['bad_debt_pct_standard']:.2f}% for standard ones.
- High-risk customers are {m['high_active_share']:.1f}% of active customers and {m['high_loss_share']:.1f}% of loss dollars in the held-out months. {m['high_loss_event_rate']:.1f}% of them had a loss event, against {m['low_loss_event_rate']:.1f}% in the Low tier ({m['stats']['lift_high_vs_low']:.1f}x, chi-square p < 0.001).
- The biggest loss patterns over 24 months were {pats[0]['pattern']} at {usd(pats[0]['est_loss_dollars'])}, {pats[1]['pattern']} at {usd(pats[1]['est_loss_dollars'])}, and {pats[2]['pattern']} at {usd(pats[2]['est_loss_dollars'])}. They overlap, so don't add them up.
- The reason code often doesn't match what shows up at the warehouse. {m['nln_mismatch_rate']:.1f}% of graded "no longer needed" returns were used, damaged, empty or the wrong item. In the logistic regression, an address with clustered INR claims multiplies the odds of a future loss by {m['or_address_cluster']:.1f}x, and a past condition mismatch by {m['or_mismatch']:.1f}x.
- For context, the return rate is {m['return_rate'] * 100:.1f}% overall and {m['top_category_rate'] * 100:.1f}% for {m['top_category']}. November and December orders come back at {m['nov_dec_return_rate'] * 100:.1f}%, compared with {m['other_month_return_rate'] * 100:.1f}% the rest of the year.

## What I'd change
Ending instant refunds for everyone is the blunt option. It saves {usd(m['s4_saved'])} but slows refunds for {m['s4_pct_good']:.1f}% of good customers. A targeted package saves less and touches far fewer people: refund-on-receipt for the High tier, a {m['params']['RESTOCK_FEE_RATE'] * 100:.0f}% restocking fee on repeat "no longer needed" returns, and an investigation step for INR claims from flagged addresses. Replayed on July to December 2025, it would have saved **{usd(m['s7_saved'])}** ({m['s7_pct_loss']:.1f}% of loss dollars) and touched {m['s7_pct_good']:.2f}% of good customers. The full trade-off table is in the [policy memo](docs/Policy_Recommendation_Memo.md).

## How I worked through it
I loosely followed DMAIC.

1. Define: wrote down the question, metrics and requirements in the [BRD](docs/BRD_Returns_Risk_Dashboard.md).
2. Measure: data-quality checks and cleaning (sql/01-02), then baselines for return rate, cycle time and bad debt (sql/03-06).
3. Analyze: built customer features with 90-day rolling windows (sql/07) and turned them into a points score and tiers (sql/08). Looked at abuse patterns and signup cohorts (sql/12, sql/10), then tested the tiers on months the score never saw (src/stats_analysis.py).
4. Improve: replayed seven policy scenarios and compared $ saved with good customers affected (sql/11). The Excel workbook lets you change the thresholds and watch the numbers move.
5. Control: a dashboard spec with a refresh schedule and a data-quality panel, a weekly status note, and a pilot plan with guardrails.

## What's in the repo
| Piece | Where |
|---|---|
| 12 numbered SQL queries: data quality, return rate, cycle time, bad debt, window-function features, risk tiers, cohorts, policy simulation | [sql/](sql) |
| Statistical checks: chi-square, two-proportion z-tests, logistic regression with odds ratios | [src/stats_analysis.py](src/stats_analysis.py) |
| Notebook that walks through the analysis | [notebooks/analysis.ipynb](notebooks/analysis.ipynb) |
| Excel what-if model (Policy What-If, Summary, Monthly, Tier Lookup tabs) | [excel/Returns_Risk_Model.xlsx](excel/Returns_Risk_Model.xlsx) |
| Dashboard extract, layout spec and a preview render | [dashboard/](dashboard), [screenshots/dashboard.png](screenshots/dashboard.png) |
| Requirements doc with goals, RACI, testable requirements and metric definitions | [docs/BRD_Returns_Risk_Dashboard.md](docs/BRD_Returns_Risk_Dashboard.md) (+ .docx) |
| Policy memo and a weekly status note | [docs/Policy_Recommendation_Memo.md](docs/Policy_Recommendation_Memo.md) (+ .docx, .pdf), [docs/Stakeholder_Status_Update.md](docs/Stakeholder_Status_Update.md) |
| Condition grading and resale recovery by reason code | sql/04 |
| Raw synthetic CSVs, query outputs and metrics.json | data/raw/, data/processed/ |
| One-command rebuild | src/run_all.py |

## How to run
```
git clone https://github.com/omkarvyas7/Data-Analytics-Portfolio.git
cd Data-Analytics-Portfolio/Returns-Abuse-and-Bad-Debt-Analysis
python -m venv .venv
.venv\\Scripts\\activate          (macOS / Linux: source .venv/bin/activate)
pip install -r requirements.txt
python src/run_all.py
```
`run_all.py` rebuilds everything from scratch: the data, the SQLite database, every query, the stats, the Excel workbook, the charts, the docs, and the executed notebook. It takes about 20 seconds. The ~90 MB database is deleted at the end. Run `python src/run_all.py --keep-db` if you want `data/returns.db` around for your own queries or to rerun the notebook.

The SQL targets SQLite 3.45 (CTEs, window functions with RANGE frames). Date math uses `julianday()` and `substr()`. In Redshift or Postgres those become `DATEDIFF` / `DATE_TRUNC`.

## About the data
All data is synthetic (made by src/generate_data.py). None of it comes from Amazon or any employer. The generator uses a fixed seed and creates {m['customers']:,} customers and {m['orders']:,} clean orders over 24 months, with a Q4 peak. Most customers behave normally. Mixed in are serial returners, wardrobers, empty-box and wrong-item returns, INR claims clustered by address, and instant refunds where the item never ships back. I also added some dirty records on purpose (duplicates, null reason codes, negative prices) so sql/01-02 has something to clean.

License: MIT
"""


def main():
    DOCS_DIR.mkdir(exist_ok=True)
    m = metrics.load()
    docs = {
        "BRD_Returns_Risk_Dashboard": brd(m),
        "Policy_Recommendation_Memo": memo(m),
        "Stakeholder_Status_Update": status(m),
    }
    for name, md in docs.items():
        (DOCS_DIR / f"{name}.md").write_text(md, encoding="utf-8")
    md_to_docx(docs["BRD_Returns_Risk_Dashboard"], DOCS_DIR / "BRD_Returns_Risk_Dashboard.docx")
    md_to_docx(docs["Policy_Recommendation_Memo"], DOCS_DIR / "Policy_Recommendation_Memo.docx")
    md_to_pdf(docs["Policy_Recommendation_Memo"], DOCS_DIR / "Policy_Recommendation_Memo.pdf")
    (ROOT / "README.md").write_text(readme(m), encoding="utf-8")
    print("docs + README written")


if __name__ == "__main__":
    main()
