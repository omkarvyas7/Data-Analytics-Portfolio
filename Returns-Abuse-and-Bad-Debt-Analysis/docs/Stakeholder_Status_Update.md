# Weekly Status: Returns Risk & Bad Debt Dashboard

Subject: [Status] Returns Risk & Bad Debt Dashboard, week 4 | Overall: GREEN

Hi team,

Quick update on the returns risk and bad debt work.

## Summary
Dashboard v1 and the policy what-if model are done, and both reconcile to the SQL outputs. In the July to December 2025 replay, the recommended package would have saved $23,453 (15.2% of loss dollars) and affected 1.18% of good customers. We'd like a pilot decision next week.

## Done this week
- Wrote 12 SQL queries: data quality, return rate, cycle time, bad debt, risk features, risk tiers, cohorts and the policy simulation.
- Checked the risk tiers on held-out months. High tier had a 59.1% loss-event rate against 6.3% for Low (chi-square p < 0.001).
- Shared the Excel what-if model (excel/Returns_Risk_Model.xlsx) so Finance can change thresholds and see the savings move.
- Cleaned 556 flagged raw records (duplicates, null reasons, negative prices) across 12 checks.

## Numbers
| Metric | Value |
|---|---|
| Return rate (24 months) | 15.4% |
| Bad debt $ / % of refund $ | $80,032 / 2.77% |
| Share of bad debt on instant refunds | 73% |
| High tier: share of customers / share of loss $ | 2.7% / 31.3% |
| Recommended package savings (6-month replay) | $23,453 |

## Next week
- Walk Finance through the savings method and the 30-day bad debt rule (Finance partner).
- Agree on the customer-contact guardrail for the pilot (Customer Experience lead).
- Scope the daily refresh job with the data engineer.

## Risks and asks
- Decision needed by next Friday: pilot region and start date (Returns Operations Manager).
- Risk: abusers may move to new accounts. Monthly re-scoring and the new-account rule cover this.

Thanks,
Returns Analytics
