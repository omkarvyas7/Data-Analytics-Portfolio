-- 10_cohort_view.sql
-- Cohorts by account signup period. Do newer accounts behave differently
-- from older ones on return rate, loss per order and High-tier share?
-- Output: signup cohort x period (scoring / performance) with customers,
-- orders, return rate, loss $ per 1,000 orders and % High tier.
WITH cohort AS (
    SELECT customer_id,
           CASE WHEN signup_date < '2022-01-01' THEN '1. before 2022'
                WHEN signup_date < '2023-01-01' THEN '2. 2022'
                WHEN signup_date < '2024-01-01' THEN '3. 2023'
                WHEN signup_date < '2024-07-01' THEN '4. 2024 H1'
                WHEN signup_date < '2025-01-01' THEN '5. 2024 H2'
                WHEN signup_date < '2025-07-01' THEN '6. 2025 H1'
                ELSE '7. 2025 H2' END AS signup_cohort
    FROM customers
),
o AS (
    SELECT c.signup_cohort,
           CASE WHEN o.order_date < (SELECT scoring_cutoff FROM params) THEN 'scoring' ELSE 'performance' END AS period,
           COUNT(*) AS orders
    FROM clean_orders o JOIN cohort c ON c.customer_id = o.customer_id
    GROUP BY 1, 2
),
r AS (
    SELECT c.signup_cohort,
           CASE WHEN rf.order_date < (SELECT scoring_cutoff FROM params) THEN 'scoring' ELSE 'performance' END AS period,
           SUM(CASE WHEN rf.is_inr = 0 THEN 1 ELSE 0 END) AS returns,
           SUM(rf.loss_amt) AS loss_dollars
    FROM return_facts rf JOIN cohort c ON c.customer_id = rf.customer_id
    GROUP BY 1, 2
),
t AS (
    SELECT c.signup_cohort, COUNT(*) AS customers,
           ROUND(100.0 * SUM(CASE WHEN k.risk_tier = 'High' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_high_tier
    FROM cohort c JOIN customer_risk k ON k.customer_id = c.customer_id
    GROUP BY 1
)
SELECT o.signup_cohort, o.period, t.customers, o.orders,
       ROUND(100.0 * COALESCE(r.returns, 0) / o.orders, 2) AS return_rate_pct,
       ROUND(1000.0 * COALESCE(r.loss_dollars, 0) / o.orders, 2) AS loss_dollars_per_1k_orders,
       t.pct_high_tier
FROM o
JOIN t ON t.signup_cohort = o.signup_cohort
LEFT JOIN r ON r.signup_cohort = o.signup_cohort AND r.period = o.period
ORDER BY o.signup_cohort, CASE o.period WHEN 'scoring' THEN 1 ELSE 2 END;
