"""
PDF Verification Report for Chubby-Checker.

Produces a printable / savable PDF named:
    CC_Checked_{JobNumber}_{YYYY-MM-DD}.pdf

Content:
  - Header with job number and check date
  - Status banner: "NO ERRORS" or "ERRORS FOUND"
  - Summary counts by severity
  - Detailed discrepancy listing when errors exist
  - Footer with tool version and timestamp
"""

from pathlib import Path
from datetime import datetime
from typing import List, Optional, Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


# Severity display order and colors
SEVERITY_ORDER = ["CRITICAL", "WARNING", "INFO"]
SEVERITY_COLORS = {
    "CRITICAL": colors.HexColor("#b71c1c"),
    "WARNING": colors.HexColor("#e65100"),
    "INFO": colors.HexColor("#1565c0"),
}


def _safe_job_number(job: Optional[str]) -> str:
    if not job:
        return "UNKNOWN"
    # Keep alphanumeric, dash, underscore
    cleaned = "".join(c for c in job if c.isalnum() or c in "-_")
    return cleaned or "UNKNOWN"


def build_report_filename(job_number: Optional[str], check_date: Optional[datetime] = None) -> str:
    """Return CC_Checked_JobNumber_Date.pdf"""
    dt = check_date or datetime.now()
    date_str = dt.strftime("%Y-%m-%d")
    job = _safe_job_number(job_number)
    return f"CC_Checked_{job}_{date_str}.pdf"


