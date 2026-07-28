"""
Ascent trim length calculation rules.

Source: Trim Lengths.pdf (Base Camp).
Standard stick lengths only: 10'-2", 12'-2", 14'-2", 16'-2", 18'-2", 20'-4".
Typical lap = 2".
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

STANDARD_TRIM_FT = [10.0 + 2 / 12, 12.0 + 2 / 12, 14.0 + 2 / 12, 16.0 + 2 / 12, 18.0 + 2 / 12, 20.0 + 4 / 12]
# 10.167, 12.167, 14.167, 16.167, 18.167, 20.333


def _round_up_to_standard(length_ft: float) -> float:
    for s in STANDARD_TRIM_FT:
        if length_ft <= s + 1e-6:
            return s
    return STANDARD_TRIM_FT[-1]


def sticks_for_run(run_ft: float, divisor_ft: float = 20.0, extra_ft: float = 1.0) -> Dict[str, Any]:
    """
    Ascent method: (run + extra) / divisor → whole sticks of ~20' plus remainder
    rounded up to nearest standard length.
    """
    if run_ft <= 0:
        return {"sticks": [], "count": 0, "total_ordered_ft": 0.0}
    need = run_ft + extra_ft
    whole = int(math.floor(need / divisor_ft))
    rem_frac = (need / divisor_ft) - whole
    sticks: List[float] = [STANDARD_TRIM_FT[-1]] * whole  # prefer 20'-4" for whole portions
    if rem_frac > 0.02:
        rem_len = divisor_ft * rem_frac
        sticks.append(_round_up_to_standard(rem_len))
    elif whole == 0:
        sticks.append(_round_up_to_standard(need))
    return {
        "sticks": sticks,
        "count": len(sticks),
        "total_ordered_ft": sum(sticks),
        "need_ft": need,
    }


def expected_trim_counts(
    building_length_ft: Optional[float] = None,
    building_width_ft: Optional[float] = None,
    roof_slope_rise_per_12: float = 1.0,
    eave_sides: int = 2,
    has_gutter: bool = True,
) -> List[Dict[str, Any]]:
    """
    High-level expected stick counts for common roof trims.
    Slope length factor ≈ sqrt(1 + (rise/12)^2).
    """
    findings = []
    slope_factor = math.sqrt(1.0 + (roof_slope_rise_per_12 / 12.0) ** 2)

    if building_length_ft:
        eave = sticks_for_run(building_length_ft * max(eave_sides, 1) / max(eave_sides, 1), extra_ft=1.0)
        # per eave line
        per_eave = sticks_for_run(building_length_ft, extra_ft=1.0)
        findings.append({
            "trim": "eave_trim",
            "rule": "Length of Eave + 1'-0" / 20', round up",
            **per_eave,
            "lines": eave_sides,
            "total_sticks_all_lines": per_eave["count"] * eave_sides,
        })
        if has_gutter:
            g = sticks_for_run(building_length_ft, extra_ft=1.0)
            findings.append({
                "trim": "eave_gutter",
                "rule": "Building length + 1'-0" / 20'",
                **g,
                "lines": eave_sides,
                "total_sticks_all_lines": g["count"] * eave_sides,
            })

    if building_width_ft:
        sloped = building_width_ft * slope_factor
        rake = sticks_for_run(sloped, extra_ft=1.0)
        findings.append({
            "trim": "rake_trim",
            "rule": "Building width sloped + 1'-0" / 20'",
            "sloped_width_ft": sloped,
            **rake,
            "lines": 2,
            "total_sticks_all_lines": rake["count"] * 2,
        })

    return findings


def check_trim_against_ascent(
    shipper_trim_count: int,
    building_length_ft: Optional[float] = None,
    building_width_ft: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Soft check: if geometry known, compare total trim sticks order of magnitude."""
    out: List[Dict[str, Any]] = []
    exp = expected_trim_counts(building_length_ft, building_width_ft)
    if not exp:
        return out
    expected_total = sum(e.get("total_sticks_all_lines", e.get("count", 0)) for e in exp)
    out.append({
        "severity": "INFO",
        "category": "Trim",
        "message": f"Ascent trim estimate (eave/gutter/rake only): ~{expected_total} sticks; shipper trim pieces: {shipper_trim_count}.",
        "expected": expected_total,
        "actual": shipper_trim_count,
        "rule": "ascent_trim_estimate",
    })
    if shipper_trim_count > 0 and expected_total > 0:
        if shipper_trim_count < int(expected_total * 0.5):
            out.append({
                "severity": "WARNING",
                "category": "Trim",
                "message": f"Shipper trim count ({shipper_trim_count}) well below Ascent eave/rake/gutter estimate ({expected_total}).",
                "expected": expected_total,
                "actual": shipper_trim_count,
                "rule": "ascent_trim_vs_geometry",
            })
    return out
