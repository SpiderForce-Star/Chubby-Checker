#!/usr/bin/env python3
"""Chubby Checker GUI Launcher — Windows-safe single-mainloop startup."""
from __future__ import annotations
import os
import sys
import threading
import webbrowser
from pathlib import Path
from tkinter import (
    Tk, Frame, Label, Entry, Button, Text, Scrollbar, StringVar, Toplevel,
    filedialog, messagebox, END, DISABLED, NORMAL, BOTH, X, Y, LEFT, RIGHT, W,
)

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from chubby_checker.auth import validate_license_key, PRODUCT_NAME
from chubby_checker.automation import run_job, extract_job_number
from chubby_checker.branding import find_logo, COMPANY_NAME

ACCESS_CODEWORD = "Twist1960"
_NORMAL_BG = "#f0f0f0"
_DROP_BG = "#e3f2fd"
_DROP_BORDER = "#1565c0"
_DROP_OVERLAY_FG = "#0d47a1"
_PULSE_COLORS = ("#1565c0", "#1e88e5", "#42a5f5", "#1e88e5")
_PULSE_INTERVAL_MS = 140
_PULSE_THICKNESS = 3


def _find_loading_video() -> Path | None:
    for p in (
        _ROOT / "Loading.mp4",
        _ROOT / "assets" / "Loading.mp4",
        _ROOT / "assets" / "branding" / "Loading.mp4",
        Path.cwd() / "Loading.mp4",
    ):
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def _log(msg: str) -> None:
    print(f"[Chubby Checker] {msg}", flush=True)


