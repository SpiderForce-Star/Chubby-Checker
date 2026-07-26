# Chubby-Checker

**Ascent Buildings BOM / Shipper vs Final Drawings Verification Tool**

Chubby Checker automatically cross-checks Ascent Complete Shippers (and BOMs) against Final Erection Drawings to catch quantity, length, weight, missing piece, clip/fastener, panel-width, and layout errors before release.

## Goal
Reduce manual review time and prevent costly field or fabrication errors by providing a fast, rules-based second set of eyes on every job.

## What It Checks
- Missing or extra pieces
- Quantity mismatches
- Length and weight discrepancies
- Standing Seam clip counts, backup plates, thermal blocks, and screw ratios based on panel coverage (16", 18", 24")
- Crane runway beams, braces, and special bolts
- Mezzanine framing vs buy-out joists
- Multi-phase shipper completeness
- Section size conflicts (e.g. AC column W14 vs W16)

## Tech Stack
- Python 3.11+
- pdfplumber / PyMuPDF for PDF extraction
- pandas + openpyxl
- Modular rules engine calibrated on real Ascent jobs

## Project Structure
```
chubby_checker/
├── parsers/          # Shipper & Drawings extractors
├── rules/            # Ascent-specific verification rules
├── models/           # Piece, Panel, Connection data models
├── report/           # Discrepancy report generators
├── cli.py
└── __init__.py
tests/
examples/
docs/
```

## Quick Start
```bash
pip install -r requirements.txt
python -m chubby_checker --drawings finals.pdf --shipper shipper.pdf
```

## Status
Early scaffold. Real job data from 25-13266, 25-13059, and 25-13168 is being used to harden parsers and rules.

---
Built for Ascent Buildings internal quality control.
