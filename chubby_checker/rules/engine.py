"""
Discrepancy / Rules Engine for Chubby-Checker.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from chubby_checker.utils.length import lengths_match
from chubby_checker.rules.accessory_rules import (
    extract_closure_counts,
    extract_rivet_count,
    extract_trim_info,
    extract_gutter_downspout,
    check_closures_present,
    check_rivets_for_trim,
    check_gutter_downspout,
    check_trim_lengths_against_geometry,
    check_thermal_blocks,
)
from chubby_checker.rules.geometry_formulas import BuildingGeometry
from chubby_checker.rules.framing_rules import full_framing_review


@dataclass
class Discrepancy:
    severity: str
    category: str
    message: str
    expected: Any = None
    actual: Any = None
    mark: str = ""
    rule: str = ""


class DiscrepancyEngine:
    def __init__(
        self,
        shipper_data: Dict[str, Any],
        drawings_data: Optional[Dict[str, Any]] = None,
        building_geometry: Optional[BuildingGeometry] = None,
    ):
        self.shipper = shipper_data or {}
        self.drawings = drawings_data or {}
        self.geometry = building_geometry
        self.discrepancies: List[Discrepancy] = []

    def run(self) -> List[Discrepancy]:
        self._check_framing_review()          # <-- NEW full framing review
        self._check_panel_and_accessories()
        self._check_thermal_blocks_verified()
        self._check_clip_screw_ratio()
        self._check_closures_trim_gutter()
        self._check_missing_categories()
        self._check_mark_by_mark()
        self._check_length_match()
        self._check_system_flags()
        return self.discrepancies

    # ------------------------------------------------------------------
    # Full Primary + Secondary Framing Review
    # ------------------------------------------------------------------
    def _check_framing_review(self):
        categories = self.shipper.get("categories", {})
        drawings_map = self.drawings.get("mark_quantity_map") or {}
        if not drawings_map:
            for pieces in self.drawings.get("member_tables", {}).values():
                for p in pieces:
                    drawings_map[p.mark] = drawings_map.get(p.mark, 0) + p.quantity

        for f in full_framing_review(categories, drawings_marks=drawings_map or None):
            self.discrepancies.append(Discrepancy(**{k: v for k, v in f.items() if k in Discrepancy.__dataclass_fields__}))

    # ------------------------------------------------------------------
    # Thermal blocks
    # ------------------------------------------------------------------
    def _check_thermal_blocks_verified(self):
        accessories = self.shipper.get("ss_accessories", {})
        clips = accessories.get("sliding_clips", 0)
        blocks = accessories.get("thermal_blocks", 0)
        has_insulation = blocks > 0 or clips > 0
        for f in check_thermal_blocks(clips, blocks, has_insulation=has_insulation):
            self.discrepancies.append(Discrepancy(**f))

    # ------------------------------------------------------------------
    # Closures / Trim / Gutter
    # ------------------------------------------------------------------
    def _check_closures_trim_gutter(self):
        categories = self.shipper.get("categories", {})
        raw_text = self.shipper.get("raw_text", "")

        panel_cats = [
            c for c in categories
            if any(k in c.lower() for k in [
                "panel", "standing seam", "r-loc", "rloc", "pbr",
                "7.2", "m-loc", "mloc", "pba", "roof sheet", "wall sheet",
            ])
        ]
        has_panels = bool(panel_cats)
        panel_count = sum(getattr(p, "quantity", 0) for c in panel_cats for p in categories.get(c, []))

        for f in check_closures_present(extract_closure_counts(categories, raw_text), has_panels, panel_count):
            self.discrepancies.append(Discrepancy(**f))

        trim_info = extract_trim_info(categories)
        for f in check_rivets_for_trim(extract_rivet_count(categories, raw_text), trim_info["count"]):
            self.discrepancies.append(Discrepancy(**f))

        if trim_info["count"] > 0:
            msg = f"Trim pieces detected: {trim_info['count']} (unique marks: {trim_info['unique_marks']})"
            if trim_info.get("total_length_ft"):
                msg += f", approx total length {trim_info['total_length_ft']} ft"
            self.discrepancies.append(Discrepancy(
                severity="INFO", category="Trim", message=msg,
                actual=trim_info["count"], rule="trim_present",
            ))

        gd = extract_gutter_downspout(categories, raw_text)
        for f in check_gutter_downspout(gd, has_roof_panels=has_panels, geo=self.geometry):
            self.discrepancies.append(Discrepancy(**f))

        for f in check_trim_lengths_against_geometry(trim_info, self.geometry):
            self.discrepancies.append(Discrepancy(**f))

    # ------------------------------------------------------------------
    # Core mark / length / system checks
    # ------------------------------------------------------------------
    def _check_mark_by_mark(self):
        drawings_map = self.drawings.get("mark_quantity_map") or {}
        if not drawings_map:
            for pieces in self.drawings.get("member_tables", {}).values():
                for p in pieces:
                    drawings_map[p.mark] = drawings_map.get(p.mark, 0) + p.quantity

        if not drawings_map:
            self.discrepancies.append(Discrepancy(
                severity="INFO", category="Comparison",
                message="No Member Table marks extracted from drawings – skipping mark-by-mark check.",
                rule="mark_by_mark",
            ))
            return

        shipper_map: Dict[str, int] = {}
        for pieces in self.shipper.get("categories", {}).values():
            for p in pieces:
                shipper_map[p.mark] = shipper_map.get(p.mark, 0) + p.quantity

        for mark, expected_qty in drawings_map.items():
            actual_qty = shipper_map.get(mark, 0)
            if actual_qty == 0:
                self.discrepancies.append(Discrepancy(
                    severity="CRITICAL", category="Missing Piece",
                    message=f"Mark {mark} appears in drawings (qty {expected_qty}) but is missing from shipper.",
                    expected=expected_qty, actual=0, mark=mark, rule="mark_by_mark_missing",
                ))
            elif actual_qty != expected_qty:
                self.discrepancies.append(Discrepancy(
                    severity="WARNING", category="Quantity Mismatch",
                    message=f"Mark {mark}: drawings show {expected_qty}, shipper shows {actual_qty}.",
                    expected=expected_qty, actual=actual_qty, mark=mark, rule="mark_by_mark_qty",
                ))

    def _check_length_match(self):
        drawings_pieces: Dict[str, list] = {}
        for pieces in self.drawings.get("member_tables", {}).values():
            for p in pieces:
                drawings_pieces.setdefault(p.mark, []).append(p)

        shipper_pieces: Dict[str, list] = {}
        for pieces in self.shipper.get("categories", {}).values():
            for p in pieces:
                shipper_pieces.setdefault(p.mark, []).append(p)

        if not drawings_pieces or not shipper_pieces:
            return

        for mark, d_list in drawings_pieces.items():
            if mark not in shipper_pieces:
                continue
            d_len = next((p.length_inches for p in d_list if p.length_inches is not None), None)
            s_len = next((p.length_inches for p in shipper_pieces[mark] if p.length_inches is not None), None)
            if d_len is None or s_len is None:
                continue
            if not lengths_match(d_len, s_len, tolerance=0.25):
                d_str = next((p.length for p in d_list if p.length), f"{d_len}\"")
                s_str = next((p.length for p in shipper_pieces[mark] if p.length), f"{s_len}\"")
                diff = abs(d_len - s_len)
                self.discrepancies.append(Discrepancy(
                    severity="WARNING", category="Length Mismatch",
                    message=f"Mark {mark}: length differs by {diff:.3f}\". Drawings: {d_str} | Shipper: {s_str}",
                    expected=d_str, actual=s_str, mark=mark, rule="length_match",
                ))

    def _check_system_flags(self):
        has_crane = self.drawings.get("has_crane", False)
        has_mezz = self.drawings.get("has_mezzanine", False)
        cats = " ".join(self.shipper.get("categories", {}).keys()).upper()
        if has_crane and "RUNWAY" not in cats and "CRANE" not in cats:
            self.discrepancies.append(Discrepancy(
                severity="WARNING", category="Crane",
                message="Drawings reference crane/runway but no Runway/Crane category in shipper.",
                rule="system_crane",
            ))
        if has_mezz and "MEZZ" not in cats and "MEZZANINE" not in cats:
            self.discrepancies.append(Discrepancy(
                severity="INFO", category="Mezzanine",
                message="Drawings show mezzanine. Confirm framing is in this or another phase.",
                rule="system_mezzanine",
            ))

    def _check_panel_and_accessories(self):
        coverage = self.shipper.get("panel_coverage", {})
        accessories = self.shipper.get("ss_accessories", {})
        if not coverage:
            return
        dominant = max(coverage.items(), key=lambda x: x[1])[0] if coverage else None
        clips = accessories.get("sliding_clips", 0)
        if dominant == "16":
            self.discrepancies.append(Discrepancy(
                severity="INFO", category="Panel",
                message=f"VS16 / 16\" panels detected ({coverage.get('16', 0)} pcs). Higher clip density expected.",
                actual=coverage, rule="coverage_width",
            ))
        if clips == 0 and sum(coverage.values()) > 0:
            self.discrepancies.append(Discrepancy(
                severity="CRITICAL", category="Accessories",
                message="Standing seam panels present but zero sliding clips found.",
                expected=">0 clips", actual=0, rule="clips_present",
            ))

    def _check_clip_screw_ratio(self):
        accessories = self.shipper.get("ss_accessories", {})
        clips = accessories.get("sliding_clips", 0)
        screws = accessories.get("clip_screws", 0)
        if clips == 0:
            return
        if screws / clips < 0.9 and screws > 0:
            self.discrepancies.append(Discrepancy(
                severity="WARNING", category="Fasteners",
                message=f"Clip screws ({screws}) appear low relative to sliding clips ({clips}).",
                expected=f">={clips}", actual=screws, rule="clip_screw_ratio",
            ))

    def _check_missing_categories(self):
        cats = self.shipper.get("categories", {})
        summary = self.shipper.get("summary")
        if summary and getattr(summary, "total_weight", 0) > 50000:
            if not cats.get("Fabricated Steel") and not cats.get("Cold Formed Steel"):
                self.discrepancies.append(Discrepancy(
                    severity="WARNING", category="Structure",
                    message="High total weight but no Fabricated Steel or Cold Formed Steel extracted.",
                    rule="missing_structural_category",
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
