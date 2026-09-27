"""audio.py — playback backends (miniaudio / FFmpeg / libopenmpt / FluidSynth)."""
from __future__ import annotations

import array
import os
import struct
import subprocess
import sys
import tempfile
import threading
import wave
import ctypes
from abc import ABC, abstractmethod

from core import app_dir, log, resource_path, resource_candidates, subprocess_hidden_kwargs

SAMPLE_RATE = 44100
CHANNELS = 2

try:
    import miniaudio
    HAS_MINIAUDIO = True
except ImportError:
    miniaudio = None
    HAS_MINIAUDIO = False


# ---------- native search path (Windows DLL resolve) ----------
_DLL_PATHS_READY = False


def _prepare_native_search_path() -> str:
    """Put the app folder on the Windows DLL search path (libopenmpt / fluidsynth)."""
    global _DLL_PATHS_READY
    base = app_dir()
    if _DLL_PATHS_READY:
        return base
    extra = [base]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        extra.append(meipass)
    if sys.platform == "win32":
        add = getattr(os, "add_dll_directory", None)
        for d in extra:
            if add:
                try:
                    add(d)
                except Exception:
                    pass
            try:
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            except Exception:
                pass
    _DLL_PATHS_READY = True
    return base


def _first_existing(names) -> str | None:
    for name in names:
        for p in resource_candidates(name):
            if os.path.isfile(p):
                return p
        if os.path.isfile(name):
            return os.path.abspath(name)
    return None


def _ffmpeg_bin() -> str:
    p = _first_existing(("ffmpeg.exe", "ffmpeg"))
    return p or "ffmpeg"


def _fluidsynth_bin() -> str | None:
    return _first_existing(("fluidsynth.exe", "fluidsynth"))


def _openmpt123_bin() -> str | None:
    return _first_existing(("openmpt123.exe", "openmpt123"))


def _soundfont_path() -> str | None:
    return _first_existing((
        "soundfont.sf2",
        "FluidR3_GM.sf2",
        "weedsgm3.sf2",
        "GeneralUser GS.sf2",
        "GeneralUserGS.sf2",
        os.path.join("SoundFonts", "soundfont.sf2"),
        os.path.join("SoundFonts", "GeneralUser GS.sf2"),
    ))


def _openmpt_lib():
    _prepare_native_search_path()
    names = [
        resource_path("libopenmpt.dll"),
        resource_path("openmpt.dll"),
        resource_path("libopenmpt.so.0"),
        resource_path("libopenmpt.so"),
        resource_path("libopenmpt.dylib"),
        "libopenmpt.dll",
        "openmpt.dll",
        "libopenmpt.so.0",
        "libopenmpt.so",
        "libopenmpt.dylib",
    ]
    for n in names:
        try:
            if os.path.sep in n or n.lower().endswith(".dll"):
                if os.path.isabs(n) or os.path.sep in n:
                    if not os.path.isfile(n):
                        continue
            return ctypes.CDLL(n)
        except OSError:
            continue
    return None


def _preload_fluidsynth_dll() -> str | None:
    _prepare_native_search_path()
    names = (
        "libfluidsynth-3.dll",
        "libfluidsynth.dll",
        "fluidsynth.dll",
        "libfluidsynth-3.so",
        "libfluidsynth.so.3",
        "libfluidsynth.so",
        "libfluidsynth.dylib",
    )
    for n in names:
        p = resource_path(n)
        if not os.path.isfile(p):
            continue
        try:
            ctypes.CDLL(p)
            return p
        except OSError as e:
            log(f"[fluidsynth] preload {p} failed: {e}", 30)
    return None


def probe_ffmpeg() -> str:
    p = _ffmpeg_bin()
    if os.path.isfile(p):
        return p
    return "ffmpeg (PATH)" if shutil_which(p) else ""


def shutil_which(cmd: str) -> str | None:
    from shutil import which
    return which(cmd)


def probe_openmpt() -> str:
    lib = _openmpt_lib()
    if lib is not None:
        return getattr(lib, "_name", "") or "libopenmpt"
    p = _openmpt123_bin()
    return p or ""


def probe_fluidsynth() -> str:
    p = _fluidsynth_bin()
    if p:
        return p
    dll = _preload_fluidsynth_dll()
    if dll:
        return dll
    try:
        import fluidsynth  # noqa: F401
        return "pyfluidsynth"
    except Exception:
        return ""


def probe_soundfont() -> str:
    return _soundfont_path() or ""


def list_output_devices():
    """Return [(id_str, name), ...]. id_str is the device name (stable enough to persist)."""
    results = []
    if not HAS_MINIAUDIO:
        return results
    try:
        devices = miniaudio.Devices()
        for i, d in enumerate(devices.get_playbacks()):
            name = getattr(d, "name", None) or f"Device {i}"
            results.append((name, name))
    except Exception as e:
        log(f"[Audio] device list failed: {e}", 30)
    return results


