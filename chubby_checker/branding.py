"""
Branding assets for Chubby Checker.

Resolves the official Ascent Buildings logo and product names for CLI, PDF
reports, and watermarks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

PRODUCT_NAME = "Chubby Checker"
COMPANY_NAME = "Ascent Buildings"

# Candidate logo paths relative to repo root / install layout
_LOGO_CANDIDATES = (
    "assets/branding/ascent_logo.jpg",
    "assets/branding/ascent_logo.png",
    "assets/branding/ascent_buildings_llc_logo.jpg",
    "assets/branding/app_icon.png",
    "ascent_buildings_llc_logo.jpg",
    "ascent_logo.jpg",
    "ascent_logo.png",
)


def _repo_roots() -> list[Path]:
    """Possible roots: package parent, cwd, and parents of cwd."""
    roots: list[Path] = []
    here = Path(__file__).resolve()
    # chubby_checker/branding.py -> repo root is parents[1]
    roots.append(here.parents[1])
    roots.append(Path.cwd())
    for p in Path.cwd().resolve().parents[:3]:
        roots.append(p)
    # de-dupe preserving order
    seen = set()
    out = []
    for r in roots:
        key = str(r)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def find_logo(explicit: Optional[str | Path] = None) -> Optional[Path]:
    """
    Locate the Ascent Buildings logo file.

    Search order:
      1. Explicit path argument / ASCENT_LOGO_PATH env
      2. Known relative paths under repo roots
    """
    import os

    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p.resolve()

    env = os.environ.get("ASCENT_LOGO_PATH")
    if env:
        p = Path(env)
        if p.is_file():
            return p.resolve()

    for root in _repo_roots():
        for rel in _LOGO_CANDIDATES:
            candidate = root / rel
            if candidate.is_file():
                return candidate.resolve()
    return None


def logo_exists() -> bool:
    return find_logo() is not None
