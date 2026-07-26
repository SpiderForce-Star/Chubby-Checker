"""
Parser for Ascent Final Erection Drawings PDFs.

Strengthened Member Table extraction based on real jobs:
25-13266, 25-13059, 25-13168.

Looks for tables containing:
  Quantity | Mark | Part (or Length / Section)
and converts them into Piece objects.
"""

from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import re
import pdfplumber
from chubby_checker.models.piece import Piece


def _parse_length_to_inches(length_str: str) -> Optional[float]:
    """
    Convert Ascent-style length strings to total inches.
    Examples:
      29'-7 3/8"  → 355.375
      26'-11 1/2" → 323.5
      12'-0"      → 144.0
    """
    if not length_str:
        return None
    s = length_str.strip().replace('”', '"').replace("'", "'")

    # Pattern: feet'-inches[ fraction]"
    m = re.match(
        r"(\d+)\s*'\s*-?\s*(\d+)?\s*(\d+/\d+)?\s*\"?",
        s,
    )
    if not m:
        # Try simple feet only
        m2 = re.match(r"(\d+)\s*'", s)
        if m2:
            return float(m2.group(1)) * 12.0
        return None

    feet = int(m.group(1))
    inches = int(m.group(2) or 0)
    frac = 0.0
    if m.group(3):
        num, den = m.group(3).split("/")
        frac = float(num) / float(den)

    return feet * 12.0 + inches + frac


