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
# Closure / rivet / trim patterns
# ---------------------------------------------------------------------------
# Domain rules:
#   - Standing seam panels  → metal closures required
#   - Exposed fastener      → foam closures required (R-Loc/PBR, PBA, 7.2, PBM, etc.)
# Metal exceptions (suppress):
#   - B-deck / structural deck only (NMBS)
#   - IMP / Kingspan systems
#
# Part-number accuracy:
#   - CL426 / HW-4xx / SPED16 / SPRAKEZ6 → metal (standing seam family)
#   - RLCLOUTG / RLCLINGL / RLCLIN / RLCLOUT → FOAM (R-Loc screw-down), NOT metal
# ---------------------------------------------------------------------------

CLOSURE_PATTERNS = {
    "metal_inside": [
        r"metal\s+inside\s+cl",
        r"metal\s+inside\s+closure",
        r"metal\s+inside",
        r"\bcl426\b",
        r"\bhw-?426\b",
        r"\bcl430\b",
        r"\bhw-?430\b",
        r"\bcl\s*426\b",
    ],
    "metal_outside": [
        r"metal\s+outside\s+cl",
        r"metal\s+outside\s+closure",
        r"metal\s+outside",
        r"\bhw-?410\b",
        r"\bhw-?412\b",
        r"\bhw-?422\b",
        r"\bhw-?432\b",
    ],
    "foam_inside": [
        r"foam\s+inside",
        r"inside\s+foam",
        r"foam\s+inside\s+closure",
        r"foam\s+cl(?:osure|sr)?",
        r"\bfoam\s+closure\b",
        # R-Loc / PBR foam inside part numbers (NOT metal)
        r"\brlclingl\b",
        r"\brlclin\b",
        r"\brlcl-?in(?:side)?\b",
    ],
    "foam_outside": [
        r"foam\s+outside",
        r"outside\s+foam",
        r"foam\s+outside\s+closure",
        # R-Loc / PBR foam outside part numbers (NOT metal)
        r"\brlcloutg\b",
        r"\brlclout\b",
        r"\brlcl-?out(?:side)?\b",
    ],
    "end_dam": [
        r"\bsped16\b",
        r"\bend\s*dam\b",
        r"\benddam\b",
    ],
    "z_bird_stop": [
        r"\bsprakez6\b",
        r"\bfl-?361\b",
        r"bird\s*stop",
        r"\bz[-\s]?closure\b",
        r"\bz[-\s]?stop\b",
    ],
    "universal_closure": [
        r"universal\s+closure",
        r"univ\.?\s+cl",
    ],
    "generic_closure": [
        r"\bclosure\b",
        r"\bclsr\b",
        r"\bcloser\b",
    ],
}

STANDING_SEAM_KEYWORDS = [
    "standing seam", "central-loc", "central loc", "central seam",
    "central-snap", "central snap", "central-span", "central span",
    "double lok", "double-lok", "doublelok", "ultra-dek", "ultradek",
    "vsr", "vsr6", "ssr", "mechanical seam", "snap seam",
    "mcelroy", "mc elroy", "superlok", "super lok", "battenlok", "batten lok",
    "18\" standing", "18 in standing", "18-inch standing",
]

EXPOSED_FASTENER_KEYWORDS = [
    "r-loc", "rloc", "rlocrev", "rlr", "rlx", "pbr", "rpbr",
    "m-loc", "mloc", "mlr", "panel-loc", "panel loc",
    "pba", "pbm", "7.2", "seven point two",
    "avp", "avp wall", "rloc reverse", "r-loc reverse", "rev r-loc", "rev rloc",
    "exposed fastener", "screw down", "screw-down", "through fastened",
]

CONCEALED_WALL_KEYWORDS = [
    "shadow rib", "shadowrib", "fw-120", "fw120", "fw 120",
    "masterline", "master line", "masterline-16", "ml16",
]

LINER_KEYWORDS = [
    "pl121", "pl-121", "pl 121", "liner panel", "interior liner", "wall liner",
]

BDECK_KEYWORDS = [
    "b-deck", "b deck", "bdeck", "n-deck", "structural deck",
    "new millennium", "nmbs", "roof deck", "1.5\" deck", "1-1/2\" deck",
]

