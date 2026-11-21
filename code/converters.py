"""converters.py — Furnace / ASAP / ZXTune / PC-98 MML → WAV, plus ConversionThread."""
from __future__ import annotations

import os
import shutil
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


def _run(cmd, cwd=None, timeout=180) -> bool:
    try:
        r = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            cwd=cwd,
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


def _find_tool(names):
    folders = (
        "",
        "mml",
        os.path.join("mml", "compiler"),
        os.path.join("mml", "player"),
        os.path.join("mml", "NET6"),
        os.path.join("bin1", "NET6"),
        os.path.join("bin1", "NetCoreApp31"),
        os.path.join("bin2", "mml2vgmx64"),
        os.path.join("bin2", "mml2vgmIDEx64"),
        "compiler",
        "player",
        "NET6",
        "mml2vgm",
        "mml2vgmx64",
    )
    for name in names:
        for folder in folders:
            rel = os.path.join(folder, name) if folder else name
            p = resource_path(rel)
            if os.path.isfile(p):
                return p
    return None


def _snapshot(folder, exts):
    found = {}
    try:
        names = os.listdir(folder)
    except OSError:
        return found
    for name in names:
        if os.path.splitext(name)[1].lower() not in exts:
            continue
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            found[os.path.normcase(os.path.abspath(path))] = path
    return found


def _fresh(folder, exts, before):
    now = _snapshot(folder, exts)
    return [path for key, path in now.items() if key not in before]


def _take_wav(src):
    tmp = _temp_wav()
    try:
        os.remove(tmp)
    except Exception:
        pass
    shutil.move(src, tmp)
    if os.path.isfile(tmp) and os.path.getsize(tmp) > 128:
        return tmp
    return None


