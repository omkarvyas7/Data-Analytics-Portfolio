"""Create notebooks/analysis.ipynb and execute it in place with nbclient."""
import asyncio
import sys

import nbformat
from nbclient import NotebookClient
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

from config import NOTEBOOK

CELLS = [
    ("md", "# Returns Abuse and Bad Debt Analysis\n"
           "Which return behaviors drive refund abuse and bad debt, and which policy changes cut losses "
           "without hurting good customers?\n\nThe data is synthetic (src/generate_data.py). This notebook reads "
           "the SQLite database and query outputs that `src/run_all.py` builds."),
    ("code", "import sys, json, sqlite3\nfrom pathlib import Path\nimport pandas as pd\n"
             "import matplotlib.pyplot as plt\n"
             "ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\n"
             "sys.path.insert(0, str(ROOT / 'src'))\n"
             "PROC = ROOT / 'data' / 'processed'\n"
             "con = sqlite3.connect(ROOT / 'data' / 'returns.db')\n"
             "pd.set_option('display.width', 160)\n"
             "m = json.loads((PROC / 'metrics.json').read_text())"),
    ("md", "## 1. Measure: data quality and program health"),
    ("code", "pd.read_csv(PROC / '01_data_quality_checks.csv')"),
    ("code", "rr = pd.read_csv(PROC / '03_return_rate_by_category_month.csv')\n"
             "cat = rr.groupby('category')[['orders','returns','loss_dollars']].sum()\n"
             "cat['return_rate'] = (cat['returns'] / cat['orders']).round(4)\n"
             "cat.sort_values('return_rate', ascending=False)"),
    ("code", "mon = rr.groupby('order_month')[['orders','returns']].sum()\n"
             "ax = (mon['returns'] / mon['orders'] * 100).plot(figsize=(9,3.5), marker='o', color='#232F3E')\n"
             "ax.set_ylabel('Return rate %'); ax.set_title('Return rate by order month (Q4 peak)'); plt.show()"),
    ("code", "pd.read_csv(PROC / '04_return_reason_condition_mix.csv')"),
    ("md", "## 2. Refund cycle time and bad debt"),
    ("code", "ct = pd.read_csv(PROC / '05_refund_cycle_time.csv')\nct.pivot(index='request_quarter', columns='refund_type', values='avg_days_request_to_refund')"),
    ("code", "bd = pd.read_csv(PROC / '06_bad_debt.csv')\nbd[bd.refund_month == 'TOTAL']"),
    ("md", "## 3. Analyze: risk features, score and tiers\n"
           "Features only use activity before 2025-07-01 (the scoring window). The 90-day rolling return rate "
           "is a SQL window function with a `RANGE BETWEEN 89 PRECEDING AND CURRENT ROW` frame over order day."),
    ("code", "pd.read_csv(PROC / '07_customer_risk_features.csv')"),
    ("code", "pd.read_sql_query('''SELECT risk_tier, risk_score, COUNT(*) AS customers FROM customer_risk\n"
             "GROUP BY 1, 2 ORDER BY 2 DESC''', con).head(12)"),
    ("code", "pd.read_csv(PROC / '09_tier_outcomes_validation.csv')"),
    ("md", "## 4. Statistical validation (held-out Jul-Dec 2025)"),
    ("code", "import stats_analysis\ndf = stats_analysis.load()\ntests, chi2, p = stats_analysis.tier_tests(df)\ntests.round(4)"),
    ("code", "model, ors = stats_analysis.logit(df)\nprint(model.summary2().tables[0].to_string(header=False, index=False))\nors.round(3)"),
    ("code", "auc = stats_analysis.auc(df['risk_score'].values, df['perf_loss_event'].values)\n"
             "print(f'Score AUC on held-out window: {auc:.3f}')\n"
             "print(f\"Loss-event rate High vs Low: {m['high_loss_event_rate']}% vs {m['low_loss_event_rate']}%\")"),
    ("md", "Every rule flag has an odds ratio above 1, and none of the confidence intervals include 1, so each "
           "rule earns its points. The address-cluster and condition-mismatch rules carry the most weight. "
           "The AUC above says the score ranks risk moderately well. That's fine for a rules-based tier that "
           "routes customers to a slower refund flow. It wouldn't be good enough to deny anyone service."),
    ("md", "## 5. Improve: abuse patterns and policy simulation"),
    ("code", "pd.read_csv(PROC / '12_abuse_patterns.csv')"),
    ("code", "pol = pd.read_csv(PROC / '11_policy_simulation.csv')\n"
             "pol[['scenario','dollars_saved','pct_of_baseline_loss','good_customers_affected','pct_good_customers_affected']]"),
    ("code", "p = pol[pol.scenario_id > 0]\nfig, ax = plt.subplots(figsize=(8,4))\n"
             "ax.scatter(p.pct_good_customers_affected, p.dollars_saved/1000, s=80, color='#232F3E')\n"
             "for _, r in p.iterrows():\n    ax.annotate(r.scenario.split(' ')[0], (r.pct_good_customers_affected, r.dollars_saved/1000),\n"
             "                xytext=(5,3), textcoords='offset points')\n"
             "ax.set_xscale('symlog', linthresh=1); ax.set_xlabel('% of good customers affected')\n"
             "ax.set_ylabel('$k saved'); ax.set_title('Savings vs good-customer impact'); plt.show()"),
    ("code", "pd.read_csv(PROC / '10_cohort_view.csv')"),
    ("md", "## 6. Recommendation\nGo with S7: refund-on-receipt for the High tier, a restocking fee on repeat "
           "no-longer-needed returns, and investigation of INR claims at cluster addresses. It saves about 15% "
           "of loss dollars and touches roughly 1% of good customers. S4 saves more, but it slows refunds for "
           "nearly a quarter of good customers. More detail in docs/Policy_Recommendation_Memo.md."),
    ("code", "print(f\"S7 saved ${m['s7_saved']:,.0f} ({m['s7_pct_loss']}% of loss), good customers affected {m['s7_pct_good']}%\")\n"
             "print(f\"S4 saved ${m['s4_saved']:,.0f} ({m['s4_pct_loss']}% of loss), good customers affected {m['s4_pct_good']}%\")\n"
             "con.close()"),
]


def main():
    if sys.platform == "win32":  # zmq needs a selector event loop on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    nb = new_notebook()
    nb.cells = [new_markdown_cell(s) if t == "md" else new_code_cell(s) for t, s in CELLS]
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    client = NotebookClient(nb, timeout=600, kernel_name="python3",
                            resources={"metadata": {"path": str(NOTEBOOK.parent)}})
    client.execute()
    nbformat.write(nb, NOTEBOOK)
    print(f"executed {NOTEBOOK}")


if __name__ == "__main__":
    main()
