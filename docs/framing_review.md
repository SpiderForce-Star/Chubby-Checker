# Primary & Secondary Framing Review

## Primary Framing
Detected via mark prefixes / descriptions:
- RF / PF / MF — Rigid / Primary / Main Frames
- EF / IF — Endwall / Interior Frames
- AC / SC / EC / CC — Aux, Soldier, Endwall, Crane Columns
- Explicit “Rigid Frame”, “Main Frame”, “Crane Column” text

**Checks**
- Presence of primary framing on structural jobs
- Summary of frames vs columns
- Mark-level missing primary pieces vs drawings Member Tables

## Secondary Framing
Detected via:
- Purlins (P-*, PR-*, Z sections, “PURLIN”)
- Girts (G-*, CG-*, “GIRT”)
- Eave Struts (ES-*, E-*, “EAVE STRUT”)
- Flange Braces (FB-*, FBR-*, “FLANGE BRACE”)
- Sag angles / bridging

**Checks**
- Secondary present when primary exists
- Purlins / girts / eave struts presence
- Flange braces when purlins or girts exist
- Mark-level missing secondary pieces vs drawings

## Output
Findings appear under categories:
- `Primary Framing`
- `Secondary Framing`
- `Flange Braces`

with severities CRITICAL / WARNING / INFO.
