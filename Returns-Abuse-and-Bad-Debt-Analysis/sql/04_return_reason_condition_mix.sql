-- 04_return_reason_condition_mix.sql
-- Stated return reason vs the condition graded at the warehouse, plus how
-- much resale (ReCommerce) value comes back. Which reason codes hide
-- condition problems?
-- Output: one row per reason code with volume, refund $, receipt rate,
-- condition mix (% of graded units), mismatch rate and recovery rate.
SELECT reason_code,
       COUNT(*) AS returns,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_returns,
       ROUND(SUM(refund_amount), 2) AS refund_dollars,
       ROUND(100.0 * SUM(CASE WHEN return_received_date IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_received,
       ROUND(100.0 * SUM(CASE WHEN condition_grade = 'new' THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN condition_grade IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS pct_new,
       ROUND(100.0 * SUM(CASE WHEN condition_grade = 'open_box' THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN condition_grade IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS pct_open_box,
       ROUND(100.0 * SUM(CASE WHEN condition_grade = 'used' THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN condition_grade IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS pct_used,
       ROUND(100.0 * SUM(CASE WHEN condition_grade = 'damaged' THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN condition_grade IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS pct_damaged,
       ROUND(100.0 * SUM(CASE WHEN condition_grade IN ('empty_box', 'wrong_item_returned') THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN condition_grade IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS pct_empty_or_wrong,
       ROUND(100.0 * SUM(condition_mismatch_flag) / NULLIF(SUM(CASE WHEN condition_grade IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS mismatch_rate_pct,
       ROUND(SUM(recovery_value) / NULLIF(SUM(CASE WHEN condition_grade IS NOT NULL THEN item_price END), 0), 4) AS recovery_rate,
       ROUND(SUM(loss_amt), 2) AS loss_dollars
FROM return_facts
GROUP BY reason_code
ORDER BY returns DESC;
