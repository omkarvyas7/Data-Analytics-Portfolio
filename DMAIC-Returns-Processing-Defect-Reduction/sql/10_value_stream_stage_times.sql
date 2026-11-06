-- 10_value_stream_stage_times.sql
-- Mean hours per process step for the Dec-Jan peak, the Control period and all other months (Analyze, Lean).
-- Question: how much of the cycle is real work (triage, grading) and how much is waiting (dock, queue, routing)?
-- Returns period x stage with mean hours, share of the total and a value-added flag.
WITH p AS (
    SELECT CASE WHEN month IN ('2025-12', '2026-01') THEN 'Peak backlog (Dec-Jan)'
                WHEN phase = 'Control' THEN 'Control (May-Jun 2026)'
                ELSE 'Other baseline / pilot months' END AS period,
           dock_wait_hrs, triage_hrs, queue_to_grade_hrs, grading_hrs, routing_hrs, dock_to_disposition_hrs
    FROM v_units
    WHERE dock_to_disposition_hrs IS NOT NULL
),
s AS (
    SELECT period, 1 AS step_order, 'Dock wait' AS stage, 0 AS value_added, AVG(dock_wait_hrs) AS mean_hrs, AVG(dock_to_disposition_hrs) AS total_hrs FROM p GROUP BY period
    UNION ALL SELECT period, 2, 'Triage / receive scan', 1, AVG(triage_hrs), AVG(dock_to_disposition_hrs) FROM p GROUP BY period
    UNION ALL SELECT period, 3, 'Queue to grading', 0, AVG(queue_to_grade_hrs), AVG(dock_to_disposition_hrs) FROM p GROUP BY period
    UNION ALL SELECT period, 4, 'Grading', 1, AVG(grading_hrs), AVG(dock_to_disposition_hrs) FROM p GROUP BY period
    UNION ALL SELECT period, 5, 'Routing to disposition', 0, AVG(routing_hrs), AVG(dock_to_disposition_hrs) FROM p GROUP BY period
)
SELECT period, step_order, stage, value_added,
       ROUND(mean_hrs, 2)              AS mean_hrs,
       ROUND(mean_hrs / total_hrs, 4)  AS share_of_cycle
FROM s
ORDER BY period, step_order;
