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
from chubby_checker.rules.pemb_components import detect_pemb_signals
from chubby_checker.utils.boilerplate import (
    is_non_piece_mark,
    is_skylight_osha_boilerplate,
    strip_skylight_osha_paragraphs,
)


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
        signals = detect_pemb_signals(raw_text=text)

        if signals.get("mezzanine") or "MEZZANINE" in upper:
            if "Mezzanine present" not in self.notes:
                self.notes.append("Mezzanine present")
            self.building_info["has_mezzanine"] = True

        if signals.get("crane") or re.search(
            r"\b(crane|runway\s+beam|runway\s+support)\b", text, re.IGNORECASE
        ):
            if "Crane / runway system referenced" not in self.notes:
                self.notes.append("Crane / runway system referenced")
            self.building_info["has_crane"] = True

        if signals.get("bdeck_joist") or re.search(
            r"\b(joist|new\s+millennium|b-?deck)\b", text, re.IGNORECASE
        ):
            note = "Joists / structural deck referenced (likely buy-out)"
            if note not in self.notes:
                self.notes.append(note)
            self.building_info["has_bdeck_joist"] = True

        if signals.get("imp"):
            note = "Insulated metal panels (IMP) referenced"
            if note not in self.notes:
                self.notes.append(note)
            self.building_info["has_imp"] = True

        if signals.get("primary_framing"):
            self.building_info["has_primary_framing"] = True
        if signals.get("secondary_framing"):
            self.building_info["has_secondary_framing"] = True
        if signals.get("standing_seam"):
            self.building_info["has_standing_seam"] = True
            note = "Standing seam panel system referenced"
            if note not in self.notes:
                self.notes.append(note)
        if signals.get("exposed_fastener"):
            self.building_info["has_exposed_panels"] = True
        if signals.get("concealed_wall"):
            self.building_info["has_concealed_wall"] = True
        if signals.get("liner"):
            self.building_info["has_liner"] = True
        if signals.get("sealant_mentioned"):
            self.building_info["mentions_sealant"] = True
        if signals.get("trim_mentioned"):
            self.building_info["mentions_trim"] = True

        vendors = signals.get("vendors_hinted") or []
        if vendors:
            prev = list(self.building_info.get("vendors_hinted") or [])
            for v in vendors:
                if v not in prev:
                    prev.append(v)
            self.building_info["vendors_hinted"] = prev

        # Merge panel family list
        fams = list(self.panel_info.get("families") or [])
        for f in signals.get("panel_families") or []:
            if f not in fams:
                fams.append(f)
        if fams:
            self.panel_info["families"] = fams

        # Panel type / coverage hints (Ascent + multi-vendor)
        if re.search(r"24\s*Ga\.?\s*CS|Central\s+Seam|CS244|Central-?Loc|Central\s+Loc", text, re.IGNORECASE):
            self.panel_info["type"] = self.panel_info.get("type") or "Central Seam / Central-Loc"
            self.panel_info["coverage"] = self.panel_info.get("coverage") or 24
        if re.search(r"CS184|18\"\s*PANEL|18\s*in(?:ch)?\s*(?:standing|coverage|panel)", text, re.IGNORECASE):
            self.panel_info["coverage_18"] = True
            self.panel_info["coverage"] = self.panel_info.get("coverage") or 18
        if re.search(r"VS16|VSR6|16\"\s*(wide|panel|coverage)|Central-?Span", text, re.IGNORECASE):
            self.panel_info["coverage"] = 16
            self.panel_info["type"] = "VS16 / VSR6 / Central-Span"
        if re.search(r"Double\s*-?\s*Lok|DoubleLok", text, re.IGNORECASE):
            self.panel_info["type"] = "Double Lok"
            self.building_info["has_standing_seam"] = True
        if re.search(r"\b(R-?Loc|RLOC|PBR|AVP|PBA|PBM|7\.2)\b", text, re.IGNORECASE):
            self.panel_info.setdefault("exposed_types", [])
            for label, pat in (
                ("R-Loc/PBR", r"R-?Loc|RLOC|PBR"),
                ("AVP", r"\bAVP\b"),
                ("PBA", r"\bPBA\b"),
                ("PBM", r"\bPBM\b"),
                ("7.2", r"7\.2"),
            ):
                if re.search(pat, text, re.IGNORECASE):
                    if label not in self.panel_info["exposed_types"]:
                        self.panel_info["exposed_types"].append(label)
        if re.search(r"MasterLine|Shadow\s*Rib|FW-?120|PL-?121", text, re.IGNORECASE):
            self.panel_info.setdefault("wall_systems", [])
            for label, pat in (
                ("MasterLine", r"MasterLine"),
                ("Shadow Rib", r"Shadow\s*Rib"),
                ("FW-120", r"FW-?120"),
                ("PL121", r"PL-?121"),
            ):
                if re.search(pat, text, re.IGNORECASE):
                    if label not in self.panel_info["wall_systems"]:
                        self.panel_info["wall_systems"].append(label)

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

        part = get("part") or get("desc")
        # Drop erection-note / OSHA skylight paragraphs mis-read as marks
        if is_non_piece_mark(mark, part or ""):
            return None
        if is_skylight_osha_boilerplate(f"{mark} {part or ''}"):
            return None

        # Quantity
        qty = 1
        qty_str = get("qty")
        m = re.match(r"(\d+)", qty_str)
        if m:
            qty = int(m.group(1))

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
        # Strip skylight OSHA / fall-protection boilerplate (lives in erection manuals)
        raw_text = strip_skylight_osha_paragraphs("\n".join(self.raw_pages))
        pemb = detect_pemb_signals(raw_text=raw_text)
        return {
            "notes": self.notes,
            "has_mezzanine": self.building_info.get("has_mezzanine", False),
            "has_crane": self.building_info.get("has_crane", False),
            "has_bdeck_joist": self.building_info.get("has_bdeck_joist", False),
            "has_imp": self.building_info.get("has_imp", False),
            "has_standing_seam": self.building_info.get("has_standing_seam", False),
            "has_exposed_panels": self.building_info.get("has_exposed_panels", False),
            "has_primary_framing": self.building_info.get("has_primary_framing", False),
            "has_secondary_framing": self.building_info.get("has_secondary_framing", False),
            "building_info": self.building_info,
            "panel_info": self.panel_info,
            "pemb_signals": pemb,
            "raw_text": raw_text,
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
