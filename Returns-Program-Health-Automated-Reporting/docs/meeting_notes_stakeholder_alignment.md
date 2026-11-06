# Stakeholder Alignment Meeting Notes: Returns Program WBR

**Date:** 2026-11-03 (Tuesday) &nbsp; **Duration:** 45 min &nbsp; **Pre-read:** `reports/WBR_2026-10-26.pdf`

**Attendees (roles):** Director, Returns Experience & ReCommerce (chair); ReCommerce Program Manager; Data Analyst, Returns Analytics (notes); Reverse Logistics Program Manager; Transportation Manager; Returns Experience Product Manager; Software Development Manager; Returns Operations Manager; Disposition Program Manager; Risk & Abuse Prevention Manager; Finance partner.

> These notes are a sample written for this portfolio project. Numbers come from the synthetic-data WBR for the week of 2026-10-26.

## 1. Headline review

- 3 of 8 KPIs met target; 3 Amber; 2 Red (refund cycle time 3.77 days vs 3.30 days; contacts per return 0.192 vs 0.180).
- Data Analyst walked through the driver chart: US Mail-in accounts for +0.44 days of the +0.43-day change; the increase is transit (+2.22 days), not returns-center processing (-0.03 days). The control chart first flagged it in the week of 2026-10-12.
- Customer impact estimate: about 2,611 extra contacts this week, $11,749 at the $4.50 planning rate (finance to confirm the rate).
- Bright spots: recovery rate 38.6% (+11.8% YoY) and waste units 10,829 (-29.2% YoY) after liquidation partner onboarding.

## 2. Discussion

- Transportation Manager confirmed the carrier consolidated two linehaul lanes in late September. The carrier SLA review (M305) is At Risk; R05 had no mitigation owner.
- Reverse Logistics PgM noted the structural fix is drop-off Wave 2 (M304), which is blocked by the QR label API (M402).
- SDM: M402 slipped 63 days because engineering capacity is shared with the peak code freeze (R07). Forecast 2026-11-13 holds only if two engineers are added.
- Risk & Abuse Prevention Manager supported a refund-at-first-scan pilot for US Mail-in only for customers below the abuse-score threshold, using the returnless-refund guardrails (M201/M202).
- Finance asked that the recovery-rate definition stay on refund value (open question 2 in the BRD); agreed for now.

## 3. Decisions

1. D1. Escalate R05 to L2. Transportation Manager owns the mitigation; the carrier SLA plan is due at the next WBR.
2. D2. Approve a 4-week refund-at-first-scan pilot for low-risk US Mail-in returns. Modelled program cycle time if fully applied: 2.55 days vs 3.77 today (notebook section 5). Risk & Abuse sets the eligibility rule.
3. D3. Add two engineers to M402 for 4 weeks; descope phase-2 reason fields (R07 mitigation). M402 stays the top program risk.
4. D4. Keep the refund-cycle target at 3.30 days; no re-baseline. Restoring US Mail-in transit alone would bring the program to 3.33 days, so the pilot is needed to get back to Green.
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
