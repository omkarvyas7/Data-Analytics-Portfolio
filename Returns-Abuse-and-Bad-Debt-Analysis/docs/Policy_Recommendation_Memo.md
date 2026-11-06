# Policy Recommendation Memo: Reducing Refund Abuse and Bad Debt

To: Returns Operations Manager, Finance partner, Customer Experience lead | From: Returns Analytics | Data: synthetic, Jan 2024 to Dec 2025

## Recommendation
We recommend a targeted package instead of a blanket change. It has three parts. High-risk customers move from instant refund to refund-on-receipt. Repeat returners pay a 15% restocking fee on "no longer needed" returns. Item-not-received claims from flagged multi-account addresses go to investigation before they are paid. Replayed on July to December 2025, the package would have saved **$23,453 (15.2% of loss dollars)** and affected **206 good customers (1.18%)**. Ending instant refunds for everyone saves more ($37,629), but it slows refunds for 23.5% of good customers. We don't think that trade is worth making.

## What is driving the losses
- Most bad debt sits on instant refunds. $80,032 was refunded on items that never came back (2.77% of refund dollars), and 73% of it was instant. Instant refunds pay out in 0.5 days on average against 10.9 days for standard refunds, so the money is out for about 8 days before the item arrives.
- Losses are concentrated in a small group. High-tier customers are 2.7% of active customers and 31.3% of loss dollars. In the test period 59.1% of them had a loss event, compared with 6.3% in the Low tier (9.4x, statistically significant).
- The three largest patterns over 24 months were Serial returners (resale value lost) at $182,119, Wardrobing (used high-value item, fast return) at $90,984, and Refund issued, item never received (bad debt) at $80,032. Serial returning is mainly a cost-to-serve problem, so the package handles it with a restocking fee instead of blocking those customers.
- The stated reason is a weak guide to condition. 12.8% of graded "no longer needed" returns came back used, damaged, empty or wrong, compared with 1.5% for "defective".
- Newer accounts cost more. Accounts opened since 2024 lose $3,009 per 1,000 orders, against $1,391 for accounts opened before 2022.

## Options considered
| Scenario | $ saved (Jul-Dec 2025) | % of loss $ | Good customers affected | % of good customers |
|---|---|---|---|---|
| S1 Disable instant refund for High tier | $10,493 | 6.8% | 120 | 0.69% |
| S2 Receipt-before-refund over $X, all customers | $16,770 | 10.8% | 267 | 1.53% |
| S3 Receipt-before-refund over $X, Medium + High tier | $7,585 | 4.9% | 42 | 0.24% |
| S4 Disable instant refund for everyone | $37,629 | 24.3% | 4,111 | 23.53% |
| S5 Restocking fee on no-longer-needed, repeat returners | $7,109 | 4.6% | 128 | 0.73% |
| S6 Investigate INR claims at cluster addresses | $5,851 | 3.8% | 0 | 0.00% |
| S7 Recommended package (S1 + S5 + S6) | $23,453 | 15.2% | 206 | 1.18% |

## How the risk tier works
Customers earn points for behavior we can see in the prior 18 months: a 90-day return rate of 50% or more, a high share of order dollars returned, condition mismatches, INR claims, refunds where the item never arrived, an address shared with clustered INR claims, and a new account. High is 4+ points and Medium is 2-3. A logistic regression on the following six months shows each rule adds risk. The strongest are a clustered INR address (11.2x odds), a condition mismatch (3.6x) and a high 90-day return rate (3.1x).

## Customer impact and safeguards
- Affected good customers still get a full refund. It arrives about 11 days later instead of the same day.
- Tiers are reviewed monthly. A customer with no loss event for six months goes back to Low.
- Every policy has an appeal path through customer service.

## Decision requested and next steps
1. Approve a 12-week pilot of the package in one region with a matched control region.
2. Finance to confirm the 30-day bad debt rule and the savings method.
3. Customer Experience to set the acceptable contact-rate increase (guardrail) before launch.

All figures come from a synthetic dataset built for this analysis, so treat the dollar values as illustrative. The method is the part that carries over to real data.
