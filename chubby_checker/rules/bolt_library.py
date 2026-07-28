"""
Ascent Buildings / PEMB bolt connection library.

Default counts follow MBMA practice and typical metal-building end-plate /
secondary connections. Override via ASCENT_BOLT_LIBRARY JSON or by editing
CONNECTION_DEFAULTS when Ascent publishes official standards.

Primary connections typically use ASTM A325 (or equivalent high-strength).
Secondary often use A307 unless drawings specify otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
import json
import os


@dataclass(frozen=True)
class ConnectionSpec:
    name: str
    family: str  # primary | secondary
    bolts_per_connection: int
    diameter_in: float  # nominal, inches
    grade: str  # A325, A307, A490, etc.
    nuts_per_bolt: int = 1
    washers_per_bolt: int = 1  # hardened / F436 style when specified
    notes: str = ""


# ---------------------------------------------------------------------------
# Default Ascent-oriented library (industry-typical; refine with Ascent data)
# ---------------------------------------------------------------------------
CONNECTION_DEFAULTS: Dict[str, ConnectionSpec] = {
    # Primary moment / frame
    "knee_end_plate": ConnectionSpec(
        "knee_end_plate", "primary", 8, 0.75, "A325",
        notes="Typical multi-row extended/flush end plate at column-rafter knee",
    ),
    "ridge_end_plate": ConnectionSpec(
        "ridge_end_plate", "primary", 8, 0.75, "A325",
        notes="Rafter ridge / peak splice end plate",
    ),
    "rafter_splice": ConnectionSpec(
        "rafter_splice", "primary", 8, 0.75, "A325",
        notes="Interior rafter splice",
    ),
    "column_splice": ConnectionSpec(
        "column_splice", "primary", 6, 0.75, "A325",
        notes="Column splice when used",
    ),
    "endwall_frame": ConnectionSpec(
        "endwall_frame", "primary", 4, 0.75, "A325",
        notes="Endwall rafter/column connection (varies by design)",
    ),
    "base_plate": ConnectionSpec(
        "base_plate", "primary", 4, 0.75, "A325",
        notes="Column base plate to anchor bolts is often by others; field bolts if supplied",
    ),
    # Secondary
    "purlin_clip": ConnectionSpec(
        "purlin_clip", "secondary", 2, 0.5, "A307",
        notes="Purlin-to-rafter clip angle, typically 2 bolts",
    ),
    "purlin_lap": ConnectionSpec(
        "purlin_lap", "secondary", 4, 0.5, "A307",
        notes="2 bolts each end of purlin lap (4 total per lap joint)",
    ),
    "girt_clip": ConnectionSpec(
        "girt_clip", "secondary", 2, 0.5, "A307",
        notes="Girt-to-column clip",
    ),
    "eave_strut": ConnectionSpec(
        "eave_strut", "secondary", 2, 0.5, "A307",
        notes="Eave strut to frame connection",
    ),
    "flange_brace": ConnectionSpec(
        "flange_brace", "secondary", 2, 0.5, "A307",
        notes="Flange brace to purlin/girt and to frame flange",
    ),
    "sag_angle": ConnectionSpec(
        "sag_angle", "secondary", 2, 0.375, "A307",
        notes="Sag angle / bridging connections",
    ),
}


def load_connection_library() -> Dict[str, ConnectionSpec]:
    """
    Return connection library, optionally overridden by env ASCENT_BOLT_LIBRARY
    (JSON object mapping name -> {bolts_per_connection, diameter_in, grade, ...}).
    """
    lib = dict(CONNECTION_DEFAULTS)
    raw = os.environ.get("ASCENT_BOLT_LIBRARY")
    if not raw:
        return lib
    try:
        data = json.loads(raw)
        for name, vals in data.items():
            base = lib.get(name)
            lib[name] = ConnectionSpec(
                name=name,
                family=vals.get("family", base.family if base else "primary"),
                bolts_per_connection=int(vals["bolts_per_connection"]),
                diameter_in=float(vals.get("diameter_in", base.diameter_in if base else 0.75)),
                grade=str(vals.get("grade", base.grade if base else "A325")),
                nuts_per_bolt=int(vals.get("nuts_per_bolt", 1)),
                washers_per_bolt=int(vals.get("washers_per_bolt", 1)),
                notes=str(vals.get("notes", base.notes if base else "")),
            )
    except Exception:
        pass
    return lib


def library_as_dict() -> Dict[str, Any]:
    return {k: asdict(v) for k, v in load_connection_library().items()}


def estimate_primary_bolts(
    num_knees: int = 0,
    num_ridges: int = 0,
    num_rafter_splices: int = 0,
    num_column_splices: int = 0,
    num_endwall_frames: int = 0,
) -> Dict[str, Any]:
    """Sum expected primary bolts from connection counts."""
    lib = load_connection_library()
    total = 0
    detail = {}
    mapping = [
        ("knee_end_plate", num_knees),
        ("ridge_end_plate", num_ridges),
        ("rafter_splice", num_rafter_splices),
        ("column_splice", num_column_splices),
        ("endwall_frame", num_endwall_frames),
    ]
    for key, n in mapping:
        if n <= 0:
            continue
        spec = lib[key]
        qty = n * spec.bolts_per_connection
        detail[key] = {"connections": n, "bolts": qty, "grade": spec.grade, "dia": spec.diameter_in}
        total += qty
    return {"total_bolts": total, "detail": detail, "family": "primary"}


def estimate_secondary_bolts(
    num_purlin_clips: int = 0,
    num_purlin_laps: int = 0,
    num_girt_clips: int = 0,
    num_eave_strut_connections: int = 0,
    num_flange_braces: int = 0,
) -> Dict[str, Any]:
    lib = load_connection_library()
    total = 0
    detail = {}
    mapping = [
        ("purlin_clip", num_purlin_clips),
        ("purlin_lap", num_purlin_laps),
        ("girt_clip", num_girt_clips),
        ("eave_strut", num_eave_strut_connections),
        ("flange_brace", num_flange_braces),
    ]
    for key, n in mapping:
        if n <= 0:
            continue
        spec = lib[key]
        qty = n * spec.bolts_per_connection
        detail[key] = {"connections": n, "bolts": qty, "grade": spec.grade, "dia": spec.diameter_in}
        total += qty
    return {"total_bolts": total, "detail": detail, "family": "secondary"}
