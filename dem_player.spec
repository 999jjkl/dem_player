# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for dem_player (Windows onedir, no console).

Do NOT collect_all('PySide6') — that pulls QtWebEngine/3D and balloons the build.
Huge tools (ffmpeg, soundfonts, ...) are copied next to the exe by build.bat.
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
for pkg in ("numpy", "mutagen"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hidden += h
    except Exception:
        hidden.append(pkg)

hidden += [
    "miniaudio",
    "sounddevice",
    "cffi",
    "_cffi_backend",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "core",
    "storage",
    "audio",
    "converters",
]

for name in ("font.ttf", "FPT.ico", "Background.png", "background.png"):
    p = os.path.join(SPECDIR, name)
    if os.path.isfile(p):
        datas.append((p, "."))

a = Analysis(
    [os.path.join(SPECDIR, "main.py")],
    pathex=[SPECDIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "PyQt5", "PyQt6", "IPython", "pytest", "unittest",
        "numpy.tests", "numpy.f2py.tests",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DExtras",
        "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtGraphs",
        "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSerialPort",
        "PySide6.QtLocation", "PySide6.QtPositioning",
        "PySide6.QtPdf", "PySide6.QtPdfWidgets",
        "PySide6.QtRemoteObjects", "PySide6.QtScxml",
        "PySide6.QtSensors", "PySide6.QtSerialBus",
        "PySide6.QtTextToSpeech", "PySide6.QtWebSockets",
        "PySide6.QtWebView", "PySide6.QtHttpServer",
        "PySide6.scripts",
    ],
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
