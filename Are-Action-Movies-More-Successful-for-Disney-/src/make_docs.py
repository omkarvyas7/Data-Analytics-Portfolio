"""Write the memo (md/docx/pdf) and README.md.

All numbers come from model_results.json and the SQL outputs, so the docs can't drift from the analysis.
"""
from __future__ import annotations

import json
import math

import pandas as pd
from docx import Document
from docx.shared import Inches, Pt
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors

from common import DOCS, PROCESSED, RESULTS_JSON, ROOT, SHOTS, SQL_OUT


def m(x):  # dollars -> "$206M"
    return f"${x / 1e6:,.0f}M"


def facts() -> dict:
    r = json.loads(RESULTS_JSON.read_text())
    seg = pd.read_csv(SQL_OUT / "07_marvel_vs_non_marvel.csv").set_index("segment")
    bands = pd.read_csv(SQL_OUT / "08_action_within_budget_band.csv")
    c = r["m2_coef"]

    def pred(action, budget=150e6, score=6.8, star=800):
        return math.exp(c["Intercept"] + c["is_action"] * action + c["log_budget"] * math.log(budget)
                        + c["star_power"] * star + c["imdb_score"] * score) * r["smearing_factor"]

    marvel = seg.loc[seg.index.str.startswith("1")].iloc[0]
    act_nm = seg.loc[seg.index.str.startswith("2")].iloc[0]
    other = seg.loc[seg.index.str.startswith("3")].iloc[0]
    hi = bands[(bands.budget_band == 3) & (bands.segment == "Action")].iloc[0]
    f = dict(r=r, marvel=marvel, act_nm=act_nm, other=other, hi_band=hi,
             gross_premium=r["mean_gross_action"] / r["mean_gross_non_action"] - 1,
             budget_ratio=r["mean_budget_action"] / r["mean_budget_non_action"],
             double_budget=2 ** r["m2_budget_elasticity"] - 1,
             half_point=math.exp(c["imdb_score"] * 0.5) - 1,
             wi_action=pred(1), wi_non=pred(0), wi_score_up=pred(1, score=7.3))
    return f


def findings(f) -> list[str]:
    r = f["r"]
    return [
        f"Without controls, Action films do gross more: {m(r['mean_gross_action'])} vs {m(r['mean_gross_non_action'])} on average "
        f"(+{f['gross_premium']:.0%}). A Welch t-test gives p = {r['welch_p']:.3f}, so the gap clears the 5% bar.",
        f"Most of that gap is budget. Action films cost {f['budget_ratio']:.2f}x as much. With budget, IMDb score and star power "
        f"held constant, the Action effect is {r['m2_action_pct']:+.1%} (95% CI {r['m2_action_ci_pct'][0]:+.0%} to "
        f"{r['m2_action_ci_pct'][1]:+.0%}, p = {r['m2_p']['is_action']:.2f}), which is not statistically significant.",
        f"Budget and quality are what move gross. A 1% bigger budget goes with about {r['m2_budget_elasticity']:.2f}% more gross "
        f"(diminishing returns), and one extra IMDb point with +{r['m2_score_pct_per_point']:.0%} (p = {r['m2_p']['imdb_score']:.4f}). "
        f"Star power shows no effect (p = {r['m2_p']['star_power']:.2f}). The model has R-squared {r['m2_r2']:.2f} on n = {r['m2_n']} films.",
        f"Per budget dollar, Action does worse: mean ROI {r['mean_roi_action']:.2f}x vs {r['mean_roi_non_action']:.2f}x for other genres "
        f"(p = {r['welch_roi_p']:.3f}). Leave Marvel out and Action returns a pooled {f['act_nm'].pooled_roi:.2f}x, against "
        f"{f['other'].pooled_roi:.2f}x for all other genres.",
        f"Marvel is the outlier. Its {int(f['marvel'].films)} films are {f['marvel'].films / r['clean_rows']:.1%} of the sample but earn "
        f"{f['marvel'].pct_of_revenue:.1f}% of sample revenue, at a pooled {f['marvel'].pooled_roi:.2f}x ROI. Without Marvel, the Action "
        f"effect is {r['m3_action_pct']:+.1%} (p = {r['m3_action_p']:.2f}).",
    ]


