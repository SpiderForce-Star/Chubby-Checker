"""
User-facing file and path errors for Ascent Shipper Checker.

Provides clear messages (not raw tracebacks) when expected inputs are missing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

PathLike = Union[str, Path]


class ChubbyCheckerError(Exception):
    """Base application error with a clean user message."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class MissingFileError(ChubbyCheckerError):
    """A required file path does not exist."""

    def __init__(self, path: PathLike, role: str = "file"):
        self.path = Path(path)
        self.role = role
        super().__init__(f"Missing {role}: {self.path}")


class MissingDirectoryError(ChubbyCheckerError):
    """A required directory does not exist."""

    def __init__(self, path: PathLike, role: str = "directory"):
        self.path = Path(path)
        self.role = role
        super().__init__(f"Missing {role}: {self.path}")


class EmptyInputError(ChubbyCheckerError):
    """Required inputs were not provided."""


def require_file(path: PathLike, role: str = "file") -> Path:
    """
    Resolve and verify a file exists and is a regular file.

    Raises MissingFileError with a clear message if not.
    """
    p = Path(path).expanduser()
    if not p.exists():
        raise MissingFileError(p, role=role)
    if not p.is_file():
        raise MissingFileError(p, role=f"{role} (path exists but is not a file)")
    if p.stat().st_size == 0:
        raise ChubbyCheckerError(f"{role.capitalize()} is empty (0 bytes): {p}")
    return p.resolve()


def require_pdf(path: PathLike, role: str = "PDF") -> Path:
    """Require an existing PDF file."""
    p = require_file(path, role=role)
    if p.suffix.lower() != ".pdf":
        raise ChubbyCheckerError(
            f"{role} must be a PDF file (.pdf), got: {p.name}"
        )
    return p


def require_dir(path: PathLike, role: str = "directory", create: bool = False) -> Path:
    """
    Verify a directory exists. Optionally create it (for output dirs).
    """
    p = Path(path).expanduser()
    if not p.exists():
        if create:
            try:
                p.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ChubbyCheckerError(
                    f"Could not create {role} '{p}': {exc}"
                ) from exc
            return p.resolve()
        raise MissingDirectoryError(p, role=role)
    if not p.is_dir():
        raise MissingDirectoryError(p, role=f"{role} (path exists but is not a directory)")
    return p.resolve()


def require_shippers(paths: Sequence[PathLike]) -> List[Path]:
    """Validate one or more shipper PDF paths."""
    if not paths:
        raise EmptyInputError(
            "No shipper PDF provided. Use --shipper path/to/Complete_Shipper.pdf"
        )
    resolved: List[Path] = []
    missing: List[str] = []
    for raw in paths:
        p = Path(raw).expanduser()
        if not p.exists() or not p.is_file():
            missing.append(str(p))
            continue
        if p.suffix.lower() != ".pdf":
            raise ChubbyCheckerError(f"Shipper must be a PDF, got: {p.name}")
        if p.stat().st_size == 0:
            raise ChubbyCheckerError(f"Shipper PDF is empty (0 bytes): {p}")
        resolved.append(p.resolve())
    if missing:
        listing = "\n  - ".join(missing)
        raise MissingFileError(
            missing[0],
            role=f"shipper PDF(s). Missing:\n  - {listing}",
        )
    return resolved


def optional_pdf(path: Optional[PathLike], role: str = "drawings PDF") -> Optional[Path]:
    """
    If path is provided, require it exists as a PDF.
    If path is None/empty, return None (allowed).
    """
    if path is None or str(path).strip() == "":
        return None
    return require_pdf(path, role=role)


def optional_file(path: Optional[PathLike], role: str = "file") -> Optional[Path]:
    if path is None or str(path).strip() == "":
        return None
    return require_file(path, role=role)


def format_missing_help(role: str, path: PathLike) -> str:
    """Extra hint text for common missing inputs."""
    p = Path(path)
    hints = {
        "shipper": (
            "Provide a Complete Shipper PDF, e.g.\n"
            "  --shipper 25-13168-Complete-Shipper.pdf"
        ),
        "drawings": (
            "Provide Final Erection Drawings PDF, e.g.\n"
            "  --drawings 25-13168-FINAL-Drawings.pdf"
        ),
        "jobs directory": (
            "Point --jobs-dir at a folder that contains shipper/drawings PDFs.\n"
            "Filenames should include a job number like 25-13168."
        ),
        "logo": (
            "Place the Ascent logo at assets/branding/ascent_logo.jpg\n"
            "or pass --logo /path/to/logo.jpg"
        ),
        "license": (
            "Provide a license via --access-code / --license,\n"
            "ASCENT_SHIPPER_CHECKER_LICENSE, or ascent_shipper_checker.lic"
        ),
    }
    key = role.lower().replace(" pdf", "").strip()
    for k, text in hints.items():
        if k in key:
            return f"{text}"
    return f"Check that the path exists and you have read permission:\n  {p}"