class PmdConverter(BaseConverter):
    """PC-98 / PC-88 MML. PMD .mml/.M/.M2, or MUCOM .mml/.mub, rendered to WAV."""

    name = "pmd"

    @classmethod
    def _pmd_compiler(cls):
        return _find_tool(("PMDDotNETConsole.exe",))

    @classmethod
    def _pmd_player(cls):
        return _find_tool(("PMDDotNETPlayer.exe",))

    @classmethod
    def _mucom_compiler(cls):
        return _find_tool(("mucomDotNETConsole.exe",))

    @classmethod
    def _mucom_wav(cls):
        return _find_tool(("mucomDotNET2wav.exe",))

    @classmethod
    def _mvc(cls):
        return _find_tool(("mvcx64.exe", "mvc.exe", "mml2vgmx64.exe", "mml2vgm.exe"))

    @classmethod
    def _mdx_compiler(cls):
        return _find_tool(("mml2mdx.exe",))

    @classmethod
    def available(cls) -> bool:
        if cls._pmd_compiler() and cls._pmd_player():
            return True
        if cls._mucom_wav() and cls._mucom_compiler():
            return True
        if cls._mvc() and ZxtuneConverter.available():
            return True
        if cls._mdx_compiler() and ZxtuneConverter.available():
            return True
        return False

    @classmethod
    def convert(cls, filepath: str) -> str | None:
        ext = os.path.splitext(filepath)[1].lower()
        folder = os.path.dirname(os.path.abspath(filepath)) or "."
        if ext in (".m", ".m2", ".mz"):
            return cls._pmd_wave(filepath, folder)
        if ext == ".mub":
            return cls._mucom_wave(filepath, folder)
        if ext == ".gwi":
            return cls._mml2vgm(filepath, folder)
        if ext == ".muc":
            compiled = cls._mucom_compile(filepath, folder)
            if compiled:
                return cls._mucom_wave(compiled, os.path.dirname(compiled) or folder)
            return None
        if ext != ".mml":
            return None
        order = _dialect_order(filepath)
        log(f"[MML] dialects {' '.join(order)}", 20)
        junk = {".m", ".m2", ".mz", ".mub", ".vgm", ".vgz", ".mdx", ".wav", ".xgm", ".zgm"}
        for i, name in enumerate(order):
            before = _snapshot(folder, junk)
            timeout = 600 if i == 0 else 180
            wav = cls._try_dialect(name, filepath, folder, timeout)
            if wav:
                log(f"[MML] played as {name}", 20)
                return wav
            for extra in _fresh(folder, junk, before):
                try:
                    os.remove(extra)
                except Exception:
                    pass
        log("[MML] no dialect produced wav", 40)
        return None

    @classmethod
    def _try_dialect(cls, name, filepath, folder, timeout):
        if name == "pmd" and cls._pmd_compiler() and cls._pmd_player():
            compiled = cls._pmd_compile(filepath, folder)
            if compiled and os.path.getsize(compiled) > 32:
                return cls._pmd_wave(compiled, os.path.dirname(compiled) or folder, timeout)
        elif name == "mucom" and cls._mucom_compiler() and cls._mucom_wav():
            compiled = cls._mucom_compile(filepath, folder)
            if compiled and os.path.getsize(compiled) > 32:
                return cls._mucom_wave(compiled, os.path.dirname(compiled) or folder, timeout)
        elif name == "mml2vgm" and cls._mvc() and ZxtuneConverter.available():
            return cls._mml2vgm(filepath, folder)
        elif name == "mdx" and cls._mdx_compiler() and ZxtuneConverter.available():
            return cls._mdx(filepath, folder)
        return None

    @classmethod
    def _pmd_compile(cls, filepath, folder):
        exe = cls._pmd_compiler()
        if not exe:
            log("[MML] PMDDotNETConsole.exe missing", 40)
            return None
        before = _snapshot(folder, {".m", ".m2", ".mz"})
        _run([exe, filepath], cwd=folder, timeout=120)
        made = _fresh(folder, {".m", ".m2", ".mz"}, before)
        if not made:
            for ext in (".M", ".m", ".M2", ".m2", ".MZ", ".mz"):
                guess = os.path.splitext(filepath)[0] + ext
                if os.path.isfile(guess):
                    made = [guess]
                    break
        if not made:
            log("[MML] PMD compile wrote no .M", 40)
            return None
        made.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        log(f"[MML] compiled {made[0]}", 20)
        return made[0]

    @classmethod
    def _pmd_wave(cls, compiled, folder, timeout=600):
        exe = cls._pmd_player()
        if not exe:
            log("[MML] PMDDotNETPlayer.exe missing", 40)
            return None
        ext = os.path.splitext(compiled)[1].lower()
        play_path = compiled
        temp_copy = None
        # The player only reliably opens .M. .m2 is the PC-98-86 (OPNA) compile, .mz is Towns.
        if ext in (".m2", ".mz"):
            try:
                fd, temp_copy = tempfile.mkstemp(prefix=".__pmd_", suffix=".m", dir=folder)
                os.close(fd)
                shutil.copyfile(compiled, temp_copy)
                play_path = temp_copy
            except Exception as e:
                log(f"[MML] copy {ext} to .m failed: {e}", 40)
                temp_copy = None
                play_path = compiled
        board = "-B=86" if ext in (".m2", ".mz") else "-B=AUTO"
        watch = [folder, os.path.dirname(exe)]
        before = {}
        for directory in watch:
            before.update(_snapshot(directory, {".wav"}))
        cmd = [exe, "-D=WAVE", "-L=2", board, play_path]
        log(f"[MML] {' '.join(os.path.basename(a) if i == 0 else a for i, a in enumerate(cmd))}", 20)
        _run(cmd, cwd=folder, timeout=timeout)
        made = []
        for directory in watch:
            made.extend(_fresh(directory, {".wav"}, before))
        for guess in (
            os.path.splitext(play_path)[0] + ".wav",
            os.path.splitext(compiled)[0] + ".wav",
        ):
            if os.path.isfile(guess) and guess not in made:
                made.append(guess)
        wav = None
        try:
            if made:
                made.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                wav = _take_wav(made[0])
                if wav:
                    log(f"[MML] PMD wav {compiled}", 20)
            else:
                log(f"[MML] PMD wrote no wav for {ext}. PCM files must sit next to the song.", 40)
        finally:
            if temp_copy and os.path.isfile(temp_copy):
                try:
                    os.remove(temp_copy)
                except Exception:
                    pass
        return wav

    @classmethod
    def _mucom_compile(cls, filepath, folder):
        exe = cls._mucom_compiler()
        if not exe:
            return None
        before = _snapshot(folder, {".mub"})
        if not _run([exe, filepath], cwd=folder, timeout=120):
            log("[MML] mucom compile failed", 30)
            return None
        made = _fresh(folder, {".mub"}, before)
        if not made:
            guess = os.path.splitext(filepath)[0] + ".mub"
            if os.path.isfile(guess):
                return guess
            log("[MML] mucom compile wrote no .mub", 30)
            return None
        made.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return made[0]

    @classmethod
    def _mucom_wave(cls, compiled, folder, timeout=600):
        exe = cls._mucom_wav()
        if not exe:
            log("[MML] mucomDotNET2wav.exe missing", 40)
            return None
        before = _snapshot(folder, {".wav"})
        _run([exe, "-L=2", compiled], cwd=folder, timeout=timeout)
        made = _fresh(folder, {".wav"}, before)
        if not made:
            log("[MML] mucom wrote no wav", 40)
            return None
        made.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        wav = _take_wav(made[0])
        if wav:
            log(f"[MML] mucom wav {compiled}", 20)
        return wav


def _mml_text(path):
    try:
        raw = open(path, "rb").read(80000)
    except OSError:
        return ""
    for enc in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("latin-1", "replace")


