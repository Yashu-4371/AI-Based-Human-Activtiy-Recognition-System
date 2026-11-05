"""
Chart-rendering helpers used by report_service.py.

Kept in a separate module (rather than inline in report_service) because
this is a distinct responsibility — turning aggregated data into visual
artifacts — that's reused across two different output formats (PNG images
embedded in PDF via matplotlib; native chart objects embedded in XLSX via
openpyxl.chart). Neither of those libraries is otherwise needed by the
rest of report_service's file-writing logic.
"""

import io
from datetime import datetime
from typing import Dict, List, Optional

import matplotlib

matplotlib.use("Agg")  # headless backend — no display server on a server process
import matplotlib.pyplot as plt
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.worksheet.worksheet import Worksheet

# Shared palette — matches the frontend's Recharts palette (ActivityChart.tsx)
# so a report looks consistent with the live dashboard.
ACTIVITY_COLORS = {
    "walking": "#1D4ED8",
    "standing": "#0EA5E9",
    "sitting": "#16A34A",
    "lying": "#D97706",
}
# Deliberately a plain list, not imported from app.models.activity.ActivityType:
# this module is a presentation-layer helper and has no reason to depend on
# the ORM layer just for four constant strings.
ACTIVITY_ORDER = ["walking", "standing", "sitting", "lying"]


def render_activity_distribution_pie(distribution_seconds: Dict[str, float]) -> bytes:
    """
    Donut chart of time spent per activity type (in minutes).
    Returns PNG bytes suitable for embedding in a PDF via reportlab.Image.
    """
    labels, values, colors_ = [], [], []
    for activity_type in ACTIVITY_ORDER:
        seconds = distribution_seconds.get(activity_type, 0.0)
        if seconds > 0:
            labels.append(activity_type.title())
            values.append(round(seconds / 60, 1))
            colors_.append(ACTIVITY_COLORS.get(activity_type, "#888888"))

    fig, ax = plt.subplots(figsize=(4.6, 3.4), dpi=150)
    if not values:
        ax.text(0.5, 0.5, "No activity recorded", ha="center", va="center", fontsize=10, color="#888888")
        ax.axis("off")
    else:
        wedges, _texts, autotexts = ax.pie(
            values,
            labels=labels,
            colors=colors_,
            autopct="%1.0f%%",
            pctdistance=0.8,
            startangle=90,
            wedgeprops={"width": 0.4, "edgecolor": "white", "linewidth": 1.5},
            textprops={"fontsize": 9},
        )
        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_fontsize(8)
            autotext.set_fontweight("bold")
        ax.set_aspect("equal")

    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def render_weekly_trend_chart(daily_points: List[Dict]) -> bytes:
    """
    Bar chart of total active minutes per day.
    daily_points: list of {"date": "YYYY-MM-DD", "total_duration_sec": float}
    Returns PNG bytes suitable for embedding in a PDF via reportlab.Image.
    """
    dates = [point["date"][5:] for point in daily_points]  # MM-DD, trims noisy year prefix
    minutes = [round(point["total_duration_sec"] / 60, 1) for point in daily_points]

    fig, ax = plt.subplots(figsize=(6.2, 2.8), dpi=150)
    if not dates:
        ax.text(0.5, 0.5, "No activity recorded in this period", ha="center", va="center", fontsize=10, color="#888888")
        ax.axis("off")
    else:
        bars = ax.bar(dates, minutes, color="#0EA5E9", width=0.6)
        ax.bar_label(bars, fmt="%.0f", fontsize=7, padding=2)
        ax.set_ylabel("Active minutes", fontsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="both", labelsize=8)
        ax.margins(y=0.15)

    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def render_activity_timeline(activities: List, timeline_date: Optional[datetime] = None) -> bytes:
    """
    Horizontal timeline (broken-barh) of activity segments across a single
    24-hour day, color-coded by activity type — the visual answer to
    "what was the patient doing, and when".

    `activities` is a list of ORM Activity rows (or anything exposing
    .activity_type, .started_at, .ended_at) already filtered to the day
    being rendered; if timeline_date is given, only segments overlapping
    that calendar day are drawn.
    """
    fig, ax = plt.subplots(figsize=(6.2, 1.8), dpi=150)

    day_activities = activities
    if timeline_date is not None:
        target_date = timeline_date.date()
        day_activities = [a for a in activities if a.started_at.date() == target_date]

    if not day_activities:
        ax.text(0.5, 0.5, "No activity recorded for this day", ha="center", va="center", fontsize=10, color="#888888")
        ax.axis("off")
        fig.tight_layout()
        return _fig_to_png_bytes(fig)

    seen_types = set()
    for activity in day_activities:
        start_hour = activity.started_at.hour + activity.started_at.minute / 60
        end_time = activity.ended_at or activity.started_at
        duration_hours = max((end_time - activity.started_at).total_seconds() / 3600, 0.02)
        activity_type = activity.activity_type.value if hasattr(activity.activity_type, "value") else activity.activity_type
        color = ACTIVITY_COLORS.get(activity_type, "#888888")

        ax.broken_barh([(start_hour, duration_hours)], (0, 1), facecolors=color)
        seen_types.add(activity_type)

    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 4))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 4)], fontsize=8)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    handles = [plt.Rectangle((0, 0), 1, 1, color=ACTIVITY_COLORS.get(t, "#888888")) for t in ACTIVITY_ORDER if t in seen_types]
    labels = [t.title() for t in ACTIVITY_ORDER if t in seen_types]
    if handles:
        ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.35), ncol=len(handles), fontsize=8, frameon=False)

    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def _fig_to_png_bytes(fig) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer.read()


