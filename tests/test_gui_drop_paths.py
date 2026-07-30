"""Unit tests for Windows PDF drop path parsing (gui_launcher.parse_drop_paths)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# tools/ is not a package; import via path like the launcher does
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "tools"))

from gui_launcher import parse_drop_paths  # noqa: E402


@pytest.fixture()
def pdf_files(tmp_path: Path):
    shipper = tmp_path / "25-13168-Complete-Shipper.pdf"
    drawings = tmp_path / "25-13168 Final Drawings.pdf"
    other = tmp_path / "notes.txt"
    shipper.write_bytes(b"%PDF-1.4")
    drawings.write_bytes(b"%PDF-1.4")
    other.write_text("not a pdf")
    return shipper, drawings, other


class TestParseDropPaths:
    def test_braced_path_with_spaces(self, pdf_files):
        shipper, drawings, _ = pdf_files
        data = "{" + str(drawings) + "}"
        out = parse_drop_paths(data)
        assert drawings.resolve() in out

    def test_multiple_braced_paths(self, pdf_files):
        shipper, drawings, _ = pdf_files
        data = "{" + str(shipper) + "} {" + str(drawings) + "}"
        out = parse_drop_paths(data)
        assert shipper.resolve() in out
        assert drawings.resolve() in out
        assert len(out) == 2

    def test_tk_splitlist(self, pdf_files):
        shipper, drawings, _ = pdf_files
        data = "{" + str(shipper) + "} {" + str(drawings) + "}"

        def splitlist(s: str):
            # mimic Tcl: return unbraced tokens
            import re
            return re.findall(r"\{([^{}]+)\}", s)

        out = parse_drop_paths(data, tk_splitlist=splitlist)
        assert len(out) == 2

    def test_file_uri(self, pdf_files):
        shipper, _, _ = pdf_files
        # file:///C:/... style
        uri = shipper.resolve().as_uri()
        out = parse_drop_paths(uri)
        assert shipper.resolve() in out

    def test_ignores_non_pdf(self, pdf_files):
        _, _, other = pdf_files
        out = parse_drop_paths(str(other))
        assert out == []

    def test_quoted_path(self, pdf_files):
        shipper, _, _ = pdf_files
        data = f'"{shipper}"'
        out = parse_drop_paths(data)
        assert shipper.resolve() in out

    def test_bad_data_no_crash(self):
        assert parse_drop_paths(None) == []
        assert parse_drop_paths("") == []
        assert parse_drop_paths("{C:\\no\\such\\file.pdf}") == []
        assert parse_drop_paths(12345) == []

    def test_dedupe(self, pdf_files):
        shipper, _, _ = pdf_files
        data = "{" + str(shipper) + "} {" + str(shipper) + "}"
        out = parse_drop_paths(data)
        assert len(out) == 1
