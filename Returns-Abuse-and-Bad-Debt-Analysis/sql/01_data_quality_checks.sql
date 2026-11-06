-- 01_data_quality_checks.sql
-- Profile the raw tables before using them. Can the returns and refund
-- feeds be trusted, and what needs fixing or dropping first?
-- Output: one row per check with the rows flagged and how
-- 02_clean_tables.sql handles them.
-- Written for SQLite in ANSI style. Ports to Redshift/Postgres with small
-- date changes.
SELECT 'orders: exact duplicate rows' AS check_name,
       (SELECT COUNT(*) FROM orders) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM orders)) AS rows_flagged,
       'drop duplicates' AS handling
UNION ALL
SELECT 'orders: zero or negative item_price',
       (SELECT COUNT(*) FROM orders WHERE item_price <= 0),
       'exclude order'
UNION ALL
SELECT 'orders: null category',
       (SELECT COUNT(*) FROM orders WHERE category IS NULL),
       'exclude order'
UNION ALL
SELECT 'orders: delivered before ordered',
       (SELECT COUNT(*) FROM orders WHERE delivered_date < order_date),
       'exclude order'
UNION ALL
SELECT 'returns: exact duplicate rows',
       (SELECT COUNT(*) FROM returns) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM returns)),
       'drop duplicates'
UNION ALL
SELECT 'returns: null reason_code',
       (SELECT COUNT(*) FROM returns WHERE reason_code IS NULL),
       'map to unknown'
UNION ALL
SELECT 'returns: order_id not in orders',
       (SELECT COUNT(*) FROM returns r WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.order_id = r.order_id)),
       'exclude return'
UNION ALL
SELECT 'refunds: exact duplicate rows',
       (SELECT COUNT(*) FROM refunds) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM refunds)),
       'drop duplicates'
UNION ALL
SELECT 'refunds: return_id not in returns',
       (SELECT COUNT(*) FROM refunds f WHERE NOT EXISTS (SELECT 1 FROM returns r WHERE r.return_id = f.return_id)),
       'exclude refund'
UNION ALL
SELECT 'refunds: amount above item price',
       (SELECT COUNT(*) FROM refunds f
          JOIN returns r ON r.return_id = f.return_id
          JOIN orders o ON o.order_id = r.order_id
         WHERE f.refund_amount > ABS(o.item_price) + 0.01),
       'review'
UNION ALL
SELECT 'refunds: issued before return request',
       (SELECT COUNT(*) FROM refunds f JOIN returns r ON r.return_id = f.return_id
         WHERE f.refund_issued_date < r.return_request_date),
       'review'
UNION ALL
SELECT 'customers: duplicate customer_id',
       (SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM customers),
       'drop duplicates';
