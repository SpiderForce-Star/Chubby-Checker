"""
PDF Verification Report for Ascent Shipper Checker (codename Chubby Checker).

Produces a printable / savable PDF named:
    CC_Checked_{JobNumber}_{YYYY-MM-DD}.pdf

Includes Ascent Buildings logo (header + page corner) and diagonal watermark.
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
from reportlab.lib.enums import TA_CENTER

from chubby_checker.branding import PRODUCT_NAME, CODENAME, COMPANY_NAME, find_logo
from chubby_checker.report.watermark import make_page_canvas, apply_logo_header_flowable

SEVERITY_COLORS = {
    "CRITICAL": colors.HexColor("#b71c1c"),
    "WARNING": colors.HexColor("#e65100"),
    "INFO": colors.HexColor("#1565c0"),
}


def _safe_job_number(job: Optional[str]) -> str:
    if not job:
        return "UNKNOWN"
    cleaned = "".join(c for c in job if c.isalnum() or c in "-_")
    return cleaned or "UNKNOWN"


def build_report_filename(job_number: Optional[str], check_date: Optional[datetime] = None) -> str:
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
    watermark: bool = True,
    logo_path: Optional[str | Path] = None,
) -> Path:
    check_date = check_date or datetime.now()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = build_report_filename(job_number, check_date)
    output_path = output_dir / filename

    critical = [d for d in discrepancies if getattr(d, "severity", "").upper() == "CRITICAL"]
    warnings = [d for d in discrepancies if getattr(d, "severity", "").upper() == "WARNING"]
    infos = [d for d in discrepancies if getattr(d, "severity", "").upper() == "INFO"]

    has_errors = len(critical) > 0 or len(warnings) > 0
    status_label = "ERRORS FOUND" if has_errors else "NO ERRORS"

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", parent=styles["Heading1"], fontSize=18,
        alignment=TA_CENTER, spaceAfter=4, textColor=colors.HexColor("#1a237e"),
    ))
    styles.add(ParagraphStyle(
        name="SubHeader", parent=styles["Normal"], fontSize=11,
        alignment=TA_CENTER, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="StatusOK", parent=styles["Heading2"], fontSize=16,
        alignment=TA_CENTER, textColor=colors.HexColor("#2e7d32"),
        spaceBefore=10, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="StatusError", parent=styles["Heading2"], fontSize=16,
        alignment=TA_CENTER, textColor=colors.HexColor("#b71c1c"),
        spaceBefore=10, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="SectionHead", parent=styles["Heading2"], fontSize=12,
        spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#333333"),
    ))
    styles.add(ParagraphStyle(
        name="Finding", parent=styles["Normal"], fontSize=9, leading=12, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="Footer", parent=styles["Normal"], fontSize=8,
        textColor=colors.grey, alignment=TA_CENTER,
    ))

    resolved_logo = Path(logo_path) if logo_path else find_logo()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=f"{PRODUCT_NAME} — {_safe_job_number(job_number)}",
        author=COMPANY_NAME,
        subject=f"Shipper verification report ({status_label})",
    )

    story = []

    # ---- Header with logo ----
    logo_flow = apply_logo_header_flowable(resolved_logo, width=0.85 * inch)
    if logo_flow is not None:
        story.append(logo_flow)
        story.append(Spacer(1, 6))

    story.append(Paragraph(PRODUCT_NAME, styles["ReportTitle"]))
    story.append(Paragraph(
        f"Verification Report &nbsp;•&nbsp; codename {CODENAME}",
        styles["SubHeader"],
    ))
    story.append(Paragraph(
        f"{COMPANY_NAME} — Shipper vs Final Drawings Review",
        styles["SubHeader"],
    ))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a237e")))

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

    if has_errors:
        story.append(Paragraph(f"⚠  {status_label}", styles["StatusError"]))
    else:
        story.append(Paragraph(f"✓  {status_label}", styles["StatusOK"]))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))

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

    if not has_errors and not infos:
        story.append(Spacer(1, 16))
        story.append(Paragraph(
            "No discrepancies were flagged by the current rule set. "
            "This shipper appears consistent with the Final Drawings for the checks performed.",
            styles["Finding"],
        ))
    else:
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

    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated by {PRODUCT_NAME} ({CODENAME}) &nbsp;|&nbsp; "
        f"{check_date.strftime('%Y-%m-%d %H:%M')} &nbsp;|&nbsp; File: {filename}",
        styles["Footer"],
    ))
    story.append(Paragraph(
        f"Internal {COMPANY_NAME} QC aid. Final acceptance remains the responsibility "
        "of the reviewing engineer / detailer.",
        styles["Footer"],
    ))

    canvasmaker = None
    if watermark:
        canvasmaker = make_page_canvas(
            watermark_text=f"{COMPANY_NAME}  ·  {PRODUCT_NAME}",
            logo_path=resolved_logo,
            status_label=status_label,
        )

    if canvasmaker is not None:
        doc.build(story, canvasmaker=canvasmaker)
    else:
        doc.build(story)

    return output_path