class AppLauncher:
    """Intro → access gate → main GUI using one Tk mainloop (Windows-safe)."""

    def __init__(self) -> None:
        self.root = Tk()
        self.root.withdraw()
        self.root.title("Chubby Checker")
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        self._apply_window_icon(self.root)
        self._photo_holder = None
        self._cap = None
        self._intro_done = False
        self._gui = None

    @staticmethod
    def _apply_window_icon(win) -> None:
        """Taskbar / window icon from assets/branding/ascent_chubby.ico when present."""
        for rel in (
            "assets/branding/ascent_chubby.ico",
            "assets/branding/chubby_checker.ico",
            "assets/branding/ascent_shipper_checker.ico",
        ):
            ico = _ROOT / rel
            if ico.is_file():
                try:
                    win.iconbitmap(default=str(ico))
                except Exception:
                    try:
                        win.iconbitmap(str(ico))
                    except Exception:
                        pass
                return

    def run(self) -> None:
        _log("Launch sequence starting")
        if os.environ.get("CHUBBY_SKIP_INTRO", "").strip().lower() in {"1", "true", "yes"}:
            _log("CHUBBY_SKIP_INTRO set — skipping video")
            self.root.after(50, self._show_access_gate)
        else:
            self.root.after(50, self._show_intro)
        self.root.mainloop()

    def _show_intro(self) -> None:
        _log("Intro phase")
        video_path = _find_loading_video()
        _log(f"Video path: {video_path}")

        splash = Toplevel(self.root)
        splash.title("Chubby Checker")
        splash.configure(bg="#0d1117")
        splash.overrideredirect(True)
        try:
            splash.attributes("-topmost", True)
        except Exception:
            pass

        disp_w, disp_h = 720, 405
        sw, sh = splash.winfo_screenwidth(), splash.winfo_screenheight()
        x = max(0, (sw - disp_w) // 2)
        y = max(0, (sh - disp_h) // 2)
        splash.geometry(f"{disp_w}x{disp_h}+{x}+{y}")
        splash.update_idletasks()

        frame = Frame(splash, bg="#0d1117", width=disp_w, height=disp_h)
        frame.pack(fill=BOTH, expand=True)
        frame.pack_propagate(False)
        label = Label(
            frame, bg="#0d1117", fg="#e6edf3",
            text="Chubby Checker\nLoading…",
            font=("Segoe UI", 16, "bold"), justify="center",
        )
        label.pack(fill=BOTH, expand=True)
        Label(
            splash, text="Press Esc or click to skip",
            bg="#0d1117", fg="#8b949e", font=("Segoe UI", 9),
        ).place(relx=0.5, rely=0.97, anchor="s")

        self._splash = splash
        self._intro_label = label
        self._intro_done = False

        def finish(event=None):
            if self._intro_done:
                return
            self._intro_done = True
            _log("Intro finished — opening access gate")
            try:
                if self._cap is not None:
                    self._cap.release()
                    self._cap = None
            except Exception:
                pass
            try:
                splash.destroy()
            except Exception:
                pass
            self.root.after(30, self._show_access_gate)

        splash.bind("<Escape>", finish)
        splash.bind("<Button-1>", finish)
        label.bind("<Button-1>", finish)
        splash.protocol("WM_DELETE_WINDOW", finish)
        splash.after(17000, finish)

        played = False
        if video_path is not None:
            try:
                import cv2  # type: ignore
                cap = cv2.VideoCapture(str(video_path))
                self._cap = cap
                if not cap.isOpened():
                    _log("OpenCV could not open video")
                else:
                    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
                    delay_ms = max(20, min(60, int(1000 / max(fps, 1))))
                    _log(f"Playing video fps={fps:.1f} delay_ms={delay_ms}")

                    def tick():
                        if self._intro_done:
                            return
                        try:
                            ok, fr = cap.read()
                        except Exception as exc:
                            _log(f"Frame read error: {exc}")
                            finish()
                            return
                        if not ok or fr is None:
                            finish()
                            return
                        try:
                            h, w = fr.shape[:2]
                            scale = min(disp_w / max(w, 1), disp_h / max(h, 1))
                            nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                            fr = cv2.resize(fr, (nw, nh), interpolation=cv2.INTER_AREA)
                            fr = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)
                            try:
                                from PIL import Image, ImageTk
                                img = ImageTk.PhotoImage(Image.fromarray(fr))
                            except Exception:
                                ppm = f"P6 {nw} {nh} 255 ".encode("ascii") + fr.tobytes()
                                img = __import__("tkinter").PhotoImage(data=ppm, format="PPM")
                            self._photo_holder = img
                            label.configure(image=img, text="")
                        except Exception:
                            pass
                        if not self._intro_done:
                            splash.after(delay_ms, tick)

                    played = True
                    splash.after(20, tick)
            except Exception as exc:
                _log(f"Video backend error: {exc}")
                played = False

        if not played:
            _log("Fallback branded splash (2.5s)")
            label.configure(
                text="Chubby Checker\nAscent Buildings",
                font=("Segoe UI", 18, "bold"), fg="#e6edf3",
            )
            splash.after(2500, finish)

        try:
            splash.focus_force()
        except Exception:
            pass

    def _show_access_gate(self) -> None:
        _log("Access gate phase")

        gate = Toplevel(self.root)
        gate.title("Chubby Checker - Access")
        gate.resizable(False, False)
        gate.configure(bg="#f5f5f5")

        w, h = 400, 210
        x = (gate.winfo_screenwidth() // 2) - (w // 2)
        y = (gate.winfo_screenheight() // 2) - (h // 2)
        gate.geometry(f"{w}x{h}+{x}+{y}")

        try:
            gate.attributes("-topmost", True)
        except Exception:
            pass
        gate.lift()
        gate.deiconify()
        try:
            gate.focus_force()
        except Exception:
            pass

        try:
            self.root.geometry("1x1+-200+-200")
            self.root.deiconify()
            self.root.update_idletasks()
        except Exception:
            pass

        frame = Frame(gate, padx=24, pady=18, bg="#f5f5f5")
        frame.pack(fill=BOTH, expand=True)
        Label(frame, text="Chubby Checker", font=("Segoe UI", 14, "bold"), bg="#f5f5f5").pack(anchor=W)
        Label(
            frame, text="Enter access code to continue",
            fg="#555", font=("Segoe UI", 9), bg="#f5f5f5",
        ).pack(anchor=W, pady=(0, 10))

        code_var = StringVar()
        entry = Entry(frame, textvariable=code_var, show="*", width=34, font=("Segoe UI", 11))
        entry.pack(fill=X, pady=4)
        entry.focus_set()

        status = Label(frame, text="", fg="#b71c1c", font=("Segoe UI", 9), bg="#f5f5f5")
        status.pack(anchor=W, pady=(2, 8))

        def close_denied():
            _log("Access cancelled")
            try:
                gate.destroy()
            except Exception:
                pass
            try:
                self.root.destroy()
            except Exception:
                pass
            sys.exit(0)

        def try_unlock(event=None):
            val = code_var.get().strip()
            if not val:
                status.config(text="Access code required.")
                return
            info = validate_license_key(val)
            if info.valid or val == ACCESS_CODEWORD:
                _log("Access granted")
                try:
                    gate.attributes("-topmost", False)
                except Exception:
                    pass
                try:
                    gate.destroy()
                except Exception:
                    pass
                self.root.after(30, self._show_main)
            else:
                status.config(text="Invalid access code.")
                entry.select_range(0, END)
                entry.focus_set()

        btn_row = Frame(frame, bg="#f5f5f5")
        btn_row.pack(fill=X)
        Button(btn_row, text="Unlock", command=try_unlock, width=12, bg="#1a7f37", fg="white").pack(side=LEFT)
        Button(btn_row, text="Cancel", command=close_denied, width=10).pack(side=LEFT, padx=8)
        entry.bind("<Return>", try_unlock)
        gate.protocol("WM_DELETE_WINDOW", close_denied)

        try:
            gate.grab_set()
        except Exception:
            pass
        gate.update_idletasks()
        _log("Access gate is visible — enter Twist1960")

    def _show_main(self) -> None:
        _log("Main UI phase")
        try:
            self.root.withdraw()
        except Exception:
            pass
        self.root.geometry("760x620")
        self.root.deiconify()
        self.root.lift()
        try:
            self.root.focus_force()
        except Exception:
            pass
        self._gui = ChubbyCheckerGUI(self.root)
        _log("Main window ready")


class ChubbyCheckerGUI:
    def __init__(self, root):
        self.root = root; self.root.title("Chubby Checker"); self.root.minsize(680, 560); self.root.geometry("760x620"); self.root.configure(bg=_NORMAL_BG)
        self.shipper_paths = []; self.drawings_paths = []; self.report_path = None
        self._drag_active = False; self._pulse_after_id = None; self._pulse_index = 0; self._last_pulse_color = None
        self._build_ui(); self._center(); self._enable_dnd()
    def _build_ui(self):
        pad = {"padx": 10, "pady": 4}
        self.main = Frame(self.root, padx=12, pady=10, bg=_NORMAL_BG); self.main.pack(fill=BOTH, expand=True)
        header = Frame(self.main, bg=_NORMAL_BG); header.pack(fill=X, pady=(0, 6))
        logo_path = find_logo()
        if logo_path:
            try:
                if logo_path.suffix.lower() in {".png", ".gif"}:
                    from tkinter import PhotoImage
                    img = PhotoImage(file=str(logo_path))
                    if img.width() > 120: img = img.subsample(max(1, img.width()//100), max(1, img.width()//100))
                    self._logo_img = img; Label(header, image=self._logo_img, bg=_NORMAL_BG).pack(side=LEFT, padx=(0,12))
                elif logo_path.suffix.lower() in {".jpg", ".jpeg"}:
                    from PIL import Image, ImageTk
                    pil = Image.open(logo_path); pil.thumbnail((110, 60)); self._logo_img = ImageTk.PhotoImage(pil)
                    Label(header, image=self._logo_img, bg=_NORMAL_BG).pack(side=LEFT, padx=(0,12))
            except Exception: pass
        tf = Frame(header, bg=_NORMAL_BG); tf.pack(side=LEFT, fill=X, expand=True)
        Label(tf, text="Chubby Checker", font=("Segoe UI", 16, "bold"), bg=_NORMAL_BG).pack(anchor=W)
        Label(tf, text=COMPANY_NAME, font=("Segoe UI", 9), fg="#555", bg=_NORMAL_BG).pack(anchor=W)
        self.drop_zone = Frame(self.main, bg="#fafafa", highlightbackground="#cccccc", highlightthickness=2, padx=8, pady=8)
        self.drop_zone.pack(fill=X, pady=(4, 8))
        self.drop_hint = Label(self.drop_zone, text="v  Drag & drop Shipper / Drawings PDFs here  v", font=("Segoe UI", 10), fg="#666666", bg="#fafafa", pady=6)
        self.drop_hint.pack(fill=X)
        row = Frame(self.main, bg=_NORMAL_BG); row.pack(fill=X, **pad)
        Label(row, text="Shipper PDF(s)", width=14, anchor=W, bg=_NORMAL_BG).pack(side=LEFT)
        self.shipper_var = StringVar(value="(none selected)")
        Label(row, textvariable=self.shipper_var, anchor=W, fg="#333", bg=_NORMAL_BG).pack(side=LEFT, fill=X, expand=True)
        Button(row, text="Browse...", command=self._pick_shippers, width=10).pack(side=RIGHT)
        row = Frame(self.main, bg=_NORMAL_BG); row.pack(fill=X, **pad)
        Label(row, text="Drawings PDF(s)", width=14, anchor=W, bg=_NORMAL_BG).pack(side=LEFT)
        self.drawings_var = StringVar(value="(optional) - multi-file / phasing supported")
        Label(row, textvariable=self.drawings_var, anchor=W, fg="#333", bg=_NORMAL_BG).pack(side=LEFT, fill=X, expand=True)
        Button(row, text="Browse...", command=self._pick_drawings, width=10).pack(side=RIGHT)
        row = Frame(self.main, bg=_NORMAL_BG); row.pack(fill=X, **pad)
        Label(row, text="Job number", width=14, anchor=W, bg=_NORMAL_BG).pack(side=LEFT)
        self.job_var = StringVar(); Entry(row, textvariable=self.job_var, width=20).pack(side=LEFT)
        Label(row, text="(auto-detect if blank)", fg="#888", font=("Segoe UI", 8), bg=_NORMAL_BG).pack(side=LEFT, padx=6)
        row = Frame(self.main, bg=_NORMAL_BG); row.pack(fill=X, **pad)
        Label(row, text="Output folder", width=14, anchor=W, bg=_NORMAL_BG).pack(side=LEFT)
        self.output_var = StringVar(value=str(Path.cwd()/"reports"))
        Entry(row, textvariable=self.output_var).pack(side=LEFT, fill=X, expand=True, padx=(0,6))
        Button(row, text="Browse...", command=self._pick_output, width=10).pack(side=RIGHT)
        actions = Frame(self.main, bg=_NORMAL_BG); actions.pack(fill=X, pady=10)
        self.run_btn = Button(actions, text="  Run Check  ", command=self._start_run, font=("Segoe UI", 11, "bold"), bg="#1a7f37", fg="white", padx=12, pady=4); self.run_btn.pack(side=LEFT)
        self.open_btn = Button(actions, text="Open Report", command=self._open_report, state=DISABLED, padx=10); self.open_btn.pack(side=LEFT, padx=8)
        Button(actions, text="Clear Log", command=self._clear_log).pack(side=RIGHT)
        Label(self.main, text="Results", anchor=W, bg=_NORMAL_BG).pack(fill=X, pady=(4,0))
        log_frame = Frame(self.main, bg=_NORMAL_BG); log_frame.pack(fill=BOTH, expand=True, pady=4)
        self.log = Text(log_frame, height=12, wrap="word", font=("Consolas", 9), state=DISABLED)
        sb = Scrollbar(log_frame, command=self.log.yview); self.log.configure(yscrollcommand=sb.set)
        self.log.pack(side=LEFT, fill=BOTH, expand=True); sb.pack(side=RIGHT, fill=Y)
        self._log(f"{PRODUCT_NAME} ready.\nSelect or drop Complete Shipper PDF(s) to begin.")
    def _center(self):
        self.root.update_idletasks(); w,h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth()//2)-(w//2); y = (self.root.winfo_screenheight()//2)-(h//2); self.root.geometry(f"+{x}+{y}")
    def _enable_dnd(self):
        try:
            from tkinterdnd2 import DND_FILES
            self.root.drop_target_register(DND_FILES); self.drop_zone.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self._on_drop); self.root.dnd_bind("<<DragEnter>>", self._on_drag_enter); self.root.dnd_bind("<<DragLeave>>", self._on_drag_leave)
            self.drop_zone.dnd_bind("<<Drop>>", self._on_drop); self.drop_zone.dnd_bind("<<DragEnter>>", self._on_drag_enter); self.drop_zone.dnd_bind("<<DragLeave>>", self._on_drag_leave)
            self._log("Drag-and-drop enabled (with pulse animation).")
        except Exception:
            self._log("Drag-and-drop unavailable - install tkinterdnd2 for full support.")
    def _set_drop_visual(self, active):
        if active == self._drag_active:
            return
        self._drag_active = active
        if active:
            self.root.configure(bg=_DROP_BG)
            self.main.configure(bg=_DROP_BG)
            self.drop_zone.configure(bg=_DROP_BG, highlightbackground=_DROP_BORDER, highlightthickness=_PULSE_THICKNESS)
            self.drop_hint.configure(text="v  DROP PDFs HERE  v", fg=_DROP_OVERLAY_FG, bg=_DROP_BG, font=("Segoe UI", 11, "bold"))
            self._start_pulse()
        else:
            self._stop_pulse()
            self.root.configure(bg=_NORMAL_BG)
            self.main.configure(bg=_NORMAL_BG)
            self.drop_zone.configure(bg="#fafafa", highlightbackground="#cccccc", highlightthickness=2)
            self.drop_hint.configure(text="v  Drag & drop Shipper / Drawings PDFs here  v", fg="#666666", bg="#fafafa", font=("Segoe UI", 10))
    def _start_pulse(self):
        self._pulse_index = 0
        self._last_pulse_color = None
        if self._pulse_after_id is None:
            self._pulse_tick()
    def _stop_pulse(self):
        aid = self._pulse_after_id
        if aid is not None:
            try:
                self.root.after_cancel(aid)
            except Exception:
                pass
            self._pulse_after_id = None
        self._pulse_index = 0
        self._last_pulse_color = None
    def _pulse_tick(self):
        if not self._drag_active:
            self._pulse_after_id = None
            return
        color = _PULSE_COLORS[self._pulse_index % len(_PULSE_COLORS)]
        if color != self._last_pulse_color:
            try:
                self.drop_zone.configure(highlightbackground=color)
                self._last_pulse_color = color
            except Exception:
                self._pulse_after_id = None
                return
        self._pulse_index += 1
        self._pulse_after_id = self.root.after(_PULSE_INTERVAL_MS, self._pulse_tick)
    def _on_drag_enter(self, event): self._set_drop_visual(True)
    def _on_drag_leave(self, event): self._set_drop_visual(False)
    def _on_drop(self, event):
        self._set_drop_visual(False)
        self._add_dropped_files(self.root.tk.splitlist(event.data))
    def _add_dropped_files(self, paths):
        pdfs = [Path(p) for p in paths if str(p).lower().endswith(".pdf") and Path(p).is_file()]
        if not pdfs: self._log("Drop ignored - only PDF files are accepted."); return
        a_s=a_d=0
        for p in pdfs:
            name = p.name.lower()
            if any(k in name for k in ("final","drawing","drawings","ab ","permit","construction")):
                if p not in self.drawings_paths: self.drawings_paths.append(p); a_d += 1
            else:
                if p not in self.shipper_paths: self.shipper_paths.append(p); a_s += 1
        self._refresh_file_labels()
        if a_s or a_d:
            self._log(f"Dropped: {a_s} shipper, {a_d} drawings PDF(s).")
            if not self.job_var.get().strip() and self.shipper_paths:
                job = extract_job_number(*self.shipper_paths)
                if job: self.job_var.set(job); self._log(f"Detected job number: {job}")
    def _refresh_file_labels(self):
        if self.shipper_paths:
            n = ", ".join(p.name for p in self.shipper_paths); self.shipper_var.set(n if len(n)<90 else n[:87]+"...")
        else: self.shipper_var.set("(none selected)")
        if self.drawings_paths:
            n = ", ".join(p.name for p in self.drawings_paths); self.drawings_var.set(n if len(n)<90 else n[:87]+"...")
        else: self.drawings_var.set("(optional) - multi-file / phasing supported")
    def _log(self, msg):
        self.log.configure(state=NORMAL); self.log.insert(END, msg+"\n"); self.log.see(END); self.log.configure(state=DISABLED)
    def _clear_log(self):
        self.log.configure(state=NORMAL); self.log.delete("1.0", END); self.log.configure(state=DISABLED)
    def _pick_shippers(self):
        paths = filedialog.askopenfilenames(title="Select Complete Shipper PDF(s)", filetypes=[("PDF files","*.pdf"),("All files","*.*")])
        if not paths: return
        self.shipper_paths = [Path(p) for p in paths]; self._refresh_file_labels()
        if not self.job_var.get().strip():
            job = extract_job_number(*self.shipper_paths)
            if job: self.job_var.set(job); self._log(f"Detected job number: {job}")
    def _pick_drawings(self):
        paths = filedialog.askopenfilenames(title="Select Final Drawings PDF(s)", filetypes=[("PDF files","*.pdf"),("All files","*.*")])
        if not paths: return
        self.drawings_paths = [Path(p) for p in paths]; self._refresh_file_labels()
        if not self.job_var.get().strip():
            job = extract_job_number(*self.drawings_paths)
            if job: self.job_var.set(job)
    def _pick_output(self):
        path = filedialog.askdirectory(title="Select output folder")
        if path: self.output_var.set(path)
    def _open_report(self):
        if self.report_path and self.report_path.is_file(): webbrowser.open(self.report_path.as_uri())
        else: messagebox.showinfo("No report", "No report file is available yet.")
    def _start_run(self):
        if not self.shipper_paths: messagebox.showwarning("Missing shipper", "Please select at least one Complete Shipper PDF."); return
        self.run_btn.configure(state=DISABLED); self.open_btn.configure(state=DISABLED); self.report_path = None
        self._log("-"*48); self._log("Running check...")
        kwargs = {"shippers": list(self.shipper_paths), "drawings": self.drawings_paths[0] if self.drawings_paths else None,
                  "job_number": self.job_var.get().strip() or None, "output_dir": self.output_var.get().strip() or "./reports",
                  "watermark": False, "logo_path": find_logo()}
        threading.Thread(target=self._run_worker, args=(kwargs,), daemon=True).start()
    def _run_worker(self, kwargs):
        try:
            os.environ["ASCENT_SHIPPER_CHECKER_LICENSE"] = ACCESS_CODEWORD
            result = run_job(**kwargs)
        except Exception as exc:
            self.root.after(0, self._on_error, str(exc)); return
        self.root.after(0, self._on_done, result)
    def _on_error(self, msg):
        self._log(f"ERROR: {msg}"); self.run_btn.configure(state=NORMAL); messagebox.showerror("Check failed", msg)
    def _on_done(self, result):
        self.run_btn.configure(state=NORMAL)
        if not result.success:
            self._log(f"FAILED: {result.error}"); messagebox.showerror("Check failed", result.error or "Unknown error"); return
        self.report_path = Path(result.report_path) if result.report_path else None
        self._log(f"Job:      {result.job_number}"); self._log(f"CRITICAL: {result.critical}"); self._log(f"WARNING:  {result.warning}"); self._log(f"INFO:     {result.info}")
        if self.report_path: self._log(f"Report:   {self.report_path}"); self.open_btn.configure(state=NORMAL)
        if result.critical or result.warning:
            self._log("Status: ERRORS FOUND - review required before release.")
            messagebox.showwarning("Errors found", f"Job {result.job_number}\nCRITICAL: {result.critical}  WARNING: {result.warning}  INFO: {result.info}\n\nReport:\n{self.report_path}")
        else:
            self._log("Status: NO ERRORS")
            messagebox.showinfo("No errors", f"Job {result.job_number}\nNo discrepancies found.\n\nReport:\n{self.report_path}")


def main() -> None:
    AppLauncher().run()


if __name__ == "__main__":
    main()
