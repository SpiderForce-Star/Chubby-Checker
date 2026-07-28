"""
Ascent Buildings panel catalog (Central States / MBS-supported).

Source: Ascent Panel Comparison Chart + Panel Max weight & lengths
(Base Camp / Technical Reference).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import re


@dataclass(frozen=True)
class PanelSpec:
    key: str
    name: str
    family: str  # exposed | standing_seam | misc
    mbs_codes: tuple
    coverage_in: tuple  # possible coverages
    gauges: tuple
    min_pitch: str
    max_length_ft: float
    weight_plf: Dict[str, float]  # gauge -> lb/ft where known
    fastener_system: str  # exposed | concealed_clip | snap | mechanical
    notes: str = ""


# Primary Ascent / Central States panels used with MBS
ASCENT_PANELS: Dict[str, PanelSpec] = {
    # ----- Exposed fastener -----
    "r-loc": PanelSpec(
        key="r-loc",
        name="R-Loc",
        family="exposed",
        mbs_codes=("RL", "RLX", "RLR"),
        coverage_in=(36,),
        gauges=(24, 26),
        min_pitch="1/2:12",
        max_length_ft=50.0,
        weight_plf={"26": 2.58, "24": 3.35},  # Standard / Grade 50 prime approx from weight sheet
        fastener_system="exposed",
        notes="36\" coverage; X = DripX condensation control; reverse = RLR",
    ),
    "m-loc": PanelSpec(
        key="m-loc",
        name="M-Loc",
        family="exposed",
        mbs_codes=("ML", "MLR"),
        coverage_in=(36,),
        gauges=(24, 26),
        min_pitch="1:12",
        max_length_ft=50.0,
        weight_plf={"26": 2.58},
        fastener_system="exposed",
        notes="36\" coverage; reverse = MLR",
    ),
    "panel-loc-plus": PanelSpec(
        key="panel-loc-plus",
        name="Panel-Loc Plus",
        family="exposed",
        mbs_codes=("PP", "PPR"),
        coverage_in=(36,),
        gauges=(29, 26),
        min_pitch="1/2:12",
        max_length_ft=50.0,
        weight_plf={"29": 2.03, "26": 2.55},
        fastener_system="exposed",
    ),
    "panel-loc": PanelSpec(
        key="panel-loc",
        name="Panel-Loc",
        family="exposed",
        mbs_codes=("PL", "PLR"),
        coverage_in=(36,),
        gauges=(29, 26),
        min_pitch="3:12",
        max_length_ft=50.0,
        weight_plf={"29": 1.99, "26": 2.55},
        fastener_system="exposed",
    ),
    "7.2": PanelSpec(
        key="7.2",
        name="7.2 Panel",
        family="exposed",
        mbs_codes=(),  # not currently MBS-supported per chart
        coverage_in=(36, 28.8),
        gauges=(24, 26),
        min_pitch="1/2:12",
        max_length_ft=52.0,
        weight_plf={"26_36": 2.8, "26_28.8": 2.71, "24_36": 3.41},
        fastener_system="exposed",
        notes="MBS code not currently supported; denser ribs → more fasteners/line",
    ),
    # ----- Standing seam (Central States) -----
    "central-loc": PanelSpec(
        key="central-loc",
        name="Central-Loc",
        family="standing_seam",
        mbs_codes=("CL", "CLX"),
        coverage_in=(24, 18),
        gauges=(24,),
        min_pitch="1/4:12",
        max_length_ft=52.0,
        weight_plf={"24": 2.33},
        fastener_system="snap",
        notes="Snap-Loc roof; X = DripX",
    ),
    "central-seam-plus": PanelSpec(
        key="central-seam-plus",
        name="Central Seam Plus",
        family="standing_seam",
        mbs_codes=("CS", "CSX"),
        coverage_in=(24, 18),
        gauges=(24,),
        min_pitch="1/4:12",
        max_length_ft=52.0,
        weight_plf={"24": 2.33},
        fastener_system="mechanical",
        notes="Mechanically seamed; X = DripX",
    ),
    "central-snap": PanelSpec(
        key="central-snap",
        name="Central-Snap",
        family="standing_seam",
        mbs_codes=("S6",),
        coverage_in=(16, 18),
        gauges=(24,),
        min_pitch="1:12",
        max_length_ft=52.0,
        weight_plf={"24": 1.71},
        fastener_system="snap",
        notes="Snap seamed; 16\" or 18\" coverage",
    ),
    "central-span": PanelSpec(
        key="central-span",
        name="Central-Span",
        family="standing_seam",
        mbs_codes=("VSR6",),
        coverage_in=(16,),
        gauges=(24,),
        min_pitch="1:12",
        max_length_ft=52.0,
        weight_plf={"24": 1.71},
        fastener_system="mechanical",
        notes="Multiple mechanically seamed options",
    ),
    "precision-loc": PanelSpec(
        key="precision-loc",
        name="Precision-Loc",
        family="misc",
        mbs_codes=("PSF", "PS1", "PS2", "PS3"),
        coverage_in=(12,),
        gauges=(24,),
        min_pitch="N/A",
        max_length_ft=35.0,
        weight_plf={"24": 1.23},
        fastener_system="concealed_clip",
        notes="Soffit/wall style options solid/vented",
    ),
}

# Alias map: shipper/drawing text → catalog key
PANEL_ALIASES = {
    "r-loc": "r-loc", "rloc": "r-loc", "r loc": "r-loc", "rl": "r-loc", "rlx": "r-loc", "rlr": "r-loc",
    "pbr": "r-loc",  # often used interchangeably in conversation; Ascent MBS is R-Loc
    "m-loc": "m-loc", "mloc": "m-loc", "ml": "m-loc", "mlr": "m-loc",
    "panel-loc plus": "panel-loc-plus", "panel loc plus": "panel-loc-plus", "pp": "panel-loc-plus",
    "panel-loc": "panel-loc", "panel loc": "panel-loc", "pl": "panel-loc",
    "7.2": "7.2", "7.2 panel": "7.2",
    "central-loc": "central-loc", "central loc": "central-loc", "cl": "central-loc", "clx": "central-loc",
    "central seam": "central-seam-plus", "central seam plus": "central-seam-plus",
    "cs": "central-seam-plus", "csx": "central-seam-plus",
    "central-snap": "central-snap", "central snap": "central-snap", "s6": "central-snap",
    "central-span": "central-span", "vsr6": "central-span",
    "vs16": "central-span",  # 16\" mechanical SS family used on Ascent jobs
    "precision-loc": "precision-loc", "precision loc": "precision-loc",
}


def identify_panel(text: str) -> Optional[PanelSpec]:
    if not text:
        return None
    t = text.lower()
    # Prefer longer aliases first
    for alias in sorted(PANEL_ALIASES.keys(), key=len, reverse=True):
        if alias in t:
            return ASCENT_PANELS.get(PANEL_ALIASES[alias])
    # MBS code tokens
    for key, spec in ASCENT_PANELS.items():
        for code in spec.mbs_codes:
            if re.search(rf"\b{re.escape(code)}\b", text, re.IGNORECASE):
                return spec
    return None


def get_panel(key: str) -> Optional[PanelSpec]:
    return ASCENT_PANELS.get(key) or ASCENT_PANELS.get(PANEL_ALIASES.get(key.lower(), ""))


def list_panels(family: Optional[str] = None) -> List[Dict[str, Any]]:
    out = []
    for p in ASCENT_PANELS.values():
        if family and p.family != family:
            continue
        out.append(asdict(p))
    return out


def expected_coverage_in(panel_key: str, preferred: Optional[int] = None) -> Optional[int]:
    spec = get_panel(panel_key)
    if not spec:
        return preferred
    if preferred and preferred in spec.coverage_in:
        return preferred
    return spec.coverage_in[0] if spec.coverage_in else preferred
