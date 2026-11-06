/* 06_program_health_initiative.sql
Program health, one row per initiative: what's on track, what's slipping, and why.

Param: :week_end (Sunday of the WBR week, the status as-of date)
Milestone rules:
  schedule_variance_days = actual_end - planned_end      (complete)
                         = forecast_end - planned_end    (open, has a forecast)
                         = as_of - planned_end           (open, overdue, no forecast)
  blocked_by_dependency  = predecessor not Complete AND this milestone not Complete
                           AND planned_start <= as_of
  milestone RAG  Red   if status Blocked, blocked_by_dependency, or slip > 21 days
                 Amber if status At Risk, slip > 7 days, or planned start passed with no start
                 Green otherwise (Complete milestones show as Complete)
Initiative RAG is Red if any open milestone is Red, Amber if any is Amber or there is an
open High risk (likelihood x impact >= 15), else Green.
Returns counts, max/avg slip, % complete, open High risks, RAG and the next open milestone.
*/
WITH ms AS (
    SELECT
        m.*,
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
    LEFT JOIN milestones d ON d.milestone_id = m.depends_on
),
ms_rag AS (
    SELECT ms.*,
        CASE
            WHEN status = 'Complete' THEN 'Complete'
            WHEN status = 'Blocked' OR blocked_by_dependency = 1 OR schedule_variance_days > 21 THEN 'Red'
            WHEN status = 'At Risk' OR schedule_variance_days > 7 OR late_start = 1 THEN 'Amber'
            ELSE 'Green'
        END AS milestone_rag
    FROM ms
),
risk AS (
    SELECT initiative_id,
           SUM(CASE WHEN status <> 'Closed' AND likelihood * impact >= 15 THEN 1 ELSE 0 END) AS open_high_risks,
           SUM(CASE WHEN status <> 'Closed' THEN 1 ELSE 0 END)                              AS open_risks
    FROM risks
    GROUP BY initiative_id
),
nxt AS (
    SELECT initiative_id, milestone AS next_milestone, planned_end AS next_milestone_planned_end,
           ROW_NUMBER() OVER (PARTITION BY initiative_id ORDER BY planned_end) AS rn
    FROM ms_rag
    WHERE status <> 'Complete'
),
roll AS (
    SELECT
        initiative_id,
        COUNT(*)                                                         AS milestones_total,
        SUM(CASE WHEN status = 'Complete' THEN 1 ELSE 0 END)             AS milestones_complete,
        SUM(CASE WHEN milestone_rag IN ('Red', 'Amber') THEN 1 ELSE 0 END) AS milestones_at_risk,
        SUM(blocked_by_dependency)                                       AS blocked_by_dependency,
        MAX(schedule_variance_days)                                      AS max_slip_days,
        AVG(schedule_variance_days)                                      AS avg_slip_days,
        AVG(pct_complete)                                                AS avg_pct_complete,
        SUM(CASE WHEN milestone_rag = 'Red' THEN 1 ELSE 0 END)           AS red_milestones,
        SUM(CASE WHEN milestone_rag = 'Amber' THEN 1 ELSE 0 END)         AS amber_milestones
    FROM ms_rag
    GROUP BY initiative_id
)
SELECT
    i.initiative_id,
    i.initiative,
    i.owner_role,
    i.team,
    i.primary_kpi,
    r.milestones_total,
    r.milestones_complete,
    ROUND(r.avg_pct_complete, 1)        AS avg_pct_complete,
    r.milestones_at_risk,
    r.blocked_by_dependency,
    CAST(r.max_slip_days AS INTEGER)    AS max_slip_days,
    ROUND(r.avg_slip_days, 1)           AS avg_slip_days,
    COALESCE(k.open_high_risks, 0)      AS open_high_risks,
    COALESCE(k.open_risks, 0)           AS open_risks,
    CASE
        WHEN r.red_milestones > 0 THEN 'Red'
        WHEN r.amber_milestones > 0 OR COALESCE(k.open_high_risks, 0) > 0 THEN 'Amber'
        ELSE 'Green'
    END                                 AS program_rag,
    n.next_milestone,
    n.next_milestone_planned_end
FROM initiatives i
JOIN roll r      ON r.initiative_id = i.initiative_id
LEFT JOIN risk k ON k.initiative_id = i.initiative_id
LEFT JOIN nxt n  ON n.initiative_id = i.initiative_id AND n.rn = 1
ORDER BY CASE program_rag WHEN 'Red' THEN 1 WHEN 'Amber' THEN 2 ELSE 3 END, i.initiative_id;
