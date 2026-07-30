"""
Field-driven rules from job 25-13168 (J.A. Street) failures.
"""

from __future__ import annotations

from types import SimpleNamespace

from chubby_checker.rules.engine import DiscrepancyEngine
from chubby_checker.rules.standing_seam_system import (
    check_clip_eave_rake_height_consistency,
    check_standing_seam_system,
)
from chubby_checker.rules.sheeting_fasteners import check_fastener_finish_longlife
from chubby_checker.rules.bracing_rules import check_bracing_hardware_kit
from chubby_checker.rules.accessory_rules import check_closures_present
from chubby_checker.rules.seam_clip_library import load_seam_clip_library


def _p(mark, description="", quantity=1):
    return SimpleNamespace(
        mark=mark, description=description, quantity=quantity,
        length=None, length_inches=None, weight=None, section=None,
    )


class TestMarkByMarkWarning:
    def test_empty_drawings_map_is_warning(self):
        eng = DiscrepancyEngine(
            shipper_data={"categories": {"Cold Formed Steel": [_p("P1", "purlin", 5)]}, "raw_text": ""},
            drawings_data={"member_tables": {}, "mark_quantity_map": {}},
        )
        findings = eng.run()
        mm = [f for f in findings if f.rule == "mark_by_mark"]
        assert mm
        assert mm[0].severity == "WARNING"
        assert "could not run" in mm[0].message.lower() or "will not be detected" in mm[0].message.lower()

    def test_tables_but_all_filtered_is_warning(self):
        eng = DiscrepancyEngine(
            shipper_data={"categories": {}, "raw_text": ""},
            drawings_data={
                "member_tables": {
                    "Joists": [_p("BJ1", "bar joist New Millennium", 10)],
                },
                "mark_quantity_map": {"BJ1": 10},
            },
        )
        findings = eng.run()
        mm = [f for f in findings if f.rule == "mark_by_mark"]
        assert mm
        assert mm[0].severity == "WARNING"


class TestClipHeightMismatch:
    def test_high_clip_low_rake_warning(self):
        lib = load_seam_clip_library()
        high = lib["csp_sliding_high"]
        findings = check_clip_eave_rake_height_consistency(
            accessory_text="CL2124 sliding clip high CL7710 rake support low",
            ss_accessories={"hi_rake_supports": 0, "rake_supports_low": 4},
            clip_spec=high,
        )
        assert any(f["rule"] == "ss_clip_rake_height_mismatch" and f["severity"] == "WARNING" for f in findings)

    def test_high_clip_high_rake_no_mismatch(self):
        lib = load_seam_clip_library()
        high = lib["csp_sliding_high"]
        findings = check_clip_eave_rake_height_consistency(
            accessory_text="CL2124 CL7720 hi-rake support",
            ss_accessories={"hi_rake_supports": 4},
            clip_spec=high,
        )
        assert not any(f["rule"] == "ss_clip_rake_height_mismatch" for f in findings)

    def test_integrated_ss_check(self):
        findings = check_standing_seam_system(
            ss_accessories={
                "sliding_clips": 50,
                "clip_screws": 100,
                "thermal_blocks": 0,
                "rake_supports_low": 4,
                "hi_rake_supports": 0,
            },
            has_insulation=False,
            accessory_text="CL2124 high sliding clip standing seam CL7710 low rake",
            clip_key="csp_sliding_high",
        )
        assert any(f["rule"] == "ss_clip_rake_height_mismatch" for f in findings)


class TestLonglifeFasteners:
    def test_drawings_longlife_shipper_standard_fss(self):
        cats = {
            "Screws Fasteners": [
                _p("FSS10", "FSS10 self drill screw 1-1/4", 500),
            ],
        }
        findings = check_fastener_finish_longlife(
            cats,
            drawings_text="All roof lap fasteners shall be Longlife FSS10",
            shipper_raw_text="FSS10 standard",
        )
        assert any(
            f["rule"] == "fastener_finish_longlife" and f["severity"] == "WARNING"
            for f in findings
        )

    def test_shipper_has_fll_ok(self):
        cats = {"Screws": [_p("FLL10", "FLL Longlife screw", 200)]}
        findings = check_fastener_finish_longlife(
            cats,
            drawings_text="Long Life fasteners required",
            shipper_raw_text="FLL10 longlife",
        )
        assert any(f["rule"] == "fastener_finish_longlife" and f["severity"] == "INFO" for f in findings)


class TestBracingHardwareKit:
    def test_rods_without_hillsides(self):
        cats = {
            "Cables and Rods": [_p("RD1", "Rod bracing 3/4", 20)],
            "Bolts_Nuts_Washers": [],
        }
        findings = check_bracing_hardware_kit(cats, shipper_raw_text="rod bracing RD1")
        assert any(
            f["rule"] == "bracing_hardware_kit" and f["severity"] == "WARNING"
            for f in findings
        )

    def test_rods_with_hillsides_ok(self):
        cats = {
            "Cables and Rods": [_p("RD1", "Rod bracing", 10)],
            "Hardware": [_p("HS1", "Hillside washer", 20)],
            "Bolts_Nuts_Washers": [_p("N1", "Nut 3/4", 40), _p("W1", "Washer", 40)],
        }
        findings = check_bracing_hardware_kit(cats)
        warn = [f for f in findings if f["rule"] == "bracing_hardware_kit" and f["severity"] == "WARNING"]
        assert not warn


class TestSparseMetalClosures:
    def test_sparse_inside_only_warning(self):
        findings = check_closures_present(
            {
                "metal_total": 1,
                "metal_inside": 1,
                "metal_outside": 0,
                "end_dam": 0,
                "z_bird_stop": 0,
                "foam_total": 0,
                "total": 1,
            },
            has_panels=True,
            panel_count=40,
            panel_families={
                "standing_seam": True,
                "metal_required": True,
                "exposed_fastener": False,
                "foam_required": False,
                "suppress_metal_closures": False,
            },
        )
        assert any(
            f["rule"] == "closures_metal_sparse" and f["severity"] == "WARNING"
            for f in findings
        )

    def test_full_metal_kit_info(self):
        findings = check_closures_present(
            {
                "metal_total": 40,
                "metal_inside": 20,
                "metal_outside": 16,
                "end_dam": 4,
                "z_bird_stop": 0,
                "foam_total": 0,
                "total": 40,
            },
            has_panels=True,
            panel_count=40,
            panel_families={
                "standing_seam": True,
                "metal_required": True,
                "suppress_metal_closures": False,
            },
        )
        assert any(f["rule"] == "closures_metal_standing_seam" and f["severity"] == "INFO" for f in findings)
        assert not any(f["rule"] == "closures_metal_sparse" for f in findings)


class TestPlantCannotFab:
    def test_8x8_angle_not_routed(self):
        eng = DiscrepancyEngine(
            shipper_data={
                "categories": {"Cold Formed Steel": [_p("P1", "purlin", 10)]},
                "raw_text": "Cold Formed only",
            },
            drawings_data={
                "member_tables": {
                    "Misc": [_p("A1", "L8x8x1/2 connection angle 8x8x14ga", 2)],
                },
                "mark_quantity_map": {"A1": 2},
                "raw_text": "8x8x14ga angle required",
            },
        )
        findings = eng.run()
        assert any(f.rule == "plant_cannot_fab_not_routed" and f.severity == "WARNING" for f in findings)
