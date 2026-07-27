# Chubby-Checker

**Ascent Buildings BOM / Shipper vs Final Drawings Verification Tool**

Cross-checks Ascent Complete Shippers against Final Erection Drawings to catch quantity, length, weight, missing piece, clip/fastener, panel, framing, and accessory errors before release.

## Install

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# optional editable install:
pip install -e .
```

## Run

```bash
python -m chubby_checker \
  --shipper path/to/Complete_Shipper.pdf \
  --drawings path/to/Final_Drawings.pdf \
  --job 25-13168 \
  --output-dir ./reports
```

Multi-phase:

```bash
python -m chubby_checker \
  --shipper PH1.pdf --shipper PH3.pdf --shipper PH4.pdf \
  --drawings finals.pdf \
  --job 25-13168
```

PDF report filename: `CC_Checked_{JobNumber}_{YYYY-MM-DD}.pdf`

Use `--no-pdf` for console-only output.

## What it checks

- Primary & secondary framing presence and mark inventory
- Mark-by-mark quantity and length vs drawings
- Standing Seam clips, thermal blocks, backup plates, clip screws
- Exposed panels (R-Loc/PBR, 7.2, M-Loc, PBA)
- Closures, trim, gutters, downspouts (+ geometry length formulas when L/W known)
- Buy-outs excluded from missing-piece flags (insulation, IMP, joist/deck, doors, windows, louvers, skylights, vents, fans)
- Weight roll-up vs index totals
- Crane / mezzanine system flags
- Multi-phase shipper merge

## Project layout

```
chubby_checker/
  cli.py
  parsers/     # shipper, drawings, multi-phase
  rules/       # engine, framing, buyouts, accessories, weights, panels
  report/      # PDF report
  models/
  utils/
docs/
requirements.txt
pyproject.toml
```

## Status

Production-ready for internal QC use. Calibrated on jobs 25-13266, 25-13059, 25-13168.

Built for Ascent Buildings internal quality control.
