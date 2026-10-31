"""Figures scientifiques autonomes : SVG, PDF et PNG ; outils isolés dans /tmp."""

import gzip
import json
import os
import sys

from common import HERE, read

os.environ["MPLCONFIGDIR"] = "/tmp/multicorpus-scale-mpl"
sys.path.insert(0, "/tmp/multicorpus-scale-plot-tools")
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

CASES = [
    ("q01", 203, "Pierrelez · impôts"),
    ("q02", 258, "Albertas · répartition"),
    ("q06", 196, "Ermenonville · procédure"),
    ("q06", 268, "Beaurecueil · défense"),
    ("q07", 132, "Mirecourt · comptes"),
    ("q10", 158, "Ferrières · presse"),
    ("q13", 168, "Ferrières · gabelle"),
    ("q14", 116, "Montigny · OCR"),
]
METHODS = [
    ("lexical", None, "global", "Lexical", "#486f68"),
    ("vector", None, "global", "Vectoriel A", "#254f76"),
    ("hybrid", 50, "global", "RRF globale 50", "#ae482e"),
    ("hybrid", 50, "distributed_global_ranks", "Distribuée 50, rangs globaux", "#71578c"),
]


def save(fig, name):
    folder = HERE / "figures"
    folder.mkdir(exist_ok=True)
    for ext in ("svg", "pdf", "png"):
        fig.savefig(
            folder / f"{name}.{ext}",
            dpi=170,
            bbox_inches="tight",
            metadata={"Creator": "multicorpus-scale-study"} if ext == "pdf" else None,
        )
    plt.close(fig)


def axes_scale(ax, sizes):
    ax.set_xscale("log")
    ax.set_xticks(sizes, ["240", "1 k", "5 k", "20 k", "100 k", "1 M"])
    ax.set_xlabel("Réponses contemporaines ajoutées (269 historiques constants)")
    ax.grid(alpha=0.22)


