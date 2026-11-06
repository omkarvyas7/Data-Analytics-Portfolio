# Dashboard Spec: Returns Risk & Bad Debt Dashboard

Built for Tableau Public (QuickSight works too). The data source is `dashboard/tableau_extract.csv`, one row per return or INR claim over 24 months. `screenshots/dashboard.png` is a matplotlib mock of the layout below, not a Tableau screenshot.

## Audience and purpose
For the Returns Operations, Finance and ReCommerce leads. It should tell them whether the returns program is healthy, where money is leaking (bad debt and abuse), which customers drive it, and what a policy change would save.

## Data source fields
| Field | Type | Notes |
|---|---|---|
| return_id, order_id, customer_id | string | keys |
| region, is_member, payment_type | dimension | customer attributes |
| order_date, order_month, return_request_date, request_month | date / string | time axes |
| period | dimension | scoring (before 2025-07-01) or performance |
| category, reason_code, return_method | dimension | |
| is_inr, refund_issued, instant_refund_flag | 0/1 | |
| item_price, refund_amount, recovery_value, loss_amt | measure ($) | |
| refund_issued_date, return_received_date, condition_grade | | grading |
| days_request_to_refund | measure (days) | |
| bad_debt_flag, fraud_return_flag, condition_mismatch_flag | 0/1 | definitions in sql/02 |
| prior_returns_90d | measure | repeat-returner rule |
| risk_score, risk_tier, address_inr_cluster | customer risk | from sql/08 |
| good_customer_perf | 0/1 | active Jul-Dec 2025 with no loss event |

Order counts (the return-rate denominator) come from `data/processed/03_return_rate_by_category_month.csv`. Blend it in as a second source on order_month + category, or load the orders table directly.

## Calculated fields (Tableau syntax)
- `Physical Returns` = `SUM(IF [is_inr] = 0 THEN 1 ELSE 0 END)`
- `Return Rate` = `[Physical Returns] / SUM([orders])` (blended source)
- `Bad Debt $` = `SUM(IF [bad_debt_flag] = 1 THEN [refund_amount] END)`
- `Bad Debt %` = `[Bad Debt $] / SUM(IF [refund_issued] = 1 AND [is_inr] = 0 THEN [refund_amount] END)`
- `Loss $` = `SUM([loss_amt])`
- `Mismatch Rate` = `SUM([condition_mismatch_flag]) / COUNT(IF NOT ISNULL([condition_grade]) THEN 1 END)`
- `Avoidable If Receipt First` = `IF [bad_debt_flag] = 1 OR [fraud_return_flag] = 1 THEN [refund_amount] ELSE 0 END`
- Parameters: `p_HighCutoff` (int, default 4), `p_MedCutoff` (int, 2), `p_Threshold` ($, 200), `p_FeeRate` (0.15), `p_RepeatK` (3), `p_InrDeny` (0.70)
- `Live Tier` = `IF [risk_score] >= [p_HighCutoff] THEN "High" ELSEIF [risk_score] >= [p_MedCutoff] THEN "Medium" ELSE "Low" END`
- `Saved S1` = `SUM(IF [Live Tier] = "High" AND [instant_refund_flag] = 1 AND [period] = "performance" THEN [Avoidable If Receipt First] END)`
- `Good Customers Affected S1` = `COUNTD(IF [Live Tier] = "High" AND [instant_refund_flag] = 1 AND [good_customer_perf] = 1 AND [period] = "performance" THEN [customer_id] END)`

## Sheets
1. KPI band: Return rate, Bad debt $ and %, High-tier share of loss $, High vs Low loss-event lift, Recommended package savings.
2. Return rate trend: dual axis, order volume bars and return-rate line by order month. Color by category on drill-down.
3. Bad debt by month: stacked bars by refund type (instant vs standard).
4. Risk tier mix: % of customers vs % of loss $ per tier.
5. Top abuse patterns: horizontal bars of estimated loss $ with customer counts (from sql/12).
6. Policy what-if: scenario bars of $ saved, colored by % of good customers affected (green <= 2%, amber <= 5%, red > 5%), driven by the parameters.
7. Customer lookup (restricted): score, tier and rule points for one customer.
8. Data-quality panel: row counts flagged by sql/01.

## Filters
Region, category, member flag, payment type, refund type, risk tier and request month range. They apply across sheets 1-6.

## Refresh cadence
The extract is rebuilt daily at 06:00 local with `python src/run_all.py` (or whatever the production pipeline runs), and the dashboard picks it up at 07:00. Risk tiers are re-scored monthly. Returns Analytics owns the dashboard, and the data engineer maintains the refresh job.

## Access
Aggregate sheets are open to everyone on the returns side. Customer lookup is limited to Risk and Abuse Investigators and Returns Operations.
