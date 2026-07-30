"""
Panel coverage width and type driven rules for clips, backup plates, and screws.

Supports:
- Standing Seam (VS16, CS184, CS244, etc.)
- Exposed fastener: R-Loc (PBR), 7.2 Panel, M-Loc, PBA
"""

from typing import Dict, Any, Optional

# Standing Seam clip density factors (relative to 24")
COVERAGE_FACTOR = {
    12: 2.00,
    16: 1.50,   # VS16 needs ~50% more seams than 24"
    18: 1.333,
    24: 1.00,
}

# Exposed fastener panel profiles used by Ascent / MBCI / Central States
EXPOSED_PANELS = {
    "r-loc": {
        "aliases": ["rloc", "r-loc", "pbr", "rloc26", "rloc24"],
        "coverage": 36,
        "rib_spacing": 12,
        "application": ["roof", "wall"],
        "fastener_system": "exposed",
        "typical_screws_per_support_line": 4,  # approx (major ribs + intermediate)
        "notes": "PBR-style 36\" coverage, 1-1/4\" ribs @ 12\" centers",
    },
    "7.2": {
        "aliases": ["7.2", "7-2", "72panel", "western rib", "box rib"],
        "coverage": 36,
        "rib_spacing": 7.2,
        "application": ["roof", "wall"],
        "fastener_system": "exposed",
        "typical_screws_per_support_line": 6,  # every low + lap stitch
        "notes": "36\" (or 28.8\") coverage, 1-1/2\" ribs @ 7.2\" centers",
    },
    "m-loc": {
        "aliases": ["mloc", "m-loc", "m_loc"],
        "coverage": 36,  # typical; confirm per data sheet
        "rib_spacing": None,
        "application": ["roof", "wall"],
        "fastener_system": "exposed",
        "typical_screws_per_support_line": 4,
        "notes": "Ascent M-Loc low-rib commercial panel",
    },
    "pba": {
        "aliases": ["pba", "pba panel"],
        "coverage": 36,
        "rib_spacing": None,
        "application": ["roof", "wall"],
        "fastener_system": "exposed",
        "typical_screws_per_support_line": 4,
        "notes": "PBA exposed fastener profile",
    },
    "pbm": {
        "aliases": ["pbm", "pbm panel"],
        "coverage": 36,
        "rib_spacing": None,
        "application": ["roof", "wall"],
        "fastener_system": "exposed",
        "typical_screws_per_support_line": 4,
        "notes": "PBM exposed fastener profile",
    },
    "avp": {
        "aliases": ["avp", "avp wall", "avp panel"],
        "coverage": 36,
        "rib_spacing": None,
        "application": ["wall"],
        "fastener_system": "exposed",
        "typical_screws_per_support_line": 4,
        "notes": "AVP exposed-fastener wall panel",
    },
    "rlr": {
        "aliases": ["rlr", "rloc reverse", "r-loc reverse", "rlocrev", "rpbr", "rev r-loc"],
        "coverage": 36,
        "rib_spacing": 12,
        "application": ["roof", "wall"],
        "fastener_system": "exposed",
        "typical_screws_per_support_line": 4,
        "notes": "R-Loc reverse (paint opposite side; high rib to girt)",
    },
}


def detect_exposed_panel(text: str) -> Optional[str]:
    """Return canonical panel key if an exposed fastener panel is mentioned."""
    t = text.lower()
    for key, info in EXPOSED_PANELS.items():
        for alias in info["aliases"]:
            if alias in t:
                return key
    return None


def check_clip_ratio(actual_clips: int, coverage_inches: int) -> dict:
    factor = COVERAGE_FACTOR.get(coverage_inches, 1.0)
    return {
        "coverage": coverage_inches,
        "factor": factor,
        "status": "ok",
        "note": f"Expected higher clip density for {coverage_inches}\" panels" if coverage_inches < 24 else "Standard 24\" density",
    }


def expected_exposed_screws(
    panel_key: str,
    panel_count: int,
    panel_length_ft: float = 20.0,
    support_spacing_ft: float = 5.0,
    is_roof: bool = True,
) -> Dict[str, Any]:
    """
    Rough estimate of required exposed fasteners.
    Real jobs vary with engineering; this is a sanity-check range.
    """
    info = EXPOSED_PANELS.get(panel_key)
    if not info:
        return {"expected_min": 0, "expected_max": 0, "note": "Unknown panel"}

    screws_per_line = info["typical_screws_per_support_line"]
    # Number of support lines along the length
    lines_per_panel = max(2, int(panel_length_ft / support_spacing_ft) + 1)
    base = panel_count * lines_per_panel * screws_per_line

    # Extra for sidelaps / endlaps / perimeter (rough +15-30%)
    extra_factor = 1.25 if is_roof else 1.15
    expected = int(base * extra_factor)

    return {
        "panel": panel_key,
        "expected_nominal": expected,
        "expected_min": int(expected * 0.7),
        "expected_max": int(expected * 1.5),
        "note": info["notes"],
    }
