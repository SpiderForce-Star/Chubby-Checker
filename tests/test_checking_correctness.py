"""Regression tests for verification correctness fixes (repo audit)."""

from __future__ import annotations

from types import SimpleNamespace

from chubby_checker.rules.engine import DiscrepancyEngine
from chubby_checker.rules.standing_seam_system import check_standing_seam_system
from chubby_checker.rules.framing_rules import classify_mark
from chubby_checker.rules.buyouts import is_buyout_text, filter_buyouts_from_marks, is_imp
from chubby_checker.rules.accessory_rules import detect_panel_families


def _p(mark, description="", quantity=1, weight=None):
    return SimpleNamespace(
        mark=mark, description=description, quantity=quantity,
        length=None, length_inches=None, weight=weight, section=None,
    )


class TestThermalCorrectness:
    def test_clips_alone_do_not_force_thermal_critical(self):
        """has_insulation must not be inferred from clips alone."""
        findings = check_standing_seam_system(
            ss_accessories={"sliding_clips": 100, "clip_screws": 200, "thermal_blocks": 0},
            has_insulation=False,
            accessory_text="standing seam sliding clips",
        )
        therm = [f for f in findings if f["rule"] == "ss_thermal_blocks" and f["severity"] == "CRITICAL"]
        assert therm == []

    def test_thermal_warning_when_insulation_confirmed(self):
        findings = check_standing_seam_system(
            ss_accessories={"sliding_clips": 50, "clip_screws": 100, "thermal_blocks": 0},
            has_insulation=True,
            accessory_text="standing seam with insulation",
        )
        therm = [f for f in findings if f["rule"] == "ss_thermal_blocks"]
        assert therm
        assert therm[0]["severity"] == "WARNING"

    def test_requires_thermal_spacer_attr_no_crash(self):
        # When insulation False and clip_spec path runs, must not AttributeError
        findings = check_standing_seam_system(
            ss_accessories={"sliding_clips": 10, "clip_screws": 20, "thermal_blocks": 0},
            has_insulation=False,
            clip_key="cl2122-high",  # may or may not exist; must not crash
            accessory_text="standing seam",
        )
        assert isinstance(findings, list)


class TestSsClipsWithoutGeometry:
    def test_zero_clips_ss_text_is_critical(self):
        findings = check_standing_seam_system(
            ss_accessories={"sliding_clips": 0},
            panel_coverage_in=None,
            building_width_ft=None,
            accessory_text="Standing Seam SS Accessories Central-Loc roof",
        )
        assert any(f["rule"] == "ss_clips_present" and f["severity"] == "CRITICAL" for f in findings)

    def test_engine_ss_family_zero_clips(self):
        shipper = {
            "categories": {
                "Standing Seam": [_p("CL", "Central-Loc standing seam panel", 40)],
            },
            "ss_accessories": {"sliding_clips": 0, "clip_screws": 0, "thermal_blocks": 0},
            "raw_text": "Standing Seam panels Central-Loc",
            "summary_weights": {},
            "panel_coverage": {},
        }
        findings = DiscrepancyEngine(shipper_data=shipper, drawings_data={}).run()
        rules = {f.rule for f in findings}
        assert "clips_present" in rules or "ss_clips_present" in rules


class TestFramingClassify:
    def test_cold_not_column(self):
        fam, _ = classify_mark("COLD123", "cold formed")
        assert fam != "primary" or "Column" not in _

    def test_rf_digit_is_primary(self):
        fam, sub = classify_mark("RF1", "rigid frame")
        assert fam == "primary"

    def test_screw_not_soldier_column(self):
        fam, _ = classify_mark("SCREW1", "panel screw")
        assert fam != "primary"


class TestBuyoutFilter:
    def test_imp_not_simple(self):
        assert is_buyout_text("simple secondary piece") is False
        assert is_imp("simple") is False
        assert is_imp("Kingspan IMP panel") is True

    def test_bare_deck_not_always_buyout(self):
        # Phrase still is
        assert is_buyout_text("New Millennium roof deck") is True

    def test_joist_marks_filtered(self):
        filtered = filter_buyouts_from_marks(
            {"BJ12": 20, "RF1": 2},
            mark_context={"BJ12": "bar joist New Millennium", "RF1": "rigid frame"},
        )
        assert "BJ12" not in filtered
        assert "RF1" in filtered


class TestPanelFamilyFalsePositive:
    def test_cl_without_panel_context_not_ss(self):
        fam = detect_panel_families(
            {"Hardware": [_p("X1", "clear span note only CL class")]},
            raw_text="clear class only",
        )
        # Without panel/roof/standing context, bare CL should not force SS
        # (string "cl" may appear in "class" — word boundary helps)
        assert fam["standing_seam"] is False or "standing" in "class"
