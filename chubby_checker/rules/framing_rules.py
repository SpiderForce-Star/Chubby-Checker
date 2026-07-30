"""
Full Primary & Secondary Framing Review for Chubby-Checker.

Primary:
  - Rigid / Main frames (RF, PF, MF)
  - Endwall frames / columns
  - Intermediate / soldier / crane columns
  - Primary rafters & beams tied to frames

Secondary:
  - Purlins (roof)
  - Girts (walls)
  - Eave struts
  - Flange braces
  - Sag angles / bridging (when present)

Calibrated on Ascent mark conventions from jobs 25-13266, 25-13059, 25-13168.
"""

from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import re

from chubby_checker.models.piece import Piece

# ---------------------------------------------------------------------------
# Mark classification
# ---------------------------------------------------------------------------

PRIMARY_PREFIXES = {
    "RF": "Rigid Frame",
    "PF": "Primary Frame",
    "MF": "Main Frame",
    "EF": "Endwall Frame",
    "IF": "Interior Frame",
    "RC": "Rafter / Rigid Column",
    "AC": "Aux / Crane Column",
    "SC": "Soldier / Secondary Column",
    "EC": "Endwall Column",
    "CC": "Crane Column",
    "HC": "Heavy Column",
    "COL": "Column",
}

SECONDARY_PREFIXES = {
    "P": "Purlin",          # P1, P-1, P101, etc. – careful with false positives
    "G": "Girt",
    "CG": "Cee Girt",
    "PG": "Purlin / Girt",
    "ES": "Eave Strut",
    "E": "Eave Strut / Edge",
    "FB": "Flange Brace",
    "FBR": "Flange Brace",
    "SA": "Sag Angle",
    "BR": "Bridging / Brace",
    "ZB": "Z Bridging",
    "CB": "Cee Bridging",
}

# More specific secondary patterns (avoid treating every "P" as purlin)
PURLIN_PATTERNS = [
    r"^P-?\d+", r"^PR-?\d+", r"^PUR", r"PURLIN", r"Z\d{5,}", r"Z\d+X\d+",
]
GIRT_PATTERNS = [
    r"^G-?\d+", r"^GR-?\d+", r"^CG-?\d+", r"GIRT", r"C\d{5,}",
]
EAVE_STRUT_PATTERNS = [
    r"^ES-?\d+", r"^E-?\d+", r"EAVE\s*STRUT", r"EAVESTRUT",
]
FLANGE_BRACE_PATTERNS = [
    r"^FB-?\d+", r"^FBR-?\d+", r"FLANGE\s*BRACE", r"FLANGEBRACE",
]


