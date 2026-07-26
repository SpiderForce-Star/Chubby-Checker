"""
Discrepancy / Rules Engine for Chubby-Checker.

Compares extracted Shipper data vs Drawings data and produces
severity-tagged findings. Calibrated on real Ascent jobs.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from chubby_checker.rules.panel_rules import COVERAGE_FACTOR


@dataclass
class Discrepancy:
    severity: str          # CRITICAL | WARNING | INFO
    category: str
    message: str
    expected: Any = None
    actual: Any = None
    mark: str = ""
    rule: str = ""


class DiscrepancyEngine:
    """Core verification engine."""

    def __init__(self, shipper_data: Dict[str, Any], drawings_data: Optional[Dict[str, Any]] = None):
        self.shipper = shipper_data or {}
        self.drawings = drawings_data or {}
        self.discrepancies: List[Discrepancy] = []

    def run(self) -> List[Discrepancy]:
        """Execute all active rules."""
        self._check_panel_and_accessories()
        self._check_thermal_block_ratio()
        self._check_clip_screw_ratio()
        self._check_missing_categories()
        self._check_mark_by_mark()
        self._check_system_flags()
        return self.discrepancies

    # ------------------------------------------------------------------
    # Mark-by-mark quantity comparison (new)
    # ------------------------------------------------------------------
    def _check_mark_by_mark(self):
        """Compare drawings mark quantities against shipper pieces."""
        drawings_map = self.drawings.get("mark_quantity_map") or {}
        if not drawings_map:
            # Try to build from member_tables if present
            member_tables = self.drawings.get("member_tables", {})
            for pieces in member_tables.values():
                for p in pieces:
                    drawings_map[p.mark] = drawings_map.get(p.mark, 0) + p.quantity

        if not drawings_map:
            self.discrepancies.append(Discrepancy(
                severity="INFO",
                category="Comparison",
                message="No Member Table marks extracted from drawings – skipping mark-by-mark check.",
                rule="mark_by_mark"
            ))
            return

        # Build shipper mark → qty map from all categories
        shipper_map: Dict[str, int] = {}
        categories = self.shipper.get("categories", {})
        for pieces in categories.values():
            for p in pieces:
                shipper_map[p.mark] = shipper_map.get(p.mark, 0) + p.quantity

        # Also include any top-level pieces if the parser stores them differently
        # (future-proof)

        missing = []
        qty_mismatch = []
        extra = []

        for mark, expected_qty in drawings_map.items():
            actual_qty = shipper_map.get(mark, 0)
            if actual_qty == 0:
                missing.append((mark, expected_qty))
            elif actual_qty != expected_qty:
                qty_mismatch.append((mark, expected_qty, actual_qty))

        for mark, actual_qty in shipper_map.items():
            if mark not in drawings_map:
                extra.append((mark, actual_qty))

        # Report findings
        for mark, qty in missing[:30]:  # limit noise
            self.discrepancies.append(Discrepancy(
                severity="CRITICAL",
                category="Missing Piece",
                message=f"Mark {mark} appears in drawings (qty {qty}) but is missing from shipper.",
                expected=qty,
                actual=0,
                mark=mark,
                rule="mark_by_mark_missing"
            ))

        for mark, exp, act in qty_mismatch[:30]:
            self.discrepancies.append(Discrepancy(
                severity="WARNING",
                category="Quantity Mismatch",
                message=f"Mark {mark}: drawings show {exp}, shipper shows {act}.",
                expected=exp,
                actual=act,
                mark=mark,
                rule="mark_by_mark_qty"
            ))

        # Extras are often less critical (may be accessories or phased)
        if extra:
            self.discrepancies.append(Discrepancy(
                severity="INFO",
                category="Extra Pieces",
                message=f"{len(extra)} mark(s) present in shipper but not found in drawings Member Tables (may be secondary/accessory/phased).",
                actual=len(extra),
                rule="mark_by_mark_extra"
            ))

    def _check_system_flags(self):
        """Cross-check high-level system presence."""
        has_crane_drawings = self.drawings.get("has_crane", False)
        has_mezz_drawings = self.drawings.get("has_mezzanine", False)

        # Simple presence checks in shipper categories / notes
        shipper_text_cats = " ".join(self.shipper.get("categories", {}).keys()).upper()
        accessories = self.shipper.get("ss_accessories", {})

        if has_crane_drawings and "RUNWAY" not in shipper_text_cats and "CRANE" not in shipper_text_cats:
            self.discrepancies.append(Discrepancy(
                severity="WARNING",
                category="Crane",
                message="Drawings reference crane/runway system but no Runway/Crane category found in shipper.",
                rule="system_crane"
            ))

        if has_mezz_drawings and "MEZZ" not in shipper_text_cats and "MEZZANINE" not in shipper_text_cats:
            # Mezzanine often lives under Fabricated Steel or separate phase
            self.discrepancies.append(Discrepancy(
                severity="INFO",
                category="Mezzanine",
                message="Drawings show mezzanine. Confirm mezzanine framing is present in this or another shipper phase.",
                rule="system_mezzanine"
            ))

    # ------------------------------------------------------------------
    # Panel coverage driven rules
    # ------------------------------------------------------------------
    def _check_panel_and_accessories(self):
        coverage = self.shipper.get("panel_coverage", {})
        accessories = self.shipper.get("ss_accessories", {})

        if not coverage:
            self.discrepancies.append(Discrepancy(
                severity="INFO",
                category="Panel",
                message="No standing seam panel coverage detected in shipper.",
                rule="panel_coverage_detect"
            ))
            return

        dominant = max(coverage.items(), key=lambda x: x[1])[0] if coverage else None
        clips = accessories.get("sliding_clips", 0)
        plates_24 = accessories.get("backup_plates_24", 0)
        plates_18 = accessories.get("backup_plates_18", 0)

        if dominant == "16":
            self.discrepancies.append(Discrepancy(
                severity="INFO",
                category="Panel",
                message=f"VS16 / 16\" panels detected ({coverage.get('16', 0)} pcs). Expect ~1.5× clip density vs 24\" system.",
                actual=coverage,
                rule="coverage_width"
            ))
        elif dominant == "18":
            self.discrepancies.append(Discrepancy(
                severity="INFO",
                category="Panel",
                message=f"18\" panels dominant. Clip density should be higher than 24\" system.",
                actual=coverage,
                rule="coverage_width"
            ))

        if dominant == "24" and plates_18 > plates_24 * 0.3 and plates_24 > 0:
            self.discrepancies.append(Discrepancy(
                severity="WARNING",
                category="Accessories",
                message=f"Unexpected number of 18\" backup plates ({plates_18}) on a predominantly 24\" roof.",
                expected="Mostly 24\" plates",
                actual=f"24\": {plates_24}, 18\": {plates_18}",
                rule="backup_plate_match"
            ))

        if clips == 0 and sum(coverage.values()) > 0:
            self.discrepancies.append(Discrepancy(
                severity="CRITICAL",
                category="Accessories",
                message="Standing seam panels present but zero sliding clips found in SS Accessories.",
                expected=">0 clips",
                actual=0,
                rule="clips_present"
            ))

    def _check_thermal_block_ratio(self):
        accessories = self.shipper.get("ss_accessories", {})
        clips = accessories.get("sliding_clips", 0)
        blocks = accessories.get("thermal_blocks", 0)

        if clips == 0:
            return

        ratio = blocks / clips if clips else 0
        if ratio < 0.85:
            self.discrepancies.append(Discrepancy(
                severity="WARNING",
                category="Accessories",
                message=f"Thermal block count ({blocks}) is significantly lower than sliding clips ({clips}). Expected ~1:1 when insulation is present.",
                expected=f"~{clips}",
                actual=blocks,
                rule="thermal_block_ratio"
            ))
        elif ratio > 1.15:
            self.discrepancies.append(Discrepancy(
                severity="INFO",
                category="Accessories",
                message=f"Thermal blocks ({blocks}) exceed clips ({clips}). May include extras or different system.",
                expected=f"~{clips}",
                actual=blocks,
                rule="thermal_block_ratio"
            ))

    def _check_clip_screw_ratio(self):
        accessories = self.shipper.get("ss_accessories", {})
        clips = accessories.get("sliding_clips", 0)
        screws = accessories.get("clip_screws", 0)

        if clips == 0:
            return

        ratio = screws / clips if clips else 0
        if ratio < 0.9:
            self.discrepancies.append(Discrepancy(
                severity="WARNING",
                category="Fasteners",
                message=f"Clip screws ({screws}) appear low relative to sliding clips ({clips}).",
                expected=f">={clips}",
                actual=screws,
                rule="clip_screw_ratio"
            ))

    def _check_missing_categories(self):
        cats = self.shipper.get("categories", {})
        summary = self.shipper.get("summary")
        if summary and getattr(summary, "total_weight", 0) > 50000:
            if not cats.get("Fabricated Steel") and not cats.get("Cold Formed Steel"):
                self.discrepancies.append(Discrepancy(
                    severity="WARNING",
                    category="Structure",
                    message="High total weight but no Fabricated Steel or Cold Formed Steel category extracted.",
                    rule="missing_structural_category"
                ))

    def report(self) -> str:
        if not self.discrepancies:
            return "No discrepancies found. Shipper appears consistent with extracted rules."

        lines = ["# Chubby-Checker Discrepancy Report", ""]
        for sev in ["CRITICAL", "WARNING", "INFO"]:
            items = [d for d in self.discrepancies if d.severity == sev]
            if items:
                lines.append(f"## {sev}")
                for d in items:
                    prefix = f"[{d.mark}] " if d.mark else ""
                    lines.append(f"- **{d.category}** ({d.rule}): {prefix}{d.message}")
                    if d.expected is not None:
                        lines.append(f"  - Expected: {d.expected} | Actual: {d.actual}")
                lines.append("")
        return "\n".join(lines)
