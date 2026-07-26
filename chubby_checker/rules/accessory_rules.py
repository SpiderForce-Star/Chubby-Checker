"""
Accessory rules for Chubby-Checker:
  - Panel closers (inside / outside / foam / metal)
  - Pop rivets for trim
  - Trim presence & length sanity
  - Gutter requirements
  - Downspout requirements

Calibrated on real Ascent shipper patterns (CL426 Metal Inside Clsr, etc.).
"""

from typing import Dict, Any, List, Optional
import re

# ---------------------------------------------------------------------------
# Closure detection patterns
# ---------------------------------------------------------------------------
CLOSURE_PATTERNS = {
    "metal_inside": [
        r"metal\s+inside\s+cl", r"inside\s+closure", r"cl426", r"inside\s+clsr",
    ],
    "metal_outside": [
        r"metal\s+outside\s+cl", r"outside\s+closure", r"outside\s+clsr",
    ],
    "foam_inside": [
        r"foam\s+inside", r"inside\s+foam", r"foam\s+closure",
    ],
    "foam_outside": [
        r"foam\s+outside", r"outside\s+foam",
    ],
    "universal_closure": [
        r"universal\s+closure", r"univ\.?\s+cl",
    ],
    "generic_closure": [
        r"\bclosure\b", r"\bclsr\b", r"\bcloser\b",
    ],
}

# Pop rivet / blind rivet patterns
RIVET_PATTERNS = [
    r"pop\s+rivet", r"blind\s+rivet", r"fu13", r"fu15",
    r"1/8\".*rivet", r"3/16\".*rivet", r"rivet",
]

# Trim related
TRIM_KEYWORDS = [
    "trim", "eave", "rake", "corner", "base", "jamb", "header",
    "gutter", "downspout", "down spout", "scupper", "flashing",
    "ridge", "valley", "transition",
]

GUTTER_PATTERNS = [
    r"\bgutter\b", r"eave\s+gutter", r"box\s+gutter", r"gen4",
]

DOWNSPOUT_PATTERNS = [
    r"down\s*spout", r"downspout", r"ds-?\d", r"leader",
]


def _count_matches(text: str, patterns: List[str]) -> int:
    total = 0
    for pat in patterns:
        total += len(re.findall(pat, text, re.IGNORECASE))
    return total


def extract_closure_counts(categories: Dict[str, list], raw_text: str = "") -> Dict[str, int]:
    """
    Scan shipper categories and optional raw text for closure pieces.
    Returns counts by closure type.
    """
    counts = {k: 0 for k in CLOSURE_PATTERNS}
    counts["total"] = 0

    # From structured pieces
    for cat, pieces in categories.items():
        for p in pieces:
            desc = f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')} {cat}".lower()
            matched = False
            for ctype, pats in CLOSURE_PATTERNS.items():
                for pat in pats:
                    if re.search(pat, desc, re.IGNORECASE):
                        counts[ctype] += getattr(p, "quantity", 1)
                        counts["total"] += getattr(p, "quantity", 1)
                        matched = True
                        break
                if matched:
                    break

    # Fallback text scan (less precise)
    if raw_text and counts["total"] == 0:
        for ctype, pats in CLOSURE_PATTERNS.items():
            for pat in pats:
                for m in re.finditer(rf"(\d+)\s+.*?(?:{pat})", raw_text, re.IGNORECASE):
                    try:
                        counts[ctype] += int(m.group(1))
                        counts["total"] += int(m.group(1))
                    except ValueError:
                        pass

    return counts


def extract_rivet_count(categories: Dict[str, list], raw_text: str = "") -> int:
    """Return total pop/blind rivet quantity found."""
    total = 0
    for cat, pieces in categories.items():
        for p in pieces:
            desc = f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')} {cat}".lower()
            for pat in RIVET_PATTERNS:
                if re.search(pat, desc, re.IGNORECASE):
                    total += getattr(p, "quantity", 1)
                    break

    if total == 0 and raw_text:
        for pat in RIVET_PATTERNS:
            for m in re.finditer(rf"(\d+)\s+.*?(?:{pat})", raw_text, re.IGNORECASE):
                try:
                    total += int(m.group(1))
                except ValueError:
                    pass
    return total


def extract_trim_info(categories: Dict[str, list]) -> Dict[str, Any]:
    """Summarize trim-related pieces (count + total length if available)."""
    trim_pieces = []
    total_length_ft = 0.0

    for cat, pieces in categories.items():
        cat_lower = cat.lower()
        is_trim_cat = any(k in cat_lower for k in ["trim", "gutter", "downspout", "flashing"])
        for p in pieces:
            desc = f"{getattr(p, 'description', '')} {cat}".lower()
            if is_trim_cat or any(k in desc for k in TRIM_KEYWORDS):
                trim_pieces.append(p)
                # Best-effort length sum
                if getattr(p, "length_inches", None):
                    total_length_ft += (p.length_inches / 12.0) * getattr(p, "quantity", 1)
                elif getattr(p, "length", None):
                    # leave as-is; parser may not have normalized
                    pass

    return {
        "count": sum(getattr(p, "quantity", 1) for p in trim_pieces),
        "unique_marks": len({getattr(p, "mark", "") for p in trim_pieces}),
        "total_length_ft": round(total_length_ft, 1) if total_length_ft else None,
        "pieces": trim_pieces,
    }


