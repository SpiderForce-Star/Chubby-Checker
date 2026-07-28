"""
Ascent Buildings member part-code catalog.

Sources (Base Camp Drafting Manual):
  - Cold Form Zee / Cee / Open Cee / Eave Struts
  - Built-Up Welded Members (BzzYxW)
  - Hot Rolled Pipe (PPccDDD) / Tube (TaaaBBBc)
  - Standard Punches (EP, LL, SL) context for secondary

Part-code grammar (validated 2026-07-27 Heavy Grok audit):
  Cee/Zee   C|Z + depth(8|10|12) + flange(25=2.5"|35=3.5") + gauge(12|14|16)
            e.g. C82516, Z103512
  Open Cee  U + depth(82|102|122) + 5 + gauge(12|14|16)
            e.g. U82516 → 8.25", U122514 → 12.25"
  Eave      depth(06|08|10) + botFl + topFl + gaugeCode + [slope] + optional ---
  Built-up  B + depth(10-36) + web(a-k) + flangeW(0|2|5|6|8) + flangeT(a-k)
  Pipe      PP + sizeDigit + wall*1000
  Tube      TS|T + depth3 + width3 + thickLetter
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import re

# ----- Cold-form Zee (purlins / girts) plf -----
ZEE_PLF = {
    "Z82516": 2.61, "Z82514": 3.23, "Z82512": 4.65,
    "Z83516": 2.98, "Z83514": 3.69, "Z83512": 5.32,
    "Z102516": 2.98, "Z102514": 3.69, "Z102512": 5.32,
    "Z103514": 4.15, "Z103512": 5.98,
    "Z122514": 4.15, "Z122512": 5.98,
    "Z123514": 4.61, "Z123512": 6.65,
}

# Cee (girts, FO headers/jambs/sills)
CEE_PLF = {
    "C82516": 2.61, "C82514": 3.23, "C82512": 4.65,
    "C83516": 2.98, "C83514": 3.69, "C83512": 5.32,
    "C102516": 2.98, "C102514": 3.69, "C102512": 5.32,
    "C103514": 4.15, "C103512": 5.98,
    "C122514": 4.15, "C122512": 5.98,
    "C123514": 4.61, "C123512": 6.65,
}

# Open Cee (base channel / rake extension cap)
OPEN_CEE_PLF = {
    "U82516": 2.61, "U82514": 3.23, "U82512": 4.65,
    "U102516": 2.98, "U102514": 3.69, "U102512": 5.32,
    "U122514": 4.15, "U122512": 5.98,
}

# Eave strut base codes (last digit before slope = gauge code 6→16, 4→14, 2→12)
EAVE_STRUT_PLF = {
    "06436": 2.61, "06434": 3.22, "06432": 4.65,
    "08534": 3.92, "08532": 5.65,
    "10534": 4.61, "10532": 6.32,
}

# Built-up thickness letter codes (Base Camp continuous a–k)
BUILTUP_THICK = {
    "a": 0.1345, "b": 0.1875, "c": 0.2500, "d": 0.3125,
    "e": 0.3750, "f": 0.5000, "g": 0.6250, "h": 0.7500,
    "i": 1.0000, "j": 0.7500, "k": 1.0000,
}
BUILTUP_FLANGE_WIDTH = {
    "5": 5.0, "6": 6.0, "8": 8.0, "0": 10.0, "2": 12.0,
}

# Tube wall thickness letter
TUBE_THICK = {
    "a": 0.125, "b": 0.1875, "c": 0.250, "d": 0.3125,
    "e": 0.375, "f": 0.500, "g": 0.625, "h": 0.750, "i": 1.000,
}

# Stocked pipe
STOCK_PIPE = {
    "PP6188": (6.625, 0.188),
    "PP6280": (6.625, 0.280),
    "PP6432": (6.625, 0.432),
    "PP8250": (8.625, 0.250),
    "PP8322": (8.625, 0.322),
}


@dataclass
class MemberDecode:
    raw: str
    kind: str  # zee | cee | open_cee | eave_strut | built_up | pipe | tube | unknown
    depth_in: Optional[float] = None
    flange_in: Optional[float] = None
    gauge: Optional[int] = None
    weight_plf: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


def _norm(code: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (code or "")).upper()


def decode_zee_cee(code: str) -> Optional[MemberDecode]:
    """
    Decode Cee / Zee / Open Cee part codes.

    Cee/Zee grammar:  C|Z + depth(8|10|12) + flange(25|35) + gauge(12|14|16)
      C82516  → 8" × 2.5" × 16 ga
      Z103512 → 10" × 3.5" × 12 ga

    Open Cee grammar: U + depth(82|102|122) + 5 + gauge(12|14|16)
      U82516  → 8.25" × ~3" × 16 ga
      U122514 → 12.25" × ~3" × 14 ga
    """
    c = _norm(code)

    # ----- Cee / Zee -----
    m = re.match(r"^([CZ])(8|10|12)(25|35)(12|14|16)$", c)
    if m:
        kind = "cee" if m.group(1) == "C" else "zee"
        depth = float(m.group(2))
        flange = 2.5 if m.group(3) == "25" else 3.5
        gauge = int(m.group(4))
        plf_table = CEE_PLF if kind == "cee" else ZEE_PLF
        plf = plf_table.get(c)
        return MemberDecode(
            raw=code,
            kind=kind,
            depth_in=depth,
            flange_in=flange,
            gauge=gauge,
            weight_plf=plf,
            details={"part": c, "flange_code": m.group(3)},
        )

    # ----- Open Cee -----
    m = re.match(r"^U(82|102|122)5(12|14|16)$", c)
    if m:
        depth_map = {"82": 8.25, "102": 10.25, "122": 12.25}
        depth = depth_map[m.group(1)]
        gauge = int(m.group(2))
        plf = OPEN_CEE_PLF.get(c)
        return MemberDecode(
            raw=code,
            kind="open_cee",
            depth_in=depth,
            flange_in=3.0,
            gauge=gauge,
            weight_plf=plf,
            details={"part": c, "depth_code": m.group(1)},
        )

    return None


def decode_eave_strut(code: str) -> Optional[MemberDecode]:
    c = _norm(code)
    # 08534 / 08534DU / 08534---  — first 5 chars are depth+flanges+gaugeCode
    m = re.match(r"^(\d{5})([A-Z]{0,2})(\d?)$", c)
    if not m:
        return None
    base = m.group(1)
    if base not in EAVE_STRUT_PLF:
        if len(c) >= 5 and c[:5] in EAVE_STRUT_PLF:
            base = c[:5]
        else:
            return None
    depth = float(base[:2])
    # Gauge digit encoding: 6→16 ga, 4→14 ga, 2→12 ga
    gauge_map = {"6": 16, "4": 14, "2": 12}
    gauge = gauge_map.get(base[4])
    return MemberDecode(
        raw=code,
        kind="eave_strut",
        depth_in=depth,
        gauge=gauge,
        weight_plf=EAVE_STRUT_PLF.get(base),
        details={"base": base, "slope_code": m.group(2) or ""},
    )


def decode_built_up(code: str) -> Optional[MemberDecode]:
    c = _norm(code)
    # B22d0g — depth 10–36"
    m = re.match(r"^B(\d{2})([a-k])([05268])([a-k])$", c, re.IGNORECASE)
    if not m:
        return None
    depth = float(m.group(1))
    if not (10 <= depth <= 36):
        return None
    web_t = BUILTUP_THICK.get(m.group(2).lower())
    fl_w = BUILTUP_FLANGE_WIDTH.get(m.group(3))
    fl_t = BUILTUP_THICK.get(m.group(4).lower())
    return MemberDecode(
        raw=code,
        kind="built_up",
        depth_in=depth,
        details={"web_thickness": web_t, "flange_width": fl_w, "flange_thickness": fl_t},
    )


def decode_pipe(code: str) -> Optional[MemberDecode]:
    c = _norm(code)
    if c in STOCK_PIPE:
        od, t = STOCK_PIPE[c]
        return MemberDecode(
            raw=code, kind="pipe", depth_in=od,
            details={"od": od, "wall": t, "stock": True},
        )
    m = re.match(r"^PP(\d)(\d{3})$", c)
    if not m:
        return None
    size_map = {"4": 4.5, "6": 6.625, "8": 8.625, "1": 10.75}
    od = size_map.get(m.group(1))
    wall = int(m.group(2)) / 1000.0
    return MemberDecode(raw=code, kind="pipe", depth_in=od, details={"od": od, "wall": wall})


def decode_tube(code: str) -> Optional[MemberDecode]:
    c = _norm(code)
    # TS080080C or T080080C
    m = re.match(r"^(?:TS|T)(\d{3})(\d{3})([A-I])$", c, re.IGNORECASE)
    if not m:
        return None
    depth = int(m.group(1)) / 10.0  # 080 → 8.0
    width = int(m.group(2)) / 10.0
    thick = TUBE_THICK.get(m.group(3).lower())
    return MemberDecode(
        raw=code,
        kind="tube",
        depth_in=depth,
        details={"depth": depth, "width": width, "wall": thick},
    )


def decode_member(code: str) -> MemberDecode:
    """Try all Ascent part-code families."""
    for fn in (decode_zee_cee, decode_eave_strut, decode_built_up, decode_pipe, decode_tube):
        hit = fn(code)
        if hit:
            return hit
    return MemberDecode(raw=code, kind="unknown")


def weight_for_length(code: str, length_ft: float) -> Optional[float]:
    d = decode_member(code)
    if d.weight_plf is None:
        return None
    return d.weight_plf * length_ft


def is_ascent_secondary_code(code: str) -> bool:
    return decode_member(code).kind in {"zee", "cee", "open_cee", "eave_strut"}
