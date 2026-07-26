"""
Accessory rules for Chubby-Checker:
  - Panel closers (inside / outside / foam / metal)
  - Pop rivets for trim
  - Trim presence & length sanity
  - Gutter & downspout requirements + length formulas
  - Thermal block verification (strengthened)
"""

from typing import Dict, Any, List, Optional
import re

from chubby_checker.rules.geometry_formulas import (
    BuildingGeometry,
    all_trim_expectations,
    compare_length,
    expected_gutter_length,
    expected_downspout_count,
)

# ---------------------------------------------------------------------------
# Closure / rivet / trim patterns (unchanged core)
# ---------------------------------------------------------------------------
CLOSURE_PATTERNS = {
    "metal_inside": [r"metal\s+inside\s+cl", r"inside\s+closure", r"cl426", r"inside\s+clsr"],
    "metal_outside": [r"metal\s+outside\s+cl", r"outside\s+closure", r"outside\s+clsr"],
    "foam_inside": [r"foam\s+inside", r"inside\s+foam", r"foam\s+closure"],
    "foam_outside": [r"foam\s+outside", r"outside\s+foam"],
    "universal_closure": [r"universal\s+closure", r"univ\.?\s+cl"],
    "generic_closure": [r"\bclosure\b", r"\bclsr\b", r"\bcloser\b"],
}

RIVET_PATTERNS = [
    r"pop\s+rivet", r"blind\s+rivet", r"fu13", r"fu15",
    r"1/8\".*rivet", r"3/16\".*rivet", r"rivet",
]

TRIM_KEYWORDS = [
    "trim", "eave", "rake", "corner", "base", "jamb", "header",
    "gutter", "downspout", "down spout", "scupper", "flashing",
    "ridge", "valley", "transition",
]

GUTTER_PATTERNS = [r"\bgutter\b", r"eave\s+gutter", r"box\s+gutter", r"gen4"]
DOWNSPOUT_PATTERNS = [r"down\s*spout", r"downspout", r"ds-?\d", r"leader"]


def extract_closure_counts(categories: Dict[str, list], raw_text: str = "") -> Dict[str, int]:
    counts = {k: 0 for k in CLOSURE_PATTERNS}
    counts["total"] = 0
    for cat, pieces in categories.items():
        for p in pieces:
            desc = f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')} {cat}".lower()
            matched = False
            for ctype, pats in CLOSURE_PATTERNS.items():
                for pat in pats:
                    if re.search(pat, desc, re.IGNORECASE):
                        q = getattr(p, "quantity", 1)
                        counts[ctype] += q
                        counts["total"] += q
                        matched = True
                        break
                if matched:
                    break
    return counts


def extract_rivet_count(categories: Dict[str, list], raw_text: str = "") -> int:
    total = 0
    for cat, pieces in categories.items():
        for p in pieces:
            desc = f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')} {cat}".lower()
            for pat in RIVET_PATTERNS:
                if re.search(pat, desc, re.IGNORECASE):
                    total += getattr(p, "quantity", 1)
                    break
    return total