def _match_any(text: str, patterns: List[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify_mark(mark: str, description: str = "") -> Tuple[str, str]:
    """
    Return (family, sub_type) where family is 'primary' | 'secondary' | 'other'.
    """
    m = (mark or "").upper().strip()
    d = (description or "").upper()
    combined = f"{m} {d}"

    # Primary – require prefix + digit/separator (avoid COL→COLD, SC→SCREW)
    for prefix, label in PRIMARY_PREFIXES.items():
        if re.match(rf"^{re.escape(prefix)}(?:\d|[-_])", m):
            return "primary", label
        if len(prefix) >= 2 and m == prefix:
            return "primary", label

    if any(k in combined for k in ["RIGID FRAME", "MAIN FRAME", "PRIMARY FRAME", "ENDWALL FRAME"]):
        return "primary", "Frame"
    if any(k in combined for k in ["CRANE COLUMN", "SOLDIER COLUMN", "ENDWALL COLUMN"]):
        return "primary", "Column"

    # Secondary – specific patterns
    if _match_any(m, PURLIN_PATTERNS) or "PURLIN" in d:
        return "secondary", "Purlin"
    if _match_any(m, GIRT_PATTERNS) or "GIRT" in d:
        return "secondary", "Girt"
    if _match_any(m, EAVE_STRUT_PATTERNS) or "EAVE STRUT" in d or "EAVESTRUT" in d:
        return "secondary", "Eave Strut"
    if _match_any(m, FLANGE_BRACE_PATTERNS) or "FLANGE BRACE" in d:
        return "secondary", "Flange Brace"
    if any(k in combined for k in ["SAG ANGLE", "BRIDGING", "SAG ROD"]):
        return "secondary", "Bridging / Sag"

    # Cold formed category fallback
    if "COLD FORMED" in d or "COLD FORMED" in m:
        return "secondary", "Cold Formed"

    return "other", "Other"


def build_framing_inventory(categories: Dict[str, List[Piece]]) -> Dict[str, Any]:
    """
    Classify all pieces into primary / secondary inventories.
    Returns counts and mark lists suitable for review rules.
    """
    primary: Dict[str, List[Piece]] = defaultdict(list)
    secondary: Dict[str, List[Piece]] = defaultdict(list)
    other: List[Piece] = []

    for cat, pieces in categories.items():
        for p in pieces:
            family, sub = classify_mark(p.mark, f"{p.description} {cat}")
            if family == "primary":
                primary[sub].append(p)
            elif family == "secondary":
                secondary[sub].append(p)
            else:
                other.append(p)

    def summarize(group: Dict[str, List[Piece]]) -> Dict[str, Any]:
        out = {}
        for sub, plist in group.items():
            out[sub] = {
                "count": sum(p.quantity for p in plist),
                "unique_marks": len({p.mark for p in plist}),
                "marks": sorted({p.mark for p in plist}),
                "pieces": plist,
            }
        return out

    return {
        "primary": summarize(primary),
        "secondary": summarize(secondary),
        "other_count": sum(p.quantity for p in other),
    }


def _all_shipper_marks(inventory: Dict[str, Any], categories: Optional[Dict[str, List[Piece]]] = None) -> set:
    """Union of all marks in inventory + raw categories (case-sensitive as on shipper)."""
    marks: set = set()
    for fam in ("primary", "secondary"):
        for info in (inventory.get(fam) or {}).values():
            marks.update(info.get("marks") or [])
    if categories:
        for pieces in categories.values():
            for p in pieces:
                if getattr(p, "mark", None):
                    marks.add(p.mark)
    return marks


def review_primary_framing(
    inventory: Dict[str, Any],
    drawings_marks: Optional[Dict[str, int]] = None,
    all_shipper_marks: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """
    Primary framing review findings.
    """
    findings = []
    primary = inventory.get("primary", {})

    total_primary = sum(v["count"] for v in primary.values())
    if total_primary == 0:
        findings.append({
            "severity": "WARNING",
            "category": "Primary Framing",
            "message": "No primary framing marks (RF/PF/MF/columns) detected in shipper.",
            "rule": "primary_present",
        })
        return findings

    # Summarize what we found
    parts = [f"{sub}: {info['count']} pcs ({info['unique_marks']} marks)" for sub, info in primary.items()]
    findings.append({
        "severity": "INFO",
        "category": "Primary Framing",
        "message": "Primary framing detected — " + "; ".join(parts),
        "actual": total_primary,
        "rule": "primary_summary",
    })

    # Expect at least some frame marks on a normal building
    frame_count = sum(
        primary.get(k, {}).get("count", 0)
        for k in ["Rigid Frame", "Primary Frame", "Main Frame", "Endwall Frame", "Interior Frame", "Frame"]
    )
    col_count = sum(
        primary.get(k, {}).get("count", 0)
        for k in ["Column", "Aux / Crane Column", "Soldier / Secondary Column", "Endwall Column", "Crane Column", "Heavy Column"]
    )

    if frame_count == 0 and col_count > 0:
        findings.append({
            "severity": "INFO",
            "category": "Primary Framing",
            "message": "Columns present but no explicit RF/PF/MF frame marks detected (may be embedded in Fabricated Steel).",
            "rule": "primary_frames_vs_columns",
        })

    # Cross-check: mark present anywhere on shipper is enough (avoid false CRITICAL)
    if drawings_marks:
        ship_marks = all_shipper_marks or _all_shipper_marks(inventory)
        ship_upper = {str(m).upper() for m in ship_marks}
        primary_draw_marks = {
            m: q for m, q in drawings_marks.items()
            if classify_mark(m)[0] == "primary"
        }
        for m, q in list(primary_draw_marks.items())[:25]:
            if str(m).upper() in ship_upper or m in ship_marks:
                continue
            findings.append({
                "severity": "WARNING",
                "category": "Primary Framing",
                "message": (
                    f"Primary mark {m} (qty {q}) appears on drawings but was not found "
                    "on the shipper. Confirm phase or mark naming."
                ),
                "mark": m,
                "expected": q,
                "actual": 0,
                "rule": "primary_mark_missing",
            })

    return findings


def review_secondary_framing(
    inventory: Dict[str, Any],
    has_primary: bool = True,
    drawings_marks: Optional[Dict[str, int]] = None,
    all_shipper_marks: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """
    Secondary framing review findings.
    """
    findings = []
    secondary = inventory.get("secondary", {})

    total_secondary = sum(v["count"] for v in secondary.values())

    if has_primary and total_secondary == 0:
        findings.append({
            "severity": "WARNING",
            "category": "Secondary Framing",
            "message": "Primary framing present but no secondary (purlins/girts/eave struts/flange braces) detected.",
            "rule": "secondary_present",
        })
        return findings

    if total_secondary == 0:
        return findings

    parts = [f"{sub}: {info['count']} pcs ({info['unique_marks']} marks)" for sub, info in secondary.items()]
    findings.append({
        "severity": "INFO",
        "category": "Secondary Framing",
        "message": "Secondary framing detected — " + "; ".join(parts),
        "actual": total_secondary,
        "rule": "secondary_summary",
    })

    purlins = secondary.get("Purlin", {}).get("count", 0)
    girts = secondary.get("Girt", {}).get("count", 0)
    eave = secondary.get("Eave Strut", {}).get("count", 0)
    fb = secondary.get("Flange Brace", {}).get("count", 0)

    # Basic expectations for a complete envelope job
    if purlins == 0 and girts == 0 and eave == 0:
        findings.append({
            "severity": "WARNING",
            "category": "Secondary Framing",
            "message": "No purlins, girts, or eave struts detected — verify secondary is in this phase or another shipper.",
            "rule": "secondary_members_missing",
        })

    if purlins > 0 and fb == 0:
        findings.append({
            "severity": "INFO",
            "category": "Flange Braces",
            "message": f"Purlins present ({purlins}) but no flange braces detected. Confirm if required for this system.",
            "rule": "flange_brace_with_purlins",
        })

    if girts > 0 and fb == 0:
        findings.append({
            "severity": "INFO",
            "category": "Flange Braces",
            "message": f"Girts present ({girts}) but no flange braces detected. Confirm if required.",
            "rule": "flange_brace_with_girts",
        })

    # Drawings cross-check: present anywhere on shipper is enough
    if drawings_marks:
        ship_marks = all_shipper_marks or _all_shipper_marks(inventory)
        ship_upper = {str(m).upper() for m in ship_marks}
        sec_draw = {
            m: q for m, q in drawings_marks.items()
            if classify_mark(m)[0] == "secondary"
        }
        for m, q in list(sec_draw.items())[:25]:
            if str(m).upper() in ship_upper or m in ship_marks:
                continue
            findings.append({
                "severity": "WARNING",
                "category": "Secondary Framing",
                "message": (
                    f"Secondary mark {m} (qty {q}) on drawings but missing from shipper. "
                    "Confirm phase or mark naming."
                ),
                "mark": m,
                "expected": q,
                "actual": 0,
                "rule": "secondary_mark_missing",
            })

    return findings


def full_framing_review(
    categories: Dict[str, List[Piece]],
    drawings_marks: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """Run complete primary + secondary framing review."""
    inv = build_framing_inventory(categories)
    all_marks = _all_shipper_marks(inv, categories)
    findings = []
    findings.extend(review_primary_framing(inv, drawings_marks, all_shipper_marks=all_marks))
    has_primary = sum(v["count"] for v in inv.get("primary", {}).values()) > 0
    findings.extend(review_secondary_framing(
        inv, has_primary=has_primary, drawings_marks=drawings_marks, all_shipper_marks=all_marks,
    ))
    return findings
