"""P0–P2 envelope kit rules: SS kit, trim openings, sealant, gutter straps, liner, FB clips."""

from __future__ import annotations

from types import SimpleNamespace

from chubby_checker.rules.envelope_kits import (
    check_ss_accessory_kit_incomplete,
    check_sealant_tape_required,
    check_gutter_strap_kit,
    check_liner_insulation_kit,
    check_flange_brace_clip_qty,
    check_ridge_peak_trim,
    check_purlin_extension_cap,
    check_clip_to_purlin_pancake_sds,
)
from chubby_checker.rules.accessory_rules import check_trim_vs_framed_openings
from chubby_checker.rules.engine import DiscrepancyEngine
from chubby_checker.rules.geometry_formulas import BuildingGeometry
from chubby_checker.rules.accessory_rules import check_trim_lengths_against_geometry, extract_trim_info


def _p(mark, description="", quantity=1, length_inches=None):
    return SimpleNamespace(
        mark=mark, description=description, quantity=quantity,
        length=None, length_inches=length_inches, weight=None, section=None,
    )


class TestSsAccessoryKit:
    def test_partial_kit_warning(self):
        cats = {
            "Standing Seam": [_p("CL", "standing seam panel", 40)],
            "SS Accessories": [_p("CL2124", "sliding clip high", 50)],
        }
        acc = {"sliding_clips": 50, "clip_screws": 100, "thermal_blocks": 0}
        findings = check_ss_accessory_kit_incomplete(
            categories=cats,
            ss_accessories=acc,
            drawings_text="standing seam roof insulated",
            shipper_raw_text="standing seam CL2124",
            panel_families={"standing_seam": True},
            has_insulation=True,
            clip_height="high",
        )
        warn = [f for f in findings if f["rule"] == "ss_accessory_kit_incomplete" and f["severity"] == "WARNING"]
        assert warn
        assert "thermal" in warn[0]["actual"].lower() or "eave" in warn[0]["actual"].lower() or "metal" in warn[0]["actual"].lower()

    def test_complete_kit_info(self):
        cats = {
            "Standing Seam": [_p("CL", "standing seam", 20)],
            "Closures": [_p("CL426", "metal inside", 10)],
            "Sealant": [_p("S1", "butyl sealant", 5)],
        }
        acc = {
            "sliding_clips": 40,
            "hi_eave_plates": 4,
            "hi_rake_supports": 4,
            "thermal_blocks": 40,
            "backup_plates_24": 8,
        }
        findings = check_ss_accessory_kit_incomplete(
            categories=cats,
            ss_accessories=acc,
            drawings_text="standing seam",
            panel_families={"standing_seam": True},
            has_insulation=True,
            clip_height="high",
        )
        assert any(f["severity"] == "INFO" and f["rule"] == "ss_accessory_kit_incomplete" for f in findings)


class TestTrimOpenings:
    def test_openings_without_jamb_trim(self):
        findings = check_trim_vs_framed_openings(
            categories={"Trim": [_p("ET1", "eave trim", 10)]},
            drawings_text="Framed opening FO-1 overhead door FO-2 walk door FO-3",
        )
        assert any(f["rule"] == "trim_vs_framed_openings" and f["severity"] == "WARNING" for f in findings)

    def test_trim_vs_geometry_underbill(self):
        geo = BuildingGeometry(length_ft=100, width_ft=60, eave_height_ft=16)
        # Only short eave length vs 200 ft expected
        cats = {"Trim": [_p("ET", "eave trim", 2, length_inches=120)]}  # 10 ft * 2 qty = 20 ft
        info = extract_trim_info(cats)
        findings = check_trim_lengths_against_geometry(info, geo)
        assert any(f["rule"] == "trim_vs_geometry" and f["severity"] == "WARNING" for f in findings)


class TestSealantGutterLiner:
    def test_sealant_required(self):
        findings = check_sealant_tape_required(
            categories={"Standing Seam": [_p("CL", "ss", 10)]},
            drawings_text="Apply tri-bead sealant at endlaps",
            panel_families={"standing_seam": True},
        )
        assert any(f["rule"] == "sealant_tape_required" and f["severity"] == "WARNING" for f in findings)

    def test_gutter_without_straps(self):
        cats = {"Trim": [_p("G1", "eave gutter", 20)]}
        findings = check_gutter_strap_kit(cats, drawings_text="eave gutter both sides")
        assert any(f["rule"] == "gutter_strap_kit" and f["severity"] == "WARNING" for f in findings)

    def test_liner_base_missing(self):
        findings = check_liner_insulation_kit(
            categories={"Panels": [_p("PL", "PL121 liner panel", 30)]},
            drawings_text="PL121 interior liner full height",
            panel_families={"liner": True, "pl121": True},
        )
        assert any(f["rule"] == "liner_base_member" for f in findings)


class TestFlangeBraceClips:
    def test_fb_without_sc197(self):
        cats = {"Flange Braces": [_p("FB1", "flange brace", 40)]}
        findings = check_flange_brace_clip_qty(cats)
        assert any(f["rule"] == "flange_brace_clip_qty" and f["severity"] == "WARNING" for f in findings)


class TestP2:
    def test_ridge_missing(self):
        findings = check_ridge_peak_trim(
            categories={"Standing Seam": [_p("CL", "ss", 10)]},
            drawings_text="ridge cap continuous",
        )
        assert any(f["rule"] == "ridge_peak_trim_qty" and f["severity"] == "WARNING" for f in findings)

    def test_purlin_extension_cap(self):
        findings = check_purlin_extension_cap(
            categories={"Cold Formed Steel": [_p("P1", "purlin", 20)]},
            drawings_text="purlin extension at canopy with cap channel",
        )
        assert any(f["rule"] == "purlin_extension_cap_channel" for f in findings)

    def test_pancake_sds(self):
        findings = check_clip_to_purlin_pancake_sds(
            categories={"Standing Seam": [_p("CL", "ss", 10)]},
            ss_accessories={"sliding_clips": 30, "clip_screws": 0},
            drawings_text="pancake SDS clip to purlin",
        )
        assert any(f["rule"] == "clip_purlin_pancake_sds" for f in findings)


class TestEngineWiresNewRules:
    def test_engine_runs_with_ss_partial(self):
        eng = DiscrepancyEngine(
            shipper_data={
                "categories": {
                    "Standing Seam": [_p("CL", "standing seam", 40)],
                    "SS Accessories": [_p("CL2124", "high sliding clip", 40)],
                },
                "ss_accessories": {"sliding_clips": 40, "clip_screws": 80},
                "raw_text": "standing seam CL2124",
                "summary_weights": {},
            },
            drawings_data={
                "raw_text": "standing seam roof Longlife fasteners ridge cap framed opening FO-1",
                "mark_quantity_map": {},
                "member_tables": {},
            },
        )
        findings = eng.run()
        rules = {f.rule for f in findings}
        assert "mark_by_mark" in rules
        assert "ss_accessory_kit_incomplete" in rules or "closures_metal_standing_seam" in rules or "closures_metal_sparse" in rules
