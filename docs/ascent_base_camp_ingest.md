# Ascent Base Camp ingest (2026-07-27)

Documents absorbed into Chubby Checker libraries:

| Document | Module |
|----------|--------|
| Ascent Panel Comparison Chart | `ascent_panel_catalog.py` |
| Panel Max weight & lengths | `ascent_panel_catalog.py` |
| Cold Form Zee / Cee / Open Cee / Eave Struts | `ascent_member_catalog.py` |
| Built-Up Welded Members | `ascent_member_catalog.py` |
| Hot Rolled Pipe / Tube | `ascent_member_catalog.py` |
| Trim Lengths | `ascent_trim_rules.py` |
| Bolt Reference | dimensional reference only (not connection qty) |
| Standard Punches EP/LL/SL | secondary punch context |
| Main Frame Fabrication Guidelines | fab practice notes |
| Metal Buildings 101 | industry context |

## MBS-supported panel highlights

**Exposed:** R-Loc (RL/RLX/RLR), M-Loc (ML/MLR), Panel-Loc Plus (PP), Panel-Loc (PL) — typically 36\" coverage, max 50'.

**Standing seam:** Central-Loc (CL/CLX), Central Seam Plus (CS/CSX), Central-Snap (S6), Central-Span (VSR6) — 16/18/24\" modules, max ~52'.

**7.2 Panel:** weights known; MBS code not currently supported per chart.

## Member codes

- Zee/Cee: `Z82516` = Z, 8\" depth, 2.5\" flange, 16 ga
- Open Cee: `U102514`
- Eave strut: `08534DU` + slope code
- Built-up: `B22d0g` = 22\" deep, 5/16\" web, 10\" flange, 3/8\" flange thick
- Pipe: `PP6188`; Tube: `T080080C`

## Trim sticks

Only 10'-2", 12'-2", 14'-2", 16'-2", 18'-2", 20'-4". Lap 2\". Eave/gutter/rake use (length+1')/20 rounded up to standard stick.
