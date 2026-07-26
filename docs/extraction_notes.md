# Extraction Notes – Chubby Checker

## Standing Seam
- CS244 → 24\" coverage
- CS184 → 18\" coverage
- VS16 / 16\" panels → higher clip density
- Sliding clips (CSP212), Thermal blocks (CL575), Backup plates (CL7760 24\", CL7769 18\")

## Exposed Fastener Panels (Ascent / MBCI / Central States)
| Profile | Coverage | System | Typical use |
|---------|----------|--------|-------------|
| R-Loc / RLOC / PBR | 36\" | Exposed | Roof + Wall |
| 7.2 Panel | 36\" (or 28.8\") | Exposed | Roof + Wall |
| M-Loc | ~36\" | Exposed | Commercial low-rib |
| PBA | ~36\" | Exposed | Roof / Wall |

Fastener rules use approximate screws-per-support-line + support spacing (default 5' for purlins/girts). Engine flags large deviations when these panels appear but exposed-fastener screw quantities are missing or extremely low.

## Multi-phase
Shippers often arrive as PH1 (structure), PH3 (mezz), PH4 (panels), etc. Aggregator sums everything before comparison.

## Length
Both parsers normalize Ascent lengths (e.g. 29'-7 3/8\") to decimal inches for tolerance checks (±0.5\" warning, >6\" critical).