def extract_trim_info(categories: Dict[str, list]) -> Dict[str, Any]:
    trim_pieces = []
    total_length_ft = 0.0
    by_type: Dict[str, float] = {}

    for cat, pieces in categories.items():
        cat_lower = cat.lower()
        is_trim_cat = any(k in cat_lower for k in ["trim", "gutter", "downspout", "flashing"])
        for p in pieces:
            desc = f"{getattr(p, 'description', '')} {cat}".lower()
            mark = getattr(p, "mark", "") or ""
            if not (is_trim_cat or any(k in desc for k in TRIM_KEYWORDS)):
                continue
            trim_pieces.append(p)
            length_ft = None
            if getattr(p, "length_inches", None):
                length_ft = (p.length_inches / 12.0) * getattr(p, "quantity", 1)
                total_length_ft += length_ft

            # Classify for formula comparison
            key = "other_trim"
            if any(x in desc or x in mark.lower() for x in ["gutter"]):
                key = "gutter"
            elif any(x in desc for x in ["downspout", "down spout"]):
                key = "downspout"
            elif "eave" in desc:
                key = "eave_trim"
            elif "rake" in desc:
                key = "rake_trim"
            elif "corner" in desc:
                key = "corner_trim"
            elif "base" in desc:
                key = "base_trim"
            elif "ridge" in desc:
                key = "ridge_trim"

            if length_ft:
                by_type[key] = by_type.get(key, 0.0) + length_ft

    return {
        "count": sum(getattr(p, "quantity", 1) for p in trim_pieces),
        "unique_marks": len({getattr(p, "mark", "") for p in trim_pieces}),
        "total_length_ft": round(total_length_ft, 1) if total_length_ft else None,
        "length_by_type": {k: round(v, 1) for k, v in by_type.items()},
        "pieces": trim_pieces,
    }


def extract_gutter_downspout(categories: Dict[str, list], raw_text: str = "") -> Dict[str, Any]:
    gutter_qty = 0
    downspout_qty = 0
    gutter_length_ft = 0.0

    for cat, pieces in categories.items():
        for p in pieces:
            desc = f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')} {cat}".lower()
            q = getattr(p, "quantity", 1)
            if any(re.search(pat, desc, re.IGNORECASE) for pat in GUTTER_PATTERNS):
                gutter_qty += q
                if getattr(p, "length_inches", None):
                    gutter_length_ft += (p.length_inches / 12.0) * q
            if any(re.search(pat, desc, re.IGNORECASE) for pat in DOWNSPOUT_PATTERNS):
                downspout_qty += q

    return {
        "gutter_qty": gutter_qty,
        "gutter_length_ft": round(gutter_length_ft, 1) if gutter_length_ft else None,
        "downspout_qty": downspout_qty,
        "has_gutter": gutter_qty > 0,
        "has_downspout": downspout_qty > 0,
    }


def check_closures_present(closure_counts: Dict[str, int], has_panels: bool, panel_count: int = 0) -> List[Dict[str, Any]]:
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
    geo: Optional[BuildingGeometry] = None,
) -> List[Dict[str, Any]]:
    findings = []

    if has_roof_panels:
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
                "message": f"Gutter pieces detected: {gd.get('gutter_qty', 0)}"
                           + (f", length ≈ {gd['gutter_length_ft']} ft" if gd.get("gutter_length_ft") else ""),
                "actual": gd.get("gutter_qty"),
                "rule": "gutter_present",
            })

            # Length formula check when geometry is available
            if geo and gd.get("gutter_length_ft"):
                exp = expected_gutter_length(geo)
                cmp = compare_length(exp["expected_ft"], gd["gutter_length_ft"])
                if cmp["status"] == "mismatch":
                    findings.append({
                        "severity": "WARNING",
                        "category": "Gutter Length",
                        "message": (
                            f"Gutter length {gd['gutter_length_ft']} ft differs from expected "
                            f"{exp['expected_ft']} ft ({exp['formula']}). Δ {cmp['delta_ft']} ft"
                        ),
                        "expected": exp["expected_ft"],
                        "actual": gd["gutter_length_ft"],
                        "rule": "gutter_length_formula",
                    })
                else:
                    findings.append({
                        "severity": "INFO",
                        "category": "Gutter Length",
                        "message": f"Gutter length ≈ {gd['gutter_length_ft']} ft is consistent with building eave length ({exp['expected_ft']} ft).",
                        "rule": "gutter_length_formula",
                    })

        if not gd.get("has_downspout"):
            findings.append({
                "severity": "WARNING",
                "category": "Downspout",
                "message": "Roof panels present but no downspout material detected in shipper.",
                "rule": "downspout_present",
            })
        else:
            msg = f"Downspout pieces detected: {gd.get('downspout_qty', 0)}."
            if geo:
                exp_ds = expected_downspout_count(geo)
                msg += f" Rule-of-thumb expectation ≈ {exp_ds['expected_count']} (spacing ~40 ft)."
            findings.append({
                "severity": "INFO",
                "category": "Downspout",
                "message": msg,
                "actual": gd.get("downspout_qty"),
                "rule": "downspout_present",
            })

    return findings


