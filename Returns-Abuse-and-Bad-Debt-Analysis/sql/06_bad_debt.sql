-- 06_bad_debt.sql
-- Bad debt: refunds where the item still hadn't arrived params.bad_debt_days
-- (30) after the refund. How much money goes out this way, and how much of
-- it is instant refunds?
-- Output: refund month x refund type, plus TOTAL rows, with refunds,
-- refund $, bad-debt count, bad-debt $ and bad-debt % of refund $.
-- INR claims are left out (nothing is expected back). They are sized as INR
-- concessions in 12_abuse_patterns.sql.
WITH f AS (
    SELECT substr(refund_issued_date, 1, 7) AS refund_month,
           CASE WHEN instant_refund_flag = 1 THEN 'instant' ELSE 'standard' END AS refund_type,
           refund_amount, bad_debt_flag
    FROM return_facts
    WHERE refund_issued = 1 AND is_inr = 0
      AND julianday((SELECT extract_date FROM params)) - julianday(refund_issued_date) >= (SELECT bad_debt_days FROM params)
),
monthly AS (
    SELECT refund_month, refund_type,
           COUNT(*) AS refunds,
           SUM(refund_amount) AS refund_dollars,
           SUM(bad_debt_flag) AS bad_debt_refunds,
           SUM(CASE WHEN bad_debt_flag = 1 THEN refund_amount ELSE 0 END) AS bad_debt_dollars
    FROM f GROUP BY 1, 2
    UNION ALL
    SELECT 'TOTAL', refund_type, COUNT(*), SUM(refund_amount), SUM(bad_debt_flag),
           SUM(CASE WHEN bad_debt_flag = 1 THEN refund_amount ELSE 0 END)
    FROM f GROUP BY 2
    UNION ALL
    SELECT 'TOTAL', 'all', COUNT(*), SUM(refund_amount), SUM(bad_debt_flag),
           SUM(CASE WHEN bad_debt_flag = 1 THEN refund_amount ELSE 0 END)
    FROM f
)
SELECT refund_month, refund_type, refunds,
       ROUND(refund_dollars, 2) AS refund_dollars,
       bad_debt_refunds,
       ROUND(bad_debt_dollars, 2) AS bad_debt_dollars,
       ROUND(100.0 * bad_debt_dollars / refund_dollars, 3) AS bad_debt_pct_of_refund_dollars,
       ROUND(100.0 * bad_debt_refunds / refunds, 3) AS bad_debt_pct_of_refunds
FROM monthly
ORDER BY CASE WHEN refund_month = 'TOTAL' THEN 1 ELSE 0 END, refund_month, refund_type;
