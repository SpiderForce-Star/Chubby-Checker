"""
Unit tests for Ascent member part-code decoder.

Locks in the corrected Cee/Zee/Open Cee grammar from the 2026-07-27 Heavy Grok
audit so the previous depth=82 regression cannot return.
"""

from __future__ import annotations

import pytest

from chubby_checker.rules.ascent_member_catalog import (
    decode_zee_cee,
    decode_eave_strut,
    decode_built_up,
    decode_pipe,
    decode_tube,
    decode_member,
    weight_for_length,
    is_ascent_secondary_code,
    CEE_PLF,
    ZEE_PLF,
    OPEN_CEE_PLF,
    EAVE_STRUT_PLF,
    BUILTUP_THICK,
)


# ---------------------------------------------------------------------------
# Cee / Zee — corrected grammar
# ---------------------------------------------------------------------------

class TestDecodeZeeCee:
    """C82516 must be 8\" × 2.5\" × 16 ga — never depth 82."""

    @pytest.mark.parametrize(
        "code, kind, depth, flange, gauge, plf",
        [
            ("C82516", "cee", 8.0, 2.5, 16, 2.61),
            ("C82514", "cee", 8.0, 2.5, 14, 3.23),
            ("C82512", "cee", 8.0, 2.5, 12, 4.65),
            ("C83516", "cee", 8.0, 3.5, 16, 2.98),
            ("C83514", "cee", 8.0, 3.5, 14, 3.69),
            ("C83512", "cee", 8.0, 3.5, 12, 5.32),
            ("C102516", "cee", 10.0, 2.5, 16, 2.98),
            ("C103512", "cee", 10.0, 3.5, 12, 5.98),
            ("C123514", "cee", 12.0, 3.5, 14, 4.61),
            ("C123512", "cee", 12.0, 3.5, 12, 6.65),
            ("Z82516", "zee", 8.0, 2.5, 16, 2.61),
            ("Z103512", "zee", 10.0, 3.5, 12, 5.98),
            ("Z123514", "zee", 12.0, 3.5, 14, 4.61),
            ("Z122512", "zee", 12.0, 2.5, 12, 5.98),
        ],
    )
    def test_valid_cee_zee(self, code, kind, depth, flange, gauge, plf):
        d = decode_zee_cee(code)
        assert d is not None, f"{code} should parse"
        assert d.kind == kind
        assert d.depth_in == depth
        assert d.flange_in == flange
        assert d.gauge == gauge
        assert d.weight_plf == plf
        assert d.details["part"] == code.upper()
        assert d.details["flange_code"] in ("25", "35")

    def test_case_and_whitespace_tolerance(self):
        for raw in ("c82516", "C82516 ", " c82516", "C-825-16"):
            d = decode_zee_cee(raw)
            assert d is not None, f"{raw!r} should parse"
            assert d.depth_in == 8.0
            assert d.flange_in == 2.5
            assert d.gauge == 16

    @pytest.mark.parametrize(
        "bad",
        [
            "C82599",   # invalid gauge
            "C82515",   # invalid gauge
            "C92516",   # invalid depth
            "C72516",   # invalid depth
            "C8216",    # too short / wrong shape
            "C825160",  # too long
            "X82516",   # wrong letter
            "C24516",   # invalid flange code
            "",
            "NOPE",
        ],
    )
    def test_invalid_cee_zee_rejected(self, bad):
        assert decode_zee_cee(bad) is None

    def test_regression_depth_not_82(self):
        """The pre-fix bug decoded C82516 as depth=82. Guard against regression."""
        d = decode_zee_cee("C82516")
        assert d is not None
        assert d.depth_in != 82
        assert d.depth_in == 8.0
        assert d.flange_in != 5
        assert d.flange_in == 2.5


# ---------------------------------------------------------------------------
# Open Cee
# ---------------------------------------------------------------------------

class TestDecodeOpenCee:
    @pytest.mark.parametrize(
        "code, depth, gauge, plf",
        [
            ("U82516", 8.25, 16, 2.61),
            ("U82514", 8.25, 14, 3.23),
            ("U82512", 8.25, 12, 4.65),
            ("U102516", 10.25, 16, 2.98),
            ("U102512", 10.25, 12, 5.32),
            ("U122514", 12.25, 14, 4.15),
            ("U122512", 12.25, 12, 5.98),
        ],
    )
    def test_valid_open_cee(self, code, depth, gauge, plf):
        d = decode_zee_cee(code)
        assert d is not None
        assert d.kind == "open_cee"
        assert d.depth_in == depth
        assert d.flange_in == 3.0
        assert d.gauge == gauge
        assert d.weight_plf == plf

    @pytest.mark.parametrize("bad", ["U92516", "U82599", "U82515", "U722516"])
    def test_invalid_open_cee_rejected(self, bad):
        assert decode_zee_cee(bad) is None


# ---------------------------------------------------------------------------
# Eave strut
# ---------------------------------------------------------------------------

class TestDecodeEaveStrut:
    @pytest.mark.parametrize(
        "code, depth, gauge, plf, slope",
        [
            ("06436", 6.0, 16, 2.61, ""),
            ("06434", 6.0, 14, 3.22, ""),
            ("06432", 6.0, 12, 4.65, ""),
            ("08534", 8.0, 14, 3.92, ""),
            ("08532", 8.0, 12, 5.65, ""),
            ("08534SU", 8.0, 14, 3.92, "SU"),
            ("08534DU", 8.0, 14, 3.92, "DU"),
            ("10534", 10.0, 14, 4.61, ""),
            ("10532", 10.0, 12, 6.32, ""),
            ("10532DD", 10.0, 12, 6.32, "DD"),
            ("10532---", 10.0, 12, 6.32, ""),  # dashes stripped by _norm
            ("08534---", 8.0, 14, 3.92, ""),
        ],
    )
    def test_valid_eave(self, code, depth, gauge, plf, slope):
        d = decode_eave_strut(code)
        assert d is not None, f"{code} should parse"
        assert d.kind == "eave_strut"
        assert d.depth_in == depth
        assert d.gauge == gauge
        assert d.weight_plf == plf
        assert d.details["slope_code"] == slope

    def test_unknown_eave_base_rejected(self):
        assert decode_eave_strut("99999") is None
        assert decode_eave_strut("12345") is None