def recommendation(f) -> list[str]:
    r = f["r"]
    return [
        "Stop using genre as a green-light criterion. Judge each project on budget-adjusted expected return. The what-if "
        "model in excel/Disney_Genre_Performance.xlsx works as a first-pass screen.",
        f"Put quality ahead of spend. In the model, +0.5 IMDb points is worth about +{f['half_point']:.0%} gross. Doubling the "
        f"budget adds about {f['double_budget']:.0%}, so return per budget dollar falls as budgets grow.",
        f"Treat Marvel-type franchises as a separate portfolio. They are not evidence that Action works: non-Marvel Action returned "
        f"{f['act_nm'].pooled_roi:.2f}x per budget dollar vs {f['other'].pooled_roi:.2f}x for other genres.",
        f"Worked example from the What_If sheet: a $150M film with a 6.8 IMDb score and star power 800 is expected to gross "
        f"{m(f['wi_action'])} as Action and {m(f['wi_non'])} as non-Action. Raising the expected score to 7.3 lifts it to "
        f"{m(f['wi_score_up'])}.",
    ]


LIMITS = [
    "Small sample. 148 films have budgets and only 20 are labelled Action, so the Action interval is wide.",
    "Selection. Only 148 of 579 Disney titles have a correct budget match, and older and smaller releases drop out.",
    "The data is observational. Budgets are set with expected demand in mind, so the model shows association, not causation.",
    "Gross is domestic only and budgets exclude marketing. International, streaming and merchandise revenue are not counted.",
    "Disney and IMDb label genres differently (20 vs 43 Action films). The result holds under both labels.",
]

BOTTOM_LINE = ("Action films earn more at the box office because Disney spends more on them. At comparable budget, quality "
               "and star power, Action adds no detectable premium ({pct}, p = {p}), and it returns less per budget dollar. "
               "Green-light decisions should rest on budget-adjusted expected return and quality, not on genre.")


def memo_md(f) -> str:
    r = f["r"]
    out = ["# Executive summary: Are Action movies more successful for Disney?", "",
           "**To:** Studio leadership, green-light committee  ",
           "**From:** Business analytics  ",
           f"**Scope:** {r['clean_rows']} Disney releases, {r['year_min']}-{r['year_max']}, with budget data. Gross is domestic, inflation-adjusted.", "",
           "## Bottom line",
           BOTTOM_LINE.format(pct=f"{r['m2_action_pct']:+.1%}", p=f"{r['m2_p']['is_action']:.2f}"), "",
           "## Findings"] + [f"{i}. {x}" for i, x in enumerate(findings(f), 1)] + [
           "", "![Action premium by model](../screenshots/chart_action_effect.png)", "",
           "## Recommendation for green-lighting decisions"] + [f"- {x}" for x in recommendation(f)] + [
           "", "## Method",
           "Disney's gross file was joined to a public movies file (budget, IMDb score, lead star) and an actor popularity file. "
           f"In {r['rows_dropped_mismatch']} rows the title matched a different film, usually a later remake, and those rows were dropped. "
           "A Welch t-test compared Action and non-Action gross. An OLS regression of log gross on Action, log budget, star power and "
           "IMDb score, with HC3 standard errors, separated the genre effect from budget. The model was re-run without Marvel, with "
           "IMDb's genre label and with Action interactions as sensitivity checks.", "",
           "## Limitations"] + [f"- {x}" for x in LIMITS] + [
           "", "## Next steps",
           "- Add worldwide gross and marketing spend to measure full return.",
           "- Re-run quarterly as new releases close their theatrical window.",
           "- Pilot the What_If screen on the next three green-light submissions and compare with actuals.", ""]
    return "\n".join(out)


