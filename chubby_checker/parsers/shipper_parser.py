"""
Parser for Ascent Buildings Complete Shipper PDFs.

Extracts:
- Category weight summaries from the cover / index page
- Piece-level data (mark, qty, description, length, weight, section)
- Standing Seam accessories (clips, backup plates, thermal blocks, screws)

Calibrated on real jobs: 25-13266, 25-13059, 25-13168 (PH1–PH6)
and Ascent Central Seam Plus / Central-Loc / Central Span manuals.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import re
import pdfplumber
from chubby_checker.models.piece import Piece
from chubby_checker.utils.length import parse_length_to_inches

# Official Ascent / Central States sliding & floating clip part numbers
SLIDING_CLIP_PARTS = (
    "CL2122", "CL2124", "CL2102", "CL2104",  # CSP / Central-Loc sliding
    "CL200", "CL204", "CL208",              # Central-Loc fixed / utility
    "CSP212", "CS2124", "CS2122", "CSP2124",  # shipper aliases
    "SPLCLIP", "SPHCLIP",                    # Central Span floating
)


class ShipperParser:
    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        self.categories: Dict[str, List[Piece]] = {}
        self.summary_weights: Dict[str, float] = {}
        self.ss_accessories: Dict[str, int] = {
            "sliding_clips": 0,
            "backup_plates_24": 0,
            "backup_plates_18": 0,
            "thermal_blocks": 0,
            "clip_screws": 0,
            "hi_eave_plates": 0,
            "hi_rake_supports": 0,
            "eave_plates_low": 0,
            "rake_supports_low": 0,
            "bearing_plates": 0,
        }
        self.raw_text_pages: List[str] = []

    def parse(self) -> Dict[str, List[Piece]]:
        """Main entry point. Parses the entire shipper PDF."""
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                self.raw_text_pages.append(text)
                tables = page.extract_tables() or []
                self._process_tables(tables, text)
                self._extract_from_text(text)

        self._post_process_ss_accessories()
        return self.categories

    def _process_tables(self, tables: List[List[List[Any]]], page_text: str):
        for table in tables:
            if not table or len(table) < 2:
                continue
            header = [str(c or "").lower() for c in table[0]]
            has_qty = any("qnty" in h or "qty" in h or "quantity" in h for h in header)
            has_mark = any("mark" in h for h in header)
            if has_qty and has_mark:
                self._parse_piece_table(table, header)

    def _parse_piece_table(self, table: List[List[Any]], header: List[str]):
        col_map = {}
        for i, h in enumerate(header):
            h = h.lower()
            if "qnty" in h or "qty" in h or "quantity" in h:
                col_map["qty"] = i
            elif "mark" in h:
                col_map["mark"] = i
            elif "description" in h or "desc" in h:
                col_map["desc"] = i
            elif "part" in h:
                col_map["part"] = i
            elif "length" in h:
                col_map["length"] = i
            elif "weight" in h and "unit" not in h:
                col_map["weight"] = i
            elif "unit weight" in h:
                col_map["unit_weight"] = i
            elif "color" in h:
                col_map["color"] = i

        category = self._detect_category_from_header(header) or "Unknown"

        for row in table[1:]:
            if not row or len(row) < 2:
                continue
            try:
                qty_str = str(row[col_map.get("qty", 0)] or "").strip()
                if not qty_str or not re.match(r"^\d+", qty_str):
                    continue
                qty = int(re.match(r"(\d+)", qty_str).group(1))

                mark = str(row[col_map.get("mark", 1)] or "").strip()
                if not mark:
                    continue

                desc = str(row[col_map.get("desc", 2)] or "").strip()
                length = str(row[col_map.get("length", -1)] or "").strip() if "length" in col_map else None
                length_inches = parse_length_to_inches(length) if length else None

                weight = None
                if "weight" in col_map:
                    try:
                        weight = float(str(row[col_map["weight"]] or "0").replace(",", ""))
                    except ValueError:
                        pass

                section = None
                part = str(row[col_map.get("part", -1)] or "").strip() if "part" in col_map else None
                if part:
                    section = part

                piece = Piece(
                    mark=mark,
                    description=desc,
                    quantity=qty,
                    length=length,
                    length_inches=length_inches,
                    weight=weight,
                    section=section,
                    category=category,
                    source="shipper",
                )
                self.categories.setdefault(category, []).append(piece)
                self._capture_ss_accessory(mark, desc, qty)

            except Exception:
                continue

    def _detect_category_from_header(self, header: List[str]) -> Optional[str]:
        header_str = " ".join(header).lower()
        # PEMB shipper index / table categories (Ascent + multi-vendor wording)
        checks = (
            ("standing seam", "Standing Seam"),
            ("ss accessories", "SS Accessories"),
            ("ss accessory", "SS Accessories"),
            ("cold formed", "Cold Formed Steel"),
            ("hot rolled beam", "Hot Rolled Beam"),
            ("hot rolled pipe", "Hot Rolled Pipe Tube"),
            ("fabricated", "Fabricated Steel"),
            ("flange brace", "Flange Braces"),
            ("runway", "Runway Beams"),
            ("crane", "Runway Beams"),
            ("standard panel", "Standard Panels"),
            ("exposed fastener", "Standard Panels"),
            ("r-loc", "Standard Panels"),
            ("rloc", "Standard Panels"),
            ("trim", "Trim"),
            ("sealant", "Sealant"),
            ("screw", "Screws Fasteners"),
            ("fastener", "Screws Fasteners"),
            ("bolt", "Bolts_Nuts_Washers"),
            ("insulation", "Insulation"),
            ("bar joist", "Bar Joists"),
            ("joist", "Bar Joists"),
            ("deck", "Deck"),
            ("mezzanine", "Mezzanine"),
            ("closure", "Closures"),
            ("cable", "Cables and Rods"),
            ("loose clip", "Loose Clips"),
            ("structural angle", "Structural Angle"),
        )
        for needle, label in checks:
            if needle in header_str:
                return label
        return None

    def _extract_from_text(self, text: str):
        weight_pattern = re.compile(
            r"(Cold Formed Steel|Standard Panels|Trim|Sealant|Screws[_ ]Fasteners|"
            r"Hot Rolled Beam|Hot Rolled Pipe[_ ]Tube|Fabricated Steel|Flange Braces|"
            r"Loose Clips|Bolts[_ ]Nuts[_ ]Washers|Cables and Rods|Runway Beams|"
            r"Structural Angle|Standing Seam|SS Accessories|Bar Joists|Insulation|"
            r"Closures|Mezzanine|Deck|Imp|Insulated Panels)\s+([\d,]+\.?\d*)",
            re.IGNORECASE,
        )
        for match in weight_pattern.finditer(text):
            cat = match.group(1).replace("_", " ").strip()
            try:
                wt = float(match.group(2).replace(",", ""))
                self.summary_weights[cat] = wt
            except ValueError:
                pass
        self._extract_ss_from_text(text)

    def _extract_ss_from_text(self, text: str):
        clip_alt = "|".join(re.escape(p) for p in SLIDING_CLIP_PARTS)
        patterns = {
            "sliding_clips": [
                rf"(\d+)\s+(?:{clip_alt})",
                r"(\d+)\s+(?:2\" High Sliding Clip|Sliding Clip)",
                r"(\d+)\s+.*Sliding Clip",
            ],
            "backup_plates_24": [
                r"(\d+)\s+(?:CL7760|24\" Back Up Plate)",
            ],
            "backup_plates_18": [
                r"(\d+)\s+(?:CL7769|18\" Back Up Plate)",
            ],
            "thermal_blocks": [
                r"(\d+)\s+(?:CL575|1\" Thermal Block|Thermal Spacer)",
            ],
            "clip_screws": [
                r"(\d+)\s+.*Panel Clip Screw",
                r"(\d+)\s+FSS10",
                r"(\d+)\s+FSS1\b",
                r"(\d+)\s+FT1\b",
            ],
            "hi_eave_plates": [
                r"(\d+)\s+(?:CL7616|Hi-Eave Plate|Eave Plate,? High)",
            ],
            "eave_plates_low": [
                r"(\d+)\s+(?:CL7600|Eave Plate,? Low)",
            ],
            "hi_rake_supports": [
                r"(\d+)\s+(?:CL7720|Hi-Rake Support|Rake Support,? High)",
            ],
            "rake_supports_low": [
                r"(\d+)\s+(?:CL7710|Rake Support,? Low)",
            ],
            "bearing_plates": [
                r"(\d+)\s+(?:CL7500|Bearing Plate)",
            ],
        }
        for key, pats in patterns.items():
            for pat in pats:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    try:
                        self.ss_accessories[key] = max(self.ss_accessories.get(key, 0), int(m.group(1)))
                    except ValueError:
                        pass

    def _capture_ss_accessory(self, mark: str, desc: str, qty: int):
        combined = f"{mark} {desc}".upper().replace("-", "")
        mark_u = mark.upper().replace("-", "")

        if any(p.replace("-", "") in combined for p in SLIDING_CLIP_PARTS) or "SLIDING CLIP" in combined or "FIXED CLIP" in combined or "FLOATING CLIP" in combined or "UTILITY CLIP" in combined:
            self.ss_accessories["sliding_clips"] += qty
        elif "CL7760" in combined or "24\" BACK" in combined or "24 BACK" in combined:
            self.ss_accessories["backup_plates_24"] += qty
        elif "CL7769" in combined or "18\" BACK" in combined or "18 BACK" in combined:
            self.ss_accessories["backup_plates_18"] += qty
        elif "THERMAL" in combined or "CL575" in combined:
            self.ss_accessories["thermal_blocks"] += qty
        elif "CL7616" in combined or "HI-EAVE" in combined or "HI EAVE" in combined:
            self.ss_accessories["hi_eave_plates"] += qty
        elif "CL7600" in combined:
            self.ss_accessories["eave_plates_low"] += qty
        elif "CL7720" in combined or "HI-RAKE" in combined or "HI RAKE" in combined:
            self.ss_accessories["hi_rake_supports"] += qty
        elif "CL7710" in combined:
            self.ss_accessories["rake_supports_low"] += qty
        elif "CL7500" in combined or "BEARING PLATE" in combined:
            self.ss_accessories["bearing_plates"] += qty
        elif any(x in combined for x in ("FSS1", "FSS10", "FT1", "PANEL CLIP SCREW", "CLIP SCREW")):
            self.ss_accessories["clip_screws"] += qty

    def _post_process_ss_accessories(self):
        pass

    def get_ss_accessories(self) -> Dict[str, int]:
        return self.ss_accessories.copy()

    def get_summary_weights(self) -> Dict[str, float]:
        return self.summary_weights.copy()

    def get_category_piece_count(self, category: str) -> int:
        pieces = self.categories.get(category, [])
        return sum(p.quantity for p in pieces)
