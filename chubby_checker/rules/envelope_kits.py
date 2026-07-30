"""
Envelope accessory kit completeness for final drawings vs original shipper.

Covers standing-seam kits, sealant/tape, gutter straps, liner/insulation members,
flange-brace clips, ridge/peak, purlin-extension caps, and pancake SDS.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _blob(categories: Optional[Dict[str, list]] = None, raw_text: str = "") -> str:
    parts = [raw_text or ""]
    for cat, pieces in (categories or {}).items():
        parts.append(str(cat))
        for p in pieces:
            parts.append(f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')}")
    return " ".join(parts)


def _qty(categories: Optional[Dict[str, list]], patterns: tuple) -> int:
    total = 0
    for cat, pieces in (categories or {}).items():
        for p in pieces:
            desc = f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')} {cat}"
            if any(re.search(pat, desc, re.I) for pat in patterns):
                total += int(getattr(p, "quantity", 0) or 0)
    return total


def _has(blob: str, *needles: str) -> bool:
    b = (blob or "").lower()
    return any(n.lower() in b for n in needles)


# ---------------------------------------------------------------------------
# P0-4 Standing seam accessory kit
# ---------------------------------------------------------------------------

def check_ss_accessory_kit_incomplete(
    categories: Optional[Dict[str, list]] = None,
    ss_accessories: Optional[Dict[str, int]] = None,
    drawings_text: str = "",
    shipper_raw_text: str = "",
    panel_families: Optional[Dict[str, Any]] = None,
    has_insulation: bool = False,
    clip_height: str = "",
) -> List[Dict[str, Any]]:
    """
    Standing seam on drawings/shipper → full kit on original shipper.
    rule: ss_accessory_kit_incomplete
    """
    findings: List[Dict[str, Any]] = []
    fam = panel_families or {}
    acc = ss_accessories or {}
    ship = _blob(categories, shipper_raw_text)
    draw = drawings_text or ""
    combined = f"{ship}\n{draw}".lower()

    ss = bool(
        fam.get("standing_seam")
        or _has(combined, "standing seam", "central-loc", "central seam", "double lok", "vsr", "ssr")
        or int(acc.get("sliding_clips", 0) or 0) > 0
    )
    if not ss:
        return findings

    clips = int(acc.get("sliding_clips", 0) or 0)
    eave = (
        int(acc.get("hi_eave_plates", 0) or 0)
        + int(acc.get("eave_plates_low", 0) or 0)
        or _qty(categories, (r"cl7600", r"cl7616", r"eave\s*plate"))
    )
    rake = (
        int(acc.get("hi_rake_supports", 0) or 0)
        + int(acc.get("rake_supports_low", 0) or 0)
        or _qty(categories, (r"cl7710", r"cl7720", r"rake\s*support"))
    )
    thermal = int(acc.get("thermal_blocks", 0) or 0)
    backup = (
        int(acc.get("backup_plates_24", 0) or 0)
        + int(acc.get("backup_plates_18", 0) or 0)
    )
    metal_clos = _qty(
        categories,
        (r"cl426", r"cl430", r"hw-?4", r"metal\s+(inside|outside)", r"sped16", r"metal\s+closure"),
    )
    sealant = _qty(
        categories,
        (r"sealant", r"butyl", r"tri-?bead", r"mastic", r"tape", r"tube\s+seal"),
    ) or (1 if _has(ship, "sealant", "butyl", "tri-bead", "mastic") else 0)

    missing: List[str] = []
    if clips == 0:
        missing.append("sliding/floating clips")
    if eave == 0:
        missing.append("eave plates (CL7600/CL7616)")
    if rake == 0:
        missing.append("rake supports (CL7710/CL7720)")
    need_thermal = has_insulation or (clip_height or "").lower() == "high"
    if need_thermal and thermal == 0:
        missing.append("thermal blocks/spacers")
    if backup == 0 and _has(combined, "endlap", "end lap", "ridge"):
        missing.append("backup plates")
    if metal_clos == 0:
        missing.append("metal closures")
    if sealant == 0:
        missing.append("sealant/tape")

    if not missing:
        findings.append({
            "severity": "INFO",
            "category": "Standing Seam",
            "message": (
                "Standing seam accessory kit appears present "
                f"(clips={clips}, eave={eave}, rake={rake}, thermal={thermal}, "
                f"backup={backup}, metal_clos={metal_clos}, sealant={'yes' if sealant else 'no'})."
            ),
            "rule": "ss_accessory_kit_incomplete",
        })
        return findings

    findings.append({
        "severity": "WARNING",
        "category": "Standing Seam",
        "message": (
            "Standing seam system indicated but original shipper kit is incomplete: "
            + ", ".join(missing)
            + ". Expected full kit: clips, height-consistent eave/rake, "
            "thermal (if insulated/high), backup plates, metal closures, sealant/tape."
        ),
        "expected": "full SS accessory kit",
        "actual": f"missing: {', '.join(missing)}",
        "rule": "ss_accessory_kit_incomplete",
    })
    return findings


# ---------------------------------------------------------------------------
# P1 sealant / tape
# ---------------------------------------------------------------------------

def check_sealant_tape_required(
    categories: Optional[Dict[str, list]] = None,
    drawings_text: str = "",
    shipper_raw_text: str = "",
    panel_families: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """rule: sealant_tape_required"""
    findings: List[Dict[str, Any]] = []
    fam = panel_families or {}
    ship = _blob(categories, shipper_raw_text)
    draw = (drawings_text or "").lower()
    combined = f"{ship}\n{draw}".lower()

    needs = bool(
        fam.get("standing_seam")
        or fam.get("exposed_fastener")
        or fam.get("any_panel")
        or _has(combined, "standing seam", "r-loc", "pbr", "panel")
    )
    # Drawings explicitly require sealant/tape
    drawings_req = _has(
        draw,
        "tri-bead", "tribead", "butyl", "mastic", "sealant", "sealing tape",
        "panel tape", "side lap sealant",
    )
    if not needs and not drawings_req:
        return findings

    has_seal = (
        _qty(categories, (r"sealant", r"butyl", r"tri-?bead", r"mastic", r"\btape\b"))
        or _has(ship, "sealant", "butyl", "tri-bead", "mastic", "sealing tape")
    )
    if drawings_req or fam.get("standing_seam") or fam.get("exposed_fastener"):
        if not has_seal:
            findings.append({
                "severity": "WARNING",
                "category": "Sealant",
                "message": (
                    "Panel/SS system (or drawings) require sealant/tape "
                    "(tri-bead/mastic/butyl), but none was found on the original shipper."
                ),
                "expected": ">0 sealant/tape",
                "actual": 0,
                "rule": "sealant_tape_required",
            })
        else:
            findings.append({
                "severity": "INFO",
                "category": "Sealant",
                "message": "Sealant/tape evidence present on original shipper.",
                "rule": "sealant_tape_required",
            })
    return findings


# ---------------------------------------------------------------------------
# P1 gutter strap kit
# ---------------------------------------------------------------------------

def check_gutter_strap_kit(
    categories: Optional[Dict[str, list]] = None,
    drawings_text: str = "",
    shipper_raw_text: str = "",
) -> List[Dict[str, Any]]:
    """rule: gutter_strap_kit — gutters need straps/hangers + downspouts when Ascent-supplied."""
    findings: List[Dict[str, Any]] = []
    ship = _blob(categories, shipper_raw_text)
    draw = drawings_text or ""
    gut_qty = _qty(categories, (r"\bgutter\b", r"eave\s+gutter", r"box\s+gutter"))
    has_gutter = gut_qty > 0 or _has(ship, "gutter")
    drawings_gutter = _has(draw.lower(), "gutter", "eave gutter") and not _has(
        draw.lower(), "gutter by others", "gutter by owner"
    )
    if not has_gutter and not drawings_gutter:
        return findings

    straps = _qty(
        categories,
        (r"gutter\s*strap", r"gutter\s*hanger", r"hanger\s*strap", r"strap\s*hanger", r"\bhanger\b"),
    ) or (1 if _has(ship, "gutter strap", "gutter hanger", "hanger strap") else 0)
    ds = _qty(categories, (r"down\s*spout", r"downspout", r"\bds-?\d")) or (
        1 if _has(ship, "downspout", "down spout") else 0
    )

    if has_gutter and straps == 0:
        findings.append({
            "severity": "WARNING",
            "category": "Gutter",
            "message": (
                f"Gutter material on shipper (≈{gut_qty or 'present'}) but no gutter "
                "straps/hangers detected. Gutter kits typically include straps/hangers."
            ),
            "expected": ">0 straps/hangers",
            "actual": 0,
            "rule": "gutter_strap_kit",
        })
    if (has_gutter or drawings_gutter) and ds == 0 and has_gutter:
        findings.append({
            "severity": "WARNING",
            "category": "Gutter",
            "message": (
                "Gutter present on original shipper but no downspouts detected — "
                "confirm downspout kit is included."
            ),
            "expected": ">0 downspouts",
            "actual": 0,
            "rule": "gutter_strap_kit",
        })
    if has_gutter and straps > 0 and ds > 0:
        findings.append({
            "severity": "INFO",
            "category": "Gutter",
            "message": f"Gutter kit appears complete (straps/hangers + downspouts).",
            "rule": "gutter_strap_kit",
        })
    return findings


# ---------------------------------------------------------------------------
# P1 liner / insulation members
# ---------------------------------------------------------------------------

def check_liner_insulation_kit(
    categories: Optional[Dict[str, list]] = None,
    drawings_text: str = "",
    shipper_raw_text: str = "",
    panel_families: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    rules: liner_base_member, liner_trim_kit, insulation_angle_required
    """
    findings: List[Dict[str, Any]] = []
    fam = panel_families or {}
    ship = _blob(categories, shipper_raw_text)
    draw = (drawings_text or "").lower()
    combined = f"{ship}\n{draw}".lower()

    has_liner = bool(
        fam.get("liner")
        or fam.get("pl121")
        or _has(combined, "liner panel", "pl121", "pl-121", "interior liner", "wall liner")
    )
    has_insul = _has(combined, "insulation", "skyliner", "r-19", "r-13", "blanket")

    if has_liner:
        base_mem = _qty(
            categories,
            (r"liner\s*base", r"base\s*angle", r"base\s*member", r"liner\s*girt", r"base\s*channel"),
        ) or (1 if _has(ship, "liner base", "base angle", "base member") else 0)
        if base_mem == 0:
            findings.append({
                "severity": "WARNING",
                "category": "Liner",
                "message": (
                    "Liner system indicated but no liner base member / base angle "
                    "detected on the original shipper."
                ),
                "expected": ">0 liner base members",
                "actual": 0,
                "rule": "liner_base_member",
            })
        liner_trim = _qty(
            categories,
            (r"liner\s*trim", r"liner\s*flash", r"inside\s*corner", r"partition\s*trim"),
        ) or (1 if _has(ship, "liner trim", "liner flash") else 0)
        if liner_trim == 0:
            findings.append({
                "severity": "WARNING",
                "category": "Liner",
                "message": (
                    "Liner system indicated but no liner trim / flashing kit detected "
                    "on the original shipper."
                ),
                "expected": ">0 liner trim",
                "actual": 0,
                "rule": "liner_trim_kit",
            })

    if has_insul and (has_liner or _has(combined, "standing seam", "thermal")):
        ang = _qty(
            categories,
            (r"insulation\s*angle", r"insul\s*angle", r"retainer\s*angle", r"band\s*angle"),
        ) or (1 if _has(ship, "insulation angle", "insul angle", "retainer angle") else 0)
        if ang == 0 and _has(draw, "insulation angle", "insul angle", "retainer"):
            findings.append({
                "severity": "WARNING",
                "category": "Insulation",
                "message": (
                    "Drawings call for insulation angle/retainer, but none found on "
                    "the original shipper."
                ),
                "expected": ">0 insulation angles",
                "actual": 0,
                "rule": "insulation_angle_required",
            })
        elif ang == 0 and has_insul and has_liner:
            findings.append({
                "severity": "INFO",
                "category": "Insulation",
                "message": (
                    "Insulation + liner present; confirm insulation angles/retainers "
                    "if required by system (none detected on shipper)."
                ),
                "rule": "insulation_angle_required",
            })
    return findings


