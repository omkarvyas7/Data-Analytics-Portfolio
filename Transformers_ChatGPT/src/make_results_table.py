"""Render a summary table of the notebook's results to screenshots/results_summary.png.

Values are copied from the saved outputs of notebooks/Transformers.ipynb
(run in Google Colab with transformers 4.25.1 and flair 0.12.1). The models are not re-run here.

Run:  python src/make_results_table.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]

ROWS = [
    ("Sentiment analysis", '"I like NLP course."', "POSITIVE", "0.999"),
    ("Sentiment analysis", '"I hate when my computer crashes."', "NEGATIVE", "0.999"),
    ("Zero-shot classification", '"Los Angeles Clippers is a good basketball team"', "sports", "0.997"),
    ("Fill-mask", '"Math course will teach you about <mask> topics"', "mathematical", "0.182"),
    ("Named entity recognition", '"Tim Cook is the CEO of Apple located in San Jose."',
     "PER / ORG / LOC", "0.998+"),
    ("Question answering", '"In which state Los Angeles located"', "California", "0.984"),
    ("Word embeddings: 'bank'", "money bank vs river bank", "GloVe distance 0.0 / BERT 14.11", "n/a"),
]


def main() -> None:
    out = ROOT / "screenshots"
    out.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(13, 3.8))
    ax.axis("off")
    table = ax.table(cellText=[list(r) for r in ROWS],
                     colLabels=["Task", "Input", "Output", "Confidence"],
                     colWidths=[0.2, 0.45, 0.23, 0.1], loc="center", cellLoc="left")
    table.auto_set_font_size(False)
    table.set_fontsize(9.5)
    table.scale(1, 1.6)
    for (r, _), cell in table.get_celld().items():
        if r == 0:
            cell.set_text_props(fontweight="bold", color="white")
            cell.set_facecolor("#34495E")
        elif r % 2 == 0:
            cell.set_facecolor("#F2F4F6")
    ax.set_title("Hugging Face pipelines: results summary", fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(out / "results_summary.png", dpi=150)
    plt.close(fig)
    print("saved", out / "results_summary.png")


if __name__ == "__main__":
    main()
