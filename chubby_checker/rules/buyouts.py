"""
Buy-out exclusion rules for Chubby-Checker (Ascent Buildings).

=====================================================================
ASCENT SUPPLIES (must be present and checked when required by drawings)
=====================================================================
  • Primary / main framing   (RF, PF, MF, columns, rafters, endwalls)
  • Secondary framing        (purlins, girts, eave struts, flange braces)
  • Sheeting                 (standing seam + exposed fastener panels)
  • Trim                     (eave, rake, corner, base, gutter, downspout, etc.)
  • Related accessories      (clips, thermal blocks, screws, bolts, closures)
  • Crane runway SUPPORTS    (beams & braces – NOT the rail itself)
  • Mezzanine framing        (when Ascent-supplied)

=====================================================================
ALWAYS BUY-OUTS (exclude from missing-piece checks; expect zero/near-zero weight)
=====================================================================
  • Insulation               (blanket, Skyliner, bay insulation, etc.)
                             → Weight on shipper should be 0.00
  • IMPs                     (Insulated Metal Panels – Kingspan, AWIP, Nucor…)
  • Joists & Deck            (New Millennium Building Systems)
                             → Framing by others; interfaces with Ascent steel
  • Walk / personnel doors   (door UNIT only – framed opening may be Ascent CFS)
  • Overhead / roll-up doors (door UNIT only)
  • Windows                  (unit only)
  • Louvers                  (unit only)
  • Skylights
  • Roof & wall vents
  • Fans                     (exhaust / supply)

Important distinctions
----------------------
- Framed openings, jambs, headers, and trimmers for doors/windows are often
  Ascent cold-formed and SHOULD be checked.
- The door/window/louver UNIT itself is a buy-out.
- Joist seats or connections on Ascent beams are Ascent; the joists are not.
"""

import re
from typing import Dict, List, Set, Any, Optional

# ---------------------------------------------------------------------------
# Keyword groups (order = specificity preference)
# ---------------------------------------------------------------------------

# Insulation – always buy-out, weight expected = 0
INSULATION_KEYWORDS = [
    "insulation",
    "skyliner",
    "bay insulation",
    "faced insulation",
    "unfaced insulation",
    "thermal insulation",
    "blanket insulation",
    "vinyl faced",
    "fiberglass blanket",
]

# Insulated Metal Panels – always buy-out (avoid bare "imp" substring)
IMP_KEYWORDS = [
    "insulated metal panel",
    "insulated panel",
    "kingspan",
    "awip",
    "all weather insulated",
    "nucor panel",
    "metl-span",
    "metlspan",
]
IMP_WORD_RE = re.compile(r"\bimps?\b", re.IGNORECASE)

# Joist & Deck – New Millennium (framing by others)
# Prefer phrases; bare "deck" alone is too aggressive for mark filters
JOIST_DECK_KEYWORDS = [
    "bar joist",
    "steel joist",
    "open web joist",
    "new millennium",
    "roof deck",
    "floor deck",
    "metal deck",
    "b-deck",
    "b deck",
    "n-deck",
    "structural deck",
]
JOIST_WORD_RE = re.compile(r"\bjoists?\b", re.IGNORECASE)

# Door / window / louver UNITS (not the framed opening)
DOOR_WINDOW_KEYWORDS = [
    "walk door",
    "man door",
    "personnel door",
    "hollow metal door",
    "overhead door",
    "roll-up door",
    "rollup door",
    "rolling door",
    "sectional door",
    "oh door",
    "window",
    "louver",
    "louvre",
]

# Skylights, vents, fans
SKYLIGHT_VENT_FAN_KEYWORDS = [
    "skylight",
    "sky light",
    "roof vent",
    "wall vent",
    "ridge vent",
    "turbine vent",
    "gravity vent",
    "exhaust fan",
    "supply fan",
    "wall fan",
    "roof fan",
]

# Combined flat list for simple scans
BUYOUT_KEYWORDS: List[str] = (
    INSULATION_KEYWORDS
    + IMP_KEYWORDS
    + JOIST_DECK_KEYWORDS
    + DOOR_WINDOW_KEYWORDS
    + SKYLIGHT_VENT_FAN_KEYWORDS
)
# Note: bare "imp" / "deck" / lone "joist" are handled via word-boundary helpers

# Exact category names that appear on Ascent Shipping List Index
BUYOUT_CATEGORIES: Set[str] = {
    "insulation",
    "bar joists",
    "joists",
    "deck",
    "metal deck",
    "imp",
    "insulated panels",
    "insulated metal panels",
}


def _normalize(text: str) -> str:
    return (text or "").lower().strip()