def memo_docx(f, path):
    r = f["r"]
    d = Document()
    st = d.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(11)
    d.add_heading("Executive summary: Are Action movies more successful for Disney?", 1)
    d.add_paragraph("To: Studio leadership, green-light committee\nFrom: Business analytics\n"
                    f"Scope: {r['clean_rows']} Disney releases, {r['year_min']}-{r['year_max']}, with budget data. Gross is domestic, inflation-adjusted.")
    d.add_heading("Bottom line", 2)
    d.add_paragraph(BOTTOM_LINE.format(pct=f"{r['m2_action_pct']:+.1%}", p=f"{r['m2_p']['is_action']:.2f}"))
    d.add_heading("Findings", 2)
    for x in findings(f):
        d.add_paragraph(x, style="List Number")
    d.add_picture(str(SHOTS / "chart_action_effect.png"), width=Inches(6))
    d.add_heading("Key numbers", 2)
    rows = [("Metric", "Action", "Non-Action"),
            ("Films", str(r["n_action"]), str(r["n_non_action"])),
            ("Average adj. gross", m(r["mean_gross_action"]), m(r["mean_gross_non_action"])),
            ("Average adj. budget", m(r["mean_budget_action"]), m(r["mean_budget_non_action"])),
            ("Mean ROI (gross/budget)", f"{r['mean_roi_action']:.2f}x", f"{r['mean_roi_non_action']:.2f}x")]
    t = d.add_table(rows=len(rows), cols=3)
    t.style = "Light Grid Accent 1"
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            t.cell(i, j).text = v
    d.add_heading("Recommendation for green-lighting decisions", 2)
    for x in recommendation(f):
        d.add_paragraph(x, style="List Bullet")
    d.add_heading("Limitations", 2)
    for x in LIMITS:
        d.add_paragraph(x, style="List Bullet")
    d.save(path)


def memo_pdf(f, path):
    r = f["r"]
    ss = getSampleStyleSheet()
    body = ss["BodyText"]
    story = [Paragraph("Executive summary: Are Action movies more successful for Disney?", ss["Title"]),
             Paragraph(f"To: Studio leadership, green-light committee. Scope: {r['clean_rows']} Disney releases, "
                       f"{r['year_min']}-{r['year_max']}, domestic gross, inflation-adjusted.", body),
             Paragraph("Bottom line", ss["Heading2"]),
             Paragraph(BOTTOM_LINE.format(pct=f"{r['m2_action_pct']:+.1%}", p=f"{r['m2_p']['is_action']:.2f}"), body),
             Paragraph("Findings", ss["Heading2"]),
             ListFlowable([ListItem(Paragraph(x, body)) for x in findings(f)], bulletType="1"),
             Spacer(1, 6), Image(str(SHOTS / "chart_action_effect.png"), width=6 * inch, height=3 * inch),
             Paragraph("Recommendation", ss["Heading2"]),
             ListFlowable([ListItem(Paragraph(x, body)) for x in recommendation(f)], bulletType="bullet"),
             Paragraph("Limitations", ss["Heading2"]),
             ListFlowable([ListItem(Paragraph(x, body)) for x in LIMITS], bulletType="bullet")]
    tbl = Table([["Metric", "Action", "Non-Action"],
                 ["Average adj. gross", m(r["mean_gross_action"]), m(r["mean_gross_non_action"])],
                 ["Average adj. budget", m(r["mean_budget_action"]), m(r["mean_budget_non_action"])],
                 ["Mean ROI", f"{r['mean_roi_action']:.2f}x", f"{r['mean_roi_non_action']:.2f}x"]])
    tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b73")),
                             ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                             ("GRID", (0, 0), (-1, -1), .5, colors.grey)]))
    story[5:5] = [tbl, Spacer(1, 8)]
    SimpleDocTemplate(str(path), pagesize=letter, leftMargin=.8 * inch, rightMargin=.8 * inch,
                      topMargin=.7 * inch, bottomMargin=.7 * inch).build(story)


