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


def drawings_require_longlife(drawings_text: str = "", shipper_text: str = "") -> bool:
    """True if drawings (or notes) call for Long Life / Longlife / FLL fasteners."""
    blob = f"{drawings_text or ''} {shipper_text or ''}".lower()
    return any(
        k in blob
        for k in (
            "long life", "longlife", "long-life", "fll",
            "long life fastener", "longlife fastener", "long life fss",
            "longlife fss", "coated long life",
        )
    )


def shipper_has_longlife_fasteners(categories: Dict[str, list], raw_text: str = "") -> bool:
    """Evidence of Longlife / FLL finish on shipper fastener lines."""
    bits = [raw_text or ""]
    for cat, pieces in (categories or {}).items():
        bits.append(str(cat))
        for p in pieces:
            bits.append(f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')}")
    blob = " ".join(bits).lower()
    if any(k in blob for k in ("long life", "longlife", "long-life", "fll")):
        return True
    # FLL* part numbers
    if re.search(r"\bfll[\w-]*\b", blob, re.I):
        return True
    return False


def shipper_has_standard_fss(categories: Dict[str, list], raw_text: str = "") -> bool:
    bits = [raw_text or ""]
    for cat, pieces in (categories or {}).items():
        bits.append(str(cat))
        for p in pieces:
            bits.append(f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')}")
    blob = " ".join(bits).upper().replace("-", "")
    # Standard FSS without FLL prefix
    return bool(re.search(r"\bFSS\d", blob)) and "FLL" not in blob


def check_fastener_finish_longlife(
    categories: Dict[str, list],
    drawings_text: str = "",
    shipper_raw_text: str = "",
) -> List[Dict[str, Any]]:
    """
    WARNING when drawings require Longlife fasteners but shipper only shows standard FSS.
    Field failure 25-13168 SO3: lap fasteners not Longlife FSS10.
    """
    findings: List[Dict[str, Any]] = []
    if not drawings_require_longlife(drawings_text, shipper_raw_text):
        return findings
    has_ll = shipper_has_longlife_fasteners(categories, shipper_raw_text)
    has_std = shipper_has_standard_fss(categories, shipper_raw_text) or extract_screw_count_from_shipper(categories) > 0
    if has_ll:
        findings.append({
            "severity": "INFO",
            "category": "Sheeting Fasteners",
            "message": "Drawings call for Longlife fasteners; shipper shows Longlife/FLL evidence.",
            "rule": "fastener_finish_longlife",
        })
        return findings
    if has_std or extract_screw_count_from_shipper(categories) > 0:
        findings.append({
            "severity": "WARNING",
            "category": "Sheeting Fasteners",
            "message": (
                "Drawings require Long Life / Longlife fasteners, but the shipper shows "
                "standard FSS (or no FLL/Longlife marks). Verify lap and structural screws "
                "are Longlife (e.g. Longlife FSS10), not standard finish."
            ),
            "expected": "Longlife / FLL fasteners",
            "actual": "standard FSS or no Longlife evidence",
            "rule": "fastener_finish_longlife",
        })
    return findings


def _parse_insulation_depth_in(text: str) -> Optional[float]:
    """Best-effort insulation thickness (inches) from drawings/shipper text."""
    if not text:
        return None
    t = text.lower()
    # 6" insulation, 6 in insulation, R-19 (~6")
    m = re.search(r"(\d+(?:\.\d+)?)\s*[\"″']?\s*(?:in(?:ch(?:es)?)?)?\s*insulat", t)
    if m:
        return float(m.group(1))
    m = re.search(r"insulat[^\n]{0,40}?(\d+(?:\.\d+)?)\s*[\"″']", t)
    if m:
        return float(m.group(1))
    # R-19 / R19 common metal building → ~6"
    m = re.search(r"\br\s*[- ]?\s*(13|19|25|30)\b", t)
    if m:
        rmap = {"13": 3.5, "19": 6.0, "25": 8.0, "30": 9.0}
        return rmap.get(m.group(1))
    return None


def _shipper_screw_lengths_in(categories: Dict[str, list], raw_text: str = "") -> List[float]:
    """Extract mentioned screw lengths in inches from shipper lines."""
    lengths: List[float] = []
    bits = [raw_text or ""]
    for cat, pieces in (categories or {}).items():
        for p in pieces:
            bits.append(f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')}")
    blob = " ".join(bits)
    for m in re.finditer(
        r"(\d+(?:\.\d+)?)\s*[\"″]\s*(?:long\s+)?(?:self[-\s]?drill|screw|fastener|fss|tek)?",
        blob,
        re.I,
    ):
        try:
            val = float(m.group(1))
            if 0.5 <= val <= 8.0:
                lengths.append(val)
        except ValueError:
            pass
    # Patterns like 1-1/2" or 2-1/2"
    for m in re.finditer(r"(\d+)\s*-\s*(\d+)/(\d+)\s*[\"″]", blob):
        try:
            val = float(m.group(1)) + float(m.group(2)) / float(m.group(3))
            if 0.5 <= val <= 8.0:
                lengths.append(val)
        except ValueError:
            pass
    return lengths


def check_fastener_length_vs_insulation(
    categories: Dict[str, list],
    drawings_text: str = "",
    shipper_raw_text: str = "",
) -> List[Dict[str, Any]]:
    """
    Soft WARNING when insulation depth implies longer screws but only short ones appear.
    rule: fastener_length_vs_insulation
    """
    findings: List[Dict[str, Any]] = []
    blob = f"{drawings_text or ''}\n{shipper_raw_text or ''}"
    depth = _parse_insulation_depth_in(blob)
    if not depth or depth < 3.0:
        return findings
    if extract_screw_count_from_shipper(categories) <= 0:
        return findings
    lengths = _shipper_screw_lengths_in(categories, shipper_raw_text)
    if not lengths:
        return findings  # no length callouts — skip (prefer INFO/skip over false CRITICAL)
    max_len = max(lengths)
    # Heuristic: insulation ≥6" expects ≥2" screws commonly
    expected_min = 2.0 if depth >= 5.5 else 1.5
    if max_len + 0.01 < expected_min:
        findings.append({
            "severity": "WARNING",
            "category": "Sheeting Fasteners",
            "message": (
                f"Insulation depth ≈ {depth}\" is indicated, but the longest listed "
                f"screw is {max_len}\". Longer fasteners (≈{expected_min}\"+) are typically "
                "required through insulation — verify screw lengths."
            ),
            "expected": f">={expected_min}\"",
            "actual": f"{max_len}\"",
            "rule": "fastener_length_vs_insulation",
        })
    return findings


def check_sheeting_fasteners(
    categories: Dict[str, list],
    panel_key: Optional[str] = None,
    area_width_ft: Optional[float] = None,
    slope_length_ft: Optional[float] = None,
    support_lines: Optional[int] = None,
    eave_endlap_lines: int = 2,
    is_roof: bool = True,
    drawings_text: str = "",
    shipper_raw_text: str = "",
) -> List[Dict[str, Any]]:
    """
    Compare shipper screw totals to MBCI-style expected bands when geometry is known.
    Always reports extracted screw totals when present.
    """
    findings: List[Dict[str, Any]] = []
    actual = extract_screw_count_from_shipper(categories)
    key = panel_key or detect_panel_key_from_categories(categories)
    raw = shipper_raw_text or ""

    if actual > 0:
        findings.append({
            "severity": "INFO",
            "category": "Sheeting Fasteners",
            "message": f"Exposed/sheeting fasteners extracted from shipper: {actual:,}"
                       + (f" (panel type hint: {key})" if key else ""),
            "actual": actual,
            "rule": "sheeting_screws_extracted",
        })

    findings.extend(check_fastener_finish_longlife(categories, drawings_text, raw))
    findings.extend(check_fastener_length_vs_insulation(categories, drawings_text, raw))

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
