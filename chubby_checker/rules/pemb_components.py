"""
Pre-engineered metal building (PEMB) component signal detection.

Research-informed vocabulary for scanning Final Drawings and Complete Shippers.
Used by parsers and the discrepancy engine so drawings→shipper checks share
one awareness model (panels, framing, accessories, buyouts, systems).

Not a substitute for mark-by-mark Member Tables — these are free-text /
category-level signals that raise the right severity when drawings imply
systems the shipper does not carry.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional


# ---------------------------------------------------------------------------
# Keyword banks (case-insensitive substring / regex)
# ---------------------------------------------------------------------------

STANDING_SEAM_SIGNALS = (
    "standing seam", "central-loc", "central loc", "central seam",
    "central-snap", "central snap", "central-span", "central span",
    "double lok", "double-lok", "doublelok", "ultra-dek", "ultradek",
    "vsr6", "vsr 6", " vsr", "ssr", "mechanical seam", "snap seam",
    "mcelroy", "superlok", "super lok", "battenlok", "batten lok",
    "cs244", "cs184", "vs16", "cl2122", "sliding clip", "floating clip",
)

EXPOSED_PANEL_SIGNALS = (
    "r-loc", "rloc", "r loc", "rlocrev", "rlr", "rlx", "pbr", "rpbr",
    "m-loc", "mloc", "panel-loc", "panel loc", "pba", "pbm", "7.2",
    "avp", "exposed fastener", "screw down", "screw-down", "through fastened",
    "through-fastened", "rev r-loc", "r-loc reverse",
)

CONCEALED_WALL_SIGNALS = (
    "shadow rib", "shadowrib", "fw-120", "fw120", "fw 120",
    "masterline", "master line", "masterline-16", "ml16",
)

LINER_SIGNALS = (
    "pl121", "pl-121", "liner panel", "interior liner", "wall liner",
)

IMP_SIGNALS = (
    "kingspan", "insulated metal panel", "insulated panel",
    "awip", "all weather insulated", "metl-span", "metlspan",
    "permotherm", "brucha", "nucor panel",
)

BDECK_JOIST_SIGNALS = (
    "b-deck", "b deck", "bdeck", "n-deck", "structural deck",
    "new millennium", "nmbs", "bar joist", "steel joist", "roof deck",
    "floor deck", "open web joist",
)

PRIMARY_FRAMING_SIGNALS = (
    "rigid frame", "main frame", "primary frame", "endwall frame",
    "clear span", "modular frame", "tapered frame", "built-up frame",
    "rafter", "frame line", "moment frame",
)

SECONDARY_FRAMING_SIGNALS = (
    "purlin", "girt", "eave strut", "eavestrut", "flange brace",
    "sag angle", "bridging", "cold formed", "zee purlin", "cee girt",
)

CRANE_SIGNALS = (
    "crane", "runway beam", "runway support", "crane beam", "crane rail",
    "underhung crane", "top running crane", "bridge crane",
)

MEZZ_SIGNALS = (
    "mezzanine", "floor beam", "mezz floor", "elevated floor",
)

CLOSURE_METAL_SIGNALS = (
    "metal closure", "metal inside", "metal outside", "cl426", "cl430",
    "hw-410", "hw-412", "hw-422", "hw-432", "sped16", "end dam", "enddam",
    "sprakez6", "bird stop", "fl-361",
)

CLOSURE_FOAM_SIGNALS = (
    "foam closure", "foam inside", "foam outside", "rlcloutg", "rlclingl",
    "rlclin", "rlclout", "closed cell closure",
)

SEALANT_SIGNALS = (
    "sealant", "butyl", "tube sealant", "gun grade", "mastic",
    "joint sealant", "seam sealant",
)

FASTENER_SIGNALS = (
    "self-drill", "self drilling", "stitch screw", "lap screw",
    "panel screw", "tek screw", "sealing washer", "structural bolt",
    "a325", "a490", "clip screw", "fss10", "fss1",
)

TRIM_SIGNALS = (
    "eave trim", "rake trim", "ridge cap", "ridge trim", "base trim",
    "corner trim", "gutter", "downspout", "down spout", "transition trim",
    "step trim", "roof step",
)

CLIP_SIGNALS = (
    "sliding clip", "floating clip", "fixed clip", "panel clip",
    "seam clip", "backup plate", "back up plate", "thermal block",
    "thermal spacer", "s-5", "s5 clamp",
)

DOOR_OPENING_SIGNALS = (
    "overhead door", "roll-up", "rollup", "framed opening", "walk door",
    "personnel door", "sectional door", "hangar door",
)

VENDOR_DRAWING_HINTS = (
    "american buildings", "steelco", "mbci", "mcelroy", "central states",
    "ascent", "varco pruden", "vp buildings", "butler", "nci",
)


def _blob_from_categories(categories: Optional[Dict[str, list]]) -> str:
    parts: List[str] = []
    for cat, pieces in (categories or {}).items():
        parts.append(str(cat))
        for p in pieces or []:
            parts.append(f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')}")
    return " ".join(parts)


def _has_any(blob: str, signals: Iterable[str]) -> bool:
    return any(s in blob for s in signals)


def _has_regex(blob: str, pattern: str) -> bool:
    return bool(re.search(pattern, blob, re.IGNORECASE))


def detect_pemb_signals(
    raw_text: str = "",
    categories: Optional[Dict[str, list]] = None,
    extra_keys: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """
    Return boolean / list signals describing PEMB systems present in text.

    Suitable for drawings notes pages, shipper index text, or combined blobs.
    """
    parts = [raw_text or "", _blob_from_categories(categories)]
    if extra_keys:
        parts.extend(str(k) for k in extra_keys)
    blob = " ".join(parts).lower()
    # Normalize curly quotes / dashes for matching
    blob = (
        blob.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )

    standing_seam = _has_any(blob, STANDING_SEAM_SIGNALS) or _has_regex(
        blob, r"\b(csx?|clx?|vsr6?|ssr|s6)\b"
    )
    exposed = _has_any(blob, EXPOSED_PANEL_SIGNALS) or _has_regex(
        blob, r"\b(rl|rlr|rlx|pbr|rpbr|pba|pbm|avp)\b"
    )
    # Avoid bare "imp" false positives
    imp = any(s in blob for s in IMP_SIGNALS if s != "imp") or _has_regex(
        blob, r"\bimps?\b"
    )
    bdeck_joist = _has_any(blob, BDECK_JOIST_SIGNALS)
    primary = _has_any(blob, PRIMARY_FRAMING_SIGNALS) or _has_regex(
        blob, r"\b(rf|pf|mf|ef)[- ]?\d"
    )
    secondary = _has_any(blob, SECONDARY_FRAMING_SIGNALS)
    crane = _has_any(blob, CRANE_SIGNALS)
    mezz = _has_any(blob, MEZZ_SIGNALS)
    concealed = _has_any(blob, CONCEALED_WALL_SIGNALS)
    liner = _has_any(blob, LINER_SIGNALS)
    metal_closures = _has_any(blob, CLOSURE_METAL_SIGNALS)
    foam_closures = _has_any(blob, CLOSURE_FOAM_SIGNALS)
    sealant = _has_any(blob, SEALANT_SIGNALS)
    fasteners = _has_any(blob, FASTENER_SIGNALS)
    trim = _has_any(blob, TRIM_SIGNALS)
    clips = _has_any(blob, CLIP_SIGNALS)
    doors = _has_any(blob, DOOR_OPENING_SIGNALS)

    families: List[str] = []
    if standing_seam:
        families.append("standing_seam")
    if exposed:
        families.append("exposed_fastener")
    if concealed:
        families.append("concealed_wall")
    if liner:
        families.append("liner")
    if imp:
        families.append("imp")
    if bdeck_joist:
        families.append("bdeck_joist")

    vendors = [v for v in VENDOR_DRAWING_HINTS if v in blob]

    return {
        "standing_seam": standing_seam,
        "exposed_fastener": exposed,
        "concealed_wall": concealed,
        "liner": liner,
        "imp": imp,
        "bdeck_joist": bdeck_joist,
        "primary_framing": primary,
        "secondary_framing": secondary,
        "crane": crane,
        "mezzanine": mezz,
        "metal_closures_mentioned": metal_closures,
        "foam_closures_mentioned": foam_closures,
        "sealant_mentioned": sealant,
        "fasteners_mentioned": fasteners,
        "trim_mentioned": trim,
        "clips_accessories_mentioned": clips,
        "doors_openings": doors,
        "panel_families": families,
        "vendors_hinted": vendors,
        "any_cladding": standing_seam or exposed or concealed or liner or imp,
        "any_structure": primary or secondary or crane or mezz,
    }


def shipper_category_blob(categories: Optional[Dict[str, list]]) -> str:
    return " ".join((categories or {}).keys()).lower()


def shipper_has_runway(categories: Optional[Dict[str, list]], raw_text: str = "") -> bool:
    blob = shipper_category_blob(categories) + " " + (raw_text or "").lower()
    return any(k in blob for k in ("runway", "crane"))


def shipper_has_mezz(categories: Optional[Dict[str, list]], raw_text: str = "") -> bool:
    blob = shipper_category_blob(categories) + " " + (raw_text or "").lower()
    return any(k in blob for k in ("mezz", "mezzanine"))


def shipper_has_primary_structure(categories: Optional[Dict[str, list]], raw_text: str = "") -> bool:
    blob = shipper_category_blob(categories) + " " + (raw_text or "").lower()
    return any(
        k in blob
        for k in (
            "fabricated steel", "hot rolled", "primary", "frame",
            "rigid", "column",
        )
    )


def shipper_has_secondary(categories: Optional[Dict[str, list]], raw_text: str = "") -> bool:
    blob = shipper_category_blob(categories) + " " + (raw_text or "").lower()
    return any(
        k in blob
        for k in ("cold formed", "purlin", "girt", "eave", "secondary", "zee", "cee")
    )


def shipper_has_sealant(categories: Optional[Dict[str, list]], raw_text: str = "") -> bool:
    blob = shipper_category_blob(categories) + " " + (raw_text or "").lower()
    return "sealant" in blob or "butyl" in blob


def shipper_has_screws_fasteners(categories: Optional[Dict[str, list]], raw_text: str = "") -> bool:
    blob = shipper_category_blob(categories) + " " + (raw_text or "").lower()
    return any(k in blob for k in ("screw", "fastener", "bolt"))


def cross_check_drawings_to_shipper(
    drawings_signals: Dict[str, Any],
    shipper_categories: Optional[Dict[str, list]] = None,
    shipper_raw_text: str = "",
    shipper_families: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Produce findings when Final Drawings imply PEMB systems missing from shipper.

    Severity policy (research + prior Chubby behavior):
      - Crane system missing → WARNING
      - Mezzanine missing → INFO (often multi-phase)
      - Standing seam on drawings, none on shipper → WARNING
      - Exposed panels on drawings, none on shipper → WARNING
      - Primary framing implied, no structural categories → WARNING
      - Exterior cladding present, no sealant category → INFO
      - B-deck/joist on drawings → INFO buyout awareness
      - IMP on drawings → INFO buyout / closure exception awareness
    """
    findings: List[Dict[str, Any]] = []
    fam = shipper_families or {}
    cats = shipper_categories or {}
    raw = shipper_raw_text or ""

    # Crane
    if drawings_signals.get("crane") and not shipper_has_runway(cats, raw):
        findings.append({
            "severity": "WARNING",
            "category": "Crane",
            "message": (
                "Final drawings reference crane/runway components, but the shipper "
                "has no Runway/Crane category or related marks. Confirm phase or buy-out."
            ),
            "rule": "drawings_shipper_crane",
        })

    # Mezzanine
    if drawings_signals.get("mezzanine") and not shipper_has_mezz(cats, raw):
        findings.append({
            "severity": "INFO",
            "category": "Mezzanine",
            "message": (
                "Final drawings show mezzanine/floor framing. Confirm mezzanine "
                "steel is on this shipper or another phase."
            ),
            "rule": "drawings_shipper_mezzanine",
        })

    # Standing seam cladding
    shipper_ss = bool(fam.get("standing_seam")) or "standing seam" in shipper_category_blob(cats)
    if drawings_signals.get("standing_seam") and not shipper_ss:
        findings.append({
            "severity": "WARNING",
            "category": "Panels",
            "message": (
                "Final drawings indicate standing seam roof/wall systems, but the "
                "shipper does not show standing-seam panel families or SS categories. "
                "Verify panel type and SS accessories (clips, backup plates, metal closures)."
            ),
            "rule": "drawings_shipper_standing_seam",
        })

    # Exposed fastener cladding
    shipper_exp = bool(fam.get("exposed_fastener")) or any(
        k in shipper_category_blob(cats)
        for k in ("r-loc", "rloc", "pbr", "standard panel", "exposed")
    )
    if drawings_signals.get("exposed_fastener") and not shipper_exp and not shipper_ss:
        findings.append({
            "severity": "WARNING",
            "category": "Panels",
            "message": (
                "Final drawings indicate exposed-fastener / screw-down panels "
                "(R-Loc/PBR/AVP/PBA/7.2 class), but the shipper does not show those "
                "panel families. Verify wall/roof panel marks and foam closures."
            ),
            "rule": "drawings_shipper_exposed_panels",
        })

    # Primary structure
    if drawings_signals.get("primary_framing") and not shipper_has_primary_structure(cats, raw):
        # Only warn if shipper has some content (avoid empty false alarm noise)
        if cats:
            findings.append({
                "severity": "WARNING",
                "category": "Primary Framing",
                "message": (
                    "Final drawings reference primary/rigid frame structure, but the "
                    "shipper lacks Fabricated Steel / Hot Rolled / primary frame categories. "
                    "Confirm primary steel is included or shipped in another phase."
                ),
                "rule": "drawings_shipper_primary",
            })

    # Secondary structure
    if drawings_signals.get("secondary_framing") and not shipper_has_secondary(cats, raw):
        if cats:
            findings.append({
                "severity": "INFO",
                "category": "Secondary Framing",
                "message": (
                    "Final drawings reference purlins/girts/eave struts, but Cold Formed / "
                    "secondary categories were not obvious on the shipper. Confirm secondary steel."
                ),
                "rule": "drawings_shipper_secondary",
            })

    # Sealant with cladding
    if drawings_signals.get("any_cladding") or drawings_signals.get("sealant_mentioned"):
        if (drawings_signals.get("any_cladding") or drawings_signals.get("trim_mentioned")) and not shipper_has_sealant(cats, raw):
            if fam.get("any_panel") or drawings_signals.get("any_cladding"):
                findings.append({
                    "severity": "INFO",
                    "category": "Sealant",
                    "message": (
                        "Exterior cladding/trim is indicated, but no Sealant category was "
                        "detected on the shipper. MBMA common practice includes sealants with "
                        "exterior covering — confirm sealant is listed or supplied separately."
                    ),
                    "rule": "drawings_shipper_sealant",
                })

    # B-deck / joists
    if drawings_signals.get("bdeck_joist"):
        findings.append({
            "severity": "INFO",
            "category": "Buyouts",
            "message": (
                "Final drawings reference bar joists / structural deck (e.g. New Millennium "
                "B-deck). Treat as buy-out; do not apply standing-seam metal or screw-down "
                "foam closure rules to deck-only systems."
            ),
            "rule": "drawings_shipper_bdeck_joist",
        })

    # IMP
    if drawings_signals.get("imp") and not fam.get("standing_seam"):
        findings.append({
            "severity": "INFO",
            "category": "Buyouts",
            "message": (
                "Final drawings reference insulated metal panels (IMP/Kingspan/AWIP class). "
                "IMPs are typically buy-outs; standard SS metal-closure checks are suppressed "
                "for pure IMP scopes."
            ),
            "rule": "drawings_shipper_imp",
        })

    # Vendor diversity (awareness only)
    vendors = drawings_signals.get("vendors_hinted") or []
    if len(vendors) >= 2:
        findings.append({
            "severity": "INFO",
            "category": "Drawings",
            "message": (
                "Multiple manufacturer/vendor names appear on drawings "
                f"({', '.join(vendors[:5])}). Chubby Checker compares marks/quantities "
                "generically — verify multi-company scopes are fully on the shipper."
            ),
            "rule": "drawings_multi_vendor",
        })

    return findings