def add_xlsx_summary_and_charts(
    workbook,
    distribution_seconds: Dict[str, float],
    daily_points: List[Dict],
) -> None:
    """
    Adds a "Summary" sheet to the workbook with the activity-distribution
    and weekly-trend data plus native Excel charts built from it (so the
    charts stay interactive/editable for the recipient, unlike a pasted
    image — the appropriate approach for a spreadsheet deliverable).
    """
    sheet: Worksheet = workbook.create_sheet("Summary", 0)

    sheet.append(["Activity Type", "Minutes"])
    for activity_type in ACTIVITY_ORDER:
        seconds = distribution_seconds.get(activity_type, 0.0)
        sheet.append([activity_type.title(), round(seconds / 60, 1)])

    pie = PieChart()
    pie.title = "Activity distribution"
    data_ref = Reference(sheet, min_col=2, min_row=1, max_row=1 + len(ACTIVITY_ORDER))
    labels_ref = Reference(sheet, min_col=1, min_row=2, max_row=1 + len(ACTIVITY_ORDER))
    pie.add_data(data_ref, titles_from_data=True)
    pie.set_categories(labels_ref)
    pie.height, pie.width = 8, 10
    sheet.add_chart(pie, "D2")

    trend_start_row = len(ACTIVITY_ORDER) + 4
    sheet.cell(row=trend_start_row, column=1, value="Date")
    sheet.cell(row=trend_start_row, column=2, value="Active Minutes")
    for offset, point in enumerate(daily_points, start=1):
        sheet.cell(row=trend_start_row + offset, column=1, value=point["date"])
        sheet.cell(row=trend_start_row + offset, column=2, value=round(point["total_duration_sec"] / 60, 1))

    if daily_points:
        bar = BarChart()
        bar.title = "Weekly trend (active minutes/day)"
        bar.type = "col"
        data_ref = Reference(
            sheet, min_col=2, min_row=trend_start_row, max_row=trend_start_row + len(daily_points)
        )
        cats_ref = Reference(
            sheet, min_col=1, min_row=trend_start_row + 1, max_row=trend_start_row + len(daily_points)
        )
        bar.add_data(data_ref, titles_from_data=True)
        bar.set_categories(cats_ref)
        bar.height, bar.width = 8, 14
        sheet.add_chart(bar, f"D{trend_start_row}")