def _dialect_order(path):
    """Score the text, then still try every dialect afterwards."""
    text = _mml_text(path).lower()
    scored = {}

    def bump(name, n):
        scored[name] = scored.get(name, 0) + n

    if "#driver" in text and "mucom" in text:
        bump("mucom", 80)
    if "#voice" in text or ("#pcm" in text and "#pcmfile" not in text):
        bump("mucom", 40)
    if any(s in text for s in (
        "#ppcfile", "#ppsfile", "#p86file", "#fffile", "#option", "#detune", "#filename",
    )):
        bump("pmd", 70)
    if text.startswith("%") or "\n%" in text:
        bump("pmd", 25)
    if any(s in text for s in ("#pcmfile", "#octave-rev", "#ex-pcm")):
        bump("mdx", 60)
    if any(s in text for s in (
        "ym2608", "ym2612", "ym2203", "ym2151", "sn76489", "huc6280", "#clock",
    )):
        bump("mml2vgm", 55)
    order = [name for name, _score in sorted(scored.items(), key=lambda kv: -kv[1])]
    for name in ("pmd", "mucom", "mml2vgm", "mdx"):
        if name not in order:
            order.append(name)
    return order


class _MmlMore(PmdConverter):
    @classmethod
    def _mml2vgm(cls, filepath, folder):
        exe = cls._mvc()
        if not exe:
            return None
        dest = os.path.join(folder, os.path.splitext(os.path.basename(filepath))[0] + ".__dem.vgm")
        before = _snapshot(folder, {".vgm", ".vgz", ".wav"})
        _run([exe, "-v+", filepath, dest], cwd=folder, timeout=120)
        made = _fresh(folder, {".vgm", ".vgz", ".wav"}, before)
        if os.path.isfile(dest) and dest not in made:
            made.append(dest)
        made.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        for src in made:
            low = src.lower()
            if low.endswith(".wav") and os.path.getsize(src) > 128:
                log(f"[MML] mml2vgm wav {src}", 20)
                return _take_wav(src)
            if low.endswith((".vgm", ".vgz")) and os.path.getsize(src) > 32:
                wav = ZxtuneConverter.convert(src)
                if wav:
                    log(f"[MML] mml2vgm via vgm {src}", 20)
                    return wav
        log("[MML] mml2vgm wrote no vgm", 30)
        return None

    @classmethod
    def _mdx(cls, filepath, folder):
        exe = cls._mdx_compiler()
        if not exe:
            return None
        before = _snapshot(folder, {".mdx", ".wav"})
        _run([exe, filepath], cwd=folder, timeout=120)
        made = _fresh(folder, {".mdx", ".wav"}, before)
        guess = os.path.splitext(filepath)[0] + ".mdx"
        if os.path.isfile(guess) and guess not in made:
            made.append(guess)
        for src in made:
            if src.lower().endswith(".wav") and os.path.getsize(src) > 128:
                return _take_wav(src)
            if src.lower().endswith(".mdx") and os.path.getsize(src) > 32:
                wav = ZxtuneConverter.convert(src)
                if wav:
                    log(f"[MML] mdx via zxtune {src}", 20)
                    return wav
        log("[MML] mml2mdx wrote nothing playable", 30)
        return None


PmdConverter._mml2vgm = _MmlMore._mml2vgm
PmdConverter._mdx = _MmlMore._mdx
PmdConverter._mvc = _MmlMore._mvc
PmdConverter._mdx_compiler = _MmlMore._mdx_compiler


ENGINE_MAP = {
    "chiptune_cli": FurnaceConverter,
    "furnace": FurnaceConverter,
    "asap": AsapConverter,
    "zxtune": ZxtuneConverter,
    "pmd": PmdConverter,
}


class FfmpegDecodeThread(QThread):
    """Local M4A/AAC/WMA/… → WAV off the UI thread. Interruption kills ffmpeg."""
    decoded = Signal(str)

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath

    def run(self):
        from audio import _ffmpeg_decode_to_wav
        wav = ""
        if not (hasattr(self, "isInterruptionRequested") and self.isInterruptionRequested()):
            wav = _ffmpeg_decode_to_wav(self.filepath, cancel=self.isInterruptionRequested) or ""
        if not (hasattr(self, "isInterruptionRequested") and self.isInterruptionRequested()):
            self.decoded.emit(wav)


class DurationScanThread(QThread):
    """F10: read durations off the UI thread. One signal per file."""
    progress = Signal(int, int, str, int)
    done = Signal(int, int)

    def __init__(self, paths):
        super().__init__()
        self.paths = list(paths)

    def run(self):
        from core import probe_file_duration_ms
        ok = 0
        total = len(self.paths)
        for i, path in enumerate(self.paths, 1):
            if hasattr(self, "isInterruptionRequested") and self.isInterruptionRequested():
                self.done.emit(ok, total)
                return
            ms = 0
            try:
                ms = int(probe_file_duration_ms(path) or 0)
            except Exception:
                ms = 0
            if ms > 0:
                ok += 1
            self.progress.emit(i, total, path, ms)
        self.done.emit(ok, total)


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
