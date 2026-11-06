"""Write the memo and requirements doc (md, docx, pdf). Numbers come from metrics.load().

Outputs go to docs/Executive_Summary_Dispatch_Recommendation.* and
docs/Requirements_Dispatch_Performance_Dashboard.*
"""
import re

from docx import Document
from docx.shared import Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import metrics
from common import DOCS_DIR, SCREENSHOTS_DIR


def memo(m: dict) -> str:
    return f"""# Executive Summary: Moving from First-Dispatch to Batched Dispatch

For: Rider Operations leadership, Marketplace Program Manager, Finance partner, Dispatch engineering lead
Basis: Monte Carlo simulation of {m['windows']:,} seeded batching windows ({m['riders']:,} rider requests). All data is synthetic. None of it comes from Uber or any employer.

## Recommendation

Replace greedy first-dispatch with batched assignment that minimizes total rider ETA, cap the dispatch radius at 3 miles, and roll the change out through a zone-level pilot tracked on the Dispatch Performance Dashboard. In the simulation this cuts average rider ETA by {abs(m['eta_pct']):.1f}% with no change in match rate. With the radius in place it also serves {m['mdr_match_pp']:.2f} percentage points more riders and adds {m['mdr_contrib_pct']:.2f}% modelled contribution.

## The problem with first-dispatch

- Greedy first-dispatch gives each request the nearest open driver in arrival order. Early requests take drivers that later requests needed, and the tail grows: {m['tail_greedy']:.2f}% of matched riders wait 12+ minutes, and the average window p90 ETA is {m['greedy_p90']:.2f} minutes.
- On the same riders and drivers, greedy dispatch costs {m['greedy_enroute']:.2f} unpaid en-route minutes per window. Batching costs {m['batched_enroute']:.2f}.
- Once a dispatch radius is enforced, greedy dispatch strands riders it could have served. Its match rate is {m['mdr_match_greedy']:.2f}%, against {m['mdr_match_batched']:.2f}% for batching.

## Results

| KPI | Greedy first-dispatch | Batched min-ETA | Change |
|---|---|---|---|
| Avg rider ETA (min), no radius | {m['greedy_eta']:.2f} | {m['batched_eta']:.2f} | {m['eta_pct']:+.2f}% |
| Avg window p90 ETA (min), no radius | {m['greedy_p90']:.2f} | {m['batched_p90']:.2f} | {m['p90_pct']:+.2f}% |
| Riders waiting 12+ min, no radius | {m['tail_greedy']:.2f}% | {m['tail_batched']:.2f}% | {m['tail_batched'] - m['tail_greedy']:+.2f} pp |
| Match rate, 1.5-4 mile radius | {m['mdr_match_greedy']:.2f}% | {m['mdr_match_batched']:.2f}% | {m['mdr_match_pp']:+.2f} pp |
| Avg rider ETA (min), with radius | {m['mdr_eta_greedy']:.2f} | {m['mdr_eta_batched']:.2f} | {m['mdr_eta_pct']:+.2f}% |
| Contribution per window, with radius | ${m['contrib_greedy_mdr_avg']:.2f} | ${m['contrib_batched_mdr_avg']:.2f} | {m['mdr_contrib_pct']:+.2f}% |

- The gain is largest when drivers are scarce. In under-supplied windows (fewer than 0.8 drivers per rider, {m['sup_under_windows']} windows) batching cuts ETA by {m['sup_under_pct']:.2f}% ({m['sup_under_saved']:.2f} minutes per rider). In over-supplied windows ({m['sup_over_windows']} windows) the gain is {m['sup_over_pct']:.2f}% ({m['sup_over_saved']:.2f} minutes).
- The radius is the main trade-off. At 3 miles batching keeps a {m['m3_match_batched']:.2f}% match rate, close to {m['m3_match_norad']:.2f}% with no radius, at {m['m3_eta_batched']:.2f} minutes average ETA. At 1.5 miles the match rate falls to {m['m15_match_batched']:.2f}%.
- Maximizing contribution instead of minimizing ETA adds {m['profit_contrib_pct']:.2f}% contribution over greedy (radius enforced), but average ETA rises {m['profit_eta_pct']:.2f}% versus greedy. That is why it is not the default.

## Risks and how the dashboard catches them

The gap analysis flags {m['gap_windows']} of {m['windows']:,} windows where batching looks worse on at least one KPI. None of them ({m['gap_true_regression']}) is a true ETA regression on the same riders. In {m['gap_more_riders']} windows average ETA is higher only because batching served extra riders who would otherwise go unmatched. {m['gap_p90_only']} have a longer p90 tail with a better average, and {m['gap_contrib_only']} earn less contribution because the objective ignores fare. The dashboard labels each flag by cause, so operations can tell these apart from a real regression before deciding to roll back.

## Proposed plan

1. Weeks 1-2: agree KPI definitions and guardrails (avg ETA, p90 ETA, match rate, unmatched riders, share of drivers matched, contribution) with Finance and Dispatch engineering.
2. Weeks 3-6: switch-back pilot in a set of zones, comparing batched min-ETA with a 3-mile radius against current first-dispatch. Review the dashboard daily.
3. Week 7: go or no-go. Go if p90 ETA improves, match rate does not drop, and no zone shows a true regression for 3 consecutive days.
4. After launch: test a contribution-weighted objective, but only in zones where ETA is already within target.

## Assumptions and limits

- 6 x 6 mile zone, 18 mph average speed, lognormal traffic noise, about 15 requests per window, design supply ratios of 0.6 to 1.5 drivers per rider, radius drawn from 1.5, 2, 3 and 4 miles.
- Contribution is fare (base $2.50 + $1.25 per trip mile + $0.30 per trip minute) minus $0.65 per unpaid en-route mile. It is a model input, not a P&L figure.
- Unmatched riders do not carry into the next window, and driver repositioning and cancellations are not modelled. These figures need a field pilot before they are used for planning.
"""


