#!/usr/bin/env python3
"""
Ascent Shipper Checker — GUI Launcher

Double-click friendly front-end for Chubby Checker.
Pick shipper + drawings PDFs, enter job number / access code, run the check,
and open the PDF report when finished.

Usage:
  python tools/gui_launcher.py
  # or via the Desktop batch file (Windows)
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path
from tkinter import (
    Tk, Frame, Label, Entry, Button, Text, Scrollbar, StringVar,
    filedialog, messagebox, END, DISABLED, NORMAL, BOTH, X, Y, LEFT, RIGHT, W, E, N, S,
)

# ---------------------------------------------------------------------------
# Make sure the package is importable when launched from tools/ or Desktop
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from chubby_checker.auth import require_access, PRODUCT_NAME, CODENAME, validate_license_key
from chubby_checker.automation import run_job, extract_job_number
from chubby_checker.branding import find_logo, COMPANY_NAME


class ChubbyCheckerGUI:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title(f"{PRODUCT_NAME}  ·  {CODENAME}")
        self.root.minsize(640, 520)
        self.root.geometry("720x580")

        self.shipper_paths: list[Path] = []
        self.drawings_path: Path | None = None
        self.report_path: Path | None = None

        self._build_ui()
        self._center()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 4}
        main = Frame(self.root, padx=12, pady=10)
        main.pack(fill=BOTH, expand=True)

        # Header
        Label(
            main,
            text=PRODUCT_NAME,
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=W)
        Label(
            main,
            text=f"codename {CODENAME}  ·  {COMPANY_NAME}",
            font=("Segoe UI", 9),
            fg="#555",
        ).pack(anchor=W, pady=(0, 8))

        # ---- Shipper PDFs ----
        row = Frame(main)
        row.pack(fill=X, **pad)
        Label(row, text="Shipper PDF(s)", width=14, anchor=W).pack(side=LEFT)
        self.shipper_var = StringVar(value="(none selected)")
        Label(row, textvariable=self.shipper_var, anchor=W, fg="#333").pack(
            side=LEFT, fill=X, expand=True
        )
        Button(row, text="Browse…", command=self._pick_shippers, width=10).pack(side=RIGHT)

        # ---- Drawings PDF ----
        row = Frame(main)
        row.pack(fill=X, **pad)
        Label(row, text="Drawings PDF", width=14, anchor=W).pack(side=LEFT)
        self.drawings_var = StringVar(value="(optional)")
        Label(row, textvariable=self.drawings_var, anchor=W, fg="#333").pack(
            side=LEFT, fill=X, expand=True
        )
        Button(row, text="Browse…", command=self._pick_drawings, width=10).pack(side=RIGHT)

        # ---- Job number ----
        row = Frame(main)
        row.pack(fill=X, **pad)
        Label(row, text="Job number", width=14, anchor=W).pack(side=LEFT)
        self.job_var = StringVar()
        Entry(row, textvariable=self.job_var, width=20).pack(side=LEFT)
        Label(row, text="(auto-detect if blank)", fg="#888", font=("Segoe UI", 8)).pack(
            side=LEFT, padx=6
        )

        # ---- Access / license ----
        row = Frame(main)
        row.pack(fill=X, **pad)
        Label(row, text="Access code", width=14, anchor=W).pack(side=LEFT)
        self.access_var = StringVar(value="Twist")
        Entry(row, textvariable=self.access_var, width=28, show="*").pack(side=LEFT)
        Label(row, text="(legacy code or signed license)", fg="#888", font=("Segoe UI", 8)).pack(
            side=LEFT, padx=6
        )

        # ---- Output dir ----
        row = Frame(main)
        row.pack(fill=X, **pad)
        Label(row, text="Output folder", width=14, anchor=W).pack(side=LEFT)
        self.output_var = StringVar(value=str(Path.cwd() / "reports"))
        Entry(row, textvariable=self.output_var).pack(side=LEFT, fill=X, expand=True, padx=(0, 6))
        Button(row, text="Browse…", command=self._pick_output, width=10).pack(side=RIGHT)

        # ---- Actions ----
        actions = Frame(main)
        actions.pack(fill=X, pady=10)
        self.run_btn = Button(
            actions,
            text="  Run Check  ",
            command=self._start_run,
            font=("Segoe UI", 11, "bold"),
            bg="#1a7f37",
            fg="white",
            activebackground="#15632c",
            activeforeground="white",
            padx=12,
            pady=4,
        )
        self.run_btn.pack(side=LEFT)
        self.open_btn = Button(
            actions,
            text="Open Report",
            command=self._open_report,
            state=DISABLED,
            padx=10,
        )
        self.open_btn.pack(side=LEFT, padx=8)
        Button(actions, text="Clear Log", command=self._clear_log).pack(side=RIGHT)

        # ---- Log / results ----
        Label(main, text="Results", anchor=W).pack(fill=X, pady=(4, 0))
        log_frame = Frame(main)
        log_frame.pack(fill=BOTH, expand=True, pady=4)
        self.log = Text(log_frame, height=14, wrap="word", font=("Consolas", 9), state=DISABLED)
        sb = Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        self.log.pack(side=LEFT, fill=BOTH, expand=True)
        sb.pack(side=RIGHT, fill=Y)

        self._log(f"{PRODUCT_NAME} ready.\nSelect a Complete Shipper PDF to begin.")

    def _center(self) -> None:
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"+{x}+{y}")

    # -------------------------------------------------------------- helpers
    def _log(self, msg: str) -> None:
        self.log.configure(state=NORMAL)
        self.log.insert(END, msg + "\n")
        self.log.see(END)
        self.log.configure(state=DISABLED)

    def _clear_log(self) -> None:
        self.log.configure(state=NORMAL)
        self.log.delete("1.0", END)
        self.log.configure(state=DISABLED)

    def _pick_shippers(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select Complete Shipper PDF(s)",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not paths:
            return
        self.shipper_paths = [Path(p) for p in paths]
        names = ", ".join(p.name for p in self.shipper_paths)
        self.shipper_var.set(names if len(names) < 80 else names[:77] + "…")
        # Auto-fill job if empty
        if not self.job_var.get().strip():
            job = extract_job_number(*self.shipper_paths)
            if job:
                self.job_var.set(job)
                self._log(f"Detected job number: {job}")

    def _pick_drawings(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Final Drawings PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return
        self.drawings_path = Path(path)
        self.drawings_var.set(self.drawings_path.name)
        if not self.job_var.get().strip():
            job = extract_job_number(self.drawings_path)
            if job:
                self.job_var.set(job)

    def _pick_output(self) -> None:
        path = filedialog.askdirectory(title="Select output folder for PDF report")
        if path:
            self.output_var.set(path)

    def _open_report(self) -> None:
        if self.report_path and self.report_path.is_file():
            webbrowser.open(self.report_path.as_uri())
        else:
            messagebox.showinfo("No report", "No report file is available yet.")

    # --------------------------------------------------------------- run
    def _start_run(self) -> None:
        if not self.shipper_paths:
            messagebox.showwarning("Missing shipper", "Please select at least one Complete Shipper PDF.")
            return

        access = self.access_var.get().strip()
        if not access:
            messagebox.showwarning("Access required", "Enter the access code or license key.")
            return

        info = validate_license_key(access)
        if not info.valid:
            messagebox.showerror("Access denied", f"License validation failed:\n{info.message}")
            return

        self.run_btn.configure(state=DISABLED)
        self.open_btn.configure(state=DISABLED)
        self.report_path = None
        self._log("—" * 48)
        self._log("Running check…")

        kwargs = {
            "shippers": list(self.shipper_paths),
            "drawings": self.drawings_path,
            "job_number": self.job_var.get().strip() or None,
            "output_dir": self.output_var.get().strip() or "./reports",
            "watermark": True,
            "logo_path": find_logo(),
        }
        threading.Thread(target=self._run_worker, args=(kwargs,), daemon=True).start()

    def _run_worker(self, kwargs: dict) -> None:
        try:
            # Access already validated in UI; set env so deeper calls don't prompt
            os.environ["ASCENT_SHIPPER_CHECKER_LICENSE"] = self.access_var.get().strip()
            result = run_job(**kwargs)
        except Exception as exc:
            self.root.after(0, self._on_error, str(exc))
            return
        self.root.after(0, self._on_done, result)

    def _on_error(self, msg: str) -> None:
        self._log(f"ERROR: {msg}")
        self.run_btn.configure(state=NORMAL)
        messagebox.showerror("Check failed", msg)

    def _on_done(self, result) -> None:
        self.run_btn.configure(state=NORMAL)
        if not result.success:
            self._log(f"FAILED: {result.error}")
            messagebox.showerror("Check failed", result.error or "Unknown error")
            return

        self.report_path = Path(result.report_path) if result.report_path else None
        self._log(f"Job:      {result.job_number}")
        self._log(f"CRITICAL: {result.critical}")
        self._log(f"WARNING:  {result.warning}")
        self._log(f"INFO:     {result.info}")
        if self.report_path:
            self._log(f"Report:   {self.report_path}")
            self.open_btn.configure(state=NORMAL)

        if result.critical or result.warning:
            self._log("Status: ERRORS FOUND — review required before release.")
            messagebox.showwarning(
                "Errors found",
                f"Job {result.job_number}\n"
                f"CRITICAL: {result.critical}  WARNING: {result.warning}  INFO: {result.info}\n\n"
                f"Report:\n{self.report_path}",
            )
        else:
            self._log("Status: NO ERRORS")
            messagebox.showinfo(
                "No errors",
                f"Job {result.job_number}\nNo discrepancies found.\n\nReport:\n{self.report_path}",
            )


def main() -> None:
    root = Tk()
    # Prefer a slightly denser look on Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    ChubbyCheckerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
