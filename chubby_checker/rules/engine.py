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
    detect_panel_families,
)
from chubby_checker.rules.geometry_formulas import BuildingGeometry
from chubby_checker.rules.framing_rules import full_framing_review
from chubby_checker.rules.buyouts import (
    filter_buyouts_from_marks,
    check_unexpected_buyouts,
    is_buyout_text,
)
from chubby_checker.rules.weight_rules import check_weight_rollup
from chubby_checker.rules.bolt_rules import check_bolts
from chubby_checker.rules.standing_seam_system import check_standing_seam_system
from chubby_checker.rules.sheeting_fasteners import check_sheeting_fasteners


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
        connection_counts: Optional[Dict[str, int]] = None,
    ):
        self.shipper = shipper_data or {}
        self.drawings = drawings_data or {}
        self.geometry = building_geometry
        self.connection_counts = connection_counts or self.drawings.get("connection_counts") or {}
        self.discrepancies: List[Discrepancy] = []

    def _add(self, finding: Dict[str, Any]):
        payload = {
            "severity": finding.get("severity", "INFO"),
            "category": finding.get("category", "General"),
            "message": finding.get("message", ""),
            "expected": finding.get("expected"),
            "actual": finding.get("actual"),
            "mark": finding.get("mark", "") or "",
            "rule": finding.get("rule", "") or "",
        }
        self.discrepancies.append(Discrepancy(**payload))

    def run(self) -> List[Discrepancy]:
        self._check_buyouts()
        self._check_weight_rollups()
        self._check_framing_review()
        self._check_bolts()
        self._check_standing_seam_system()
        self._check_sheeting_fasteners()
        self._check_panel_and_accessories()
        self._check_thermal_blocks_verified()
        self._check_clip_screw_ratio()
        self._check_closures_trim_gutter()
        self._check_missing_categories()
        self._check_mark_by_mark()
        self._check_length_match()
        self._check_system_flags()
        return self.discrepancies

    def _check_buyouts(self):
        for f in check_unexpected_buyouts(self.shipper.get("categories", {})):
            self._add(f)

    def _check_weight_rollups(self):
        for f in check_weight_rollup(
            self.shipper.get("categories", {}),
            self.shipper.get("summary_weights", {}) or {},
        ):
            if "rule" not in f:
                f["rule"] = "weight_rollup"
            self._add(f)

    def _check_framing_review(self):
        categories = self.shipper.get("categories", {})
        drawings_map = self.drawings.get("mark_quantity_map") or {}
        if not drawings_map:
            for pieces in self.drawings.get("member_tables", {}).values():
                for p in pieces:
                    drawings_map[p.mark] = drawings_map.get(p.mark, 0) + p.quantity
        for f in full_framing_review(categories, drawings_marks=drawings_map or None):
            self._add(f)

    def _check_bolts(self):
        drawings_text = self.drawings.get("raw_text") or self.drawings.get("notes_text") or ""
        if isinstance(self.drawings.get("notes"), dict):
            drawings_text = drawings_text or str(self.drawings.get("notes"))
        for f in check_bolts(
            self.shipper.get("categories", {}),
            drawings_text=drawings_text if isinstance(drawings_text, str) else "",
            connection_counts=self.connection_counts or None,
        ):
            self._add(f)

    def _check_standing_seam_system(self):
        acc = self.shipper.get("ss_accessories", {}) or {}
        geo = self.geometry
        coverage = None
        pc = self.shipper.get("panel_coverage") or {}
        if pc:
            try:
                coverage = float(max(pc.items(), key=lambda x: x[1])[0])
            except Exception:
                coverage = None
        width_ft = getattr(geo, "width_ft", None) if geo else self.drawings.get("width_ft")
        purlin_lines = self.drawings.get("purlin_lines") or self.shipper.get("purlin_lines")
        endlap_lines = int(self.drawings.get("endlap_lines") or self.shipper.get("endlap_lines") or 0)
        slopes = int(getattr(geo, "slopes", None) or self.drawings.get("slopes") or 1)
        has_ins = bool(acc.get("thermal_blocks", 0) or self.drawings.get("has_insulation", True))
        clip_key = self.shipper.get("clip_key") or self.drawings.get("clip_key")

        accessory_bits = [self.shipper.get("raw_text") or ""]
        for cat, pieces in (self.shipper.get("categories") or {}).items():
            if any(k in cat.lower() for k in ("standing", "ss access", "clip", "seam")):
                for p in pieces:
                    accessory_bits.append(f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')}")
        accessory_text = " ".join(str(b) for b in accessory_bits if b)

        for f in check_standing_seam_system(
            ss_accessories=acc,
            panel_coverage_in=coverage,
            building_width_ft=float(width_ft) if width_ft else None,
            purlin_lines=int(purlin_lines) if purlin_lines else None,
            endlap_lines=endlap_lines,
            slopes=slopes,
            has_insulation=has_ins,
            clip_key=clip_key,
            accessory_text=accessory_text,
        ):
            self._add(f)

    def _check_sheeting_fasteners(self):
        geo = self.geometry
        width_ft = getattr(geo, "width_ft", None) if geo else self.drawings.get("width_ft")
        length_ft = getattr(geo, "length_ft", None) if geo else self.drawings.get("length_ft")
        support_lines = self.drawings.get("purlin_lines") or self.drawings.get("support_lines")
        for f in check_sheeting_fasteners(
            categories=self.shipper.get("categories", {}),
            panel_key=self.shipper.get("exposed_panel_key") or self.drawings.get("exposed_panel_key"),
            area_width_ft=float(width_ft) if width_ft else None,
            slope_length_ft=float(length_ft) if length_ft else None,
            support_lines=int(support_lines) if support_lines else None,
            eave_endlap_lines=int(self.drawings.get("eave_endlap_lines") or 2),
            is_roof=bool(self.drawings.get("is_roof", True)),
        ):
            self._add(f)

    def _check_thermal_blocks_verified(self):
        accessories = self.shipper.get("ss_accessories", {})
        clips = accessories.get("sliding_clips", 0)
        blocks = accessories.get("thermal_blocks", 0)
        has_insulation = blocks > 0 or clips > 0
        for f in check_thermal_blocks(clips, blocks, has_insulation=has_insulation):
            self._add(f)

    def _check_closures_trim_gutter(self):
        categories = self.shipper.get("categories", {})
        raw_text = self.shipper.get("raw_text", "")
        panel_cats = [
            c for c in categories
            if any(k in c.lower() for k in [
                "panel", "standing seam", "r-loc", "rloc", "rlocrev", "pbr", "rpbr",
                "7.2", "m-loc", "mloc", "pba", "pbm", "avp", "roof sheet", "wall sheet",
                "double lok", "double-lok", "vsr", "vsr6", "ssr", "liner", "pl121",
                "shadow rib", "fw-120", "masterline", "standard panel", "sheeting",
                "b-deck", "b deck", "kingspan", "imp", "deck",
            ])
        ]
        panel_count = sum(getattr(p, "quantity", 0) for c in panel_cats for p in categories.get(c, []))
        families = detect_panel_families(categories, raw_text)
        has_panels = bool(panel_cats) or bool(families.get("any_panel"))
        cat_blob = " ".join(panel_cats).lower()
        if any(k in cat_blob for k in (
            "standing seam", "vsr", "ssr", "double lok", "central-loc", "central loc", "mcelroy",
        )):
            families["standing_seam"] = True
        if any(k in cat_blob for k in (
            "r-loc", "rloc", "pbr", "rpbr", "pba", "pbm", "7.2", "m-loc", "avp", "rlr",
        )):
            families["exposed_fastener"] = True
            families["foam_required"] = True
        if any(k in cat_blob for k in ("shadow rib", "fw-120", "masterline")):
            families["concealed_metal_wall"] = True
        # Recompute metal requirement after category-name overrides
        if families.get("suppress_metal_closures"):
            families["metal_required"] = False
        else:
            families["metal_required"] = bool(
                families.get("standing_seam") or families.get("concealed_metal_wall")
            )
        if families.get("suppress_foam_closures"):
            families["foam_required"] = False
        elif families.get("exposed_fastener"):
            families["foam_required"] = True
        for f in check_closures_present(
            extract_closure_counts(categories, raw_text),
            has_panels,
            panel_count,
            panel_families=families,
        ):
            self._add(f)
        trim_info = extract_trim_info(categories)
        for f in check_rivets_for_trim(extract_rivet_count(categories, raw_text), trim_info["count"]):
            self._add(f)
        if trim_info["count"] > 0:
            msg = f"Trim pieces detected: {trim_info['count']} (unique marks: {trim_info['unique_marks']})"
            if trim_info.get("total_length_ft"):
                msg += f", approx total length {trim_info['total_length_ft']} ft"
            self._add({
                "severity": "INFO", "category": "Trim", "message": msg,
                "actual": trim_info["count"], "rule": "trim_present",
            })
        gd = extract_gutter_downspout(categories, raw_text)
        for f in check_gutter_downspout(gd, has_roof_panels=has_panels, geo=self.geometry):
            self._add(f)
        for f in check_trim_lengths_against_geometry(trim_info, self.geometry):
            self._add(f)

    def _check_mark_by_mark(self):
        drawings_map = self.drawings.get("mark_quantity_map") or {}
        if not drawings_map:
            for pieces in self.drawings.get("member_tables", {}).values():
                for p in pieces:
                    drawings_map[p.mark] = drawings_map.get(p.mark, 0) + p.quantity
        if not drawings_map:
            self._add({
                "severity": "INFO", "category": "Comparison",
                "message": "No Member Table marks extracted from drawings – skipping mark-by-mark check.",
                "rule": "mark_by_mark",
            })
            return
        drawings_map = filter_buyouts_from_marks(drawings_map)
        shipper_map: Dict[str, int] = {}
        for pieces in self.shipper.get("categories", {}).values():
            for p in pieces:
                if is_buyout_text(f"{p.mark} {getattr(p, 'description', '')}"):
                    continue
                shipper_map[p.mark] = shipper_map.get(p.mark, 0) + p.quantity
        for mark, expected_qty in drawings_map.items():
            actual_qty = shipper_map.get(mark, 0)
            if actual_qty == 0:
                self._add({
                    "severity": "CRITICAL", "category": "Missing Piece",
                    "message": f"Mark {mark} appears in drawings (qty {expected_qty}) but is missing from shipper.",
                    "expected": expected_qty, "actual": 0, "mark": mark, "rule": "mark_by_mark_missing",
                })
            elif actual_qty != expected_qty:
                self._add({
                    "severity": "WARNING", "category": "Quantity Mismatch",
                    "message": f"Mark {mark}: drawings show {expected_qty}, shipper shows {actual_qty}.",
                    "expected": expected_qty, "actual": actual_qty, "mark": mark, "rule": "mark_by_mark_qty",
                })

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
            d_len = next((p.length_inches for p in d_list if getattr(p, "length_inches", None) is not None), None)
            s_len = next((p.length_inches for p in shipper_pieces[mark] if getattr(p, "length_inches", None) is not None), None)
            if d_len is None or s_len is None:
                continue
            if not lengths_match(d_len, s_len, tolerance=0.25):
                d_str = next((p.length for p in d_list if p.length), f"{d_len}\"")
                s_str = next((p.length for p in shipper_pieces[mark] if p.length), f"{s_len}\"")
                diff = abs(d_len - s_len)
                self._add({
                    "severity": "WARNING", "category": "Length Mismatch",
                    "message": f"Mark {mark}: length differs by {diff:.3f}\". Drawings: {d_str} | Shipper: {s_str}",
                    "expected": d_str, "actual": s_str, "mark": mark, "rule": "length_match",
                })

    def _check_system_flags(self):
        has_crane = self.drawings.get("has_crane", False)
        has_mezz = self.drawings.get("has_mezzanine", False)
        notes = self.drawings.get("notes") or {}
        if isinstance(notes, dict):
            has_crane = has_crane or notes.get("has_crane", False)
            has_mezz = has_mezz or notes.get("has_mezzanine", False)
        cats = " ".join(self.shipper.get("categories", {}).keys()).upper()
        if has_crane and "RUNWAY" not in cats and "CRANE" not in cats:
            self._add({
                "severity": "WARNING", "category": "Crane",
                "message": "Drawings reference crane/runway but no Runway/Crane category in shipper.",
                "rule": "system_crane",
            })
        if has_mezz and "MEZZ" not in cats and "MEZZANINE" not in cats:
            self._add({
                "severity": "INFO", "category": "Mezzanine",
                "message": "Drawings show mezzanine. Confirm framing is in this or another phase.",
                "rule": "system_mezzanine",
            })

    def _check_panel_and_accessories(self):
        coverage = self.shipper.get("panel_coverage", {})
        accessories = self.shipper.get("ss_accessories", {})
        if not coverage:
            return
        dominant = max(coverage.items(), key=lambda x: x[1])[0] if coverage else None
        clips = accessories.get("sliding_clips", 0)
        if str(dominant) == "16":
            self._add({
                "severity": "INFO", "category": "Panel",
                "message": f"VS16 / 16\" panels detected ({coverage.get('16', coverage.get(16, 0))} pcs). Higher clip density expected.",
                "actual": coverage, "rule": "coverage_width",
            })
        if clips == 0 and sum(coverage.values()) > 0:
            self._add({
                "severity": "CRITICAL", "category": "Accessories",
                "message": "Standing seam panels present but zero sliding clips found.",
                "expected": ">0 clips", "actual": 0, "rule": "clips_present",
            })

    def _check_clip_screw_ratio(self):
        accessories = self.shipper.get("ss_accessories", {})
        clips = accessories.get("sliding_clips", 0)
        screws = accessories.get("clip_screws", 0)
        if clips == 0:
            return
        if screws / clips < 0.9 and screws > 0:
            self._add({
                "severity": "WARNING", "category": "Fasteners",
                "message": f"Clip screws ({screws}) appear low relative to sliding clips ({clips}).",
                "expected": f">={clips}", "actual": screws, "rule": "clip_screw_ratio",
            })

    def _check_missing_categories(self):
        cats = self.shipper.get("categories", {})
        summary = self.shipper.get("summary")
        if summary and getattr(summary, "total_weight", 0) > 50000:
            if not cats.get("Fabricated Steel") and not cats.get("Cold Formed Steel"):
                self._add({
                    "severity": "WARNING", "category": "Structure",
                    "message": "High total weight but no Fabricated Steel or Cold Formed Steel extracted.",
                    "rule": "missing_structural_category",
                })

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
