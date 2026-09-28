# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for dem_player (Windows onedir, no console).

Huge tools (ffmpeg, soundfonts, openmpt123, fluidsynth, furnace, zxtune)
are NOT baked into the archive — build.bat copies them next to the exe.
"""
from __future__ import annotations

import os

from PyInstaller.utils.hooks import collect_all

SPECDIR = os.path.dirname(os.path.abspath(SPEC))
CONSOLE = os.environ.get("DEM_PLAYER_CONSOLE", "0") == "1"
ICON = os.path.join(SPECDIR, "FPT.ico")
if not os.path.isfile(ICON):
    ICON = None

datas, binaries, hidden = [], [], []
for pkg in ("PySide6", "miniaudio", "sounddevice", "mutagen", "numpy"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hidden += h
    except Exception:
        hidden.append(pkg)

for name in ("font.ttf", "FPT.ico", "Background.png", "background.png"):
    p = os.path.join(SPECDIR, name)
    if os.path.isfile(p):
        datas.append((p, "."))

a = Analysis(
    [os.path.join(SPECDIR, "main.py")],
    pathex=[SPECDIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden + [
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "miniaudio",
        "sounddevice",
        "mutagen",
        "numpy",
        "core",
        "storage",
        "audio",
        "converters",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PyQt5", "PyQt6", "IPython", "pytest", "unittest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="dem_player",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=CONSOLE,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="dem_player",
)
