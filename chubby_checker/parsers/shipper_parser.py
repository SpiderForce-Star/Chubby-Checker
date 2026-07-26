"""
Parser for Ascent Buildings Complete Shipper PDFs.

Extracts structured data from multi-page categorized shippers using pdfplumber.
Calibrated on real jobs: 25-13266, 25-13059, 25-13168 (PH1/PH3/PH4/PH5/PH6).
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import re
import pdfplumber
from chubby_checker.models.piece import Piece


@dataclass
class ShipperSummary:
    job_number: str = ""
    phase: str = ""
    total_weight: float = 0.0
    category_weights: Dict[str, float] = field(default_factory=dict)


class ShipperParser:
    """Extract pieces, accessories, and panel data from Ascent Complete Shipper PDFs."""

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        self.summary = ShipperSummary()
        self.categories: Dict[str, List[Piece]] = {}
        self.ss_accessories: Dict[str, int] = {
            "sliding_clips": 0,
            "backup_plates_24": 0,
            "backup_plates_18": 0,
            "thermal_blocks": 0,
            "hi_eave_plates": 0,
            "clip_screws": 0,
            "other": 0,
        }
        self.panel_coverage: Dict[str, int] = {}  # e.g. {"24": 1224, "18": 6, "16": 0}
        self.screws: Dict[str, int] = {}

    def parse(self) -> Dict[str, Any]:
        """Main entry point. Returns full structured extraction."""
        with pdfplumber.open(self.pdf_path) as pdf:
            self._parse_cover(pdf.pages[0] if pdf.pages else None)
            for page in pdf.pages:
                text = page.extract_text() or ""
                tables = page.extract_tables() or []

                if "SS Accessories" in text or "SS Accessories" in (page.extract_text() or ""):
                    self._parse_ss_accessories(tables, text)
                elif "Standing Seam" in text and "Roof Sheet" in text:
                    self._parse_standing_seam(tables, text)
                elif "Screws_Fasteners" in text or "Screws" in text:
                    self._parse_screws(tables, text)
                elif any(cat in text for cat in ["Cold Formed Steel", "Fabricated Steel", "Hot Rolled"]):
                    self._parse_structural_table(tables, text)

        return {
            "summary": self.summary,
            "categories": self.categories,
            "ss_accessories": self.ss_accessories,
            "panel_coverage": self.panel_coverage,
            "screws": self.screws,
        }

    def _parse_cover(self, page) -> None:
        if not page:
            return
        text = page.extract_text() or ""
        # Job number patterns: 25-13168 or 25-13168 PH4
        m = re.search(r"(25-\d{5})(?:\s*(PH\d+))?", text)
        if m:
            self.summary.job_number = m.group(1)
            self.summary.phase = m.group(2) or ""

        # Weight total
        m = re.search(r"Wt Total[:\s]*([\d,]+\.?\d*)", text, re.IGNORECASE)
        if m:
            self.summary.total_weight = float(m.group(1).replace(",", ""))

        # Category weights from Shipping List Index
        for line in text.splitlines():
            if any(k in line for k in ["Cold Formed", "Standing Seam", "Fabricated", "Hot Rolled", "Screws", "Bolts", "Trim"]):
                parts = re.findall(r"([\d,]+\.\d+)", line)
                if parts:
                    # Heuristic: last number is often the weight
                    try:
                        wt = float(parts[-1].replace(",", ""))
                        key = line.split()[0] if line.split() else "unknown"
                        self.summary.category_weights[key] = wt
                    except ValueError:
                        pass

    def _parse_ss_accessories(self, tables: List, text: str) -> None:
        """Extract clip, backup plate, thermal block counts from SS Accessories pages."""
        for table in tables:
            for row in table:
                if not row or len(row) < 3:
                    continue
                row_str = " ".join(str(c or "") for c in row).lower()
                qty = self._safe_int(row[0] if row else 0)

                if "sliding clip" in row_str or "csp212" in row_str or "2\" high sliding" in row_str:
                    self.ss_accessories["sliding_clips"] += qty
                elif "24\" back" in row_str or "24\" backup" in row_str or "cl7760" in row_str:
                    self.ss_accessories["backup_plates_24"] += qty
                elif "18\" back" in row_str or "18\" backup" in row_str:
                    self.ss_accessories["backup_plates_18"] += qty
                elif "thermal block" in row_str or "cl575" in row_str:
                    self.ss_accessories["thermal_blocks"] += qty
                elif "hi-eave" in row_str or "hi eave" in row_str:
                    self.ss_accessories["hi_eave_plates"] += qty

    def _parse_standing_seam(self, tables: List, text: str) -> None:
        """Detect panel coverage from part numbers (CS244=24\", CS184=18\", VS16=16\")."""
        for table in tables:
            for row in table:
                if not row:
                    continue
                row_str = " ".join(str(c or "") for c in row).upper()
                qty = self._safe_int(row[0] if row else 0)

                if "CS244" in row_str or "24\"" in row_str:
                    self.panel_coverage["24"] = self.panel_coverage.get("24", 0) + qty
                elif "CS184" in row_str or "18\"" in row_str:
                    self.panel_coverage["18"] = self.panel_coverage.get("18", 0) + qty
                elif "VS16" in row_str or "16\"" in row_str or "CS16" in row_str:
                    self.panel_coverage["16"] = self.panel_coverage.get("16", 0) + qty

    def _parse_screws(self, tables: List, text: str) -> None:
        for table in tables:
            for row in table:
                if not row or len(row) < 2:
                    continue
                qty = self._safe_int(row[0])
                desc = " ".join(str(c or "") for c in row[1:]).lower()
                if "clip screw" in desc or "fss10" in desc or "panel clip" in desc:
                    self.ss_accessories["clip_screws"] += qty
                    self.screws["clip_screws"] = self.screws.get("clip_screws", 0) + qty
                elif qty > 0:
                    key = desc[:40] if desc else "unknown"
                    self.screws[key] = self.screws.get(key, 0) + qty

    def _parse_structural_table(self, tables: List, text: str) -> None:
        """Generic structural member extraction (Cold Formed, Fabricated, HR)."""
        category = "Unknown"
        if "Cold Formed" in text:
            category = "Cold Formed Steel"
        elif "Fabricated" in text:
            category = "Fabricated Steel"
        elif "Hot Rolled" in text:
            category = "Hot Rolled"

        if category not in self.categories:
            self.categories[category] = []

        for table in tables:
            for row in table:
                if not row or len(row) < 4:
                    continue
                # Typical columns: Qty | Mark | Description | ... Length | Weight
                try:
                    qty = self._safe_int(row[0])
                    mark = str(row[1] or "").strip()
                    desc = str(row[2] or "").strip()
                    if qty > 0 and mark:
                        piece = Piece(
                            mark=mark,
                            description=desc,
                            quantity=qty,
                            category=category,
                        )
                        self.categories[category].append(piece)
                except Exception:
                    continue

    @staticmethod
    def _safe_int(val) -> int:
        try:
            if val is None:
                return 0
            s = str(val).replace(",", "").strip()
            return int(float(s)) if s else 0
        except (ValueError, TypeError):
            return 0

    def get_ss_accessories(self) -> Dict[str, int]:
        return self.ss_accessories

    def get_panel_coverage(self) -> Dict[str, int]:
        return self.panel_coverage
