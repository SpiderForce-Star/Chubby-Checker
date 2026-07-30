"""
PEMB component detection + drawings→shipper cross-check tests.

Keeps Chubby Checker aware of pre-engineered systems implied on Final Drawings
when Complete Shippers omit categories/marks.
"""

from __future__ import annotations

from types import SimpleNamespace

from chubby_checker.rules.pemb_components import (
    detect_pemb_signals,
    cross_check_drawings_to_shipper,
)
from chubby_checker.rules.engine import DiscrepancyEngine
from chubby_checker.parsers.drawings_parser import DrawingsParser


def _piece(mark, description="", quantity=1):
    return SimpleNamespace(
        mark=mark, description=description, quantity=quantity,
        length=None, length_inches=None, weight=None,
    )


class TestDetectPembSignals:
    def test_standing_seam_double_lok_vsr6(self):
        s = detect_pemb_signals("Double Lok roof with VSR6 architectural standing seam")
        assert s["standing_seam"] is True
        assert "standing_seam" in s["panel_families"]

    def test_exposed_avp_rloc(self):
        s = detect_pemb_signals("AVP wall panels and R-Loc / PBR roof screw-down")
        assert s["exposed_fastener"] is True

    def test_imp_and_bdeck(self):
        s = detect_pemb_signals(
            "Kingspan insulated metal panels; New Millennium B-deck and bar joists"
        )
        assert s["imp"] is True
        assert s["bdeck_joist"] is True

    def test_crane_mezz_primary(self):
        s = detect_pemb_signals(
            "Rigid frame clear span with crane runway beam and mezzanine floor beams"
        )
        assert s["primary_framing"] is True
        assert s["crane"] is True
        assert s["mezzanine"] is True

    def test_closures_and_sealant(self):
        s = detect_pemb_signals("Metal closures CL426; foam RLCLOUTG; butyl sealant; self-drill screws")
        assert s["metal_closures_mentioned"] is True
        assert s["foam_closures_mentioned"] is True
        assert s["sealant_mentioned"] is True
        assert s["fasteners_mentioned"] is True

    def test_multi_vendor_hints(self):
        s = detect_pemb_signals("American Buildings drawings with MBCI panels and McElroy trim")
        assert "american buildings" in s["vendors_hinted"]
        assert "mbci" in s["vendors_hinted"]

    def test_masterline_shadow_rib_liner(self):
        s = detect_pemb_signals("MasterLine-16 walls, Shadow Rib, PL121 liner")
        assert s["concealed_wall"] is True
        assert s["liner"] is True


class TestDrawingsToShipperCrossCheck:
    def test_crane_on_drawings_missing_shipper(self):
        drawings = detect_pemb_signals("crane runway beam supports")
        findings = cross_check_drawings_to_shipper(
            drawings,
            shipper_categories={"Cold Formed Steel": [_piece("P1", "purlin", 10)]},
        )
        assert any(f["rule"] == "drawings_shipper_crane" and f["severity"] == "WARNING" for f in findings)

    def test_ss_on_drawings_missing_shipper(self):
        drawings = detect_pemb_signals("Central-Loc standing seam roof VS16")
        findings = cross_check_drawings_to_shipper(
            drawings,
            shipper_categories={"Cold Formed Steel": [_piece("G1", "girt", 8)]},
            shipper_families={"standing_seam": False, "exposed_fastener": False},
        )
        assert any(f["rule"] == "drawings_shipper_standing_seam" for f in findings)

    def test_ss_present_no_warning(self):
        drawings = detect_pemb_signals("standing seam SSR roof")
        findings = cross_check_drawings_to_shipper(
            drawings,
            shipper_categories={"Standing Seam": [_piece("CL", "Central Loc", 40)]},
            shipper_families={"standing_seam": True, "any_panel": True},
        )
        assert not any(f["rule"] == "drawings_shipper_standing_seam" for f in findings)

    def test_bdeck_info(self):
        drawings = detect_pemb_signals("New Millennium B-deck structural deck")
        findings = cross_check_drawings_to_shipper(drawings, shipper_categories={})
        assert any(f["rule"] == "drawings_shipper_bdeck_joist" and f["severity"] == "INFO" for f in findings)

    def test_sealant_info_when_cladding(self):
        drawings = detect_pemb_signals("R-Loc wall panels and eave trim")
        findings = cross_check_drawings_to_shipper(
            drawings,
            shipper_categories={"Standard Panels": [_piece("RL", "R-Loc", 20)]},
            shipper_families={"exposed_fastener": True, "any_panel": True},
        )
        assert any(f["rule"] == "drawings_shipper_sealant" for f in findings)


class TestDrawingsParserSignals:
    def test_extract_notes_sets_flags(self):
        p = DrawingsParser.__new__(DrawingsParser)
        p.notes = []
        p.building_info = {}
        p.panel_info = {}
        p.raw_pages = []
        p._extract_notes_and_info(
            "MAIN FRAME LINE A — Double Lok standing seam, AVP walls, "
            "crane runway beam, mezzanine, New Millennium joists"
        )
        assert p.building_info.get("has_crane") is True
        assert p.building_info.get("has_mezzanine") is True
        assert p.building_info.get("has_standing_seam") is True
        assert p.building_info.get("has_exposed_panels") is True
        assert p.building_info.get("has_bdeck_joist") is True
        assert p.panel_info.get("type") == "Double Lok"


class TestEngineDrawingsShipper:
    def test_engine_emits_drawings_shipper_rules(self):
        shipper = {
            "categories": {
                "Cold Formed Steel": [_piece("P1", "Z purlin", 12)],
            },
            "raw_text": "Cold Formed Steel only",
            "ss_accessories": {},
            "summary_weights": {},
        }
        drawings = {
            "member_tables": {},
            "mark_quantity_map": {},
            "has_crane": True,
            "has_standing_seam": True,
            "pemb_signals": detect_pemb_signals(
                "standing seam roof with crane runway beam and rigid frame"
            ),
            "raw_text": "standing seam roof crane runway rigid frame",
        }
        findings = DiscrepancyEngine(shipper_data=shipper, drawings_data=drawings).run()
        rules = {f.rule for f in findings}
        assert "system_crane" in rules or "drawings_shipper_crane" in rules
        assert "drawings_shipper_standing_seam" in rules or "drawings_shipper_primary" in rules
