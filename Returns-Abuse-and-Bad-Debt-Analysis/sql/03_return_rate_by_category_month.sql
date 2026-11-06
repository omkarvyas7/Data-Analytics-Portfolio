-- 03_return_rate_by_category_month.sql
-- Program health: return rate by order month and category. Shows where
-- returns pile up (category mix, the Q4 peak, January).
-- Return rate = non-INR returns / orders, credited to the order month.
-- Output: order_month x category with orders, physical returns, INR claims,
-- return rate, refund $ and loss $.
WITH o AS (
    SELECT substr(order_date, 1, 7) AS order_month, category,
           COUNT(*) AS orders, SUM(item_price) AS order_dollars
    FROM clean_orders
    GROUP BY 1, 2
),
r AS (
    SELECT order_month, category,
           SUM(CASE WHEN is_inr = 0 THEN 1 ELSE 0 END) AS returns,
           SUM(is_inr) AS inr_claims,
           SUM(refund_amount) AS refund_dollars,
           SUM(loss_amt) AS loss_dollars
    FROM return_facts
    GROUP BY 1, 2
)
SELECT o.order_month, o.category, o.orders,
       ROUND(o.order_dollars, 2) AS order_dollars,
       COALESCE(r.returns, 0) AS returns,
       COALESCE(r.inr_claims, 0) AS inr_claims,
       ROUND(1.0 * COALESCE(r.returns, 0) / o.orders, 4) AS return_rate,
       ROUND(COALESCE(r.refund_dollars, 0), 2) AS refund_dollars,
       ROUND(COALESCE(r.loss_dollars, 0), 2) AS loss_dollars
FROM o
LEFT JOIN r ON r.order_month = o.order_month AND r.category = o.category
ORDER BY o.order_month, o.category;
