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

CHART_PALETTE = ["#4f46e5", "#16a34a", "#dc2626", "#7c3aed", "#ea580c", "#0891b2", "#ca8a04", "#db2777"]
STATUS_COLORS = {"open": "#4f46e5", "in_review": "#d97706", "assigned": "#7c3aed", "resolved": "#16a34a"}

THEMES = {
    "light": dict(text="#0b1220", muted="#5b6b84", grid="#0f172a24", spine="#94a3b8"),
    "dark": dict(text="#e2e8f0", muted="#94a3b8", grid="#e2e8f02e", spine="#475569"),
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
        },
    )
    return c


def _render_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, transparent=True, bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    return buf.getvalue()


def _chart_category(problems: list[Problem], theme: str) -> bytes:
    c = _apply_theme(theme)
    counts = Counter(p.category.replace("_", " ") for p in problems)
    df = pd.DataFrame(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])), columns=["category", "count"])
    fig, ax = plt.subplots(figsize=(7.4, 4.1))
    sns.barplot(data=df, x="count", y="category", hue="category", palette=CHART_PALETTE, legend=False, ax=ax)
    ax.set_title("Problems by category", fontsize=14, fontweight="bold", loc="left", pad=12)
    ax.set_xlabel("Reports")
    ax.xaxis.grid(True, alpha=0.5)
    ax.set_axisbelow(True)
    sns.despine(left=False)
    for i, v in enumerate(df["count"]):
        ax.text(v + 0.15, i, str(int(v)), va="center", fontsize=10, color=c["muted"])
    return _render_png(fig)


def _chart_status(problems: list[Problem], theme: str) -> bytes:
    c = _apply_theme(theme)
    counts = Counter(p.status.replace("_", " ") for p in problems)
    order = [s for s in ["open", "in review", "assigned", "resolved"] if s in counts]
    values = [counts[k] for k in order]
    colors = [STATUS_COLORS.get(k.replace(" ", "_"), "#64748b") for k in order]
    total = sum(values) or 1
    fig, ax = plt.subplots(figsize=(5.4, 4.4))
    wedges, _ = ax.pie(
        values,
        colors=colors,
        startangle=90,
        counterclock=False,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
    )
    # percentage labels on slice midpoints
    for wedge, v in zip(wedges, values):
        ang = (wedge.theta2 + wedge.theta1) / 2
        x, y = 0.79 * np.cos(np.deg2rad(ang)), 0.79 * np.sin(np.deg2rad(ang))
        ax.text(x, y, f"{v / total:.0%}", ha="center", va="center", fontsize=10, fontweight="bold", color="white")
    ax.set_title("Problems by status", fontsize=14, fontweight="bold", loc="left", pad=12)
    ax.text(0, 0.10, str(total), ha="center", va="center", fontsize=30, fontweight="bold", color=c["text"])
    ax.text(0, -0.20, "total", ha="center", va="center", fontsize=10, color=c["muted"])
    ax.legend(wedges, [f"{k}  ({v})" for k, v in zip(order, values)], loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=2, frameon=False, fontsize=10)
    return _render_png(fig)


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


def _chart_timeline(problems: list[Problem], theme: str) -> bytes:
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
    fig, ax = plt.subplots(figsize=(7.4, 4.1))
    ax.fill_between(range(len(buckets)), cum_total, color=CHART_PALETTE[0], alpha=0.18)
    ax.plot(range(len(buckets)), cum_total, color=CHART_PALETTE[0], marker="o", markersize=5, linewidth=2.2, label="Cumulative problems")
    ax.plot(range(len(buckets)), cum_dup, color=CHART_PALETTE[2], marker="s", markersize=4.5, linewidth=2.2, label="Duplicates caught")
    ax.set_xticks(range(len(buckets)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9.5)
    ax.set_title(f"Growth over time ({unit})", fontsize=14, fontweight="bold", loc="left", pad=12)
    ax.set_ylabel("Count")
    ax.set_ylim(bottom=0)
    ax.yaxis.grid(True, alpha=0.5)
    ax.set_axisbelow(True)
    sns.despine(left=False)
    ax.legend(frameon=False, fontsize=10, loc="upper left")
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