class DrawingsParser:
    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        self.member_tables: Dict[str, List[Piece]] = {}
        self.notes: List[str] = []
        self.building_info: Dict[str, Any] = {}
        self.panel_info: Dict[str, Any] = {}
        self.raw_pages: List[str] = []

    def parse(self) -> Dict[str, List[Piece]]:
        """Main entry – extract all Member Tables and notes."""
        with pdfplumber.open(self.pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                self.raw_pages.append(text)

                self._extract_notes_and_info(text)
                tables = page.extract_tables() or []
                self._process_member_tables(tables, text, page_number=i + 1)

        return self.member_tables

    # ------------------------------------------------------------------
    # Notes & high-level info
    # ------------------------------------------------------------------
    def _extract_notes_and_info(self, text: str):
        upper = text.upper()

        if "MEZZANINE" in upper:
            self.notes.append("Mezzanine present")
            self.building_info["has_mezzanine"] = True

        if re.search(r"\b(crane|runway\s+beam|runway\s+support)\b", text, re.IGNORECASE):
            self.notes.append("Crane / runway system referenced")
            self.building_info["has_crane"] = True

        if re.search(r"\b(joist|new\s+millennium)\b", text, re.IGNORECASE):
            self.notes.append("Joists referenced (likely buy-out)")

        # Panel type / coverage hints
        if re.search(r"24\s*Ga\.?\s*CS|Central\s+Seam|CS244", text, re.IGNORECASE):
            self.panel_info["type"] = "Central Seam"
            self.panel_info["coverage"] = 24
        if re.search(r"CS184|18\"\s*PANEL", text, re.IGNORECASE):
            self.panel_info["coverage_18"] = True
        if re.search(r"VS16|16\"\s*(wide|panel|coverage)", text, re.IGNORECASE):
            self.panel_info["coverage"] = 16
            self.panel_info["type"] = "VS16"

        # Rough building size
        m = re.search(
            r"(\d{2,3})['\u2019]?\s*-?\s*(\d+)?\s*[xX×]\s*(\d{2,3})['\u2019]?",
            text,
        )
        if m and "size_hint" not in self.building_info:
            self.building_info["size_hint"] = m.group(0)

    # ------------------------------------------------------------------
    # Member Table parsing
    # ------------------------------------------------------------------
    def _process_member_tables(self, tables: List, page_text: str, page_number: int):
        for table in tables:
            if not table or len(table) < 2:
                continue

            header = [str(c or "").strip().lower() for c in table[0]]
            header_str = " ".join(header)

            # Strong signals that this is a Member Table
            has_mark = any("mark" in h for h in header)
            has_qty = any(
                h in ("qty", "qnty", "quantity", "no.", "no", "#") or "qty" in h or "qnty" in h
                for h in header
            )
            has_part = any("part" in h or "section" in h for h in header)

            if not (has_mark and (has_qty or has_part)):
                continue

            # Determine a category / location label
            category = self._guess_table_category(page_text, header_str, page_number)

            col_map = self._map_columns(header)

            for row in table[1:]:
                piece = self._row_to_piece(row, col_map, category)
                if piece:
                    self.member_tables.setdefault(category, []).append(piece)

    def _map_columns(self, header: List[str]) -> Dict[str, int]:
        col_map = {}
        for i, h in enumerate(header):
            h = h.lower()
            if h in ("qty", "qnty", "quantity", "no.", "no", "#") or "qty" in h or "qnty" in h:
                col_map["qty"] = i
            elif "mark" in h:
                col_map["mark"] = i
            elif "part" in h or "section" in h:
                col_map["part"] = i
            elif "length" in h:
                col_map["length"] = i
            elif "description" in h or "desc" in h:
                col_map["desc"] = i
            elif "weight" in h:
                col_map["weight"] = i
        return col_map

    def _row_to_piece(
        self, row: List, col_map: Dict[str, int], category: str
    ) -> Optional[Piece]:
        if not row:
            return None

        def get(col_key: str, default="") -> str:
            idx = col_map.get(col_key)
            if idx is None or idx >= len(row):
                return default
            return str(row[idx] or "").strip()

        mark = get("mark")
        if not mark or len(mark) < 2:
            return None

        # Quantity
        qty = 1
        qty_str = get("qty")
        m = re.match(r"(\d+)", qty_str)
        if m:
            qty = int(m.group(1))

        part = get("part") or get("desc")
        length_str = get("length")
        length_inches = _parse_length_to_inches(length_str) if length_str else None

        weight = None
        weight_str = get("weight").replace(",", "")
        try:
            weight = float(weight_str) if weight_str else None
        except ValueError:
            pass

        # Try to detect section from part field (W21X44, C10x15.3, Z102516, HSS, etc.)
        section = None
        if part:
            sec_match = re.search(
                r"((?:W|C|MC|S|HSS|TS|L|Z|Pipe)\s*\d+[xX×]\d+(?:\.\d+)?)",
                part,
                re.IGNORECASE,
            )
            if sec_match:
                section = sec_match.group(1).upper().replace(" ", "")

        return Piece(
            mark=mark,
            description=part or "",
            quantity=qty,
            length=length_str or None,
            length_inches=length_inches,
            weight=weight,
            section=section,
            category=category,
            source="drawings",
        )

    def _guess_table_category(self, page_text: str, header_str: str, page_number: int) -> str:
        upper = page_text.upper()

        if "ROOF" in upper and "FRAMING" in upper:
            return "Roof Framing"
        if "MAIN FRAME" in upper or "RIGID FRAME" in upper:
            return "Main Frames"
        if "ENDWALL" in upper:
            return "Endwall"
        if "SIDEWALL" in upper:
            return "Sidewall"
        if "MEZZANINE" in upper or "FLOOR BEAM" in upper:
            return "Mezzanine"
        if "RUNWAY" in upper:
            return "Runway Beams"
        if "PURLIN" in upper or "GIRT" in upper:
            return "Secondary"
        if "FRAME LINE" in upper:
            # Try to capture frame line number
            m = re.search(r"FRAME\s+LINE\s*[:=]?\s*(\w+)", page_text, re.IGNORECASE)
            if m:
                return f"Frame Line {m.group(1)}"

        return f"Member Table (p{page_number})"

    # ------------------------------------------------------------------
    # Public helpers used by the engine / CLI
    # ------------------------------------------------------------------
    def get_notes(self) -> Dict[str, Any]:
        return {
            "notes": self.notes,
            "has_mezzanine": self.building_info.get("has_mezzanine", False),
            "has_crane": self.building_info.get("has_crane", False),
            "building_info": self.building_info,
            "panel_info": self.panel_info,
        }

    def get_all_pieces(self) -> List[Piece]:
        all_pieces = []
        for pieces in self.member_tables.values():
            all_pieces.extend(pieces)
        return all_pieces

    def get_mark_quantity_map(self) -> Dict[str, int]:
        """Flatten to mark → total quantity (useful for discrepancy engine)."""
        result: Dict[str, int] = {}
        for pieces in self.member_tables.values():
            for p in pieces:
                result[p.mark] = result.get(p.mark, 0) + p.quantity
        return result
