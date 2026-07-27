# Ascent vs Buy-out Matrix (Chubby-Checker)

Clear rules used by the discrepancy engine.

## Ascent Supplies (checked)

| Scope | Examples |
|-------|----------|
| **Primary framing** | RF / PF / MF frames, columns (AC, SC, EC, CC), rafters, endwalls |
| **Secondary framing** | Purlins, girts, eave struts, flange braces, sag rods |
| **Sheeting** | Standing Seam (CS244, CS184, VS16), R-Loc/PBR, 7.2, M-Loc, PBA |
| **Trim** | Eave, rake, corner, base, jamb, header, ridge, gutter, downspout |
| **Accessories** | Clips, thermal blocks, backup plates, screws, bolts, closures, pop rivets |
| **Crane runway supports** | Runway beams & braces (not the rail) |
| **Mezzanine framing** | When Ascent-supplied |

## Always Buy-outs (excluded from missing-piece checks)

| Item | Policy |
|------|--------|
| **Insulation** | Buy-out. Shipper weight should be **0.00**. |
| **IMPs** | Kingspan, AWIP, Nucor, Metl-Span, etc. – buy-out. |
| **Joists & Deck** | **New Millennium Building Systems**. Framing by others; interfaces with Ascent steel. |
| **Walk / personnel doors** | Door **unit** is buy-out. Framed opening / jambs / headers may be Ascent CFS. |
| **Overhead / roll-up doors** | Door **unit** is buy-out. |
| **Windows** | Unit is buy-out. |
| **Louvers** | Unit is buy-out. |
| **Skylights** | Buy-out. |
| **Roof & wall vents** | Buy-out. |
| **Fans** | Exhaust / supply – buy-out. |

## Engine Behavior

1. Marks / categories matching buy-out keywords are **removed** from mark-by-mark missing-piece checks.
2. If a buy-out category still appears with quantity:
   - Joist/Deck or IMP → **WARNING** (possible double-supply)
   - Insulation → **INFO** (should be zero weight)
   - Other units → **INFO**
3. Framed openings, jambs, and headers remain in scope – only the finished door/window/louver unit is excluded.
