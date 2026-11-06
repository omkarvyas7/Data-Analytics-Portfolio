-- 07_customer_risk_features.sql
-- Customer-level risk features, built only from the scoring window (before
-- params.scoring_cutoff = 2025-07-01) so the score can be tested on later
-- months without leakage. The point is to find return behaviors that
-- separate risky customers from good ones.
-- Features:
--   max_roll90_return_rate  highest 90-day rolling return rate (window
--                           function, RANGE over order day, needs >= 4 orders
--                           in the window)
--   return_dollar_share     returned item $ / ordered item $
--   inr_claims              item-not-received claims
--   graded_returns / condition_mismatches / mismatch_rate
--   never_received_refunds  refunds older than bad_debt_days with no item back
--   address_inr_cluster     address with >= 3 INR claims across >= 2 accounts
--   tenure_days             account age at the cutoff
-- Output: table customer_features. The final SELECT shows how common each
-- signal is.
DROP TABLE IF EXISTS customer_features;
CREATE TABLE customer_features AS
WITH p AS (SELECT * FROM params),
ord AS (
    SELECT o.customer_id, o.order_id, o.order_date, o.item_price,
           CASE WHEN EXISTS (SELECT 1 FROM return_facts rf
                              WHERE rf.order_id = o.order_id AND rf.is_inr = 0
                                AND rf.return_request_date < (SELECT scoring_cutoff FROM p))
                THEN 1 ELSE 0 END AS is_returned
    FROM clean_orders o
    WHERE o.order_date < (SELECT scoring_cutoff FROM p)
),
rolling AS (
    SELECT customer_id,
           COUNT(*) OVER w AS orders_90d,
           SUM(is_returned) OVER w AS returns_90d
    FROM ord
    WINDOW w AS (PARTITION BY customer_id ORDER BY julianday(order_date)
                 RANGE BETWEEN 89 PRECEDING AND CURRENT ROW)
),
roll_max AS (
    SELECT customer_id, MAX(1.0 * returns_90d / orders_90d) AS max_roll90_return_rate
    FROM rolling WHERE orders_90d >= 4
    GROUP BY customer_id
),
ord_agg AS (
    SELECT customer_id, COUNT(*) AS orders, SUM(item_price) AS order_dollars,
           SUM(is_returned) AS returned_orders,
           SUM(CASE WHEN is_returned = 1 THEN item_price ELSE 0 END) AS returned_dollars
    FROM ord GROUP BY customer_id
),
ret AS (
    SELECT rf.customer_id,
           SUM(rf.is_inr) AS inr_claims,
           SUM(CASE WHEN rf.return_received_date < p.scoring_cutoff THEN 1 ELSE 0 END) AS graded_returns,
           SUM(CASE WHEN rf.return_received_date < p.scoring_cutoff THEN rf.condition_mismatch_flag ELSE 0 END) AS condition_mismatches,
           SUM(CASE WHEN rf.refund_issued = 1 AND rf.is_inr = 0
                     AND julianday(p.scoring_cutoff) - julianday(rf.refund_issued_date) >= p.bad_debt_days
                     AND (rf.return_received_date IS NULL OR rf.return_received_date >= p.scoring_cutoff)
                    THEN 1 ELSE 0 END) AS never_received_refunds
    FROM return_facts rf CROSS JOIN p
    WHERE rf.return_request_date < p.scoring_cutoff
    GROUP BY rf.customer_id
),
addr AS (
    SELECT address_id
    FROM return_facts
    WHERE is_inr = 1 AND return_request_date < (SELECT scoring_cutoff FROM p)
    GROUP BY address_id
    HAVING COUNT(*) >= 3 AND COUNT(DISTINCT customer_id) >= 2
)
SELECT c.customer_id, c.region, c.is_member, c.payment_type, c.address_id, c.signup_date,
       CAST(julianday((SELECT scoring_cutoff FROM p)) - julianday(c.signup_date) AS INTEGER) AS tenure_days,
       COALESCE(oa.orders, 0) AS orders,
       ROUND(COALESCE(oa.order_dollars, 0), 2) AS order_dollars,
       COALESCE(oa.returned_orders, 0) AS returned_orders,
       ROUND(COALESCE(1.0 * oa.returned_orders / oa.orders, 0), 4) AS return_rate,
       ROUND(COALESCE(rm.max_roll90_return_rate, 0), 4) AS max_roll90_return_rate,
       ROUND(COALESCE(oa.returned_dollars / NULLIF(oa.order_dollars, 0), 0), 4) AS return_dollar_share,
       COALESCE(rt.inr_claims, 0) AS inr_claims,
       COALESCE(rt.graded_returns, 0) AS graded_returns,
       COALESCE(rt.condition_mismatches, 0) AS condition_mismatches,
       ROUND(COALESCE(1.0 * rt.condition_mismatches / NULLIF(rt.graded_returns, 0), 0), 4) AS mismatch_rate,
       COALESCE(rt.never_received_refunds, 0) AS never_received_refunds,
       CASE WHEN a.address_id IS NOT NULL THEN 1 ELSE 0 END AS address_inr_cluster
FROM customers c
LEFT JOIN ord_agg oa ON oa.customer_id = c.customer_id
LEFT JOIN roll_max rm ON rm.customer_id = c.customer_id
LEFT JOIN ret rt ON rt.customer_id = c.customer_id
LEFT JOIN addr a ON a.address_id = c.address_id;
CREATE INDEX ix_cfeat ON customer_features(customer_id);

SELECT 'customers with scoring-window orders' AS signal, COUNT(*) AS customers,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM customer_features), 2) AS pct_of_customers
FROM customer_features WHERE orders > 0
UNION ALL SELECT 'max 90-day return rate >= 50%', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM customer_features), 2)
FROM customer_features WHERE max_roll90_return_rate >= 0.5
UNION ALL SELECT 'return $ share >= 40%', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM customer_features), 2)
FROM customer_features WHERE return_dollar_share >= 0.4
UNION ALL SELECT '1+ INR claim', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM customer_features), 2)
FROM customer_features WHERE inr_claims >= 1
UNION ALL SELECT '1+ condition mismatch', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM customer_features), 2)
FROM customer_features WHERE condition_mismatches >= 1
UNION ALL SELECT '1+ never-received refund', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM customer_features), 2)
FROM customer_features WHERE never_received_refunds >= 1
UNION ALL SELECT 'address in INR cluster', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM customer_features), 2)
FROM customer_features WHERE address_inr_cluster = 1
UNION ALL SELECT 'account tenure < 180 days', COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM customer_features), 2)
FROM customer_features WHERE tenure_days < 180;
