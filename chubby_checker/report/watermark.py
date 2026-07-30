"""
PDF page helpers for Chubby Checker reports.

Page-wide diagonal watermarks and corner logo stamps are intentionally
disabled. Branding lives in the report header flowables only (logo + title).
Optional page numbers can still be painted when a custom canvas is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as pdfcanvas

from chubby_checker.branding import find_logo


def _draw_corner_logo(
    c: pdfcanvas.Canvas,
    logo_path: Path,
    page_w: float,
    page_h: float,
    max_width: float = 0.85 * inch,
) -> None:
    """Legacy helper — not used for reports (header logo only)."""
    try:
        img_w = max_width
        img_h = max_width
        x = page_w - img_w - 0.45 * inch
        y = page_h - img_h - 0.35 * inch
        c.drawImage(
            str(logo_path),
            x,
            y,
            width=img_w,
            height=img_h,
            preserveAspectRatio=True,
            mask="auto",
        )
    except Exception:
        pass


def make_page_canvas(
    watermark_text: Optional[str] = None,
    logo_path: Optional[Path] = None,
    status_label: Optional[str] = None,
    *,
    draw_watermark: bool = False,
    draw_corner_logo: bool = False,
):
    """
    Return a canvas factory for SimpleDocTemplate.build(..., canvasmaker=...).

    Diagonal text watermarks and per-page corner logos are off by default
    (and ignored when draw_watermark/draw_corner_logo remain False).
    Only page numbers are painted when this canvas is used.
    """
    # watermark_text / status_label intentionally unused for page stamping
    _ = watermark_text, status_label
    resolved_logo = logo_path or find_logo()

    class BrandCanvas(pdfcanvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self._paint_page(num_pages)
                super().showPage()
            super().save()

        def _paint_page(self, page_count: int):
            page_w, page_h = letter
            # No diagonal text. No "ERRORS FOUND" / product name across the page.
            if draw_corner_logo and resolved_logo and resolved_logo.is_file():
                _draw_corner_logo(self, resolved_logo, page_w, page_h)
            self.setFont("Helvetica", 8)
            self.setFillGray(0.45)
            page_no = self._pageNumber
            self.drawCentredString(page_w / 2.0, 0.35 * inch, f"Page {page_no} of {page_count}")

    return BrandCanvas


def apply_logo_header_flowable(logo_path: Optional[Path] = None, width: float = 0.9 * inch):
    """
    Return a reportlab Image flowable for the header, or None if logo missing.
    """
    from reportlab.platypus import Image

    path = logo_path or find_logo()
    if not path or not path.is_file():
        return None
    try:
        img = Image(str(path), width=width, height=width, kind="proportional")
        img.hAlign = "CENTER"
        return img
    except Exception:
        return None
