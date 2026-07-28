"""
Exposed fastener sheeting quantity rules (MBCI PBR / 7.2 / M-Loc / PBA aligned).

Typical PBR patterns from MBCI manuals:
  - Intermediate purlin: 3 fasteners per panel
  - Eave / high-side / endlap: 6 fasteners per panel
  - Side lap: ~20\" o.c. along slope

7.2 panel uses denser ribs → more screws per support line.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

from chubby_checker.rules.panel_rules import EXPOSED_PANELS, detect_exposed_panel

# Panel key -> screws per panel at intermediate support / at eave-endlap
PANEL_SCREW_PATTERN = {
    "r-loc": {"intermediate": 3, "eave_endlap": 6, "sidelap_oc_in": 20, "coverage_in": 36},
    "7.2": {"intermediate": 6, "eave_endlap": 6, "sidelap_oc_in": 20, "coverage_in": 36},
    "m-loc": {"intermediate": 3, "eave_endlap": 6, "sidelap_oc_in": 20, "coverage_in": 36},
    "pba": {"intermediate": 3, "eave_endlap": 6, "sidelap_oc_in": 20, "coverage_in": 36},
}


def expected_exposed_fastener_qty(
    panel_key: str,
    area_width_ft: float,
    slope_length_ft: float,
    support_lines: int,
    eave_endlap_lines: int = 2,
    is_roof: bool = True,
) -> Dict[str, Any]:
    """
    Estimate total exposed structural + sidelap fasteners for one roof/wall plane.
    """
    key = panel_key if panel_key in PANEL_SCREW_PATTERN else "r-loc"
    pat = PANEL_SCREW_PATTERN[key]
    coverage = pat["coverage_in"]
    panels_across = max(1, int(math.ceil((area_width_ft * 12.0) / coverage)))

    inter_lines = max(0, support_lines - eave_endlap_lines)
    eave_lines = max(0, min(eave_endlap_lines, support_lines))

    structural = (
        panels_across * inter_lines * pat["intermediate"]
        + panels_across * eave_lines * pat["eave_endlap"]
    )
    seams = max(0, panels_across - 1)
    sidelap = 0
    if slope_length_ft > 0 and seams > 0:
        per_seam = max(1, int(math.ceil((slope_length_ft * 12.0) / pat["sidelap_oc_in"])))
        sidelap = seams * per_seam

    total = structural + sidelap
    return {
        "panel": key,
        "panels_across": panels_across,
        "structural": structural,
        "sidelap": sidelap,
        "expected_nominal": total,
        "expected_min": int(total * 0.70),
        "expected_max": int(total * 1.50),
        "is_roof": is_roof,
    }


def extract_screw_count_from_shipper(categories: Dict[str, list]) -> int:
    """Sum screw/fastener piece quantities (excluding clip-specific already counted elsewhere)."""
    total = 0
    for cat, pieces in (categories or {}).items():
        cat_l = cat.lower()
        for p in pieces:
            desc = f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')} {cat}".lower()
            if any(k in desc or k in cat_l for k in ("screw", "fastener", "tek", "self-drill", "self drill")):
                if "clip screw" in desc or "panel clip screw" in desc:
                    continue  # counted in SS system
                total += int(getattr(p, "quantity", 0) or 0)
    return total


def detect_panel_key_from_categories(categories: Dict[str, list]) -> Optional[str]:
    blob = " ".join(
        [c for c in (categories or {}).keys()]
        + [f"{getattr(p, 'description', '')}" for plist in (categories or {}).values() for p in plist]
    )
    return detect_exposed_panel(blob)


def check_sheeting_fasteners(
    categories: Dict[str, list],
    panel_key: Optional[str] = None,
    area_width_ft: Optional[float] = None,
    slope_length_ft: Optional[float] = None,
    support_lines: Optional[int] = None,
    eave_endlap_lines: int = 2,
    is_roof: bool = True,
) -> List[Dict[str, Any]]:
    """
    Compare shipper screw totals to MBCI-style expected bands when geometry is known.
    Always reports extracted screw totals when present.
    """
    findings: List[Dict[str, Any]] = []
    actual = extract_screw_count_from_shipper(categories)
    key = panel_key or detect_panel_key_from_categories(categories)

    if actual > 0:
        findings.append({
            "severity": "INFO",
            "category": "Sheeting Fasteners",
            "message": f"Exposed/sheeting fasteners extracted from shipper: {actual:,}"
                       + (f" (panel type hint: {key})" if key else ""),
            "actual": actual,
            "rule": "sheeting_screws_extracted",
        })

    # Presence: if exposed panel marks exist but zero screws
    if key and actual == 0:
        findings.append({
            "severity": "CRITICAL",
            "category": "Sheeting Fasteners",
            "message": f"Exposed panel type '{key}' detected but no sheeting screws/fasteners found in shipper.",
            "expected": ">0",
            "actual": 0,
            "rule": "sheeting_screws_present",
        })
        return findings

    if not (key and area_width_ft and support_lines):
        return findings

    exp = expected_exposed_fastener_qty(
        panel_key=key,
        area_width_ft=area_width_ft,
        slope_length_ft=slope_length_ft or 0.0,
        support_lines=support_lines,
        eave_endlap_lines=eave_endlap_lines,
        is_roof=is_roof,
    )
    findings.append({
        "severity": "INFO",
        "category": "Sheeting Fasteners",
        "message": (
            f"{exp['panel']} estimate: nominal {exp['expected_nominal']:,} "
            f"(band {exp['expected_min']:,}–{exp['expected_max']:,}); "
            f"structural {exp['structural']:,}, sidelap {exp['sidelap']:,}."
        ),
        "expected": exp["expected_nominal"],
        "actual": actual,
        "rule": "sheeting_screws_estimate",
    })

    if actual > 0:
        if actual < exp["expected_min"]:
            findings.append({
                "severity": "CRITICAL",
                "category": "Sheeting Fasteners",
                "message": (
                    f"Sheeting fasteners ({actual:,}) below estimated minimum "
                    f"({exp['expected_min']:,}) for {exp['panel']}."
                ),
                "expected": exp["expected_min"],
                "actual": actual,
                "rule": "sheeting_screws_vs_geometry",
            })
        elif actual > exp["expected_max"]:
            findings.append({
                "severity": "INFO",
                "category": "Sheeting Fasteners",
                "message": (
                    f"Sheeting fasteners ({actual:,}) above estimated maximum band "
                    f"({exp['expected_max']:,}) — may include extras or multi-plane totals."
                ),
                "expected": exp["expected_max"],
                "actual": actual,
                "rule": "sheeting_screws_vs_geometry",
            })
        else:
            findings.append({
                "severity": "INFO",
                "category": "Sheeting Fasteners",
                "message": f"Sheeting fasteners ({actual:,}) within estimated band for {exp['panel']}.",
                "rule": "sheeting_screws_vs_geometry",
            })

    return findings