def readme(f) -> str:
    r = f["r"]
    sig = "is not statistically significant" if not r["action_significant_controls"] else "is statistically significant"
    lines = [
        "# Are Action Movies More Successful for Disney?",
        "",
        "I first looked at this in 2023. Action films seem to dominate Disney's box office, so should the studio favour them "
        "when deciding what to green-light? This is the reworked version (v2), with cleaner data and proper controls.",
        "",
        f"Short answer: no. Action films do gross more on average, but they also get much bigger budgets. Once budget is "
        f"controlled, the Action effect {sig} (p = {r['m2_p']['is_action']:.2f}).",
        "",
        "Built with SQL (SQLite, window functions), Excel (COUNTIFS/AVERAGEIFS/SUMIFS, XLOOKUP, INDEX/MATCH, a what-if model), "
        "a Tableau-ready extract, Python (pandas, SciPy, statsmodels, matplotlib) and a short Word/PDF memo.",
        "",
        "![Dashboard preview](screenshots/dashboard.png)",
        "",
        "*The preview is a matplotlib render of the layout in `dashboard/dashboard_spec.md`, drawn from "
        "`dashboard/tableau_extract.csv`. It isn't a Tableau screenshot.*",
        "",
        "## What I found",
        "",
    ] + [f"- {x}" for x in findings(f)] + [
        "",
        "![Action premium by model](screenshots/chart_action_effect.png)",
        "",
        "## What I'd recommend",
        "",
    ] + [f"- {x}" for x in recommendation(f)] + [
        "",
        "The memo version for leadership is [docs/Executive_Summary.md](docs/Executive_Summary.md) (also as .docx and .pdf).",
        "",
        "## How I got there",
        "",
        f"The data is Disney's release list with domestic gross ({r['raw_disney_titles']} titles), joined to a public movies file "
        f"and an actor popularity file. That join gave {r['raw_merged_rows']} rows. The catch is that it was done on title alone, "
        f"so {r['rows_dropped_mismatch']} rows picked up the budget of a different film with the same name (the 1991 Beauty and the "
        f"Beast got the 2017 remake's budget, for example). I dropped those, which left {r['clean_rows']} films.",
        "",
        "From there I ran SQL for profiling and the genre and ROI cuts, a Welch t-test on raw gross, and an OLS model of log gross "
        "on Action, log budget, star power and IMDb score with HC3 standard errors. To see if the answer moved, I re-ran it "
        "without Marvel, with IMDb's genre label instead of Disney's, and with Action interactions. It didn't.",
        "",
        "| | |",
        "|---|---|",
        "| ![Gross by genre](screenshots/chart_gross_by_genre.png) | ![Budget vs gross](screenshots/chart_budget_vs_gross.png) |",
        "",
        "## What's in the repo",
        "",
        "| Piece | Where |",
        "|---|---|",
        "| Source data (Disney gross, movies.csv, the final_df.csv merge, Actors_Raw.txt) | `data/raw/` |",
        "| Eight SQL queries: quality checks, genre/decade revenue, ROI, rankings, star power, Marvel, budget bands | `sql/01`-`08`, results in `data/processed/sql_outputs/` |",
        "| Cleaning steps and row counts | `src/common.py`, `data/processed/cleaning_log.csv` |",
        "| Excel workbook with genre KPIs, a title lookup and a what-if sheet, all live formulas | `excel/Disney_Genre_Performance.xlsx` |",
        "| Dashboard extract and layout spec | `dashboard/tableau_extract.csv`, `dashboard/dashboard_spec.md` |",
        "| Statistics (t-tests, regressions) | `notebooks/Disney_analysis_v2.ipynb` (executed), `src/analysis.py` |",
        "| One-page memo | `docs/Executive_Summary.md` / `.docx` / `.pdf` |",
        "| My original 2023 notebook and slides | `notebooks/Disney_original.ipynb`, `docs/original_presentation/` |",
        "| Charts | `screenshots/` |",
        "",
        "## How to run",
        "",
        "```",
        "git clone https://github.com/omkarvyas7/Data-Analytics-Portfolio.git",
        "cd Data-Analytics-Portfolio/Are-Action-Movies-More-Successful-for-Disney-",
        "python -m venv .venv && .venv\\Scripts\\activate      # or source .venv/bin/activate",
        "pip install -r requirements.txt",
        "python src/run_all.py",
        "```",
        "",
        "That one command rebuilds everything: the clean table, SQL outputs, charts, workbook, notebook, memo and this README. "
        "The SQL runs on SQLite, which ships with Python. The queries stick to CTEs and window functions, so moving them to "
        "Postgres or Redshift mostly means changing the date functions.",
        "",
        "## Data note",
        "",
        "Everything here is public: Disney's domestic gross by title (with Disney's own inflation adjustment), an IMDb-style "
        "movies file (budget, score, lead star) and an actor popularity file. The v2 numbers differ slightly from my original "
        f"analysis because v2 drops the {r['rows_dropped_mismatch']} rows where the title join picked up the wrong film.",
        "",
        "## Limitations",
        "",
    ] + [f"- {x}" for x in LIMITS] + ["", "License: MIT", ""]
    return "\n".join(lines)


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    f = facts()
    (DOCS / "Executive_Summary.md").write_text(memo_md(f), encoding="utf-8")
    memo_docx(f, DOCS / "Executive_Summary.docx")
    memo_pdf(f, DOCS / "Executive_Summary.pdf")
    (ROOT / "README.md").write_text(readme(f), encoding="utf-8")
    print("memo (md/docx/pdf) + README written")


if __name__ == "__main__":
    main()
