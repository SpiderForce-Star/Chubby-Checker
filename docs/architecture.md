# Architecture

1. Ingest Final Drawings PDF + Shipper PDF(s)
2. Extract structured data (marks, qty, lengths, weights, panel coverage, clips, bolts)
3. Normalize lengths and piece marks
4. Run modular rules engine
5. Generate clear discrepancy report

Rules are calibrated against real jobs:
- 25-13266
- 25-13059 (crane + mezzanine)
- 25-13168 (multi-phase + standing seam)
