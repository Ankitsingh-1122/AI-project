#!/usr/bin/env python3
"""TASK 11 — replace the admin chart section with a seaborn-driven implementation."""
import pathlib

p = pathlib.Path('/home/user/civic-platform/backend/app/routers/admin.py')
t = p.read_text()

start = t.index('CHART_PALETTE = ')
end = t.index('\nCHARTS = {')

new = '''# Palette policy:
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
    for i, v in enumerate(df["count"]):
        ax.text(v + max(df["count"]) * 0.01, len(df) - 1 - i, f"{int(v):,}",
                va="center", ha="left", fontsize=9.5, color=c if False else _apply_color(theme))
    return _render_png(fig)


def _apply_color(theme: str) -> str:
    return THEMES.get(theme, THEMES["light"])["muted"]


def _chart_status(problems: list[Problem], theme: str) -> bytes:
    """Donut of status shares — proportions of a small fixed set, rendered with
    matplotlib's pie (seaborn has no pie); colors match the UI status badges."""
    _apply_theme(theme)
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

'''

# fix: _chart_category references _apply_color before it is defined in source
# order — move the helper above the chart functions. Rebuild `new` accordingly:
new = new.replace(
    '''    for i, v in enumerate(df["count"]):
        ax.text(v + max(df["count"]) * 0.01, len(df) - 1 - i, f"{int(v):,}",
                va="center", ha="left", fontsize=9.5, color=c if False else _apply_color(theme))
    return _render_png(fig)


def _apply_color(theme: str) -> str:
    return THEMES.get(theme, THEMES["light"])["muted"]
''',
    '''    muted = THEMES.get(theme, THEMES["light"])["muted"]
    for i, v in enumerate(df["count"]):
        ax.text(v + max(df["count"]) * 0.01, len(df) - 1 - i, f"{int(v):,}",
                va="center", ha="left", fontsize=9.5, color=muted)
    return _render_png(fig)
''')

new_timeline = '''
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
            "period": labels,
            "series": ["Cumulative problems"] * len(labels) + ["Duplicates caught"] * len(labels),
            "count": cum_total + cum_dup,
        }
    )
    palette = SERIES_COLORS_DARK if theme == "dark" else SERIES_COLORS_LIGHT

    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    # subtle area fill under the cumulative line (annotation, matplotlib)
    ax.fill_between(range(len(labels)), cum_total, color=palette["Cumulative problems"], alpha=0.12, zorder=1)
    sns.lineplot(
        data=long_df, x="period", y="count", hue="series",
        palette=list(palette.values()), style="series",
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
    handles, labels_ = ax.get_legend_handles_labels()
    # de-duplicate handles (style+hue both add entries)
    uniq = dict(zip(labels_, handles)).items()
    ax.legend(*zip(*uniq) if uniq else ([], []), frameon=False, loc="upper left")
    return _render_png(fig)

'''

t = t[:start] + new + new_timeline + t[end:]
p.write_text(t)
print("admin.py chart section replaced")