IMP_KEYWORDS = [
    "kingspan", "imp", "insulated metal panel", "insulated panel",
    "awip", "metl-span", "metlspan", "nucor panel",
]

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
    """
    Count closures by type.

    Foam takes priority when description mentions foam (never count
    "foam inside closure" as metal). R-Loc foam SKUs (RLCLOUTG/RLCLINGL)
    classify as foam, not metal.
    """
    counts = {k: 0 for k in CLOSURE_PATTERNS}
    counts["total"] = 0
    counts["metal_total"] = 0
    counts["foam_total"] = 0

    priority = [
        "foam_inside", "foam_outside",
        "end_dam", "z_bird_stop",
        "metal_inside", "metal_outside",
        "universal_closure", "generic_closure",
    ]
    ordered = [(k, CLOSURE_PATTERNS[k]) for k in priority if k in CLOSURE_PATTERNS]
    ordered += [(k, v) for k, v in CLOSURE_PATTERNS.items() if k not in priority]

    def _tally(desc: str, qty: int = 1) -> None:
        mentions_foam = "foam" in desc
        for ctype, pats in ordered:
            if mentions_foam and ctype.startswith("metal_"):
                continue
            for pat in pats:
                if re.search(pat, desc, re.IGNORECASE):
                    q = qty or 1
                    counts[ctype] += q
                    counts["total"] += q
                    if ctype.startswith("metal_") or ctype in ("end_dam", "z_bird_stop"):
                        counts["metal_total"] += q
                    if ctype.startswith("foam_"):
                        counts["foam_total"] += q
                    return

    for cat, pieces in (categories or {}).items():
        for p in pieces:
            desc = f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')} {cat}".lower()
            _tally(desc, getattr(p, "quantity", 1) or 1)

    # Free-text fallback: only when tables yielded nothing for that family
    if raw_text and counts["total"] == 0:
        blob = raw_text.lower()
        # Count 1 synthetic hit per matching family to unlock presence rules
        for ctype, pats in ordered:
            for pat in pats:
                if re.search(pat, blob, re.IGNORECASE):
                    counts[ctype] += 1
                    counts["total"] += 1
                    if ctype.startswith("metal_") or ctype in ("end_dam", "z_bird_stop"):
                        counts["metal_total"] += 1
                    if ctype.startswith("foam_"):
                        counts["foam_total"] += 1
                    break
    return counts


