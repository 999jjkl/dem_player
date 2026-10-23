"""core.py — path helpers, logging, CUE/M3U, metadata, Windows extras.

No project-module imports. Optional: mutagen.
"""
from __future__ import annotations

import ctypes
import os
import re
import sys
import time

APP_VERSION = "0.22.9"

TIME_FORMAT_MM_SS = "mm_ss"
TIME_FORMAT_MM_SS_CC = "mm_ss_cc"

try:
    from mutagen import File as MutagenFile
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False


def probe_file_duration_ms(path: str) -> int:
    """Read length from tags without playing. -1 if unknown."""
    if not path or not os.path.isfile(path):
        return -1
    if not HAS_MUTAGEN:
        return -1
    try:
        audio = MutagenFile(path)
        info = getattr(audio, "info", None) if audio is not None else None
        length = getattr(info, "length", None) if info is not None else None
        if length and float(length) > 0:
            return int(float(length) * 1000)
    except Exception:
        pass
    return -1


# ---------- paths ----------
def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def same_path(a, b) -> bool:
    """True if a and b are the same file. Windows is case-insensitive, so use normcase."""
    if not a or not b:
        return False
    try:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
    except Exception:
        return a == b


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


_OPEN_WITH_EXTS = (
    "mp3", "wav", "flac", "ogg", "m4a", "aac", "wma", "opus", "ac3",
    "mid", "midi", "rmi", "kar",
    "mod", "xm", "it", "s3m", "mptm", "mpt", "mt2", "stm",
    "ftm", "dnm", "sap", "sid", "tm8", "vgm", "vgz",
    "m3u", "m3u8",
)


def player_launch_command() -> str:
    """Command line Explorer should run for 'Open with dem_player'."""
    if getattr(sys, "frozen", False):
        return f'"{os.path.abspath(sys.executable)}" "%1"'
    script = os.path.abspath(sys.argv[0] if sys.argv else "main.py")
    return f'"{os.path.abspath(sys.executable)}" "{script}" "%1"'


def register_open_with() -> tuple:
    """HKCU only. Does not steal the default player. Returns (count, command)."""
    if sys.platform != "win32":
        raise OSError("Windows only")
    import winreg
    cmd = player_launch_command()
    app = r"Software\Classes\Applications\dem_player.exe"
    with winreg.CreateKey(winreg.HKCU, app + r"\shell\open\command") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
    with winreg.CreateKey(winreg.HKCU, app) as k:
        winreg.SetValueEx(k, "FriendlyAppName", 0, winreg.REG_SZ, "dem_player")
    with winreg.CreateKey(winreg.HKCU, app + r"\SupportedTypes") as k:
        for ext in _OPEN_WITH_EXTS:
            winreg.SetValueEx(k, "." + ext, 0, winreg.REG_SZ, "")
    for ext in _OPEN_WITH_EXTS:
        winreg.CreateKey(winreg.HKCU, rf"Software\Classes\.{ext}\OpenWithList\dem_player.exe").Close()
    log(f"[OpenWith] registered {cmd}", 20)
    return len(_OPEN_WITH_EXTS), cmd


