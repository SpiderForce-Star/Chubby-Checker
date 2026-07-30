"""
Panel family detection and metal-vs-foam closure classification tests.

Locks in domain rules:
  - Standing seam → metal closures (CL426, HW-4xx, SPED16, …)
  - Exposed fastener → foam (RLCLOUTG, RLCLINGL, …)
  - B-deck / IMP → no SS metal-closure CRITICAL
  - R-Loc foam SKUs must never classify as metal
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from chubby_checker.rules.accessory_rules import (
    extract_closure_counts,
    detect_panel_families,
    check_closures_present,
)
from chubby_checker.rules.engine import DiscrepancyEngine


def _piece(mark: str, description: str = "", quantity: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        mark=mark,
        description=description,
        quantity=quantity,
        length=None,
        length_inches=None,
        weight=None,
    )


# ---------------------------------------------------------------------------
# Closure part-number classification
# ---------------------------------------------------------------------------

class TestClosureClassification:
    def test_rlcloutg_is_foam_not_metal(self):
        cats = {"Closures": [_piece("RLCLOUTG", "R-Loc outside closure", 40)]}
        c = extract_closure_counts(cats)
        assert c["foam_outside"] >= 40
        assert c["foam_total"] >= 40
        assert c["metal_total"] == 0

    def test_rlclingl_is_foam_inside(self):
        cats = {"Closures": [_piece("RLCLINGL", "R-Loc inside foam", 20)]}
        c = extract_closure_counts(cats)
        assert c["foam_inside"] >= 20
        assert c["metal_total"] == 0

    def test_cl426_is_metal(self):
        cats = {"SS Accessories": [_piece("CL426", "Metal inside closure", 12)]}
        c = extract_closure_counts(cats)
        assert c["metal_inside"] >= 12 or c["metal_total"] >= 12
        assert c["foam_total"] == 0

    def test_hw_series_metal_outside(self):
        cats = {
            "Closures": [
                _piece("HW-410", "Metal outside", 4),
                _piece("HW-412", "Metal outside", 4),
                _piece("HW-422", "Metal outside", 2),
                _piece("HW-432", "Metal outside", 2),
            ]
        }
        c = extract_closure_counts(cats)
        assert c["metal_outside"] >= 12
        assert c["metal_total"] >= 12

    def test_sped16_end_dam_counts_as_metal_family(self):
        cats = {"Accessories": [_piece("SPED16", "End dam", 8)]}
        c = extract_closure_counts(cats)
        assert c["end_dam"] >= 8
        assert c["metal_total"] >= 8

    def test_sprakez6_bird_stop(self):
        cats = {"Accessories": [_piece("SPRAKEZ6", "Z bird stop", 6)]}
        c = extract_closure_counts(cats)
        assert c["z_bird_stop"] >= 6
        assert c["metal_total"] >= 6

    def test_fl361_bird_stop(self):
        cats = {"Trim": [_piece("FL-361", "Bird stop", 4)]}
        c = extract_closure_counts(cats)
        assert c["z_bird_stop"] >= 4

    def test_foam_inside_description_never_metal(self):
        cats = {"Closures": [_piece("GEN", "Foam inside closure for eave", 10)]}
        c = extract_closure_counts(cats)
        assert c["foam_total"] >= 10
        assert c["metal_total"] == 0

    def test_mixed_ss_and_rloc_parts(self):
        cats = {
            "Closures": [
                _piece("CL426", "Metal inside", 10),
                _piece("RLCLOUTG", "R-Loc foam outside", 30),
            ]
        }
        c = extract_closure_counts(cats)
        assert c["metal_total"] >= 10
        assert c["foam_total"] >= 30


# ---------------------------------------------------------------------------
# Panel family detection (job-scenario style)
# ---------------------------------------------------------------------------

class TestPanelFamilyDetection:
    @pytest.mark.parametrize(
        "blob, flags",
        [
            ("CL / SSR standing seam roof + AVP wall panels",
             {"standing_seam": True, "avp": True, "exposed_fastener": True}),
            ("Double Lok roof with RLOC / PBR walls",
             {"standing_seam": True, "double_lok": True, "exposed_fastener": True}),
            ("VSR6 architectural standing seam + RL walls",
             {"standing_seam": True, "vsr6": True, "exposed_fastener": True}),
            ("Central-Loc CL standing seam + R-Loc double-check",
             {"standing_seam": True, "exposed_fastener": True}),
            ("MasterLine-16 concealed wall panels",
             {"masterline": True, "concealed_metal_wall": True, "metal_required": True}),
            ("Kingspan IMP FW-120 with VSR6 roof",
             {"standing_seam": True, "vsr6": True}),  # SS present → metal still required
            ("full RLoc roof and wall PBR",
             {"exposed_fastener": True, "foam_required": True, "metal_required": False}),
            ("Kingspan insulated metal panel + RLR reverse",
             {"imp": True, "rlr_reverse": True, "exposed_fastener": True}),
            ("New Millennium B-deck structural deck only",
             {"bdeck": True, "suppress_metal_closures": True, "metal_required": False}),
            ("Shadow Rib walls VSR6 walls PL121 liner",
             {"shadow_rib": True, "vsr6": True, "pl121": True, "liner": True}),
            ("McElroy SuperLok standing seam",
             {"standing_seam": True, "mcelroy": True, "metal_required": True}),
            ("PBA and PBM and 7.2 exposed panels",
             {"exposed_fastener": True, "pba": True, "pbm": True, "panel_7_2": True}),
        ],
    )
    def test_scenario_flags(self, blob, flags):
        cats = {"Panels": [_piece("P1", blob, 1)]}
        fam = detect_panel_families(cats, raw_text=blob)
        for key, expected in flags.items():
            assert fam.get(key) is expected, f"{key}: got {fam.get(key)}, want {expected} for {blob!r}"

    def test_imp_only_suppresses_metal_without_ss(self):
        fam = detect_panel_families(
            {"Panels": [_piece("IMP1", "Kingspan insulated metal panel", 20)]},
            raw_text="Kingspan IMP walls",
        )
        assert fam["imp"] is True
        assert fam["suppress_metal_closures"] is True
        assert fam["metal_required"] is False

    def test_bdeck_no_foam_requirement(self):
        fam = detect_panel_families(
            {"Deck": [_piece("BD", "New Millennium B-deck 1.5", 100)]},
            raw_text="B-deck structural deck",
        )
        assert fam["bdeck"] is True
        assert fam["foam_required"] is False
        assert fam["metal_required"] is False


# ---------------------------------------------------------------------------
# check_closures_present severity rules
# ---------------------------------------------------------------------------

class TestClosurePresenceRules:
    def test_ss_missing_metal_is_critical(self):
        fam = {"standing_seam": True, "metal_required": True, "exposed_fastener": False,
               "foam_required": False, "suppress_metal_closures": False}
        findings = check_closures_present(
            {"total": 0, "metal_total": 0, "foam_total": 0},
            has_panels=True,
            panel_families=fam,
        )
        crit = [f for f in findings if f["severity"] == "CRITICAL"]
        assert any(f["rule"] == "closures_metal_standing_seam" for f in crit)

    def test_ss_with_metal_is_info(self):
        fam = {"standing_seam": True, "metal_required": True, "exposed_fastener": False,
               "foam_required": False, "suppress_metal_closures": False}
        findings = check_closures_present(
            {"total": 10, "metal_total": 10, "metal_inside": 10, "foam_total": 0,
             "end_dam": 0, "z_bird_stop": 0, "metal_outside": 0},
            has_panels=True,
            panel_families=fam,
        )
        assert any(
            f["rule"] == "closures_metal_standing_seam" and f["severity"] == "INFO"
            for f in findings
        )
        assert not any(f["severity"] == "CRITICAL" for f in findings)

    def test_exposed_missing_foam_is_warning(self):
        fam = {"standing_seam": False, "metal_required": False, "exposed_fastener": True,
               "foam_required": True, "suppress_metal_closures": False}
        findings = check_closures_present(
            {"total": 0, "metal_total": 0, "foam_total": 0},
            has_panels=True,
            panel_families=fam,
        )
        warn = [f for f in findings if f["severity"] == "WARNING"]
        assert any(f["rule"] == "closures_foam_exposed_fastener" for f in warn)

    def test_exposed_with_rlcloutg_ok(self):
        cats = {
            "Panels": [_piece("RL", "R-Loc / PBR roof panel", 50)],
            "Closures": [_piece("RLCLOUTG", "Outside foam", 40)],
        }
        fam = detect_panel_families(cats)
        counts = extract_closure_counts(cats)
        findings = check_closures_present(counts, has_panels=True, panel_families=fam)
        assert counts["foam_total"] >= 40
        assert not any(
            f["rule"] == "closures_foam_exposed_fastener" and f["severity"] == "WARNING"
            for f in findings
        )

    def test_bdeck_no_metal_critical(self):
        cats = {"Deck": [_piece("BD", "New Millennium B-deck", 80)]}
        fam = detect_panel_families(cats, raw_text="B-deck only")
        findings = check_closures_present(
            extract_closure_counts(cats), has_panels=True, panel_families=fam,
        )
        assert not any(f["severity"] == "CRITICAL" for f in findings)
        assert any(f["rule"] == "closures_metal_exception" for f in findings) or fam["suppress_metal_closures"]

    def test_dual_system_ss_roof_and_rloc_walls(self):
        """AVP/RLoc walls need foam; CL roof needs metal — both flags true."""
        cats = {
            "Standing Seam Roof": [_piece("CL", "Central-Loc standing seam", 40)],
            "Wall Panels": [_piece("AVP", "AVP wall panel", 60)],
            "Closures": [
                _piece("CL426", "Metal inside", 20),
                _piece("RLCLOUTG", "Foam outside", 30),
            ],
        }
        fam = detect_panel_families(cats)
        assert fam["standing_seam"] and fam["exposed_fastener"]
        assert fam["metal_required"] and fam["foam_required"]
        counts = extract_closure_counts(cats)
        findings = check_closures_present(counts, has_panels=True, panel_families=fam)
        assert not any(f["severity"] in ("CRITICAL", "WARNING") and "closure" in f["rule"] for f in findings)


# ---------------------------------------------------------------------------
# Engine wiring
# ---------------------------------------------------------------------------

class TestEngineClosureWiring:
    def test_engine_flags_ss_missing_metal(self):
        shipper = {
            "categories": {
                "Standing Seam Panels": [_piece("SSR", "SSR standing seam roof", 30)],
            },
            "raw_text": "SSR standing seam",
            "ss_accessories": {},
            "summary_weights": {},
        }
        engine = DiscrepancyEngine(shipper_data=shipper, drawings_data={})
        findings = engine.run()
        rules = {f.rule for f in findings}
        assert "closures_metal_standing_seam" in rules
        assert any(f.severity == "CRITICAL" and f.rule == "closures_metal_standing_seam" for f in findings)

    def test_engine_rloc_foam_ok(self):
        shipper = {
            "categories": {
                "R-Loc Panels": [_piece("RL", "R-Loc PBR panel", 40)],
                "Closures": [_piece("RLCLINGL", "Foam inside", 20), _piece("RLCLOUTG", "Foam outside", 20)],
            },
            "raw_text": "R-Loc roof and walls",
            "ss_accessories": {},
            "summary_weights": {},
        }
        engine = DiscrepancyEngine(shipper_data=shipper, drawings_data={})
        findings = engine.run()
        assert not any(
            f.rule == "closures_foam_exposed_fastener" and f.severity == "WARNING"
            for f in findings
        )
        assert not any(
            f.rule == "closures_metal_standing_seam" and f.severity == "CRITICAL"
            for f in findings
        )

    def test_watermark_default_false_in_report(self):
        import inspect
        from chubby_checker.report.pdf_report import generate_pdf_report
        assert inspect.signature(generate_pdf_report).parameters["watermark"].default is False
