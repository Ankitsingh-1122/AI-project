from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_role
from ..models import (
    Feedback,
    Match,
    Problem,
    ProblemCluster,
    Team,
    User,
)
from ..ml.embed import get_shared_embedder
from ..ml import evaluate

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/statistics")
def statistics(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    problems = db.scalars(select(Problem)).all()
    total = len(problems)
    duplicates = sum(1 for p in problems if p.is_duplicate)
    by_status: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for p in problems:
        by_status[p.status] = by_status.get(p.status, 0) + 1
        by_category[p.category] = by_category.get(p.category, 0) + 1
    clusters = db.scalars(select(ProblemCluster)).all()
    matches = db.scalars(select(Match)).all()
    match_status = {"suggested": 0, "accepted": 0, "rejected": 0}
    for m in matches:
        match_status[m.status] = match_status.get(m.status, 0) + 1
    feedback = db.scalars(select(Feedback)).all()
    fb_type: dict[str, int] = {}
    for f in feedback:
        fb_type[f.feedback_type] = fb_type.get(f.feedback_type, 0) + 1
    return {
        "total_problems": total,
        "unique_problems": total - duplicates,
        "duplicate_reports": duplicates,
        "by_status": by_status,
        "by_category": by_category,
        "clusters": len(clusters),
        "registered_teams": db.scalars(select(Team)).all().__len__(),
        "registered_users": db.scalars(select(User)).all().__len__(),
        "total_recommendations": len(matches),
        "match_status": match_status,
        "feedback_count": len(feedback),
        "feedback_by_type": fb_type,
    }


@router.get("/model-performance")
def model_performance(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    embedder = get_shared_embedder()
    threshold = evaluate.get_tuned_threshold(db, settings.DEDUP_THRESHOLD)
    result = evaluate.run_full_evaluation(db, threshold, embedder)
    result["configured_embedder"] = settings.EMBEDDER
    result["embedder_in_use"] = embedder.name
    # Real-data labelling status (the models above train ONLY from these
    # human labels; see scripts/train_dedup.py + scripts/train_ranker.py).
    from .labels import label_status

    result["labeling"] = label_status(db)
    result["data_provenance"] = "REAL Chicago + NYC 311 open data; labels are " \
        "human-entered in the Data & Labels section — no synthetic data or " \
        "auto-generated labels (backend/data/real/provenance.md)"
    return result


# ---- Seaborn / matplotlib rendered analytics (PNG) -------------------------
# Rendered server-side with matplotlib + seaborn, served as PNG images so the
# frontend can embed them without any chart-library changes. Charts accept a
# `theme` query param (light/dark) so text stays readable in both app themes.

import io
from collections import Counter
from datetime import datetime, timedelta

import matplotlib

matplotlib.use("Agg")  # headless server rendering
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from fastapi import HTTPException
from fastapi.responses import Response

# Palette policy:
#   * categorical comparisons (categories) -> seaborn's built-in categorical
#     palette "muted" (colorblind-safe, professional, consistent across charts)
#   * statuses -> the same fixed hues the UI badges use, so a status keeps one
#     color everywhere (legend == UI). Light/dark variants keep contrast.
#   * timeline -> two fixed series colors (primary indigo / warning amber).
# These data are counts/labels (categorical), so no sequential or diverging
# scales are used — that guidance applies only to continuous data.

CAT_PALETTE = sns.color_palette("muted", as_cmap=False)
STATUS_LIGHT = {"open": "#4f46e5", "in_review": "#d97706", "assigned": "#7c3aed", "resolved": "#16a34a"}
STATUS_DARK = {"open": "#818cf8", "in_review": "#fbbf24", "assigned": "#a78bfa", "resolved": "#4ade80"}
SERIES_COLORS_LIGHT = {"Cumulative problems": "#4f46e5", "Duplicates caught": "#d97706"}
SERIES_COLORS_DARK = {"Cumulative problems": "#818cf8", "Duplicates caught": "#fbbf24"}

# Per-theme ink/axis/grid colors (transparent figure; the app card is the surface).
THEMES = {
    "light": dict(text="#0f1522", muted="#5d6b82", grid="#0f172a24", spine="#cdd5e0"),
    "dark": dict(text="#f5f7fb", muted="#97a4bb", grid="#e7ecf529", spine="#33415e"),
}


def _apply_theme(theme: str) -> dict:
    c = THEMES.get(theme, THEMES["light"])
    sns.set_theme(
        style="ticks",
        context="talk",
        rc={
            "font.size": 11,
            "text.color": c["text"],
            "axes.labelcolor": c["muted"],
            "xtick.color": c["muted"],
            "ytick.color": c["muted"],
            "axes.edgecolor": c["spine"],
            "axes.facecolor": "none",
            "figure.facecolor": "none",
            "savefig.facecolor": "none",
            "grid.color": c["grid"],
            "legend.fontsize": 10,
        },
    )
    return c


def _render_png(fig) -> bytes:
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, transparent=True, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    return buf.getvalue()


def _status_palette(theme: str) -> dict:
    return STATUS_DARK if theme == "dark" else STATUS_LIGHT


def _bucketize(dates: list) -> tuple[list[datetime], str]:
    """Choose hourly/daily/weekly/monthly buckets so the chart has a readable
    number of points no matter how spread out the data is."""
    first, last = dates[0], dates[-1]
    span_days = max((last - first).total_seconds() / 86400.0, 1e-9)
    if span_days <= 1.5:
        step = timedelta(hours=1)
        start = first.replace(minute=0, second=0, microsecond=0)
        fmt = "%H:%M"
    elif span_days <= 21:
        step = timedelta(days=1)
        start = first.replace(hour=0, minute=0, second=0, microsecond=0)
        fmt = "%d %b"
    elif span_days <= 200:
        step = timedelta(weeks=1)
        start = first - timedelta(days=first.weekday())
        fmt = "%d %b"
    else:
        step = None
        start = first.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        fmt = "%b %Y"

    buckets: list[datetime] = []
    d = start
    if step is not None:
        while d <= last + step:
            buckets.append(d)
            d += step
    else:  # monthly
        y, m = start.year, start.month
        end = (last.year, last.month)
        while (y, m) <= end:
            buckets.append(datetime(y, m, 1))
            m += 1
            if m == 13:
                y, m = y + 1, 1
    # pad trailing empty buckets so short histories still read as a chart
    while len(buckets) < 5:
        if step is not None:
            buckets.append(buckets[-1] + step)
        else:
            y, m = buckets[-1].year, buckets[-1].month + 1
            if m == 13:
                y, m = y + 1, 1
            buckets.append(datetime(y, m, 1))
    return buckets, fmt


def _bucket_of(dt: datetime, bucket: datetime, step) -> bool:
    if step is None:
        return dt.year == bucket.year and dt.month == bucket.month
    if step >= timedelta(days=1):
        return dt.date() == bucket.date()
    return dt.replace(minute=0, second=0, microsecond=0) == bucket


def _chart_category(problems: list[Problem], theme: str) -> bytes:
    """Horizontal bar chart — a categorical comparison, so the seaborn
    categorical palette is mapped with hue= and no misleading value scale."""
    _apply_theme(theme)
    counts = Counter((p.category or "uncategorized").replace("_", " ") for p in problems)
    df = pd.DataFrame(
        sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])),
        columns=["category", "count"],
    )
    # "muted" gives 10 distinguishable colors; fall back to "colorblind" if the
    # data ever needs more.
    palette = CAT_PALETTE if len(df) <= len(CAT_PALETTE) else sns.color_palette("colorblind", as_cmap=False)
    fig, ax = plt.subplots(figsize=(7.6, max(3.4, 0.42 * len(df) + 1.6)))
    sns.barplot(
        data=df, x="count", y="category", hue="category",
        palette=list(palette)[: len(df)], legend=False, ax=ax,
    )
    ax.set_title("Problems by category", fontsize=13, fontweight="bold", loc="left", pad=12)
    ax.set_xlabel("Number of reports")
    ax.set_ylabel("")
    ax.xaxis.grid(True, alpha=0.55)
    ax.set_axisbelow(True)
    sns.despine(left=False)
    muted = THEMES.get(theme, THEMES["light"])["muted"]
    # label each bar at its own end (position-independent, handles any axis order)
    for patch, v in zip(ax.containers[0].patches, df["count"]):
        ax.text(patch.get_width() + max(df["count"]) * 0.02,
                patch.get_y() + patch.get_height() / 2, f"{int(v):,}",
                va="center", ha="left", fontsize=9.5, color=muted)
    return _render_png(fig)