def is_buyout_text(text: str) -> bool:
    """
    Return True if the text clearly indicates a buy-out item.
    Uses whole-phrase preference to reduce false positives.
    """
    t = _normalize(text)
    if not t:
        return False
    if any(k in t for k in BUYOUT_KEYWORDS):
        return True
    if IMP_WORD_RE.search(t):
        return True
    if JOIST_WORD_RE.search(t) and any(
        k in t for k in ("bar", "steel", "open web", "millennium", "nmbs")
    ):
        return True
    return False


def is_buyout_category(category: str) -> bool:
    """Return True if the shipper category itself is a known buy-out."""
    c = _normalize(category)
    if not c:
        return False
    if c in BUYOUT_CATEGORIES:
        return True
    return is_buyout_text(c)


def is_insulation(text: str) -> bool:
    t = _normalize(text)
    return any(k in t for k in INSULATION_KEYWORDS)


def is_joist_or_deck(text: str) -> bool:
    t = _normalize(text)
    if any(k in t for k in JOIST_DECK_KEYWORDS):
        return True
    return bool(JOIST_WORD_RE.search(t) and any(
        k in t for k in ("bar", "steel", "open web", "millennium", "nmbs", "deck")
    ))


def is_imp(text: str) -> bool:
    t = _normalize(text)
    if any(k in t for k in IMP_KEYWORDS):
        return True
    return bool(IMP_WORD_RE.search(t))


def filter_buyouts_from_marks(
    mark_map: Dict[str, int],
    mark_context: Optional[Dict[str, str]] = None,
) -> Dict[str, int]:
    """
    Remove marks that look like buy-outs so they do not generate
    CRITICAL missing-piece errors against drawings.

    mark_context: optional mark → description/category blob for richer filtering
    (joists often use marks like J1 / BJ3 that do not contain the word 'joist').
    """
    out: Dict[str, int] = {}
    ctx = mark_context or {}
    for m, q in mark_map.items():
        blob = f"{m} {ctx.get(m, '')}"
        if is_buyout_text(blob):
            continue
        # Common joist mark patterns when context says joist/deck
        mu = (m or "").upper()
        ctx_l = (ctx.get(m) or "").lower()
        if re.match(r"^(BJ|OJ|J)\d", mu) and any(
            k in ctx_l for k in ("joist", "deck", "millennium", "nmbs")
        ):
            continue
        # Bare BJ/OJ marks (New Millennium style) without context → treat as buy-out
        if re.match(r"^(BJ|OJ)\d", mu):
            continue
        out[m] = q
    return out


