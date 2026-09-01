"""De-identified demo safety-case PDF rendering.

This module accepts an intentionally narrow data transfer object. Patient-account,
e-consent, signature, ABHA, and patient-request fields cannot be passed to it.
The generated document is decision-support output, not an official regulatory form.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


DISCLAIMER = (
    "Demo decision support only - not an official regulatory submission. "
    "This report has not been validated against CDSCO, CIOMS, or NPvCC "
    "reporting requirements."
)


@dataclass(frozen=True)
class SafetyCaseReportData:
    """Only the de-identified clinical fields permitted in the PDF."""

    protocol_number: str
    trial_title: str
    ctri_number: str | None
    sponsor_name: str
    site_code: str
    site_name: str
    site_location: str
    subject_code: str
    subject_sex: str
    subject_age_at_enrollment: int | None
    study_arm: str
    ae_number: str
    term_verbatim: str
    description: str
    onset_date: date
    resolution_date: date | None
    severity: str
    is_serious: bool
    seriousness_criteria: str | None
    causality: str
    outcome: str
    action_taken: str | None
    meddra_pt_code: str | None
    meddra_pt_term: str | None
    meddra_soc: str | None
    coding_confidence: float | None
    reported_date: date | None
    reported_to_ec: bool
    reported_to_ec_date: date | None


def _display(value: object | None) -> str:
    if value is None or value == "":
        return "Not recorded"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def build_safety_case_pdf(data: SafetyCaseReportData) -> bytes:
    """Render one de-identified safety case as a valid PDF byte string."""
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Safety report {data.ae_number}",
        author="AIIA Clinical Trials Dashboard",
        subject="De-identified demo safety case report",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SafetyTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=7 * mm,
    )
    disclaimer_style = ParagraphStyle(
        "SafetyDisclaimer",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#7A1F1F"),
        backColor=colors.HexColor("#FDECEC"),
        borderColor=colors.HexColor("#D8A0A0"),
        borderWidth=0.5,
        borderPadding=6,
        spaceAfter=6 * mm,
    )
    section_style = ParagraphStyle(
        "SafetySection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        textColor=colors.white,
        backColor=colors.HexColor("#2F5597"),
        borderPadding=4,
        spaceBefore=3 * mm,
        spaceAfter=2 * mm,
    )
    label_style = ParagraphStyle(
        "SafetyLabel",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
    )
    value_style = ParagraphStyle(
        "SafetyValue",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
    )

    def paragraph(value: object | None, style=value_style) -> Paragraph:
        return Paragraph(escape(_display(value)), style)

    def section(title: str, rows: list[tuple[str, object | None]]) -> list[object]:
        table_rows = [
            [paragraph(label, label_style), paragraph(value)]
            for label, value in rows
        ]
        table = Table(table_rows, colWidths=[52 * mm, 105 * mm], repeatRows=0)
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7C9E2")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF0F8")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return [Paragraph(escape(title), section_style), table, Spacer(1, 2 * mm)]

    story: list[object] = [
        Paragraph("DE-IDENTIFIED DEMO SAFETY CASE REPORT", title_style),
        Paragraph(escape(DISCLAIMER), disclaimer_style),
    ]
    story.extend(
        section(
            "Trial and site",
            [
                ("Protocol number", data.protocol_number),
                ("Trial title", data.trial_title),
                ("CTRI number", data.ctri_number),
                ("Sponsor", data.sponsor_name),
                ("Site code", data.site_code),
                ("Site", data.site_name),
                ("Site location", data.site_location),
            ],
        )
    )
    story.extend(
        section(
            "De-identified participant",
            [
                ("Subject code", data.subject_code),
                ("Sex", data.subject_sex),
                ("Age at enrollment", data.subject_age_at_enrollment),
                ("Study arm", data.study_arm),
            ],
        )
    )
    story.extend(
        section(
            "Adverse event",
            [
                ("AE number", data.ae_number),
                ("Verbatim term", data.term_verbatim),
                ("Narrative", data.description),
                ("Onset date", data.onset_date),
                ("Resolution date", data.resolution_date),
                ("Severity", data.severity),
                ("Serious event", data.is_serious),
                ("Seriousness criteria", data.seriousness_criteria),
                ("Causality", data.causality),
                ("Outcome", data.outcome),
                ("Action taken", data.action_taken),
            ],
        )
    )
    story.extend(
        section(
            "Coding and reporting status",
            [
                ("MedDRA PT code", data.meddra_pt_code),
                ("MedDRA PT term", data.meddra_pt_term),
                ("MedDRA SOC", data.meddra_soc),
                ("Coding confidence", data.coding_confidence),
                ("Reported date", data.reported_date),
                ("Reported to Ethics Committee", data.reported_to_ec),
                ("Ethics Committee report date", data.reported_to_ec_date),
            ],
        )
    )

    document.build(story)
    return output.getvalue()