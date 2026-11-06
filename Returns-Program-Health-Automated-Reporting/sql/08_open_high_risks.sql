/* 08_open_high_risks.sql
Open risks for the WBR, and which ones need leadership this week.

Param: :week_end
severity = likelihood (1-5) x impact (1-5). High >= 15, Medium 8-14, Low <= 7.
needs_escalation = High and either no mitigation recorded or the target close date has passed.
Returns all non-closed risks by severity, with days_open and an overdue flag.
*/
SELECT
    r.risk_id,
    r.initiative_id,
    i.initiative,
    r.risk,
    r.likelihood,
    r.impact,
    r.likelihood * r.impact                                         AS severity,
    CASE WHEN r.likelihood * r.impact >= 15 THEN 'High'
         WHEN r.likelihood * r.impact >= 8  THEN 'Medium'
         ELSE 'Low' END                                             AS risk_level,
    r.status,
    r.owner_role,
    COALESCE(r.mitigation, '(none recorded)')                       AS mitigation,
    r.opened_date,
    r.target_close_date,
    CAST(julianday(:week_end) - julianday(r.opened_date) AS INTEGER) AS days_open,
    CASE WHEN r.target_close_date < :week_end THEN 1 ELSE 0 END     AS past_target_close,
    CASE WHEN r.likelihood * r.impact >= 15
          AND (r.mitigation IS NULL OR r.target_close_date < :week_end) THEN 1 ELSE 0 END AS needs_escalation
FROM risks r
JOIN initiatives i ON i.initiative_id = r.initiative_id
WHERE r.status <> 'Closed'
ORDER BY severity DESC, r.target_close_date;
