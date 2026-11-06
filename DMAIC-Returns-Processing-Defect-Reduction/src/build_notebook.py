"""Create notebooks/analysis.ipynb and execute it in place with nbclient (kernel: python3)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "analysis.ipynb"

CELLS = [
    ("md", """# Returns disposition defects: DMAIC analysis notebook

This steps through the Measure, Analyze, Improve and Control work. All data is synthetic (made by
`src/generate_data.py`). None of it comes from Amazon or any employer. Run `python src/run_all.py` first so
`data/returns_dmaic.db` exists, since the notebook reads from it."""),
    ("code", """import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf
from statsmodels.stats.proportion import proportions_ztest

ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()
con = sqlite3.connect(ROOT / 'data' / 'returns_dmaic.db')
sql = lambda name: pd.read_sql_query((ROOT / 'sql' / name).read_text(), con)
pd.set_option('display.width', 140)"""),
    ("md", "## Measure: data quality and baseline (DPMO, sigma, first-pass yield)"),
    ("code", "pd.read_csv(ROOT / 'data' / 'processed' / 'data_quality_log.csv')"),
    ("code", "sql('02_baseline_defect_rate_dpmo_sigma.sql')"),
    ("code", """ct = sql('05_cycle_time_percentiles.sql')
ct.pivot(index='month', columns='site_id', values='p90_hrs')"""),
    ("md", "## Analyze: Pareto and stratification"),
    ("code", """par = sql('03_defect_pareto_by_cause.sql')
fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(par.defect_cause, par.defects, color='#1f3b57')
ax2 = ax.twinx(); ax2.plot(par.defect_cause, par.cumulative_share * 100, color='#f4a261', marker='o')
ax2.set_ylim(0, 105); ax.tick_params(axis='x', rotation=30)
ax.set_title('Baseline defects by cause'); plt.tight_layout(); plt.show()
par"""),
    ("code", """seg = sql('04_defect_rate_by_segment.sql')
seg[seg.dimension.isin(['Shift', 'Tenure band', 'Site', 'Photo step done'])]"""),
    ("md", "### Root-cause check: logistic regression on baseline audits"),
    ("code", """aud = pd.read_sql_query('SELECT * FROM v_audited', con)
b = aud[aud.phase == 'Baseline'].assign(
    tenure_lt30=lambda d: (d.tenure_days < 30).astype(int),
    tenure_30_89=lambda d: d.tenure_days.between(30, 89).astype(int),
    electronics=lambda d: (d.category == 'Electronics').astype(int),
    true_open_box=lambda d: (d.audited_disposition == 'OPEN_BOX').astype(int),
    night_shift=lambda d: (d['shift'] == 'Night').astype(int),
    swing_shift=lambda d: (d['shift'] == 'Swing').astype(int),
    no_photo_step=lambda d: (d.photo_step_done == 0).astype(int),
    peak_backlog_dec_jan=lambda d: d.month.isin(['2025-12', '2026-01']).astype(int))
fit = smf.logit('is_defect ~ tenure_lt30 + tenure_30_89 + electronics + true_open_box + night_shift + swing_shift'
                ' + no_photo_step + peak_backlog_dec_jan', data=b).fit(disp=False)
pd.DataFrame({'odds_ratio': np.exp(fit.params), 'p_value': fit.pvalues}).round(4)"""),
    ("code", "sql('10_value_stream_stage_times.sql')"),
    ("md", "## Improve: pilot at RC-CENTRAL vs comparison sites (two-proportion z-test)"),
    ("code", "sql('08_pilot_pre_post.sql')"),
    ("code", """def ztest(after, before):
    d = [aud.loc[after, 'is_defect'].sum(), aud.loc[before, 'is_defect'].sum()]
    n = [after.sum(), before.sum()]
    z, p = proportions_ztest(d, n, alternative='smaller')
    return {'rate_after': d[0] / n[0], 'rate_before': d[1] / n[1], 'z': z, 'p_value': p}

pilot = aud.is_pilot_site == 1
pd.DataFrame({
    'Pilot site: pilot vs baseline': ztest(pilot & (aud.phase == 'Pilot'), pilot & (aud.phase == 'Baseline')),
    'Comparison sites: same windows': ztest(~pilot & (aud.phase == 'Pilot'), ~pilot & (aud.phase == 'Baseline')),
    'Network: control vs baseline': ztest(aud.phase == 'Control', aud.phase == 'Baseline'),
}).T"""),
    ("md", "## Control: p-chart with recalculated limits"),
    ("code", """w = sql('09_weekly_control_chart_feed.sql')
w = w[w.partial_week_flag == 0].copy()
w['week_start'] = pd.to_datetime(w.week_start)
for ph in ['Baseline', 'Control']:
    g = w[w.phase == ph]
    w.loc[w.phase == ph if ph == 'Control' else w.phase != 'Control', 'pbar'] = g.defects.sum() / g.audited_units.sum()
w['ucl'] = w.pbar + 3 * np.sqrt(w.pbar * (1 - w.pbar) / w.audited_units)
w['lcl'] = (w.pbar - 3 * np.sqrt(w.pbar * (1 - w.pbar) / w.audited_units)).clip(lower=0)
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(w.week_start, w.defect_rate, marker='o', color='#1f3b57')
ax.step(w.week_start, w.ucl, where='mid', color='#d62828', ls='--'); ax.step(w.week_start, w.lcl, where='mid', color='#d62828', ls='--')
ax.plot(w.week_start, w.pbar, color='#2d6a4f'); ax.set_title('Weekly defect rate p-chart'); plt.show()
w.groupby('phase')[['audited_units', 'defects']].sum().assign(rate=lambda d: d.defects / d.audited_units)"""),
    ("code", "pd.read_csv(ROOT / 'data' / 'processed' / 'capability.csv').round(3)"),
    ("code", "pd.read_csv(ROOT / 'data' / 'processed' / 'impact_summary.csv')"),
    ("md", """## What this shows

- The Measure tables give the baseline defect rate, DPMO and sigma, and the Pareto shows which causes lead.
- In the logistic regression, tenure under 30 days, open-box items, Electronics, no photo step, night shift and the Dec-Jan backlog all raise the odds of a misgrade.
- Testing the comparison sites over the same weeks is what separates the SOP fix from seasonality.
- The Control-period p-chart and capability table show the gain holding. The ongoing checks are in `docs/06_Control_Plan.md`."""),
]


def main() -> None:
    if sys.platform == "win32":  # zmq warns under the default Proactor loop on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    NB.parent.mkdir(exist_ok=True)
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.cells = [nbformat.v4.new_markdown_cell(s) if k == "md" else nbformat.v4.new_code_cell(s) for k, s in CELLS]
    NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(NB.parent)}}).execute()
    nbformat.write(nb, NB)
    print(f"executed {NB}")


if __name__ == "__main__":
    main()
