"""
Ascent Buildings member part-code catalog.

Sources (Base Camp Drafting Manual):
  - Cold Form Zee / Cee / Open Cee / Eave Struts
  - Built-Up Welded Members (BzzYxW)
  - Hot Rolled Pipe (PPccDDD) / Tube (TaaaBBBc)
  - Standard Punches (EP, LL, SL) context for secondary
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

# Eave strut base codes (last 3 chars = slope code SU/SD/DU/DD)
EAVE_STRUT_PLF = {
    "06436": 2.61, "06434": 3.22, "06432": 4.65,
    "08534": 3.92, "08532": 5.65,
    "10534": 4.61, "10532": 6.32,
}

# Built-up thickness letter codes
BUILTUP_THICK = {
    "a": 0.1345, "b": 0.1875, "c": 0.2500, "d": 0.3125,
    "g": 0.3750, "h": 0.5000, "i": 0.6250, "j": 0.7500, "k": 1.0000,
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
    c = _norm(code)
    # Z82516 / C102514 / U122512
    m = re.match(r"^([ZCU])(\d{2})(\d)(\d{2})$", c)
    if not m:
        return None
    kind_map = {"Z": "zee", "C": "cee", "U": "open_cee"}
    kind = kind_map[m.group(1)]
    depth = float(m.group(2))
    # open cee depths coded as 82/102/122 → 8.25 / 10.25 / 12.25 conceptually; use nominal 8/10/12
    flange_digit = int(m.group(3))
    flange = 2.5 if flange_digit == 2 else 3.5 if flange_digit == 3 else float(flange_digit)
    gauge = int(m.group(4))
    plf_table = {"zee": ZEE_PLF, "cee": CEE_PLF, "open_cee": OPEN_CEE_PLF}[kind]
    # try exact then without leading zeros issues
    plf = plf_table.get(c) or plf_table.get(c.replace("Z10", "Z10"))
    return MemberDecode(
        raw=code, kind=kind, depth_in=depth, flange_in=flange, gauge=gauge,
        weight_plf=plf, details={"part": c},
    )


def decode_eave_strut(code: str) -> Optional[MemberDecode]:
    c = _norm(code)
    # 08534DU1 style — first 5 digits depth/flange/gauge
    m = re.match(r"^(\d{5})([A-Z]{0,2})(\d?)$", c)
    if not m:
        return None
    base = m.group(1)
    if base not in EAVE_STRUT_PLF and base[:5] not in EAVE_STRUT_PLF:
        # try first 5 of longer
        if len(c) >= 5 and c[:5] in EAVE_STRUT_PLF:
            base = c[:5]
        else:
            return None
    depth = float(base[:2])
    return MemberDecode(
        raw=code, kind="eave_strut", depth_in=depth,
        weight_plf=EAVE_STRUT_PLF.get(base),
        details={"base": base, "slope_code": m.group(2) or ""},
    )


def decode_built_up(code: str) -> Optional[MemberDecode]:
    c = _norm(code)
    # B22d0g
    m = re.match(r"^B(\d{2})([a-k])([05268])([a-k])$", c, re.IGNORECASE)
    if not m:
        return None
    depth = float(m.group(1))
    web_t = BUILTUP_THICK.get(m.group(2).lower())
    fl_w = BUILTUP_FLANGE_WIDTH.get(m.group(3))
    fl_t = BUILTUP_THICK.get(m.group(4).lower())
    return MemberDecode(
        raw=code, kind="built_up", depth_in=depth,
        details={"web_thickness": web_t, "flange_width": fl_w, "flange_thickness": fl_t},
    )


def decode_pipe(code: str) -> Optional[MemberDecode]:
    c = _norm(code)
    if c in STOCK_PIPE:
        od, t = STOCK_PIPE[c]
        return MemberDecode(raw=code, kind="pipe", depth_in=od, details={"od": od, "wall": t, "stock": True})
    m = re.match(r"^PP(\d)(\d{3})$", c)
    if not m:
        return None
    # simplified: first digit maps rough OD class 4/6/8/10
    size_map = {"4": 4.5, "6": 6.625, "8": 8.625, "1": 10.75}
    od = size_map.get(m.group(1))
    wall = int(m.group(2)) / 1000.0
    return MemberDecode(raw=code, kind="pipe", depth_in=od, details={"od": od, "wall": wall})


def decode_tube(code: str) -> Optional[MemberDecode]:
    c = _norm(code)
    # T080080C
    m = re.match(r"^T(\d{3})(\d{3})([A-I])$", c, re.IGNORECASE)
    if not m:
        return None
    depth = int(m.group(1)) / 10.0  # 080 → 8.0
    width = int(m.group(2)) / 10.0
    thick = TUBE_THICK.get(m.group(3).lower())
    return MemberDecode(
        raw=code, kind="tube", depth_in=depth,
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
