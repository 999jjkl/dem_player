"""core.py — path helpers, logging, CUE/M3U, metadata, Windows extras.

No project-module imports. Optional: mutagen.
"""
from __future__ import annotations

import ctypes
import os
import re
import sys
import time

APP_VERSION = "0.21.5"

TIME_FORMAT_MM_SS = "mm_ss"
TIME_FORMAT_MM_SS_CC = "mm_ss_cc"

try:
    from mutagen import File as MutagenFile
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False


# ---------- paths ----------
def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def data_dir() -> str:
    path = os.path.join(app_dir(), "data")
    os.makedirs(path, exist_ok=True)
    return path


def logs_dir() -> str:
    path = os.path.join(data_dir(), "logs")
    os.makedirs(path, exist_ok=True)
    return path


def data_path(name: str) -> str:
    return os.path.join(data_dir(), name)


def resource_candidates(relative: str) -> list:
    """Places to look for a bundled or sidecar file (dev / frozen onedir / onefile)."""
    rel = relative.replace("/", os.sep)
    out = []
    here = os.path.dirname(os.path.abspath(__file__))
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if meipass:
            out.append(os.path.join(meipass, rel))
        out.append(os.path.join(exe_dir, rel))
    else:
        out.append(os.path.join(here, rel))
    try:
        out.append(os.path.join(os.getcwd(), rel))
    except Exception:
        pass
    seen = set()
    uniq = []
    for p in out:
        try:
            key = os.path.normcase(os.path.abspath(p))
        except Exception:
            key = p
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def resource_path(relative: str) -> str:
    cands = resource_candidates(relative)
    for p in cands:
        if os.path.isfile(p) or os.path.isdir(p):
            return p
    return cands[0] if cands else relative


# ---------- logging ----------
LOG_FILE = None
LOG_ENABLED = True
LOG_LEVEL = 20
LOG_LEVEL_NAMES = {10: "DEBUG", 20: "INFO", 30: "WARN", 40: "ERROR"}


def init_log() -> None:
    global LOG_FILE, LOG_ENABLED
    if not LOG_ENABLED or LOG_FILE:
        return
    try:
        os.makedirs(logs_dir(), exist_ok=True)
    except Exception:
        LOG_FILE = None
        return
    filename = time.strftime("player_data_%H.%M.%S-%d.%m.%Y.log", time.localtime())
    filepath = os.path.join(logs_dir(), filename)
    try:
        LOG_FILE = open(filepath, "w", encoding="utf-8")
    except Exception:
        LOG_FILE = None


def log(message: str, level: int = 20) -> None:
    global LOG_FILE, LOG_ENABLED, LOG_LEVEL
    if not LOG_ENABLED or not LOG_FILE:
        return
    if level < LOG_LEVEL:
        return
    stamp = time.strftime("%H:%M:%S", time.localtime())
    tag = LOG_LEVEL_NAMES.get(level, "INFO")
    try:
        LOG_FILE.write(f"[{stamp}] [{tag}] {message}\n")
        LOG_FILE.flush()
    except Exception:
        pass


def close_log() -> None:
    global LOG_FILE
    if LOG_FILE:
        try:
            log("---- Session ended ----")
            LOG_FILE.close()
        except Exception:
            pass
        LOG_FILE = None


# ---------- Windows extras ----------
def prevent_sleep(enable: bool) -> None:
    if sys.platform != "win32":
        return
    try:
        if enable:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000002)
        else:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    except Exception:
        pass


def apply_cpu_affinity() -> None:
    if sys.platform != "win32":
        return
    try:
        import multiprocessing
        total_cores = multiprocessing.cpu_count()
        if total_cores <= 1:
            return
        target_core = total_cores - 1
        mask = 1 << target_core
        kernel32 = ctypes.windll.kernel32
        kernel32.SetProcessAffinityMask(kernel32.GetCurrentProcess(), mask)
        max_ws = 512 * 1024 * 1024
        kernel32.SetProcessWorkingSetSize(kernel32.GetCurrentProcess(), -1, max_ws)
    except Exception:
        pass