def brd(m: dict) -> str:
    return f"""# Requirements: Dispatch Performance Dashboard

Version 1.0 | Status: Draft for review | Data: simulated ({m['windows']:,} windows), see README

## 1. Background

Operations is considering a move from greedy first-dispatch to batched dispatch with a maximum dispatch radius (MDR). The simulation in this repository shows a {abs(m['eta_pct']):.1f}% cut in average rider ETA, and a {m['mdr_match_pp']:.2f} pp gain in match rate when a radius is enforced. To run a pilot, operations needs a single view that compares protocols on the same KPI definitions and shows regressions early.

## 2. Problem statement

Without a shared dashboard, dispatch KPIs end up in ad hoc queries with different definitions (average ETA per window in one place, per rider in another). Without a gap classification, a pilot can also be stopped on a false alarm. In the simulation {m['gap_windows']} windows look worse on some KPI, but {m['gap_true_regression']} are true ETA regressions.

## 3. Goals and non-goals

Goals
- G1. One dashboard comparing dispatch protocols on rider ETA, match rate, share of drivers matched and contribution.
- G2. Sensitivity views by max dispatch radius and driver supply ratio.
- G3. A classified gap list so reviewers can separate expected trade-offs from true regressions.
- G4. Daily automated refresh with no manual steps.

Non-goals
- Changing the dispatch algorithm itself (owned by Dispatch engineering).
- Real-time (sub-minute) monitoring or alerting on individual trips.
- Driver pay or pricing analysis.

## 4. Stakeholders (RACI)

| Role | Responsibility | RACI |
|---|---|---|
| Rider Operations Manager | Pilot owner, go/no-go decision | A |
| Business / Data Analyst | Metric definitions, SQL, dashboard build | R |
| Marketplace Program Manager | Timeline, cross-team alignment | R |
| Software Development Engineer, Dispatch | Event logging, data pipeline | C |
| Finance partner | Contribution definition and sign-off | C |
| Regional operations leads | Daily dashboard users | I |

## 5. Functional requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR1 | Show KPI tiles: avg ETA, p90 ETA, match rate, unmatched riders, share of drivers matched, contribution per window | Tile values equal sql/01 output for the same filters, to 2 decimals |
| FR2 | Filter by protocol, radius policy, MDR, supply segment and date | Every chart responds to every filter; default view is the last 7 days |
| FR3 | Protocol comparison chart for avg and p90 ETA | Bars match sql/01; baseline protocol is visually distinct |
| FR4 | ETA distribution in bands <3, 3-5, 5-8, 8-12, 12+ minutes | Band shares per protocol sum to 100% and match sql/03 |
| FR5 | Match rate vs MDR line chart | One line per protocol; values match sql/04 |
| FR6 | Batching gain by supply segment | Segments and % reduction match sql/05 |
| FR7 | Gap list with gap type for each flagged window or zone-day | Counts by gap type match sql/06 and sql/07 |
| FR8 | Daily refresh by 07:00 local time | Refresh log shows success for 5 consecutive days in UAT |
| FR9 | Data dictionary tab with each metric's formula and owner | Every tile and chart metric appears in the dictionary |

## 6. Metric definitions

| Metric | Formula | Grain | Source | Owner |
|---|---|---|---|---|
| Avg ETA (min) | SUM(total_enroute_min) / SUM(matched) | protocol x filter | simulation_results | Analyst |
| p90 ETA (min) | AVG of window-level 90th percentile ETA | protocol x filter | simulation_results | Analyst |
| Match rate | SUM(matched) / SUM(riders) | protocol x filter | simulation_results | Rider Ops |
| Unmatched riders | SUM(riders - matched) | protocol x filter | simulation_results | Rider Ops |
| Share of drivers matched (driver_utilization) | SUM(matched) / SUM(drivers) | protocol x filter | simulation_results | Rider Ops |
| Contribution per window ($) | AVG(profit_usd) | protocol x filter | simulation_results | Finance |
| 12+ min share | riders with ETA >= 12 / matched riders | protocol | simulation_matches | Analyst |
| Gap type | CASE rules in sql/06 | window | simulation_results | Analyst |

## 7. Data requirements

- Window-level table: window_id, zone, timestamp, protocol, riders, drivers, matched, MDR, ETA aggregates, contribution. In this repository: dashboard/tableau_extract.csv ({m['windows'] * 5:,} rows).
- Rider-level match table for ETA distribution: dashboard/tableau_eta_distribution.csv (pre-aggregated) or simulation_matches.
- Production equivalent: dispatch event logs with request, assignment and pickup timestamps; latency up to 24 hours is acceptable.

## 8. Assumptions

- Protocol labels are logged on every dispatch decision during the pilot.
- ETA is measured as assignment-to-pickup time, not the quoted ETA.
- Contribution uses the Finance-approved fare and cost model.

## 9. Risks

- Definition drift between teams. Mitigation: FR9 data dictionary and Finance sign-off.
- Small zones produce noisy daily KPIs. Mitigation: show window counts and use 7-day rolling views.
- Higher average ETA after launch may reflect more riders served. Mitigation: FR7 gap classification.

## 10. Open questions

- What p90 ETA target counts as success for go/no-go?
- Is the 3-mile radius uniform, or set by zone density?
- Which BI tool hosts the production version (Tableau or QuickSight)?

## 11. Timeline and milestones

| Milestone | Target |
|---|---|
| Requirements sign-off | Week 1 |
| Metric definitions approved by Finance | Week 2 |
| Dashboard v1 on simulated extract | Week 3 |
| UAT with operations leads | Week 4 |
| Pilot launch with daily refresh | Week 5 |
| Go/no-go review | Week 7 |
"""


