"""
Discrepancy / Rules Engine for Chubby-Checker.

Compares extracted Shipper data vs Drawings data and produces
severity-tagged findings. Calibrated on real Ascent jobs.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from chubby_checker.rules.panel_rules import COVERAGE_FACTOR, check_clip_ratio


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
        # Future: mark-by-mark member comparison once drawings parser is richer
        return self.discrepancies

    # ------------------------------------------------------------------
    # Panel coverage driven rules (core of the original request)
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

        # Determine dominant coverage
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

        # Basic sanity on backup plates matching coverage
        if dominant == "24" and plates_18 > plates_24 * 0.3:
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

        # Typical: 1.0 – 2.0 screws per clip depending on insulation thickness / manufacturer
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
        """Flag if major expected categories are completely absent."""
        cats = self.shipper.get("categories", {})
        summary = self.shipper.get("summary")
        if summary and getattr(summary, "total_weight", 0) > 50000:
            # Heavy structural job should have fabricated or cold formed
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
                    if d.expected is not None:
                        lines.append(f"  - Expected: {d.expected} | Actual: {d.actual}")
                lines.append("")
        return "\n".join(lines)
