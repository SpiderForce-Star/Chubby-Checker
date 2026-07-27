"""
Buy-out exclusion rules for Ascent Buildings jobs.

=======================================================================
ASCENT SCOPE (checked by Chubby-Checker)
=======================================================================
Ascent designs, fabricates, and ships:
  • Primary / main framing   (RF, PF, MF, columns, rafters, endwalls)
  • Secondary framing        (purlins, girts, eave struts, flange braces, sag rods)
  • Sheeting                 (standing seam + exposed fastener panels)
  • Trim, gutters, downspouts, closures, fasteners
  • Crane runway beams & braces (when in contract — not the rail itself)
  • Mezzanine framing        (when Ascent-supplied)

Framed openings (door jambs, headers, sills, trimmers) are typically
Ascent cold-formed steel and SHOULD be checked.

=======================================================================
ALWAYS BUY-OUTS (do not flag as missing)
=======================================================================
These items are supplied by others. Chubby-Checker must:
  1. Never raise CRITICAL "missing piece" errors for them.
  2. Expect Insulation weight = 0.00 on the shipper.
  3. Warn only if a buy-out category appears with unexpected quantity/weight
     (possible data-entry error on the shipper).

Buy-out list (exact):
  • Insulation (any type — blanket, Skyliner, bay, faced/unfaced)
  • IMPs — Insulated Metal Panels (Kingspan, AWIP, Nucor, etc.)
  • Joist & Deck supplied by New Millennium Building Systems
        ("framing by others" — joists themselves are buy-out;
         any Ascent support steel around them is still checked)
  • Walk / personnel / man doors          (the door unit)
  • Overhead / roll-up / sectional doors  (the door unit)
  • Windows
  • Louvers
  • Skylights
  • Roof vents & wall vents
  • Fans (exhaust, supply, etc.)

=======================================================================
"""

from typing import Dict, List, Set, Any, Optional

# ---------------------------------------------------------------------------
# Keyword lists (case-insensitive matching)
# ---------------------------------------------------------------------------

INSULATION_KEYWORDS = [
    "insulation", "skyliner", "bay insulation",
    "faced insulation", "unfaced insulation",
    "thermal insulation", "blanket insulation",
    "vinyl faced", "scrim",
]

IMP_KEYWORDS = [
    "imp", "insulated metal panel", "insulated panel",
    "kingspan", "awip", "all weather insulated",
    "nucor panel", "nucor insulated",
]

JOIST_DECK_KEYWORDS = [
    "joist", "bar joist", "steel joist", "open web joist",
    "new millennium", "newmillennium",
    "metal deck", "roof deck", "floor deck", "composite deck",
    # bare "deck" is risky; keep it only with context in is_buyout_text
]

DOOR_UNIT_KEYWORDS = [
    "walk door", "man door", "personnel door",
    "overhead door", "roll-up", "rollup", "rolling door",
    "sectional door", "oh door",
]

OPENING_UNIT_KEYWORDS = [
    "window", "louver", "louvre",
    "skylight", "sky light",
    "roof vent", "wall vent", "ridge vent", "exhaust vent",
    "exhaust fan", "supply fan", "power fan", "fan unit",
]

# Combined list used by the generic matcher
BUYOUT_KEYWORDS: List[str] = (
    INSULATION_KEYWORDS
    + IMP_KEYWORDS
    + JOIST_DECK_KEYWORDS
    + DOOR_UNIT_KEYWORDS
    + OPENING_UNIT_KEYWORDS
    + ["fan"]  # broad fan catch; refined below
)

# Category names that appear on Ascent Shipping List Index / Load Out
BUYOUT_CATEGORIES: Set[str] = {
    "insulation",
    "bar joists",
    "joists",
    "joist",
    "deck",
    "metal deck",
    "imp",
    "imps",
    "insulated panels",
    "insulated metal panels",
}


def is_buyout_text(text: str) -> bool:
    """
    Return True if the text clearly indicates a buy-out item.

    Notes on ambiguity:
    - "Deck" alone can mean mezzanine decking support or buy-out metal deck.
      We treat clear "metal deck / roof deck / floor deck / New Millennium"
      as buy-out; bare structural marks stay in scope.
    - "Fan" alone is broad; prefer "exhaust fan", "supply fan", etc.
    - Framed opening steel (jamb, header, sill) is NOT a buy-out.
    """
    if not text:
        return False
    t = text.lower().strip()

    # Strong matches first
    for k in (INSULATION_KEYWORDS + IMP_KEYWORDS + DOOR_UNIT_KEYWORDS + OPENING_UNIT_KEYWORDS):
        if k in t:
            return True

    # Joist / deck – require clearer context
    for k in JOIST_DECK_KEYWORDS:
        if k in t:
            return True

    # Bare "fan" only if it looks like equipment, not a mark fragment
    if "fan" in t and any(w in t for w in ["exhaust", "supply", "roof", "wall", "unit", "power"]):
        return True

    return False


def is_buyout_category(category: str) -> bool:
    """Return True if the shipper category name itself is a buy-out."""
    if not category:
        return False
    c = category.lower().strip()
    if c in BUYOUT_CATEGORIES:
        return True
    return is_buyout_text(c)


def is_insulation_category(category: str) -> bool:
    """Special case: insulation must show 0.00 weight."""
    if not category:
        return False
    c = category.lower()
    return any(k in c for k in INSULATION_KEYWORDS) or c == "insulation"


def filter_buyouts_from_marks(mark_map: Dict[str, int]) -> Dict[str, int]:
    """
    Remove marks that look like buy-outs so they never generate
    CRITICAL missing-piece errors.
    """
    return {m: q for m, q in mark_map.items() if not is_buyout_text(m)}


def check_unexpected_buyouts(
    shipper_categories: Dict[str, Any],
    summary_weights: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Flag two conditions:
      1. A known buy-out category appears with quantity > 0 (data error?)
      2. Insulation appears with weight != 0
    """
    findings: List[Dict[str, Any]] = []
    summary_weights = summary_weights or {}

    for cat, pieces in (shipper_categories or {}).items():
        total_qty = sum(getattr(p, "quantity", 0) for p in (pieces or []))

        if is_buyout_category(cat) and total_qty > 0:
            findings.append({
                "severity": "WARNING",
                "category": cat,
                "quantity": total_qty,
                "message": (
                    f"Category '{cat}' is a standard Ascent buy-out but appears "
                    f"in the shipper with quantity {total_qty}. Confirm this is intentional."
                ),
            })

        # Insulation weight must be 0.00
        if is_insulation_category(cat):
            reported = None
            for k, v in summary_weights.items():
                if "insul" in k.lower():
                    reported = v
                    break
            if reported is not None and abs(reported) > 0.01:
                findings.append({
                    "severity": "WARNING",
                    "category": cat,
                    "message": (
                        f"Insulation weight is {reported} lbs. "
                        f"Ascent policy expects insulation weight = 0.00 (buy-out)."
                    ),
                    "expected": 0.0,
                    "actual": reported,
                })

    return findings


def buyout_policy_statement() -> str:
    """Short policy text for reports and INFO findings."""
    return (
        "Ascent supplies primary framing, secondary framing, sheeting, and trim. "
        "Always buy-outs (excluded from missing-piece checks; insulation weight expected 0.00): "
        "insulation, IMPs, joist/deck (New Millennium), walk doors, overhead/roll-up doors, "
        "windows, louvers, skylights, vents, and fans. "
        "Framed-opening steel (jambs/headers) remains in Ascent scope."
    )
