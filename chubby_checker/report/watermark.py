"""
PDF watermark helpers for Ascent Shipper Checker reports.

Applies a light diagonal text watermark and optional centered logo mark on
each page after the story is built (via reportlab canvas callbacks).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as pdfcanvas

from chubby_checker.branding import PRODUCT_NAME, COMPANY_NAME, find_logo


def _draw_diagonal_text(c: pdfcanvas.Canvas, text: str, page_w: float, page_h: float) -> None:
    c.saveState()
    c.setFont("Helvetica", 28)
    c.setFillGray(0.88)
    c.translate(page_w / 2.0, page_h / 2.0)
    c.rotate(35)
    c.drawCentredString(0, 0, text)
    c.restoreState()


def _draw_corner_logo(
    c: pdfcanvas.Canvas,
    logo_path: Path,
    page_w: float,
    page_h: float,
    max_width: float = 0.85 * inch,
) -> None:
    try:
        # Keep aspect; place top-right
        img_w = max_width
        img_h = max_width  # square-ish source logo
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
        # Never fail report generation because of logo issues
        pass


def make_page_canvas(
    watermark_text: Optional[str] = None,
    logo_path: Optional[Path] = None,
    status_label: Optional[str] = None,
):
    """
    Return a multi_canvas factory for SimpleDocTemplate.build(..., canvasmaker=...)
    that stamps logo + watermark on every page.
    """
    text = watermark_text or f"{COMPANY_NAME}  ·  {PRODUCT_NAME}"
    if status_label:
        text = f"{text}  ·  {status_label}"

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
            _draw_diagonal_text(self, text, page_w, page_h)
            if resolved_logo and resolved_logo.is_file():
                _draw_corner_logo(self, resolved_logo, page_w, page_h)
            # page number
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
