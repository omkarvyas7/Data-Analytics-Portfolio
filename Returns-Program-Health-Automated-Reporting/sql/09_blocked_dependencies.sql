/* 09_blocked_dependencies.sql
Milestones stuck because another team's milestone isn't done, and which team has to unblock them.

Param: :week_end
Returns the blocked milestone and its team, the predecessor with its owning team, status
and forecast, and how many days the blocked milestone is past its planned start.
*/
SELECT
    m.milestone_id                                                   AS blocked_milestone_id,
    m.milestone                                                      AS blocked_milestone,
    bi.initiative                                                    AS blocked_initiative,
    bi.team                                                          AS blocked_team,
    m.status                                                         AS blocked_status,
    m.planned_start,
    CAST(julianday(:week_end) - julianday(m.planned_start) AS INTEGER) AS days_past_planned_start,
    d.milestone_id                                                   AS dependency_id,
    d.milestone                                                      AS dependency_milestone,
    di.team                                                          AS dependency_team,
    d.owner_role                                                     AS dependency_owner_role,
    d.status                                                         AS dependency_status,
    d.forecast_end                                                   AS dependency_forecast_end,
    CASE WHEN bi.team <> di.team THEN 'Cross-team' ELSE 'Same team' END AS dependency_type
FROM milestones m
JOIN milestones d   ON d.milestone_id = m.depends_on
JOIN initiatives bi ON bi.initiative_id = m.initiative_id
JOIN initiatives di ON di.initiative_id = d.initiative_id
WHERE d.status <> 'Complete'
  AND m.status <> 'Complete'
  AND m.planned_start <= :week_end
ORDER BY days_past_planned_start DESC;