# ---------------------------------------------------------------------------
# P1 flange brace clips SC197/SC199
# ---------------------------------------------------------------------------

def check_flange_brace_clip_qty(
    categories: Optional[Dict[str, list]] = None,
    shipper_raw_text: str = "",
) -> List[Dict[str, Any]]:
    """rule: flange_brace_clip_qty"""
    findings: List[Dict[str, Any]] = []
    fb = _qty(
        categories,
        (r"flange\s*brace", r"\bfb-?\d", r"\bfbr-?\d", r"flangebrace"),
    )
    if fb <= 0:
        return findings
    clips = _qty(
        categories,
        (r"sc197", r"sc199", r"sc-?197", r"sc-?199", r"brace\s*clip", r"flange\s*brace\s*clip"),
    )
    # Also count loose clips category with brace context
    if clips == 0:
        for cat, pieces in (categories or {}).items():
            if "clip" in cat.lower() or "loose" in cat.lower():
                for p in pieces:
                    desc = f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')}".lower()
                    if any(k in desc for k in ("sc197", "sc199", "brace clip", "flange")):
                        clips += int(getattr(p, "quantity", 0) or 0)

    if clips == 0:
        findings.append({
            "severity": "WARNING",
            "category": "Flange Braces",
            "message": (
                f"Flange braces present (≈{fb}) but no SC197/SC199-class brace clips "
                "detected on the original shipper."
            ),
            "expected": f">= {fb} brace clips (often 1–2 per brace)",
            "actual": 0,
            "rule": "flange_brace_clip_qty",
        })
    elif clips < max(1, int(fb * 0.5)):
        findings.append({
            "severity": "WARNING",
            "category": "Flange Braces",
            "message": (
                f"Flange braces ≈{fb} but brace clips (SC197/SC199 class) ≈{clips} "
                "look low — confirm clip quantity matches brace count."
            ),
            "expected": f"~{fb}+ clips",
            "actual": clips,
            "rule": "flange_brace_clip_qty",
        })
    else:
        findings.append({
            "severity": "INFO",
            "category": "Flange Braces",
            "message": f"Flange braces ≈{fb} with brace clips ≈{clips}.",
            "rule": "flange_brace_clip_qty",
        })
    return findings


