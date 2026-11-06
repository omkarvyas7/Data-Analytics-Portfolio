-- 03_defect_pareto_by_cause.sql
-- Pareto of baseline defects by the root cause QA coded (Analyze).
-- Question: which few causes account for most of the misgrades?
-- Returns cause, defects, share, running cumulative share and leakage $ on those audited units, high to low.
WITH c AS (
    SELECT defect_cause,
           COUNT(*)                        AS defects,
           ROUND(SUM(recovery_leakage_usd), 2) AS leakage_usd_in_sample
    FROM v_audited
    WHERE phase = 'Baseline' AND is_defect = 1
    GROUP BY defect_cause
)
SELECT defect_cause, defects, leakage_usd_in_sample,
       ROUND(1.0 * defects / SUM(defects) OVER (), 4)                                   AS share,
       ROUND(1.0 * SUM(defects) OVER (ORDER BY defects DESC, defect_cause
                                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             / SUM(defects) OVER (), 4)                                                 AS cumulative_share
FROM c
ORDER BY defects DESC, defect_cause;
