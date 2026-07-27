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
from typing import Any, Dict, List, Optional, Sequence

from chubby_checker.branding import find_logo
from chubby_checker.errors import (
    ChubbyCheckerError,
    MissingDirectoryError,
    MissingFileError,
    EmptyInputError,
    require_shippers,
    optional_pdf,
    require_dir,
    require_pdf,
)
from chubby_checker.parsers.shipper_parser import ShipperParser
from chubby_checker.parsers.drawings_parser import DrawingsParser
from chubby_checker.rules.engine import DiscrepancyEngine
from chubby_checker.report.pdf_report import generate_pdf_report

JOB_RE = re.compile(r"(?P<job>\d{2}-\d{4,6})")

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
    for p in paths:
        if not p:
            continue
        name = Path(p).name
        m = JOB_RE.search(name)
        if m:
            return m.group("job")
        parent = Path(p).parent.name
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
    root = Path(root)
    if not root.exists():
        raise MissingDirectoryError(root, role="jobs directory")
    if not root.is_dir():
        raise MissingDirectoryError(root, role="jobs directory (not a directory)")

    pdfs = list(root.rglob("*.pdf") if recursive else root.glob("*.pdf"))
    if not pdfs:
        raise ChubbyCheckerError(
            f"No PDF files found under jobs directory: {root.resolve()}\n"
            "Add Complete Shipper and/or Final Drawings PDFs (filenames should "
            "include a job number like 25-13168)."
        )

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
            if bundle.drawings is None:
                bundle.drawings = pdf
            else:
                score_new = sum(1 for h in ("final", "erection") if h in pdf.name.lower())
                score_old = sum(1 for h in ("final", "erection") if h in bundle.drawings.name.lower())
                if score_new > score_old:
                    bundle.drawings = pdf

    for pdf in sorted(pdfs):
        job = extract_job_number(pdf)
        if not job or job not in bundles:
            continue
        b = bundles[job]
        if not b.shippers and not _is_drawings(pdf):
            b.shippers.append(pdf)
        if b.drawings is None and _is_drawings(pdf):
            b.drawings = pdf

    ready = [b for b in bundles.values() if b.ready]
    if not ready:
        raise ChubbyCheckerError(
            f"Found {len(pdfs)} PDF(s) under {root}, but none could be matched to a "
            f"shipper for a job number.\n"
            "Expected filenames like:\n"
            "  25-13168-Complete-Shipper.pdf\n"
            "  25-13168-FINAL-Drawings.pdf"
        )
    return ready


def _parse_shippers(shipper_paths: Sequence[Path]) -> Dict[str, Any]:
    paths = require_shippers(shipper_paths)

    if len(paths) > 1:
        try:
            from chubby_checker.parsers.multi_phase import MultiPhaseShipper
            agg = MultiPhaseShipper([str(p) for p in paths])
            data = agg.parse() if hasattr(agg, "parse") else {}
            if data:
                return data
        except MissingFileError:
            raise
        except Exception:
            pass

    try:
        parser = ShipperParser(str(paths[0]))
        pieces = parser.parse()
    except FileNotFoundError as exc:
        raise MissingFileError(paths[0], role="shipper PDF") from exc
    except Exception as exc:
        raise ChubbyCheckerError(
            f"Failed to parse shipper PDF '{paths[0].name}': {exc}"
        ) from exc

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
        try:
            ep = ShipperParser(str(extra))
            epieces = ep.parse()
        except FileNotFoundError as exc:
            raise MissingFileError(extra, role="shipper PDF (phase)") from exc
        except Exception as exc:
            raise ChubbyCheckerError(
                f"Failed to parse phase shipper '{extra.name}': {exc}"
            ) from exc
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
    path = require_pdf(drawings_path, role="drawings PDF")
    try:
        dparser = DrawingsParser(str(path))
        member_tables = dparser.parse()
    except FileNotFoundError as exc:
        raise MissingFileError(path, role="drawings PDF") from exc
    except Exception as exc:
        raise ChubbyCheckerError(
            f"Failed to parse drawings PDF '{path.name}': {exc}"
        ) from exc

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
      validate paths → parse → discrepancy engine → PDF report
    """
    job = job_number or "UNKNOWN"
    try:
        shipper_paths = require_shippers(shippers)
        drawings_path = optional_pdf(drawings, role="drawings PDF") if drawings else None
        job = job_number or extract_job_number(*shipper_paths, drawings_path or Path()) or "UNKNOWN"
        check_date = check_date or datetime.now()
        out = require_dir(output_dir, role="output directory", create=True)

        # Logo is optional — warn via result only if explicitly requested path is missing
        resolved_logo = None
        if logo_path:
            try:
                from chubby_checker.errors import require_file
                resolved_logo = require_file(logo_path, role="logo image")
            except MissingFileError as exc:
                return RunResult(
                    job_number=job,
                    success=False,
                    error=str(exc),
                )
        else:
            resolved_logo = find_logo()

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
            output_dir=out,
            check_date=check_date,
            shipper_files=[str(p) for p in shipper_paths],
            drawings_file=str(drawings_path) if drawings_path else None,
            watermark=watermark,
            logo_path=resolved_logo,
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
    except (MissingFileError, MissingDirectoryError, EmptyInputError, ChubbyCheckerError) as exc:
        return RunResult(job_number=job, success=False, error=str(exc))
    except FileNotFoundError as exc:
        return RunResult(
            job_number=job,
            success=False,
            error=f"Missing file: {exc.filename or exc}",
        )
    except Exception as exc:
        return RunResult(job_number=job, success=False, error=f"Unexpected error: {exc}")


def run_batch(
    jobs_dir: str | Path,
    output_dir: str | Path = "./reports",
    recursive: bool = True,
    watermark: bool = True,
    logo_path: Optional[str | Path] = None,
    only_jobs: Optional[Sequence[str]] = None,
) -> List[RunResult]:
    """Discover all jobs under jobs_dir and generate a PDF report for each."""
    root = Path(jobs_dir)
    if not root.exists():
        raise MissingDirectoryError(root, role="jobs directory")
    if not root.is_dir():
        raise MissingDirectoryError(root, role="jobs directory")

    bundles = discover_jobs(root, recursive=recursive)
    if only_jobs:
        allow = set(only_jobs)
        bundles = [b for b in bundles if b.job_number in allow]
        if not bundles:
            raise ChubbyCheckerError(
                f"No matching jobs for --only filter {sorted(allow)} under {root}"
            )

    results: List[RunResult] = []
    for bundle in bundles:
        # Skip shipper paths that disappeared between discovery and run
        existing = [p for p in bundle.shippers if p.is_file()]
        if not existing:
            results.append(RunResult(
                job_number=bundle.job_number,
                success=False,
                error=f"Shipper PDF(s) missing for job {bundle.job_number}",
            ))
            continue
        drawings = bundle.drawings if (bundle.drawings and bundle.drawings.is_file()) else None
        if bundle.drawings and drawings is None:
            results.append(RunResult(
                job_number=bundle.job_number,
                success=False,
                error=f"Drawings PDF missing: {bundle.drawings}",
            ))
            continue

        result = run_job(
            shippers=existing,
            drawings=drawings,
            job_number=bundle.job_number,
            output_dir=output_dir,
            watermark=watermark,
            logo_path=logo_path,
        )
        results.append(result)
    return results