def apply_window_blur(hwnd, enable: bool = False, opacity: int = 40, kind: str | None = None) -> bool:
    """kind: 'aero' frosted, 'qt' turn DWM glass off and leave Qt's layered bit alone, 'off' solid.

    'qt' is the 0.20 transparent path: no acrylic, no accent gradient.
    """
    if kind is None:
        kind = "aero" if enable else "off"
    if sys.platform != "win32":
        return False
    try:
        hwnd = int(hwnd)
    except Exception:
        return False

    user32 = ctypes.windll.user32
    dwmapi = ctypes.windll.dwmapi
    ok = False

    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    try:
        get_long = user32.GetWindowLongPtrW
        set_long = user32.SetWindowLongPtrW
    except Exception:
        get_long = user32.GetWindowLongW
        set_long = user32.SetWindowLongW
    try:
        if kind != "qt":
            ex = get_long(hwnd, GWL_EXSTYLE)
            if kind == "aero":
                set_long(hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED)
            elif ex & WS_EX_LAYERED:
                set_long(hwnd, GWL_EXSTYLE, ex & ~WS_EX_LAYERED)
    except Exception as e:
        log(f"[DWM] layered: {e}", 30)

    try:
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        # 1 = DWMSBT_NONE. 3 = acrylic. Only aero may set 3.
        backdrop_value = 3 if kind == "aero" else 1
        dark = ctypes.c_int(1 if kind == "aero" else 0)
        dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark), ctypes.sizeof(dark))
        backdrop = ctypes.c_int(backdrop_value)
        dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(backdrop), ctypes.sizeof(backdrop))
        ok = True
    except Exception as e:
        log(f"[DWM] backdrop: {e}", 30)

    class ACCENTPOLICY(ctypes.Structure):
        _fields_ = [
            ("AccentState", ctypes.c_int),
            ("AccentFlags", ctypes.c_int),
            ("GradientColor", ctypes.c_uint32),
            ("AnimationId", ctypes.c_int),
        ]

    class WINCOMPATTRDATA(ctypes.Structure):
        _fields_ = [
            ("Attribute", ctypes.c_int),
            ("Data", ctypes.POINTER(ACCENTPOLICY)),
            ("SizeOfData", ctypes.c_size_t),
        ]

    try:
        accent = ACCENTPOLICY()
        if kind == "aero":
            accent.AccentState = 4  # acrylic blur
            accent.AccentFlags = 0x20 | 0x40 | 0x80 | 0x100
            op = max(0, min(100, int(opacity)))
            alpha = max(16, min(230, int(round(16 + op * 2.14))))
            accent.GradientColor = (alpha << 24) | 0x00101010
        else:
            # 0 = disabled. Do not use 2 (transparent gradient): Win11 draws that as glass.
            accent.AccentState = 0
            accent.AccentFlags = 0
            accent.GradientColor = 0
        data = WINCOMPATTRDATA()
        data.Attribute = 19
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)
        user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        ok = True
    except Exception as e:
        log(f"[DWM] composition: {e}", 30)

    try:
        class DWM_BLURBEHIND(ctypes.Structure):
            _fields_ = [
                ("dwFlags", ctypes.c_uint),
                ("fEnable", ctypes.c_int),
                ("hRgnBlur", ctypes.c_void_p),
                ("fTransitionOnMaximized", ctypes.c_int),
            ]

        class MARGINS(ctypes.Structure):
            _fields_ = [
                ("cxLeftWidth", ctypes.c_int),
                ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int),
                ("cyBottomHeight", ctypes.c_int),
            ]

        bb = DWM_BLURBEHIND(1, 1 if kind == "aero" else 0, None, 0)
        dwmapi.DwmEnableBlurBehindWindow(hwnd, ctypes.byref(bb))
        m = MARGINS(-1, -1, -1, -1) if kind == "aero" else MARGINS(0, 0, 0, 0)
        dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(m))
        ok = True
    except Exception as e:
        log(f"[DWM] blurbehind: {e}", 30)
    return ok


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
    """Local files and stream URLs (http/https/mms/rtmp/rtsp), including UTF-16 playlists."""
    items = []
    if not os.path.isfile(m3u_path):
        return items
    base_dir = os.path.dirname(os.path.abspath(m3u_path))
    try:
        with open(m3u_path, "rb") as f:
            raw = f.read()
    except Exception as e:
        log(f"[M3U] {m3u_path}: {e}", 30)
        return items
    text = ""
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        text = raw.decode("utf-16", errors="ignore")
    else:
        for enc in ("utf-8-sig", "utf-8", "gbk", "big5", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    schemes = ("http://", "https://", "mms://", "mmsh://", "rtmp://", "rtmps://", "rtsp://")
    for line in text.splitlines():
        line = line.strip().strip('"').strip("'")
        if not line or line.startswith("#"):
            continue
        low = line.lower()
        if low.startswith(schemes):
            items.append(line)
            continue
        full = line if os.path.isabs(line) else os.path.join(base_dir, line)
        if os.path.isfile(full):
            items.append(full)
    log(f"[M3U] {m3u_path} entries={len(items)}", 20)
    if not items:
        log(f"[M3U] no playable entries in {m3u_path}", 30)
    return items


def write_m3u(dest: str, entries: list) -> None:
    """Write a playlist. entries are local paths or stream URLs."""
    lines = ["#EXTM3U"]
    for item in entries or []:
        item = str(item or "").strip()
        if not item:
            continue
        name = item.rstrip("/\\").split("/")[-1].split("\\")[-1] or item
        lines.append(f"#EXTINF:-1,{name}")
        lines.append(item)
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


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
