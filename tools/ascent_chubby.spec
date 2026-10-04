# -*- mode: python ; coding: utf-8 -*-
"""One-file Windows build. Double-click Build Ascent Chubby.bat in the repo root."""
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

root = os.path.abspath(os.path.join(SPECPATH, os.pardir))
if root not in sys.path:
    sys.path.insert(0, root)

datas = []
binaries = []
hiddenimports = collect_submodules("chubby_checker")
hiddenimports += [
    "tkinter",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "tkinter.ttk",
    "cv2",
    "fitz",
    "pdfplumber",
    "pdfminer",
    "reportlab",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "tkinterdnd2",
    "pandas",
    "numpy",
    "openpyxl",
    "click",
    "rich",
    "dotenv",
]

loading = os.path.join(root, "Loading.mp4")
if os.path.isfile(loading):
    datas.append((loading, "."))

assets = os.path.join(root, "assets")
if os.path.isdir(assets):
    datas.append((assets, "assets"))

launcher = os.path.join(root, "tools", "gui_launcher.py")
if os.path.isfile(launcher):
    datas.append((launcher, "tools"))

for pkg in (
    "tkinterdnd2",
    "cv2",
    "fitz",
    "pdfplumber",
    "pdfminer",
    "reportlab",
    "PIL",
    "pandas",
    "numpy",
    "openpyxl",
):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

icon = os.path.join(root, "assets", "branding", "ascent_chubby.ico")

a = Analysis(
    [os.path.join(root, "tools", "ascent_desktop.py")],
    pathex=[root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Ascent Chubby",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=icon if os.path.isfile(icon) else None,
)
