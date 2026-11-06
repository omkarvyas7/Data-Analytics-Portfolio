/* 05_refund_cycle_driver_channel.sql
Refund cycle time is off target. Which marketplace x channel segments explain the change,
and is it rate (a segment got slower) or mix (volume moved to slower channels)?

Param: :week_start
Baseline is the 4 weeks from 8 to 5 weeks before the WBR week, before things got worse.
Program cycle = SUM(share_s * days_s), which splits exactly into:
  rate_effect_s = share_cur_s * (days_cur_s - days_base_s)
  mix_effect_s  = (share_cur_s - share_base_s) * days_base_s
The two effects summed over segments equal the program change in days. Transit
(customer to receive) and processing (receive to refund) are reported separately.
One row per marketplace x channel, ranked by total effect.
*/
WITH seg AS (
    SELECT
        CASE WHEN week_start = :week_start THEN 'cur' ELSE 'base' END AS period,
        marketplace,
        channel,
        SUM(cycle_units)                     AS cycle_units,
        SUM(refund_cycle_hours) / 24.0       AS cycle_days_total,
        SUM(transit_hours) / 24.0            AS transit_days_total,
        SUM(processing_hours) / 24.0         AS processing_days_total
    FROM weekly_fact
    WHERE week_start = :week_start
       OR week_start BETWEEN date(:week_start, '-56 days') AND date(:week_start, '-35 days')
    GROUP BY 1, 2, 3
),
tot AS (
    SELECT period, SUM(cycle_units) AS units FROM seg GROUP BY period
),
s AS (
    SELECT
        seg.marketplace,
        seg.channel,
        MAX(CASE WHEN seg.period = 'cur'  THEN 1.0 * seg.cycle_units / tot.units END)     AS share_cur,
        MAX(CASE WHEN seg.period = 'base' THEN 1.0 * seg.cycle_units / tot.units END)     AS share_base,
        MAX(CASE WHEN seg.period = 'cur'  THEN seg.cycle_days_total / NULLIF(seg.cycle_units, 0) END)      AS days_cur,
        MAX(CASE WHEN seg.period = 'base' THEN seg.cycle_days_total / NULLIF(seg.cycle_units, 0) END)      AS days_base,
        MAX(CASE WHEN seg.period = 'cur'  THEN seg.transit_days_total / NULLIF(seg.cycle_units, 0) END)    AS transit_cur,
        MAX(CASE WHEN seg.period = 'base' THEN seg.transit_days_total / NULLIF(seg.cycle_units, 0) END)    AS transit_base,
        MAX(CASE WHEN seg.period = 'cur'  THEN seg.processing_days_total / NULLIF(seg.cycle_units, 0) END) AS processing_cur,
        MAX(CASE WHEN seg.period = 'base' THEN seg.processing_days_total / NULLIF(seg.cycle_units, 0) END) AS processing_base
    FROM seg JOIN tot ON tot.period = seg.period
    GROUP BY seg.marketplace, seg.channel
)
SELECT
    marketplace,
    channel,
    share_base,
    share_cur,
    days_base,
    days_cur,
    days_cur - days_base                                        AS days_change,
    transit_cur - transit_base                                  AS transit_change,
    processing_cur - processing_base                            AS processing_change,
    share_cur * (days_cur - days_base)                          AS rate_effect_days,
    (share_cur - share_base) * days_base                        AS mix_effect_days,
    share_cur * (days_cur - days_base) + (share_cur - share_base) * days_base AS total_effect_days,
    RANK() OVER (ORDER BY share_cur * (days_cur - days_base) + (share_cur - share_base) * days_base DESC) AS driver_rank
FROM s
ORDER BY driver_rank;
