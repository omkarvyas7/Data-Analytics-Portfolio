-- 08_risk_score_tiers.sql
-- Turn the features into a points score and Low / Medium / High tiers that
-- anyone can trace back to the rules. This decides who gets a different
-- returns experience (e.g. no instant refund) and why.
-- Points (scoring window, before 2025-07-01):
--   90-day rolling return rate  >= 75% : 2 | >= 50% : 1
--   return $ share              >= 50% : 1
--   condition mismatches        >= 2   : 3 | = 1 : 1
--   INR claims                  >= 2   : 3 | = 1 : 1
--   never-received refunds      >= 2   : 4 | = 1 : 2
--   address in INR cluster              : 3
--   account tenure < 180 days           : 1
-- High if points >= params.tier_high_cutoff (4), Medium if points >=
-- params.tier_med_cutoff (2), else Low.
-- Output: table customer_risk. The final SELECT gives the tier mix and
-- profile.
DROP TABLE IF EXISTS customer_risk;
CREATE TABLE customer_risk AS
WITH pts AS (
    SELECT f.*,
           CASE WHEN max_roll90_return_rate >= 0.75 THEN 2 WHEN max_roll90_return_rate >= 0.5 THEN 1 ELSE 0 END AS pts_roll90,
           CASE WHEN return_dollar_share >= 0.5 THEN 1 ELSE 0 END AS pts_dollar_share,
           CASE WHEN condition_mismatches >= 2 THEN 3 WHEN condition_mismatches = 1 THEN 1 ELSE 0 END AS pts_mismatch,
           CASE WHEN inr_claims >= 2 THEN 3 WHEN inr_claims = 1 THEN 1 ELSE 0 END AS pts_inr,
           CASE WHEN never_received_refunds >= 2 THEN 4 WHEN never_received_refunds = 1 THEN 2 ELSE 0 END AS pts_never_received,
           CASE WHEN address_inr_cluster = 1 THEN 3 ELSE 0 END AS pts_address_cluster,
           CASE WHEN tenure_days < 180 THEN 1 ELSE 0 END AS pts_new_account
    FROM customer_features f
)
SELECT pts.*,
       pts_roll90 + pts_dollar_share + pts_mismatch + pts_inr + pts_never_received
         + pts_address_cluster + pts_new_account AS risk_score,
       CASE WHEN pts_roll90 + pts_dollar_share + pts_mismatch + pts_inr + pts_never_received
                 + pts_address_cluster + pts_new_account >= p.tier_high_cutoff THEN 'High'
            WHEN pts_roll90 + pts_dollar_share + pts_mismatch + pts_inr + pts_never_received
                 + pts_address_cluster + pts_new_account >= p.tier_med_cutoff THEN 'Medium'
            ELSE 'Low' END AS risk_tier
FROM pts CROSS JOIN params p;
CREATE INDEX ix_crisk ON customer_risk(customer_id);

SELECT risk_tier,
       COUNT(*) AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_customers,
       ROUND(AVG(risk_score), 2) AS avg_score,
       ROUND(AVG(return_rate), 4) AS avg_return_rate,
       ROUND(AVG(return_dollar_share), 4) AS avg_return_dollar_share,
       SUM(inr_claims) AS inr_claims,
       SUM(condition_mismatches) AS condition_mismatches,
       SUM(never_received_refunds) AS never_received_refunds
FROM customer_risk
GROUP BY risk_tier
ORDER BY CASE risk_tier WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END;
