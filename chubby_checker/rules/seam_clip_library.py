"""
Standing Seam (seamed panel) clip library for Ascent Shipper Checker.

Maps panel coverage / system names to clip types, part numbers, fasteners
per clip, thermal block pairing, and backup plate widths.

Calibrated from Ascent shipper parts (CSP212, CS2124, CL7760, CL7769, CL575,
FSS10, CL7616, CL7720) and MBCI-style Double-Lok / SuperLok / LokSeam practice:
  - Minimum 2 fasteners per clip
  - Thermal spacer/block with insulated systems
  - Backup plate width matches panel coverage at endlaps
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
import json
import os
import re


@dataclass(frozen=True)
class SeamClipSpec:
    key: str
    name: str
    motion: str  # sliding | fixed | floating | utility
    height: str  # low | high | hi-thermal | standard
    panel_coverage_in: Tuple[int, ...]  # compatible panel widths
    systems: Tuple[str, ...]  # e.g. ascent_vs16, double_lok, superlok
    part_numbers: Tuple[str, ...]  # shipper / vendor marks
    aliases: Tuple[str, ...]  # description keywords
    screws_per_clip: int = 2
    requires_thermal_block: bool = True
    thermal_block_parts: Tuple[str, ...] = ("CL575",)
    backup_plate_width_in: Optional[int] = None  # preferred plate width for this coverage
    notes: str = ""


# ---------------------------------------------------------------------------
# Default library — Ascent primary + MBCI-aligned aliases
# ---------------------------------------------------------------------------
SEAM_CLIP_DEFAULTS: Dict[str, SeamClipSpec] = {
    # Ascent / common PEMB sliding clips
    "ascent_sliding_2in": SeamClipSpec(
        key="ascent_sliding_2in",
        name="2\" High Sliding Clip",
        motion="sliding",
        height="standard",
        panel_coverage_in=(12, 16, 18, 24),
        systems=("ascent_ss", "vs16", "vs18", "vs24"),
        part_numbers=("CSP212", "CS2124", "CSP-212", "CS-2124"),
        aliases=(
            "sliding clip", "2\" high sliding", "2 in sliding", "panel clip sliding",
        ),
        screws_per_clip=2,
        requires_thermal_block=True,
        thermal_block_parts=("CL575", "CL-575"),
        backup_plate_width_in=None,  # depends on panel
        notes="Primary Ascent sliding clip extracted on jobs 25-13266 / 25-13059 / 25-13168",
    ),
    "ascent_hi_thermal_sliding": SeamClipSpec(
        key="ascent_hi_thermal_sliding",
        name="Hi-Thermal Sliding Clip",
        motion="sliding",
        height="hi-thermal",
        panel_coverage_in=(12, 16, 18, 24),
        systems=("ascent_ss", "double_lok"),
        part_numbers=("HW-2129", "HW2129"),
        aliases=("hi-thermal", "hi thermal sliding", "2\" standoff sliding"),
        screws_per_clip=2,
        requires_thermal_block=True,
        notes="MBCI-style hi-thermal sliding (taller standoff for thick insulation)",
    ),
    # MBCI Double-Lok family (reference)
    "doublelok_2in_sliding_low": SeamClipSpec(
        key="doublelok_2in_sliding_low",
        name="Double-Lok 2\" Sliding Clip Low",
        motion="sliding",
        height="low",
        panel_coverage_in=(24,),
        systems=("double_lok", "doublelok"),
        part_numbers=("HW-2122", "HW2122"),
        aliases=("double-lok", "doublelok", "2\" sliding low"),
        screws_per_clip=2,
        requires_thermal_block=True,
        backup_plate_width_in=24,
        notes="MBCI Double-Lok low 2\" sliding; 2 fasteners/clip",
    ),
    "doublelok_2in_sliding_high": SeamClipSpec(
        key="doublelok_2in_sliding_high",
        name="Double-Lok 2\" Sliding Clip High",
        motion="sliding",
        height="high",
        panel_coverage_in=(24,),
        systems=("double_lok", "doublelok"),
        part_numbers=("HW-2124", "HW2124"),
        aliases=("double-lok high", "2\" sliding high"),
        screws_per_clip=2,
        requires_thermal_block=True,
        backup_plate_width_in=24,
    ),
    "doublelok_4in_sliding_low": SeamClipSpec(
        key="doublelok_4in_sliding_low",
        name="Double-Lok 4\" Sliding Clip Low",
        motion="sliding",
        height="low",
        panel_coverage_in=(24,),
        systems=("double_lok",),
        part_numbers=("HW-2126", "HW2126"),
        aliases=("4\" sliding", "4 in sliding clip"),
        screws_per_clip=2,
        requires_thermal_block=True,
        backup_plate_width_in=24,
        notes="2\" movement each direction; Double-Lok",
    ),
    # SuperLok / BattenLok-style fixed/floating
    "superlok_low_fixed": SeamClipSpec(
        key="superlok_low_fixed",
        name="SuperLok Low Fixed Clip",
        motion="fixed",
        height="low",
        panel_coverage_in=(12, 16, 18),
        systems=("superlok", "battenlok"),
        part_numbers=("HW-236", "HW236", "HW-226", "HW226"),
        aliases=("low fixed", "fixed clip low", "superlok fixed"),
        screws_per_clip=2,
        requires_thermal_block=False,
        notes="Fixed clip — limited building width before floating required",
    ),
    "superlok_high_fixed": SeamClipSpec(
        key="superlok_high_fixed",
        name="SuperLok High Fixed Clip",
        motion="fixed",
        height="high",
        panel_coverage_in=(12, 16, 18),
        systems=("superlok", "battenlok"),
        part_numbers=("HW-234", "HW234", "HW-224", "HW224"),
        aliases=("high fixed", "fixed clip high"),
        screws_per_clip=2,
        requires_thermal_block=True,
    ),
    "superlok_low_floating": SeamClipSpec(
        key="superlok_low_floating",
        name="SuperLok Low Floating Clip",
        motion="floating",
        height="low",
        panel_coverage_in=(12, 16, 18),
        systems=("superlok", "battenlok"),
        part_numbers=("HW-230", "HW230", "HW-220", "HW220"),
        aliases=("low floating", "floating clip low"),
        screws_per_clip=2,
        requires_thermal_block=False,
    ),
    "superlok_high_floating": SeamClipSpec(
        key="superlok_high_floating",
        name="SuperLok High Floating Clip",
        motion="floating",
        height="high",
        panel_coverage_in=(12, 16, 18),
        systems=("superlok", "battenlok"),
        part_numbers=("HW-232", "HW232", "HW-222", "HW222"),
        aliases=("high floating", "floating clip high"),
        screws_per_clip=2,
        requires_thermal_block=True,
    ),
    # LokSeam
    "lokseam_ul90": SeamClipSpec(
        key="lokseam_ul90",
        name="LokSeam UL 90 Clip",
        motion="fixed",
        height="standard",
        panel_coverage_in=(12, 16, 18),
        systems=("lokseam",),
        part_numbers=("LOKSEAM",),
        aliases=("lokseam clip", "lok seam clip", "ul 90 clip"),
        screws_per_clip=2,
        requires_thermal_block=False,
        notes="Often 2 screws/clip; spacing per UL construction",
    ),
}

# Backup plate catalog (Ascent)
BACKUP_PLATE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "24": {
        "width_in": 24,
        "part_numbers": ("CL7760", "CL-7760"),
        "aliases": ("24\" back up", "24\" backup", "24 in backup plate"),
    },
    "18": {
        "width_in": 18,
        "part_numbers": ("CL7769", "CL-7769"),
        "aliases": ("18\" back up", "18\" backup", "18 in backup plate"),
    },
    "16": {
        "width_in": 16,
        "part_numbers": (),
        "aliases": ("16\" back up", "16\" backup"),
    },
    "12": {
        "width_in": 12,
        "part_numbers": (),
        "aliases": ("12\" back up", "12\" backup"),
    },
}

THERMAL_BLOCK_DEFAULTS = {
    "part_numbers": ("CL575", "CL-575"),
    "aliases": ("thermal block", "1\" thermal", "thermal spacer"),
    "ratio_to_clips": 1.0,
}

CLIP_SCREW_DEFAULTS = {
    "part_numbers": ("FSS10", "FSS-10"),
    "aliases": ("panel clip screw", "clip screw"),
    "min_per_clip": 2,
}

HI_EAVE_RAKE = {
    "hi_eave_plates": {"part_numbers": ("CL7616",), "aliases": ("hi-eave", "hi eave plate")},
    "hi_rake_supports": {"part_numbers": ("CL7720",), "aliases": ("hi-rake", "hi rake support")},
}


def load_seam_clip_library() -> Dict[str, SeamClipSpec]:
    """Return clip library, optionally overridden by ASCENT_SEAM_CLIP_LIBRARY JSON."""
    lib = dict(SEAM_CLIP_DEFAULTS)
    raw = os.environ.get("ASCENT_SEAM_CLIP_LIBRARY")
    if not raw:
        return lib
    try:
        data = json.loads(raw)
        for key, vals in data.items():
            base = lib.get(key)
            lib[key] = SeamClipSpec(
                key=key,
                name=str(vals.get("name", base.name if base else key)),
                motion=str(vals.get("motion", base.motion if base else "sliding")),
                height=str(vals.get("height", base.height if base else "standard")),
                panel_coverage_in=tuple(vals.get("panel_coverage_in", base.panel_coverage_in if base else (24,))),
                systems=tuple(vals.get("systems", base.systems if base else ())),
                part_numbers=tuple(vals.get("part_numbers", base.part_numbers if base else ())),
                aliases=tuple(vals.get("aliases", base.aliases if base else ())),
                screws_per_clip=int(vals.get("screws_per_clip", base.screws_per_clip if base else 2)),
                requires_thermal_block=bool(
                    vals.get("requires_thermal_block", base.requires_thermal_block if base else True)
                ),
                thermal_block_parts=tuple(
                    vals.get("thermal_block_parts", base.thermal_block_parts if base else ("CL575",))
                ),
                backup_plate_width_in=vals.get(
                    "backup_plate_width_in",
                    base.backup_plate_width_in if base else None,
                ),
                notes=str(vals.get("notes", base.notes if base else "")),
            )
    except Exception:
        pass
    return lib


def library_as_dict() -> Dict[str, Any]:
    return {k: asdict(v) for k, v in load_seam_clip_library().items()}


def identify_clip_from_text(text: str) -> Optional[SeamClipSpec]:
    """Match first library clip by part number or alias in text."""
    if not text:
        return None
    t = text.upper()
    lib = load_seam_clip_library()
    # Prefer part-number hits
    for spec in lib.values():
        for pn in spec.part_numbers:
            if pn.upper().replace("-", "") in t.replace("-", ""):
                return spec
    t_lower = text.lower()
    for spec in lib.values():
        for alias in spec.aliases:
            if alias.lower() in t_lower:
                return spec
    return None


def clips_for_coverage(coverage_in: int) -> List[SeamClipSpec]:
    """All clip specs that support a given panel coverage width."""
    return [
        s for s in load_seam_clip_library().values()
        if coverage_in in s.panel_coverage_in
    ]


def default_clip_for_coverage(coverage_in: int) -> SeamClipSpec:
    """
    Prefer Ascent sliding clip for general PEMB work; else first matching spec.
    """
    lib = load_seam_clip_library()
    ascent = lib.get("ascent_sliding_2in")
    if ascent and coverage_in in ascent.panel_coverage_in:
        return ascent
    matches = clips_for_coverage(coverage_in)
    return matches[0] if matches else ascent or next(iter(lib.values()))


def screws_required(clip_count: int, clip_spec: Optional[SeamClipSpec] = None) -> int:
    per = clip_spec.screws_per_clip if clip_spec else CLIP_SCREW_DEFAULTS["min_per_clip"]
    return int(clip_count) * int(per)


def backup_plate_for_coverage(coverage_in: int) -> Dict[str, Any]:
    """Return backup plate catalog entry for panel width (exact or nearest common)."""
    key = str(int(coverage_in))
    if key in BACKUP_PLATE_DEFAULTS:
        return {"coverage_in": int(coverage_in), **BACKUP_PLATE_DEFAULTS[key]}
    # nearest of 12/16/18/24
    options = sorted(int(k) for k in BACKUP_PLATE_DEFAULTS)
    nearest = min(options, key=lambda w: abs(w - coverage_in))
    return {"coverage_in": nearest, **BACKUP_PLATE_DEFAULTS[str(nearest)], "matched_nearest": True}


def match_accessories_in_text(text: str) -> Dict[str, Any]:
    """
    Scan free text for known clip / plate / thermal / screw part numbers.
    Returns counts of distinct part hits (not quantities).
    """
    if not text:
        return {}
    t = text.upper().replace("-", "")
    hits: Dict[str, List[str]] = {"clips": [], "backup_plates": [], "thermal": [], "screws": [], "other": []}
    for spec in load_seam_clip_library().values():
        for pn in spec.part_numbers:
            if pn.upper().replace("-", "") in t:
                hits["clips"].append(pn)
    for width, info in BACKUP_PLATE_DEFAULTS.items():
        for pn in info.get("part_numbers", ()):
            if pn.upper().replace("-", "") in t:
                hits["backup_plates"].append(pn)
    for pn in THERMAL_BLOCK_DEFAULTS["part_numbers"]:
        if pn.upper().replace("-", "") in t:
            hits["thermal"].append(pn)
    for pn in CLIP_SCREW_DEFAULTS["part_numbers"]:
        if pn.upper().replace("-", "") in t:
            hits["screws"].append(pn)
    for group, info in HI_EAVE_RAKE.items():
        for pn in info["part_numbers"]:
            if pn.upper().replace("-", "") in t:
                hits["other"].append(pn)
    return hits


def system_requirements(
    panel_coverage_in: int,
    clip_count: int,
    has_insulation: bool = True,
    clip_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full accessory requirement package for a detected / assumed clip system.
    """
    lib = load_seam_clip_library()
    spec = lib.get(clip_key) if clip_key else None
    if spec is None:
        spec = default_clip_for_coverage(panel_coverage_in)

    screws = screws_required(clip_count, spec)
    need_thermal = has_insulation or spec.requires_thermal_block
    thermal = clip_count if need_thermal else 0
    plate = backup_plate_for_coverage(
        spec.backup_plate_width_in or panel_coverage_in
    )

    return {
        "clip_spec": asdict(spec),
        "clip_count": clip_count,
        "expected_clip_screws": screws,
        "screws_per_clip": spec.screws_per_clip,
        "expected_thermal_blocks": thermal,
        "requires_thermal_block": need_thermal,
        "backup_plate": plate,
        "notes": spec.notes,
    }
