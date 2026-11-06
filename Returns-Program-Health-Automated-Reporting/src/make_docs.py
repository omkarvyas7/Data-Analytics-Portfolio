"""Write docs/ (md + docx) and README.md. Every number is read from the pipeline outputs."""
import json

import pandas as pd

from config import DEFAULT_WEEK, DOCS, PROCESSED, RAW, ROOT, DASH_DIR, fmt_kpi
from md_to_docx import convert

WEEK = DEFAULT_WEEK


def load():
    d = PROCESSED / f"wbr_{WEEK}"
    f = {
        "rag": pd.read_csv(d / "02_kpi_vs_target_rag.csv"),
        "sum": pd.read_csv(d / "01_wbr_kpi_summary.csv"),
        "ph": pd.read_csv(d / "06_program_health_initiative.csv"),
        "ms": pd.read_csv(d / "07_milestone_status.csv"),
        "risks": pd.read_csv(d / "08_open_high_risks.csv"),
        "gaps": pd.read_csv(d / "10_gap_list_partner_teams.csv"),
        "movers": pd.read_csv(d / "04_top_movers_category.csv"),
        "drv": pd.read_csv(PROCESSED / "driver_analysis_summary.csv").set_index("metric")["value"],
        "dq": pd.read_csv(PROCESSED / "data_quality_log.csv"),
        "nar": json.loads((d / "narrative.json").read_text(encoding="utf-8")),
        "allrisks": pd.read_csv(RAW / "risks.csv", keep_default_na=False),
        "targets": pd.read_csv(RAW / "kpi_targets.csv"),
        "extract_rows": sum(1 for _ in open(DASH_DIR / "tableau_extract.csv", encoding="utf-8")) - 1,
    }
    return f


def k(f, kpi, col):
    return f["rag"].set_index("kpi").loc[kpi, col]


def s(f, kpi, col):
    return f["sum"].set_index("kpi").loc[kpi, col]


def facts(f):
    D = f["drv"]
    unit = dict(zip(f["rag"]["kpi"], f["rag"]["unit"]))
    x = {}
    for kpi in f["rag"]["kpi"]:
        x[f"{kpi}_act"] = fmt_kpi(k(f, kpi, "actual"), unit[kpi])
        x[f"{kpi}_tgt"] = fmt_kpi(k(f, kpi, "target"), unit[kpi])
        x[f"{kpi}_rag"] = k(f, kpi, "rag")
        x[f"{kpi}_var"] = f"{k(f, kpi, 'variance_pct') * 100:+.1f}%"
        x[f"{kpi}_yoy"] = f"{s(f, kpi, 'yoy_pct') * 100:+.1f}%"
        x[f"{kpi}_ly"] = fmt_kpi(s(f, kpi, "last_year"), unit[kpi])
        x[f"{kpi}_miss4"] = int(k(f, kpi, "weeks_missed_last_4"))
    c = f["nar"]["counts"]
    x.update({f"n_{a}": c[a] for a in c})
    ph = f["ph"]
    x["at_risk"] = int(ph["milestones_at_risk"].sum())
    x["blocked"] = int(ph["blocked_by_dependency"].sum())
    x["high_risks"] = int(ph["open_high_risks"].sum())
    x["red_inits"] = ", ".join(ph.loc[ph["program_rag"] == "Red", "initiative"])
    x["p1"] = int((f["gaps"]["priority"] == "P1").sum())
    x["p2"] = int((f["gaps"]["priority"] == "P2").sum())
    x["gap_teams"] = f["gaps"]["team"].nunique()
    m402 = f["ms"].set_index("milestone_id").loc["M402"]
    x["m402_slip"] = int(m402["schedule_variance_days"])
    x["m402_fc"] = m402["forecast_end"]
    unm = f["risks"][f["risks"]["needs_escalation"] == 1]
    x["unmitigated"] = len(unm)
    x["unmitigated_ids"] = ", ".join(unm["risk_id"])
    for key in D.index:
        x[f"d_{key}"] = D[key]
    x["d_share_pct"] = f"{float(D['top_driver_volume_share']) * 100:.1f}%"
    x["d_cost_week"] = f"${float(D['excess_contact_cost_week_usd']):,.0f}"
    x["d_cost_year"] = f"${float(D['excess_contact_cost_annualized_usd']):,.0f}"
    x["d_excess"] = f"{float(D['excess_contacts_week']):,.0f}"
    mv = f["movers"].set_index(["category", "kpi"])
    x["elec_recovery_yoy"] = f"{mv.loc[('Electronics', 'recovery_rate'), 'yoy_pct'] * 100:+.1f}%"
    x["beauty_cost_yoy"] = f"{mv.loc[('Beauty', 'cost_per_return'), 'yoy_pct'] * 100:+.1f}%"
    x["home_cycle_yoy"] = f"{mv.loc[('Home', 'refund_cycle_days'), 'yoy_pct'] * 100:+.1f}%"
    dq = f["dq"].set_index("check")["rows"]
    x["dq_dups"] = int(dq["exact duplicate rows removed"])
    x["dq_mkt"] = int(dq["marketplace codes trimmed/upper-cased"])
    x["dq_ch"] = int(dq["channel labels mapped to canonical names"])
    x["dq_neg"] = int(dq["rows with negative return_units excluded"])
    x["dq_miss"] = int(dq["rows with missing cycle scans excluded from cycle-time calc only"])
    x["dq_rows"] = int(dq["rows loaded after cleaning"])
    x["extract_rows"] = f["extract_rows"]
    x["week_end"] = f["nar"]["week_end"]
    return x


