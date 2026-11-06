-- 09_tier_outcomes_validation.sql
-- Out-of-time check on the score. Tiers come from Jan 2024 to Jun 2025,
-- outcomes from Jul to Dec 2025 (which includes the Q4 peak). Do High-tier
-- customers really lose more money later, and what share of loss $ do
-- they hold?
--   loss event     any bad-debt refund, condition mismatch or INR claim
--   loss $         return_facts.loss_amt (see 02_clean_tables.sql)
--   good customer  active in the performance window with no loss event
-- Output: table customer_outcomes. The final SELECT gives loss rates by tier.
DROP TABLE IF EXISTS customer_outcomes;
CREATE TABLE customer_outcomes AS
WITH perf_orders AS (
    SELECT customer_id, COUNT(*) AS perf_orders, SUM(item_price) AS perf_order_dollars
    FROM clean_orders
    WHERE order_date >= (SELECT scoring_cutoff FROM params)
    GROUP BY customer_id
),
perf_returns AS (
    SELECT customer_id,
           SUM(CASE WHEN is_inr = 0 THEN 1 ELSE 0 END) AS perf_returns,
           SUM(refund_amount) AS perf_refund_dollars,
           SUM(instant_refund_flag) AS perf_instant_refunds,
           SUM(bad_debt_flag) AS perf_bad_debt_refunds,
           SUM(condition_mismatch_flag) AS perf_condition_mismatches,
           SUM(is_inr) AS perf_inr_claims,
           SUM(loss_amt) AS perf_loss_dollars
    FROM return_facts
    WHERE period = 'performance'
    GROUP BY customer_id
)
SELECT r.customer_id, r.region, r.is_member, r.payment_type, r.risk_score, r.risk_tier,
       r.orders AS scoring_orders, r.return_rate, r.max_roll90_return_rate, r.return_dollar_share,
       r.inr_claims, r.condition_mismatches, r.mismatch_rate, r.never_received_refunds,
       r.address_inr_cluster, r.tenure_days,
       COALESCE(po.perf_orders, 0) AS perf_orders,
       ROUND(COALESCE(po.perf_order_dollars, 0), 2) AS perf_order_dollars,
       COALESCE(pr.perf_returns, 0) AS perf_returns,
       ROUND(COALESCE(pr.perf_refund_dollars, 0), 2) AS perf_refund_dollars,
       COALESCE(pr.perf_instant_refunds, 0) AS perf_instant_refunds,
       COALESCE(pr.perf_bad_debt_refunds, 0) AS perf_bad_debt_refunds,
       COALESCE(pr.perf_condition_mismatches, 0) AS perf_condition_mismatches,
       COALESCE(pr.perf_inr_claims, 0) AS perf_inr_claims,
       ROUND(COALESCE(pr.perf_loss_dollars, 0), 2) AS perf_loss_dollars,
       CASE WHEN COALESCE(po.perf_orders, 0) + COALESCE(pr.perf_returns, 0) + COALESCE(pr.perf_inr_claims, 0) > 0
            THEN 1 ELSE 0 END AS perf_active,
       CASE WHEN COALESCE(pr.perf_bad_debt_refunds, 0) + COALESCE(pr.perf_condition_mismatches, 0)
                 + COALESCE(pr.perf_inr_claims, 0) > 0 THEN 1 ELSE 0 END AS perf_loss_event
FROM customer_risk r
LEFT JOIN perf_orders po ON po.customer_id = r.customer_id
LEFT JOIN perf_returns pr ON pr.customer_id = r.customer_id;
CREATE INDEX ix_cout ON customer_outcomes(customer_id);

SELECT risk_tier,
       COUNT(*) AS customers,
       SUM(perf_active) AS active_customers,
       SUM(CASE WHEN perf_active = 1 AND perf_loss_event = 0 THEN 1 ELSE 0 END) AS good_customers,
       SUM(perf_loss_event) AS customers_with_loss_event,
       ROUND(100.0 * SUM(perf_loss_event) / NULLIF(SUM(perf_active), 0), 2) AS loss_event_rate_pct,
       ROUND(100.0 * SUM(perf_returns) / NULLIF(SUM(perf_orders), 0), 2) AS perf_return_rate_pct,
       ROUND(SUM(perf_loss_dollars), 2) AS loss_dollars,
       ROUND(SUM(perf_loss_dollars) / NULLIF(SUM(perf_active), 0), 2) AS loss_dollars_per_active_customer,
       ROUND(100.0 * SUM(perf_loss_dollars) / SUM(SUM(perf_loss_dollars)) OVER (), 2) AS pct_of_loss_dollars,
       ROUND(100.0 * SUM(perf_active) / SUM(SUM(perf_active)) OVER (), 2) AS pct_of_active_customers
FROM customer_outcomes
GROUP BY risk_tier
ORDER BY CASE risk_tier WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END;