def main():
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.titlesize": 12,
        }
    )
    sizes = read(HERE / "protocol.json")["stages"]
    summary = read(HERE / "data/summary.json")["growth"]
    track = [json.loads(x) for x in gzip.open(HERE / "data/witness-tracking.jsonl.gz", "rt")]
    # Raw exact ranks are not censored by candidate budgets.
    fig, ax = plt.subplots(figsize=(11, 6))
    for qid, g, label in CASES:
        values = [
            next(
                r["vector_rank"]
                for r in track
                if r["size"] == s
                and r["query_id"] == qid
                and r["g"] == g
                and r["method"] == "vector"
            )
            for s in sizes
        ]
        ax.plot(sizes, values, marker="o", label=label, linewidth=1.6)
    ax.set_yscale("log")
    ax.set_ylabel("Rang vectoriel exact (plus bas = mieux)")
    ax.set_title("Le score reste fixe ; le nombre de concurrents augmente")
    axes_scale(ax, sizes)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), frameon=False)
    save(fig, "01-witness-ranks")
    fig, axs = plt.subplots(2, 2, figsize=(12, 8), sharex=True, sharey=True)
    for ax, k in zip(axs.flat, (10, 20, 50, 100)):
        for method, depth, strategy, label, color in METHODS:
            values = [
                next(
                    r["recall_at"][str(k)]
                    for r in summary
                    if r["size"] == s
                    and r["method"] == method
                    and r["depth"] == depth
                    and r["strategy"] == strategy
                )
                * 100
                for s in sizes
            ]
            ax.plot(sizes, values, marker="o", label=label, color=color)
        axes_scale(ax, sizes)
        ax.set_title(f"Présents dans les {k} premiers résultats")
        ax.set_ylabel("Rappel des 270 couples témoins (%)")
        ax.set_ylim(0, 100)
    axs[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle("Rappel sur témoins connus — aucune estimation de rappel exhaustif", y=1.02)
    fig.tight_layout()
    save(fig, "02-known-witness-recall")
    fig, ax = plt.subplots(figsize=(10, 5))
    for method, depth, strategy, label, color in METHODS:
        values = [
            next(
                r["mean_historical_at"]["10"]
                for r in summary
                if r["size"] == s
                and r["method"] == method
                and r["depth"] == depth
                and r["strategy"] == strategy
            )
            for s in sizes
        ]
        ax.plot(sizes, values, marker="o", label=label, color=color)
    axes_scale(ax, sizes)
    ax.set_ylabel("Nombre moyen de résultats historiques dans le top 10")
    ax.set_ylim(0, 10)
    ax.set_title("Composition des premières pages — cette part ne mesure pas la pertinence")
    ax.legend(frameon=False)
    save(fig, "03-result-composition")
    fig, axs = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    depths = read(HERE / "protocol.json")["depths"]
    for ax, strategy, title in (
        (axs[0], "global", "Récupération globale"),
        (axs[1], "distributed_global_ranks", "Distribuée, rangs globaux (oracle expérimental)"),
    ):
        for key, label, style in (
            ("candidate_recall", "Dans les candidats", "-"),
            ("10", "Top 10", "--"),
            ("100", "Top 100", ":"),
        ):
            vals = []
            for d in depths:
                r = next(
                    r
                    for r in summary
                    if r["size"] == 1000000
                    and r["method"] == "hybrid"
                    and r["depth"] == d
                    and r["strategy"] == strategy
                )
                vals.append(100 * (r[key] if key == "candidate_recall" else r["recall_at"][key]))
            ax.plot(depths, vals, marker="o", linestyle=style, label=label)
        ax.set_xscale("log")
        ax.set_xticks(depths, [str(d) for d in depths])
        ax.set_xlabel("Candidats par branche (et par corpus si distribuée)")
        ax.set_title(title)
        ax.set_ylim(0, 105)
        ax.set_ylabel("Rappel des 270 couples témoins (%)")
        ax.grid(alpha=0.2)
        ax.legend(frameon=False)
    fig.suptitle("Au million : entrer dans les candidats ne garantit pas une place utile", y=1.03)
    fig.tight_layout()
    save(fig, "04-candidate-depth")
    from matplotlib.colors import BoundaryNorm, ListedColormap

    matrix = []
    for qid, g, label in CASES:
        row = []
        for s in sizes:
            r = next(
                r
                for r in track
                if r["size"] == s
                and r["query_id"] == qid
                and r["g"] == g
                and r["method"] == "hybrid"
                and r["depth"] == 50
                and r["strategy"] == "global"
            )
            rank = r["final_rank"]
            row.append(
                5
                if rank is None
                else 0
                if rank <= 10
                else 1
                if rank <= 20
                else 2
                if rank <= 50
                else 3
                if rank <= 100
                else 4
            )
        matrix.append(row)
    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ["#275e49", "#63a084", "#a8c5a8", "#dec995", "#bd9d87", "#eee8e1"]
    im = ax.imshow(
        matrix, cmap=ListedColormap(colors), norm=BoundaryNorm(np.arange(-0.5, 6), 6), aspect="auto"
    )
    ax.set_xticks(range(len(sizes)), ["240", "1 k", "5 k", "20 k", "100 k", "1 M"])
    ax.set_yticks(range(len(CASES)), [c[2] for c in CASES])
    ax.set_xlabel("Réponses contemporaines")
    ax.set_title("Accessibilité des témoins — RRF globale, 50 candidats par branche")
    for y, row in enumerate(matrix):
        for x, v in enumerate(row):
            ax.text(
                x,
                y,
                ["≤10", "≤20", "≤50", "≤100", ">100", "Absent des\ncandidats"][v],
                ha="center",
                va="center",
                fontsize=9,
                color="white" if v == 0 else "#252525",
            )
    bar = fig.colorbar(im, ax=ax, ticks=range(6))
    bar.ax.set_yticklabels(["Top 10", "11–20", "21–50", "51–100", ">100", "Non récupéré"])
    save(fig, "05-first-pages")
    print("Five figures exported asSVG,PDF,PNG")


if __name__ == "__main__":
    main()