def _chart_status(problems: list[Problem], theme: str) -> bytes:
    """Status distribution — rendered using seaborn barplot with status hues,
    value labels, and percentage shares."""
    c = _apply_theme(theme)
    if not problems:
        fig, ax = plt.subplots(figsize=(6.4, 4.2))
        ax.text(0.5, 0.5, "No problems yet", ha="center", va="center", fontsize=12, color=c["muted"])
        ax.axis("off")
        return _render_png(fig)

    colors = _status_palette(theme)
    counts = Counter((p.status or "open").replace("_", " ") for p in problems)
    order = ["open", "in review", "assigned", "resolved"]
    total = sum(counts.values()) or 1

    df = pd.DataFrame([
        {
            "status": s.title(),
            "count": counts.get(s, 0),
            "pct": (counts.get(s, 0) / total) * 100,
            "raw_status": s.replace(" ", "_"),
        }
        for s in order
    ])

    palette = [colors.get(r["raw_status"], "#4f46e5") for _, r in df.iterrows()]

    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    sns.barplot(
        data=df,
        x="status",
        y="count",
        hue="status",
        palette=palette,
        legend=False,
        ax=ax,
    )

    ax.set_title(f"Problems by status (Total: {total:,})", fontsize=13, fontweight="bold", loc="left", pad=12)
    ax.set_xlabel("")
    ax.set_ylabel("Reports")
    ax.yaxis.grid(True, alpha=0.55)
    ax.set_axisbelow(True)
    sns.despine(left=False)

    muted = c["muted"]
    for patch, (_, row) in zip(ax.patches, df.iterrows()):
        h = patch.get_height()
        ax.text(
            patch.get_x() + patch.get_width() / 2,
            h + max(df["count"]) * 0.03,
            f"{int(h)} ({row['pct']:.0f}%)",
            ha="center",
            va="bottom",
            fontsize=9.5,
            fontweight="bold",
            color=muted,
        )

    ax.set_ylim(0, max(df["count"]) * 1.18 + 1)
    return _render_png(fig)


