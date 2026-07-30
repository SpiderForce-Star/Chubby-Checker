"""
Complete standing seam application system checks (MBCI / Ascent-aligned).

Uses seam_clip_library for clip type, screws/clip, thermal pairing, and
backup plate width by panel coverage.

Expected quantities:
  clips ≈ seams × purlin_lines
  clip_screws ≥ screws_per_clip × clips (library default 2)
  thermal_blocks ≈ clips (when insulation / clip requires thermal)
  backup_plates ≈ endlap_lines × seams (plate width from library)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from chubby_checker.rules.seam_clip_library import (
    default_clip_for_coverage,
    identify_clip_from_text,
    load_seam_clip_library,
    screws_required,
    system_requirements,
    backup_plate_for_coverage,
)


def expected_ss_quantities(
    panel_coverage_in: float,
    building_width_ft: float,
    purlin_lines: int,
    endlap_lines: int = 0,
    slopes: int = 1,
    has_insulation: bool = True,
    clip_key: Optional[str] = None,
) -> Dict[str, Any]:
    if panel_coverage_in <= 0 or building_width_ft <= 0 or purlin_lines <= 0:
        return {"ok": False, "reason": "insufficient geometry"}

    coverage = int(panel_coverage_in)
    width_in = building_width_ft * 12.0
    run_width_in = width_in / max(slopes, 1)
    seams_per_slope = max(1, int(math.ceil(run_width_in / panel_coverage_in)))
    clips = seams_per_slope * purlin_lines * max(slopes, 1)

    req = system_requirements(
        panel_coverage_in=coverage,
        clip_count=clips,
        has_insulation=has_insulation,
        clip_key=clip_key,
    )
    backup = max(0, endlap_lines) * seams_per_slope * max(slopes, 1)

    return {
        "ok": True,
        "panel_coverage_in": coverage,
        "seams_per_slope": seams_per_slope,
        "purlin_lines": purlin_lines,
        "slopes": slopes,
        "expected_clips": clips,
        "expected_clip_screws": req["expected_clip_screws"],
        "screws_per_clip": req["screws_per_clip"],
        "expected_thermal_blocks": req["expected_thermal_blocks"],
        "expected_backup_plates": backup,
        "backup_plate_width_in": req["backup_plate"].get("width_in"),
        "clip_spec_key": req["clip_spec"]["key"],
        "clip_spec_name": req["clip_spec"]["name"],
        "notes": req["notes"],
    }


def check_standing_seam_system(
    ss_accessories: Dict[str, int],
    panel_coverage_in: Optional[float] = None,
    building_width_ft: Optional[float] = None,
    purlin_lines: Optional[int] = None,
    endlap_lines: int = 0,
    slopes: int = 1,
    has_insulation: bool = True,
    tolerance: float = 0.20,
    clip_key: Optional[str] = None,
    accessory_text: str = "",
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    acc = ss_accessories or {}
    clips = int(acc.get("sliding_clips", 0) or 0)
    screws = int(acc.get("clip_screws", 0) or 0)
    blocks = int(acc.get("thermal_blocks", 0) or 0)
    backup = int(acc.get("backup_plates_24", 0) or 0) + int(acc.get("backup_plates_18", 0) or 0)

    # Identify clip type from text or coverage
    identified = identify_clip_from_text(accessory_text) if accessory_text else None
    if identified and not clip_key:
        clip_key = identified.key
    coverage_int = int(panel_coverage_in) if panel_coverage_in else None
    clip_spec = None
    if clip_key:
        clip_spec = load_seam_clip_library().get(clip_key)
    elif coverage_int:
        clip_spec = default_clip_for_coverage(coverage_int)
    elif identified:
        clip_spec = identified

    if clip_spec:
        findings.append({
            "severity": "INFO",
            "category": "Standing Seam",
            "message": (
                f"Seam clip library: {clip_spec.name} ({clip_spec.key}) — "
                f"{clip_spec.motion}/{clip_spec.height}, "
                f"{clip_spec.screws_per_clip} screws/clip, "
                f"parts: {', '.join(clip_spec.part_numbers) or 'n/a'}."
            ),
            "rule": "ss_clip_library_id",
        })

    # Indicate SS without requiring geometry (coverage/width often unavailable)
    _acc_l = (accessory_text or "").lower()
    _ss_keywords = (
        "standing seam", "sliding clip", "central-loc", "central loc",
        "double lok", "vsr", "ssr", "ss access",
    )
    ss_text = any(k in _acc_l for k in _ss_keywords)
    ss_indicated = bool(
        panel_coverage_in or building_width_ft or ss_text or clips > 0 or backup > 0
    )

    if clips == 0 and ss_indicated and (
        panel_coverage_in or building_width_ft or ss_text
    ):
        findings.append({
            "severity": "CRITICAL",
            "category": "Standing Seam",
            "message": "Standing seam system indicated but zero sliding clips extracted from shipper.",
            "expected": ">0",
            "actual": 0,
            "rule": "ss_clips_present",
        })
        return findings

    if clips > 0:
        per = clip_spec.screws_per_clip if clip_spec else 2
        min_screws = screws_required(clips, clip_spec)
        if screws == 0:
            findings.append({
                "severity": "WARNING",
                "category": "Standing Seam",
                "message": (
                    f"{clips} clips but no panel clip screws detected "
                    f"(library requires ≥{per}/clip = {min_screws})."
                ),
                "expected": min_screws,
                "actual": 0,
                "rule": "ss_clip_screws_min",
            })
        elif screws < int(min_screws * (1.0 - tolerance)):
            findings.append({
                "severity": "WARNING",
                "category": "Standing Seam",
                "message": f"Clip screws ({screws}) below library minimum {per}× clips ({min_screws}).",
                "expected": min_screws,
                "actual": screws,
                "rule": "ss_clip_screws_min",
            })
        else:
            findings.append({
                "severity": "INFO",
                "category": "Standing Seam",
                "message": f"Clip screws ({screws}) meet ≥{per} per clip vs {clips} clips.",
                "rule": "ss_clip_screws_min",
            })

        # Thermal only when insulation is confirmed AND clip type needs a spacer
        # (or insulation confirmed with unknown clip). Do NOT treat clips alone as insulation.
        clip_needs_spacer = bool(
            getattr(clip_spec, "requires_thermal_spacer", False) if clip_spec else False
        )
        need_thermal = bool(has_insulation) and (clip_needs_spacer or clip_spec is None)
        if need_thermal:
            if blocks == 0:
                findings.append({
                    "severity": "WARNING",
                    "category": "Standing Seam",
                    "message": (
                        f"{clips} clips with insulation indicated; thermal spacer/blocks "
                        f"expected (~1:1) but none found"
                        + (f" for {clip_spec.name}" if clip_spec else "")
                        + "."
                    ),
                    "expected": clips,
                    "actual": 0,
                    "rule": "ss_thermal_blocks",
                })
            elif abs(blocks - clips) / max(clips, 1) > tolerance:
                findings.append({
                    "severity": "WARNING",
                    "category": "Standing Seam",
                    "message": f"Thermal blocks ({blocks}) vs clips ({clips}) outside ±{int(tolerance*100)}% band.",
                    "expected": clips,
                    "actual": blocks,
                    "rule": "ss_thermal_blocks",
                })

        if endlap_lines > 0 and backup == 0:
            plate_w = None
            if coverage_int:
                plate_w = backup_plate_for_coverage(coverage_int).get("width_in")
            findings.append({
                "severity": "WARNING",
                "category": "Standing Seam",
                "message": (
                    f"Endlap lines indicated ({endlap_lines}) but no backup plates extracted"
                    + (f" (expect ~{plate_w}\" plates)" if plate_w else "")
                    + "."
                ),
                "expected": ">0",
                "actual": 0,
                "rule": "ss_backup_plates",
            })
        elif backup > 0:
            msg = f"Backup plates extracted: {backup}"
            if coverage_int:
                bp = backup_plate_for_coverage(coverage_int)
                parts = bp.get("part_numbers") or ()
                if parts:
                    msg += f" (library plate for {bp['width_in']}\": {', '.join(parts)})"
            findings.append({
                "severity": "INFO",
                "category": "Standing Seam",
                "message": msg,
                "actual": backup,
                "rule": "ss_backup_plates",
            })

    if panel_coverage_in and building_width_ft and purlin_lines:
        exp = expected_ss_quantities(
            panel_coverage_in=panel_coverage_in,
            building_width_ft=building_width_ft,
            purlin_lines=purlin_lines,
            endlap_lines=endlap_lines,
            slopes=slopes,
            has_insulation=has_insulation,
            clip_key=clip_key or (clip_spec.key if clip_spec else None),
        )
        if exp.get("ok"):
            findings.append({
                "severity": "INFO",
                "category": "Standing Seam",
                "message": (
                    f"SS system estimate [{exp.get('clip_spec_name', 'clip')}] "
                    f"({exp['panel_coverage_in']}\"): clips≈{exp['expected_clips']}, "
                    f"screws≥{exp['expected_clip_screws']} ({exp['screws_per_clip']}/clip), "
                    f"thermal≈{exp['expected_thermal_blocks']}, "
                    f"backup≈{exp['expected_backup_plates']}"
                    + (f" @ {exp.get('backup_plate_width_in')}\"" if exp.get("backup_plate_width_in") else "")
                    + "."
                ),
                "expected": exp["expected_clips"],
                "actual": clips,
                "rule": "ss_system_estimate",
            })
            if clips > 0 and clips < int(exp["expected_clips"] * (1.0 - tolerance)):
                findings.append({
                    "severity": "CRITICAL",
                    "category": "Standing Seam",
                    "message": (
                        f"Sliding clips ({clips}) below estimated system need "
                        f"({exp['expected_clips']}) for {panel_coverage_in}\" panel / "
                        f"{purlin_lines} purlin lines."
                    ),
                    "expected": exp["expected_clips"],
                    "actual": clips,
                    "rule": "ss_clips_vs_geometry",
                })
            if backup > 0 and exp["expected_backup_plates"] > 0:
                if backup < int(exp["expected_backup_plates"] * (1.0 - tolerance)):
                    findings.append({
                        "severity": "WARNING",
                        "category": "Standing Seam",
                        "message": (
                            f"Backup plates ({backup}) below endlap estimate "
                            f"({exp['expected_backup_plates']})."
                        ),
                        "expected": exp["expected_backup_plates"],
                        "actual": backup,
                        "rule": "ss_backup_vs_geometry",
                    })

    return findings