# ---------------------------------------------------------------------------
# P2 ridge/peak, purlin extension cap, pancake SDS
# ---------------------------------------------------------------------------

def check_ridge_peak_trim(
    categories: Optional[Dict[str, list]] = None,
    drawings_text: str = "",
    shipper_raw_text: str = "",
    building_length_ft: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """rule: ridge_peak_trim_qty"""
    findings: List[Dict[str, Any]] = []
    ship = _blob(categories, shipper_raw_text)
    draw = (drawings_text or "").lower()
    ridge_qty = _qty(categories, (r"ridge\s*cap", r"ridge\s*trim", r"peak\s*trim", r"ridge\s*flash"))
    has_ridge_draw = _has(draw, "ridge cap", "ridge trim", "peak trim", "ridge flashing")
    has_ss_roof = _has(f"{ship}\n{draw}", "standing seam", "ridge", "ssr", "double lok", "vsr")
    if not has_ridge_draw and not has_ss_roof and ridge_qty == 0:
        return findings
    if (has_ridge_draw or has_ss_roof) and ridge_qty == 0:
        findings.append({
            "severity": "WARNING",
            "category": "Trim",
            "message": (
                "Ridge/peak trim indicated by drawings or SS roof system, but no "
                "ridge cap/peak trim found on the original shipper."
            ),
            "expected": ">0 ridge/peak trim",
            "actual": 0,
            "rule": "ridge_peak_trim_qty",
        })
    elif ridge_qty > 0 and building_length_ft and building_length_ft > 20:
        # Soft under-bill: pieces much less than length/20 sticks
        min_sticks = max(1, int(building_length_ft / 20.0))
        if ridge_qty < min_sticks:
            findings.append({
                "severity": "WARNING",
                "category": "Trim",
                "message": (
                    f"Ridge/peak trim qty {ridge_qty} looks low for building length "
                    f"≈{building_length_ft} ft (rough min ~{min_sticks} sticks)."
                ),
                "expected": f">={min_sticks}",
                "actual": ridge_qty,
                "rule": "ridge_peak_trim_qty",
            })
    return findings


def check_purlin_extension_cap(
    categories: Optional[Dict[str, list]] = None,
    drawings_text: str = "",
    shipper_raw_text: str = "",
) -> List[Dict[str, Any]]:
    """rule: purlin_extension_cap_channel"""
    findings: List[Dict[str, Any]] = []
    ship = _blob(categories, shipper_raw_text)
    draw = (drawings_text or "").lower()
    has_ext = _has(
        f"{ship}\n{draw}",
        "purlin extension", "extension purlin", "overhang purlin",
        "canopy purlin", "purlin ext",
    )
    if not has_ext and not _has(draw, "purlin extension", "extension channel", "cap channel"):
        return findings
    caps = _qty(
        categories,
        (r"cap\s*channel", r"extension\s*cap", r"purlin\s*cap", r"closure\s*channel"),
    ) or (1 if _has(ship, "cap channel", "extension cap", "purlin cap") else 0)
    if _has(draw, "purlin extension", "extension purlin", "cap channel") and caps == 0:
        findings.append({
            "severity": "WARNING",
            "category": "Secondary Framing",
            "message": (
                "Drawings indicate purlin extension / overhang, but no cap channel "
                "(or purlin extension cap) found on the original shipper."
            ),
            "expected": ">0 cap channel",
            "actual": 0,
            "rule": "purlin_extension_cap_channel",
        })
    return findings


def check_clip_to_purlin_pancake_sds(
    categories: Optional[Dict[str, list]] = None,
    ss_accessories: Optional[Dict[str, int]] = None,
    shipper_raw_text: str = "",
    drawings_text: str = "",
) -> List[Dict[str, Any]]:
    """rule: clip_purlin_pancake_sds — SS clips need pancake/self-drill to purlin when called."""
    findings: List[Dict[str, Any]] = []
    acc = ss_accessories or {}
    clips = int(acc.get("sliding_clips", 0) or 0)
    ship = _blob(categories, shipper_raw_text)
    draw = (drawings_text or "").lower()
    if clips <= 0 and not _has(f"{ship}\n{draw}", "standing seam", "sliding clip"):
        return findings
    if clips <= 0:
        return findings

    pancake = _qty(
        categories,
        (r"pancake", r"\bpanc\b", r"low\s*profile\s*sds", r"clip\s*to\s*purlin", r"purlin\s*sds"),
    ) or (1 if _has(ship, "pancake", "low profile sds", "clip to purlin") else 0)
    clip_screws = int(acc.get("clip_screws", 0) or 0)

    drawings_call = _has(draw, "pancake", "clip to purlin", "self-drill to purlin")
    if drawings_call and pancake == 0 and clip_screws == 0:
        findings.append({
            "severity": "WARNING",
            "category": "Standing Seam",
            "message": (
                "Drawings call for pancake / SDS clip-to-purlin fasteners, but none "
                "were found on the original shipper (and no clip screws extracted)."
            ),
            "expected": "pancake SDS / clip screws",
            "actual": 0,
            "rule": "clip_purlin_pancake_sds",
        })
    elif clips > 0 and clip_screws == 0 and pancake == 0:
        # Soft INFO only — covered by ss_clip_screws_min often
        pass
    return findings


def check_partition_mezz_secondary(
    categories: Optional[Dict[str, list]] = None,
    drawings_text: str = "",
    shipper_raw_text: str = "",
) -> List[Dict[str, Any]]:
    """rule: partition_mezz_secondary"""
    findings: List[Dict[str, Any]] = []
    ship = _blob(categories, shipper_raw_text)
    draw = (drawings_text or "").lower()
    has_part = _has(draw, "partition", "interior wall frame", "demising")
    has_mezz = _has(draw, "mezzanine", "mezz floor", "elevated floor")
    if not has_part and not has_mezz:
        return findings

    sec = _qty(
        categories,
        (r"partition", r"mezz", r"floor\s*beam", r"joist", r"interior\s*girt"),
    ) or (
        1 if _has(ship, "partition", "mezzanine", "mezz", "floor beam") else 0
    )
    if has_part and not _has(ship, "partition") and sec == 0:
        findings.append({
            "severity": "WARNING",
            "category": "Secondary Framing",
            "message": (
                "Drawings show partition framing, but no partition secondary "
                "was found on the original shipper (confirm phase / scope)."
            ),
            "rule": "partition_mezz_secondary",
        })
    if has_mezz and not _has(ship, "mezz", "mezzanine", "floor beam") and sec == 0:
        findings.append({
            "severity": "INFO",
            "category": "Mezzanine",
            "message": (
                "Drawings show mezzanine; no mezz secondary/floor beams on original "
                "shipper — confirm phase scope."
            ),
            "rule": "partition_mezz_secondary",
        })
    return findings