def _chart_heatmap(problems: list[Problem], theme: str) -> bytes:
    """Category vs Status cross-tabulation heatmap — rendered with seaborn heatmap,
    annotated counts, and theme-adaptive gradient palette."""
    c = _apply_theme(theme)
    if not problems:
        fig, ax = plt.subplots(figsize=(7.6, 4.4))
        ax.text(0.5, 0.5, "No problems yet", ha="center", va="center", fontsize=12, color=c["muted"])
        ax.axis("off")
        return _render_png(fig)

    data = [
        {
            "category": (p.category or "uncategorized").replace("_", " ").title(),
            "status": (p.status or "open").replace("_", " ").title(),
        }
        for p in problems
    ]
    df = pd.DataFrame(data)
    ct = pd.crosstab(df["category"], df["status"])

    canonical_cols = ["Open", "In Review", "Assigned", "Resolved"]
    cols = [col for col in canonical_cols if col in ct.columns] + [col for col in ct.columns if col not in canonical_cols]
    ct = ct.reindex(columns=cols, fill_value=0)

    fig, ax = plt.subplots(figsize=(7.8, max(3.8, 0.38 * len(ct) + 1.8)))
    cmap = "mako" if theme == "dark" else "Blues"

    sns.heatmap(
        ct,
        annot=True,
        fmt="d",
        cmap=cmap,
        linewidths=1.0,
        linecolor="#1e293b22" if theme == "light" else "#ffffff15",
        cbar=True,
        cbar_kws={"shrink": 0.8, "label": "Problems count"},
        ax=ax,
    )

    ax.set_title("Category × Status Matrix (Seaborn Heatmap)", fontsize=13, fontweight="bold", loc="left", pad=12)
    ax.set_xlabel("Status")
    ax.set_ylabel("")
    ax.tick_params(axis="x", rotation=0)
    ax.tick_params(axis="y", rotation=0)

    return _render_png(fig)