def subprocess_hidden_kwargs() -> dict:
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess_create_no_window()
    return kwargs


def subprocess_create_no_window() -> int:
    if sys.platform == "win32":
        return getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0x08000000)
    return 0


# ---------- M3U ----------
def parse_m3u(m3u_path: str) -> list:
    items = []
    if not os.path.isfile(m3u_path):
        return items
    base_dir = os.path.dirname(os.path.abspath(m3u_path))
    try:
        with open(m3u_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                low = line.lower()
                if low.startswith("http://") or low.startswith("https://"):
                    items.append(line)
                else:
                    full = line if os.path.isabs(line) else os.path.join(base_dir, line)
                    if os.path.isfile(full):
                        items.append(full)
    except Exception as e:
        log(f"[M3U] {m3u_path}: {e}", 30)
    return items


# ---------- CUE ----------
def parse_cue_file(cue_path: str) -> list:
    tracks = []
    current = None
    cue_dir = os.path.dirname(os.path.abspath(cue_path))
    current_audio_file = None
    try:
        with open(cue_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        log(f"[CUE] Cannot read {cue_path}: {e}", 40)
        return tracks

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("FILE"):
            m = re.match(r'FILE\s+"(.+?)"\s+(\S+)', line, re.IGNORECASE)
            if m:
                rel = m.group(1)
                current_audio_file = rel if os.path.isabs(rel) else os.path.join(cue_dir, rel)
        elif upper.startswith("TRACK"):
            m = re.match(r"TRACK\s+(\d+)\s+(\S+)", line, re.IGNORECASE)
            if m:
                if current:
                    tracks.append(current)
                current = {
                    "number": int(m.group(1)),
                    "type": m.group(2).upper(),
                    "file": current_audio_file,
                    "title": "",
                    "performer": "",
                    "index01": 0,
                }
        elif upper.startswith("TITLE") and current is not None:
            m = re.match(r'TITLE\s+"?(.+?)"?\s*$', line, re.IGNORECASE)
            if m:
                current["title"] = m.group(1)
        elif upper.startswith("PERFORMER") and current is not None:
            m = re.match(r'PERFORMER\s+"?(.+?)"?\s*$', line, re.IGNORECASE)
            if m:
                current["performer"] = m.group(1)
        elif upper.startswith("INDEX") and current is not None:
            m = re.match(r"INDEX\s+(\d+)\s+(\d+):(\d+):(\d+)", line, re.IGNORECASE)
            if m:
                idx = int(m.group(1))
                mm = int(m.group(2))
                ss = int(m.group(3))
                ff = int(m.group(4))
                ms = mm * 60000 + ss * 1000 + int(ff * 1000 / 75)
                if idx == 1:
                    current["index01"] = ms
    if current:
        tracks.append(current)

    for i, t in enumerate(tracks):
        if i + 1 < len(tracks) and tracks[i + 1]["file"] == t["file"]:
            t["end_ms"] = tracks[i + 1]["index01"]
        else:
            t["end_ms"] = None
    return tracks


# ---------- metadata ----------
def read_metadata(track) -> dict | None:
    if not HAS_MUTAGEN:
        return None
    if isinstance(track, dict):
        path = track.get("path")
        cue_title = track.get("cue_title")
        cue_performer = track.get("cue_performer")
    else:
        path = track
        cue_title = None
        cue_performer = None
    if not path or str(path).startswith("http") or not os.path.isfile(path):
        return None
    try:
        audio = MutagenFile(path, easy=True)
        if audio is None:
            return None

        def first(key):
            v = audio.get(key)
            if isinstance(v, list) and v:
                return str(v[0])
            return None

        return {
            "title": cue_title or first("title"),
            "artist": cue_performer or first("artist"),
            "album": first("album"),
            "tracknumber": first("tracknumber"),
        }
    except Exception as e:
        log(f"[Meta] {path}: {e}", 30)
        return None