def check_trim_lengths_against_geometry(
    trim_info: Dict[str, Any],
    geo: Optional[BuildingGeometry],
) -> List[Dict[str, Any]]:
    """Compare extracted trim lengths to geometry formulas."""
    findings = []
    if not geo:
        return findings

    expectations = all_trim_expectations(geo)
    by_type = trim_info.get("length_by_type", {})

    for key, exp in expectations.items():
        if key == "downspout":
            continue  # count-based, handled elsewhere
        actual = by_type.get(key)
        expected_ft = exp.get("expected_ft")
        if actual is None or expected_ft is None:
            continue
        cmp = compare_length(expected_ft, actual)
        if cmp["status"] == "mismatch":
            findings.append({
                "severity": "WARNING",
                "category": "Trim Length",
                "message": (
                    f"{exp['item']} length {actual} ft vs expected {expected_ft} ft "
                    f"({exp.get('formula', '')}). Δ {cmp['delta_ft']} ft"
                ),
                "expected": expected_ft,
                "actual": actual,
                "rule": "trim_length_formula",
            })
        else:
            findings.append({
                "severity": "INFO",
                "category": "Trim Length",
                "message": f"{exp['item']} length ≈ {actual} ft matches geometry expectation ({expected_ft} ft).",
                "rule": "trim_length_formula",
            })

    return findings


def check_thermal_blocks(
    clips: int,
    thermal_blocks: int,
    has_insulation: bool = True,
    strict: bool = True,
) -> List[Dict[str, Any]]:
    """
    Strengthened thermal block verification.

    Rules:
    - If sliding clips exist and insulation is expected, thermal blocks should be ~1:1 with clips.
    - Ratio < 0.85 → WARNING (possible missing blocks)
    - Ratio > 1.20 → INFO (extras / different system)
    - Zero blocks with clips + insulation → WARNING / CRITICAL
    """
    findings = []
    if clips <= 0:
        return findings

    if thermal_blocks == 0 and has_insulation:
        findings.append({
            "severity": "WARNING" if not strict else "CRITICAL",
            "category": "Thermal Blocks",
            "message": f"{clips} sliding clips present but zero thermal blocks found. Expected ~1:1 when insulation is used.",
            "expected": clips,
            "actual": 0,
            "rule": "thermal_block_verification",
        })
        return findings

    if thermal_blocks == 0:
        return findings

    ratio = thermal_blocks / clips
    if ratio < 0.85:
        findings.append({
            "severity": "WARNING",
            "category": "Thermal Blocks",
            "message": (
                f"Thermal blocks ({thermal_blocks}) significantly below sliding clips ({clips}). "
                f"Ratio {ratio:.2f} (expected ~1.0)."
            ),
            "expected": f"~{clips}",
            "actual": thermal_blocks,
            "rule": "thermal_block_verification",
        })
    elif ratio > 1.20:
        findings.append({
            "severity": "INFO",
            "category": "Thermal Blocks",
            "message": (
                f"Thermal blocks ({thermal_blocks}) exceed clips ({clips}). "
                f"Ratio {ratio:.2f} – may include extras or alternate system."
            ),
            "expected": f"~{clips}",
            "actual": thermal_blocks,
            "rule": "thermal_block_verification",
        })
    else:
        findings.append({
            "severity": "INFO",
            "category": "Thermal Blocks",
            "message": f"Thermal block count ({thermal_blocks}) is consistent with sliding clips ({clips}). Ratio {ratio:.2f}.",
            "rule": "thermal_block_verification",
        })

    return findings