def _find_device_id(name: str):
    if not name or not HAS_MINIAUDIO:
        return None
    try:
        devices = miniaudio.Devices()
        for d in devices.get_playbacks():
            if getattr(d, "name", "") == name:
                return d.id
    except Exception:
        pass
    return None


def _write_wav_s16(path: str, pcm: bytes, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS) -> bool:
    try:
        with wave.open(path, "wb") as w:
            w.setnchannels(channels)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(pcm)
        return os.path.isfile(path) and os.path.getsize(path) > 128
    except Exception as e:
        log(f"[wav] write failed: {e}", 40)
        return False


def _cleanup_file(path: str | None) -> None:
    if not path:
        return
    try:
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass


def _ffmpeg_decode_to_wav(filepath: str) -> str | None:
    try:
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        cmd = [
            _ffmpeg_bin(), "-y", "-nostdin", "-i", filepath,
            "-f", "wav", "-acodec", "pcm_s16le",
            "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS), tmp,
        ]
        r = subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            **subprocess_hidden_kwargs(),
        )
        if r.returncode != 0 or not os.path.isfile(tmp) or os.path.getsize(tmp) < 128:
            err = (r.stderr or b"")[-400:].decode("utf-8", "ignore")
            log(f"[ffmpeg] decode failed rc={r.returncode} {err}", 30)
            try:
                os.remove(tmp)
            except Exception:
                pass
            return None
        return tmp
    except Exception as e:
        log(f"[ffmpeg] {e}", 40)
        return None


# ---------- MIDI / RMI ----------
def extract_smf_bytes(filepath: str) -> bytes | None:
    """Return Standard MIDI File bytes. Handles .mid and RIFF-wrapped .rmi."""
    try:
        with open(filepath, "rb") as f:
            data = f.read()
    except Exception as e:
        log(f"[midi] read failed: {e}", 40)
        return None
    if not data:
        return None
    if data.startswith(b"MThd"):
        return data
    idx = data.find(b"MThd")
    if idx >= 0:
        return data[idx:]
    log("[midi] no MThd chunk (not a MIDI/RMI SMF)", 40)
    return None


def _read_vlq(data: bytes, i: int):
    value = 0
    n = len(data)
    while i < n:
        b = data[i]
        i += 1
        value = (value << 7) | (b & 0x7F)
        if not (b & 0x80):
            break
    return value, i


def parse_smf(data: bytes):
    """Return (ticks_per_beat, events) where events are (tick, status, a, b, extra).

    extra is used for tempo (us per quarter) when status == 0xFF and a == 0x51.
    """
    if not data or not data.startswith(b"MThd"):
        return 480, [], False
    if len(data) < 14:
        return 480, [], False
    hdr_len = struct.unpack(">I", data[4:8])[0]
    _fmt, ntrks, division = struct.unpack(">HHH", data[8:14])
    if division & 0x8000:
        # SMPTE — treat fps*tpf as ticks/sec, fake 1_000_000 us "beat" of 1 second
        fps = 128 - ((division >> 8) & 0x7F)
        tpf = division & 0xFF
        tpq = max(1, fps * tpf)
        smpte = True
    else:
        tpq = max(1, division)
        smpte = False
    i = 8 + hdr_len
    events = []
    n = len(data)
    tracks_parsed = 0
    while i + 8 <= n and tracks_parsed < ntrks:
        if data[i:i + 4] != b"MTrk":
            i += 1
            continue
        tlen = struct.unpack(">I", data[i + 4:i + 8])[0]
        i += 8
        end = min(n, i + tlen)
        tick = 0
        running = 0
        while i < end:
            delta, i = _read_vlq(data, i)
            tick += delta
            if i >= end:
                break
            b = data[i]
            if b >= 0x80:
                status = b
                i += 1
                if b < 0xF0:
                    running = status
            else:
                status = running
                if status < 0x80:
                    i += 1
                    continue
            stype = status & 0xF0
            if status == 0xFF:
                if i >= end:
                    break
                meta = data[i]
                i += 1
                mlen, i = _read_vlq(data, i)
                payload = data[i:i + mlen]
                i += mlen
                if meta == 0x2F:
                    break
                if meta == 0x51 and len(payload) >= 3:
                    us = (payload[0] << 16) | (payload[1] << 8) | payload[2]
                    events.append((tick, 0xFF, 0x51, us, None))
            elif status in (0xF0, 0xF7):
                slen, i = _read_vlq(data, i)
                i += slen
            elif stype in (0xC0, 0xD0):
                a = data[i] if i < end else 0
                i += 1
                events.append((tick, status, a, 0, None))
            else:
                a = data[i] if i < end else 0
                b2 = data[i + 1] if i + 1 < end else 0
                i += 2
                events.append((tick, status, a, b2, None))
        tracks_parsed += 1
        i = end
    events.sort(key=lambda e: e[0])
    return tpq, events, smpte


