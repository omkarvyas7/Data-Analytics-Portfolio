-- 11_policy_simulation.sql
-- Replay Jul to Dec 2025 under each candidate policy and compare dollars
-- saved with good customers affected (the false-positive cost).
-- Assumptions (params table, same values as src/config.py and the Excel
-- what-if):
--   * Receipt-before-refund saves the full refund when the item never
--     arrives (bad debt) or arrives empty or wrong (graded before refund).
--   * Restocking fee = restock_fee_rate x refund, on 'no_longer_needed'
--     returns by customers with >= repeat_returns_90d returns in the prior
--     90 days.
--   * INR claims from flagged cluster addresses go to investigation, and
--     inr_deny_rate of their value is not refunded.
--   * Good customer = active in the performance window with no loss event.
-- Output: one row per scenario with refunds affected, customers affected,
-- good customers affected (count and % of all good customers), $ saved,
-- % of performance-window loss $, and $ saved per good customer hit.
WITH p AS (SELECT * FROM params),
perf AS (
    SELECT rf.return_id, rf.customer_id, rf.reason_code, rf.is_inr, rf.refund_issued,
           rf.refund_amount, rf.instant_refund_flag, rf.prior_returns_90d, rf.loss_amt,
           co.risk_tier, co.address_inr_cluster,
           CASE WHEN co.perf_active = 1 AND co.perf_loss_event = 0 THEN 1 ELSE 0 END AS good_customer,
           CASE WHEN rf.bad_debt_flag = 1 OR rf.fraud_return_flag = 1 THEN rf.refund_amount ELSE 0 END AS avoidable_if_receipt_first
    FROM return_facts rf
    JOIN customer_outcomes co ON co.customer_id = rf.customer_id
    WHERE rf.period = 'performance'
),
flags AS (
    SELECT perf.*,
           (instant_refund_flag = 1 AND risk_tier = 'High') AS a1,
           (instant_refund_flag = 1 AND refund_amount >= p.high_value_threshold) AS a2,
           (instant_refund_flag = 1 AND refund_amount >= p.high_value_threshold AND risk_tier IN ('High', 'Medium')) AS a3,
           (instant_refund_flag = 1) AS a4,
           (reason_code = 'no_longer_needed' AND prior_returns_90d >= p.repeat_returns_90d AND refund_issued = 1
                AND avoidable_if_receipt_first = 0) AS a5,
           (is_inr = 1 AND address_inr_cluster = 1 AND refund_issued = 1) AS a6,
           p.restock_fee_rate, p.inr_deny_rate
    FROM perf CROSS JOIN p
),
scen(scenario_id, scenario) AS (
    VALUES (1, 'S1 Disable instant refund for High tier'),
           (2, 'S2 Receipt-before-refund over $X, all customers'),
           (3, 'S3 Receipt-before-refund over $X, Medium + High tier'),
           (4, 'S4 Disable instant refund for everyone'),
           (5, 'S5 Restocking fee on no-longer-needed, repeat returners'),
           (6, 'S6 Investigate INR claims at cluster addresses'),
           (7, 'S7 Recommended package (S1 + S5 + S6)')
),
sim AS (
    SELECT s.scenario_id, s.scenario, f.customer_id, f.good_customer,
           CASE s.scenario_id WHEN 1 THEN a1 WHEN 2 THEN a2 WHEN 3 THEN a3 WHEN 4 THEN a4
                              WHEN 5 THEN a5 WHEN 6 THEN a6
                              WHEN 7 THEN (a1 OR a5 OR a6) END AS applies,
           CASE s.scenario_id
                WHEN 1 THEN a1 * avoidable_if_receipt_first
                WHEN 2 THEN a2 * avoidable_if_receipt_first
                WHEN 3 THEN a3 * avoidable_if_receipt_first
                WHEN 4 THEN a4 * avoidable_if_receipt_first
                WHEN 5 THEN a5 * restock_fee_rate * refund_amount
                WHEN 6 THEN a6 * inr_deny_rate * refund_amount
                WHEN 7 THEN CASE WHEN a1 AND avoidable_if_receipt_first > 0 THEN avoidable_if_receipt_first
                                 WHEN a5 THEN restock_fee_rate * refund_amount
                                 WHEN a6 THEN inr_deny_rate * refund_amount
                                 ELSE 0 END
           END AS saved
    FROM flags f CROSS JOIN scen s
),
totals AS (
    SELECT (SELECT SUM(loss_amt) FROM perf) AS perf_loss_dollars,
           (SELECT SUM(CASE WHEN perf_active = 1 AND perf_loss_event = 0 THEN 1 ELSE 0 END) FROM customer_outcomes) AS good_customers_total
)
SELECT 0 AS scenario_id, 'S0 Baseline: current policy (loss $ in window)' AS scenario,
       0 AS refunds_affected, 0 AS customers_affected, 0 AS good_customers_affected,
       0.0 AS pct_good_customers_affected, 0.0 AS dollars_saved,
       ROUND((SELECT perf_loss_dollars FROM totals), 2) AS baseline_loss_dollars,
       0.0 AS pct_of_baseline_loss, NULL AS saved_per_good_customer_affected
UNION ALL
SELECT scenario_id, scenario,
       SUM(applies) AS refunds_affected,
       COUNT(DISTINCT CASE WHEN applies = 1 THEN customer_id END) AS customers_affected,
       COUNT(DISTINCT CASE WHEN applies = 1 AND good_customer = 1 THEN customer_id END) AS good_customers_affected,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN applies = 1 AND good_customer = 1 THEN customer_id END)
             / (SELECT good_customers_total FROM totals), 2) AS pct_good_customers_affected,
       ROUND(SUM(saved), 2) AS dollars_saved,
       ROUND((SELECT perf_loss_dollars FROM totals), 2) AS baseline_loss_dollars,
       ROUND(100.0 * SUM(saved) / (SELECT perf_loss_dollars FROM totals), 2) AS pct_of_baseline_loss,
       ROUND(SUM(saved) / NULLIF(COUNT(DISTINCT CASE WHEN applies = 1 AND good_customer = 1 THEN customer_id END), 0), 2)
           AS saved_per_good_customer_affected
FROM sim
GROUP BY scenario_id, scenario
ORDER BY scenario_id;
