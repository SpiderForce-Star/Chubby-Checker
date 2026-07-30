"""Skylight OSHA / fall-protection boilerplate must not appear in checks."""

from __future__ import annotations

from chubby_checker.utils.boilerplate import (
    is_skylight_osha_boilerplate,
    is_non_piece_mark,
    strip_skylight_osha_paragraphs,
)
from chubby_checker.rules.engine import DiscrepancyEngine
from chubby_checker.parsers.drawings_parser import DrawingsParser
from types import SimpleNamespace


class TestSkylightOshaFilter:
    def test_detects_osha_skylight_paragraph(self):
        text = (
            "OSHA requires that all skylights be protected against falls. "
            "Provide screens or covers per 29 CFR 1926 before roof work."
        )
        assert is_skylight_osha_boilerplate(text) is True

    def test_normal_mark_not_filtered(self):
        assert is_non_piece_mark("RF1", "Rigid frame rafter") is False
        assert is_skylight_osha_boilerplate("R-Loc panel 26 ga") is False

    def test_long_note_mark_rejected(self):
        mark = "OSHA WARNING Skylights must have fall protection screens installed"
        assert is_non_piece_mark(mark, "") is True

    def test_strip_removes_paragraph(self):
        body = (
            "Building is 100x200 clear span.\n\n"
            "OSHA requires skylight fall protection and safety screens on all roof openings.\n\n"
            "Standing seam roof panels Central-Loc."
        )
        cleaned = strip_skylight_osha_paragraphs(body)
        assert "OSHA" not in cleaned
        assert "skylight fall" not in cleaned.lower()
        assert "Standing seam" in cleaned
        assert "100x200" in cleaned

    def test_engine_drops_osha_finding(self):
        eng = DiscrepancyEngine(shipper_data={"categories": {}}, drawings_data={})
        eng._add({
            "severity": "INFO",
            "category": "Notes",
            "message": "OSHA skylight fall protection screens required on all roof openings.",
            "rule": "test_osha",
        })
        assert eng.discrepancies == []

    def test_drawings_row_skips_osha_mark(self):
        p = DrawingsParser.__new__(DrawingsParser)
        piece = p._row_to_piece(
            ["1", "OSHA WARNING: Protect skylights against falls per safety code", "note"],
            {"qty": 0, "mark": 1, "desc": 2},
            "Notes",
        )
        assert piece is None
