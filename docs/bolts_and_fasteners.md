# Bolts, Standing Seam System & Sheeting Fasteners

## Bolt library (`bolt_library.py`)

Default connection counts (override with `ASCENT_BOLT_LIBRARY` JSON env):

| Connection | Family | Bolts | Grade |
|------------|--------|------:|-------|
| knee_end_plate | primary | 8 | A325 |
| ridge_end_plate | primary | 8 | A325 |
| rafter_splice | primary | 8 | A325 |
| column_splice | primary | 6 | A325 |
| endwall_frame | primary | 4 | A325 |
| purlin_clip | secondary | 2 | A307 |
| purlin_lap | secondary | 4 | A307 |
| girt_clip | secondary | 2 | A307 |
| eave_strut | secondary | 2 | A307 |
| flange_brace | secondary | 2 | A307 |

Pass `connection_counts` into `DiscrepancyEngine` or put them on `drawings_data["connection_counts"]`:

```python
connection_counts = {
  "knees": 8, "ridges": 4, "purlin_clips": 120, "purlin_laps": 40,
}
```

## Standing seam system

MBCI-aligned:

- ≥ **2 clip screws per sliding clip**
- thermal blocks ≈ clips when insulation present
- backup plates at endlap lines × seams
- optional geometry: `seams × purlin_lines` expected clips

Provide on drawings_data / shipper_data when known:

- `panel_coverage` or dominant coverage
- `width_ft`, `purlin_lines`, `endlap_lines`, `slopes`

## Sheeting fasteners

PBR / R-Loc: 3 @ intermediate, 6 @ eave/endlap, sidelap ~20" o.c.  
7.2: denser intermediate (6).  
M-Loc / PBA: same pattern defaults as PBR until Ascent specifies otherwise.

## Rules wired in engine

1. `bolts_present` / `bolts_vs_library` / `nuts_vs_bolts`
2. `ss_clip_screws_min` / `ss_thermal_blocks` / `ss_backup_plates` / `ss_clips_vs_geometry`
3. `sheeting_screws_present` / `sheeting_screws_vs_geometry`
