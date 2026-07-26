"""
Discrepancy / Rules Engine for Chubby-Checker.

Compares extracted Shipper data vs Drawings data and produces
severity-tagged findings. Calibrated on real Ascent jobs.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from chubby_checker.rules.panel_rules import COVERAGE_FACTOR, check_clip_ratio
from chubby_checker.models.piece import Piece


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

    def __init__(
        self,
        shipper_data: Dict[str, Any],
        drawings_data: Optional[Dict[str, Any]] = None,
        drawings_mark_qty: Optional[Dict[str, int]] = None,
        shipper_mark_qty: Optional[Dict[str, int]] = None,
    ):
        self.shipper = shipper_data or {}
        self.drawings = drawings_data or {}
        self.drawings_mark_qty = drawings_mark_qty or {}
        self.shipper_mark_qty = shipper_mark_qty or {}
        self.discrepancies: List[Discrepancy] = []

    def run(self) -> List[Discrepancy]:
        """Execute all active rules."""
        self._check_panel_and_accessories()
        self._check_thermal_block_ratio()
        self._check_clip_screw_ratio()
        self._check_missing_categories()
        self._check_mark_by_mark()          # <-- new mark-by-mark comparison
        return self.discrepancies

    # ------------------------------------------------------------------
    # Mark-by-mark quantity comparison
    # ------------------------------------------------------------------
    def _check_mark_by_mark(self):
        """
        Compare every mark that appears on the drawings against the shipper.
        Also report marks that exist only on the shipper.
        """
        if not self.drawings_mark_qty and not self.shipper_mark_qty:
            # Try to build maps from piece lists if they were passed inside the data dicts
            self.drawings_mark_qty = self._build_mark_map(self.drawings)
            self.shipper_mark_qty = self._build_mark_map(self.shipper)

        if not self.drawings_mark_qty:
            self.discrepancies.append(Discrepancy(
                severity="INFO",
                category="Mark Comparison",
                message="No Member Table marks extracted from drawings – skipping mark-by-mark check.",
                rule="mark_by_mark"
            ))
            return

        if not self.shipper_mark_qty:
            self.discrepancies.append(Discrepancy(
                severity="WARNING",
                category="Mark Comparison",
                message="No piece marks extracted from shipper – cannot perform mark-by-mark comparison.",
                rule="mark_by_mark"
            ))
            return

        # 1. Marks on drawings but missing or wrong qty in shipper
        for mark, expected_qty in self.drawings_mark_qty.items():
            actual_qty = self.shipper_mark_qty.get(mark)

            if actual_qty is None:
                self.discrepancies.append(Discrepancy(
                    severity="CRITICAL",
                    category="Missing Mark",
                    message=f"Mark {mark} appears on drawings (qty {expected_qty}) but is missing from the shipper.",
                    expected=expected_qty,
                    actual=0,
                    mark=mark,
                    rule="mark_by_mark"
                ))
            elif actual_qty != expected_qty:
                self.discrepancies.append(Discrepancy(
                    severity="WARNING",
                    category="Quantity Mismatch",
                    message=f"Mark {mark}: drawings show {expected_qty}, shipper shows {actual_qty}.",
                    expected=expected_qty,
                    actual=actual_qty,
                    mark=mark,
                    rule="mark_by_mark"
                ))

        # 2. Marks that exist only in the shipper (possible extras or drawings extraction miss)
        for mark, actual_qty in self.shipper_mark_qty.items():
            if mark not in self.drawings_mark_qty:
                self.discrepancies.append(Discrepancy(
                    severity="INFO",
                    category="Extra Mark",
                    message=f"Mark {mark} (qty {actual_qty}) is in the shipper but was not found in drawings Member Tables.",
                    expected=0,
                    actual=actual_qty,
                    mark=mark,
                    rule="mark_by_mark"
                ))

    def _build_mark_map(self, data: Dict[str, Any]) -> Dict[str, int]:
        """Build mark → total quantity from either a categories dict of Piece lists or a flat map."""
        result: Dict[str, int] = {}

        # Case 1: already a mark→qty map
        if data and all(isinstance(v, int) for v in data.values()):
            return dict(data)

        # Case 2: categories → List[Piece]
        categories = data.get("categories") or data.get("member_tables") or data
        if isinstance(categories, dict):
            for pieces in categories.values():
                if isinstance(pieces, list):
                    for p in pieces:
                        if isinstance(p, Piece):
                            result[p.mark] = result.get(p.mark, 0) + p.quantity
                        elif isinstance(p, dict) and "mark" in p:
                            result[p["mark"]] = result.get(p["mark"], 0) + p.get("quantity", 1)
        return result

    # ------------------------------------------------------------------
    # Panel coverage driven rules
    # ------------------------------------------------------------------
    def _check_panel_and_accessories(self):
        coverage = self.shipper.get("panel_coverage", {})
        accessories = self.shipper.get("ss_accessories", {})

        if not coverage:
            # Not every shipper has standing seam – only warn if we expected it
            return

        dominant = max(coverage.items(), key=lambda x: x[1])[0] if coverage else None
        clips = accessories.get("sliding_clips", 0)
        plates_24 = accessories.get("backup_plates_24", 0)
        plates_18 = accessories.get("backup_plates_18", 0)

        if dominant == "16":
            self.discrepancies.append(Discrepancy(
                severity="INFO",
                category="Panel",
                message=f"VS16 / 16\" panels detected ({coverage.get('16', 0)} pcs). Expect ~1.5	imes clip density vs 24\" system.",
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

        if dominant == "24" and plates_18 > plates_24 * 0.3 and plates_18 > 10:
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
        if ratio < 0.9 and screws > 0:
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
                    lines.append(f"- **{d.category}** ({d.rule}): {d.message}")
                    if d.mark:
                        lines.append(f"  - Mark: `{d.mark}`")
                    if d.expected is not None:
                        lines.append(f"  - Expected: {d.expected} | Actual: {d.actual}")
                lines.append("")
        return "\n".join(lines)