# ---------------------------------------------------------------------------
# Built-up
# ---------------------------------------------------------------------------

class TestDecodeBuiltUp:
    def test_valid_builtup(self):
        d = decode_built_up("B22d0g")
        assert d is not None
        assert d.kind == "built_up"
        assert d.depth_in == 22.0
        assert d.details["web_thickness"] == 0.3125
        assert d.details["flange_width"] == 10.0
        assert d.details["flange_thickness"] == 0.625

    def test_thickness_letter_e_and_f(self):
        """Regression: e/f must exist after thickness-map fix."""
        d = decode_built_up("B22e0g")
        assert d is not None
        assert d.details["web_thickness"] == 0.375
        d = decode_built_up("B18f5c")
        assert d is not None
        assert d.details["web_thickness"] == 0.500

    @pytest.mark.parametrize("code", ["B09a0a", "B40a0a", "B99z9z"])
    def test_out_of_range_or_bad_format_rejected(self, code):
        assert decode_built_up(code) is None

    def test_continuous_thickness_map(self):
        assert "e" in BUILTUP_THICK and "f" in BUILTUP_THICK
        assert BUILTUP_THICK["e"] == 0.3750
        assert BUILTUP_THICK["f"] == 0.5000
        assert BUILTUP_THICK["g"] == 0.6250


# ---------------------------------------------------------------------------
# Pipe / Tube
# ---------------------------------------------------------------------------

class TestDecodePipeTube:
    def test_stock_pipe(self):
        d = decode_pipe("PP6188")
        assert d is not None
        assert d.kind == "pipe"
        assert d.depth_in == 6.625
        assert d.details["wall"] == 0.188
        assert d.details["stock"] is True

    def test_generic_pipe(self):
        d = decode_pipe("PP8322")
        assert d is not None
        assert d.kind == "pipe"
        assert d.depth_in == 8.625

    def test_tube_ts_prefix(self):
        d = decode_tube("TS080080c")
        assert d is not None
        assert d.kind == "tube"
        assert d.depth_in == 8.0
        assert d.details["width"] == 8.0
        assert d.details["wall"] == 0.25

    def test_tube_t_prefix(self):
        d = decode_tube("T060060e")
        assert d is not None
        assert d.depth_in == 6.0
        assert d.details["wall"] == 0.375

    def test_bad_pipe_rejected(self):
        d = decode_pipe("XYZ")
        assert d is None


# ---------------------------------------------------------------------------
# decode_member router
# ---------------------------------------------------------------------------

class TestDecodeMember:
    @pytest.mark.parametrize(
        "code, kind",
        [
            ("C82516", "cee"),
            ("Z103512", "zee"),
            ("U122514", "open_cee"),
            ("08534---", "eave_strut"),
            ("10532SU", "eave_strut"),
            ("B22d0g", "built_up"),
            ("PP6188", "pipe"),
            ("TS080080c", "tube"),
            ("T080080c", "tube"),
            ("NOPE", "unknown"),
            ("C82599", "unknown"),
            ("C92516", "unknown"),
        ],
    )
    def test_routing(self, code, kind):
        d = decode_member(code)
        assert d.kind == kind, f"{code}: expected {kind}, got {d.kind}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_weight_for_length(self):
        # C82516 = 2.61 plf × 20 ft = 52.2
        w = weight_for_length("C82516", 20.0)
        assert w == pytest.approx(52.2)
        assert weight_for_length("NOPE", 10.0) is None

    def test_is_ascent_secondary_code(self):
        assert is_ascent_secondary_code("C82516") is True
        assert is_ascent_secondary_code("Z103512") is True
        assert is_ascent_secondary_code("U82516") is True
        assert is_ascent_secondary_code("08534---") is True
        assert is_ascent_secondary_code("B22d0g") is False
        assert is_ascent_secondary_code("PP6188") is False
        assert is_ascent_secondary_code("NOPE") is False


# ---------------------------------------------------------------------------
# PLF table integrity (catalog data must match decoder expectations)
# ---------------------------------------------------------------------------

class TestCatalogTables:
    def test_cee_plf_keys_decode(self):
        for code in CEE_PLF:
            d = decode_zee_cee(code)
            assert d is not None, f"CEE_PLF key {code} failed to decode"
            assert d.weight_plf == CEE_PLF[code]

    def test_zee_plf_keys_decode(self):
        for code in ZEE_PLF:
            d = decode_zee_cee(code)
            assert d is not None, f"ZEE_PLF key {code} failed to decode"
            assert d.weight_plf == ZEE_PLF[code]

    def test_open_cee_plf_keys_decode(self):
        for code in OPEN_CEE_PLF:
            d = decode_zee_cee(code)
            assert d is not None, f"OPEN_CEE_PLF key {code} failed to decode"
            assert d.weight_plf == OPEN_CEE_PLF[code]

    def test_eave_plf_keys_decode(self):
        for base in EAVE_STRUT_PLF:
            d = decode_eave_strut(base)
            assert d is not None, f"EAVE_STRUT_PLF key {base} failed to decode"
            assert d.weight_plf == EAVE_STRUT_PLF[base]
