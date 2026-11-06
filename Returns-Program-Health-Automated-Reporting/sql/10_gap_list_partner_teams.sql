/* 10_gap_list_partner_teams.sql
The asks section of the WBR: what each team needs to fix or decide before next week.

Params: :week_start, :week_end
Four kinds of gap, each routed to a team:
  (a) KPI off target (Red = P1, Amber = P2), to the KPI owner team
  (b) milestone blocked by another team's dependency, to the predecessor's team (P1)
  (c) open milestone slipping > 7 days and not blocked, to its owner team (P1 if > 21 days)
  (d) High risk with no mitigation or past close date, to the initiative team (P1)
One row per gap: priority, gap_type, team, owner_role, item, detail, ask, due_date.
Due date is the next WBR as-of date.
*/
WITH kpi AS (
    SELECT l.kpi, l.value, t.display_name, t.unit, t.target, t.direction, t.amber_band,
           t.owner_team, t.initiative_id,
           CASE
               WHEN t.direction = 'lower'  AND l.value <= t.target                      THEN 'Green'
               WHEN t.direction = 'lower'  AND l.value <= t.target * (1 + t.amber_band) THEN 'Amber'
               WHEN t.direction = 'lower'                                               THEN 'Red'
               WHEN t.direction = 'higher' AND l.value >= t.target                      THEN 'Green'
               WHEN t.direction = 'higher' AND l.value >= t.target * (1 - t.amber_band) THEN 'Amber'
               ELSE 'Red'
           END AS rag
    FROM v_weekly_kpi_long l
    JOIN kpi_targets t ON t.kpi = l.kpi
    WHERE l.week_start = :week_start
),
fmt AS (
    SELECT kpi.*,
           CASE unit WHEN 'pct'  THEN printf('%.1f%%', value * 100)
                     WHEN 'usd'  THEN printf('$%.2f', value)
                     WHEN 'days' THEN printf('%.2f days', value)
                     WHEN 'units' THEN printf('%,d', CAST(value AS INTEGER))
                     ELSE printf('%.3f', value) END AS value_txt,
           CASE unit WHEN 'pct'  THEN printf('%.1f%%', target * 100)
                     WHEN 'usd'  THEN printf('$%.2f', target)
                     WHEN 'days' THEN printf('%.2f days', target)
                     WHEN 'units' THEN printf('%,d', CAST(target AS INTEGER))
                     ELSE printf('%.3f', target) END AS target_txt
    FROM kpi
),
ms AS (
    SELECT m.*, i.team, d.status AS dep_status, d.forecast_end AS dep_forecast, d.milestone AS dep_name,
           di.team AS dep_team, d.owner_role AS dep_owner,
           CASE
               WHEN m.actual_end   IS NOT NULL THEN julianday(m.actual_end)   - julianday(m.planned_end)
               WHEN m.forecast_end IS NOT NULL THEN julianday(m.forecast_end) - julianday(m.planned_end)
               WHEN m.planned_end < :week_end  THEN julianday(:week_end)      - julianday(m.planned_end)
               ELSE 0
           END AS slip,
           CASE WHEN m.depends_on IS NOT NULL AND d.status <> 'Complete' AND m.status <> 'Complete'
                     AND m.planned_start <= :week_end THEN 1 ELSE 0 END AS blocked
    FROM milestones m
    JOIN initiatives i       ON i.initiative_id = m.initiative_id
    LEFT JOIN milestones d   ON d.milestone_id = m.depends_on
    LEFT JOIN initiatives di ON di.initiative_id = d.initiative_id
),
gaps AS (
    SELECT CASE WHEN f.rag = 'Red' THEN 'P1' ELSE 'P2' END AS priority,
           'KPI off target'                                AS gap_type,
           f.owner_team                                    AS team,
           i.owner_role                                    AS owner_role,
           f.display_name                                  AS item,
           f.value_txt || ' vs target ' || f.target_txt || ' (' || f.rag || ')' AS detail,
           CASE WHEN f.rag = 'Red'
                THEN 'Root cause and recovery plan with a date-to-green at next WBR'
                ELSE 'Confirm trajectory; flag if the miss persists a second week' END AS ask
    FROM fmt f
    JOIN initiatives i ON i.initiative_id = f.initiative_id
    WHERE f.rag <> 'Green'
    UNION ALL
    /* one row per blocking predecessor; GROUP_CONCAT is LISTAGG in Redshift, STRING_AGG in Postgres */
    SELECT 'P1', 'Blocked by dependency', ms.dep_team, ms.dep_owner,
           ms.depends_on || ' ' || ms.dep_name,
           'Blocks ' || COUNT(*) || ' milestone(s): ' || GROUP_CONCAT(ms.milestone_id || ' (' || ms.team || ')', ', ')
               || '; predecessor forecast ' || COALESCE(ms.dep_forecast, 'not set'),
           'Commit a firm delivery date or an interim workaround for the blocked teams'
    FROM ms
    WHERE ms.blocked = 1
    GROUP BY ms.dep_team, ms.dep_owner, ms.depends_on, ms.dep_name, ms.dep_forecast
    UNION ALL
    SELECT CASE WHEN ms.slip > 21 THEN 'P1' ELSE 'P2' END, 'Milestone slipping', ms.team, ms.owner_role,
           ms.milestone_id || ' ' || ms.milestone,
           'Planned end ' || ms.planned_end || ', forecast ' || COALESCE(ms.forecast_end, 'not set')
               || ' (' || CAST(ms.slip AS INTEGER) || ' days late)',
           'Re-baseline the plan or add capacity; confirm impact on downstream milestones'
    FROM ms
    WHERE ms.status <> 'Complete' AND ms.blocked = 0 AND ms.slip > 7
    UNION ALL
    SELECT 'P1', 'High risk unmitigated', i.team, r.owner_role,
           r.risk_id || ' ' || r.risk,
           'Severity ' || (r.likelihood * r.impact) || '; mitigation: ' || COALESCE(r.mitigation, 'none recorded')
               || '; target close ' || r.target_close_date,
           'Assign a mitigation owner and plan, or accept the risk explicitly at the WBR'
    FROM risks r
    JOIN initiatives i ON i.initiative_id = r.initiative_id
    WHERE r.status <> 'Closed' AND r.likelihood * r.impact >= 15
      AND (r.mitigation IS NULL OR r.target_close_date < :week_end)
)
SELECT priority, gap_type, team, owner_role, item, detail, ask,
       date(:week_end, '+7 days') AS due_date
FROM gaps
ORDER BY priority, gap_type, team;
