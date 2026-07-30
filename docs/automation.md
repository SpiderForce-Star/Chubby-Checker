# Automated PDF Report Generation

**Ascent Shipper Checker** can generate verification PDFs automatically for one job or a whole folder of jobs.

## Single job (CLI)

PDF output is **on by default**:

```bash
python -m chubby_checker \
  --access-code Twist \
  --shipper path/to/25-13168-Complete-Shipper.pdf \
  --drawings path/to/25-13168-FINAL-Drawings.pdf \
  --job 25-13168 \
  --output-dir ./reports
```

Report file:

```text
CC_Checked_25-13168_YYYY-MM-DD.pdf
```

Job number is auto-detected from filenames when `--job` is omitted.

## Batch folder (recommended for QC queues)

```bash
python tools/auto_report.py \
  --access-code Twist \
  --jobs-dir ./jobs \
  --output-dir ./reports
```

### What it finds

| Role | Filename hints |
|------|----------------|
| Shipper | `Shipper`, `Complete Shipper`, `BOM`, `PH1`…`PH6` |
| Drawings | `FINAL`, `Finals`, `Erection`, `Drawings` |
| Job number | Pattern `YY-#####` e.g. `25-13168` |

Supports:
- Flat folders with mixed PDFs
- Subfolders per job
- Multi-phase shippers for the same job number

### Useful flags

```bash
# Preview discovery only
python tools/auto_report.py --jobs-dir ./jobs --dry-run

# Limit to specific jobs
python tools/auto_report.py --jobs-dir ./jobs --only 25-13168 --only 25-13059

# Watermarks are off by default (no diagonal page text)
python tools/auto_report.py --jobs-dir ./jobs
```

## Programmatic API

```python
from chubby_checker.automation import run_job, run_batch

result = run_job(
    shippers=["shipper.pdf"],
    drawings="finals.pdf",
    output_dir="./reports",
)
print(result.report_path, result.critical, result.warning)

results = run_batch("./jobs", output_dir="./reports")
```

## Output

Every successful run writes:

```text
CC_Checked_{JobNumber}_{YYYY-MM-DD}.pdf
```

with Ascent logo in the header and NO ERRORS / ERRORS FOUND status banner (no page watermarks).