def _chart_cluster_scatter(problems: list[Problem], theme: str) -> bytes:
    """2-D PCA scatter of live problem embeddings coloured by AI cluster label
    (hue=cluster) and shaped by category (style=category).  Uses seaborn
    scatterplot with the 'husl' palette so each cluster gets a vivid,
    perceptually-uniform hue that is readable on both light and dark backgrounds.
    """
    c = _apply_theme(theme)
    if not problems:
        fig, ax = plt.subplots(figsize=(7.6, 5.0))
        ax.text(0.5, 0.5, "No problems yet", ha="center", va="center", fontsize=12, color=c["muted"])
        ax.axis("off")
        return _render_png(fig)

    from ..ml.embed import get_shared_embedder
    from ..ml import preprocess
    from sklearn.decomposition import PCA

    embedder = get_shared_embedder()
    semantic = getattr(embedder, "name", "tfidf") == "sentence"
    texts = [preprocess.doc_text(p.title, p.description, semantic) for p in problems]
    matrix = embedder.transform(texts)

    # Densify if sparse (TF-IDF returns sparse matrix)
    if hasattr(matrix, "toarray"):
        matrix = matrix.toarray()
    matrix = np.array(matrix, dtype=np.float32)

    n_components = min(2, matrix.shape[0], matrix.shape[1])
    if n_components < 2:
        fig, ax = plt.subplots(figsize=(7.6, 5.0))
        ax.text(0.5, 0.5, "Need at least 2 problems to plot", ha="center", va="center",
                fontsize=12, color=c["muted"])
        ax.axis("off")
        return _render_png(fig)

    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(matrix)

    # Build cluster name lookup from DB (passed via problems list)
    # We stored cluster_id on each Problem
    cluster_names: dict[int, str] = {}
    for p in problems:
        cid = p.cluster_id
        if cid is not None and cid not in cluster_names:
            # Use a short label — will be loaded from DB if available
            cluster_names[cid] = f"C{cid}"

    def _cluster_label(p) -> str:
        if p.cluster is not None and p.cluster.name:
            # Shorten long cluster names: take first 2 words
            parts = p.cluster.name.split()[:3]
            return " ".join(parts)
        if p.cluster_id is not None:
            return f"Cluster {p.cluster_id}"
        return "Unassigned"

    df = pd.DataFrame({
        "PC 1": coords[:, 0],
        "PC 2": coords[:, 1],
        "Cluster": [_cluster_label(p) for p in problems],
        "Category": [(p.category or "other").replace("_", " ").title() for p in problems],
    })

    n_clusters = df["Cluster"].nunique()
    palette = sns.color_palette("husl", n_clusters)

    fig, ax = plt.subplots(figsize=(7.8, 5.4))
    sns.scatterplot(
        data=df,
        x="PC 1",
        y="PC 2",
        hue="Cluster",
        style="Category",
        palette=palette,
        s=110,
        alpha=0.82,
        edgecolor="white" if theme == "dark" else "#00000030",
        linewidth=0.6,
        ax=ax,
    )

    var_ratio = pca.explained_variance_ratio_
    ax.set_title(
        f"Problem clusters — 2D PCA projection ({var_ratio[0]:.0%} + {var_ratio[1]:.0%} variance)",
        fontsize=12, fontweight="bold", loc="left", pad=12,
    )
    ax.set_xlabel(f"PC 1 ({var_ratio[0]:.1%})")
    ax.set_ylabel(f"PC 2 ({var_ratio[1]:.1%})")
    ax.xaxis.grid(True, alpha=0.35)
    ax.yaxis.grid(True, alpha=0.35)
    ax.set_axisbelow(True)
    sns.despine()

    leg = ax.get_legend()
    if leg is not None:
        leg.set_frame_on(False)
        leg.set_title(None)
        for text in leg.get_texts():
            text.set_fontsize(8.5)

    return _render_png(fig)


