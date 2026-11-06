# Business Requirements Document: Returns Risk & Bad Debt Dashboard

Version 1.0 | Owner: Returns Analytics (Data Analyst) | Status: Draft for review

## 1. Background
Most members get instant refunds, meaning the refund is issued before the item arrives back. It keeps returns fast for the customer. Over 24 months of synthetic program data, customers returned 38,696 of 251,075 orders (15.4%) and filed 1,063 item-not-received (INR) claims. Refunds where the item never came back within 30 days add up to $80,032 (2.77% of refund dollars), and 73% of that is on instant refunds. There is no shared view today that ties return behavior and refund type to loss, so policy discussions run on anecdotes.

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
| FR-3 | Show bad debt $ and % of refund $ by refund month and refund type, using the 30-day rule. | TOTAL row equals $80,032 on the current extract, with the rule documented on the sheet. |
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
| Bad debt $ | sum of refunds (non-INR) with no item received within 30 days of refund | refund month | return_facts | Finance |
| Bad debt % | bad debt $ / refund $ judged | refund month | return_facts | Finance |
| Condition mismatch rate | graded returns whose condition is worse than the stated reason allows / graded returns | reason code | return_facts | ReCommerce |
| Recovery rate | resale recovery value / item price of graded returns | condition | return_facts | ReCommerce |
| Loss $ | bad debt + empty-box / wrong-item refunds + INR refunds + (refund - recovery) on other mismatches | return | return_facts | Finance |
| Risk score / tier | sum of rule points, High >= 4, Medium >= 2 | customer | customer_risk | Returns Analytics |
| Good customer | active in window with no loss event | customer | customer_outcomes | Returns Analytics |
| Good customers affected | distinct good customers touched by a policy / all good customers | scenario | sql/11 | Customer Experience |

## 7. Data requirements
- Sources: customers, orders, returns, refunds, carrier scans (daily snapshots). Keys: customer_id, order_id, return_id, refund_id.
- History: at least 24 months, so two Q4 peaks are covered. Features use an 18-month scoring window and a 6-month performance window.
- Quality rules (sql/01): drop exact duplicates, exclude non-positive prices, map null reason codes to "unknown", exclude orphan returns.
- Extract: dashboard/tableau_extract.csv, one row per return, refreshed daily.

## 8. Assumptions
- Receipt-before-refund prevents the full refund only when the item never arrives or arrives empty / wrong.
- 70% of INR claims from flagged cluster addresses are denied after investigation.
- Restocking fee of 15% applies only to "no longer needed" returns by customers with 3+ returns in the prior 90 days.
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
4. Is the 30-day bad debt rule aligned with Finance write-off timing?

## 11. Timeline and milestones
| Milestone | Target | Exit criteria |
|---|---|---|
| Requirements sign-off | Week 1 | BRD approved by Returns Operations Manager and Finance partner |
| Data pipeline and extract | Week 2-3 | Daily extract passes DQ checks |
| Dashboard v1 (FR-1 to FR-5) | Week 4 | Stakeholder walkthrough, numbers reconciled to SQL |
| Policy what-if (FR-6, FR-8) | Week 5 | Finance validates savings logic |
| Pilot recommended policy | Week 6-13 | One-region pilot with control group |
| Readout and scale decision | Week 14 | Pilot results versus G4 |
