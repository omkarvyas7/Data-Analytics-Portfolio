/* 07_milestone_status.sql
Milestone-level status: which ones are slipping, by how many days, and who owns them.

Param: :week_end (status as-of date)
Uses the same variance, dependency and RAG rules as 06_program_health_initiative.sql.
Returns every milestone with schedule_variance_days, blocked_by_dependency, late_start
and milestone_rag. at_risk_flag = 1 for open Red/Amber milestones.
*/
WITH ms AS (
    SELECT
        m.*,
        i.initiative,
        i.team,
        d.status AS dependency_status,
        CASE
            WHEN m.actual_end   IS NOT NULL THEN julianday(m.actual_end)   - julianday(m.planned_end)
            WHEN m.forecast_end IS NOT NULL THEN julianday(m.forecast_end) - julianday(m.planned_end)
            WHEN m.planned_end < :week_end  THEN julianday(:week_end)      - julianday(m.planned_end)
            ELSE 0
        END AS schedule_variance_days,
        CASE WHEN m.depends_on IS NOT NULL AND d.status <> 'Complete' AND m.status <> 'Complete'
                  AND m.planned_start <= :week_end THEN 1 ELSE 0 END AS blocked_by_dependency,
        CASE WHEN m.actual_start IS NULL AND m.status <> 'Complete'
                  AND m.planned_start <= :week_end THEN 1 ELSE 0 END AS late_start
    FROM milestones m
    JOIN initiatives i     ON i.initiative_id = m.initiative_id
    LEFT JOIN milestones d ON d.milestone_id = m.depends_on
)
SELECT
    initiative_id,
    initiative,
    team,
    milestone_id,
    milestone,
    owner_role,
    planned_start,
    planned_end,
    actual_start,
    actual_end,
    forecast_end,
    status,
    pct_complete,
    depends_on,
    dependency_status,
    CAST(schedule_variance_days AS INTEGER) AS schedule_variance_days,
    blocked_by_dependency,
    late_start,
    CASE
        WHEN status = 'Complete' THEN 'Complete'
        WHEN status = 'Blocked' OR blocked_by_dependency = 1 OR schedule_variance_days > 21 THEN 'Red'
        WHEN status = 'At Risk' OR schedule_variance_days > 7 OR late_start = 1 THEN 'Amber'
        ELSE 'Green'
    END AS milestone_rag,
    CASE WHEN status <> 'Complete'
          AND (status IN ('Blocked', 'At Risk') OR blocked_by_dependency = 1
               OR schedule_variance_days > 7 OR late_start = 1) THEN 1 ELSE 0 END AS at_risk_flag
FROM ms
ORDER BY initiative_id, planned_start;