def _chart_timeline(problems: list[Problem], theme: str) -> bytes:
    """Growth over time — two categorical series (cumulative vs duplicates),
    drawn with seaborn lineplot (hue=) over readable time buckets."""
    c = _apply_theme(theme)
    if not problems:
        fig, ax = plt.subplots(figsize=(7.4, 4.1))
        ax.text(0.5, 0.5, "No problems yet", ha="center", va="center", fontsize=12, color=c["muted"])
        ax.axis("off")
        return _render_png(fig)
    dates = sorted(p.created_at for p in problems if p.created_at)
    buckets, fmt = _bucketize(dates)

    # bucket step (monthly buckets have step=None)
    step = buckets[1] - buckets[0] if len(buckets) > 1 else timedelta(hours=1)
    if step >= timedelta(days=28):
        step = None

    new_by: dict[datetime, int] = {}
    dup_by: dict[datetime, int] = {}
    for p in problems:
        if not p.created_at:
            continue
        for b in buckets:
            if _bucket_of(p.created_at, b, step):
                new_by[b] = new_by.get(b, 0) + 1
                if p.is_duplicate:
                    dup_by[b] = dup_by.get(b, 0) + 1
                break

    labels = [b.strftime(fmt) for b in buckets]
    cum_total, cum_dup, run_t, run_d = [], [], 0, 0
    for b in buckets:
        run_t += new_by.get(b, 0)
        run_d += dup_by.get(b, 0)
        cum_total.append(run_t)
        cum_dup.append(run_d)

    if step is None:
        unit = "monthly"
    elif step < timedelta(days=1):
        unit = "hourly"
    elif step < timedelta(days=7):
        unit = "daily"
    else:
        unit = "weekly"

    long_df = pd.DataFrame(
        {
            "period": labels + labels,
            "series": ["Cumulative problems"] * len(labels) + ["Duplicates caught"] * len(labels),
            "count": cum_total + cum_dup,
        }
    )
    palette = SERIES_COLORS_DARK if theme == "dark" else SERIES_COLORS_LIGHT

    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    # subtle area fill under the cumulative line (annotation, matplotlib)
    ax.fill_between(range(len(labels)), cum_total, color=palette["Cumulative problems"], alpha=0.12, zorder=1)
    sns.lineplot(
        data=long_df, x="period", y="count", hue="series", style="series",
        palette=list(palette.values()),
        markers=True, linewidth=2.2, markersize=4.5, errorbar=None, ax=ax,
    )
    ax.set_title(f"Growth over time ({unit})", fontsize=13, fontweight="bold", loc="left", pad=12)
    ax.set_xlabel("Period")
    ax.set_ylabel("Number of problems")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_ylim(bottom=0)
    ax.yaxis.grid(True, alpha=0.55)
    ax.set_axisbelow(True)
    sns.despine(left=False)
    leg = ax.get_legend()
    if leg is not None:
        leg.set_frame_on(False)
        leg.set_title(None)
    return _render_png(fig)


CHARTS = {
    "category": _chart_category,
    "status": _chart_status,
    "timeline": _chart_timeline,
    "heatmap": _chart_heatmap,
    "cluster_scatter": _chart_cluster_scatter,
}


@router.get("/charts/{kind}")
def chart_image(
    kind: str,
    theme: str = "light",
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """Render a seaborn/matplotlib analytics chart as a PNG image."""
    if kind not in CHARTS:
        raise HTTPException(400, f"Unknown chart kind '{kind}' (use: {', '.join(CHARTS)})")
    if theme not in THEMES:
        theme = "light"
    problems = db.scalars(select(Problem)).all()
    png = CHARTS[kind](problems, theme)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )
