# Chubby Checker

**Official product name:** Chubby Checker  
**Company:** Ascent Buildings  
**Desktop shortcut label:** Ascent Chubby

Internal PEMB verification tool for **Ascent Buildings**.  
Compares Complete Shipper PDFs against Final Drawings and produces a dated PDF report (`CC_Checked_{Job}_{Date}.pdf`).

---

## Access

Licensed for internal Ascent Buildings use.

**Access code:** `Twist`

You can supply it three ways:

```bash
# 1. Interactive prompt (default)
python -m chubby_checker --shipper shipper.pdf --drawings finals.pdf --job 25-13168

# 2. CLI flag
python -m chubby_checker --access-code Twist --shipper shipper.pdf ...

# 3. Environment variable (good for scripts)
export ASCENT_SHIPPER_CHECKER_CODE=Twist
python -m chubby_checker --shipper shipper.pdf ...
```

> This is a simple internal gate, not cryptographic security. Anyone with the source can see the code.

---

## Install

```bash
git clone <ascent-buildings-repo-url>
cd Chubby-Checker   # or Ascent-Shipper-Checker
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Optional editable install:

```bash
pip install -e .
```

---

## Usage

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

### Desktop GUI (Ascent Chubby)

```bash
pip install -r requirements.txt   # includes tkinterdnd2 for PDF drag-and-drop
python tools/gui_launcher.py
# or double-click the Desktop "Ascent Chubby" shortcut (silent VBS launch)
```

- **Drag-and-drop** PDFs onto the main window / drop zone (requires `tkinterdnd2`).
- **Browse...** always works if drag-and-drop is unavailable.
- Access code: **Twist1960**

---

## What it checks

- Primary & secondary framing (mark-by-mark, lengths)
- Standing seam accessories (clips, thermal blocks, backup plates, screws)
- Exposed fastener panels (R-Loc/PBR, 7.2, M-Loc, PBA)
- Closures, trim, gutters, downspouts
- Weight roll-up
- Crane / mezzanine system flags
- Buy-outs correctly excluded (insulation, IMPs, New Millennium joist/deck, door/window units, etc.)

---

## Report

Produces:

```text
CC_Checked_{JobNumber}_{YYYY-MM-DD}.pdf
```

- **NO ERRORS** banner when clean  
- **ERRORS FOUND** with CRITICAL / WARNING detail when issues exist

---

## Transfer / licensing note

This repository is intended to be transferred to an Ascent Buildings-controlled GitHub (or other) account.  
Ascent Buildings may license and use the software internally under their own policies.

Codename **Chubby Checker** remains in the codebase for continuity.
