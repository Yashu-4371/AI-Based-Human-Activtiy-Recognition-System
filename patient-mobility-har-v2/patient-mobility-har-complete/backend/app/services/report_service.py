
"""
Report generation for daily, weekly and monthly patient mobility reports.

PDF reports follow the requested Patient Mobility Report layout.
CSV and XLSX reports retain activity, alert and mobility comparison data.
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import Workbook

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.patient import Patient
from app.models.report import Report, ReportType, ReportFormat
from app.models.alert import AlertType
from app.models.activity import Activity, ActivityType

from app.services.activity_service import get_history
from app.services.analytics_service import (
    activity_distribution,
    daily_activity_duration,
)
from app.services.alert_service import list_alerts
from app.services.monitoring_session_service import total_monitoring_seconds

from app.services.report_charts import (
    render_activity_distribution_pie,
    render_weekly_trend_chart,
    render_activity_timeline,
    add_xlsx_summary_and_charts,
)

from app.utils.file_storage import new_report_path, to_relative_url
from app.utils.logger import get_logger


logger = get_logger(__name__)

IST = ZoneInfo("Asia/Kolkata")

_PERIOD_DAYS = {
    ReportType.daily: 1,
    ReportType.weekly: 7,
    ReportType.monthly: 30,
}


# ---------------------------------------------------------
# DATE AND TIME HELPERS
# ---------------------------------------------------------

def _period_window(
    report_type: ReportType,
) -> tuple[datetime, datetime]:

    date_to = datetime.utcnow()
    date_from = date_to - timedelta(
        days=_PERIOD_DAYS[report_type]
    )

    return date_from, date_to


def _to_ist(value: datetime) -> datetime:
    """Convert a UTC datetime to Indian Standard Time."""

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=ZoneInfo("UTC")
        )

    return value.astimezone(IST)


# ---------------------------------------------------------
# MOBILITY CALCULATION
# ---------------------------------------------------------

def _mobility_seconds(
    db: Session,
    patient_id: int,
    date_from: datetime,
    date_to: datetime,
) -> float:

    total = (
        db.query(func.sum(Activity.duration_sec))
        .filter(
            Activity.patient_id == patient_id,
            Activity.activity_type.in_([
                ActivityType.walking,
                ActivityType.standing,
            ]),
            Activity.started_at >= date_from,
            Activity.started_at < date_to,
            Activity.duration_sec.isnot(None),
        )
        .scalar()
    )

    return float(total or 0)


def _calculate_recovery_rate(
    monitoring_seconds: float,
    walking_seconds: float,
    standing_seconds: float,
) -> Optional[float]:
    """
    Activity-based mobility estimate.

    It is not a clinically validated recovery measurement.
    """

    if monitoring_seconds <= 0:
        return None

    active_seconds = (
        walking_seconds + standing_seconds
    )

    rate = (
        active_seconds / monitoring_seconds
    ) * 100

    return min(100.0, max(0.0, rate))


def _recovery_interpretation(
    recovery_rate: Optional[float],
) -> str:

    if recovery_rate is None:
        return "Insufficient monitoring data"

    if recovery_rate >= 75:
        return "Higher activity-based mobility score"

    if recovery_rate >= 50:
        return "Moderate activity-based mobility score"

    return "Lower activity-based mobility score"


# ---------------------------------------------------------
# COMMON REPORT DATA
# ---------------------------------------------------------

def _report_context(
    patient: Patient,
    report_type: ReportType,
    date_from: datetime,
    date_to: datetime,
    db: Session,
) -> dict:

    activities = get_history(
        db,
        patient.id,
        date_from,
        date_to,
        limit=10000,
    )

    distribution = activity_distribution(
        db,
        patient.id,
        date_from,
        date_to,
    )

    trend_days = min(
        _PERIOD_DAYS[report_type],
        30,
    )

    daily_points = daily_activity_duration(
        db,
        patient.id,
        days=trend_days,
    )

    all_alerts = list_alerts(
        db,
        patient_id=patient.id,
        date_from=date_from,
        date_to=date_to,
        limit=10000,
    )

    inactivity_events = sum(
        1
        for alert in all_alerts
        if alert.type == AlertType.inactivity
    )

    monitoring_seconds = float(
        total_monitoring_seconds(
            db,
            patient.id,
            date_from,
            date_to,
        ) or 0
    )

    walking_seconds = float(
        distribution.get("walking", 0) or 0
    )

    standing_seconds = float(
        distribution.get("standing", 0) or 0
    )

    sitting_seconds = float(
        distribution.get("sitting", 0) or 0
    )

    lying_seconds = float(
        distribution.get("lying", 0) or 0
    )

    recovery_rate = _calculate_recovery_rate(
        monitoring_seconds,
        walking_seconds,
        standing_seconds,
    )

    interpretation = _recovery_interpretation(
        recovery_rate
    )

    # Previous equal-length period for CSV/XLSX.
    period_length = date_to - date_from
    previous_date_from = date_from - period_length

    previous_mobility_seconds = _mobility_seconds(
        db,
        patient.id,
        previous_date_from,
        date_from,
    )

    current_mobility_seconds = _mobility_seconds(
        db,
        patient.id,
        date_from,
        date_to,
    )

    mobility_improvement_pct = None

    if previous_mobility_seconds > 0:
        mobility_improvement_pct = (
            (
                current_mobility_seconds
                - previous_mobility_seconds
            )
            / previous_mobility_seconds
        ) * 100

    return {
        "activities": activities,
        "distribution": distribution,
        "daily_points": daily_points,
        "alerts": all_alerts,
        "inactivity_events": inactivity_events,
        "monitoring_seconds": monitoring_seconds,
        "walking_seconds": walking_seconds,
        "standing_seconds": standing_seconds,
        "sitting_seconds": sitting_seconds,
        "lying_seconds": lying_seconds,
        "recovery_rate": recovery_rate,
        "interpretation": interpretation,
        "current_mobility_seconds": current_mobility_seconds,
        "previous_mobility_seconds": previous_mobility_seconds,
        "mobility_improvement_pct": mobility_improvement_pct,
    }


# ---------------------------------------------------------
# CSV REPORT
# ---------------------------------------------------------

def _generate_csv(
    patient: Patient,
    report_type: ReportType,
    date_from: datetime,
    date_to: datetime,
    db: Session,
) -> str:

    destination = new_report_path(
        patient.id,
        report_type.value,
        "csv",
    )

    ctx = _report_context(
        patient,
        report_type,
        date_from,
        date_to,
        db,
    )

    with open(
        destination,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.writer(f)

        writer.writerow([
            f"Patient Mobility Report - {report_type.value.title()}"
        ])

        writer.writerow(["Patient", patient.name])
        writer.writerow([
            "Room",
            patient.room_number or "N/A",
        ])

        writer.writerow([
            "Period",
            f"{date_from.isoformat()} to {date_to.isoformat()}",
        ])

        writer.writerow([
            "Total monitoring time (min)",
            round(ctx["monitoring_seconds"] / 60, 1),
        ])

        writer.writerow([])

        writer.writerow(["Activity Distribution"])
        writer.writerow(["Activity Type", "Total Minutes"])

        for activity_type, seconds in ctx["distribution"].items():
            writer.writerow([
                activity_type.title(),
                round(seconds / 60, 1),
            ])

        writer.writerow([])

        writer.writerow(["Recovery Rate (%)"])
        writer.writerow([
            "Activity-based mobility estimate",
            (
                round(ctx["recovery_rate"], 1)
                if ctx["recovery_rate"] is not None
                else "N/A"
            ),
        ])

        writer.writerow([
            "Interpretation",
            ctx["interpretation"],
        ])

        writer.writerow([])
        writer.writerow(["Statistics"])

        writer.writerow([
            "Inactivity events",
            ctx["inactivity_events"],
        ])

        writer.writerow([
            "Current walking + standing (min)",
            round(ctx["current_mobility_seconds"] / 60, 1),
        ])

        writer.writerow([
            "Previous walking + standing (min)",
            round(ctx["previous_mobility_seconds"] / 60, 1),
        ])

        improvement = ctx["mobility_improvement_pct"]

        writer.writerow([
            "Estimated Mobility Improvement (%)",
            (
                round(improvement, 1)
                if improvement is not None
                else "N/A"
            ),
        ])

        writer.writerow([])
        writer.writerow(["Alert History"])

        writer.writerow([
            "Type",
            "Priority",
            "Status",
            "Message",
            "Created At",
            "Resolved At",
        ])

        for alert in ctx["alerts"]:
            writer.writerow([
                alert.type.value,
                alert.priority.value,
                alert.status.value,
                alert.message,
                alert.created_at.isoformat(),
                (
                    alert.resolved_at.isoformat()
                    if alert.resolved_at
                    else ""
                ),
            ])

        writer.writerow([])
        writer.writerow(["Activity Timeline"])

        writer.writerow([
            "Activity",
            "Confidence",
            "Started At",
            "Ended At",
            "Duration (sec)",
        ])

        for activity in ctx["activities"]:
            writer.writerow([
                activity.activity_type.value,
                f"{activity.confidence:.2f}",
                activity.started_at.isoformat(),
                (
                    activity.ended_at.isoformat()
                    if activity.ended_at
                    else ""
                ),
                activity.duration_sec or "",
            ])

    return str(destination)


# ---------------------------------------------------------
# EXCEL REPORT
# ---------------------------------------------------------

def _generate_xlsx(
    patient: Patient,
    report_type: ReportType,
    date_from: datetime,
    date_to: datetime,
    db: Session,
) -> str:

    destination = new_report_path(
        patient.id,
        report_type.value,
        "xlsx",
    )

    ctx = _report_context(
        patient,
        report_type,
        date_from,
        date_to,
        db,
    )

    workbook = Workbook()

    # Activity timeline sheet.
    timeline_sheet = workbook.active
    timeline_sheet.title = "Activity Timeline"

    timeline_sheet.append([
        "Activity",
        "Confidence",
        "Started At",
        "Ended At",
        "Duration (sec)",
    ])

    for activity in ctx["activities"]:
        timeline_sheet.append([
            activity.activity_type.value,
            round(activity.confidence, 2),
            activity.started_at.isoformat(),
            (
                activity.ended_at.isoformat()
                if activity.ended_at
                else ""
            ),
            activity.duration_sec or "",
        ])

    # Alert history sheet.
    alerts_sheet = workbook.create_sheet("Alert History")

    alerts_sheet.append([
        "Type",
        "Priority",
        "Status",
        "Message",
        "Created At",
        "Resolved At",
    ])

    for alert in ctx["alerts"]:
        alerts_sheet.append([
            alert.type.value,
            alert.priority.value,
            alert.status.value,
            alert.message,
            alert.created_at.isoformat(),
            (
                alert.resolved_at.isoformat()
                if alert.resolved_at
                else ""
            ),
        ])

    # Summary and charts.
    add_xlsx_summary_and_charts(
        workbook,
        ctx["distribution"],
        ctx["daily_points"],
    )

    summary_sheet = (
        workbook["Summary"]
        if "Summary" in workbook.sheetnames
        else workbook.worksheets[0]
    )

    next_row = summary_sheet.max_row + 3

    summary_values = [
        (
            "Total monitoring time (min)",
            round(ctx["monitoring_seconds"] / 60, 1),
        ),
        (
            "Recovery Rate (%)",
            (
                round(ctx["recovery_rate"], 1)
                if ctx["recovery_rate"] is not None
                else "N/A"
            ),
        ),
        (
            "Interpretation",
            ctx["interpretation"],
        ),
        (
            "Inactivity events",
            ctx["inactivity_events"],
        ),
        (
            "Current walking + standing (min)",
            round(ctx["current_mobility_seconds"] / 60, 1),
        ),
        (
            "Previous walking + standing (min)",
            round(ctx["previous_mobility_seconds"] / 60, 1),
        ),
        (
            "Estimated Mobility Improvement (%)",
            (
                round(ctx["mobility_improvement_pct"], 1)
                if ctx["mobility_improvement_pct"] is not None
                else "N/A"
            ),
        ),
    ]

    for offset, (label, value) in enumerate(summary_values):
        summary_sheet.cell(
            row=next_row + offset,
            column=1,
            value=label,
        )

        summary_sheet.cell(
            row=next_row + offset,
            column=2,
            value=value,
        )

    workbook.save(str(destination))

    return str(destination)


# ---------------------------------------------------------
# PDF REPORT - MATCHES THE UPLOADED REFERENCE
# ---------------------------------------------------------

def _generate_pdf(
    patient: Patient,
    report_type: ReportType,
    date_from: datetime,
    date_to: datetime,
    db: Session,
) -> str:

    destination = new_report_path(
        patient.id,
        report_type.value,
        "pdf",
    )

    ctx = _report_context(
        patient,
        report_type,
        date_from,
        date_to,
        db,
    )

    styles = getSampleStyleSheet()

    styles["Title"].alignment = 1
    styles["Title"].fontSize = 17
    styles["Title"].leading = 22

    styles["Heading2"].fontSize = 14
    styles["Heading2"].leading = 18

    doc = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )

    elements = []

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    elements.append(
        Paragraph(
            f"Patient Mobility Report - {report_type.value.title()}",
            styles["Title"],
        )
    )

    # -----------------------------------------------------
    # PATIENT DETAILS
    # -----------------------------------------------------

    patient_line = (
        f"Patient: {patient.name} | "
        f"Room: {patient.room_number or 'N/A'}"
    )

    if patient.age is not None:
        patient_line += f" | Age: {patient.age}"

    elements.append(
        Paragraph(
            patient_line,
            styles["Normal"],
        )
    )

    generated_at = datetime.now(IST)

    elements.append(
        Paragraph(
            "Report generated on: "
            f"{generated_at.strftime('%d-%m-%Y %I:%M:%S %p')} "
            "India Standard Time",
            styles["Normal"],
        )
    )

    period_start = _to_ist(date_from)
    period_end = _to_ist(date_to)

    elements.append(
        Paragraph(
            "Monitoring period: "
            f"{period_start.strftime('%d-%m-%Y %H:%M')} "
            "to "
            f"{period_end.strftime('%d-%m-%Y %H:%M')}",
            styles["Normal"],
        )
    )

    elements.append(Spacer(1, 14))

    # -----------------------------------------------------
    # SUMMARY TABLE
    # -----------------------------------------------------

    recovery_rate = ctx["recovery_rate"]

    recovery_label = (
        f"{recovery_rate:.1f}%"
        if recovery_rate is not None
        else "N/A"
    )

    summary_data = [
        ["Metric", "Value"],

        [
            "Total monitoring time",
            f"{ctx['monitoring_seconds'] / 60:.1f} min",
        ],

        [
            "Walking duration",
            f"{ctx['walking_seconds'] / 60:.1f} min",
        ],

        [
            "Standing duration",
            f"{ctx['standing_seconds'] / 60:.1f} min",
        ],

        [
            "Sitting duration",
            f"{ctx['sitting_seconds'] / 60:.1f} min",
        ],

        [
            "Lying duration",
            f"{ctx['lying_seconds'] / 60:.1f} min",
        ],

        [
            "Recovery Rate (%)",
            recovery_label,
        ],

        [
            "Interpretation",
            ctx["interpretation"],
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[7.5 * cm, 5.0 * cm],
        hAlign="LEFT",
        repeatRows=1,
    )

    summary_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#1e40af"),
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white,
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey,
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                9,
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                6,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                6,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE",
            ),
        ])
    )

    elements.append(summary_table)

    elements.append(Spacer(1, 40))

    # -----------------------------------------------------
    # ACTIVITY DISTRIBUTION
    # -----------------------------------------------------

    elements.append(
        Paragraph(
            "Activity Distribution",
            styles["Heading2"],
        )
    )

    elements.append(Spacer(1, 8))

    pie_png = render_activity_distribution_pie(
        ctx["distribution"]
    )

    pie_chart = Image(
        BytesIO(pie_png),
        width=9 * cm,
        height=6.8 * cm,
    )

    pie_chart.hAlign = "CENTER"

    elements.append(pie_chart)

    elements.append(Spacer(1, 25))

    # -----------------------------------------------------
    # ACTIVITY TIMELINE
    # -----------------------------------------------------

    timeline_date = period_end

    timeline_png = render_activity_timeline(
        ctx["activities"],
        timeline_date=date_to,
    )

    elements.append(
        Paragraph(
            f"Activity Timeline - {timeline_date.strftime('%d-%m-%Y')}",
            styles["Heading2"],
        )
    )

    elements.append(Spacer(1, 8))

    timeline_chart = Image(
        BytesIO(timeline_png),
        width=15.5 * cm,
        height=4.3 * cm,
    )

    timeline_chart.hAlign = "CENTER"

    elements.append(timeline_chart)

    # -----------------------------------------------------
    # BUILD PDF
    # -----------------------------------------------------

    doc.build(elements)

    return str(destination)


# ---------------------------------------------------------
# GENERATE AND SAVE REPORT RECORD
# ---------------------------------------------------------

def generate_report(
    db: Session,
    patient: Patient,
    report_type: ReportType,
    report_format: ReportFormat,
) -> Report:

    date_from, date_to = _period_window(
        report_type
    )

    if report_format == ReportFormat.csv:

        file_path = _generate_csv(
            patient,
            report_type,
            date_from,
            date_to,
            db,
        )

    elif report_format == ReportFormat.xlsx:

        file_path = _generate_xlsx(
            patient,
            report_type,
            date_from,
            date_to,
            db,
        )

    else:

        file_path = _generate_pdf(
            patient,
            report_type,
            date_from,
            date_to,
            db,
        )

    report = Report(
        patient_id=patient.id,
        report_type=report_type,
        report_format=report_format,
        file_path=to_relative_url(
            Path(file_path)
        ),
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    logger.info(
        "Generated %s %s report for patient_id=%s",
        report_type.value,
        report_format.value,
        patient.id,
    )

    return report


# ---------------------------------------------------------
# LIST REPORTS
# ---------------------------------------------------------

def list_reports(
    db: Session,
    patient_id: Optional[int] = None,
):

    query = db.query(Report)

    if patient_id is not None:
        query = query.filter(
            Report.patient_id == patient_id
        )

    return query.order_by(
        Report.generated_at.desc()
    ).all()


# ---------------------------------------------------------
# GET REPORT
# ---------------------------------------------------------

def get_report(
    db: Session,
    report_id: int,
) -> Optional[Report]:

    return (
        db.query(Report)
        .filter(Report.id == report_id)
        .first()
    )


# ---------------------------------------------------------
# DOWNLOAD FILENAME
# ---------------------------------------------------------

def build_download_filename(
    report: Report,
    patient_name: str,
) -> str:

    safe_name = "".join(
        character
        if character.isalnum() or character in " -_"
        else "_"
        for character in patient_name
    ).strip().replace(" ", "_")

    date_str = report.generated_at.strftime(
        "%Y-%m-%d"
    )

    extension = Path(
        report.file_path
    ).suffix.lstrip(".")

    return (
        f"{safe_name}_{report.report_type.value}_"
        f"report_{date_str}.{extension}"
    )
