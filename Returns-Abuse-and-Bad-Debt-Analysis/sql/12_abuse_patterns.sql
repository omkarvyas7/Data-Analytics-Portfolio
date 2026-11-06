-- 12_abuse_patterns.sql
-- Size the main abuse patterns over all 24 months, and check how
-- concentrated each one is.
--   Refund issued, item never received (bad debt)
--   Empty-box / wrong-item returned (refund paid)
--   Wardrobing: used apparel/shoes/electronics >= $100, reason
--               no_longer_needed / size_fit, requested <= 14 days after
--               delivery
--   INR claims at cluster addresses (>= 3 claims across >= 2 accounts)
--   INR claims at other addresses
--   Serial returners: >= 10 orders and >= 50% return rate (cost = resale
--               value lost on their returns)
-- Output: pattern, events, customers, refund $, estimated loss $, share of
-- loss. Patterns overlap (a serial returner can also wardrobe), so read the
-- shares as relative size, not something that adds up.
WITH addr AS (
    SELECT address_id FROM return_facts WHERE is_inr = 1
    GROUP BY address_id HAVING COUNT(*) >= 3 AND COUNT(DISTINCT customer_id) >= 2
),
serial AS (
    SELECT o.customer_id
    FROM clean_orders o
    LEFT JOIN (SELECT DISTINCT order_id FROM return_facts WHERE is_inr = 0) r ON r.order_id = o.order_id
    GROUP BY o.customer_id
    HAVING COUNT(*) >= 10 AND 1.0 * COUNT(r.order_id) / COUNT(*) >= 0.5
),
events AS (
    SELECT 'Refund issued, item never received (bad debt)' AS pattern, customer_id, refund_amount, refund_amount AS est_loss
    FROM return_facts WHERE bad_debt_flag = 1
    UNION ALL
    SELECT 'Empty-box / wrong-item returned', customer_id, refund_amount, refund_amount
    FROM return_facts WHERE fraud_return_flag = 1
    UNION ALL
    SELECT 'Wardrobing (used high-value item, fast return)', customer_id, refund_amount, refund_amount - recovery_value
    FROM return_facts
    WHERE condition_grade = 'used' AND refund_issued = 1 AND item_price >= 100
      AND category IN ('Apparel', 'Shoes', 'Electronics')
      AND reason_code IN ('no_longer_needed', 'size_fit') AND days_delivered_to_request <= 14
    UNION ALL
    SELECT 'INR claims at cluster addresses', customer_id, refund_amount, refund_amount
    FROM return_facts WHERE is_inr = 1 AND refund_issued = 1 AND address_id IN (SELECT address_id FROM addr)
    UNION ALL
    SELECT 'INR claims at other addresses', customer_id, refund_amount, refund_amount
    FROM return_facts WHERE is_inr = 1 AND refund_issued = 1 AND address_id NOT IN (SELECT address_id FROM addr)
    UNION ALL
    SELECT 'Serial returners (resale value lost)', customer_id, refund_amount,
           CASE WHEN condition_grade IS NOT NULL THEN refund_amount - recovery_value ELSE 0 END
    FROM return_facts
    WHERE customer_id IN (SELECT customer_id FROM serial) AND is_inr = 0 AND refund_issued = 1
      AND bad_debt_flag = 0 AND fraud_return_flag = 0
)
SELECT pattern,
       COUNT(*) AS events,
       COUNT(DISTINCT customer_id) AS customers,
       ROUND(100.0 * COUNT(DISTINCT customer_id) / (SELECT COUNT(*) FROM customers), 2) AS pct_of_customers,
       ROUND(SUM(refund_amount), 2) AS refund_dollars,
       ROUND(SUM(est_loss), 2) AS est_loss_dollars,
       ROUND(100.0 * SUM(est_loss) / SUM(SUM(est_loss)) OVER (), 2) AS pct_of_pattern_loss
FROM events
GROUP BY pattern
ORDER BY est_loss_dollars DESC;
