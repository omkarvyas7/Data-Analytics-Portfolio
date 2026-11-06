-- 02_clean_tables.sql
-- Clean the raw tables and build return_facts, the one return-level table
-- every later query reads. It answers a simple question per return: what
-- did it cost, and was it a loss?
-- Cleaning: drop exact duplicates, drop orders priced <= 0, map null reason
-- codes to 'unknown', keep returns only for valid orders.
-- Loss flags:
--   bad_debt_flag       refund issued on a non-INR return and the item hadn't
--                       arrived params.bad_debt_days after the refund (only
--                       judged once the refund is old enough)
--   fraud_return_flag   refund issued and the item graded empty_box or
--                       wrong_item_returned
--   condition_mismatch  graded condition is worse than the stated reason allows
--   loss_amt            full refund for bad debt, fraud and INR. For other
--                       mismatches, refund minus resale recovery value.
-- Output: clean_orders, clean_returns, clean_refunds, return_facts. The final
-- SELECT compares raw and clean row counts.
DROP TABLE IF EXISTS clean_orders;
CREATE TABLE clean_orders AS
SELECT DISTINCT order_id, customer_id, order_date, delivered_date, category, item_price
FROM orders
WHERE item_price > 0 AND category IS NOT NULL AND delivered_date >= order_date;
CREATE INDEX ix_co_order ON clean_orders(order_id);
CREATE INDEX ix_co_cust ON clean_orders(customer_id, order_date);

DROP TABLE IF EXISTS clean_returns;
CREATE TABLE clean_returns AS
SELECT DISTINCT r.return_id, r.order_id, r.customer_id, r.return_request_date,
       COALESCE(r.reason_code, 'unknown') AS reason_code, r.return_method
FROM returns r
WHERE EXISTS (SELECT 1 FROM clean_orders o WHERE o.order_id = r.order_id);
CREATE INDEX ix_cr_return ON clean_returns(return_id);

DROP TABLE IF EXISTS clean_refunds;
CREATE TABLE clean_refunds AS
SELECT DISTINCT f.*
FROM refunds f
WHERE EXISTS (SELECT 1 FROM clean_returns r WHERE r.return_id = f.return_id);
CREATE INDEX ix_cf_return ON clean_refunds(return_id);

DROP TABLE IF EXISTS return_facts;
CREATE TABLE return_facts AS
WITH base AS (
    SELECT r.return_id, r.order_id, r.customer_id,
           c.region, c.is_member, c.payment_type, c.address_id, c.signup_date,
           o.order_date, substr(o.order_date, 1, 7) AS order_month,
           o.delivered_date, o.category, o.item_price,
           r.return_request_date, substr(r.return_request_date, 1, 7) AS request_month,
           r.reason_code, r.return_method,
           CASE WHEN r.reason_code = 'item_not_received' THEN 1 ELSE 0 END AS is_inr,
           CASE WHEN f.refund_id IS NOT NULL THEN 1 ELSE 0 END AS refund_issued,
           COALESCE(f.refund_amount, 0) AS refund_amount,
           f.refund_issued_date,
           COALESCE(f.instant_refund_flag, 0) AS instant_refund_flag,
           f.return_received_date,
           f.condition_grade,
           CAST(julianday(r.return_request_date) - julianday(o.delivered_date) AS INTEGER) AS days_delivered_to_request,
           CAST(julianday(f.refund_issued_date) - julianday(r.return_request_date) AS INTEGER) AS days_request_to_refund,
           CAST(julianday(f.return_received_date) - julianday(f.refund_issued_date) AS INTEGER) AS days_refund_to_receipt,
           p.scoring_cutoff, p.extract_date, p.bad_debt_days
    FROM clean_returns r
    JOIN clean_orders o ON o.order_id = r.order_id
    JOIN customers c ON c.customer_id = r.customer_id
    LEFT JOIN clean_refunds f ON f.return_id = r.return_id
    CROSS JOIN params p
),
flags AS (
    SELECT b.*,
           CASE WHEN refund_issued = 1 AND is_inr = 0
                 AND julianday(extract_date) - julianday(refund_issued_date) >= bad_debt_days
                 AND (return_received_date IS NULL
                      OR julianday(return_received_date) - julianday(refund_issued_date) > bad_debt_days)
                THEN 1 ELSE 0 END AS bad_debt_flag,
           CASE WHEN refund_issued = 1 AND condition_grade IN ('empty_box', 'wrong_item_returned')
                THEN 1 ELSE 0 END AS fraud_return_flag,
           CASE WHEN reason_code IN ('no_longer_needed', 'size_fit', 'wrong_item', 'unknown')
                 AND condition_grade IN ('used', 'damaged', 'empty_box', 'wrong_item_returned') THEN 1
                WHEN reason_code IN ('defective', 'damaged')
                 AND condition_grade IN ('empty_box', 'wrong_item_returned') THEN 1
                ELSE 0 END AS condition_mismatch_flag,
           CASE condition_grade WHEN 'new' THEN 0.90 WHEN 'open_box' THEN 0.70 WHEN 'used' THEN 0.35
                WHEN 'damaged' THEN 0.10 WHEN 'wrong_item_returned' THEN 0.05 ELSE 0 END AS recovery_rate,
           CASE WHEN return_request_date < scoring_cutoff THEN 'scoring' ELSE 'performance' END AS period
    FROM base b
)
SELECT f.*,
       ROUND(item_price * recovery_rate, 2) AS recovery_value,
       ROUND(CASE WHEN bad_debt_flag = 1 OR fraud_return_flag = 1 THEN refund_amount
                  WHEN is_inr = 1 THEN refund_amount
                  WHEN condition_mismatch_flag = 1 AND refund_issued = 1
                       THEN refund_amount - item_price * recovery_rate
                  ELSE 0 END, 2) AS loss_amt,
       /* non-INR returns by the same customer in the 90 days before this request */
       COUNT(CASE WHEN is_inr = 0 THEN 1 END) OVER (
           PARTITION BY customer_id ORDER BY julianday(return_request_date)
           RANGE BETWEEN 90 PRECEDING AND 1 PRECEDING) AS prior_returns_90d
FROM flags f;
CREATE INDEX ix_rf_cust ON return_facts(customer_id);
CREATE INDEX ix_rf_order ON return_facts(order_id);

SELECT 'orders' AS table_name, (SELECT COUNT(*) FROM orders) AS raw_rows, (SELECT COUNT(*) FROM clean_orders) AS clean_rows
UNION ALL SELECT 'returns', (SELECT COUNT(*) FROM returns), (SELECT COUNT(*) FROM clean_returns)
UNION ALL SELECT 'refunds', (SELECT COUNT(*) FROM refunds), (SELECT COUNT(*) FROM clean_refunds)
UNION ALL SELECT 'return_facts', NULL, (SELECT COUNT(*) FROM return_facts);
