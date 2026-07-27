"""
Buy-out rules for Ascent Buildings jobs.

Ascent supplies:
  - Primary / main framing
  - Secondary framing (purlins, girts, eave struts, etc.)
  - Sheeting (roof & wall panels)
  - Trim

Always buy-outs (do not expect in Ascent shipper, or expect zero weight):
  - Insulation
  - IMPs (Insulated Metal Panels) – Kingspan, AWIP, Nucor, etc.
  - Joist & Deck (New Millennium Building Systems) – framing by others
  - Walk doors
  - Skylights
  - Vents (roof and wall)
  - Fans
  - Overhead / roll-up doors
  - Windows
  - Louvers
"""

from typing import Dict, List, Set, Any

# Categories / keywords that are ALWAYS buy-outs for Ascent
BUYOUT_KEYWORDS: List[str] = [
    # Insulation
    "insulation", "skyliner", "bay insulation", "faced insulation", "unfaced",
    "thermal insulation", "blanket insulation",
    # IMPs
    "imp", "insulated metal panel", "kingspan", "awip", "all weather insulated",
    "nucor panel", "insulated panel",
    # Joist / Deck
    "joist", "bar joist", "steel joist", "new millennium", "deck", "metal deck",
    "roof deck", "floor deck",
    # Doors & openings (typically by others)
    "walk door", "man door", "personnel door", "overhead door", "roll-up",
    "rollup", "rolling door", "sectional door",
    "window", "louver", "louvre",
    # Skylights, vents, fans
    "skylight", "sky light", "roof vent", "wall vent", "ridge vent",
    "exhaust fan", "supply fan", "fan",
]

# Normalized buy-out category names that may appear on shipper index
BUYOUT_CATEGORIES: Set[str] = {
    "insulation",
    "bar joists",
    "joists",
    "deck",
    "metal deck",
    "imp",
    "insulated panels",
}


def is_buyout_text(text: str) -> bool:
    """Return True if the text clearly indicates a buy-out item."""
    if not text:
        return False
    t = text.lower()
    return any(k in t for k in BUYOUT_KEYWORDS)


def is_buyout_category(category: str) -> bool:
    if not category:
        return False
    c = category.lower().strip()
    if c in BUYOUT_CATEGORIES:
        return True
    return is_buyout_text(c)


def filter_buyouts_from_marks(mark_map: Dict[str, int]) -> Dict[str, int]:
    """Remove marks that look like buy-outs so they do not generate missing-piece errors."""
    return {m: q for m, q in mark_map.items() if not is_buyout_text(m)}


def check_unexpected_buyouts(shipper_categories: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Flag if a known buy-out category appears with significant weight or quantity
    in an Ascent shipper (possible data entry error).
    """
    findings = []
    for cat, pieces in (shipper_categories or {}).items():
        if is_buyout_category(cat):
            total_qty = sum(getattr(p, "quantity", 0) for p in pieces)
            if total_qty > 0:
                findings.append({
                    "category": cat,
                    "quantity": total_qty,
                    "message": f"Category '{cat}' is a standard Ascent buy-out but appears in the shipper with qty {total_qty}.",
                })
    return findings
