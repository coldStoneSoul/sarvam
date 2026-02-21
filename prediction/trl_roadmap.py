"""
Technology Readiness Roadmap (TRL 6 → TRL 9)
Generates a professional Gantt-style roadmap chart.

Usage:
    python trl_roadmap.py          # opens the chart in a window
    python trl_roadmap.py --save   # saves as trl_roadmap.png
"""

import sys
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np

# ── Colour palette ──────────────────────────────────────────────────
NAVY   = "#1B2A4A"   # completed
AMBER  = "#F59E0B"   # in-progress
GRAY   = "#9CA3AF"   # planned
WHITE  = "#FFFFFF"
BG     = "#F8FAFC"
GRID   = "#E2E8F0"
TEXT   = "#1E293B"

# ── Milestone data ──────────────────────────────────────────────────
milestones = [
    {
        "trl": "TRL 5",
        "label": "Component Integration &\nLaboratory Validation",
        "start": datetime(2025, 6, 1),
        "end": datetime(2025, 12, 31),
        "status": "completed",
        "deliverable": "All modules integrated,\nsynthetic data validation",
    },
    {
        "trl": "TRL 6 (Current)",
        "label": "End-to-End PoC on\nSynthetic MSME Cases",
        "start": datetime(2026, 1, 1),
        "end": datetime(2026, 2, 28),
        "status": "in-progress",
        "deliverable": "Working demo, AUC 0.814,\nDocker containerized",
    },
    {
        "trl": "TRL 7",
        "label": "Pilot with Real MSEFC\nCases via AIKosh Data",
        "start": datetime(2026, 3, 1),
        "end": datetime(2026, 5, 31),
        "status": "planned",
        "deliverable": "Real case validation,\nperformance benchmarking",
    },
    {
        "trl": "TRL 8",
        "label": "ODR Portal Integration\n& Security Audit",
        "start": datetime(2026, 6, 1),
        "end": datetime(2026, 8, 31),
        "status": "planned",
        "deliverable": "API integration, pen-testing,\nDPDP compliance",
    },
    {
        "trl": "TRL 9",
        "label": "Full National\nDeployment",
        "start": datetime(2026, 9, 1),
        "end": datetime(2027, 2, 28),
        "status": "planned",
        "deliverable": "NIC Cloud deployment,\npan-India accessibility",
    },
]

STATUS_COLORS = {
    "completed":   NAVY,
    "in-progress": AMBER,
    "planned":     GRAY,
}

STATUS_TEXT_COLORS = {
    "completed":   WHITE,
    "in-progress": TEXT,
    "planned":     WHITE,
}


