"""
Complete standing seam application system checks (MBCI-aligned).

Expected quantities:
  clips ≈ seams × purlin_lines
  clip_screws ≥ 2 × clips
  thermal_blocks ≈ clips (when insulation system present)
  backup_plates ≈ endlap_lines × seams (panel-width plates)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def expected_ss_quantities(
    panel_coverage_in: float,
    building_width_ft: float,
    purlin_lines: int,
    endlap_lines: int = 0,
    slopes: int = 1,
    has_insulation: bool = True,
) -> Dict[str, Any]:
    """
    Compute expected SS accessory counts.

    building_width_ft: eave-to-eave width contributing to panel count (one slope run width).
    slopes: 1 for single slope, 2 for gable (applies width per slope if width is building width).
    """
    if panel_coverage_in <= 0 or building_width_ft <= 0 or purlin_lines <= 0:
        return {"ok": False, "reason": "insufficient geometry"}

    width_in = building_width_ft * 12.0
    # For gable, each slope is ~half span along width for simple symmetric buildings when
    # caller passes full building width — allow slopes factor.
    run_width_in = width_in / max(slopes, 1)
    seams_per_slope = max(1, int(math.ceil(run_width_in / panel_coverage_in)))
    # clips at each purlin along each seam
    clips = seams_per_slope * purlin_lines * max(slopes, 1)
    clip_screws = clips * 2
    thermal = clips if has_insulation else 0
    backup = max(0, endlap_lines) * seams_per_slope * max(slopes, 1)

    return {
        "ok": True,
        "panel_coverage_in": panel_coverage_in,
        "seams_per_slope": seams_per_slope,
        "purlin_lines": purlin_lines,
        "slopes": slopes,
        "expected_clips": clips,
        "expected_clip_screws": clip_screws,
        "expected_thermal_blocks": thermal,
        "expected_backup_plates": backup,
        "notes": "MBCI-style: ≥2 screws/clip; backup plates at endlaps per panel module",
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
) -> List[Dict[str, Any]]:
    """
    Compare extracted SS accessories to system expectations.

    Always runs presence / ratio rules. Geometry-based expected counts run when
    coverage + width + purlin_lines are provided.
    """
    findings: List[Dict[str, Any]] = []
    acc = ss_accessories or {}
    clips = int(acc.get("sliding_clips", 0) or 0)
    screws = int(acc.get("clip_screws", 0) or 0)
    blocks = int(acc.get("thermal_blocks", 0) or 0)
    backup = int(acc.get("backup_plates_24", 0) or 0) + int(acc.get("backup_plates_18", 0) or 0)

    if clips == 0 and (panel_coverage_in or building_width_ft):
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
        # 2 screws per clip minimum (MBCI)
        min_screws = clips * 2
        if screws == 0:
            findings.append({
                "severity": "WARNING",
                "category": "Standing Seam",
                "message": f"{clips} sliding clips but no panel clip screws detected (expect ≥2 per clip = {min_screws}).",
                "expected": min_screws,
                "actual": 0,
                "rule": "ss_clip_screws_min",
            })
        elif screws < int(min_screws * (1.0 - tolerance)):
            findings.append({
                "severity": "WARNING",
                "category": "Standing Seam",
                "message": f"Clip screws ({screws}) below MBCI minimum 2× clips ({min_screws}).",
                "expected": min_screws,
                "actual": screws,
                "rule": "ss_clip_screws_min",
            })
        else:
            findings.append({
                "severity": "INFO",
                "category": "Standing Seam",
                "message": f"Clip screws ({screws}) meet ≥2 per clip vs {clips} clips.",
                "rule": "ss_clip_screws_min",
            })

        if has_insulation:
            if blocks == 0:
                findings.append({
                    "severity": "CRITICAL",
                    "category": "Standing Seam",
                    "message": f"{clips} clips with insulation system expected but zero thermal blocks found.",
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

        # Backup plates: if endlaps expected, require some plates; else INFO only
        if endlap_lines > 0 and backup == 0:
            findings.append({
                "severity": "WARNING",
                "category": "Standing Seam",
                "message": f"Endlap lines indicated ({endlap_lines}) but no backup plates extracted.",
                "expected": ">0",
                "actual": 0,
                "rule": "ss_backup_plates",
            })
        elif backup > 0:
            findings.append({
                "severity": "INFO",
                "category": "Standing Seam",
                "message": f"Backup plates extracted: {backup} (18\" + 24\" combined).",
                "actual": backup,
                "rule": "ss_backup_plates",
            })

    # Geometry-driven expected counts
    if panel_coverage_in and building_width_ft and purlin_lines:
        exp = expected_ss_quantities(
            panel_coverage_in=panel_coverage_in,
            building_width_ft=building_width_ft,
            purlin_lines=purlin_lines,
            endlap_lines=endlap_lines,
            slopes=slopes,
            has_insulation=has_insulation,
        )
        if exp.get("ok"):
            findings.append({
                "severity": "INFO",
                "category": "Standing Seam",
                "message": (
                    f"SS system estimate ({exp['panel_coverage_in']}\" coverage): "
                    f"clips≈{exp['expected_clips']}, screws≥{exp['expected_clip_screws']}, "
                    f"thermal≈{exp['expected_thermal_blocks']}, backup≈{exp['expected_backup_plates']}."
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
