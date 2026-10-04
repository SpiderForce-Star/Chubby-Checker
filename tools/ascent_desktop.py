"""Entry point for the one-file Windows build.

PyInstaller runs this file. It loads tools/gui_launcher.py and points
that launcher at the unpacked bundle so the video and icon are found.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# Static imports so the freezer follows the real app, not only this wrapper.
import chubby_checker.auth  # noqa: F401
import chubby_checker.automation  # noqa: F401
import chubby_checker.branding  # noqa: F401


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def _launcher_source() -> tuple[str, Path]:
    root = _bundle_root()
    candidates = [
        root / "tools" / "gui_launcher.py",
        Path(__file__).resolve().parent / "gui_launcher.py",
    ]
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8"), path
    raise FileNotFoundError("gui_launcher.py was not included in the build")


def _start() -> None:
    root = _bundle_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    if getattr(sys, "frozen", False):
        docs = Path.home() / "Documents"
        if docs.is_dir():
            os.chdir(docs)
    source, path = _launcher_source()
    old = "_ROOT = Path(__file__).resolve().parents[1]\n"
    new = "_ROOT = Path(__import__('sys')._MEIPASS)\n"
    if getattr(sys, "frozen", False):
        if old not in source:
            raise RuntimeError(
                "gui_launcher.py layout changed. Build again from the latest repo."
            )
        source = source.replace(old, new, 1)
    exec(compile(source, str(path), "exec"), {"__name__": "__main__", "__file__": str(path)})


def main() -> None:
    try:
        _start()
    except Exception:
        import traceback

        detail = traceback.format_exc()
        log_path = Path.home() / "Desktop" / "AscentChubby-error.log"
        try:
            log_path.write_text(detail, encoding="utf-8")
        except Exception:
            log_path = Path.home() / "AscentChubby-error.log"
            try:
                log_path.write_text(detail, encoding="utf-8")
            except Exception:
                log_path = None
        try:
            import tkinter.messagebox as messagebox

            where = str(log_path) if log_path else "the error log"
            messagebox.showerror(
                "Ascent Chubby",
                "Could not start.\n\nDetails saved to:\n" + where,
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