def kpi_table(f):
    rows = ["| KPI | Actual | Target | Variance (unfav +) | YoY | RAG |", "|---|---|---|---|---|---|"]
    for _, r in f["rag"].iterrows():
        rows.append(f"| {r['display_name']} | {fmt_kpi(r['actual'], r['unit'])} | {fmt_kpi(r['target'], r['unit'])} | "
                    f"{r['variance_pct'] * 100:+.1f}% | {s(f, r['kpi'], 'yoy_pct') * 100:+.1f}% | {r['rag']} |")
    return "\n".join(rows)


def metric_dictionary(f):
    defs = {
        "return_rate": ("SUM(return_units) / SUM(units_shipped)", "returns_daily, shipments_daily"),
        "refund_cycle_days": ("SUM(transit_hours + processing_hours) / 24 / SUM(cycle_units); rows with missing scans excluded from numerator and denominator", "returns_daily"),
        "contacts_per_return": ("SUM(customer_contacts) / SUM(return_units)", "returns_daily"),
        "resale_pct": ("SUM(resold_units) / SUM(resold + liquidated + recycled + waste units)", "returns_daily"),
        "liquidation_pct": ("SUM(liquidated_units) / SUM(disposition units)", "returns_daily"),
        "recovery_rate": ("SUM(recovered_usd) / SUM(refund_usd)", "returns_daily"),
        "waste_units": ("SUM(waste_units) (landfill)", "returns_daily"),
        "cost_per_return": ("SUM(processing_cost_usd) / SUM(return_units)", "returns_daily"),
    }
    rows = ["| Metric | Formula | Grain | Source | Better | Target | Owner team |", "|---|---|---|---|---|---|---|"]
    for _, t in f["targets"].iterrows():
        fm, src = defs[t["kpi"]]
        rows.append(f"| {t['display_name']} (`{t['kpi']}`) | {fm} | week (Mon-Sun) x marketplace x category x channel | {src} | "
                    f"{t['direction']} | {fmt_kpi(t['target'], t['unit'])} (amber band {t['amber_band'] * 100:.0f}%) | {t['owner_team']} |")
    rows.append("| Schedule variance (days) | actual_end - planned_end; else forecast_end - planned_end; else as_of - planned_end if overdue | milestone | milestones | lower | 0 (Amber > 7, Red > 21) | milestone owner |")
    rows.append("| Blocked by dependency | predecessor not Complete AND milestone not Complete AND planned_start <= as_of | milestone | milestones | lower | 0 | predecessor owner |")
    rows.append("| Risk severity | likelihood (1-5) x impact (1-5); High >= 15 | risk | risks | lower | no unmitigated High risks | risk owner |")
    return "\n".join(rows)