def _samples_to_s16le(raw) -> bytes:
    """Convert pyfluidsynth get_samples() output to interleaved s16le bytes."""
    if raw is None:
        return b""
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    if isinstance(raw, array.array):
        if raw.typecode == "h":
            return raw.tobytes()
        samples = array.array("h")
        for v in raw:
            iv = int(v)
            if iv > 32767:
                iv = 32767
            elif iv < -32768:
                iv = -32768
            samples.append(iv)
        return samples.tobytes()
    try:
        import numpy as np
        arr = np.asarray(raw)
        if arr.dtype.kind == "f":
            arr = (arr.astype(np.float32).reshape(-1) * 32767.0).clip(-32768, 32767)
            return arr.astype("<i2").tobytes()
        if arr.dtype.kind in "iu":
            return arr.astype("<i2", copy=False).reshape(-1).tobytes()
    except Exception:
        pass
    samples = array.array("h")
    for v in raw:
        try:
            fv = float(v)
        except Exception:
            continue
        if -1.5 <= fv <= 1.5:
            iv = int(fv * 32767)
        else:
            iv = int(fv)
        if iv > 32767:
            iv = 32767
        elif iv < -32768:
            iv = -32768
        samples.append(iv)
    return samples.tobytes()


def render_midi_pyfluidsynth(smf_bytes: bytes, sf2: str) -> bytes | None:
    """Render SMF to interleaved s16le stereo PCM via pyfluidsynth (no audio driver)."""
    _preload_fluidsynth_dll()
    try:
        import fluidsynth
    except Exception as e:
        log(f"[fluidsynth] pyfluidsynth import: {e}", 30)
        return None
    parsed = parse_smf(smf_bytes)
    if len(parsed) == 3:
        tpq, events, smpte = parsed
    else:
        tpq, events = parsed
        smpte = False
    if not events:
        log("[fluidsynth] MIDI has no events", 40)
        return None

    try:
        fs = fluidsynth.Synth(samplerate=float(SAMPLE_RATE), gain=0.4)
    except Exception as e:
        log(f"[fluidsynth] Synth(): {e}", 40)
        return None
    try:
        sfid = fs.sfload(sf2)
        if sfid is None or sfid < 0:
            log("[fluidsynth] sfload failed", 40)
            return None
        for ch in range(16):
            try:
                fs.program_select(ch, sfid, 0, 0)
            except Exception:
                try:
                    fs.sfont_select(ch, sfid)
                    fs.program_change(ch, 0)
                except Exception:
                    pass

        us_per_qn = 500000
        chunks = []
        last_tick = 0
        sr = SAMPLE_RATE

        def ticks_to_frames(dticks: int, tempo: int) -> int:
            if dticks <= 0:
                return 0
            if smpte:
                return int(dticks * sr / max(1, tpq))
            return int(dticks * (tempo / 1_000_000.0) * sr / tpq)

        def pull(nframes: int):
            if nframes <= 0:
                return
            remain = nframes
            while remain > 0:
                n = min(remain, 2048)
                raw = fs.get_samples(n)
                if raw is None:
                    break
                chunks.append(_samples_to_s16le(raw))
                remain -= n

        for tick, status, a, b, _extra in events:
            dt = tick - last_tick
            if dt > 0:
                pull(ticks_to_frames(dt, us_per_qn))
                last_tick = tick
            stype = status & 0xF0
            chan = status & 0x0F
            try:
                if status == 0xFF and a == 0x51:
                    us_per_qn = max(1, int(b))
                elif stype == 0x90:
                    if b <= 0:
                        fs.noteoff(chan, a)
                    else:
                        fs.noteon(chan, a, b)
                elif stype == 0x80:
                    fs.noteoff(chan, a)
                elif stype == 0xB0:
                    fs.cc(chan, a, b)
                elif stype == 0xC0:
                    fs.program_change(chan, a)
                elif stype == 0xD0:
                    if hasattr(fs, "channel_pressure"):
                        fs.channel_pressure(chan, a)
                elif stype == 0xE0:
                    val = (b << 7) | a
                    fs.pitch_bend(chan, val)
                elif stype == 0xA0:
                    if hasattr(fs, "key_pressure"):
                        fs.key_pressure(chan, a, b)
            except Exception:
                pass

        pull(int(sr * 1.5))  # release tail
        pcm = b"".join(chunks)
        if len(pcm) < 256:
            log("[fluidsynth] render produced no audio", 40)
            return None
        return pcm
    except Exception as e:
        log(f"[fluidsynth] render: {e}", 40)
        return None
    finally:
        try:
            fs.delete()
        except Exception:
            pass


# ---------- abstract ----------
class AudioBackend(ABC):
    @abstractmethod
    def play(self, filepath: str, start_ms: int = 0) -> bool: ...
    @abstractmethod
    def stop(self) -> None: ...
    @abstractmethod
    def pause(self) -> None: ...
    @abstractmethod
    def resume(self) -> None: ...
    @abstractmethod
    def is_playing(self) -> bool: ...
    @abstractmethod
    def set_volume(self, vol_percent: int) -> None: ...
    @abstractmethod
    def get_time(self): ...
    @abstractmethod
    def get_position(self) -> float: ...
    @abstractmethod
    def set_position(self, ratio: float) -> None: ...
    @abstractmethod
    def get_level(self): ...
    @abstractmethod
    def free(self) -> None: ...


