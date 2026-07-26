# PDF Extraction Notes

## Ascent Complete Shipper Patterns

### Cover / Index Page
- Weight totals listed for each category (Cold Formed Steel, Hot Rolled Beam, Fabricated Steel, Standing Seam, SS Accessories, etc.)
- Regex patterns capture these reliably.

### Piece Tables
Typical columns:
`Revision | Qnty | Mark | Description | Part | Color | Length | Unit Weight | Weight | Material ID`

pdfplumber `extract_tables()` works well on most category pages.

### Standing Seam Accessories (critical for rules)
Common marks seen in real jobs:
- CSP212 / CS2124 → 2" High Sliding Clip
- CL7760 → 24" Back Up Plate
- CL7769 → 18" Back Up Plate
- CL575 → 1" Thermal Block
- CL7616 → Hi-Eave Plate
- CL7720 → Hi-Rake Support
- FSS10 → Panel Clip Screw (Insulation > 4")

### Panel Coverage
- CS244 → 24" coverage (most common)
- CS184 → 18" coverage
- VS16 / similar → 16" coverage (higher clip density)

## Final Drawings
Member Tables are often graphical. pdfplumber helps on cleaner pages; more complex elevations may need additional OCR or coordinate-based extraction later.
