"""Create and execute notebooks/analysis.ipynb (KPI exploration + driver analysis of the refund-cycle miss)."""
import nbformat as nbf
from nbclient import NotebookClient

from config import NOTEBOOKS

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell

CELLS = [
    md("# Returns program KPI exploration and driver analysis\n\n"
       "Refund cycle time and customer contacts per return both went Red in the WBR for the week of 2026-10-26. "
       "I wanted to know what is behind the miss, how much it costs in extra customer contacts, and what the "
       "owning teams should do about it.\n\n"
       "The sections follow DMAIC loosely: define the KPI and target, measure the trend and find when it shifted, "
       "analyze the driver (segment, rate vs mix, transit vs processing), size a few fixes, then set a monitoring rule.\n\n"
       "*All data is synthetic (made by `src/generate_data.py`). None of it comes from Amazon or any employer.*"),
    code("import sqlite3\nfrom pathlib import Path\n\nimport matplotlib.pyplot as plt\nimport numpy as np\nimport pandas as pd\n"
         "import statsmodels.formula.api as smf\n\n"
         "ROOT = Path('..').resolve()\nDB = ROOT / 'data' / 'returns_wbr.db'\nOUT = ROOT / 'data' / 'processed'\n"
         "WEEK = '2026-10-26'\ncon = sqlite3.connect(DB)\npd.set_option('display.width', 160)\n"
         "pd.set_option('display.float_format', lambda v: f'{v:,.4f}')\n"
         "kpi = pd.read_sql('SELECT * FROM v_weekly_kpi ORDER BY week_start', con, parse_dates=['week_start'])\n"
         "targets = pd.read_sql('SELECT * FROM kpi_targets ORDER BY sort_order', con)\n"
         "print(f\"{len(kpi)} weeks: {kpi.week_start.min():%Y-%m-%d} to {kpi.week_start.max():%Y-%m-%d}\")\n"
         "targets[['kpi', 'display_name', 'direction', 'target', 'amber_band', 'owner_team']]"),
    md("## 1. Define and Measure: KPI overview\n\nAll ratios are computed from summed numerators and denominators per week."),
    code("cols = targets.kpi.tolist()\nsummary = pd.DataFrame({\n"
         "    'first_13wk_avg': kpi[cols].head(13).mean(),\n"
         "    'last_13wk_avg': kpi[cols].tail(13).mean(),\n"
         "    'report_week': kpi.set_index('week_start').loc[WEEK, cols],\n"
         "    'target': targets.set_index('kpi')['target'],\n})\n"
         "summary['change_first_to_last_13wk_pct'] = summary.last_13wk_avg / summary.first_13wk_avg - 1\nsummary"),
    code("fig, axes = plt.subplots(2, 4, figsize=(15, 6))\n"
         "for ax, (_, t) in zip(axes.ravel(), targets.iterrows()):\n"
         "    ax.plot(kpi.week_start, kpi[t.kpi], lw=1.4)\n"
         "    ax.axhline(t.target, ls='--', color='k', lw=0.8)\n"
         "    ax.set_title(t.display_name[:32], fontsize=9)\n    ax.tick_params(labelsize=7)\n"
         "fig.suptitle('Weekly KPIs, May 2025 to Oct 2026 (dashed = target)')\nfig.tight_layout()"),
    md("Quick seasonality check: return rate peaks in January (post-holiday returns), and refund cycle time rises in "
       "December and January when the warehouses are congested. A late-October jump in cycle time doesn't fit that pattern."),
    code("m = kpi.assign(month=kpi.week_start.dt.to_period('M')).groupby('month')[['return_rate', 'refund_cycle_days', "
         "'contacts_per_return']].mean()\nm.tail(18)"),
    code("dispo = pd.read_sql('''SELECT week_start, SUM(resold_units) resold, SUM(liquidated_units) liquidated,\n"
         "  SUM(recycled_units) recycled, SUM(waste_units) waste FROM weekly_fact GROUP BY week_start''', con, parse_dates=['week_start'])\n"
         "sh = dispo.set_index('week_start')\nsh = sh.div(sh.sum(axis=1), axis=0)\n"
         "ax = sh.plot.area(figsize=(10, 3.5), cmap='viridis', alpha=0.85)\n"
         "ax.set_title('Disposition mix (share of units with a disposition)'); ax.set_ylim(0, 1)\n"
         "print('Waste share first 13 wks vs last 13 wks:', f\"{sh.waste.head(13).mean():.2%} -> {sh.waste.tail(13).mean():.2%}\")"),
    md("## 2. Measure: detect the shift with a control chart\n\nBaseline = 26 non-holiday weeks (2026-03-02 to 2026-08-24). "
       "Control limits = mean +/- 3 standard deviations of the weekly values."),
    code("base = kpi[(kpi.week_start >= '2026-03-02') & (kpi.week_start <= '2026-08-24')]\n"
         "mu, sd = base.refund_cycle_days.mean(), base.refund_cycle_days.std()\nucl, lcl = mu + 3 * sd, mu - 3 * sd\n"
         "recent = kpi[kpi.week_start >= '2026-08-31'][['week_start', 'refund_cycle_days', 'contacts_per_return']].copy()\n"
         "recent['above_ucl'] = recent.refund_cycle_days > ucl\n"
         "print(f'baseline mean {mu:.3f} d, sd {sd:.3f}, UCL {ucl:.3f}')\nfirst_signal = recent.loc[recent.above_ucl, 'week_start'].min()\n"
         "print('first week above UCL:', first_signal.date())\n"
         "fig, ax = plt.subplots(figsize=(10, 3.5))\nw = kpi[kpi.week_start >= '2026-03-02']\n"
         "ax.plot(w.week_start, w.refund_cycle_days, marker='o', ms=3)\n"
         "for y, s in [(mu, '-'), (ucl, '--'), (lcl, '--')]: ax.axhline(y, ls=s, color='grey', lw=0.9)\n"
         "ax.axhline(3.30, color='k', ls=':', lw=1, label='target 3.30')\nax.set_title('Refund cycle time control chart'); ax.legend()\nrecent"),
    md("## 3. Analyze: which segment, rate or mix, transit or processing?\n\n"
       "`sql/05_refund_cycle_driver_channel.sql` decomposes the change between a 4-week pre-incident baseline "
       "(weeks starting 2026-08-31 to 2026-09-21) and the report week into a **rate effect** (a segment got slower) and a "
       "**mix effect** (volume moved to a slower channel). The two effects sum exactly to the program change."),
    code("sql = (ROOT / 'sql' / '05_refund_cycle_driver_channel.sql').read_text()\n"
         "drv = pd.read_sql(sql, con, params={'week_start': WEEK})\n"
         "print(f\"program change: {drv.total_effect_days.sum():+.3f} days (rate {drv.rate_effect_days.sum():+.3f}, mix {drv.mix_effect_days.sum():+.3f})\")\n"
         "drv.head(6)[['marketplace', 'channel', 'share_cur', 'days_base', 'days_cur', 'transit_change', 'processing_change', "
         "'rate_effect_days', 'mix_effect_days', 'total_effect_days']]"),
    code("seg = pd.read_sql('''SELECT week_start, marketplace, channel, category,\n"
         "  SUM(transit_hours)/24.0/SUM(cycle_units) transit_days, SUM(processing_hours)/24.0/SUM(cycle_units) processing_days\n"
         "  FROM weekly_fact WHERE week_start >= '2026-07-06' AND channel <> 'Returnless'\n"
         "  GROUP BY 1,2,3,4''', con, parse_dates=['week_start'])\n"
         "us_mail = seg[(seg.marketplace == 'US') & (seg.channel == 'Mail-in')]\n"
         "fig, axes = plt.subplots(1, 2, figsize=(13, 3.6))\n"
         "for c, g in us_mail.groupby('category'): axes[0].plot(g.week_start, g.transit_days, label=c)\n"
         "axes[0].set_title('US Mail-in transit days by category'); axes[0].legend(fontsize=7)\n"
         "for (mk, ch), g in seg.groupby(['marketplace', 'channel']):\n"
         "    g2 = g.groupby('week_start')[['processing_days']].mean()\n"
         "    axes[1].plot(g2.index, g2.processing_days, lw=1.5 if (mk, ch) == ('US', 'Mail-in') else 0.6, color='C3' if (mk, ch) == ('US', 'Mail-in') else 'grey')\n"
         "axes[1].set_title('Processing days (receive -> refund), US Mail-in in red'); fig.tight_layout()"),
    md("So the rise sits in one segment (US Mail-in), shows up in every category inside it, and it's transit "
       "(customer hand-off to warehouse receipt), not warehouse processing. That points at the carrier network change "
       "logged as ISS-005 / R05 (linehaul consolidation) rather than the returns centers. Mix effects are close to zero, "
       "so the drop-off expansion isn't pushing volume into slow channels."),
    md("## 4. Analyze: customer impact (contacts per return vs cycle time)"),
    code("ols = smf.ols('contacts_per_return ~ refund_cycle_days', data=kpi).fit()\n"
         "print(ols.summary().tables[1])\nslope = ols.params['refund_cycle_days']\n"
         "cur = kpi.set_index('week_start').loc[WEEK]\nbase_days = cur.refund_cycle_days - drv.total_effect_days.sum()\n"
         "excess_contacts = slope * (cur.refund_cycle_days - base_days) * cur.return_units\n"
         "print(f'R^2 {ols.rsquared:.2f}; each extra day of refund cycle = {slope:+.4f} contacts per return')\n"
         "print(f'excess contacts in report week attributable to the cycle-time rise: {excess_contacts:,.0f}')"),
    md("## 5. Improve: sized options\n\n"
       "* Option A fixes the cause: get US Mail-in transit back to baseline through the carrier SLA review (M305) "
       "and escalate R05, which still has no mitigation owner.\n"
       "* Option B protects customers while A lands: refund low-risk US Mail-in customers at the first carrier scan "
       "(the same pattern returnless refunds already use). They then wait only for the scan, not the linehaul. "
       "The Risk partner has to sign off on an abuse guardrail first.\n"
       "* Option C is the structural one: unblock drop-off Wave 2 (M304), which is waiting on the QR label API (M402).\n\n"
       "For the dollar sizing I assumed $4.50 handling cost per customer contact. That's a placeholder, not a measured "
       "number, and should be swapped for the finance partner's rate."),
    code("COST_PER_CONTACT = 4.50  # planning assumption\n"
         "top = drv.sort_values('total_effect_days', ascending=False).iloc[0]\n"
         "cycle_if_restored = cur.refund_cycle_days - top.total_effect_days\n"
         "# Option B: US Mail-in customers refunded at carrier scan -> their wait = processing at origin scan ~ 0.25 d (returnless-like)\n"
         "us_share = top.share_cur\ncycle_if_scan_refund = cur.refund_cycle_days - us_share * (top.days_cur - 0.25)\n"
         "weekly_contact_cost = excess_contacts * COST_PER_CONTACT\n"
         "out = pd.DataFrame([\n"
         "    ['report_week', WEEK],\n"
         "    ['refund_cycle_days_current', round(cur.refund_cycle_days, 4)],\n"
         "    ['refund_cycle_target', 3.30],\n"
         "    ['baseline_cycle_days_program', round(base_days, 4)],\n"
         "    ['program_change_days', round(drv.total_effect_days.sum(), 4)],\n"
         "    ['top_driver_segment', f'{top.marketplace} {top.channel}'],\n"
         "    ['top_driver_effect_days', round(top.total_effect_days, 4)],\n"
         "    ['top_driver_days_base', round(top.days_base, 4)],\n"
         "    ['top_driver_days_cur', round(top.days_cur, 4)],\n"
         "    ['top_driver_transit_change_days', round(top.transit_change, 4)],\n"
         "    ['top_driver_processing_change_days', round(top.processing_change, 4)],\n"
         "    ['top_driver_volume_share', round(top.share_cur, 4)],\n"
         "    ['control_chart_ucl_days', round(ucl, 4)],\n"
         "    ['first_week_above_ucl', str(first_signal.date())],\n"
         "    ['contacts_per_day_slope', round(slope, 4)],\n"
         "    ['ols_r2', round(ols.rsquared, 4)],\n"
         "    ['excess_contacts_week', round(excess_contacts)],\n"
         "    ['assumed_cost_per_contact_usd', COST_PER_CONTACT],\n"
         "    ['excess_contact_cost_week_usd', round(weekly_contact_cost)],\n"
         "    ['excess_contact_cost_annualized_usd', round(weekly_contact_cost * 52)],\n"
         "    ['cycle_days_if_us_mailin_restored', round(cycle_if_restored, 4)],\n"
         "    ['cycle_days_if_us_mailin_refund_at_scan', round(cycle_if_scan_refund, 4)],\n"
         "], columns=['metric', 'value'])\n"
         "out.to_csv(OUT / 'driver_analysis_summary.csv', index=False)\nout"),
    md("## 6. Control\n\n"
       "* Add the control-chart rule to the WBR: flag any week above the UCL for refund cycle time at the "
       "marketplace x channel grain. A single-segment shift would then show up in week 1 instead of after the "
       "program KPI has already crossed target.\n"
       "* Track transit and processing days separately in the dashboard (calculated fields in `dashboard/dashboard_spec.md`).\n"
       "* Keep R05 on the WBR risk table until US Mail-in transit is back within the baseline control limits for 2 consecutive weeks."),
    code("con.close()"),
]


def main():
    import asyncio
    import sys
    if sys.platform == "win32":  # zmq needs a selector event loop on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    NOTEBOOKS.mkdir(parents=True, exist_ok=True)
    nb = nbf.v4.new_notebook()
    nb["cells"] = CELLS
    nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(NOTEBOOKS)}}).execute()
    path = NOTEBOOKS / "analysis.ipynb"
    nbf.write(nb, path)
    print(f"make_notebook: executed {path.name} ({len(CELLS)} cells)")


if __name__ == "__main__":
    main()
