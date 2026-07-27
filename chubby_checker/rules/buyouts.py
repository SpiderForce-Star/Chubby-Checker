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

from typing import Dict, List, Set, Any

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

# Insulated Metal Panels – always buy-out
IMP_KEYWORDS = [
    "imp",
    "insulated metal panel",
    "insulated panel",
    "kingspan",
    "awip",
    "all weather insulated",
    "nucor panel",
    "metl-span",
    "metlspan",
]

# Joist & Deck – New Millennium (framing by others)
JOIST_DECK_KEYWORDS = [
    "bar joist",
    "steel joist",
    "joist",
    "new millennium",
    "roof deck",
    "floor deck",
    "metal deck",
    "b-deck",
    "n-deck",
    "deck",
]

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
    return any(k in t for k in BUYOUT_KEYWORDS)


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
    return any(k in t for k in JOIST_DECK_KEYWORDS)


def is_imp(text: str) -> bool:
    t = _normalize(text)
    return any(k in t for k in IMP_KEYWORDS)


def filter_buyouts_from_marks(mark_map: Dict[str, int]) -> Dict[str, int]:
    """
    Remove marks that look like buy-outs so they do not generate
    CRITICAL missing-piece errors against drawings.
    """
    return {m: q for m, q in mark_map.items() if not is_buyout_text(m)}


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
