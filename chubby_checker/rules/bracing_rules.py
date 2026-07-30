"""
Rod / cable bracing hardware kit completeness.

Field failure 25-13168 SO2: rod bracing shipped without hillsides, nuts, washers.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


ROD_CABLE_PATTERNS = (
    r"\brod\s*brac",
    r"\bcable\s*brac",
    r"\bbrace\s*rod\b",
    r"\bbracing\s*rod\b",
    r"\bx[- ]?brace\b",
    r"\brd-?\d",
    r"\bcb-?\d",
    r"\bdiag(?:onal)?\s*brace",
)

HARDWARE_PATTERNS = (
    r"\bhillside\b",
    r"\bclevis\b",
    r"\bturnbuckle\b",
    r"\beyebolt\b",
    r"\beye\s*bolt\b",
    r"\bcable\s*clamp\b",
    r"\bthimble\b",
    r"\bbrace\s*plate\b",
)


def _blob(categories: Optional[Dict[str, list]], raw_text: str = "") -> str:
    parts = [raw_text or ""]
    for cat, pieces in (categories or {}).items():
        parts.append(str(cat))
        for p in pieces:
            parts.append(f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')}")
    return " ".join(parts)


def _count_matches(blob: str, patterns: tuple) -> int:
    n = 0
    for pat in patterns:
        n += len(re.findall(pat, blob, re.I))
    return n


def _qty_for_patterns(categories: Optional[Dict[str, list]], patterns: tuple) -> int:
    total = 0
    for cat, pieces in (categories or {}).items():
        for p in pieces:
            desc = f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')} {cat}"
            if any(re.search(pat, desc, re.I) for pat in patterns):
                total += int(getattr(p, "quantity", 0) or 0)
    return total


def check_bracing_hardware_kit(
    categories: Optional[Dict[str, list]] = None,
    drawings_text: str = "",
    shipper_raw_text: str = "",
) -> List[Dict[str, Any]]:
    """
    If rod/cable bracing is present, expect hillside/clevis/turnbuckle kit + nuts/washers.
    rule: bracing_hardware_kit
    """
    findings: List[Dict[str, Any]] = []
    ship_blob = _blob(categories, shipper_raw_text)
    draw_blob = drawings_text or ""
    combined = f"{ship_blob}\n{draw_blob}"

    rod_qty = _qty_for_patterns(categories, ROD_CABLE_PATTERNS)
    has_rods = rod_qty > 0 or _count_matches(ship_blob, ROD_CABLE_PATTERNS) > 0
    has_rods_drawings = _count_matches(draw_blob, ROD_CABLE_PATTERNS) > 0
    if not has_rods and not has_rods_drawings:
        return findings

    hw_qty = _qty_for_patterns(categories, HARDWARE_PATTERNS)
    has_hw = hw_qty > 0 or _count_matches(ship_blob, HARDWARE_PATTERNS) > 0

    # Nuts/washers near brace context is soft; use bolt category totals as proxy
    nut_wash = 0
    for cat, pieces in (categories or {}).items():
        cl = cat.lower()
        if any(k in cl for k in ("nut", "washer", "bolt")):
            for p in pieces:
                desc = f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')}".lower()
                if any(k in desc for k in ("nut", "washer")) or "nut" in cl or "washer" in cl:
                    nut_wash += int(getattr(p, "quantity", 0) or 0)

    if has_rods and not has_hw:
        findings.append({
            "severity": "WARNING",
            "category": "Bracing",
            "message": (
                f"Rod/cable bracing is present on the shipper"
                f"{f' (≈{rod_qty} pcs)' if rod_qty else ''}, but no hillside / clevis / "
                "turnbuckle (or similar brace hardware) was detected. "
                "Brace kits typically include hillsides, nuts, and washers."
            ),
            "expected": ">0 hillside/clevis/turnbuckle",
            "actual": 0,
            "rule": "bracing_hardware_kit",
        })
    elif has_rods_drawings and not has_rods and not has_hw:
        findings.append({
            "severity": "WARNING",
            "category": "Bracing",
            "message": (
                "Drawings reference rod/cable bracing, but neither rods/cables nor "
                "hillside/clevis brace hardware were found on the shipper."
            ),
            "expected": "bracing + hardware kit",
            "actual": "missing",
            "rule": "bracing_hardware_kit",
        })
    elif has_rods and has_hw and nut_wash == 0:
        findings.append({
            "severity": "WARNING",
            "category": "Bracing",
            "message": (
                "Rod/cable bracing and hillside/clevis hardware are present, but no "
                "nuts/washers were detected for the brace kit — confirm shop hardware."
            ),
            "expected": ">0 nuts/washers for brace kit",
            "actual": 0,
            "rule": "bracing_hardware_kit",
        })
    elif has_rods and has_hw:
        findings.append({
            "severity": "INFO",
            "category": "Bracing",
            "message": (
                f"Rod/cable bracing with brace hardware detected "
                f"(rods≈{rod_qty or 'present'}, hardware≈{hw_qty or 'present'})."
            ),
            "rule": "bracing_hardware_kit",
        })

    return findings
