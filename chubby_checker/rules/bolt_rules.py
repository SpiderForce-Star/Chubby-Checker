"""
Bolt quantity rules for main frames and secondary framing.

1. Extract bolt / nut / washer lines from shipper categories.
2. Parse drawing callouts like (8) 3/4\" A325.
3. Compare shipper totals to drawing callouts and optional connection-library estimates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from chubby_checker.rules.bolt_library import (
    estimate_primary_bolts,
    estimate_secondary_bolts,
    load_connection_library,
)

# (12) 3/4" Ø A325   or   8 - 3/4" A325 x 2-1/2"
CALLOUT_RE = re.compile(
    r"[\(\[]?\s*(\d{1,3})\s*[\)\]]?\s*[–\-x×]?\s*"
    r"(\d(?:\.\d+)?|\d/\d)\s*[\"″]?\s*(?:Ø|DIA|DIAMETER)?\s*"
    r"(?:×|x)?\s*(?:\d(?:\.\d+)?(?:\s*-\s*\d+/\d+)?)?\s*[\"″]?\s*"
    r"(A\s*325|A\s*490|A\s*307|F\s*1852)?",
    re.IGNORECASE,
)

BOLT_LINE_RE = re.compile(
    r"(bolt|a325|a490|a307|hsbolt|machine\s*bolt|structural\s*bolt)",
    re.IGNORECASE,
)
NUT_RE = re.compile(r"\bnut\b", re.IGNORECASE)
WASHER_RE = re.compile(r"\bwasher\b|f436|harden", re.IGNORECASE)


@dataclass
class BoltLine:
    quantity: int
    diameter_in: Optional[float]
    grade: Optional[str]
    description: str
    kind: str  # bolt | nut | washer | other


def _parse_fraction(token: str) -> Optional[float]:
    token = token.strip().replace('"', "").replace("″", "")
    if not token:
        return None
    if "/" in token:
        try:
            a, b = token.split("/", 1)
            return float(a) / float(b)
        except ValueError:
            return None
    try:
        return float(token)
    except ValueError:
        return None


def extract_bolts_from_shipper(categories: Dict[str, list]) -> Dict[str, Any]:
    """Sum bolt/nut/washer quantities from shipper piece lists."""
    lines: List[BoltLine] = []
    bolts = nuts = washers = 0

    for cat, pieces in (categories or {}).items():
        cat_l = cat.lower()
        is_bolt_cat = any(k in cat_l for k in ("bolt", "nut", "washer"))
        for p in pieces:
            desc = f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')} {cat}"
            q = int(getattr(p, "quantity", 0) or 0)
            if q <= 0:
                continue
            if BOLT_LINE_RE.search(desc) or (is_bolt_cat and "nut" not in desc.lower() and "washer" not in desc.lower()):
                dia = None
                grade = None
                m = CALLOUT_RE.search(desc)
                if m:
                    dia = _parse_fraction(m.group(2))
                    grade = (m.group(3) or "").replace(" ", "").upper() or None
                lines.append(BoltLine(q, dia, grade, desc.strip(), "bolt"))
                bolts += q
            elif NUT_RE.search(desc) or (is_bolt_cat and "nut" in desc.lower()):
                lines.append(BoltLine(q, None, None, desc.strip(), "nut"))
                nuts += q
            elif WASHER_RE.search(desc) or (is_bolt_cat and "washer" in desc.lower()):
                lines.append(BoltLine(q, None, None, desc.strip(), "washer"))
                washers += q

    return {
        "bolt_qty": bolts,
        "nut_qty": nuts,
        "washer_qty": washers,
        "lines": lines,
        "has_bolts": bolts > 0,
    }


def extract_bolt_callouts_from_text(text: str) -> List[Dict[str, Any]]:
    """Parse drawing/shipper text for explicit bolt callouts."""
    if not text:
        return []
    found = []
    for m in CALLOUT_RE.finditer(text):
        qty = int(m.group(1))
        dia = _parse_fraction(m.group(2))
        grade = (m.group(3) or "").replace(" ", "").upper() or None
        if qty <= 0 or qty > 500:
            continue
        found.append({"quantity": qty, "diameter_in": dia, "grade": grade, "raw": m.group(0)})
    return found


def check_bolts(
    categories: Dict[str, list],
    drawings_text: str = "",
    connection_counts: Optional[Dict[str, int]] = None,
    require_bolts_if_framing: bool = True,
) -> List[Dict[str, Any]]:
    """
    Produce bolt discrepancy findings.

    connection_counts keys (optional):
      knees, ridges, rafter_splices, column_splices, endwall_frames,
      purlin_clips, purlin_laps, girt_clips, eave_strut_connections, flange_braces
    """
    findings: List[Dict[str, Any]] = []
    extracted = extract_bolts_from_shipper(categories)
    shipper_bolts = extracted["bolt_qty"]
    shipper_nuts = extracted["nut_qty"]
    shipper_washers = extracted["washer_qty"]

    # Framing present?
    cat_keys = " ".join((categories or {}).keys()).lower()
    has_framing = any(
        k in cat_keys
        for k in ("fabricated", "cold formed", "hot rolled", "frame", "primary", "secondary")
    )

    if require_bolts_if_framing and has_framing and shipper_bolts == 0:
        findings.append({
            "severity": "CRITICAL",
            "category": "Bolts",
            "message": "Primary/secondary framing categories present but no bolts detected in shipper.",
            "expected": ">0",
            "actual": 0,
            "rule": "bolts_present",
        })
    elif shipper_bolts > 0:
        findings.append({
            "severity": "INFO",
            "category": "Bolts",
            "message": f"Shipper bolt count: {shipper_bolts:,}  | nuts: {shipper_nuts:,}  | washers: {shipper_washers:,}",
            "actual": shipper_bolts,
            "rule": "bolts_extracted",
        })

    # Nuts / washers ratio
    if shipper_bolts > 0:
        if shipper_nuts > 0 and shipper_nuts < int(shipper_bolts * 0.85):
            findings.append({
                "severity": "WARNING",
                "category": "Bolts",
                "message": f"Nut quantity ({shipper_nuts}) is low relative to bolts ({shipper_bolts}).",
                "expected": f"~{shipper_bolts}",
                "actual": shipper_nuts,
                "rule": "nuts_vs_bolts",
            })
        if shipper_washers > 0 and shipper_washers < int(shipper_bolts * 0.5):
            findings.append({
                "severity": "INFO",
                "category": "Bolts",
                "message": f"Washer quantity ({shipper_washers}) is low vs bolts ({shipper_bolts}) — confirm if washers are required.",
                "expected": f"~{shipper_bolts}",
                "actual": shipper_washers,
                "rule": "washers_vs_bolts",
            })

    # Drawing callouts sum
    callouts = extract_bolt_callouts_from_text(drawings_text or "")
    if callouts:
        callout_total = sum(c["quantity"] for c in callouts)
        findings.append({
            "severity": "INFO",
            "category": "Bolts",
            "message": f"Drawing bolt callouts parsed: {len(callouts)} hits, sum qty {callout_total:,}.",
            "actual": callout_total,
            "rule": "bolt_callouts_parsed",
        })
        if shipper_bolts > 0 and callout_total > 0:
            # Callouts are often per-connection, not full building — only flag severe under-ship
            if shipper_bolts < int(callout_total * 0.5):
                findings.append({
                    "severity": "WARNING",
                    "category": "Bolts",
                    "message": (
                        f"Shipper bolts ({shipper_bolts}) are far below summed drawing callouts "
                        f"({callout_total}). Verify multi-connection totals vs single-detail callouts."
                    ),
                    "expected": callout_total,
                    "actual": shipper_bolts,
                    "rule": "bolts_vs_callouts",
                })

    # Connection library estimate when counts provided
    cc = connection_counts or {}
    if cc:
        primary = estimate_primary_bolts(
            num_knees=int(cc.get("knees", 0)),
            num_ridges=int(cc.get("ridges", 0)),
            num_rafter_splices=int(cc.get("rafter_splices", 0)),
            num_column_splices=int(cc.get("column_splices", 0)),
            num_endwall_frames=int(cc.get("endwall_frames", 0)),
        )
        secondary = estimate_secondary_bolts(
            num_purlin_clips=int(cc.get("purlin_clips", 0)),
            num_purlin_laps=int(cc.get("purlin_laps", 0)),
            num_girt_clips=int(cc.get("girt_clips", 0)),
            num_eave_strut_connections=int(cc.get("eave_strut_connections", 0)),
            num_flange_braces=int(cc.get("flange_braces", 0)),
        )
        expected = primary["total_bolts"] + secondary["total_bolts"]
        if expected > 0:
            findings.append({
                "severity": "INFO",
                "category": "Bolts",
                "message": (
                    f"Connection-library estimate: {expected:,} bolts "
                    f"(primary {primary['total_bolts']}, secondary {secondary['total_bolts']})."
                ),
                "expected": expected,
                "actual": shipper_bolts,
                "rule": "bolt_library_estimate",
            })
            if shipper_bolts > 0 and shipper_bolts < int(expected * 0.85):
                findings.append({
                    "severity": "CRITICAL",
                    "category": "Bolts",
                    "message": (
                        f"Shipper bolts ({shipper_bolts}) below 85% of connection-library estimate "
                        f"({expected}). Possible short ship on framing bolts."
                    ),
                    "expected": expected,
                    "actual": shipper_bolts,
                    "rule": "bolts_vs_library",
                })
            elif shipper_bolts > int(expected * 1.35):
                findings.append({
                    "severity": "INFO",
                    "category": "Bolts",
                    "message": (
                        f"Shipper bolts ({shipper_bolts}) exceed library estimate ({expected}). "
                        f"May include extras, erection bolts, or non-standard connections."
                    ),
                    "expected": expected,
                    "actual": shipper_bolts,
                    "rule": "bolts_vs_library",
                })

    return findings