def build_chart():
    fig, ax = plt.subplots(figsize=(18, 8), facecolor=BG)
    ax.set_facecolor(BG)

    n = len(milestones)
    y_positions = list(range(n - 1, -1, -1))  # top-to-bottom

    bar_height = 0.55

    for idx, m in enumerate(milestones):
        y = y_positions[idx]
        color = STATUS_COLORS[m["status"]]
        text_color = STATUS_TEXT_COLORS[m["status"]]

        start_num = mdates.date2num(m["start"])
        end_num = mdates.date2num(m["end"])
        width = end_num - start_num

        # ── Main bar (rounded rectangle) ────────────────────────────
        bar = mpatches.FancyBboxPatch(
            (start_num, y - bar_height / 2),
            width,
            bar_height,
            boxstyle=mpatches.BoxStyle.Round(pad=0.02, rounding_size=0.03),
            facecolor=color,
            edgecolor="none",
            zorder=3,
        )
        ax.add_patch(bar)

        # ── Bar label (milestone name) ──────────────────────────────
        mid_x = start_num + width / 2
        ax.text(
            mid_x, y + 0.02,
            m["label"],
            ha="center", va="center",
            fontsize=9, fontweight="bold",
            color=text_color,
            zorder=4,
            linespacing=1.3,
        )

        # ── Deliverable annotation below bar ────────────────────────
        ax.text(
            mid_x, y - bar_height / 2 - 0.12,
            m["deliverable"],
            ha="center", va="top",
            fontsize=7.5, color="#64748B",
            style="italic",
            zorder=4,
            linespacing=1.2,
        )

        # ── Diamond marker at start ─────────────────────────────────
        ax.plot(
            start_num, y,
            marker="D", markersize=7,
            color=color, markeredgecolor=WHITE, markeredgewidth=1.2,
            zorder=5,
        )

    # ── Y-axis labels (TRL levels) ──────────────────────────────────
    ax.set_yticks(y_positions)
    ax.set_yticklabels(
        [m["trl"] for m in milestones],
        fontsize=11, fontweight="bold", color=TEXT,
    )
    ax.tick_params(axis="y", length=0, pad=12)

    # ── X-axis formatting ───────────────────────────────────────────
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.tick_params(axis="x", labelsize=9, colors="#64748B", length=4)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    # ── Grid lines ──────────────────────────────────────────────────
    ax.xaxis.grid(True, color=GRID, linewidth=0.6, zorder=1)
    ax.yaxis.grid(False)
    ax.set_axisbelow(True)

    # ── Axis limits ─────────────────────────────────────────────────
    pad_days = 30
    x_min = mdates.date2num(milestones[0]["start"]) - pad_days
    x_max = mdates.date2num(milestones[-1]["end"]) + pad_days
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(-0.8, n - 0.2)

    # ── Remove spines ───────────────────────────────────────────────
    for spine in ax.spines.values():
        spine.set_visible(False)

    # ── "TODAY" marker ──────────────────────────────────────────────
    today = datetime(2026, 2, 21)
    today_num = mdates.date2num(today)
    ax.axvline(
        today_num, color="#EF4444", linewidth=1.8,
        linestyle="--", zorder=6, alpha=0.8,
    )
    ax.text(
        today_num, n - 0.15,
        "  TODAY",
        fontsize=9, fontweight="bold",
        color="#EF4444", va="top", ha="left",
        zorder=7,
    )

    # ── Legend ──────────────────────────────────────────────────────
    legend_handles = [
        mpatches.Patch(facecolor=NAVY,  label="Completed",   edgecolor="none"),
        mpatches.Patch(facecolor=AMBER, label="In Progress", edgecolor="none"),
        mpatches.Patch(facecolor=GRAY,  label="Planned",     edgecolor="none"),
    ]
    legend = ax.legend(
        handles=legend_handles,
        loc="upper right",
        fontsize=10,
        frameon=True,
        facecolor=WHITE,
        edgecolor=GRID,
        framealpha=0.95,
        borderpad=0.8,
        handlelength=1.6,
    )
    legend.get_frame().set_linewidth(0.8)

    # ── Title & subtitle ────────────────────────────────────────────
    fig.suptitle(
        "Technology Readiness Roadmap  (TRL 5 → TRL 9)",
        fontsize=18, fontweight="bold", color=TEXT,
        y=0.97, x=0.5, ha="center",
    )
    ax.set_title(
        "Figure 10.1 — MSME Dispute Resolution AI System",
        fontsize=12, color="#64748B", pad=18,
    )

    # ── Stage annotations ───────────────────────────────────────────
    # Stage 2 bracket (Month 1-12, i.e., Mar 2026 – Feb 2027)
    stage2_start = mdates.date2num(datetime(2026, 3, 1))
    stage2_end   = mdates.date2num(datetime(2027, 2, 28))
    bracket_y    = -0.65

    ax.annotate(
        "", xy=(stage2_start, bracket_y), xytext=(stage2_end, bracket_y),
        arrowprops=dict(arrowstyle="<->", color="#475569", lw=1.5),
        zorder=6,
    )
    ax.text(
        (stage2_start + stage2_end) / 2, bracket_y - 0.08,
        "◀── Stage 2  (Month 1–12) ──▶",
        ha="center", va="top",
        fontsize=9, fontweight="bold", color="#475569",
        zorder=6,
    )

    plt.tight_layout(rect=[0.02, 0.06, 0.98, 0.94])
    return fig


if __name__ == "__main__":
    fig = build_chart()

    if "--save" in sys.argv:
        out = "trl_roadmap.png"
        fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
        print(f"✅  Saved → {out}")
    else:
        plt.show()