def generate_pdf_report(
    discrepancies: List[Any],
    job_number: Optional[str] = None,
    output_dir: str | Path = ".",
    check_date: Optional[datetime] = None,
    shipper_files: Optional[List[str]] = None,
    drawings_file: Optional[str] = None,
    extra_summary: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Generate the verification PDF and return the path written.

    `discrepancies` should be a list of objects with at least:
        .severity, .category, .message, .rule
        optional: .mark, .expected, .actual
    """
    check_date = check_date or datetime.now()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = build_report_filename(job_number, check_date)
    output_path = output_dir / filename

    # Classify findings
    critical = [d for d in discrepancies if getattr(d, "severity", "").upper() == "CRITICAL"]
    warnings = [d for d in discrepancies if getattr(d, "severity", "").upper() == "WARNING"]
    infos = [d for d in discrepancies if getattr(d, "severity", "").upper() == "INFO"]

    has_errors = len(critical) > 0 or len(warnings) > 0
    status_label = "ERRORS FOUND" if has_errors else "NO ERRORS"

    # Styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Heading1"],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=6,
        textColor=colors.HexColor("#1a237e"),
    ))
    styles.add(ParagraphStyle(
        name="SubHeader",
        parent=styles["Normal"],
        fontSize=11,
        alignment=TA_CENTER,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="StatusOK",
        parent=styles["Heading2"],
        fontSize=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#2e7d32"),
        spaceBefore=12,
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="StatusError",
        parent=styles["Heading2"],
        fontSize=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#b71c1c"),
        spaceBefore=12,
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="SectionHead",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=14,
        spaceAfter=6,
        textColor=colors.HexColor("#333333"),
    ))
    styles.add(ParagraphStyle(
        name="Finding",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="Footer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER,
    ))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    story = []

    # ---- Header ----
    story.append(Paragraph("Chubby-Checker Verification Report", styles["ReportTitle"]))
    story.append(Paragraph("Ascent Buildings — Shipper vs Final Drawings Review", styles["SubHeader"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a237e")))

    # Meta table
    meta = [
        ["Job Number:", _safe_job_number(job_number)],
        ["Check Date:", check_date.strftime("%B %d, %Y  %I:%M %p")],
    ]
    if drawings_file:
        meta.append(["Drawings:", Path(drawings_file).name])
    if shipper_files:
        if len(shipper_files) == 1:
            meta.append(["Shipper:", Path(shipper_files[0]).name])
        else:
            meta.append(["Shippers:", f"{len(shipper_files)} phase file(s)"])

    meta_table = Table(meta, colWidths=[1.4 * inch, 5.2 * inch])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(Spacer(1, 10))
    story.append(meta_table)

    # ---- Status banner ----
    if has_errors:
        story.append(Paragraph(f"⚠  {status_label}", styles["StatusError"]))
    else:
        story.append(Paragraph(f"✓  {status_label}", styles["StatusOK"]))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))

    # ---- Summary counts ----
    story.append(Paragraph("Summary", styles["SectionHead"]))
    summary_data = [
        ["Severity", "Count"],
        ["CRITICAL", str(len(critical))],
        ["WARNING", str(len(warnings))],
        ["INFO", str(len(infos))],
        ["Total findings", str(len(discrepancies))],
    ]
    summary_table = Table(summary_data, colWidths=[2.5 * inch, 1.2 * inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eaf6")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("TEXTCOLOR", (0, 1), (-1, 1), SEVERITY_COLORS["CRITICAL"]),
        ("TEXTCOLOR", (0, 2), (-1, 2), SEVERITY_COLORS["WARNING"]),
        ("TEXTCOLOR", (0, 3), (-1, 3), SEVERITY_COLORS["INFO"]),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(summary_table)

    if extra_summary:
        story.append(Spacer(1, 8))
        for k, v in extra_summary.items():
            story.append(Paragraph(f"<b>{k}:</b> {v}", styles["Finding"]))

    # ---- Detail section ----
    if not has_errors and not infos:
        story.append(Spacer(1, 16))
        story.append(Paragraph(
            "No discrepancies were flagged by the current rule set. "
            "This shipper appears consistent with the Final Drawings for the checks performed.",
            styles["Finding"],
        ))
    else:
        # Errors first (CRITICAL + WARNING)
        if has_errors:
            story.append(Paragraph("Errors / Discrepancies to Review", styles["SectionHead"]))
            story.append(Paragraph(
                "The following items require review before release.",
                styles["Finding"],
            ))
            story.append(Spacer(1, 4))

            for sev in ["CRITICAL", "WARNING"]:
                items = [d for d in discrepancies if getattr(d, "severity", "").upper() == sev]
                if not items:
                    continue
                color = SEVERITY_COLORS[sev]
                story.append(Paragraph(
                    f"<font color='#{color.hexval()[2:]}'><b>{sev}</b></font> ({len(items)})",
                    styles["Finding"],
                ))
                for d in items:
                    mark = getattr(d, "mark", "") or ""
                    mark_prefix = f"[<b>{mark}</b>] " if mark else ""
                    cat = getattr(d, "category", "")
                    msg = getattr(d, "message", "")
                    rule = getattr(d, "rule", "")
                    line = f"• <b>{cat}</b> ({rule}): {mark_prefix}{msg}"
                    story.append(Paragraph(line, styles["Finding"]))
                    exp = getattr(d, "expected", None)
                    act = getattr(d, "actual", None)
                    if exp is not None or act is not None:
                        story.append(Paragraph(
                            f"&nbsp;&nbsp;&nbsp;&nbsp;Expected: {exp} &nbsp;|&nbsp; Actual: {act}",
                            styles["Finding"],
                        ))
                story.append(Spacer(1, 6))

        # INFO findings
        if infos:
            story.append(Paragraph("Informational Notes", styles["SectionHead"]))
            for d in infos:
                mark = getattr(d, "mark", "") or ""
                mark_prefix = f"[<b>{mark}</b>] " if mark else ""
                cat = getattr(d, "category", "")
                msg = getattr(d, "message", "")
                rule = getattr(d, "rule", "")
                line = f"• <b>{cat}</b> ({rule}): {mark_prefix}{msg}"
                story.append(Paragraph(line, styles["Finding"]))

    # ---- Footer ----
    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated by Chubby-Checker &nbsp;|&nbsp; {check_date.strftime('%Y-%m-%d %H:%M')} &nbsp;|&nbsp; "
        f"File: {filename}",
        styles["Footer"],
    ))
    story.append(Paragraph(
        "This report is a quality-control aid. Final acceptance remains the responsibility of the reviewing engineer / detailer.",
        styles["Footer"],
    ))

    doc.build(story)
    return output_path
