# Verification PDF Report

## Filename
```
CC_Checked_{JobNumber}_{YYYY-MM-DD}.pdf
```
Example: `CC_Checked_25-13168_2026-07-26.pdf`

## Content

### When clean
- Status banner: **NO ERRORS**
- Job number, check date, source files
- Summary counts (all zero for CRITICAL/WARNING)
- Statement that the shipper appears consistent with the drawings for the checks performed

### When issues exist
- Status banner (header only, not a page watermark): **ERRORS FOUND**
- Summary counts by severity
- Section **Errors / Discrepancies to Review** listing every CRITICAL and WARNING item with:
  - Category, rule id, message
  - Mark (when applicable)
  - Expected vs Actual values
- Informational notes (INFO severity) in a separate section

## CLI
```bash
python -m chubby_checker \
  --shipper path/to/shipper.pdf \
  --drawings path/to/finals.pdf \
  --job 25-13168 \
  --output-dir ./reports
```

Options:
- `--job` — used in the filename and report header
- `--output-dir` — where to write the PDF (default: current directory)
- `--no-pdf` — skip PDF generation (console only)