# ---------- miniaudio PCM pump ----------
class MiniaudioBackend(AudioBackend):
    """Direct decode+play for WAV/MP3/FLAC/OGG (and anything miniaudio can open)."""

    def __init__(self, device_name: str = "", on_end=None):
        self.device_name = device_name
        self.on_end = on_end
        self._device = None
        self._lock = threading.Lock()
        self._paused = False
        self._stopped = True
        self._ended = False
        self._volume = 0.5
        self._frames_played = 0
        self._total_frames = 0
        self._sample_rate = SAMPLE_RATE
        self._filepath = ""
        self._start_ms = 0
        self._last_amp = 0.0
        self._pcm_chunk = None
        self._end_sent = False
        self.last_error = ""

    def play(self, filepath, start_ms=0):
        if not HAS_MINIAUDIO:
            self.last_error = "miniaudio not installed (pip install miniaudio)"
            log("[miniaudio] not installed", 40)
            return False
        self._stop_device()
        if not os.path.isfile(filepath):
            self.last_error = f"missing file: {filepath}"
            log(f"[miniaudio] missing {filepath}", 30)
            return False
        try:
            info = miniaudio.get_file_info(filepath)
        except Exception as e:
            self.last_error = f"cannot open: {e}"
            log(f"[miniaudio] cannot open {filepath}: {e}", 30)
            return False

        self._filepath = filepath
        self._start_ms = start_ms or 0
        self._sample_rate = int(info.sample_rate or SAMPLE_RATE)
        self._total_frames = int(getattr(info, "nframes", 0) or getattr(info, "num_frames", 0) or 0)
        if self._total_frames <= 0 and getattr(info, "duration", 0):
            self._total_frames = int(info.duration * self._sample_rate)
        seek_frame = int(self._sample_rate * self._start_ms / 1000.0) if self._start_ms else 0
        self._frames_played = seek_frame
        self._stopped = False
        self._paused = False
        self._ended = False
        self._end_sent = False

        try:
            stream = miniaudio.stream_file(
                filepath,
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=CHANNELS,
                sample_rate=self._sample_rate,
                seek_frame=seek_frame,
            )
            # stream_file() returns a generator. send(non-None) is illegal until next().
            next(stream)
        except StopIteration:
            self.last_error = "empty stream"
            log("[miniaudio] empty stream", 30)
            return False
        except Exception as e:
            self.last_error = f"stream failed: {e}"
            log(f"[miniaudio] stream_file failed: {e}", 30)
            return False

        wrapped = self._wrap_stream(stream)
        try:
            next(wrapped)
        except StopIteration:
            self.last_error = "empty stream"
            return False

        device_id = _find_device_id(self.device_name)
        try:
            self._device = miniaudio.PlaybackDevice(
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=CHANNELS,
                sample_rate=self._sample_rate,
                device_id=device_id,
            )
            self._device.start(wrapped)
        except Exception as e:
            self.last_error = f"device: {e}"
            log(f"[miniaudio] PlaybackDevice failed: {e}", 40)
            self._device = None
            return False
        self.last_error = ""
        log(f"[miniaudio] playing {filepath} start_ms={start_ms}", 20)
        return True

    def _wrap_stream(self, stream):
        paused_silence = array.array("h", [0] * (1024 * CHANNELS))

        def gen():
            num_frames = yield b""
            try:
                while True:
                    with self._lock:
                        if self._stopped:
                            return
                        paused = self._paused
                        vol = self._volume
                    if paused:
                        num_frames = yield paused_silence
                        continue
                    try:
                        if num_frames:
                            chunk = stream.send(num_frames)
                        else:
                            chunk = next(stream)
                    except StopIteration:
                        self._ended = True
                        self._fire_end()
                        return
                    except Exception as e:
                        log(f"[miniaudio] stream error: {e}", 40)
                        self.last_error = str(e)
                        self._ended = True
                        self._fire_end()
                        return
                    if not chunk:
                        self._ended = True
                        self._fire_end()
                        return
                    samples = chunk if isinstance(chunk, array.array) else array.array("h", chunk)
                    if vol < 0.999:
                        scaled = array.array("h")
                        amp = int(vol * 256)
                        for s in samples:
                            v = (s * amp) >> 8
                            if v > 32767:
                                v = 32767
                            elif v < -32768:
                                v = -32768
                            scaled.append(v)
                        samples = scaled
                    n = len(samples)
                    if n:
                        step = max(1, n // 64)
                        peak = 0
                        for i in range(0, n, step):
                            a = abs(samples[i])
                            if a > peak:
                                peak = a
                        self._last_amp = min(1.0, peak / 32768.0)
                        self._pcm_chunk = samples
                        self._frames_played += n // CHANNELS
                    num_frames = yield samples
            except GeneratorExit:
                return

        return gen()

    def _fire_end(self):
        if self._end_sent:
            return
        self._end_sent = True
        cb = self.on_end
        if cb:
            try:
                cb()
            except Exception as e:
                log(f"[miniaudio] on_end error: {e}", 30)

    def _stop_device(self):
        with self._lock:
            self._stopped = True
            self._paused = False
        if self._device is not None:
            try:
                self._device.stop()
            except Exception:
                pass
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None
        self._ended = False
        self._last_amp = 0.0

    def stop(self):
        self._stop_device()

    def pause(self):
        with self._lock:
            self._paused = True

    def resume(self):
        with self._lock:
            self._paused = False

    def is_playing(self):
        return (self._device is not None) and (not self._stopped) and (not self._paused) and (not self._ended)

    def set_volume(self, vol_percent):
        with self._lock:
            self._volume = max(0.0, min(1.0, vol_percent / 100.0))

    def get_time(self):
        if self._sample_rate <= 0:
            return -1, -1
        curr = int(self._frames_played * 1000 / self._sample_rate)
        total = int(self._total_frames * 1000 / self._sample_rate) if self._total_frames else -1
        return curr, total

    def get_position(self):
        if self._total_frames <= 0:
            return 0.0
        return max(0.0, min(1.0, self._frames_played / self._total_frames))

    def set_position(self, ratio):
        if not self._filepath:
            return
        ratio = max(0.0, min(1.0, ratio))
        total_ms = 0
        if self._total_frames and self._sample_rate:
            total_ms = int(self._total_frames * 1000 / self._sample_rate)
        self.play(self._filepath, start_ms=int(total_ms * ratio))

    def get_level(self):
        a = self._last_amp
        return a, a

    def get_spectrum_bands(self):
        samples = self._pcm_chunk
        if not samples or len(samples) < 64:
            return (0.0, 0.0, 0.0)
        n = min(len(samples), 2048)
        third = n // 3

        def rms(start, end):
            s = 0
            c = 0
            for i in range(start, end, 2):
                v = samples[i] / 32768.0
                s += v * v
                c += 1
            if c == 0:
                return 0.0
            return min(1.0, (s / c) ** 0.5 * 2)

        return (rms(0, third), rms(third, third * 2), rms(third * 2, n))

    def free(self):
        self.stop()


class FFmpegBackend(MiniaudioBackend):
    """Decode M4A/AAC/WMA/APE/Opus via ffmpeg CLI → temp WAV → miniaudio."""

    def __init__(self, device_name="", on_end=None):
        super().__init__(device_name=device_name, on_end=on_end)
        self._tmp = None

    def play(self, filepath, start_ms=0):
        # If this is a seek on the WAV we already rendered, do not re-decode.
        if self._tmp and os.path.isfile(self._tmp) and os.path.abspath(filepath) == os.path.abspath(self._tmp):
            return super().play(filepath, start_ms=start_ms)
        wav = self._decode_to_wav(filepath)
        if not wav:
            self.last_error = self.last_error or "ffmpeg decode failed"
            return False
        old = self._tmp
        self._tmp = None
        ok = super().play(wav, start_ms=start_ms)
        if ok:
            self._tmp = wav
        else:
            _cleanup_file(wav)
        if old and old != wav:
            _cleanup_file(old)
        return ok

    def _decode_to_wav(self, filepath):
        wav = _ffmpeg_decode_to_wav(filepath)
        if not wav:
            self.last_error = "ffmpeg cannot decode this file (is ffmpeg.exe next to the player?)"
        return wav

    def stop(self):
        super().stop()
        if self._tmp and os.path.exists(self._tmp):
            try:
                os.remove(self._tmp)
            except Exception:
                pass
            self._tmp = None


class OpenMptBackend(MiniaudioBackend):
    """Render tracker modules with openmpt123.exe (then ctypes / ffmpeg), play WAV."""

    def __init__(self, device_name="", on_end=None):
        super().__init__(device_name=device_name, on_end=on_end)
        self._tmp = None

    def play(self, filepath, start_ms=0):
        if self._tmp and os.path.isfile(self._tmp) and os.path.abspath(filepath) == os.path.abspath(self._tmp):
            return super().play(filepath, start_ms=start_ms)
        wav = self._render(filepath)
        if not wav:
            return False
        old = self._tmp
        self._tmp = None
        ok = super().play(wav, start_ms=start_ms)
        if ok:
            self._tmp = wav
        else:
            _cleanup_file(wav)
        if old and old != wav:
            _cleanup_file(old)
        return ok

    def _render(self, filepath):
        _prepare_native_search_path()
        wav = self._render_openmpt123(filepath)
        if wav:
            return wav
        wav = self._render_ctypes(filepath)
        if wav:
            return wav
        wav = _ffmpeg_decode_to_wav(filepath)
        if wav:
            log("[openmpt] ffmpeg fallback ok", 20)
            return wav
        if not probe_openmpt():
            self.last_error = "need openmpt123.exe (or libopenmpt.dll) next to the player"
        else:
            self.last_error = "openmpt123 / libopenmpt could not render this module"
        return None

    def _bind(self, lib):
        try:
            lib.openmpt_module_destroy.argtypes = [ctypes.c_void_p]
            lib.openmpt_module_destroy.restype = None
        except Exception:
            pass
        try:
            lib.openmpt_module_read_interleaved_stereo.restype = ctypes.c_size_t
            lib.openmpt_module_read_interleaved_stereo.argtypes = [
                ctypes.c_void_p, ctypes.c_int32, ctypes.c_size_t, ctypes.POINTER(ctypes.c_short)
            ]
        except Exception:
            pass
        try:
            lib.openmpt_module_set_repeat_count.argtypes = [ctypes.c_void_p, ctypes.c_int32]
            lib.openmpt_module_set_repeat_count.restype = None
        except Exception:
            pass

    def _create_module(self, lib, data: bytes):
        buf = ctypes.create_string_buffer(data, len(data))
        if hasattr(lib, "openmpt_module_create_from_memory2"):
            lib.openmpt_module_create_from_memory2.restype = ctypes.c_void_p
            lib.openmpt_module_create_from_memory2.argtypes = [
                ctypes.c_void_p, ctypes.c_size_t,
                ctypes.c_void_p, ctypes.c_void_p,
                ctypes.c_void_p, ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_int),
                ctypes.c_void_p,
            ]
            err = ctypes.c_int(0)
            mod = lib.openmpt_module_create_from_memory2(
                ctypes.cast(buf, ctypes.c_void_p), len(data),
                None, None, None, None, ctypes.byref(err), None,
            )
            if mod:
                return mod, buf
            log(f"[openmpt] create_from_memory2 err={err.value}", 30)
        if hasattr(lib, "openmpt_module_create_from_memory"):
            lib.openmpt_module_create_from_memory.restype = ctypes.c_void_p
            lib.openmpt_module_create_from_memory.argtypes = [
                ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
            ]
            mod = lib.openmpt_module_create_from_memory(
                ctypes.cast(buf, ctypes.c_void_p), len(data), None, None, None
            )
            if mod:
                return mod, buf
        return None, buf

    def _render_ctypes(self, filepath):
        lib = _openmpt_lib()
        if lib is None:
            return None
        try:
            with open(filepath, "rb") as f:
                data = f.read()
        except Exception as e:
            log(f"[openmpt] read failed: {e}", 40)
            return None
        if not data:
            return None
        self._bind(lib)
        mod, _keep = self._create_module(lib, data)
        if not mod:
            log("[openmpt] null module", 40)
            return None
        try:
            try:
                lib.openmpt_module_set_repeat_count(mod, 0)
            except Exception:
                pass
            frames = 2048
            pcm = (ctypes.c_short * (frames * CHANNELS))()
            chunks = []
            max_bytes = SAMPLE_RATE * CHANNELS * 2 * 60 * 30
            total = 0
            while total < max_bytes:
                n = lib.openmpt_module_read_interleaved_stereo(mod, SAMPLE_RATE, frames, pcm)
                if not n:
                    break
                nbytes = int(n) * CHANNELS * 2
                chunks.append(bytes(pcm)[:nbytes])
                total += nbytes
            if not chunks:
                log("[openmpt] zero frames", 40)
                return None
            fd, tmp = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            if _write_wav_s16(tmp, b"".join(chunks)):
                log("[openmpt] ctypes render ok", 20)
                return tmp
            try:
                os.remove(tmp)
            except Exception:
                pass
            return None
        except Exception as e:
            log(f"[openmpt] ctypes failed: {e}", 40)
            return None
        finally:
            try:
                lib.openmpt_module_destroy(mod)
            except Exception:
                pass

    def _render_openmpt123(self, filepath):
        exe = _openmpt123_bin()
        if not exe:
            log("[openmpt123] exe not found", 30)
            return None

        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            os.remove(tmp)
        except Exception:
            pass

        cmds = [
            [exe, "--batch", "--quiet", "--force", "-o", tmp, filepath],
            [exe, "--render", "--quiet", "--force", "-o", tmp, filepath],
            [exe, "--render", "--force", "--output-type", "wav", "-o", tmp, filepath],
            [exe, "--output", tmp, filepath],
            [exe, "-o", tmp, filepath],
        ]
        for cmd in cmds:
            try:
                r = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=180,
                    **subprocess_hidden_kwargs(),
                )
                if r.returncode == 0 and os.path.isfile(tmp) and os.path.getsize(tmp) > 128:
                    log(f"[openmpt123] rendered {filepath}", 20)
                    return tmp
                err = (r.stderr or b"")[-200:].decode("utf-8", "ignore")
                log(f"[openmpt123] rc={r.returncode} {err}", 30)
            except subprocess.TimeoutExpired:
                log("[openmpt123] timeout", 40)
            except Exception as e:
                log(f"[openmpt123] {e}", 40)
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
        return None

    def stop(self):
        super().stop()
        if self._tmp and os.path.exists(self._tmp):
            try:
                os.remove(self._tmp)
            except Exception:
                pass
            self._tmp = None