def check_unexpected_buyouts(shipper_categories: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Flag when a known buy-out category appears with quantity or weight
    in an Ascent shipper (possible mis-classification or double-supply).

    Returns list of finding dicts compatible with DiscrepancyEngine.
    """
    findings: List[Dict[str, Any]] = []

    for cat, pieces in (shipper_categories or {}).items():
        if not is_buyout_category(cat):
            continue

        total_qty = sum(getattr(p, "quantity", 0) or 0 for p in pieces)
        if total_qty <= 0:
            continue

        # Tailor message by type
        if is_joist_or_deck(cat):
            msg = (
                f"Category '{cat}' (qty {total_qty}) appears in the Ascent shipper. "
                f"Joists & Deck are always buy-outs from New Millennium Building Systems. "
                f"Confirm Ascent is not supplying this material."
            )
            severity = "WARNING"
        elif is_insulation(cat):
            msg = (
                f"Category '{cat}' (qty {total_qty}) appears in the shipper. "
                f"Insulation is a buy-out and normally carries 0.00 weight."
            )
            severity = "INFO"
        elif is_imp(cat):
            msg = (
                f"Category '{cat}' (qty {total_qty}) appears in the shipper. "
                f"IMPs (Kingspan / AWIP / Nucor etc.) are buy-outs."
            )
            severity = "WARNING"
        elif any(k in cat.lower() for k in ("skylight", "sky light")):
            # Units are buy-outs; do not restate OSHA/safety language (erection manuals)
            msg = (
                f"Category '{cat}' (qty {total_qty}) appears in the shipper. "
                f"Skylight units are buy-outs; safety notes are covered in erection manuals."
            )
            severity = "INFO"
        else:
            msg = (
                f"Category '{cat}' (qty {total_qty}) is a standard Ascent buy-out "
                f"but appears in the shipper. Confirm classification."
            )
            severity = "INFO"

        findings.append({
            "severity": severity,
            "category": "Buy-out",
            "message": msg,
            "actual": total_qty,
            "rule": "buyout_unexpected",
        })

    return findings


# ---------------------------------------------------------------------------
# Plant-cannot-fab angles / specials that must be routed to CS / vendor
# (field 25-13168 SO6: 8x8x14ga angle never marked up for CS)
# ---------------------------------------------------------------------------

# L8x8, L6x6, L3x3, 8x8x14, connection angles often cannot plant-fab at Ascent
PLANT_CANNOT_FAB_PATTERNS = (
    re.compile(r"\bL\s*8\s*[xX×]\s*8\b", re.I),
    re.compile(r"\bL\s*6\s*[xX×]\s*6\b", re.I),
    re.compile(r"\bL\s*3\s*[xX×]\s*3\b", re.I),
    re.compile(r"\b8\s*[xX×]\s*8\s*[xX×]\s*14\b", re.I),
    re.compile(r"\b8\s*[xX×]\s*8\s*[xX×]\s*1/?4\b", re.I),
    re.compile(r"\b8x8x14\s*ga", re.I),
    re.compile(r"\bconnection\s+angle\b", re.I),
    re.compile(r"\blintel\b", re.I),
    re.compile(r"\bplant\s+cannot\s+fab", re.I),
    re.compile(r"\bcannot\s+fab\b", re.I),
)

VENDOR_ROUTING_EVIDENCE = (
    "central states", "cs fab", "cs shop", "vendor", "buyout", "buy-out",
    "buy out", "outside fab", "outsource", "special order", "so to cs",
)


def is_plant_cannot_fab_text(text: str) -> bool:
    t = text or ""
    return any(p.search(t) for p in PLANT_CANNOT_FAB_PATTERNS)


def check_plant_cannot_fab_routing(
    drawings_member_tables: Optional[Dict[str, list]] = None,
    drawings_mark_map: Optional[Dict[str, int]] = None,
    shipper_categories: Optional[Dict[str, list]] = None,
    shipper_raw_text: str = "",
    drawings_raw_text: str = "",
) -> List[Dict[str, Any]]:
    """
    WARNING when plant-cannot-fab shapes appear on drawings but shipper has no
    matching mark and no CS/vendor routing evidence.
    rule: plant_cannot_fab_not_routed
    """
    findings: List[Dict[str, Any]] = []
    suspects: List[tuple] = []  # (mark, qty, blob)

    for cat, pieces in (drawings_member_tables or {}).items():
        for p in pieces:
            mark = getattr(p, "mark", "") or ""
            desc = getattr(p, "description", "") or ""
            section = getattr(p, "section", "") or ""
            blob = f"{mark} {desc} {section} {cat}"
            if is_plant_cannot_fab_text(blob):
                suspects.append((mark, int(getattr(p, "quantity", 1) or 1), blob))

    # Also scan drawings free text for angle callouts without mark
    if drawings_raw_text and is_plant_cannot_fab_text(drawings_raw_text):
        if not suspects:
            suspects.append(("", 0, drawings_raw_text[:200]))

    if not suspects:
        return findings

    ship_marks = set()
    ship_blob_parts = [shipper_raw_text or ""]
    for cat, pieces in (shipper_categories or {}).items():
        ship_blob_parts.append(str(cat))
        for p in pieces:
            ship_marks.add(str(getattr(p, "mark", "") or "").upper())
            ship_blob_parts.append(f"{getattr(p, 'mark', '')} {getattr(p, 'description', '')}")
    ship_blob = " ".join(ship_blob_parts).lower()
    has_routing = any(k in ship_blob for k in VENDOR_ROUTING_EVIDENCE)

    for mark, qty, blob in suspects[:15]:
        mark_u = (mark or "").upper()
        on_shipper = bool(mark_u and mark_u in ship_marks)
        if on_shipper or has_routing:
            continue
        # Also treat presence of matching angle text on shipper as OK
        if mark and is_plant_cannot_fab_text(ship_blob) and mark_u and mark_u[:4] in ship_blob.upper():
            continue
        findings.append({
            "severity": "WARNING",
            "category": "Buy-out / Vendor",
            "message": (
                f"Plant-cannot-fab shape indicated on drawings"
                f"{f' (mark {mark}, qty {qty})' if mark else ''} "
                f"— e.g. heavy angle / special lintel — but no matching shipper mark "
                "and no CS/vendor routing evidence. Mark up for Central States / outside fab."
            ),
            "expected": "CS/vendor routing or shipper mark",
            "actual": "not routed",
            "mark": mark or "",
            "rule": "plant_cannot_fab_not_routed",
        })
        break  # one WARNING is enough per run

    return findings
