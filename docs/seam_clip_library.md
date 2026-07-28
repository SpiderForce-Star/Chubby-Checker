# Seam Clip Library

`chubby_checker/rules/seam_clip_library.py` defines standing-seam clip types used by Ascent Shipper Checker.

## Ascent primary parts

| Role | Part # | Notes |
|------|--------|-------|
| Sliding clip | CSP212 / CS2124 | 2\" high sliding; 2 screws/clip |
| Thermal block | CL575 | ~1:1 with clips when insulated |
| Backup 24\" | CL7760 | Endlaps for 24\" module |
| Backup 18\" | CL7769 | Endlaps for 18\" module |
| Clip screw | FSS10 | Panel clip screw |
| Hi-eave plate | CL7616 | |
| Hi-rake support | CL7720 | |

## MBCI-aligned reference clips

Double-Lok (HW-2122/2124/2126/2129), SuperLok/BattenLok fixed & floating (HW-22x/23x), LokSeam UL90.

All default to **≥ 2 fasteners per clip**.

## Override

```bash
export ASCENT_SEAM_CLIP_LIBRARY='{"ascent_sliding_2in":{"screws_per_clip":2,"part_numbers":["CSP212"]}}'
```

## Engine integration

`check_standing_seam_system()` uses the library for:

- clip identification (`ss_clip_library_id`)
- screws/clip minimum
- thermal requirement by clip type
- backup plate width for panel coverage
- geometry estimates (`ss_system_estimate`)
