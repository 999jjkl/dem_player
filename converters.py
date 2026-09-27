"""converters.py — Furnace / ASAP / ZXTune → WAV, plus ConversionThread."""
from __future__ import annotations

import os
import subprocess
import tempfile

from core import log, resource_path, subprocess_hidden_kwargs

try:
    from PySide6.QtCore import QThread, Signal
except ImportError:
    QThread = object  # type: ignore
    class Signal:  # type: ignore
        def __init__(self, *a):
            pass
        def emit(self, *a):
            pass
        def connect(self, *a):
            pass


def _run(cmd) -> bool:
    try:
        r = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
            **subprocess_hidden_kwargs(),
        )
        if r.returncode != 0:
            err = ((r.stderr or b"") + (r.stdout or b""))[-400:].decode("utf-8", "replace")
            log(f"[conv] rc={r.returncode} {os.path.basename(cmd[0])} {cmd[1:]} {err}", 30)
            return False
        return True
    except Exception as e:
        log(f"[conv] {cmd[0] if cmd else '?'}: {e}", 40)
        return False


def _temp_wav():
    fd, tmp = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    return tmp


def _temp_wav_path():
    """Path that does not exist yet (some CLIs refuse to overwrite)."""
    tmp = _temp_wav()
    try:
        os.remove(tmp)
    except Exception:
        pass
    return tmp


def _file_uri(path: str) -> str:
    p = os.path.abspath(path).replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        return "file:///" + p
    return "file://" + p


class BaseConverter:
    name = "base"

    @classmethod
    def available(cls) -> bool:
        return False

    @classmethod
    def convert(cls, filepath: str) -> str | None:
        raise NotImplementedError


class FurnaceConverter(BaseConverter):
    name = "furnace"

    @classmethod
    def _exe(cls):
        p = resource_path("furnace.exe")
        if os.path.isfile(p):
            return p
        p = resource_path("furnace")
        if os.path.isfile(p):
            return p
        return None

    @classmethod
    def available(cls) -> bool:
        return cls._exe() is not None

    @classmethod
    def convert(cls, filepath: str) -> str | None:
        exe = cls._exe()
        if not exe:
            log("[Furnace] exe missing", 40)
            return None
        tmp = _temp_wav()
        cmd = [exe, "-noreport", "-output", tmp, filepath]
        if _run(cmd) and os.path.isfile(tmp) and os.path.getsize(tmp) > 128:
            log(f"[Furnace] ok: {filepath}", 20)
            return tmp
        try:
            os.remove(tmp)
        except Exception:
            pass
        log("[Furnace] conversion failed", 40)
        return None


class AsapConverter(BaseConverter):
    name = "asap"

    @classmethod
    def _exe(cls):
        p = resource_path("asapconv.exe")
        if os.path.isfile(p):
            return p
        p = resource_path("asapconv")
        if os.path.isfile(p):
            return p
        return None

    @classmethod
    def available(cls) -> bool:
        return cls._exe() is not None

    @classmethod
    def convert(cls, filepath: str) -> str | None:
        exe = cls._exe()
        if not exe:
            log("[ASAP] exe missing", 40)
            return None
        tmp = _temp_wav()
        if _run([exe, "-o", tmp, filepath]) and os.path.isfile(tmp) and os.path.getsize(tmp) > 128:
            return tmp
        try:
            os.remove(tmp)
        except Exception:
            pass
        log("[ASAP] conversion failed", 40)
        return None


class ZxtuneConverter(BaseConverter):
    name = "zxtune"

    @classmethod
    def _exe(cls):
        for name in ("zxtune-cli.exe", "zxtune123.exe", "zxtune-cli", "zxtune123"):
            p = resource_path(name)
            if os.path.isfile(p):
                return p
        return None

    @classmethod
    def available(cls) -> bool:
        return cls._exe() is not None

    @classmethod
    def convert(cls, filepath: str) -> str | None:
        exe = cls._exe()
        if not exe:
            log("[ZXTune] exe missing", 40)
            return None
        tmp = _temp_wav_path()
        tmp_fwd = tmp.replace("\\", "/")
        uri = _file_uri(filepath)
        cmds = [
            # convert-only: --null disables live audio so it won't hang on SID loops
            [exe, "--null", "--wav", f"filename={tmp}", "--loop-limit=1", filepath],
            [exe, "--null", "--wav", f"filename={tmp}", "--loop-count=1", filepath],
            [exe, "--null", "--wav", f"filename={tmp_fwd}", filepath],
            [exe, "--null", "--wav", f"filename={tmp}", "--", filepath],
            [exe, "--null", "--wav", f"filename={tmp}", uri],
            [exe, "--wav", f"filename={tmp}", "--null", filepath],
            [exe, "--wav", f"filename={tmp}", filepath],
            [exe, "--mode=wav", f"--file={tmp}", filepath],
            [exe, "-o", tmp, filepath],
        ]
        for cmd in cmds:
            try:
                if os.path.isfile(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            if _run(cmd) and os.path.isfile(tmp) and os.path.getsize(tmp) > 128:
                log(f"[ZXTune] ok args={cmd[1:]}", 20)
                return tmp
            # some builds write next to the source as <name>.wav
            sibling = os.path.splitext(filepath)[0] + ".wav"
            if os.path.isfile(sibling) and os.path.getsize(sibling) > 128:
                log("[ZXTune] used sibling wav", 20)
                return sibling
        try:
            if os.path.isfile(tmp):
                os.remove(tmp)
        except Exception:
            pass
        log("[ZXTune] conversion failed", 40)
        return None


ENGINE_MAP = {
    "chiptune_cli": FurnaceConverter,
    "furnace": FurnaceConverter,
    "asap": AsapConverter,
    "zxtune": ZxtuneConverter,
}


class ConversionThread(QThread):
    finished = Signal(str)

    def __init__(self, engine_type, filepath):
        super().__init__()
        self.engine_type = engine_type
        self.filepath = filepath

    def run(self):
        if hasattr(self, "isInterruptionRequested") and self.isInterruptionRequested():
            return
        cls = ENGINE_MAP.get(self.engine_type)
        result = cls.convert(self.filepath) if cls else None
        if not (hasattr(self, "isInterruptionRequested") and self.isInterruptionRequested()):
            self.finished.emit(result or "")
