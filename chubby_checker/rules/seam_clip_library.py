"""
Standing Seam clip library — Ascent / Central States calibrated.

Primary sources (Base Camp technical manuals):
  - Ascent Central Seam Plus Technical Manual (CL2122/CL2124, CL7760/CL7769,
    CL7600/CL7616, CL7710/CL7720, CL7500; 2 fasteners/clip FSS1 or FT1)
  - Ascent Central-Loc Technical Manual (CL2102/CL2104, CL200/CL204, CL208)
  - Ascent Central Span Technical Manual (SPLCLIP / SPHCLIP floating)
  - Shipper aliases seen on jobs: CSP212, CS2124, FSS10, CL575

Rule: minimum 2 fasteners per clip at each purlin (not typically at eave strut).
Backup plates: CL7760 (24\"), CL7769 (18\") at endlaps / ridge.
Thermal spacer required for HIGH clip systems over insulation.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
import json
import os
import re


@dataclass(frozen=True)
class SeamClipSpec:
    key: str
    name: str
    motion: str  # sliding | fixed | floating | utility
    height: str  # low | high | utility
    panel_systems: Tuple[str, ...]  # central_seam_plus | central_loc | central_span | ascent_generic
    panel_coverage_in: Tuple[int, ...]
    part_numbers: Tuple[str, ...]
    aliases: Tuple[str, ...]
    screws_per_clip: int = 2
    fastener_purlin: str = "FSS1"
    fastener_joist: str = "FT1"
    requires_thermal_spacer: bool = False  # high systems over insulation
    standoff_in: Optional[float] = None
    max_movement_each_way_in: Optional[float] = None
    notes: str = ""


SEAM_CLIP_DEFAULTS: Dict[str, SeamClipSpec] = {
    # ----- Central Seam Plus (mechanically seamed) -----
    "csp_sliding_low": SeamClipSpec(
        key="csp_sliding_low",
        name="Central Seam Plus 2\" Sliding Clip Low",
        motion="sliding",
        height="low",
        panel_systems=("central_seam_plus", "cs", "csx"),
        panel_coverage_in=(18, 24),
        part_numbers=("CL2122", "CSP212", "CS2122"),
        aliases=("2\" sliding clip low", "sliding clip low", "2 in sliding low"),
        screws_per_clip=2,
        fastener_purlin="FSS1",
        fastener_joist="FT1",
        requires_thermal_spacer=False,
        standoff_in=None,
        max_movement_each_way_in=1.0,
        notes="Ascent CSP manual p.7/26; floating max 1\" each direction",
    ),
    "csp_sliding_high": SeamClipSpec(
        key="csp_sliding_high",
        name="Central Seam Plus 2\" Sliding Clip High",
        motion="sliding",
        height="high",
        panel_systems=("central_seam_plus", "cs", "csx"),
        panel_coverage_in=(18, 24),
        part_numbers=("CL2124", "CS2124", "CSP2124"),
        aliases=("2\" sliding clip high", "sliding clip high", "2 in sliding high"),
        screws_per_clip=2,
        fastener_purlin="FSS1",
        fastener_joist="FT1",
        requires_thermal_spacer=True,
        max_movement_each_way_in=1.0,
        notes="High system — thermal spacer over insulation (manual Step 3)",
    ),
    # ----- Central-Loc (snap) -----
    "cloc_sliding_low": SeamClipSpec(
        key="cloc_sliding_low",
        name="Central-Loc 2\" Sliding Clip Low",
        motion="sliding",
        height="low",
        panel_systems=("central_loc", "cl", "clx"),
        panel_coverage_in=(18, 24),
        part_numbers=("CL2102",),
        aliases=("central-loc sliding low", "cloc sliding low"),
        screws_per_clip=2,
        requires_thermal_spacer=False,
        max_movement_each_way_in=1.0,
    ),
    "cloc_sliding_high": SeamClipSpec(
        key="cloc_sliding_high",
        name="Central-Loc 2\" Sliding Clip High",
        motion="sliding",
        height="high",
        panel_systems=("central_loc", "cl", "clx"),
        panel_coverage_in=(18, 24),
        part_numbers=("CL2104",),
        aliases=("central-loc sliding high", "cloc sliding high"),
        screws_per_clip=2,
        requires_thermal_spacer=True,
        max_movement_each_way_in=1.0,
    ),
    "cloc_fixed_low": SeamClipSpec(
        key="cloc_fixed_low",
        name="Central-Loc Fixed Clip Low",
        motion="fixed",
        height="low",
        panel_systems=("central_loc",),
        panel_coverage_in=(18, 24),
        part_numbers=("CL200",),
        aliases=("fixed clip low", "cloc fixed low"),
        screws_per_clip=2,
        requires_thermal_spacer=False,
    ),
    "cloc_fixed_high": SeamClipSpec(
        key="cloc_fixed_high",
        name="Central-Loc Fixed Clip High",
        motion="fixed",
        height="high",
        panel_systems=("central_loc",),
        panel_coverage_in=(18, 24),
        part_numbers=("CL204",),
        aliases=("fixed clip high", "cloc fixed high"),
        screws_per_clip=2,
        requires_thermal_spacer=True,
    ),
    "cloc_utility": SeamClipSpec(
        key="cloc_utility",
        name="Central-Loc Utility Clip",
        motion="utility",
        height="utility",
        panel_systems=("central_loc",),
        panel_coverage_in=(18, 24),
        part_numbers=("CL208",),
        aliases=("utility clip", "solid deck clip"),
        screws_per_clip=2,
        requires_thermal_spacer=False,
        notes="No 3/8\" insulation clearance; solid deck applications",
    ),
    # ----- Central Span -----
    "cspan_float_low": SeamClipSpec(
        key="cspan_float_low",
        name="Central Span Low Floating Clip",
        motion="floating",
        height="low",
        panel_systems=("central_span", "vsr6", "vs16"),
        panel_coverage_in=(16,),
        part_numbers=("SPLCLIP", "SPL-CLIP"),
        aliases=("low floating", "splclip", "3/8 standoff"),
        screws_per_clip=2,
        standoff_in=0.375,
        requires_thermal_spacer=False,
        notes="Stand-off 3/8\"; 2 clip fasteners per clip (Central Span manual)",
    ),
    "cspan_float_high": SeamClipSpec(
        key="cspan_float_high",
        name="Central Span High Floating Clip",
        motion="floating",
        height="high",
        panel_systems=("central_span", "vsr6", "vs16"),
        panel_coverage_in=(16,),
        part_numbers=("SPHCLIP", "SPH-CLIP"),
        aliases=("high floating", "sphclip", "1-3/8 standoff"),
        screws_per_clip=2,
        standoff_in=1.375,
        requires_thermal_spacer=True,
        notes="Stand-off 1-3/8\"; thermal for high systems",
    ),
    # ----- Generic / shipper-seen fallback (older or alternate marks) -----
    "ascent_sliding_generic": SeamClipSpec(
        key="ascent_sliding_generic",
        name="Ascent / Shipper Sliding Clip (generic)",
        motion="sliding",
        height="standard",
        panel_systems=("ascent_generic", "central_seam_plus", "central_loc"),
        panel_coverage_in=(12, 16, 18, 24),
        part_numbers=("CSP212", "CS2124", "CSP-212"),
        aliases=("sliding clip", "2\" high sliding clip", "panel clip sliding"),
        screws_per_clip=2,
        notes="Matches shipper extraction patterns on jobs 25-13266 / 25-13059 / 25-13168",
    ),
}

BACKUP_PLATE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "24": {
        "width_in": 24,
        "part_numbers": ("CL7760", "CL-7760"),
        "aliases": ("24\" back up", "24\" backup", "24 in backup plate"),
        "systems": ("central_seam_plus", "central_loc"),
    },
    "18": {
        "width_in": 18,
        "part_numbers": ("CL7769", "CL-7769"),
        "aliases": ("18\" back up", "18\" backup", "18 in backup plate"),
        "systems": ("central_seam_plus", "central_loc"),
    },
}

EAVE_RAKE_PLATES = {
    "eave_low": {"part_numbers": ("CL7600",), "aliases": ("eave plate low",), "length_ft": 8.0},
    "eave_high": {"part_numbers": ("CL7616",), "aliases": ("hi-eave", "eave plate high", "hi eave plate"), "length_ft": 8.0},
    "rake_low": {"part_numbers": ("CL7710",), "aliases": ("rake support low",), "length_ft": 20.0},
    "rake_high": {"part_numbers": ("CL7720",), "aliases": ("hi-rake", "rake support high", "hi rake support"), "length_ft": 20.0},
    "bearing_plate": {"part_numbers": ("CL7500",), "aliases": ("bearing plate", "rigid board"), "notes": "16 ga red oxide; rigid board insulation"},
}

THERMAL_SPACER = {
    "part_numbers": ("CL575", "CL-575"),  # shipper thermal block mark when present
    "aliases": ("thermal block", "thermal spacer", "1\" thermal"),
    "required_for_heights": ("high",),
    "ratio_to_clips": 1.0,
    "notes": "Manual: thermal spacer for HIGH systems only, over each purlin on insulation",
}

CLIP_SCREW_DEFAULTS = {
    "part_numbers": ("FSS1", "FSS10", "FSS-10", "FT1"),
    "aliases": ("panel clip screw", "clip screw", "fss1", "ft1"),
    "min_per_clip": 2,
    "notes": "Purlins FSS1; Joists FT1; always 2 per clip per Ascent manuals",
}


def load_seam_clip_library() -> Dict[str, SeamClipSpec]:
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
                panel_systems=tuple(vals.get("panel_systems", base.panel_systems if base else ())),
                panel_coverage_in=tuple(vals.get("panel_coverage_in", base.panel_coverage_in if base else (24,))),
                part_numbers=tuple(vals.get("part_numbers", base.part_numbers if base else ())),
                aliases=tuple(vals.get("aliases", base.aliases if base else ())),
                screws_per_clip=int(vals.get("screws_per_clip", base.screws_per_clip if base else 2)),
                fastener_purlin=str(vals.get("fastener_purlin", base.fastener_purlin if base else "FSS1")),
                fastener_joist=str(vals.get("fastener_joist", base.fastener_joist if base else "FT1")),
                requires_thermal_spacer=bool(
                    vals.get("requires_thermal_spacer", base.requires_thermal_spacer if base else False)
                ),
                standoff_in=vals.get("standoff_in", base.standoff_in if base else None),
                max_movement_each_way_in=vals.get(
                    "max_movement_each_way_in", base.max_movement_each_way_in if base else None
                ),
                notes=str(vals.get("notes", base.notes if base else "")),
            )
    except Exception:
        pass
    return lib


def library_as_dict() -> Dict[str, Any]:
    return {k: asdict(v) for k, v in load_seam_clip_library().items()}


def identify_clip_from_text(text: str) -> Optional[SeamClipSpec]:
    if not text:
        return None
    t = text.upper().replace("-", "")
    lib = load_seam_clip_library()
    for spec in lib.values():
        for pn in spec.part_numbers:
            if pn.upper().replace("-", "") in t:
                return spec
    t_lower = text.lower()
    for spec in lib.values():
        for alias in spec.aliases:
            if alias.lower() in t_lower:
                return spec
    return None


def clips_for_system(system: str) -> List[SeamClipSpec]:
    s = system.lower()
    return [c for c in load_seam_clip_library().values() if s in c.panel_systems or s in " ".join(c.panel_systems)]


def clips_for_coverage(coverage_in: int) -> List[SeamClipSpec]:
    return [s for s in load_seam_clip_library().values() if coverage_in in s.panel_coverage_in]


def default_clip_for_coverage(coverage_in: int, system: Optional[str] = None) -> SeamClipSpec:
    lib = load_seam_clip_library()
    if system:
        for c in clips_for_system(system):
            if coverage_in in c.panel_coverage_in and c.motion in ("sliding", "floating"):
                return c
    # Prefer generic shipper-seen, then CSP low, then any match
    for key in ("ascent_sliding_generic", "csp_sliding_low", "cloc_sliding_low", "cspan_float_low"):
        c = lib.get(key)
        if c and coverage_in in c.panel_coverage_in:
            return c
    matches = clips_for_coverage(coverage_in)
    return matches[0] if matches else lib["ascent_sliding_generic"]


def screws_required(clip_count: int, clip_spec: Optional[SeamClipSpec] = None) -> int:
    per = clip_spec.screws_per_clip if clip_spec else CLIP_SCREW_DEFAULTS["min_per_clip"]
    return int(clip_count) * int(per)


def backup_plate_for_coverage(coverage_in: int) -> Dict[str, Any]:
    key = str(int(coverage_in))
    if key in BACKUP_PLATE_DEFAULTS:
        return {"coverage_in": int(coverage_in), **BACKUP_PLATE_DEFAULTS[key]}
    options = sorted(int(k) for k in BACKUP_PLATE_DEFAULTS)
    nearest = min(options, key=lambda w: abs(w - coverage_in))
    return {"coverage_in": nearest, **BACKUP_PLATE_DEFAULTS[str(nearest)], "matched_nearest": True}


def system_requirements(
    panel_coverage_in: int,
    clip_count: int,
    has_insulation: bool = True,
    clip_key: Optional[str] = None,
    system: Optional[str] = None,
) -> Dict[str, Any]:
    lib = load_seam_clip_library()
    spec = lib.get(clip_key) if clip_key else None
    if spec is None:
        spec = default_clip_for_coverage(panel_coverage_in, system=system)

    screws = screws_required(clip_count, spec)
    need_thermal = (spec.requires_thermal_spacer and has_insulation) or (
        has_insulation and spec.height == "high"
    )
    thermal = clip_count if need_thermal else 0
    plate = backup_plate_for_coverage(panel_coverage_in)

    return {
        "clip_spec": asdict(spec),
        "clip_count": clip_count,
        "expected_clip_screws": screws,
        "screws_per_clip": spec.screws_per_clip,
        "fastener_purlin": spec.fastener_purlin,
        "fastener_joist": spec.fastener_joist,
        "expected_thermal_blocks": thermal,
        "requires_thermal_spacer": need_thermal,
        "backup_plate": plate,
        "notes": spec.notes,
    }