def extract_gutter_downspout(categories: Dict[str, list], raw_text: str = "") -> Dict[str, Any]:
    """Detect gutter and downspout presence + rough counts."""
    gutter_qty = 0
    downspout_qty = 0

    for cat, pieces in categories.items():
        for p in pieces:
            desc = f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')} {cat}".lower()
            if any(re.search(pat, desc, re.IGNORECASE) for pat in GUTTER_PATTERNS):
                gutter_qty += getattr(p, "quantity", 1)
            if any(re.search(pat, desc, re.IGNORECASE) for pat in DOWNSPOUT_PATTERNS):
                downspout_qty += getattr(p, "quantity", 1)

    # Text fallback
    if raw_text:
        if gutter_qty == 0:
            for pat in GUTTER_PATTERNS:
                for m in re.finditer(rf"(\d+)\s+.*?(?:{pat})", raw_text, re.IGNORECASE):
                    try:
                        gutter_qty += int(m.group(1))
                    except ValueError:
                        pass
        if downspout_qty == 0:
            for pat in DOWNSPOUT_PATTERNS:
                for m in re.finditer(rf"(\d+)\s+.*?(?:{pat})", raw_text, re.IGNORECASE):
                    try:
                        downspout_qty += int(m.group(1))
                    except ValueError:
                        pass

    return {
        "gutter_qty": gutter_qty,
        "downspout_qty": downspout_qty,
        "has_gutter": gutter_qty > 0,
        "has_downspout": downspout_qty > 0,
    }


def check_closures_present(
    closure_counts: Dict[str, int],
    has_panels: bool,
    panel_count: int = 0,
) -> List[Dict[str, Any]]:
    """Return list of findings related to closures."""
    findings = []
    total = closure_counts.get("total", 0)

    if has_panels and total == 0:
        findings.append({
            "severity": "WARNING",
            "category": "Closures",
            "message": "Panels are present but no closures (inside/outside/foam/metal) were detected in the shipper.",
            "rule": "closures_present",
        })
    elif total > 0:
        findings.append({
            "severity": "INFO",
            "category": "Closures",
            "message": (
                f"Closures found: total {total} "
                f"(metal inside: {closure_counts.get('metal_inside', 0)}, "
                f"metal outside: {closure_counts.get('metal_outside', 0)}, "
                f"foam: {closure_counts.get('foam_inside', 0) + closure_counts.get('foam_outside', 0)})"
            ),
            "rule": "closures_present",
        })

    return findings


def check_rivets_for_trim(rivet_count: int, trim_count: int) -> List[Dict[str, Any]]:
    """Sanity-check pop rivet quantity against trim."""
    findings = []
    if trim_count > 0 and rivet_count == 0:
        findings.append({
            "severity": "WARNING",
            "category": "Pop Rivets",
            "message": f"Trim pieces present ({trim_count}) but no pop/blind rivets detected.",
            "expected": ">0",
            "actual": 0,
            "rule": "rivets_for_trim",
        })
    elif trim_count > 0 and rivet_count > 0:
        # Very rough: often dozens to thousands of rivets depending on trim complexity
        findings.append({
            "severity": "INFO",
            "category": "Pop Rivets",
            "message": f"Pop/blind rivets found: {rivet_count:,} (trim pieces: {trim_count}).",
            "actual": rivet_count,
            "rule": "rivets_for_trim",
        })
    return findings


def check_gutter_downspout(
    gd: Dict[str, Any],
    has_roof_panels: bool,
    building_has_eave: bool = True,
) -> List[Dict[str, Any]]:
    """Flag missing gutter / downspout when roof panels exist."""
    findings = []

    if has_roof_panels and building_has_eave:
        if not gd.get("has_gutter"):
            findings.append({
                "severity": "WARNING",
                "category": "Gutter",
                "message": "Roof panels present but no gutter material detected in shipper.",
                "rule": "gutter_present",
            })
        else:
            findings.append({
                "severity": "INFO",
                "category": "Gutter",
                "message": f"Gutter pieces detected: {gd.get('gutter_qty', 0)}.",
                "actual": gd.get("gutter_qty"),
                "rule": "gutter_present",
            })

        if not gd.get("has_downspout"):
            findings.append({
                "severity": "WARNING",
                "category": "Downspout",
                "message": "Roof panels present but no downspout material detected in shipper.",
                "rule": "downspout_present",
            })
        else:
            findings.append({
                "severity": "INFO",
                "category": "Downspout",
                "message": f"Downspout pieces detected: {gd.get('downspout_qty', 0)}.",
                "actual": gd.get("downspout_qty"),
                "rule": "downspout_present",
            })

    return findings