def detect_panel_families(
    categories: Dict[str, list],
    raw_text: str = "",
    panel_keys: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Detect panel families and closure requirement/suppress flags.

    Metal required: standing seam + certain concealed walls (Shadow Rib / FW-120 / MasterLine).
    Foam required: exposed-fastener / screw-down (R-Loc/PBR, AVP, PBA, 7.2, PBM, RLR, …).
    Suppress metal: pure B-deck/NMBS structural deck, IMP/Kingspan (no SS metal closures).
    """
    blob_parts = [raw_text or ""]
    for cat, pieces in (categories or {}).items():
        blob_parts.append(str(cat))
        for p in pieces:
            blob_parts.append(f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')}")
    if panel_keys:
        blob_parts.extend(str(k) for k in panel_keys)
    blob = " ".join(blob_parts).lower()

    # Prefer explicit names; short MBS codes only with panel/roof context
    has_ss = any(k in blob for k in STANDING_SEAM_KEYWORDS)
    if not has_ss and re.search(r"\b(csx|clx|vsr6|ssr|s6)\b", blob, re.IGNORECASE):
        has_ss = True
    if not has_ss and re.search(r"\b(cs|cl)\b", blob, re.IGNORECASE) and any(
        k in blob for k in ("panel", "roof", "standing", "seam", "central", "sheeting")
    ):
        has_ss = True

    has_exposed = any(k in blob for k in EXPOSED_FASTENER_KEYWORDS) or bool(
        re.search(r"\b(rl|rlr|rlx|pbr|rpbr|pba|pbm|avp)\b", blob, re.IGNORECASE)
    )

    has_concealed_metal_wall = any(k in blob for k in CONCEALED_WALL_KEYWORDS)
    has_pl121 = any(k in blob for k in ("pl121", "pl-121", "pl 121"))
    has_liner = has_pl121 or any(k in blob for k in LINER_KEYWORDS)
    has_double_lok = any(k in blob for k in ("double lok", "double-lok", "doublelok"))
    has_vsr6 = any(k in blob for k in ("vsr6", "vsr 6", "central-span", "central span")) or bool(
        re.search(r"\bvsr\b", blob)
    )
    has_central_loc = any(
        k in blob for k in ("central-loc", "central loc", "central-seam", "central seam")
    ) or bool(re.search(r"\b(clx|csx)\b", blob)) or (
        bool(re.search(r"\b(cl|cs)\b", blob))
        and any(k in blob for k in ("panel", "roof", "standing", "seam", "central"))
    )
    has_avp = "avp" in blob
    has_shadow_rib = any(k in blob for k in ("shadow rib", "shadowrib"))
    has_masterline = any(k in blob for k in ("masterline", "master line", "masterline-16", "ml16"))
    has_fw120 = any(k in blob for k in ("fw-120", "fw120", "fw 120"))
    has_mcelroy = any(k in blob for k in ("mcelroy", "mc elroy", "superlok", "battenlok"))
    has_rlr = any(k in blob for k in ("rlr", "rloc reverse", "r-loc reverse", "rlocrev", "rpbr", "rev r-loc"))
    has_pba = "pba" in blob
    has_pbm = "pbm" in blob
    has_72 = "7.2" in blob or "seven point two" in blob
    has_18_ss = bool(re.search(r"\b18\s*[\"']?\s*(standing|ss|seam|coverage)\b", blob)) or (
        has_ss and "18\"" in blob
    )

    is_bdeck = any(k in blob for k in BDECK_KEYWORDS if k not in ("deck",)) or bool(
        re.search(r"\b(b-?deck|n-?deck|structural\s+deck|new\s+millennium|nmbs)\b", blob)
    )
    # Avoid bare "imp" matching inside unrelated words (e.g. "simple")
    is_imp = any(k in blob for k in IMP_KEYWORDS if k != "imp") or bool(
        re.search(r"\bimps?\b", blob)
    )

    # B-deck-only: structural deck without SS / metal-wall systems that need metal closures
    is_bdeck_only_context = is_bdeck and not has_ss and not has_concealed_metal_wall
    # IMP context: suppress metal SS closures unless a true SS roof is also present
    is_imp_context = is_imp and not has_ss

    suppress_metal = bool(is_bdeck_only_context or is_imp_context)
    metal_required = (has_ss or has_concealed_metal_wall) and not suppress_metal
    # Foam for screw-down; not for pure B-deck / pure IMP without exposed panels
    foam_required = has_exposed and not (is_bdeck_only_context and not has_exposed)
    if is_imp_context and not has_exposed:
        foam_required = False

    return {
        "standing_seam": has_ss,
        "exposed_fastener": has_exposed,
        "concealed_metal_wall": has_concealed_metal_wall,
        "metal_required": metal_required,
        "foam_required": foam_required,
        "suppress_metal_closures": suppress_metal,
        "suppress_foam_closures": bool(is_bdeck_only_context or (is_imp_context and not has_exposed)),
        "suppress_reason": (
            "b-deck/structural deck" if is_bdeck_only_context
            else "IMP/Kingspan system" if is_imp_context
            else ""
        ),
        "bdeck": is_bdeck,
        "imp": is_imp,
        "double_lok": has_double_lok,
        "vsr6": has_vsr6,
        "central_loc": has_central_loc,
        "avp": has_avp,
        "pl121": has_pl121,
        "liner": has_liner,
        "shadow_rib": has_shadow_rib,
        "masterline": has_masterline,
        "fw120": has_fw120,
        "mcelroy": has_mcelroy,
        "rlr_reverse": has_rlr,
        "pba": has_pba,
        "pbm": has_pbm,
        "panel_7_2": has_72,
        "ss_18in": has_18_ss,
        "any_panel": (
            has_ss or has_exposed or has_concealed_metal_wall
            or has_liner or is_bdeck or is_imp or "panel" in blob
        ),
    }


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


def check_closures_present(
    closure_counts: Dict[str, int],
    has_panels: bool,
    panel_count: int = 0,
    panel_families: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Closure requirements by panel family:
      - Standing seam (+ Shadow Rib / FW-120 / MasterLine) → metal closures required
      - Exposed fastener (R-Loc/PBR, AVP, PBA, 7.2, PBM, RLR, …) → foam required

    Metal-closure EXCEPTIONS (suppress metal CRITICAL):
      - B-deck / structural deck only (NMBS)
      - IMP / Kingspan systems (no SS metal closures)
    """
    findings: List[Dict[str, Any]] = []
    families = panel_families or {}
    has_ss = bool(families.get("standing_seam"))
    has_exposed = bool(families.get("exposed_fastener"))
    has_concealed_metal = bool(families.get("concealed_metal_wall"))
    suppress_metal = bool(families.get("suppress_metal_closures"))
    suppress_foam = bool(families.get("suppress_foam_closures"))
    metal_required = bool(families.get("metal_required", has_ss or has_concealed_metal)) and not suppress_metal
    foam_required = bool(families.get("foam_required", has_exposed)) and not suppress_foam
    suppress_reason = families.get("suppress_reason") or ""

    metal = int(closure_counts.get("metal_total", 0) or 0)
    if metal == 0:
        metal = (
            int(closure_counts.get("metal_inside", 0) or 0)
            + int(closure_counts.get("metal_outside", 0) or 0)
            + int(closure_counts.get("end_dam", 0) or 0)
            + int(closure_counts.get("z_bird_stop", 0) or 0)
        )
    foam = int(closure_counts.get("foam_total", 0) or 0)
    if foam == 0:
        foam = (
            int(closure_counts.get("foam_inside", 0) or 0)
            + int(closure_counts.get("foam_outside", 0) or 0)
        )
    total = int(closure_counts.get("total", 0) or 0)

    if suppress_metal and (
        has_ss or has_concealed_metal
        or "deck" in suppress_reason.lower()
        or "imp" in suppress_reason.lower()
    ):
        findings.append({
            "severity": "INFO",
            "category": "Closures",
            "message": (
                f"Metal closure check suppressed ({suppress_reason or 'exception'}). "
                "B-deck/IMP systems do not use standard standing-seam metal closures."
            ),
            "rule": "closures_metal_exception",
        })

    if metal_required:
        label = "standing seam"
        if has_concealed_metal and not has_ss:
            label = "concealed metal-wall panel (Shadow Rib / FW-120 / MasterLine)"
        elif has_ss and has_concealed_metal:
            label = "standing seam / concealed metal-wall panels"
        if metal == 0:
            findings.append({
                "severity": "CRITICAL",
                "category": "Closures",
                "message": (
                    f"{label.capitalize()} present but no metal closures detected. "
                    "Metal inside/outside closures are required "
                    "(e.g. CL426/CL430, HW-426/HW-430, HW-410/412/422/432, "
                    "end dams SPED16, Z/bird stop SPRAKEZ6/FL-361)."
                ),
                "expected": ">0 metal closures",
                "actual": 0,
                "rule": "closures_metal_standing_seam",
            })
        else:
            findings.append({
                "severity": "INFO",
                "category": "Closures",
                "message": (
                    f"Metal closures found for {label}: {metal} "
                    f"(inside: {closure_counts.get('metal_inside', 0)}, "
                    f"outside: {closure_counts.get('metal_outside', 0)}, "
                    f"end dams: {closure_counts.get('end_dam', 0)}, "
                    f"Z/bird stop: {closure_counts.get('z_bird_stop', 0)})."
                ),
                "actual": metal,
                "rule": "closures_metal_standing_seam",
            })

    if foam_required:
        if foam == 0:
            findings.append({
                "severity": "WARNING",
                "category": "Closures",
                "message": (
                    "Exposed-fastener / screw-down panels present (R-Loc/PBR, RLR, AVP, PBA, "
                    "7.2, PBM, etc.) but no foam closures detected. Foam inside/outside "
                    "closures are required (e.g. RLCLOUTG, RLCLINGL)."
                ),
                "expected": ">0 foam closures",
                "actual": 0,
                "rule": "closures_foam_exposed_fastener",
            })
        else:
            findings.append({
                "severity": "INFO",
                "category": "Closures",
                "message": (
                    f"Foam closures found for exposed-fastener panels: {foam} "
                    f"(inside: {closure_counts.get('foam_inside', 0)}, "
                    f"outside: {closure_counts.get('foam_outside', 0)})."
                ),
                "actual": foam,
                "rule": "closures_foam_exposed_fastener",
            })

    if has_panels and not has_ss and not has_exposed and not has_concealed_metal and total == 0:
        if not suppress_metal and not suppress_foam:
            findings.append({
                "severity": "WARNING",
                "category": "Closures",
                "message": (
                    "Panels are present but no closures were detected. "
                    "Standing seam requires metal closures; screw-down panels require foam closures."
                ),
                "rule": "closures_present",
            })
    elif total > 0 and not has_ss and not has_exposed and not has_concealed_metal:
        findings.append({
            "severity": "INFO",
            "category": "Closures",
            "message": (
                f"Closures found: total {total} "
                f"(metal: {metal}, foam: {foam}, "
                f"Z/bird stop: {closure_counts.get('z_bird_stop', 0)})."
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
    findings = []
    if not geo:
        return findings

    expectations = all_trim_expectations(geo)
    by_type = trim_info.get("length_by_type", {})

    for key, exp in expectations.items():
        if key == "downspout":
            continue
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
