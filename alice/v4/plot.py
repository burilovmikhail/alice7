"""Plots of a V4 run or fork (spec §8): the artifact by which a firing is explained (T101, T127), not decoration.

One PNG, panels sharing the time axis: mode (awake, conversation, NREM, REM); coherence against its threshold;
urgency against the brake (separate panels: different scales, never two y-axes); the drives as small multiples of
at most four each; the activations of the nodes that reached working memory. Firings and dreams are marked across
all panels.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from . import constants as K

# The reference categorical palette, slots in fixed order (dataviz skill, references/palette.md)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
OTHER = "#b9b8b2"
MODE_SHADE = {"awake": "#fcfcfb", "conversation": "#cde2fb", "nrem": "#86b6ef", "rem": "#3987e5"}
DRIVE_GROUPS = [("sleep and energy", ["S", "arousal", "fatigue", "boredom"]),
                ("pulls", ["social", "curiosity", "uncertainty", "goal_tension"]),
                ("affect", ["valence", "mood", "frustration", "dissonance"])]
NAMES = {"S": "sleep pressure", "goal_tension": "goal tension"}


def _load(db: sqlite3.Connection, start: str | None, end: str | None):
    where, args = [], []
    if start:
        where.append("at >= ?")
        args.append(start)
    if end:
        where.append("at <= ?")
        args.append(end)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    steps = db.execute(f"SELECT * FROM v4_steps{clause} ORDER BY rowid", args).fetchall()
    firings = db.execute(f"SELECT at, kind, cause FROM v4_firings{clause} ORDER BY id",
                         args).fetchall()
    return steps, [f for f in firings if f["kind"] in ("fire", "dream")]


def plot(db_path: Path | str, out: Path | str, *, start: str | None = None, end: str | None = None,
         nodes: list[int] | None = None, max_nodes: int = 8) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    steps, firings = _load(db, start, end)
    if not steps:
        raise ValueError(f"no V4 steps in {db_path} (was the field on?)")
    labels = {r["id"]: (r["kind"], r["label"]) for r in db.execute("SELECT id, kind, label FROM v4_nodes")}
    db.close()
    t = [datetime.fromisoformat(r["at"]) for r in steps]
    drives = [json.loads(r["drives"]) for r in steps]
    tops = [dict((n, a) for n, a in json.loads(r["top"])) for r in steps]

    plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED,
                         "ytick.color": MUTED, "axes.titlecolor": INK, "axes.titlesize": 9, "axes.titleweight": "bold",
                         "axes.titlelocation": "left", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    heights = [0.5, 1.2, 1.2, 1.4, 1.4, 1.4, 2.2]
    fig, axes = plt.subplots(len(heights), 1, figsize=(13, 15), sharex=True,
                             gridspec_kw={"height_ratios": heights, "hspace": 0.45})
    for ax in axes:
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.spines[["top", "right"]].set_visible(False)
        for f in firings:
            at = datetime.fromisoformat(f["at"])
            ax.axvline(at, color=SERIES[7] if f["kind"] == "fire" else SERIES[6], linewidth=1, alpha=0.7, zorder=1)

    # 1. mode band
    ax = axes[0]
    run_start = 0
    for k in range(1, len(steps) + 1):
        if k == len(steps) or steps[k]["mode"] != steps[run_start]["mode"]:
            ax.axvspan(t[run_start], t[min(k, len(t) - 1)], color=MODE_SHADE.get(steps[run_start]["mode"], OTHER),
                       linewidth=0)
            run_start = k
    ax.set_yticks([])
    ax.set_title("Mode: white awake · light blue conversation · mid blue NREM · dark blue REM;  "
                 "red lines: firings, violet: dreams")

    # 2. coherence vs threshold
    ax = axes[1]
    ax.plot(t, [r["coherence"] for r in steps], color=SERIES[0], linewidth=2, label="coherence")
    theta = [K.COHERENCE_THETA * (1 - K.COHERENCE_BOREDOM * d["boredom"]) *
             (K.REM_THETA_GAIN if r["mode"] == "rem" else 1) for r, d in zip(steps, drives)]
    ax.plot(t, theta, color=MUTED, linewidth=1, linestyle="--", label="threshold θ_c")
    ax.set_title("Coherence of the coalition, against its threshold")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, labelcolor=INK)

    # 3. urgency vs brake
    ax = axes[2]
    ax.plot(t, [r["urgency"] for r in steps], color=SERIES[1], linewidth=2, label="urgency u")
    ax.plot(t, [r["brake"] if r["brake"] >= 0 else float("nan") for r in steps], color=MUTED, linewidth=1,
            linestyle="--", label="brake (gaps: closed)")
    ax.set_title("Urgency, against the brake")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, labelcolor=INK)

    # 4-6. drives, small multiples of four
    for ax, (title, group) in zip(axes[3:6], DRIVE_GROUPS):
        for slot, name in enumerate(group):
            ax.plot(t, [d.get(name) for d in drives], color=SERIES[slot], linewidth=2, label=NAMES.get(name, name))
        ax.set_title(f"Drives: {title}")
        ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, labelcolor=INK)
    axes[5].axhline(0, color=GRID, linewidth=1)

    # 7. activations of the nodes that reached working memory
    ax = axes[6]
    peak: dict[int, float] = {}
    for top in tops:
        for n, a in top.items():
            peak[n] = max(peak.get(n, 0.0), a)
    reached = [n for n, a in peak.items() if a >= K.WM_THRESHOLD and labels.get(n, ("", ""))[0] != "self"]
    chosen = nodes or sorted(reached, key=lambda n: -peak[n])[:max_nodes]
    for n in [n for n in reached if n not in chosen]:
        ax.plot(t, [top.get(n, 0.0) for top in tops], color=OTHER, linewidth=1, zorder=2)
    for slot, n in enumerate(chosen[:len(SERIES)]):
        kind, label = labels.get(n, ("?", "?"))
        ax.plot(t, [top.get(n, 0.0) for top in tops], color=SERIES[slot], linewidth=2, zorder=3,
                label=f"[{n}] {kind}: {label[:48]}")
    ax.axhline(K.WM_THRESHOLD, color=MUTED, linewidth=1, linestyle="--")
    ax.set_title(f"Activation of nodes that reached working memory (dashed: {K.WM_THRESHOLD}); gray: others"
                 if len(reached) > len(chosen) else "Activation of nodes that reached working memory")
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.32), frameon=False, ncol=2, fontsize=8, labelcolor=INK)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d %H:%M"))
    fig.autofmt_xdate()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out