class FluidSynthBackend(MiniaudioBackend):
    """Render MIDI/RMI with FluidSynth CLI or pyfluidsynth → WAV → miniaudio."""

    def __init__(self, device_name="", on_end=None):
        super().__init__(device_name=device_name, on_end=on_end)
        self._tmp = None
        self._mid_tmp = None

    def play(self, filepath, start_ms=0):
        if self._tmp and os.path.isfile(self._tmp) and os.path.abspath(filepath) == os.path.abspath(self._tmp):
            return super().play(filepath, start_ms=start_ms)
        wav = self._render_midi(filepath)
        if not wav:
            return False
        old = self._tmp
        self._tmp = None
        ok = super().play(wav, start_ms=start_ms)
        if ok:
            self._tmp = wav
        else:
            _cleanup_file(wav)
        if old and old != wav:
            _cleanup_file(old)
        return ok

    def _smf_path(self, filepath) -> str | None:
        smf = extract_smf_bytes(filepath)
        if not smf:
            self.last_error = "not a valid MIDI / RMI file"
            return None
        if smf.startswith(b"MThd") and filepath.lower().endswith((".mid", ".midi", ".kar")):
            try:
                with open(filepath, "rb") as f:
                    if f.read(4) == b"MThd":
                        return filepath
            except Exception:
                pass
        fd, tmp = tempfile.mkstemp(suffix=".mid")
        os.close(fd)
        try:
            with open(tmp, "wb") as f:
                f.write(smf)
            old = self._mid_tmp
            self._mid_tmp = tmp
            if old and old != tmp:
                _cleanup_file(old)
            return tmp
        except Exception as e:
            log(f"[fluidsynth] write temp mid: {e}", 40)
            _cleanup_file(tmp)
            return None

    def _render_midi(self, filepath):
        sf2 = _soundfont_path()
        if not sf2:
            self.last_error = "need soundfont.sf2 next to the player (MIDI)"
            log("[fluidsynth] soundfont.sf2 missing", 40)
            return None

        mid = self._smf_path(filepath)
        if not mid:
            return None

        # 1) CLI — -a file so it does not try to open a sound card
        exe = _fluidsynth_bin()
        if exe:
            _prepare_native_search_path()
            fd, tmp = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            try:
                os.remove(tmp)
            except Exception:
                pass
            cmds = [
                [exe, "-ni", "-a", "file", "-q", "-g", "0.5", "-F", tmp, "-r", str(SAMPLE_RATE), sf2, mid],
                [exe, "-a", "file", "-F", tmp, "-r", str(SAMPLE_RATE), "-ni", sf2, mid],
                [exe, "-ni", "-q", "-g", "0.5", "-F", tmp, "-r", str(SAMPLE_RATE), sf2, mid],
            ]
            for cmd in cmds:
                try:
                    r = subprocess.run(
                        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                        timeout=180,
                        **subprocess_hidden_kwargs(),
                    )
                    if r.returncode == 0 and os.path.isfile(tmp) and os.path.getsize(tmp) > 128:
                        log("[fluidsynth] CLI render ok", 20)
                        return tmp
                    err = (r.stderr or b"")[-300:].decode("utf-8", "ignore")
                    log(f"[fluidsynth] CLI rc={r.returncode} {err}", 30)
                except subprocess.TimeoutExpired:
                    log("[fluidsynth] CLI timeout", 40)
                except Exception as e:
                    log(f"[fluidsynth] CLI: {e}", 30)
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass

        # 2) pyfluidsynth (needs libfluidsynth DLL)
        try:
            with open(mid, "rb") as f:
                smf = f.read()
            pcm = render_midi_pyfluidsynth(smf, sf2)
            if pcm:
                fd, tmp = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                if _write_wav_s16(tmp, pcm):
                    log("[fluidsynth] pyfluidsynth render ok", 20)
                    return tmp
                try:
                    os.remove(tmp)
                except Exception:
                    pass
        except Exception as e:
            log(f"[fluidsynth] pyfluidsynth: {e}", 30)

        # 3) ffmpeg (only works if ffmpeg was built with a MIDI decoder)
        wav = _ffmpeg_decode_to_wav(mid)
        if wav:
            log("[fluidsynth] ffmpeg fallback ok", 20)
            return wav

        if not exe and not probe_fluidsynth():
            self.last_error = "need fluidsynth.exe (or libfluidsynth-3.dll) next to the player"
        else:
            self.last_error = "FluidSynth could not render this MIDI"
        return None

    def stop(self):
        super().stop()
        if self._tmp and os.path.exists(self._tmp):
            try:
                os.remove(self._tmp)
            except Exception:
                pass
            self._tmp = None
        if self._mid_tmp and os.path.exists(self._mid_tmp):
            try:
                os.remove(self._mid_tmp)
            except Exception:
                pass
            self._mid_tmp = None


