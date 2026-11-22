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
    """Donut of status shares — proportions of a small fixed set, rendered with
    matplotlib's pie (seaborn has no pie); colors match the UI status badges."""
    c = _apply_theme(theme)
    if not problems:
        fig, ax = plt.subplots(figsize=(5.6, 4.6))
        ax.text(0.5, 0.5, "No problems yet", ha="center", va="center", fontsize=12, color=c["muted"])
        ax.axis("off")
        return _render_png(fig)
    colors = _status_palette(theme)
    counts = Counter((p.status or "open").replace("_", " ") for p in problems)
    order = [s for s in ["open", "in review", "assigned", "resolved"] if s in counts]
    values = [counts[k] for k in order]
    total = sum(values) or 1
    surface = "#131a29" if theme == "dark" else "#ffffff"
    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    wedges, _ = ax.pie(
        values,
        colors=[colors[k.replace(" ", "_")] for k in order],
        startangle=90,
        counterclock=False,
        wedgeprops=dict(width=0.42, edgecolor=surface, linewidth=2),
    )
    for wedge, v in zip(wedges, values):
        ang = (wedge.theta2 + wedge.theta1) / 2
        x, y = 0.79 * np.cos(np.deg2rad(ang)), 0.79 * np.sin(np.deg2rad(ang))
        ax.text(x, y, f"{v / total:.0%}", ha="center", va="center",
                fontsize=10.5, fontweight="bold", color="white")
    ax.set_title("Problems by status", fontsize=13, fontweight="bold", loc="left", pad=12)
    ax.text(0, 0.10, f"{total:,}", ha="center", va="center", fontsize=28, fontweight="bold")
    ax.text(0, -0.20, "total", ha="center", va="center", fontsize=10)
    ax.legend(
        wedges, [f"{k}  ({v:,})" for k, v in zip(order, values)],
        loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2, frameon=False,
    )
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
