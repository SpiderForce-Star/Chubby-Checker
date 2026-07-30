"""
Filter erection-drawing / shipper boilerplate that must not drive QC findings.

Skylight OSHA / fall-protection notes already live in Ascent erection manuals;
Chubby Checker must not surface them as marks, findings, or report paragraphs.
"""

from __future__ import annotations

import re
from typing import Iterable, List

# Phrases that identify safety/OSHA skylight note paragraphs (not BOM marks)
_SKYLIGHT_OSHA_PATTERNS = (
    re.compile(r"\bosha\b", re.I),
    re.compile(r"fall\s+protect", re.I),
    re.compile(r"fall\s+hazard", re.I),
    re.compile(r"skylight\w*.{0,40}(screen|guard|protect|cover|cage)", re.I),
    re.compile(r"(screen|guard|protect|cover|cage).{0,40}skylight", re.I),
    re.compile(r"skylight\w*.{0,60}\bosha\b", re.I),
    re.compile(r"\bosha\b.{0,80}skylight", re.I),
    re.compile(r"29\s*CFR", re.I),  # OSHA regulatory cites often on notes
    re.compile(r"safety\s+net", re.I),
    re.compile(r"roof\s+opening.{0,40}(protect|guard|cover)", re.I),
)

# Lines that are clearly narrative notes rather than piece marks
_NOTE_MARK_RE = re.compile(
    r"^(note|notes|warning|caution|attention|see\s+erection|refer\s+to)\b",
    re.I,
)


def is_skylight_osha_boilerplate(text: str) -> bool:
    """True if text is (or contains) skylight OSHA / fall-protection note language."""
    t = (text or "").strip()
    if not t:
        return False
    # Require skylight or roof-opening context for generic OSHA/CFR hits
    low = t.lower()
    has_sky_context = any(
        k in low for k in ("skylight", "sky light", "roof opening", "roof open")
    )
    for pat in _SKYLIGHT_OSHA_PATTERNS:
        if pat.search(t):
            # Pure OSHA without skylight still drop if fall-protect + roof context
            if pat.pattern.lower() in (r"\bosha\b", r"29\s*cfr") and not has_sky_context:
                if "fall" not in low and "skylight" not in low:
                    continue
            return True
    if has_sky_context and any(k in low for k in ("osha", "fall protect", "fall hazard", "29 cfr")):
        return True
    return False


def is_non_piece_mark(mark: str, description: str = "") -> bool:
    """
    True if mark/description should never enter mark-by-mark or member inventory.
    Catches note paragraphs mis-parsed into the Mark column.
    """
    m = (mark or "").strip()
    d = (description or "").strip()
    blob = f"{m} {d}".strip()
    if not blob:
        return True
    if is_skylight_osha_boilerplate(blob):
        return True
    # Extremely long "marks" are almost always notes/paragraphs
    if len(m) > 40 or m.count(" ") >= 5:
        return True
    if _NOTE_MARK_RE.match(m) or _NOTE_MARK_RE.match(d[:40] if d else ""):
        # Allow short NOTE-1 style marks only if short
        if len(m) > 24 or is_skylight_osha_boilerplate(d):
            return True
    return False


def strip_skylight_osha_paragraphs(text: str) -> str:
    """Remove skylight OSHA / fall-protection paragraphs from free text."""
    if not text:
        return text
    # Split on blank lines and long sentence breaks
    parts = re.split(r"\n\s*\n|(?<=\.)\s+(?=[A-Z])", text)
    kept: List[str] = []
    for part in parts:
        if is_skylight_osha_boilerplate(part):
            continue
        # Also drop single lines that are pure boilerplate
        lines = []
        for line in part.splitlines():
            if is_skylight_osha_boilerplate(line):
                continue
            lines.append(line)
        chunk = "\n".join(lines).strip()
        if chunk:
            kept.append(chunk)
    return "\n\n".join(kept)


def filter_boilerplate_findings(findings: Iterable[dict]) -> List[dict]:
    """Drop discrepancy dicts whose message is skylight OSHA boilerplate."""
    out: List[dict] = []
    for f in findings:
        msg = f"{f.get('message', '')} {f.get('mark', '')} {f.get('category', '')}"
        if is_skylight_osha_boilerplate(msg):
            continue
        if is_non_piece_mark(str(f.get("mark") or ""), str(f.get("message") or "")):
            # Only skip if message itself looks like the note, not every long message
            if is_skylight_osha_boilerplate(str(f.get("message") or "")):
                continue
        out.append(f)
    return out