# ---------- engine ----------
MINIAUDIO_EXT = {".mp3", ".wav", ".flac", ".ogg"}
FFMPEG_EXT = {".m4a", ".aac", ".wma", ".opus", ".alac", ".ape", ".ac3", ".mp2", ".mpga"}
OPENMPT_EXT = {
    ".mod", ".xm", ".it", ".s3m", ".mtm", ".umx", ".mo3", ".mptm", ".mpt", ".stm",
    ".669", ".far", ".ult", ".mt2", ".okt", ".ptm", ".med", ".dbm", ".digi",
    ".dmf", ".dsm", ".imf", ".j2b", ".mdl", ".psm", ".amf", ".ams", ".mmcmp",
}
MIDI_EXT = {".mid", ".midi", ".rmi", ".kar"}


class AudioEngine:
    def __init__(self, device_name: str = "", on_end=None):
        _prepare_native_search_path()
        self.device_name = device_name or ""
        self.on_end = on_end
        self._backend: AudioBackend | None = None
        self._backend_name = ""
        self._volume = 50
        self.last_error = ""

    def set_on_end(self, cb):
        self.on_end = cb
        if self._backend is not None:
            self._backend.on_end = cb

    def set_device_name(self, name: str):
        self.device_name = name or ""

    def _make(self, kind: str) -> AudioBackend:
        kwargs = dict(device_name=self.device_name, on_end=self.on_end)
        if kind == "miniaudio":
            return MiniaudioBackend(**kwargs)
        if kind == "ffmpeg":
            return FFmpegBackend(**kwargs)
        if kind == "openmpt":
            return OpenMptBackend(**kwargs)
        if kind == "fluidsynth":
            return FluidSynthBackend(**kwargs)
        return MiniaudioBackend(**kwargs)

    def pick_kind(self, filepath: str) -> str:
        if str(filepath).lower().startswith(("http://", "https://")):
            return "ffmpeg"
        ext = os.path.splitext(filepath)[1].lower()
        if ext in MIDI_EXT:
            return "fluidsynth"
        if ext in OPENMPT_EXT:
            return "openmpt"
        if ext in FFMPEG_EXT:
            return "ffmpeg"
        if ext in MINIAUDIO_EXT:
            return "miniaudio"
        return "ffmpeg"

    def play(self, filepath: str, start_ms: int = 0) -> bool:
        self.stop()
        kind = self.pick_kind(filepath)
        order = [kind]
        # do NOT blindly fall back to miniaudio for tracker/midi — it cannot decode them
        if kind == "openmpt":
            order.append("ffmpeg")
        elif kind == "fluidsynth":
            pass
        elif kind == "ffmpeg":
            order.append("miniaudio")
        elif kind == "miniaudio":
            order.append("ffmpeg")
        errors = []
        for k in order:
            backend = self._make(k)
            backend.set_volume(self._volume)
            ok = backend.play(filepath, start_ms=start_ms)
            if ok:
                self._backend = backend
                self._backend_name = k
                self.last_error = ""
                log(f"[engine] {k} playing {filepath}", 20)
                return True
            err = getattr(backend, "last_error", "") or k
            errors.append(f"{k}: {err}")
            backend.free()
        self.last_error = " | ".join(errors) if errors else "all backends failed"
        log(f"[engine] all backends failed for {filepath}: {self.last_error}", 40)
        self._backend = None
        self._backend_name = ""
        return False

    def stop(self):
        if self._backend is not None:
            try:
                self._backend.stop()
            except Exception:
                pass
            try:
                self._backend.free()
            except Exception:
                pass
            self._backend = None

    def pause(self):
        if self._backend:
            self._backend.pause()

    def resume(self):
        if self._backend:
            self._backend.resume()

    def is_playing(self):
        return bool(self._backend) and self._backend.is_playing()

    def is_paused(self):
        if not self._backend:
            return False
        return getattr(self._backend, "_paused", False) and not getattr(self._backend, "_stopped", True)

    def set_volume(self, vol_percent: int):
        self._volume = max(0, min(100, int(vol_percent)))
        if self._backend:
            self._backend.set_volume(self._volume)

    def get_time(self):
        if not self._backend:
            return -1, -1
        return self._backend.get_time()

    def get_position(self):
        if not self._backend:
            return 0.0
        return self._backend.get_position()

    def set_position(self, ratio: float):
        if self._backend:
            self._backend.set_position(ratio)

    def get_level(self):
        if not self._backend:
            return 0.0, 0.0
        return self._backend.get_level()

    def get_spectrum_bands(self):
        if not self._backend or not hasattr(self._backend, "get_spectrum_bands"):
            return (0.0, 0.0, 0.0)
        return self._backend.get_spectrum_bands()

    @property
    def current_name(self):
        return self._backend_name

    def free(self):
        self.stop()