def brd(f, x):
    return f"""# Business Requirements Document: Returns Program Health Dashboard and Automated WBR

| Field | Value |
|---|---|
| Document owner | Data Analyst, Returns & ReCommerce Analytics |
| Status | Approved for build (v1.0) |
| Business sponsor | Director, Returns Experience & ReCommerce |
| Last updated | {x['week_end']} |
| Related artifacts | `sql/`, `src/run_wbr.py`, `excel/Program_Tracker.xlsx`, `dashboard/dashboard_spec.md` |

## 1. Background

The Returns and ReCommerce program runs five cross-functional initiatives: grade-and-resell open-box electronics, returnless refunds for low-value items, drop-off point expansion, return reason capture redesign, and liquidation partner onboarding. Each initiative is owned by a different team and moves a different customer or cost KPI. Today the weekly business review (WBR) is assembled by hand from four spreadsheets, takes about a day of analyst time, and reports outcome KPIs separately from program status. Leaders cannot see in one place whether a KPI miss is linked to a late or blocked initiative.

## 2. Problem statement

Leaders need a single, automated weekly view that answers three questions: (1) are the returns outcome KPIs on target, (2) are the initiatives that should move them on schedule, and (3) which team owes what action before next week. For the week of {WEEK}, the manual process would not have connected the refund-cycle miss ({x['refund_cycle_days_act']} vs {x['refund_cycle_days_tgt']}) to the blocked drop-off Wave 2 milestone and an unmitigated carrier risk.

## 3. Goals and non-goals

**Goals**
- G1. Publish the WBR (Excel workbook + PDF pre-read) automatically every Monday by 08:00 local, with zero manual data steps.
- G2. Show every KPI vs target with WoW, YoY, trailing-4-week average and a documented RAG rule.
- G3. Roll up program health (schedule variance, milestones at risk, blocked dependencies, open High risks) per initiative.
- G4. Produce a gap list that routes each miss to an owning team with a specific ask and due date.
- G5. Provide a Tableau/QuickSight-ready extract so the same numbers drive the interactive dashboard.

**Non-goals**
- Real-time (intra-day) monitoring; the grain is weekly.
- Customer-level or order-level drill-down (privacy and scale; aggregates only).
- Changing initiative scope or targets; the dashboard reports against targets set by the business owners.
- Forecasting KPIs (a later phase).

## 4. Stakeholders (RACI)

| Stakeholder role | Interest | R | A | C | I |
|---|---|---|---|---|---|
| Director, Returns Experience & ReCommerce (sponsor) | Decisions and escalations at the WBR | | X | | |
| ReCommerce Program Manager | Program health, milestone data quality | X | | | |
| Data Analyst, Returns Analytics (document owner) | Requirements, SQL, pipeline, dashboard | X | | | |
| Returns Operations Manager | Processing and grading KPIs | | | X | X |
| Reverse Logistics Program Manager | Cycle time, drop-off network | | | X | X |
| Returns Experience Product Manager | Contacts per return, reason capture | | | X | X |
| Disposition Program Manager | Recovery rate, waste, liquidation | | | X | X |
| Returns Policy Manager / Risk & Abuse Prevention Manager | Returnless refunds, abuse, bad debt | | | X | X |
| Finance partner | $ recovery and cost definitions | | | X | X |
| Software Development Manager / Data Engineer | Source feeds, scheduling, access | | | X | X |
| Business Intelligence Engineer | Tableau/QuickSight build and refresh | X | | | |

## 5. User stories

1. As the program sponsor, I want a one-page headline written from the numbers so that I can see the week's top issues in two minutes before the WBR.
2. As a KPI owner, I want each KPI shown against its target with a RAG status and WoW/YoY deltas so that I know whether I need to present a recovery plan.
3. As the program manager, I want milestones with schedule variance and dependency blockers so that I can escalate cross-team blockers before they slip the launch.
4. As a partner team lead, I want a gap list filtered to my team with a due date so that I know exactly what I owe before next week.
5. As an analyst, I want a driver breakdown (marketplace x channel, rate vs mix, transit vs processing) so that I can explain a KPI miss without ad-hoc queries.
6. As a BI engineer, I want one tidy extract with additive measures so that I can rebuild every KPI in Tableau/QuickSight without custom SQL.

## 6. Functional requirements

| ID | Requirement | Acceptance criteria | Delivered by |
|---|---|---|---|
| FR-1 | The pipeline runs for any week with one command: `python src/run_wbr.py --week YYYY-MM-DD`. | Given a Monday within the data range, the command exits 0 and writes the xlsx, PDF and query CSVs; a non-Monday or out-of-range week exits non-zero with a clear message. | `src/run_wbr.py`, `src/run_sql.py` |
| FR-2 | KPI summary shows current, prior week, WoW (abs and %), same week last year, YoY, trailing-4-week average and target for all 8 KPIs. | Values match `sql/01_wbr_kpi_summary.sql` output to 4 decimals; YoY compares 52 weeks back (-364 days). | `sql/01`, WBR Summary tab |
| FR-3 | Each KPI gets a RAG status from a documented rule (Green at/better than target; Amber within the KPI's tolerance band; Red outside). | Excel RAG formula (column P) equals SQL RAG (column Q) for every KPI; status counts agree. | `sql/02`, WBR Summary tab |
| FR-4 | Persistence of a miss is shown (weeks missed in the last 4). | Column present in the scorecard; equals count of non-Green weeks in the trailing 4. | `sql/02` |
| FR-5 | Top movers by category for cycle time, contacts, cost, recovery and return rate, ranked by absolute WoW % change, with YoY. | Ranks 1..5 per KPI; favourable/unfavourable flag respects KPI direction. | `sql/04`, Top Movers tab |
| FR-6 | When refund cycle time is off target, the WBR includes a marketplace x channel driver decomposition into rate and mix effects, split into transit and processing. | Sum of segment effects equals the program change vs baseline (to 3 decimals). | `sql/05`, Refund Cycle Drivers tab |
| FR-7 | Program health per initiative: milestones complete/total, at risk, blocked by dependency, max and average schedule variance, open High risks, initiative RAG. | Rules in `sql/06` header; recomputed in `excel/Program_Tracker.xlsx` with COUNTIFS/MAXIFS and give the same counts. | `sql/06`, `sql/07`, tracker |
| FR-8 | Risk register shows open risks with severity = likelihood x impact and flags High risks with no mitigation or past target close. | Flag = 1 exactly for those rows; rows highlighted in Excel and PDF. | `sql/08` |
| FR-9 | Cross-team dependency blockers list the blocked milestone, the predecessor and its owning team. | Every milestone whose predecessor is not Complete and whose planned start has passed appears once. | `sql/09` |
| FR-10 | Gap list routes each KPI miss, blocker, slipping milestone and unmitigated High risk to a team with priority (P1/P2), ask and due date. | Each gap has team, owner role, ask and due date = next WBR as-of date. | `sql/10`, Gap List tab |
| FR-11 | The PDF pre-read is 2-3 pages: headline narrative, KPI scorecard, program health, trend and driver charts, asks/escalations. | Page count between 2 and 3; every narrative number traceable to a query CSV. | `src/wbr_pdf.py`, `src/narrative.py` |
| FR-12 | Excel workbook is formula-driven: changing the report week or a target on the Inputs tab recalculates the summary. | Summary cells contain INDEX/MATCH and AVERAGEIFS formulas, not pasted values; RAG uses conditional formatting. | `src/wbr_excel.py` |
| FR-13 | A tidy BI extract with additive measures is produced every run. | `dashboard/tableau_extract.csv` rebuilds program KPIs to within rounding of `v_weekly_kpi`. | `sql/11`, `src/make_dashboard.py` |

## 7. Non-functional requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| NFR-1 Refresh SLA | Source data lands by Sunday 23:59; WBR artifacts published by Monday 08:00 local. | Scheduled task at 06:00; run time under 5 minutes (current run is a few seconds). |
| NFR-2 Reliability | A failed run alerts the owner and never publishes partial output silently. | Non-zero exit code on failure; scheduler sends failure notice; previous week's file stays in place. |
| NFR-3 Data quality | Duplicates, key casing, sign errors and missing scans are handled by rule and logged. | `data/processed/data_quality_log.csv` written each run; zero duplicate keys at daily grain after cleaning. |
| NFR-4 Reproducibility | Any past week can be regenerated from raw data. | `run_wbr.py --week <past Monday>` reproduces that week's numbers. |
| NFR-5 Access | Aggregated, non-customer data only. Dashboard viewers: program team and partner teams; edit rights on targets restricted to KPI owners. | No customer identifiers in any extract; target changes go through the KPI owner. |
| NFR-6 Portability | SQL is ANSI-style (CTEs, window functions, CASE) and ports to Redshift/Postgres with date-function swaps only. | Dialect notes in each SQL header and the README. |
| NFR-7 Readability | A non-technical leader can read the headline without the tables. | Headline sentences use plain units (days, %, $) and name the owning team. |

## 8. Metric dictionary

{metric_dictionary(f)}

## 9. Data sources and requirements

| Source | Grain | Key fields | Refresh | Owner |
|---|---|---|---|---|
| `returns_daily` | day x marketplace x category x return channel | return_units, refund_usd, transit_hours, processing_hours, customer_contacts, disposition units, recovered_usd, processing_cost_usd | daily, by 23:59 | Data Engineer |
| `shipments_daily` | day x marketplace x category | units_shipped | daily | Data Engineer |
| `kpi_targets` | KPI | target, direction, amber_band, owner_team, initiative_id | on change (owner sign-off) | KPI owners |
| `initiatives`, `milestones` | initiative / milestone | planned, actual and forecast dates, status, % complete, depends_on | weekly, by Friday 17:00 | Program managers |
| `risks`, `issues` | risk / issue | likelihood, impact, mitigation, owner, dates | weekly | Initiative owners |

Data cleaning rules applied this run: {x['dq_dups']} duplicate rows removed, {x['dq_mkt']} marketplace codes normalised, {x['dq_ch']} channel labels mapped, {x['dq_neg']} negative-unit rows excluded, {x['dq_miss']} rows with missing scans excluded from the cycle-time calculation only. {x['dq_rows']:,} clean daily rows loaded.

## 10. Assumptions

- Weeks run Monday to Sunday; YoY compares the same week 52 weeks earlier.
- Trailing-4-week average is the mean of the four weekly values (a ratio-of-sums version is available in the extract).
- Milestone status and forecasts are updated by owners before the Friday cut-off; the pipeline does not infer status.
- Customer contact handling cost is a planning assumption ($4.50 per contact) until finance provides a rate.

## 11. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Milestone data entered late or inconsistently | Program RAG is stale | Friday cut-off, late-update flag, program manager owns tracker hygiene |
| Target changes without sign-off | RAG loses credibility | Targets table owned by KPI owners; change log in the tracker |
| Upstream feed delay on Sunday | WBR misses the 08:00 SLA | Retry at 07:00; alert the Data Engineer on failure |
| Metric definition drift between Excel, PDF and BI | Conflicting numbers in the room | One SQL layer feeds all three outputs; Excel shows Excel vs SQL RAG side by side |

## 12. Open questions

1. Should the amber tolerance band be uniform (5%) or set per KPI by the owner? (Current build: per KPI, 3-5%.)
2. Does finance want recovery rate on refund value or on original sale price?
3. Which partner teams need row-level security in the BI tool versus a shared view?

## 13. Timeline and milestones

| Milestone | Target date | Exit criteria |
|---|---|---|
| Requirements sign-off | 2026-09-25 | This BRD approved by sponsor and KPI owners |
| SQL layer and data-quality rules | 2026-10-09 | `sql/00-11` reviewed; DQ log in place |
| Excel + PDF WBR automated | 2026-10-23 | FR-1 to FR-12 pass for 3 back-tested weeks |
| BI dashboard live (Tableau/QuickSight) | 2026-11-06 | FR-13; extract refresh scheduled |
| First automated WBR | 2026-11-02 | Run for week {WEEK}; artifacts in `excel/` and `reports/` |
| Retire manual WBR | 2026-11-30 | Four consecutive on-time automated WBRs |

## Appendix: example output (week of {WEEK})

{kpi_table(f)}
"""


