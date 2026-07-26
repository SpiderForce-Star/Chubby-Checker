"""
Parser for Ascent Final Erection Drawings PDFs.

Focuses on:
- Member Tables (primary, secondary, runway, mezzanine)
- Bolt Tables
- Panel / Sheeting schedules
- Key notes (crane, mezzanine location, loads)
"""

from pathlib import Path
from typing import Dict, List, Any
import re
import pdfplumber
from chubby_checker.models.piece import Piece


class DrawingsParser:
    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        self.member_tables: Dict[str, List[Piece]] = {}
        self.notes: List[str] = []
        self.building_info: Dict[str, Any] = {}

    def parse(self) -> Dict[str, List[Piece]]:
        """Extract member tables and key information from drawings."""
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                self._extract_notes(text)
                tables = page.extract_tables() or []
                self._process_member_tables(tables, text)
        return self.member_tables

    def _extract_notes(self, text: str):
        """Pull important design notes."""
        if "MEZZANINE" in text.upper():
            self.notes.append("Mezzanine present")
        if re.search(r"crane|runway", text, re.IGNORECASE):
            self.notes.append("Crane / runway system referenced")
        # Building size patterns
        m = re.search(r"(\d+)'-\s*(\d+)\"?\s*[xX×]\s*(\d+)'-\s*(\d+)", text)
        if m:
            self.building_info["size_hint"] = m.group(0)

    def _process_member_tables(self, tables: List, page_text: str):
        """Attempt to parse Member Table style tables."""
        for table in tables:
            if not table or len(table) < 2:
                continue
            header = [str(c or "").lower() for c in table[0]]
            if any("mark" in h for h in header) and any(
                "qty" in h or "qnty" in h or "no." in h for h in header
            ):
                # Basic extraction similar to shipper
                for row in table[1:]:
                    if not row:
                        continue
                    try:
                        mark = str(row[1] if len(row) > 1 else "").strip()
                        if not mark:
                            continue
                        qty = 1
                        qty_candidate = str(row[0] or "").strip()
                        if re.match(r"^\d+$", qty_candidate):
                            qty = int(qty_candidate)
                        piece = Piece(
                            mark=mark,
                            description=str(row[2] if len(row) > 2 else ""),
                            quantity=qty,
                            source="drawings",
                        )
                        self.member_tables.setdefault("Member Table", []).append(piece)
                    except Exception:
                        continue
