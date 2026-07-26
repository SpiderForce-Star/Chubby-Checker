"""Shared length parsing utilities for Ascent drawings and shippers."""

from typing import Optional, Tuple
import re


def parse_length_to_inches(length_str: str) -> Optional[float]:
    """
    Convert Ascent-style length strings to total inches.

    Examples:
      29'-7 3/8"   → 355.375
      26'-11 1/2"  → 323.5
      12'-0"       → 144.0
      41'-8 3/4"   → 500.75
    """
    if not length_str:
        return None

    s = (
        str(length_str)
        .strip()
        .replace("\u201d", '"')
        .replace("\u2019", "'")
        .replace("“", '"')
        .replace("‘", "'")
    )

    # Full pattern: feet'-inches [fraction]"
    m = re.match(
        r"(\d+)\s*'\s*[-\u2013]?\s*(\d+)?\s*(?:(\d+)\s*/\s*(\d+))?\s*\"?",
        s,
    )
    if m:
        feet = int(m.group(1))
        inches = int(m.group(2) or 0)
        frac = 0.0
        if m.group(3) and m.group(4):
            frac = float(m.group(3)) / float(m.group(4))
        return round(feet * 12.0 + inches + frac, 4)

    # Feet only
    m2 = re.match(r"(\d+)\s*'", s)
    if m2:
        return float(m2.group(1)) * 12.0

    # Pure inches or decimal
    try:
        return float(s.replace('"', ""))
    except ValueError:
        return None


def lengths_match(a: Optional[float], b: Optional[float], tolerance: float = 0.25) -> bool:
    """Return True if both lengths are present and within tolerance (default 1/4\")."""
    if a is None or b is None:
        return True  # cannot compare – treat as match
    return abs(a - b) <= tolerance