# ---------------- tiny markdown renderers ----------------
def _clean(t: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"\1", t).replace("`", "")


def to_docx(md: str, path):
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# "):
            h = doc.add_heading(_clean(ln[2:]), level=0)
            h.runs[0].font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
        elif ln.startswith("## "):
            doc.add_heading(_clean(ln[3:]), level=1)
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[-| ]+\|$", lines[i]):
                    rows.append([_clean(c.strip()) for c in lines[i].strip("|").split("|")])
                i += 1
            t = doc.add_table(rows=len(rows), cols=len(rows[0]))
            t.style = "Light Grid Accent 1"
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    t.cell(r, c).text = val
                    if r == 0:
                        t.cell(r, c).paragraphs[0].runs[0].bold = True
            doc.add_paragraph()
            continue
        elif ln.startswith("- "):
            doc.add_paragraph(_clean(ln[2:]), style="List Bullet")
        elif re.match(r"^\d+\. ", ln):
            doc.add_paragraph(_clean(re.sub(r"^\d+\. ", "", ln)), style="List Number")
        elif ln.strip():
            doc.add_paragraph(_clean(ln))
        i += 1
    doc.save(path)


def to_pdf(md: str, path, image=None):
    ss = getSampleStyleSheet()
    body = ss["BodyText"]
    body.fontSize, body.leading = 9.5, 12.5
    story = []
    lines = md.splitlines()
    i = 0
    esc = lambda s: _clean(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# "):
            story += [Paragraph(esc(ln[2:]), ss["Title"]), Spacer(1, 4)]
        elif ln.startswith("## "):
            story.append(Paragraph(esc(ln[3:]), ss["Heading2"]))
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[-| ]+\|$", lines[i]):
                    rows.append([Paragraph(esc(c.strip()), body) for c in lines[i].strip("|").split("|")])
                i += 1
            ncol = len(rows[0])
            widths = [2.6 * inch] + [(7.0 - 2.6) * inch / (ncol - 1)] * (ncol - 1)
            t = Table(rows, colWidths=widths, repeatRows=1)
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F1")),
                                   ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story += [t, Spacer(1, 6)]
            continue
        elif ln.startswith("- "):
            story.append(Paragraph(esc(ln[2:]), body, bulletText="\u2022"))
        elif re.match(r"^\d+\. ", ln):
            n = ln.split(".")[0]
            story.append(Paragraph(esc(re.sub(r"^\d+\. ", "", ln)), body, bulletText=f"{n}."))
        elif ln.strip():
            story.append(Paragraph(esc(ln), body))
        i += 1
        if image and ln.startswith("## Results"):
            story += [Image(str(image), width=7.0 * inch, height=4.4 * inch), Spacer(1, 6)]
    SimpleDocTemplate(str(path), pagesize=LETTER, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                      topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                      title=_clean(md.splitlines()[0][2:]), author="Omkar Vyas").build(story)


def main():
    m = metrics.load()
    ex, rq = memo(m), brd(m)
    base_ex = DOCS_DIR / "Executive_Summary_Dispatch_Recommendation"
    base_rq = DOCS_DIR / "Requirements_Dispatch_Performance_Dashboard"
    base_ex.with_suffix(".md").write_text(ex, encoding="utf-8")
    base_rq.with_suffix(".md").write_text(rq, encoding="utf-8")
    to_docx(ex, base_ex.with_suffix(".docx"))
    to_docx(rq, base_rq.with_suffix(".docx"))
    to_pdf(ex, base_ex.with_suffix(".pdf"), image=SCREENSHOTS_DIR / "dashboard.png")
    print("docs written to", DOCS_DIR)


if __name__ == "__main__":
    main()
