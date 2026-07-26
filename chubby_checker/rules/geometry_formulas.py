"""
Building-geometry driven length formulas for Ascent trim, gutter, and related accessories.

All lengths returned in feet unless noted.
Formulas are practical rules-of-thumb used for shipper sanity checks, not engineering design.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import math


@dataclass
class BuildingGeometry:
    """Minimal geometry needed for trim / gutter estimates."""
    length_ft: float          # building length (ridge direction)
    width_ft: float           # building width
    eave_height_ft: Optional[float] = None
    roof_slope: Optional[float] = None   # e.g. 1.0 for 1:12, 0.5 for 0.5:12
    endwall_count: int = 2
    sidewall_count: int = 2
    has_open_sides: bool = False

    @property
    def perimeter_ft(self) -> float:
        return 2 * (self.length_ft + self.width_ft)

    @property
    def eave_length_ft(self) -> float:
        """Total eave length (both sidewalls)."""
        return 2 * self.length_ft

    @property
    def rake_length_ft(self) -> float:
        """
        Approximate total rake length (both endwalls).
        For a simple gable: each rake = sqrt((width/2)^2 + rise^2)
        If slope unknown, fall back to width (conservative flat estimate).
        """
        if self.roof_slope and self.roof_slope > 0:
            half_w = self.width_ft / 2.0
            rise = half_w * (self.roof_slope / 12.0)
            rake_one = math.sqrt(half_w ** 2 + rise ** 2)
            return 2 * rake_one * self.endwall_count / 2  # two rakes per endwall pair
        # Fallback: two endwalls × width
        return 2 * self.width_ft


def expected_gutter_length(geo: BuildingGeometry, sides: int = 2) -> Dict[str, Any]:
    """
    Expected gutter length.
    Default: both eaves (2 × building length).
    `sides` can be 1 if only one eave receives gutter.
    """
    length = geo.length_ft * sides
    return {
        "item": "gutter",
        "expected_ft": round(length, 1),
        "formula": f"{sides} × building length ({geo.length_ft} ft)",
        "notes": "Assumes continuous eave gutter. Adjust if partial coverage or canopies.",
    }


def expected_downspout_count(
    geo: BuildingGeometry,
    spacing_ft: float = 40.0,
    sides: int = 2,
) -> Dict[str, Any]:
    """
    Rough downspout count: one per `spacing_ft` of eave, both sides by default.
    """
    eave = geo.length_ft * sides
    count = max(sides * 2, int(math.ceil(eave / spacing_ft)))  # at least 2 per side
    return {
        "item": "downspout",
        "expected_count": count,
        "formula": f"ceil(eave_length / {spacing_ft} ft), min 2 per side",
        "notes": "Typical commercial spacing 30–50 ft. Confirm with drawings.",
    }


def expected_eave_trim(geo: BuildingGeometry, sides: int = 2) -> Dict[str, Any]:
    length = geo.length_ft * sides
    return {
        "item": "eave_trim",
        "expected_ft": round(length, 1),
        "formula": f"{sides} × building length",
    }


def expected_rake_trim(geo: BuildingGeometry) -> Dict[str, Any]:
    length = geo.rake_length_ft
    return {
        "item": "rake_trim",
        "expected_ft": round(length, 1),
        "formula": "2 × rake length (slope-adjusted if available, else 2 × width)",
    }


def expected_corner_trim(geo: BuildingGeometry, corners: int = 4) -> Dict[str, Any]:
    """Outside corner trim – typically one piece per corner, length ≈ eave height."""
    if geo.eave_height_ft:
        total = corners * geo.eave_height_ft
        return {
            "item": "corner_trim",
            "expected_ft": round(total, 1),
            "expected_pieces": corners,
            "formula": f"{corners} corners × eave height ({geo.eave_height_ft} ft)",
        }
    return {
        "item": "corner_trim",
        "expected_pieces": corners,
        "expected_ft": None,
        "formula": f"{corners} corners (height unknown)",
    }


def expected_base_trim(geo: BuildingGeometry) -> Dict[str, Any]:
    """Base trim / base angle around the perimeter (minus openings – ignored here)."""
    return {
        "item": "base_trim",
        "expected_ft": round(geo.perimeter_ft, 1),
        "formula": "2 × (length + width)",
    }


def expected_ridge_trim(geo: BuildingGeometry) -> Dict[str, Any]:
    return {
        "item": "ridge_trim",
        "expected_ft": round(geo.length_ft, 1),
        "formula": "building length (single ridge)",
    }


def all_trim_expectations(geo: BuildingGeometry) -> Dict[str, Dict[str, Any]]:
    """Convenience: all standard trim length expectations."""
    return {
        "gutter": expected_gutter_length(geo),
        "downspout": expected_downspout_count(geo),
        "eave_trim": expected_eave_trim(geo),
        "rake_trim": expected_rake_trim(geo),
        "corner_trim": expected_corner_trim(geo),
        "base_trim": expected_base_trim(geo),
        "ridge_trim": expected_ridge_trim(geo),
    }


def compare_length(
    expected_ft: Optional[float],
    actual_ft: Optional[float],
    tolerance_pct: float = 0.20,
    tolerance_ft: float = 10.0,
) -> Dict[str, Any]:
    """
    Compare expected vs actual length.
    Passes if actual is within max(tolerance_pct * expected, tolerance_ft).
    """
    if expected_ft is None or actual_ft is None:
        return {"status": "skip", "message": "Insufficient data"}

    delta = abs(expected_ft - actual_ft)
    allow = max(expected_ft * tolerance_pct, tolerance_ft)

    if delta <= allow:
        return {
            "status": "ok",
            "expected_ft": expected_ft,
            "actual_ft": actual_ft,
            "delta_ft": round(delta, 1),
        }
    return {
        "status": "mismatch",
        "expected_ft": expected_ft,
        "actual_ft": actual_ft,
        "delta_ft": round(delta, 1),
        "allowance_ft": round(allow, 1),
    }
