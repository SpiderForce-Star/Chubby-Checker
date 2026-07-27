"""
Automated job discovery and PDF report generation for Ascent Shipper Checker.

Finds shipper + drawings pairs by job number, runs the discrepancy engine,
and always writes CC_Checked_{Job}_{Date}.pdf reports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from chubby_checker.branding import find_logo
from chubby_checker.parsers.shipper_parser import ShipperParser
from chubby_checker.parsers.drawings_parser import DrawingsParser
from chubby_checker.rules.engine import DiscrepancyEngine
from chubby_checker.report.pdf_report import generate_pdf_report, build_report_filename

# Ascent job numbers look like 25-13168, 25-13059, 24-10001
JOB_RE = re.compile(r"(?P<job>\d{2}-\d{4,6})"
)

SHIPPER_HINTS = (
    "shipper", "complete shipper", "bom", "ph1", "ph2", "ph3", "ph4", "ph5", "ph6",
)
DRAWINGS_HINTS = (
    "final", "finals", "erection", "drawing", "drawings", "edgws", "edgs",
)


@dataclass
class JobBundle:
    job_number: str
    shippers: List[Path] = field(default_factory=list)
    drawings: Optional[Path] = None
    source_dir: Optional[Path] = None

    @property
    def ready(self) -> bool:
        return bool(self.shippers)


@dataclass
class RunResult:
    job_number: str
    success: bool
    report_path: Optional[Path] = None
    critical: int = 0
    warning: int = 0
    info: int = 0
    error: Optional[str] = None
    findings: List[Any] = field(default_factory=list)


def extract_job_number(*paths: Path | str) -> Optional[str]:
    """Pull first Ascent-style job number from file/folder names."""
    for p in paths:
        name = Path(p).name if p else ""
        m = JOB_RE.search(name)
        if m:
            return m.group("job")
        # also check parent folder name
        parent = Path(p).parent.name if p else ""
        m = JOB_RE.search(parent)
        if m:
            return m.group("job")
    return None


def _is_shipper(path: Path) -> bool:
    n = path.name.lower()
    if path.suffix.lower() != ".pdf":
        return False
    return any(h in n for h in SHIPPER_HINTS)


def _is_drawings(path: Path) -> bool:
    n = path.name.lower()
    if path.suffix.lower() != ".pdf":
        return False
    return any(h in n for h in DRAWINGS_HINTS)


def discover_jobs(root: Path, recursive: bool = True) -> List[JobBundle]:
    """
    Scan a folder for PDF pairs grouped by job number.

    Supports:
      - flat folder with mixed shipper/final PDFs
      - subfolders named by job number
      - multi-phase shippers for the same job
    """
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"Jobs directory not found: {root}")

    pdfs = list(root.rglob("*.pdf") if recursive else root.glob("*.pdf"))
    bundles: Dict[str, JobBundle] = {}

    for pdf in sorted(pdfs):
        job = extract_job_number(pdf)
        if not job:
            continue
        bundle = bundles.setdefault(job, JobBundle(job_number=job, source_dir=root))
        if _is_shipper(pdf):
            if pdf not in bundle.shippers:
                bundle.shippers.append(pdf)
        elif _is_drawings(pdf):
            # Prefer names containing FINAL / ERECTION when multiple exist
            if bundle.drawings is None:
                bundle.drawings = pdf
            else:
                score_new = sum(1 for h in ("final", "erection") if h in pdf.name.lower())
                score_old = sum(1 for h in ("final", "erection") if h in bundle.drawings.name.lower())
                if score_new > score_old:
                    bundle.drawings = pdf
        else:
            # Unknown PDF with job number — treat as shipper fallback if none yet
            if not bundle.shippers and "shipper" not in pdf.name.lower():
                # only assign as drawings if final-like already handled above
                pass

    # Second pass: any job with PDFs but nothing classified — best-effort assign
    for pdf in sorted(pdfs):
        job = extract_job_number(pdf)
        if not job or job not in bundles:
            continue
        b = bundles[job]
        if not b.shippers and not _is_drawings(pdf):
            b.shippers.append(pdf)
        if b.drawings is None and _is_drawings(pdf):
            b.drawings = pdf

    return [b for b in bundles.values() if b.ready]


def _parse_shippers(shipper_paths: Sequence[Path]) -> Dict[str, Any]:
    paths = [Path(p) for p in shipper_paths]
    if len(paths) > 1:
        try:
            from chubby_checker.parsers.multi_phase import MultiPhaseShipper
            agg = MultiPhaseShipper([str(p) for p in paths])
            data = agg.parse() if hasattr(agg, "parse") else {}
            if data:
                return data
        except Exception:
            pass

    parser = ShipperParser(str(paths[0]))
    pieces = parser.parse()
    shipper_data: Dict[str, Any] = {
        "categories": pieces,
        "ss_accessories": parser.get_ss_accessories() if hasattr(parser, "get_ss_accessories") else {},
        "summary_weights": parser.get_summary_weights() if hasattr(parser, "get_summary_weights") else {},
        "panel_coverage": {},
        "mark_qty": {},
    }
    for plist in pieces.values():
        for p in plist:
            shipper_data["mark_qty"][p.mark] = shipper_data["mark_qty"].get(p.mark, 0) + p.quantity

    for extra in paths[1:]:
        ep = ShipperParser(str(extra))
        epieces = ep.parse()
        for cat, plist in epieces.items():
            shipper_data["categories"].setdefault(cat, []).extend(plist)
            for p in plist:
                shipper_data["mark_qty"][p.mark] = shipper_data["mark_qty"].get(p.mark, 0) + p.quantity
        if hasattr(ep, "get_ss_accessories"):
            for k, v in ep.get_ss_accessories().items():
                shipper_data["ss_accessories"][k] = shipper_data["ss_accessories"].get(k, 0) + v
    return shipper_data


def _parse_drawings(drawings_path: Optional[Path]) -> Dict[str, Any]:
    if not drawings_path:
        return {}
    dparser = DrawingsParser(str(drawings_path))
    member_tables = dparser.parse()
    data: Dict[str, Any] = {
        "member_tables": member_tables,
        "mark_quantity_map": dparser.get_mark_quantity_map() if hasattr(dparser, "get_mark_quantity_map") else {},
        "notes": dparser.get_notes() if hasattr(dparser, "get_notes") else {},
    }
    notes = data.get("notes") or {}
    if isinstance(notes, dict):
        if notes.get("has_mezzanine"):
            data["has_mezzanine"] = True
        if notes.get("has_crane"):
            data["has_crane"] = True
    return data


def run_job(
    shippers: Sequence[str | Path],
    drawings: Optional[str | Path] = None,
    job_number: Optional[str] = None,
    output_dir: str | Path = "./reports",
    watermark: bool = True,
    logo_path: Optional[str | Path] = None,
    check_date: Optional[datetime] = None,
) -> RunResult:
    """
    Full automated pipeline for one job:
      parse → discrepancy engine → PDF report (always generated)
    """
    shipper_paths = [Path(s) for s in shippers]
    drawings_path = Path(drawings) if drawings else None
    job = job_number or extract_job_number(*shipper_paths, drawings_path or Path())
    job = job or "UNKNOWN"
    check_date = check_date or datetime.now()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        shipper_data = _parse_shippers(shipper_paths)
        drawings_data = _parse_drawings(drawings_path)
        engine = DiscrepancyEngine(shipper_data=shipper_data, drawings_data=drawings_data)
        findings = engine.run()

        critical = sum(1 for f in findings if getattr(f, "severity", "").upper() == "CRITICAL")
        warning = sum(1 for f in findings if getattr(f, "severity", "").upper() == "WARNING")
        info = sum(1 for f in findings if getattr(f, "severity", "").upper() == "INFO")

        report_path = generate_pdf_report(
            discrepancies=findings,
            job_number=job,
            output_dir=output_dir,
            check_date=check_date,
            shipper_files=[str(p) for p in shipper_paths],
            drawings_file=str(drawings_path) if drawings_path else None,
            watermark=watermark,
            logo_path=logo_path or find_logo(),
        )

        return RunResult(
            job_number=job,
            success=True,
            report_path=report_path,
            critical=critical,
            warning=warning,
            info=info,
            findings=findings,
        )
    except Exception as exc:
        return RunResult(
            job_number=job,
            success=False,
            error=str(exc),
        )


def run_batch(
    jobs_dir: str | Path,
    output_dir: str | Path = "./reports",
    recursive: bool = True,
    watermark: bool = True,
    logo_path: Optional[str | Path] = None,
    only_jobs: Optional[Sequence[str]] = None,
) -> List[RunResult]:
    """Discover all jobs under jobs_dir and generate a PDF report for each."""
    bundles = discover_jobs(Path(jobs_dir), recursive=recursive)
    if only_jobs:
        allow = set(only_jobs)
        bundles = [b for b in bundles if b.job_number in allow]

    results: List[RunResult] = []
    for bundle in bundles:
        result = run_job(
            shippers=bundle.shippers,
            drawings=bundle.drawings,
            job_number=bundle.job_number,
            output_dir=output_dir,
            watermark=watermark,
            logo_path=logo_path,
        )
        results.append(result)
    return results
