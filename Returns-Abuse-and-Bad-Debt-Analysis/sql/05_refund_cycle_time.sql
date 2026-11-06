-- 05_refund_cycle_time.sql
-- How fast refunds go out, instant vs standard, and how long an instant
-- refund waits for the item to show up. Faster for the customer, but it
-- opens an exposure window.
-- Output: refund type x quarter with refunds, mean / p50 / p90 days from
-- request to refund, mean days from refund to receipt, % never received.
WITH r AS (
    SELECT CASE WHEN instant_refund_flag = 1 THEN 'instant' ELSE 'standard' END AS refund_type,
           substr(return_request_date, 1, 4) || '-Q' ||
               ((CAST(substr(return_request_date, 6, 2) AS INTEGER) + 2) / 3) AS request_quarter,
           days_request_to_refund, days_refund_to_receipt, return_received_date
    FROM return_facts
    WHERE refund_issued = 1 AND is_inr = 0
),
ranked AS (
    SELECT r.*,
           ROW_NUMBER() OVER (PARTITION BY refund_type, request_quarter ORDER BY days_request_to_refund) AS rn,
           COUNT(*) OVER (PARTITION BY refund_type, request_quarter) AS n
    FROM r
)
SELECT refund_type, request_quarter,
       COUNT(*) AS refunds,
       ROUND(AVG(days_request_to_refund), 2) AS avg_days_request_to_refund,
       MAX(CASE WHEN rn = (n + 1) / 2 THEN days_request_to_refund END) AS p50_days_request_to_refund,
       MAX(CASE WHEN rn = CAST(0.9 * n AS INTEGER) THEN days_request_to_refund END) AS p90_days_request_to_refund,
       /* exposure window: days an instant refund is out before the item arrives */
       ROUND(AVG(CASE WHEN refund_type = 'instant' THEN days_refund_to_receipt END), 2) AS avg_days_refund_to_receipt,
       ROUND(100.0 * SUM(CASE WHEN return_received_date IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_never_received
FROM ranked
GROUP BY refund_type, request_quarter
ORDER BY refund_type, request_quarter;
