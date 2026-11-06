"""Writes the WBR headline and asks from the query results. No number here is typed by hand."""
from datetime import date, timedelta

from config import fmt_kpi, fmt_delta


def _pct(x):
    return "n/a" if x is None or x != x else f"{x * 100:+.1f}%"


def build_narrative(res, week):
    s = res["kpi_summary"].set_index("kpi")
    r = res["kpi_rag"].set_index("kpi")
    ph = res["program_health"]
    drv = res["cycle_driver"]
    gaps = res["gap_list"]
    wk_end = (date.fromisoformat(week) + timedelta(days=6)).isoformat()

    n_green = int((r["rag"] == "Green").sum())
    n_amber = int((r["rag"] == "Amber").sum())
    n_red = int((r["rag"] == "Red").sum())
    reds = r[r["rag"] == "Red"]
    headline = []
    headline.append(
        f"{n_green} of {len(r)} KPIs met target for the week of {week} to {wk_end}; "
        f"{n_amber} are Amber and {n_red} are Red"
        + (f" ({', '.join(reds['display_name'])})." if n_red else ".")
    )
    for kpi, row in reds.iterrows():
        u = row["unit"]
        sr = s.loc[kpi]
        headline.append(
            f"{row['display_name']} was {fmt_kpi(row['actual'], u)} vs a {fmt_kpi(row['target'], u)} target "
            f"({row['variance_pct'] * 100:+.1f}% unfavourable), {fmt_delta(sr['wow_abs'], u)} WoW and "
            f"{fmt_delta(sr['yoy_abs'], u)} YoY; it has missed target {int(row['weeks_missed_last_4'])} of the last 4 weeks."
        )
    if "refund_cycle_days" in reds.index and len(drv):
        top = drv.sort_values("total_effect_days", ascending=False).iloc[0]
        total = drv["total_effect_days"].sum()
        share = top["total_effect_days"] / total if total else float("nan")
        if share >= 1:
            explain = (f"accounts for {top['total_effect_days']:+.2f} days, more than the whole {total:+.2f}-day "
                       f"program change vs the pre-incident baseline (all other segments net "
                       f"{total - top['total_effect_days']:+.2f} days)")
        else:
            explain = (f"explains {top['total_effect_days']:+.2f} of the {total:+.2f}-day program change vs the "
                       f"pre-incident baseline ({share * 100:.0f}%)")
        headline.append(
            f"Driver: {top['marketplace']} {top['channel']} {explain}. Its cycle time rose "
            f"from {top['days_base']:.2f} to {top['days_cur']:.2f} days, and {top['transit_change']:+.2f} days of that is "
            f"carrier transit, not warehouse processing ({top['processing_change']:+.2f} days)."
        )
    goods = r[(r["rag"] == "Green")]
    if len(goods):
        best = goods.copy()
        best["yoy_pct"] = s.loc[best.index, "yoy_pct"]
        k = best["yoy_pct"].abs().idxmax()
        u = best.loc[k, "unit"]
        headline.append(
            f"Bright spot: {best.loc[k, 'display_name']} at {fmt_kpi(best.loc[k, 'actual'], u)} "
            f"({_pct(s.loc[k, 'yoy_pct'])} YoY), ahead of its {fmt_kpi(best.loc[k, 'target'], u)} target."
        )
    n_r = int((ph["program_rag"] == "Red").sum())
    n_a = int((ph["program_rag"] == "Amber").sum())
    n_g = int((ph["program_rag"] == "Green").sum())
    red_names = ", ".join(ph.loc[ph["program_rag"] == "Red", "initiative"])
    headline.append(
        f"Program health: {n_r} initiatives Red ({red_names}), {n_a} Amber, {n_g} Green. "
        f"{int(ph['milestones_at_risk'].sum())} milestones are at risk, {int(ph['blocked_by_dependency'].sum())} are "
        f"blocked by a dependency, and {int(ph['open_high_risks'].sum())} High risks are open."
    )
    blk = res["blocked"]
    if len(blk):
        dep = blk.groupby(["dependency_id", "dependency_milestone", "dependency_team", "dependency_forecast_end"]).size()
        (did, dname, dteam, dfc), cnt = next(iter(dep.items()))
        headline.append(
            f"Critical path: {did} {dname} ({dteam}, forecast {dfc}) is blocking {cnt} downstream milestones, "
            f"including drop-off Wave 2, which is the structural fix for mail-in transit delays."
            if "M304" in set(blk["blocked_milestone_id"]) else
            f"Critical path: {did} {dname} ({dteam}) is blocking {cnt} downstream milestones."
        )
    asks = []
    for _, g in gaps[gaps["priority"] == "P1"].iterrows():
        asks.append(f"[{g['priority']}] {g['team']} ({g['owner_role']}), {g['item']}: {g['ask']}. {g['detail']}. Due {g['due_date']}.")
    return {"week_start": week, "week_end": wk_end, "headline": headline, "asks": asks,
            "counts": {"green": n_green, "amber": n_amber, "red": n_red,
                       "init_red": n_r, "init_amber": n_a, "init_green": n_g}}