def program_plan(f, x):
    ms = pd.read_csv(RAW / "milestones.csv", keep_default_na=False)
    stat = f["ms"].set_index("milestone_id")
    mrows = ["| ID | Initiative | Milestone | Owner role | Planned end | Forecast / actual | Status | Slip (d) | RAG |", "|---|---|---|---|---|---|---|---|---|"]
    for _, m in ms.iterrows():
        st = stat.loc[m["milestone_id"]]
        fa = m["actual_end"] or m["forecast_end"] or "-"
        mrows.append(f"| {m['milestone_id']} | {m['initiative_id']} | {m['milestone']} | {m['owner_role']} | {m['planned_end']} | {fa} | "
                     f"{m['status']} | {int(st['schedule_variance_days'])} | {st['milestone_rag']} |")
    rrows = ["| ID | Initiative | Risk | L | I | Severity | Status | Owner role | Mitigation | Close by |", "|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in f["allrisks"].iterrows():
        sev = int(r["likelihood"]) * int(r["impact"])
        rrows.append(f"| {r['risk_id']} | {r['initiative_id']} | {r['risk']} | {r['likelihood']} | {r['impact']} | {sev} | {r['status']} | "
                     f"{r['owner_role']} | {r['mitigation'] or '(none recorded)'} | {r['target_close_date']} |")
    phr = ["| Initiative | Team | Done | At risk | Blocked | Max slip (d) | Open High risks | RAG |", "|---|---|---|---|---|---|---|---|"]
    for _, p in f["ph"].iterrows():
        phr.append(f"| {p['initiative']} | {p['team']} | {p['milestones_complete']}/{p['milestones_total']} | {p['milestones_at_risk']} | "
                   f"{p['blocked_by_dependency']} | {p['max_slip_days']} | {p['open_high_risks']} | {p['program_rag']} |")
    return f"""# Program Plan: Returns Experience and ReCommerce Initiatives (FY26 H2)

Status as of {x['week_end']}. Source of truth: `excel/Program_Tracker.xlsx`; roll-up logic in `sql/06_program_health_initiative.sql`.

## 1. Objectives

Each initiative is tied to one KPI it is supposed to move:

| Initiative | Primary KPI | Current (week of {WEEK}) | Target |
|---|---|---|---|
| INI-1 Grade-and-resell open-box electronics | Resold share of dispositions | {x['resale_pct_act']} | {x['resale_pct_tgt']} |
| INI-2 Returnless refunds for low-value items | Cost per return | {x['cost_per_return_act']} | {x['cost_per_return_tgt']} |
| INI-3 Drop-off point expansion | Refund cycle time | {x['refund_cycle_days_act']} | {x['refund_cycle_days_tgt']} |
| INI-4 Return reason capture redesign | Customer contacts per return | {x['contacts_per_return_act']} | {x['contacts_per_return_tgt']} |
| INI-5 Liquidation partner onboarding | Recovery rate | {x['recovery_rate_act']} | {x['recovery_rate_tgt']} |

## 2. Current health

{chr(10).join(phr)}

{x['n_init_red']} initiatives are Red ({x['red_inits']}). {x['at_risk']} milestones are at risk and {x['blocked']} are blocked by a dependency. The critical path runs through M402 (QR label and reason-code API), {x['m402_slip']} days late with a forecast of {x['m402_fc']}; it blocks drop-off Wave 2 (M304) and two reason-capture milestones.

## 3. Governance and cadence

- Weekly WBR (Tuesday, 45 min): sponsor, initiative owners, finance partner. Pre-read is `reports/WBR_<week>.pdf`, published Monday 08:00.
- Tracker cut-off: owners update status, % complete and forecast dates by Friday 17:00.
- Monthly business review: re-baseline requests, target changes, resourcing.
- Change control: a milestone date moves only with the owner's forecast and a reason in the issue log; targets change only with KPI-owner sign-off.

## 4. RACI

| Activity | Sponsor (Director) | ReCommerce PgM | Data Analyst | Returns Ops Mgr | Reverse Logistics PgM | PM Returns Experience | Disposition PgM | SDM / Data Eng | Finance partner |
|---|---|---|---|---|---|---|---|---|---|
| Set KPI targets | A | C | C | R | R | R | R | I | C |
| Maintain milestone tracker | I | A | C | R | R | R | R | R | I |
| Build and run WBR pipeline | I | C | A/R | I | I | I | I | C | I |
| Explain KPI misses (root cause) | I | C | R | R | R | R | R | C | C |
| Escalate cross-team blockers | A | R | C | C | C | C | C | C | I |
| Approve re-baselines | A | R | I | C | C | C | C | C | C |
| Source data feeds and scheduling | I | I | C | I | I | I | I | A/R | I |
| Validate $ recovery and cost | I | I | C | I | I | I | C | I | A/R |

R = responsible, A = accountable, C = consulted, I = informed.

## 5. Milestones

{chr(10).join(mrows)}

Slip = actual or forecast end minus planned end (or days overdue when no forecast). RAG rules: Red if Blocked, blocked by dependency, or slip > 21 days; Amber if At Risk, slip > 7 days, or the planned start has passed without a start.

## 6. Risk register

{chr(10).join(rrows)}

Severity = likelihood x impact (1-5 each). High >= 15. {x['unmitigated']} High risks ({x['unmitigated_ids']}) have no mitigation recorded or are past their close date and are escalated on the WBR.

## 7. Dependencies

| Dependent milestone | Depends on | Owning team of predecessor | Type |
|---|---|---|---|
| M304 Wave 2 go-live | M402 QR label and reason-code API | Returns Experience Tech | Cross-team |
| M403 UX redesign A/B test | M402 | Returns Experience Tech | Same team |
| M404 Reason-code data feed | M402 | Returns Experience Tech | Same team |
| M106 Handoff to operations | M104 Scale grading to 6 sites | ReCommerce | Same team |
| M306 Wave 3 plan | M304 | Reverse Logistics Ops | Same team |

## 8. Lean / DMAIC application

- Define: each initiative maps to one primary KPI and target (section 1).
- Measure: weekly KPI layer (`sql/00-03`) with control-chart monitoring for cycle time.
- Analyze: driver decomposition (`sql/05`, `notebooks/analysis.ipynb`) separates rate vs mix and transit vs processing.
- Improve: gap list (`sql/10`) assigns countermeasures with owners and dates.
- Control: the WBR itself; RAG persistence (weeks missed of last 4) shows whether a fix held.
- Waste removed from the reporting process: manual copy-paste of four spreadsheets (about one analyst-day per week) replaced by one scheduled command.
"""


def comm_plan(f, x):
    return f"""# Stakeholder Communication Plan and Escalation Path

Program: Returns Experience and ReCommerce initiatives. Owner: ReCommerce Program Manager, with the Data Analyst for WBR content.

## 1. Principles

- One source of numbers: the WBR pipeline (`src/run_wbr.py`). Nobody presents a number that is not in the WBR or traceable to `sql/`.
- Lead with the decision needed, then the data. Write for a reader who has two minutes.
- Bad news travels fast: a Red KPI or a blocked dependency is communicated the day it is known, not held for the WBR.

## 2. Audiences and cadence

| Audience | What they need | Channel | Cadence | Owner |
|---|---|---|---|---|
| Director, Returns Experience & ReCommerce | Headline, Red items, decisions needed | PDF pre-read + WBR meeting | Weekly (Mon 08:00 pre-read, Tue review) | ReCommerce PgM |
| Initiative owners (5 teams) | Their KPIs, milestones, gaps due | Excel WBR (Gap List filtered by team) | Weekly | Data Analyst |
| Partner teams (Risk & Abuse, Transportation, Vendor Mgmt, Finance) | Asks routed to them, due dates | Email digest of their gap-list rows | Weekly, Monday | ReCommerce PgM |
| Engineering (SDM, Data Engineer) | Blockers on the critical path, data issues | Sprint sync + ticket | Weekly + ad hoc | Returns Experience Product Manager |
| Operations site leaders | Processing, grading and disposition KPIs | Dashboard (Tableau/QuickSight) | Daily view, weekly summary | Returns Operations Manager |
| Finance partner | Recovery $ and cost per return | Monthly business review | Monthly | Data Analyst |

## 3. Message templates

**KPI miss (owner to WBR):** "[KPI] was [actual] vs [target] ([variance]). Driver: [segment/cause]. Action: [countermeasure], owner [role], date-to-green [date]."

**Blocker (program manager to dependency owner):** "[Milestone] is blocked by [predecessor] ([team], forecast [date]). Impact: [downstream milestone / KPI]. Ask: firm date or interim workaround by [date]."

**Example from week of {WEEK}:** "Refund cycle time was {x['refund_cycle_days_act']} vs {x['refund_cycle_days_tgt']} ({x['refund_cycle_days_var']}). Driver: US Mail-in transit up {float(x['d_top_driver_transit_change_days']):.2f} days after carrier linehaul consolidation. Ask: Transportation Manager to assign a mitigation owner for R05 and bring a carrier SLA plan to the next WBR."

## 4. Escalation path

| Level | Trigger | Who | Response time | Forum |
|---|---|---|---|---|
| L0 Team | Amber KPI or milestone slip <= 7 days | Initiative owner resolves within the team | Next WBR | Team stand-up |
| L1 Program | Red KPI 1 week, slip > 7 days, or any cross-team dependency at risk | ReCommerce Program Manager with both team leads | 2 business days | Dependency sync (30 min) |
| L2 Sponsor | Red KPI 2+ consecutive weeks, blocked dependency, slip > 21 days, or High risk without mitigation | Director, Returns Experience & ReCommerce | At the WBR, or within 1 business day if urgent | WBR escalations section |
| L3 Leadership | Customer-impacting incident, policy or abuse exposure, or a launch date at risk | Sponsor escalates to the VP-level business owner | Same day | Written 1-page escalation |

Current escalations (week of {WEEK}): {x['p1']} P1 gaps across {x['gap_teams']} teams, including {x['unmitigated']} High risks without mitigation ({x['unmitigated_ids']}) and M402, {x['m402_slip']} days late, blocking {x['blocked']} milestones.

## 5. Feedback loop

- After each WBR, the program manager sends decisions and action items within 24 hours (see `docs/meeting_notes_stakeholder_alignment.md` for the format).
- Quarterly survey of WBR readers: is the pre-read useful, what is missing, what can be cut.
"""


def meeting_notes(f, x):
    return f"""# Stakeholder Alignment Meeting Notes: Returns Program WBR

**Date:** 2026-11-03 (Tuesday) &nbsp; **Duration:** 45 min &nbsp; **Pre-read:** `reports/WBR_{WEEK}.pdf`

**Attendees (roles):** Director, Returns Experience & ReCommerce (chair); ReCommerce Program Manager; Data Analyst, Returns Analytics (notes); Reverse Logistics Program Manager; Transportation Manager; Returns Experience Product Manager; Software Development Manager; Returns Operations Manager; Disposition Program Manager; Risk & Abuse Prevention Manager; Finance partner.

> These notes are a sample written for this portfolio project. Numbers come from the synthetic-data WBR for the week of {WEEK}.

## 1. Headline review

- {x['n_green']} of 8 KPIs met target; {x['n_amber']} Amber; {x['n_red']} Red (refund cycle time {x['refund_cycle_days_act']} vs {x['refund_cycle_days_tgt']}; contacts per return {x['contacts_per_return_act']} vs {x['contacts_per_return_tgt']}).
- Data Analyst walked through the driver chart: US Mail-in accounts for {float(x['d_top_driver_effect_days']):+.2f} days of the {float(x['d_program_change_days']):+.2f}-day change; the increase is transit ({float(x['d_top_driver_transit_change_days']):+.2f} days), not returns-center processing ({float(x['d_top_driver_processing_change_days']):+.2f} days). The control chart first flagged it in the week of {x['d_first_week_above_ucl']}.
- Customer impact estimate: about {x['d_excess']} extra contacts this week, {x['d_cost_week']} at the $4.50 planning rate (finance to confirm the rate).
- Bright spots: recovery rate {x['recovery_rate_act']} ({x['recovery_rate_yoy']} YoY) and waste units {x['waste_units_act']} ({x['waste_units_yoy']} YoY) after liquidation partner onboarding.

## 2. Discussion

- Transportation Manager confirmed the carrier consolidated two linehaul lanes in late September. The carrier SLA review (M305) is At Risk; R05 had no mitigation owner.
- Reverse Logistics PgM noted the structural fix is drop-off Wave 2 (M304), which is blocked by the QR label API (M402).
- SDM: M402 slipped {x['m402_slip']} days because engineering capacity is shared with the peak code freeze (R07). Forecast {x['m402_fc']} holds only if two engineers are added.
- Risk & Abuse Prevention Manager supported a refund-at-first-scan pilot for US Mail-in only for customers below the abuse-score threshold, using the returnless-refund guardrails (M201/M202).
- Finance asked that the recovery-rate definition stay on refund value (open question 2 in the BRD); agreed for now.

## 3. Decisions

1. D1. Escalate R05 to L2. Transportation Manager owns the mitigation; the carrier SLA plan is due at the next WBR.
2. D2. Approve a 4-week refund-at-first-scan pilot for low-risk US Mail-in returns. Modelled program cycle time if fully applied: {float(x['d_cycle_days_if_us_mailin_refund_at_scan']):.2f} days vs {float(x['d_refund_cycle_days_current']):.2f} today (notebook section 5). Risk & Abuse sets the eligibility rule.
3. D3. Add two engineers to M402 for 4 weeks; descope phase-2 reason fields (R07 mitigation). M402 stays the top program risk.
4. D4. Keep the refund-cycle target at {x['refund_cycle_days_tgt']}; no re-baseline. Restoring US Mail-in transit alone would bring the program to {float(x['d_cycle_days_if_us_mailin_restored']):.2f} days, so the pilot is needed to get back to Green.
5. D5. Add a segment-level control-chart alert (marketplace x channel) to the WBR pipeline.

## 4. Action items

| # | Action | Owner (role) | Due | Status |
|---|---|---|---|---|
| A1 | Assign mitigation and present carrier SLA plan for R05 | Transportation Manager | 2026-11-10 | Open |
| A2 | Define pilot eligibility rule and abuse guardrail for refund-at-first-scan | Risk & Abuse Prevention Manager | 2026-11-06 | Open |
| A3 | Launch pilot in US Mail-in; report weekly cycle time and abuse rate | Returns Policy Manager | 2026-11-13 | Open |
| A4 | Staff two engineers on M402; confirm firm date | Software Development Manager | 2026-11-06 | Open |
| A5 | Interim workaround for Wave 2 labels (pre-printed labels at partner sites) | Reverse Logistics Program Manager | 2026-11-10 | Open |
| A6 | Add segment control-chart alert to `run_wbr.py` and the dashboard | Data Analyst | 2026-11-10 | Open |
| A7 | Confirm cost-per-contact rate for impact sizing | Finance partner | 2026-11-10 | Open |
| A8 | Recover grading staffing at 4 scale sites (R01) | Returns Operations Manager | 2026-11-13 | Open |

## 5. Next WBR

2026-11-10. Pre-read published Monday 08:00 by the scheduled pipeline run for week 2026-11-02.
"""


def readme(f, x):
    return f"""# Returns Program Health and Automated Weekly Business Review

Every week a returns program like this one has the same three questions on the table: are the KPIs on target, are the five initiatives that should move them on schedule, and who owes what before next week. The usual answer is a day of copy-paste across four spreadsheets. I built a pipeline that answers all three from one command and writes the Excel WBR, a 3-page PDF pre-read and a BI extract from the same SQL.

Built with SQLite SQL (CTEs and window functions, written to port to Redshift/Postgres), Python (pandas, openpyxl, reportlab, matplotlib, statsmodels), formula-driven Excel, a Tableau/QuickSight extract and a Jupyter notebook.

![Dashboard preview](screenshots/dashboard.png)

*Preview drawn with matplotlib from `dashboard/*.csv`, using the layout in `dashboard/dashboard_spec.md`.*

## What the week of {WEEK} to {x['week_end']} shows

- Refund cycle time is Red at {x['refund_cycle_days_act']} against a {x['refund_cycle_days_tgt']} target ({x['refund_cycle_days_var']}), and it has missed {x['refund_cycle_days_miss4']} of the last 4 weeks. One segment explains it. US Mail-in ({x['d_share_pct']} of returns) adds {float(x['d_top_driver_effect_days']):+.2f} days, which is more than the whole {float(x['d_program_change_days']):+.2f}-day program change. Its cycle time went from {float(x['d_top_driver_days_base']):.2f} to {float(x['d_top_driver_days_cur']):.2f} days, and the extra time is carrier transit ({float(x['d_top_driver_transit_change_days']):+.2f} days), not returns-center processing ({float(x['d_top_driver_processing_change_days']):+.2f} days).
- Slow refunds show up as customer contacts. Contacts per return is Red at {x['contacts_per_return_act']} vs {x['contacts_per_return_tgt']}. Over 78 weeks, each extra day of refund cycle adds {float(x['d_contacts_per_day_slope']):.4f} contacts per return (OLS, R-squared {float(x['d_ols_r2']):.2f}). That works out to about {x['d_excess']} excess contacts this week, or {x['d_cost_week']} a week and {x['d_cost_year']} a year at an assumed $4.50 per contact.
- ReCommerce and disposition look good. Recovery rate is {x['recovery_rate_act']} vs a {x['recovery_rate_tgt']} target ({x['recovery_rate_yoy']} YoY, Electronics {x['elec_recovery_yoy']}), and landfill waste is down to {x['waste_units_act']} units from {x['waste_units_ly']} in the same week last year ({x['waste_units_yoy']}).
- On the program side, {x['n_init_red']} of 5 initiatives are Red ({x['red_inits']}). {x['at_risk']} milestones are at risk and {x['blocked']} are blocked, all by the same thing: the QR label API (M402), now {x['m402_slip']} days late. It also holds up drop-off Wave 2, which is the long-term fix for mail-in transit. {x['unmitigated']} High risks ({x['unmitigated_ids']}) have nobody assigned to mitigate them.
- The run produces the Excel WBR, the PDF with a headline written from the numbers, and a gap list of {x['p1']} P1 and {x['p2']} P2 asks routed to {x['gap_teams']} teams.

## What I'd recommend

1. Escalate the carrier issue (R05) and fix the cause. Getting US Mail-in transit back to its pre-incident level takes program refund cycle time from {float(x['d_refund_cycle_days_current']):.2f} to {float(x['d_cycle_days_if_us_mailin_restored']):.2f} days (-{float(x['d_top_driver_effect_days']):.2f} days). The catch is that this still leaves it just above the {x['refund_cycle_days_tgt']} target.
2. While the carrier fix lands, pilot refund-at-first-carrier-scan for low-risk US Mail-in customers. The model puts program cycle time at {float(x['d_cycle_days_if_us_mailin_refund_at_scan']):.2f} days (Green), and it should remove most of the ~{x['d_excess']} cycle-driven excess contacts a week ({x['d_cost_year']} a year at the assumed rate). It needs an abuse guardrail from the Risk partner, and the returnless-refund rules are a good starting point.
3. Unblock M402 (more engineering capacity, push the phase-2 fields out) so drop-off Wave 2 can launch and pull volume out of mail-in.

## How I worked through it

I loosely followed DMAIC. The BRD (`docs/BRD_Returns_Program_Health_Dashboard.md`) sets out stakeholders, user stories, 13 testable functional requirements and a metric dictionary. For data I generated 18 months of seeded daily records with some dirty rows on purpose, then cleaned them by rule in `src/build_db.py` and logged every fix. The weekly KPI layer (`sql/00-03`) gives WoW, YoY, trailing-4-week average and RAG against target.

For the analysis, `sql/04` ranks category movers and `sql/05` splits the cycle-time change by marketplace x channel into exact rate and mix effects. The notebook (`notebooks/analysis.ipynb`) adds a control chart and the contacts regression. Program health (`sql/06-09`) covers schedule variance, dependency blockers and risk severity, and `sql/10` turns all of it into a gap list with an owner, ask and due date. The control piece is the weekly refresh itself (`src/run_wbr.py`, `src/schedule/`), the weeks-missed-of-last-4 column, and the escalation plan in `docs/`.

## What's in the repo

| Piece | Where |
|---|---|
| SQL for the KPIs and program health | `sql/01-10`: WoW/YoY/T4W, KPI vs target RAG, top movers, rate/mix driver split, schedule variance, blocked dependencies, risk severity, gap list |
| Excel WBR | `excel/Returns_WBR_{WEEK}.xlsx`: summary built on INDEX/MATCH and AVERAGEIFS, editable week/target/amber-band inputs, RAG conditional formatting, 10 native charts |
| Program tracker | `excel/Program_Tracker.xlsx`: XLOOKUP owner lookup, COUNTIFS/AVERAGEIFS/MAXIFS status summary, a Gantt drawn with conditional formatting, stacked bar chart |
| Program plan | `docs/Program_Plan_RACI_Risks.md`: RACI, 28 milestones, risk register, dependencies, DMAIC notes |
| BRD | `docs/BRD_Returns_Program_Health_Dashboard.md` / `.docx` |
| Communication and escalation | `docs/Stakeholder_Communication_Plan.md` (cadence, message templates, L0 to L3 escalation), `docs/meeting_notes_stakeholder_alignment.md` (decisions, action items) |
| Weekly automation | `src/run_wbr.py --week`, `reports/WBR_{WEEK}.pdf`, `src/schedule/` (Task Scheduler and cron) |
| BI dashboard | `dashboard/tableau_extract.csv` and `dashboard/dashboard_spec.md` (calculated fields, layout, Tableau/QuickSight refresh) |
| Driver analysis | `notebooks/analysis.ipynb`: control chart, rate/mix split, contacts regression, sized options |
| Plain-language headline | `src/narrative.py`, which writes page 1 of the PDF (`screenshots/wbr_pdf_page1.png`) |

## Screenshots

| | |
|---|---|
| ![WBR PDF page 1](screenshots/wbr_pdf_page1.png) | ![KPI trends](screenshots/kpi_trends.png) |
| ![Refund cycle driver](screenshots/refund_cycle_driver.png) | ![Milestone timeline](screenshots/milestone_timeline.png) |

`screenshots/wbr_pdf_page1.png` is page 1 of the generated PDF, rasterized with pypdfium2. `screenshots/top_movers_category.png` has the YoY change by category.

## Repository structure

```
Returns-Program-Health-Automated-Reporting/
  data/raw/            synthetic daily returns + shipments, KPI targets, initiatives, milestones, risks, issues
  data/processed/      query outputs per WBR week, data-quality log, driver analysis summary
  sql/                 00_create_views ... 11_tableau_extract (numbered, each with a header comment)
  src/                 generate_data, build_db, run_sql, run_wbr, narrative, wbr_excel, wbr_pdf, charts,
                       make_tracker_excel, make_dashboard, make_notebook, make_docs, run_all; schedule/
  notebooks/           analysis.ipynb (executed)
  excel/               Returns_WBR_{WEEK}.xlsx, Program_Tracker.xlsx
  reports/             WBR_{WEEK}.pdf, charts/
  dashboard/           tableau_extract.csv ({x['extract_rows']:,} rows), kpi_weekly_long.csv, program_health.csv, milestones.csv, dashboard_spec.md
  docs/                BRD (md+docx), program plan with RACI and risks (md+docx), communication plan, meeting notes, schedule note
  screenshots/         dashboard preview, PDF page 1, key charts
```

## How to run

```
python -m venv .venv && .venv\\Scripts\\activate      # or source .venv/bin/activate
pip install -r requirements.txt
python src/run_all.py                                 # rebuilds data, db, WBR, workbooks, dashboard, notebook, docs
python src/run_wbr.py --week 2026-10-19               # WBR for any other Monday in the data range
```

To schedule the weekly refresh, use `src/schedule/register_wbr_task.ps1` (Windows Task Scheduler) or `src/schedule/crontab.example` (cron). `docs/schedule_refresh.md` has the details.

The SQL is SQLite. The date functions (`date(x,'weekday 0','-6 days')`, `julianday`) become `DATE_TRUNC('week', x)` and `DATEDIFF` in Redshift, and `GROUP_CONCAT` becomes `LISTAGG`. The rest is plain ANSI.

**Data note:** All data is synthetic (made by `src/generate_data.py` with a fixed seed). None of it comes from Amazon or any employer. I shaped it to look like e-commerce returns, with holiday seasonality, a post-holiday return peak, channel-mix shifts and a carrier-transit incident added on purpose. The roles in the docs are generic role titles and the meeting notes are a made-up sample.
"""


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    f = load()
    x = facts(f)
    docs = {
        "BRD_Returns_Program_Health_Dashboard": (brd(f, x), True),
        "Program_Plan_RACI_Risks": (program_plan(f, x), True),
        "Stakeholder_Communication_Plan": (comm_plan(f, x), False),
        "meeting_notes_stakeholder_alignment": (meeting_notes(f, x), False),
    }
    for name, (text, as_docx) in docs.items():
        (DOCS / f"{name}.md").write_text(text, encoding="utf-8")
        if as_docx:
            convert(text, DOCS / f"{name}.docx", title=name.replace("_", " "))
    (ROOT / "README.md").write_text(readme(f, x), encoding="utf-8")
    print(f"make_docs: {len(docs)} docs (+2 docx) and README.md written")


if __name__ == "__main__":
    main()
