import sys
import os

# --- VLC DLL bootstrap: works for both script and frozen exe ---
if getattr(sys, 'frozen', False):
    _res_dir = getattr(sys, "_MEIPASS", None)
else:
    _res_dir = os.path.dirname(os.path.abspath(__file__))

if _res_dir:
    try:
        os.add_dll_directory(_res_dir)
    except Exception:
        pass
    _plugins_dir = os.path.join(_res_dir, "plugins")
    if os.path.isdir(_plugins_dir):
        try:
            os.add_dll_directory(_plugins_dir)
        except Exception:
            pass
        os.environ["VLC_PLUGIN_PATH"] = _plugins_dir

import vlc
import ctypes
import threading
import re
import subprocess
import tempfile
import time
import json
import traceback
from collections import OrderedDict, deque

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QFrame, QSlider, QSizePolicy,
    QInputDialog, QLineEdit, QStackedWidget, QPushButton, QMessageBox,
    QSystemTrayIcon, QMenu, QStyle, QFileDialog, QDialog, QTextEdit,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer, QEvent, QObject, QThread, pyqtSignal, QMetaObject, pyqtSlot, QPoint
from PyQt6.QtGui import (
    QFont, QKeyEvent, QFontDatabase, QPainter, QColor, QPen, QFontMetrics,
    QPixmap, QIcon, QAction, QGuiApplication, QTextCursor, QTextCharFormat
)

APP_VERSION = "0.19.9"

QWIDGETSIZE_MAX = 16777215

# ---------- 選用依賴 ----------
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

try:
    from mutagen import File as MutagenFile
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False


# ---------- 基礎目錄 ----------
def app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def data_path(name):
    return os.path.join(app_dir(), name)


def resource_path(relative):
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative)


# ---------- 自訂字型 ----------
def load_custom_font():
    font_path = resource_path("font.ttf")
    if os.path.isfile(font_path):
        try:
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    print(f"[字型] 已載入自訂字型: {families[0]}")
                    return families[0]
        except Exception as e:
            print(f"[字型] 載入自訂字型失敗: {e}")
    return None


# ---------- 防止睡眠 ----------
def prevent_sleep(enable):
    if sys.platform == 'win32':
        try:
            if enable:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000002)
            else:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        except Exception:
            pass


# ---------- 拖曳外框（移動時顯示 Windows 風格外框） ----------
class DragFrame(QWidget):
    def __init__(self, accent_color="#FFFFFF"):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.accent_color = accent_color

    def set_accent_color(self, color):
        self.accent_color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(QColor(self.accent_color), 2)
        painter.setPen(pen)
        painter.drawRect(1, 1, self.width() - 2, self.height() - 2)
        painter.end()


# ---------- 跑馬燈標籤 ----------
class ScrollingLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.full_text = "------------------------"
        self.scroll_pos = 0
        self.fixed_visible_chars = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.scroll)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(50)

    def setText(self, text):
        self.full_text = text if text else "------------------------"
        self.scroll_pos = 0
        self.update_display()
        if len(self.full_text) > self.visible_chars():
            self.timer.start(300)
        else:
            self.timer.stop()
            super().setText(self.full_text)

    def visible_chars(self):
        if self.fixed_visible_chars > 0:
            return self.fixed_visible_chars
        w = self.width()
        if w <= 0:
            return 25
        return max(5, w // 8)

    def update_display(self):
        if len(self.full_text) <= self.visible_chars():
            super().setText(self.full_text)
            return
        visible_len = self.visible_chars()
        if self.scroll_pos + visible_len > len(self.full_text):
            display = self.full_text[self.scroll_pos:] + "   " + \
                      self.full_text[:visible_len - (len(self.full_text) - self.scroll_pos)]
        else:
            display = self.full_text[self.scroll_pos:self.scroll_pos + visible_len]
        super().setText(display)

    def scroll(self):
        if len(self.full_text) <= self.visible_chars():
            self.timer.stop()
            return
        self.scroll_pos = (self.scroll_pos + 1) % len(self.full_text)
        self.update_display()

    def stop_scroll(self):
        self.timer.stop()
        super().setText(self.full_text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_display()
        if len(self.full_text) > self.visible_chars():
            if not self.timer.isActive():
                self.timer.start(300)
        else:
            self.timer.stop()
            super().setText(self.full_text)


# ---------- 文字進度條 ----------
class TextBar(QLabel):
    def __init__(self, max_val=100, bar_length=20, show_percent=True, parent=None):
        super().__init__(parent)
        self.max_val = max_val
        self.bar_length = bar_length
        self.show_percent = show_percent
        self._value = 0
        self.accent_color = "#FFFFFF"
        self.prefix = ""
        self.setStyleSheet("background: transparent; border: none;")
        self.update_display()

    def set_accent_color(self, color_str):
        self.accent_color = color_str
        self.setStyleSheet(f"color: {color_str}; background: transparent;")
        self.update_display()

    def setValue(self, val):
        self._value = max(0, min(self.max_val, val))
        self.update_display()

    def value(self):
        return self._value

    def setBarLength(self, length):
        self.bar_length = length
        self.update_display()

    def update_display(self):
        ratio = self._value / self.max_val if self.max_val > 0 else 0
        filled = int(ratio * self.bar_length)
        empty = self.bar_length - filled
        bar = "[" + "█" * filled + "░" * empty + "]"
        if self.show_percent:
            percent = int(ratio * 100)
            text = f"{bar} {percent:3d}%"
        else:
            text = bar
        if self.prefix:
            text = f"{self.prefix} {text}"
        self.setText(text)


# ---------- 文字等化器 ----------
class TextEQWidget(QFrame):
    def __init__(self, parent=None, accent_color="#FFFFFF"):
        super().__init__(parent)
        self.accent_color = QColor(accent_color)
        self.setStyleSheet("background-color: transparent; border: none;")
        self.setMinimumHeight(80)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.labels = []
        self.names = ["低音:", "中音:", "高音:", "音量:"]
        for name in self.names:
            lbl = QLabel()
            lbl.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color: {self.accent_color.name()}; background: transparent;")
            layout.addWidget(lbl)
            self.labels.append(lbl)
        self.mode = "all"
        self.set_levels(0, 0, 0, 0)

    def set_accent_color(self, color_str):
        self.accent_color = QColor(color_str)
        for lbl in self.labels:
            lbl.setStyleSheet(f"color: {color_str}; background: transparent;")

    def set_mode(self, mode):
        self.mode = mode
        if mode == "volume":
            for i in range(3):
                self.labels[i].setVisible(False)
        else:
            for lbl in self.labels:
                lbl.setVisible(True)

    def set_levels(self, bass, mid, treble, vol):
        vals = [max(0.0, min(1.0, bass)),
                max(0.0, min(1.0, mid)),
                max(0.0, min(1.0, treble)),
                max(0.0, min(1.0, vol))]
        total_blocks = 20
        for i, lbl in enumerate(self.labels):
            blocks = int(vals[i] * total_blocks)
            bar = "[" + "█" * blocks + "░" * (total_blocks - blocks) + "]"
            percent = int(vals[i] * 100)
            lbl.setText(f"{self.names[i]:7s} {bar} {percent:3d}%")

    def fix_widths(self, font):
        fm = QFontMetrics(font)
        max_width = 0
        for name in self.names:
            max_text = f"{name:7s} [{'█' * 20}] {100:3d}%"
            w = fm.horizontalAdvance(max_text)
            if w > max_width:
                max_width = w
        for lbl in self.labels:
            lbl.setFixedWidth(max_width + 4)


# ---------- CPU 親和性 ----------
def apply_cpu_affinity():
    if sys.platform != 'win32':
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


# ================== 日誌 ==================
LOG_FILE = None
LOG_ENABLED = True
LOG_LEVEL = 20
LOG_LEVEL_NAMES = {10: "除錯", 20: "資訊", 30: "警告", 40: "錯誤"}


def init_log():
    global LOG_FILE, LOG_ENABLED
    if not LOG_ENABLED or LOG_FILE:
        return
    log_dir = os.path.join(app_dir(), "data")
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        LOG_FILE = None
        return
    now = time.localtime()
    filename = time.strftime("player_data_%H.%M.%S-%d.%m.%Y.log", now)
    filepath = os.path.join(log_dir, filename)
    try:
        LOG_FILE = open(filepath, "w", encoding="utf-8")
    except Exception:
        LOG_FILE = None


def log(message, level=20):
    global LOG_FILE, LOG_ENABLED, LOG_LEVEL
    if not LOG_ENABLED or not LOG_FILE:
        return
    if level < LOG_LEVEL:
        return
    stamp = time.strftime("%H:%M:%S", time.localtime())
    tag = LOG_LEVEL_NAMES.get(level, "資訊")
    try:
        LOG_FILE.write(f"[{stamp}] [{tag}] {message}\n")
        LOG_FILE.flush()
    except Exception:
        pass


def close_log():
    global LOG_FILE
    if LOG_FILE:
        try:
            log("---- 工作階段結束 ----")
            LOG_FILE.close()
        except Exception:
            pass
        LOG_FILE = None


# ================== VLC ctypes 裝置 API ==================
class VLC_AUDIO_DEVICE(ctypes.Structure):
    pass


VLC_AUDIO_DEVICE._fields_ = [
    ("psz_device", ctypes.c_char_p),
    ("psz_description", ctypes.c_char_p),
    ("p_next", ctypes.POINTER(VLC_AUDIO_DEVICE)),
]


def _load_libvlc():
    candidates = [
        resource_path("libvlc.dll"),
        os.path.join(app_dir(), "libvlc.dll"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            try:
                return ctypes.CDLL(p)
            except OSError:
                continue
    try:
        return ctypes.CDLL("libvlc.dll")
    except OSError:
        return None


def vlc_list_audio_devices(vlc_instance_ptr, aout=b"mmdevice"):
    results = []
    if vlc_instance_ptr is None:
        return results
    lib = _load_libvlc()
    if lib is None:
        log("[VLC] 無法載入 libvlc.dll 以列舉裝置", 30)
        return results
    try:
        lib.libvlc_audio_output_device_list_get.restype = ctypes.POINTER(VLC_AUDIO_DEVICE)
        lib.libvlc_audio_output_device_list_get.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.libvlc_audio_output_device_list_release.restype = None
        lib.libvlc_audio_output_device_list_release.argtypes = [ctypes.POINTER(VLC_AUDIO_DEVICE)]

        head = lib.libvlc_audio_output_device_list_get(ctypes.c_void_p(vlc_instance_ptr), aout)
        if not head:
            return results
        node = head
        while node:
            entry = node.contents
            did = entry.psz_device.decode("utf-8", errors="replace") if entry.psz_device else ""
            desc = entry.psz_description.decode("utf-8", errors="replace") if entry.psz_description else ""
            results.append((did, desc))
            node = entry.p_next
        lib.libvlc_audio_output_device_list_release(head)
    except Exception as e:
        log(f"[VLC] 列舉裝置失敗: {e}", 30)
    return results


def vlc_set_audio_device(vlc_player, device_id):
    if vlc_player is None:
        return False
    lib = _load_libvlc()
    if lib is None:
        log("[VLC] 無法載入 libvlc.dll 以設定裝置", 30)
        return False
    try:
        lib.libvlc_audio_output_device_set.restype = None
        lib.libvlc_audio_output_device_set.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        player_ptr = ctypes.c_void_p(vlc_player)
        dev_b = device_id.encode("utf-8") if device_id else None
        lib.libvlc_audio_output_device_set(player_ptr, None, dev_b)
        return True
    except Exception as e:
        log(f"[VLC] 設定裝置失敗: {e}", 30)
        return False


# ================== BASS ==================
BASS_SYNC_PROC = ctypes.CFUNCTYPE(None, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p)


class BASS_MIDI_FONT(ctypes.Structure):
    _fields_ = [
        ("font", ctypes.c_ulong),
        ("preset", ctypes.c_int),
        ("bank", ctypes.c_int)
    ]


class BASS_CHANNELINFO(ctypes.Structure):
    _fields_ = [
        ("freq", ctypes.c_ulong),
        ("chans", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("ctype", ctypes.c_ulong),
        ("origres", ctypes.c_ulong),
        ("plugin", ctypes.c_ulong),
        ("sample", ctypes.c_ulong),
        ("filename", ctypes.c_char * 260)
    ]


class BASS_DEVICEINFO(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char_p),
        ("driver", ctypes.c_char_p),
        ("flags", ctypes.c_ulong),
    ]


def bass_list_devices():
    results = []
    try:
        bass = ctypes.CDLL(resource_path("bass.dll"))
    except OSError:
        return results
    try:
        bass.BASS_GetDeviceCount.restype = ctypes.c_int
        bass.BASS_GetDeviceInfo.restype = ctypes.c_int
        bass.BASS_GetDeviceInfo.argtypes = [ctypes.c_int, ctypes.POINTER(BASS_DEVICEINFO)]
        count = bass.BASS_GetDeviceCount()
        if count <= 0:
            return results
        for i in range(count):
            info = BASS_DEVICEINFO()
            if bass.BASS_GetDeviceInfo(i, ctypes.pointer(info)):
                name = info.name.decode("utf-8", errors="replace") if info.name else f"裝置 {i}"
                results.append((i, name))
    except Exception as e:
        log(f"[BASS] 列舉裝置失敗: {e}", 30)
    return results


class BassEngine(QObject):
    endSignal = pyqtSignal()

    def __init__(self, device_index=-1):
        super().__init__()
        self.bass = None
        self.bassmidi = None
        self.handle = 0
        self.is_midi = False
        self.is_stream = False
        self._end_callback = None
        self._device_index = device_index
        self._sync_callback = BASS_SYNC_PROC(self._on_sync_end)
        self.endSignal.connect(self._emit_end_safely)
        self._decode_handle = 0
        self._decode_filepath = ""
        self._init_bass()

    def _init_bass(self):
        try:
            bass_path = resource_path("bass.dll")
            self.bass = ctypes.CDLL(bass_path)

            self.bass.BASS_Init.restype = ctypes.c_int
            self.bass.BASS_Init.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p]
            self.bass.BASS_ErrorGetCode.restype = ctypes.c_int
            self.bass.BASS_StreamCreateFile.restype = ctypes.c_ulong
            self.bass.BASS_StreamCreateFile.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_ulonglong, ctypes.c_ulong, ctypes.c_ulong]
            self.bass.BASS_ChannelBytes2Seconds.restype = ctypes.c_double
            self.bass.BASS_ChannelBytes2Seconds.argtypes = [ctypes.c_ulong, ctypes.c_ulonglong]
            self.bass.BASS_ChannelGetLength.restype = ctypes.c_ulonglong
            self.bass.BASS_ChannelGetLength.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
            self.bass.BASS_ChannelGetPosition.restype = ctypes.c_ulonglong
            self.bass.BASS_ChannelGetPosition.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
            self.bass.BASS_MusicLoad.restype = ctypes.c_ulong
            self.bass.BASS_MusicLoad.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_ulonglong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
            self.bass.BASS_ChannelPlay.restype = ctypes.c_int
            self.bass.BASS_ChannelPlay.argtypes = [ctypes.c_ulong, ctypes.c_int]
            self.bass.BASS_ChannelStop.restype = ctypes.c_int
            self.bass.BASS_ChannelStop.argtypes = [ctypes.c_ulong]
            self.bass.BASS_StreamFree.restype = ctypes.c_int
            self.bass.BASS_StreamFree.argtypes = [ctypes.c_ulong]
            self.bass.BASS_ChannelSetSync.restype = ctypes.c_ulong
            self.bass.BASS_ChannelSetSync.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulonglong, ctypes.c_void_p, ctypes.c_void_p]
            self.bass.BASS_ChannelSetAttribute.restype = ctypes.c_int
            self.bass.BASS_ChannelSetAttribute.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_float]
            self.bass.BASS_ChannelIsActive.restype = ctypes.c_ulong
            self.bass.BASS_ChannelIsActive.argtypes = [ctypes.c_ulong]
            self.bass.BASS_ChannelPause.restype = ctypes.c_int
            self.bass.BASS_ChannelPause.argtypes = [ctypes.c_ulong]
            self.bass.BASS_Free.restype = ctypes.c_int
            self.bass.BASS_ChannelGetLevel.restype = ctypes.c_ulong
            self.bass.BASS_ChannelGetLevel.argtypes = [ctypes.c_ulong]
            self.bass.BASS_ChannelGetData.restype = ctypes.c_ulong
            self.bass.BASS_ChannelGetData.argtypes = [ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong]
            self.bass.BASS_ChannelSetPosition.restype = ctypes.c_int
            self.bass.BASS_ChannelSetPosition.argtypes = [ctypes.c_ulong, ctypes.c_ulonglong, ctypes.c_ulong]
            self.bass.BASS_ChannelGetInfo.restype = ctypes.c_int
            self.bass.BASS_ChannelGetInfo.argtypes = [ctypes.c_ulong, ctypes.POINTER(BASS_CHANNELINFO)]
            self.bass.BASS_ChannelSeconds2Bytes.restype = ctypes.c_ulonglong
            self.bass.BASS_ChannelSeconds2Bytes.argtypes = [ctypes.c_ulong, ctypes.c_double]

            dev = self._device_index if self._device_index is not None else -1
            if not self.bass.BASS_Init(dev, 44100, 0, 0, 0):
                log(f"[BASS] 裝置 {dev} 初始化失敗，錯誤代碼: {self.bass.BASS_ErrorGetCode()}", 40)
                if dev != -1:
                    if self.bass.BASS_Init(-1, 44100, 0, 0, 0):
                        log("[BASS] 退回預設裝置成功", 30)
                        self._device_index = -1
                    else:
                        self.bass = None
                        return
                else:
                    self.bass = None
                    return

            bassmidi_path = resource_path("bassmidi.dll")
            if os.path.exists(bassmidi_path):
                self.bassmidi = ctypes.CDLL(bassmidi_path)
                self.bassmidi.BASS_MIDI_FontInit.restype = ctypes.c_ulong
                self.bassmidi.BASS_MIDI_FontInit.argtypes = [ctypes.c_char_p, ctypes.c_ulong]
                self.bassmidi.BASS_MIDI_StreamSetFonts.restype = ctypes.c_int
                self.bassmidi.BASS_MIDI_StreamSetFonts.argtypes = [ctypes.c_ulong, ctypes.POINTER(BASS_MIDI_FONT), ctypes.c_ulong]
                self.bassmidi.BASS_MIDI_StreamCreateFile.restype = ctypes.c_ulong
                self.bassmidi.BASS_MIDI_StreamCreateFile.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_ulonglong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]

                sf2 = resource_path("soundfont.sf2")
                if not os.path.exists(sf2):
                    log("[BASS] 缺少 SoundFont，已停用 MIDI", 30)
                    self.bassmidi = None
                else:
                    font_handle = self.bassmidi.BASS_MIDI_FontInit(sf2.encode(), 0)
                    if font_handle:
                        bfont = BASS_MIDI_FONT(font_handle, -1, 0)
                        self.bassmidi.BASS_MIDI_StreamSetFonts(0, ctypes.pointer(bfont), 1)
                        log("[BASS] SoundFont 已載入", 20)
                    else:
                        log("[BASS] SoundFont 初始化失敗", 30)
                        self.bassmidi = None
            else:
                log("[BASS] 找不到 bassmidi.dll", 30)
            log(f"[BASS] 已於裝置索引 {self._device_index} 初始化", 20)
        except OSError as e:
            log(f"[BASS] DLL 載入錯誤: {e}", 40)
            self.bass = None
        except Exception as e:
            log(f"[BASS] 未預期錯誤: {e}", 40)
            self.bass = None

    def is_available(self):
        return self.bass is not None

    def _on_sync_end(self, handle, channel, data, user):
        QMetaObject.invokeMethod(self, "emitSignalSafe", Qt.ConnectionType.QueuedConnection)

    @pyqtSlot()
    def emitSignalSafe(self):
        self.endSignal.emit()

    @pyqtSlot()
    def _emit_end_safely(self):
        if self._end_callback:
            self._end_callback()

    def play(self, filepath, start_ms=0):
        if not self.is_available():
            return False
        self.stop()
        ext = os.path.splitext(filepath)[1].lower()
        self.is_midi = ext in ('.mid', '.midi', '.rmi', '.kar')
        is_module = ext in ('.mod', '.xm', '.it', '.s3m', '.mtm', '.umx', '.mo3')
        self.is_stream = not (self.is_midi or is_module)

        if self.is_midi:
            if self.bassmidi is None:
                log("[BASS] 缺少 bassmidi 或 SoundFont", 30)
                return False
            self.handle = self.bassmidi.BASS_MIDI_StreamCreateFile(False, filepath.encode(), 0, 0, 0, 0)
            if not self.handle:
                log("[BASS] 建立 MIDI 串流失敗", 40)
                return False
            sf2 = resource_path("soundfont.sf2")
            if os.path.exists(sf2):
                f_h = self.bassmidi.BASS_MIDI_FontInit(sf2.encode(), 0)
                if f_h:
                    bfont = BASS_MIDI_FONT(f_h, -1, 0)
                    self.bassmidi.BASS_MIDI_StreamSetFonts(self.handle, ctypes.pointer(bfont), 1)
        elif is_module:
            self.handle = self.bass.BASS_MusicLoad(False, filepath.encode(), 0, 0, 0, 0)
        else:
            self.handle = self.bass.BASS_StreamCreateFile(False, filepath.encode(), 0, 0, 0)

        if self.handle:
            self.bass.BASS_ChannelSetSync(self.handle, 2, 0, self._sync_callback, None)
            if start_ms and start_ms > 0:
                try:
                    if self.is_midi:
                        byte_pos = int((start_ms / 1000.0) * 44100 * 4)
                    else:
                        byte_pos = int(self.bass.BASS_ChannelSeconds2Bytes(self.handle, start_ms / 1000.0))
                    self.bass.BASS_ChannelSetPosition(self.handle, byte_pos, 0)
                except Exception:
                    pass
            self.bass.BASS_ChannelPlay(self.handle, False)
            log(f"[BASS] 播放中: {filepath} start_ms={start_ms}", 20)
            return True
        log("[BASS] 載入檔案失敗", 40)
        return False

    def stop(self):
        if self.handle:
            try:
                self.bass.BASS_ChannelStop(self.handle)
                self.bass.BASS_StreamFree(self.handle)
            except Exception:
                pass
            self.handle = 0

    def pause(self):
        if self.handle:
            self.bass.BASS_ChannelPause(self.handle)

    def resume(self):
        if self.handle:
            self.bass.BASS_ChannelPlay(self.handle, False)

    def is_playing(self):
        return bool(self.handle) and self.bass.BASS_ChannelIsActive(self.handle) == 1

    def set_volume(self, vol_percent):
        if self.handle:
            vol = max(0.0, min(1.0, vol_percent / 100.0))
            self.bass.BASS_ChannelSetAttribute(self.handle, 2, ctypes.c_float(vol))

    def get_position(self):
        if self.handle:
            pos = self.bass.BASS_ChannelGetPosition(self.handle, 0)
            length = self.bass.BASS_ChannelGetLength(self.handle, 0)
            if length == 0 or length == 0xFFFFFFFFFFFFFFFF:
                return 0.0
            return pos / length
        return 0.0

    def get_time(self):
        if self.handle:
            pos_bytes = self.bass.BASS_ChannelGetPosition(self.handle, 0)
            length_bytes = self.bass.BASS_ChannelGetLength(self.handle, 0)
            if length_bytes == 0 or length_bytes == 0xFFFFFFFFFFFFFFFF:
                return -1, -1
            if self.is_midi:
                seconds_pos = pos_bytes / (44100 * 4)
                seconds_len = length_bytes / (44100 * 4)
            else:
                seconds_pos = self.bass.BASS_ChannelBytes2Seconds(self.handle, pos_bytes)
                seconds_len = self.bass.BASS_ChannelBytes2Seconds(self.handle, length_bytes)
            return int(seconds_pos * 1000), int(seconds_len * 1000)
        return -1, -1

    def set_position(self, ratio):
        if self.handle:
            length = self.bass.BASS_ChannelGetLength(self.handle, 0)
            if length == 0 or length == 0xFFFFFFFFFFFFFFFF:
                return
            pos = int(length * ratio)
            self.bass.BASS_ChannelSetPosition(self.handle, pos, 0)

    def get_level(self):
        if not self.handle or not self.bass:
            return 0.0, 0.0
        try:
            level = self.bass.BASS_ChannelGetLevel(self.handle)
            left = (level & 0xFFFF) / 32768.0
            right = ((level >> 16) & 0xFFFF) / 32768.0
            return left, right
        except Exception:
            return 0.0, 0.0

    def open_decode_stream(self, filepath):
        if not self.is_available():
            return 0
        if self._decode_handle and self._decode_filepath == filepath:
            if self.bass.BASS_ChannelIsActive(self._decode_handle) != 0:
                return self._decode_handle
        self.close_decode_stream()

        ext = os.path.splitext(filepath)[1].lower()
        is_midi = ext in ('.mid', '.midi', '.rmi', '.kar')
        is_module = ext in ('.mod', '.xm', '.it', '.s3m', '.mtm', '.umx', '.mo3')
        decode_flag = 0x200000

        if is_midi and self.bassmidi:
            self._decode_handle = self.bassmidi.BASS_MIDI_StreamCreateFile(
                False, filepath.encode(), 0, 0, 0, decode_flag
            )
            if self._decode_handle:
                sf2 = resource_path("soundfont.sf2")
                if os.path.exists(sf2):
                    f_h = self.bassmidi.BASS_MIDI_FontInit(sf2.encode(), 0)
                    if f_h:
                        bfont = BASS_MIDI_FONT(f_h, -1, 0)
                        self.bassmidi.BASS_MIDI_StreamSetFonts(self._decode_handle, ctypes.pointer(bfont), 1)
        elif is_module:
            self._decode_handle = self.bass.BASS_MusicLoad(
                False, filepath.encode(), 0, 0, decode_flag, 0
            )
        else:
            self._decode_handle = self.bass.BASS_StreamCreateFile(
                False, filepath.encode(), 0, 0, decode_flag
            )

        if self._decode_handle:
            self._decode_filepath = filepath
            self.bass.BASS_ChannelSetPosition(self._decode_handle, 0, 0)
        else:
            self._decode_filepath = ""
        return self._decode_handle

    def close_decode_stream(self):
        if self._decode_handle:
            try:
                self.bass.BASS_StreamFree(self._decode_handle)
            except Exception:
                pass
            self._decode_handle = 0
            self._decode_filepath = ""

    def get_decode_sample_rate(self):
        if not self._decode_handle:
            return 44100
        info = BASS_CHANNELINFO()
        if self.bass.BASS_ChannelGetInfo(self._decode_handle, ctypes.pointer(info)):
            return info.freq
        return 44100

    def get_spectrum_bands_from_decode(self, time_ms, fft_size=2048):
        if not self._decode_handle or not self.bass:
            return (0.0, 0.0, 0.0)
        if self.bass.BASS_ChannelIsActive(self._decode_handle) == 0:
            return (0.0, 0.0, 0.0)
        total_bytes = self.bass.BASS_ChannelGetLength(self._decode_handle, 0)
        if total_bytes == 0 or total_bytes == 0xFFFFFFFFFFFFFFFF:
            return (0.0, 0.0, 0.0)
        if time_ms < 0:
            return (0.0, 0.0, 0.0)
        total_seconds = self.bass.BASS_ChannelBytes2Seconds(self._decode_handle, total_bytes)
        if total_seconds <= 0:
            return (0.0, 0.0, 0.0)
        current_seconds = time_ms / 1000.0
        if current_seconds > total_seconds:
            current_seconds = total_seconds
        target_byte = int(self.bass.BASS_ChannelSeconds2Bytes(self._decode_handle, current_seconds))
        self.bass.BASS_ChannelSetPosition(self._decode_handle, target_byte, 0)
        fft = (ctypes.c_float * fft_size)()
        result = self.bass.BASS_ChannelGetData(self._decode_handle, ctypes.byref(fft), 0x20000000)
        if result <= 0:
            return (0.0, 0.0, 0.0)
        amp = [max(0.0, fft[i]) for i in range(fft_size // 2)]
        sample_rate = self.get_decode_sample_rate()
        freq_res = sample_rate / fft_size

        def idx(f):
            return int(f / freq_res)

        l_start, l_end = idx(20), idx(200)
        m_start, m_end = l_end, idx(4000)
        t_start, t_end = m_end, len(amp)

        def avg_amp(start, end):
            if start >= end:
                return 0.0
            return sum(amp[start:end]) / (end - start)

        scale = 0.3
        return (min(1.0, avg_amp(l_start, l_end) / scale),
                min(1.0, avg_amp(m_start, m_end) / scale),
                min(1.0, avg_amp(t_start, t_end) / scale))

    def free(self):
        self.stop()
        self.close_decode_stream()
        if self.bass:
            try:
                self.bass.BASS_Free()
            except Exception:
                pass


# ---------- 轉換引擎 ----------
class LibOpenMptEngine:
    @staticmethod
    def play_to_tempfile(filepath):
        try:
            fd, tmp = tempfile.mkstemp(suffix='.wav')
            os.close(fd)
            ffmpeg_path = resource_path("ffmpeg.exe")
            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = 'ffmpeg'
            cmd = [ffmpeg_path, '-y', '-i', filepath, '-f', 'wav', '-acodec', 'pcm_s16le',
                   '-ar', '44100', '-ac', '2', tmp]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            return tmp
        except Exception as e:
            log(f"[libopenmpt] FFmpeg 錯誤: {e}", 40)
            return None


class AsapEngine:
    @staticmethod
    def play_to_tempfile(filepath):
        try:
            fd, tmp = tempfile.mkstemp(suffix='.wav')
            os.close(fd)
            cmd = [resource_path("asapconv.exe"), '-o', tmp, filepath]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            return tmp
        except Exception as e:
            log(f"[ASAP] asapconv 錯誤: {e}", 40)
            return None


class ZxtuneEngine:
    @staticmethod
    def play_to_tempfile(filepath):
        try:
            fd, tmp = tempfile.mkstemp(suffix='.wav')
            os.close(fd)
            zx = resource_path("zxtune-cli.exe")
            if not os.path.exists(zx):
                zx = resource_path("zxtune123.exe")
                if not os.path.exists(zx):
                    raise FileNotFoundError("找不到 zxtune-cli.exe 或 zxtune123.exe")
            for cmd in ([zx, '-o', tmp, filepath],
                        [zx, '--wav', f'out={tmp}', filepath]):
                try:
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                    log(f"[ZXTune] 成功，參數: {cmd[1:]}", 20)
                    return tmp
                except subprocess.CalledProcessError:
                    continue
            log("[ZXTune] 所有變體皆失敗", 40)
            return None
        except Exception as e:
            log(f"[ZXTune] 錯誤: {e}", 40)
            return None


class ConversionThread(QThread):
    finished = pyqtSignal(str)

    def __init__(self, engine_type, filepath):
        super().__init__()
        self.engine_type = engine_type
        self.filepath = filepath

    def run(self):
        if self.isInterruptionRequested():
            return
        if self.engine_type == 'chiptune_cli':
            result = self.convert_with_furnace(self.filepath)
        elif self.engine_type == 'libopenmpt':
            result = LibOpenMptEngine.play_to_tempfile(self.filepath)
        elif self.engine_type == 'asap':
            result = AsapEngine.play_to_tempfile(self.filepath)
        elif self.engine_type == 'zxtune':
            result = ZxtuneEngine.play_to_tempfile(self.filepath)
        else:
            result = None
        if not self.isInterruptionRequested():
            self.finished.emit(result)

    def convert_with_furnace(self, filepath):
        try:
            fd, tmp = tempfile.mkstemp(suffix='.wav')
            os.close(fd)
            exe_path = resource_path("furnace.exe")
            cmd = [exe_path, "-noreport", "-output", tmp, filepath]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            log(f"[Furnace] 轉換成功: {filepath}", 20)
            return tmp
        except Exception as e:
            log(f"[Furnace] 錯誤: {e}", 40)
            return None


# ================== 資料檔案 ==================
SETTINGS_FILE = data_path("settings.dpst")
PLAYLIST_FILE = data_path("play_list.dppls")
HISTORY_FILE = data_path("play_history_counts.dpphc")
CACHE_FILE = data_path("cache.dpch")

OLD_CACHE_JSON = data_path("Cache.json")
OLD_CACHE_ALT = data_path("Cache_old2.json")

OLD_DATA_JSON = data_path("data.json")
OLD_DATA_JSON_ALT = data_path("data_old2.json")
OLD_DATA_TXT = data_path("data.txt")
OLD_DATA_TXT_ALT = data_path("data_old2.txt")
OLD_LIST_TXT = data_path("list.txt")
OLD_LIST_TXT_ALT = data_path("list_old2.txt")
OLD_LOVE_TXT = data_path("love.txt")
OLD_LOVE_TXT_ALT = data_path("love_old2.txt")

TIME_FORMAT_MM_SS = "mm_ss"
TIME_FORMAT_MM_SS_CC = "mm_ss_cc"

ENGINE_MODE_NORMAL = "normal"
ENGINE_MODE_VLC = "vlc"
ENGINE_MODE_BASS = "bass"

DEFAULT_SETTINGS = {
    "version": APP_VERSION,
    "theme_index": 0,
    "show_play_counts": True,
    "log_enabled": True,
    "log_level": 20,
    "show_duration": True,
    "audio_level_mode": "all",
    "show_cover_art": True,
    "show_audio_level": False,
    "audio_level_source": "file",
    "loop_mode": 0,
    "volume": 50,
    "window_mode": 0,
    "background_mode": "transparent",
    "always_on_top": False,
    "time_format": TIME_FORMAT_MM_SS_CC,
    "output_device": "",
    "vlc_device": "",
    "bass_device": "",
    "show_advanced_audio": False,
    "engine_mode": ENGINE_MODE_NORMAL,
}


def _safe_read_json(path):
    if not os.path.exists(path):
        return None
    for enc in ("utf-8-sig", "utf-8", "gbk", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                data = json.load(f)
            if enc != "utf-8-sig":
                log(f"[資料] 以 {enc} 讀取 {path}", 20)
            return data
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError as e:
            log(f"[資料] {path} 的 JSON 解析錯誤: {e}", 40)
            return None
        except Exception as e:
            log(f"[資料] 讀取 {path} 失敗: {e}", 40)
            return None
    log(f"[資料] 無法解碼 {path}", 40)
    return None


def _safe_write_json(path, payload):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        os.replace(tmp, path)
        return True
    except Exception as e:
        log(f"[資料] 寫入 {path} 失敗: {e}", 40)
        return False


def _rename_with_fallback(src, dst):
    if not os.path.exists(src):
        return False
    final = dst
    if os.path.exists(final):
        i = 2
        while os.path.exists(f"{dst}.{i}"):
            i += 1
        final = f"{dst}.{i}"
    try:
        os.rename(src, final)
        log(f"[移轉] 已重新命名 {src} -> {final}", 20)
        return True
    except Exception as e:
        log(f"[移轉] 重新命名 {src} 失敗: {e}", 30)
        return False


def load_settings():
    data = _safe_read_json(SETTINGS_FILE)
    if not isinstance(data, dict):
        return dict(DEFAULT_SETTINGS)
    for k, v in DEFAULT_SETTINGS.items():
        if k not in data:
            data[k] = v
    data["version"] = APP_VERSION
    return data


def save_settings(settings):
    settings = dict(settings)
    settings["version"] = APP_VERSION
    return _safe_write_json(SETTINGS_FILE, settings)


def load_playlist_data():
    data = _safe_read_json(PLAYLIST_FILE)
    if not isinstance(data, dict):
        return {"source_paths": [], "favorites": {}}

    source_paths = data.get("source_paths")
    if source_paths is None:
        source_paths = data.get("list", [])
        if source_paths:
            log("[資料] play_list 使用舊鍵 'list' -> 讀取為 source_paths", 20)

    favorites = data.get("favorites")
    if favorites is None:
        favorites = data.get("love_lists", {})
        if favorites:
            log("[資料] play_list 使用舊鍵 'love_lists' -> 讀取為 favorites", 20)

    return {
        "source_paths": source_paths or [],
        "favorites": favorites or {},
    }


def save_playlist_data(source_paths, favorites):
    return _safe_write_json(PLAYLIST_FILE, {
        "version": APP_VERSION,
        "source_paths": source_paths,
        "favorites": favorites,
    })


def load_history_data():
    data = _safe_read_json(HISTORY_FILE)
    if not isinstance(data, dict):
        return {"history": [], "play_counts": {}}
    return {
        "history": data.get("history", []) or [],
        "play_counts": data.get("play_counts", {}) or {},
    }


def save_history_data(history_paths, play_counts):
    return _safe_write_json(HISTORY_FILE, {
        "version": APP_VERSION,
        "history": history_paths[:100] if history_paths else [],
        "play_counts": play_counts if play_counts else {},
    })


def load_cache():
    data = _safe_read_json(CACHE_FILE)
    if isinstance(data, dict):
        return data

    for fallback in (OLD_CACHE_JSON, OLD_CACHE_ALT):
        data = _safe_read_json(fallback)
        if isinstance(data, dict):
            log(f"[移轉] 從 {fallback} 載入快取，寫入至 {CACHE_FILE}", 20)
            save_cache(data)
            if fallback == OLD_CACHE_JSON:
                _rename_with_fallback(OLD_CACHE_JSON, OLD_CACHE_ALT)
            return data
    return {}


def save_cache(cache_dict):
    return _safe_write_json(CACHE_FILE, cache_dict)


def _parse_old_data_txt_path(path):
    source_paths = []
    favorites = {}
    history_paths = []
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        log(f"[移轉] 無法讀取 {path}: {e}", 30)
        return source_paths, favorites, history_paths

    current_section = None
    current_items = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("list = ["):
            start = line.index("[") + 1
            end = line.index("]")
            source_paths = [p.strip() for p in line[start:end].split("|") if p.strip()]
            current_section = None
            continue
        m = re.match(r"love_list(\d{3}) = \[", line)
        if m:
            current_section = m.group(1)
            current_items = []
            if line.rstrip().endswith("]"):
                inner = line[line.index("[") + 1:line.rindex("]")]
                paths = [p.strip().rstrip("|") for p in inner.split("\n") if p.strip()]
                favorites[current_section] = [p for p in paths if p]
                current_section = None
            continue
        if line.startswith("history = ["):
            current_section = "history"
            current_items = []
            if line.rstrip().endswith("]"):
                inner = line[line.index("[") + 1:line.rindex("]")]
                paths = [p.strip().rstrip("|") for p in inner.split("\n") if p.strip()]
                history_paths = [p for p in paths if p]
                current_section = None
            continue
        if current_section:
            if line == "]":
                if current_section == "history":
                    history_paths = current_items
                else:
                    favorites[current_section] = current_items
                current_section = None
                current_items = []
            else:
                p = line.rstrip("|").strip()
                if p:
                    current_items.append(p)
    return source_paths, favorites, history_paths


def _parse_legacy_txt_paths(list_path, love_path):
    source_paths = []
    favorites = {}
    if list_path and os.path.exists(list_path):
        with open(list_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            for line in f:
                line = line.strip().rstrip(",").strip()
                if line:
                    source_paths.append(line)
    if love_path and os.path.exists(love_path):
        love_paths = []
        with open(love_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line:
                    love_paths.append(line)
        if love_paths:
            favorites["001"] = love_paths
    return source_paths, favorites, []


def migrate_old_files_if_needed():
    log(f"[移轉] app_dir = {app_dir()}", 20)
    log(f"[移轉] SETTINGS_FILE = {SETTINGS_FILE}", 20)
    log(f"[移轉] PLAYLIST_FILE = {PLAYLIST_FILE}", 20)
    log(f"[移轉] HISTORY_FILE  = {HISTORY_FILE}", 20)
    log(f"[移轉] CACHE_FILE    = {CACHE_FILE}", 20)

    new_settings_exists = os.path.exists(SETTINGS_FILE)
    new_playlist_exists = os.path.exists(PLAYLIST_FILE)
    new_history_exists = os.path.exists(HISTORY_FILE)
    all_new_exist = new_settings_exists and new_playlist_exists and new_history_exists

    if all_new_exist:
        log("[移轉] 主要資料檔案皆存在，無需移轉", 20)
        return load_settings()

    old_data = None
    for candidate in (OLD_DATA_JSON, OLD_DATA_JSON_ALT):
        if os.path.exists(candidate):
            d = _safe_read_json(candidate)
            if isinstance(d, dict):
                old_data = d
                log(f"[移轉] 已從 {candidate} 載入舊資料", 20)
                break
            else:
                log(f"[移轉] {candidate} 存在但非有效 JSON", 30)

    legacy_sources, legacy_favorites, legacy_hist = [], {}, []
    if old_data is None:
        for candidate in (OLD_DATA_TXT, OLD_DATA_TXT_ALT):
            if os.path.exists(candidate):
                legacy_sources, legacy_favorites, legacy_hist = _parse_old_data_txt_path(candidate)
                if legacy_sources or legacy_favorites or legacy_hist:
                    log(f"[移轉] 已從 {candidate} 載入舊資料", 20)
                    break
        if not legacy_sources and not legacy_favorites:
            list_src = None
            love_src = None
            for candidate in (OLD_LIST_TXT, OLD_LIST_TXT_ALT):
                if os.path.exists(candidate):
                    list_src = candidate
                    break
            for candidate in (OLD_LOVE_TXT, OLD_LOVE_TXT_ALT):
                if os.path.exists(candidate):
                    love_src = candidate
                    break
            if list_src or love_src:
                legacy_sources, legacy_favorites, legacy_hist = _parse_legacy_txt_paths(list_src, love_src)
                log(f"[移轉] 舊 txt: list={list_src}, love={love_src}", 20)

    if old_data:
        source_paths = old_data.get("list", []) or []
        favorites = old_data.get("love_lists", {}) or {}
        history_paths = old_data.get("history", []) or []
        play_counts = old_data.get("play_counts", {}) or {}
        settings = dict(DEFAULT_SETTINGS)
        for key in ("theme_index", "show_play_counts", "log_enabled",
                    "show_duration", "audio_level_mode", "show_cover_art",
                    "audio_level_source", "loop_mode", "volume",
                    "window_mode", "background_mode", "always_on_top",
                    "show_audio_level", "log_level", "time_format",
                    "output_device", "vlc_device", "bass_device",
                    "show_advanced_audio", "engine_mode"):
            if key in old_data:
                settings[key] = old_data[key]
    else:
        source_paths = legacy_sources
        favorites = legacy_favorites
        history_paths = legacy_hist
        play_counts = {}
        settings = dict(DEFAULT_SETTINGS)

    log(f"[移轉] 來源 -> source_paths={len(source_paths)}, favorites={len(favorites)}, "
        f"history={len(history_paths)}, play_counts={len(play_counts)}", 20)

    migrated_any = False
    if not new_settings_exists:
        if save_settings(settings):
            log(f"[移轉] 已寫入 {SETTINGS_FILE}", 20)
            migrated_any = True
    if not new_playlist_exists:
        if save_playlist_data(source_paths, favorites):
            log(f"[移轉] 已寫入 {PLAYLIST_FILE}", 20)
            migrated_any = True
    if not new_history_exists:
        if save_history_data(history_paths, play_counts):
            log(f"[移轉] 已寫入 {HISTORY_FILE}", 20)
            migrated_any = True

    if migrated_any:
        for old_name in (OLD_DATA_JSON, OLD_DATA_TXT, OLD_LIST_TXT, OLD_LOVE_TXT):
            if os.path.exists(old_name):
                if old_name.endswith(".json"):
                    new_name = old_name.replace(".json", "_old2.json")
                else:
                    new_name = old_name.replace(".txt", "_old2.txt")
                _rename_with_fallback(old_name, new_name)
    else:
        log("[移轉] 未寫入任何新檔案，舊檔案保留原處", 20)

    return settings


# ================== M3U ==================
def parse_m3u(m3u_path):
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
                if line.lower().startswith("http://") or line.lower().startswith("https://"):
                    items.append(line)
                else:
                    full = line if os.path.isabs(line) else os.path.join(base_dir, line)
                    if os.path.isfile(full):
                        items.append(full)
    except Exception as e:
        log(f"[M3U] {m3u_path}: {e}", 30)
    return items


# ================== CUE ==================
def parse_cue_file(cue_path):
    tracks = []
    current = None
    cue_dir = os.path.dirname(os.path.abspath(cue_path))
    current_audio_file = None
    try:
        with open(cue_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        log(f"[CUE] 無法讀取 {cue_path}: {e}", 40)
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
            m = re.match(r'TRACK\s+(\d+)\s+(\S+)', line, re.IGNORECASE)
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
            m = re.match(r'INDEX\s+(\d+)\s+(\d+):(\d+):(\d+)', line, re.IGNORECASE)
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


# ================== 關於對話框 ==================
class AboutDialog(QDialog):
    KONAMI = [
        Qt.Key.Key_Up, Qt.Key.Key_Up,
        Qt.Key.Key_Down, Qt.Key.Key_Down,
        Qt.Key.Key_Left, Qt.Key.Key_Right,
        Qt.Key.Key_Left, Qt.Key.Key_Right,
        Qt.Key.Key_B, Qt.Key.Key_A,
    ]

    def __init__(self, parent, info_text, accent_color="#FFFFFF", font=None):
        super().__init__(parent)
        self.setWindowTitle(f"關於 dem_player {APP_VERSION}")
        self.setMinimumSize(560, 420)
        self.accent_color = accent_color
        self.ball_label = None
        self.ball_timer = None
        self.ball_x = 0
        self.ball_y = 0
        self.ball_vx = 3
        self.ball_vy = 3
        self.konami_progress = 0
        self.ball_active = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText(info_text)
        if font is not None:
            self.text.setFont(font)
        self.text.setStyleSheet(
            f"QTextEdit {{ background-color: #000000; color: {accent_color}; "
            f"border: 1px solid {accent_color}; }}"
        )
        self.text.installEventFilter(self)
        layout.addWidget(self.text, 1)

        btns = QDialogButtonBox()
        self.copy_btn = btns.addButton("複製資訊", QDialogButtonBox.ButtonRole.ActionRole)
        self.close_btn = btns.addButton("關閉", QDialogButtonBox.ButtonRole.AcceptRole)
        self.copy_btn.clicked.connect(self.copy_info)
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(btns)

    def copy_info(self):
        QGuiApplication.clipboard().setText(self.text.toPlainText())

    def eventFilter(self, obj, event):
        if obj is self.text and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right,
                       Qt.Key.Key_B, Qt.Key.Key_A):
                expected = self.KONAMI[self.konami_progress]
                if key == expected:
                    self.konami_progress += 1
                    if self.konami_progress >= len(self.KONAMI):
                        self.konami_progress = 0
                        self.start_ball()
                        return True
                    if self.konami_progress > 1:
                        return True
                else:
                    if key == self.KONAMI[0]:
                        self.konami_progress = 1
                        return True
                    else:
                        self.konami_progress = 0
        return super().eventFilter(obj, event)

    def start_ball(self):
        if self.ball_active:
            return
        self.ball_active = True
        vp = self.text.viewport()
        self.ball_label = QLabel("█", vp)
        self.ball_label.setFont(self.text.font())
        self.ball_label.setStyleSheet(
            f"color: {self.accent_color}; background: transparent; border: none;"
        )
        self.ball_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.ball_label.adjustSize()
        self.ball_x = 10
        self.ball_y = 10
        self.ball_vx = 3
        self.ball_vy = 3
        self.ball_label.move(self.ball_x, self.ball_y)
        self.ball_label.show()
        self.ball_timer = QTimer(self)
        self.ball_timer.setInterval(66)
        self.ball_timer.timeout.connect(self._tick_ball)
        self.ball_timer.start()

    def _tick_ball(self):
        if not self.ball_active or self.ball_label is None:
            return
        vp = self.text.viewport()
        w = vp.width()
        h = vp.height()
        bw = self.ball_label.width()
        bh = self.ball_label.height()
        if w <= bw or h <= bh:
            return
        self.ball_x += self.ball_vx
        self.ball_y += self.ball_vy
        if self.ball_x <= 0:
            self.ball_x = 0
            self.ball_vx = abs(self.ball_vx)
        elif self.ball_x >= w - bw:
            self.ball_x = w - bw
            self.ball_vx = -abs(self.ball_vx)
        if self.ball_y <= 0:
            self.ball_y = 0
            self.ball_vy = abs(self.ball_vy)
        elif self.ball_y >= h - bh:
            self.ball_y = h - bh
            self.ball_vy = -abs(self.ball_vy)
        self.ball_label.move(self.ball_x, self.ball_y)
        self._update_invert()

    def _update_invert(self):
        try:
            cx = self.ball_x + self.ball_label.width() // 2
            cy = self.ball_y + self.ball_label.height() // 2
            cursor = self.text.cursorForPosition(QPoint(cx, cy))
            if cursor is None:
                return
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
            fmt = QTextCharFormat()
            bg = QColor(self.accent_color)
            fmt.setForeground(QColor("#000000"))
            fmt.setBackground(bg)
            sel.format = fmt
            self.text.setExtraSelections([sel])
        except Exception:
            pass

    def stop_ball(self):
        if self.ball_timer is not None:
            try:
                self.ball_timer.stop()
            except Exception:
                pass
            self.ball_timer = None
        if self.ball_label is not None:
            try:
                self.ball_label.hide()
                self.ball_label.deleteLater()
            except Exception:
                pass
            self.ball_label = None
        self.ball_active = False
        try:
            self.text.setExtraSelections([])
        except Exception:
            pass

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.stop_ball()
            self.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.stop_ball()
        super().closeEvent(event)


# ================== 裝置選擇對話框 ==================
class DevicePickerDialog(QDialog):
    def __init__(self, parent, title, items, accent_color="#FFFFFF", font=None, current_id=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(480, 360)
        self.selected_id = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.list = QListWidget()
        if font is not None:
            self.list.setFont(font)
        self.list.setStyleSheet(
            f"QListWidget {{ background-color: #000000; color: {accent_color}; "
            f"border: 1px solid {accent_color}; }}"
        )

        default_item = QListWidgetItem("系統預設")
        default_item.setData(Qt.ItemDataRole.UserRole, "")
        self.list.addItem(default_item)

        selected_row = 0
        for i, (did, name) in enumerate(items, start=1):
            it = QListWidgetItem(f"{name}")
            it.setData(Qt.ItemDataRole.UserRole, did)
            self.list.addItem(it)
            if current_id is not None and str(did) == str(current_id):
                selected_row = i
        self.list.setCurrentRow(selected_row)
        layout.addWidget(self.list, 1)

        btns = QDialogButtonBox()
        ok_btn = btns.addButton("套用", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = btns.addButton("取消", QDialogButtonBox.ButtonRole.RejectRole)
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btns)

    def _on_ok(self):
        it = self.list.currentItem()
        if it is None:
            self.reject()
            return
        self.selected_id = it.data(Qt.ItemDataRole.UserRole)
        self.accept()


# ================== VLC ==================
_vlc_instance = None


# ================== 主視窗 ==================
class MusicRoom(QMainWindow):
    THEMES = [
        ("黑與白",      "#000000", "#FFFFFF"),
        ("黑與綠",      "#000000", "#00FF00"),
        ("黑與紅",      "#000000", "#FF0000"),
        ("黑與橘",      "#000000", "#FFA500"),
        ("黑與藍",      "#000000", "#0084ff"),
        ("黑與紫",      "#000000", "#d000ff"),
        ("黑與青",      "#000000", "#00FFFF"),
        ("黑與黃",      "#000000", "#FFFF00"),
        ("黑與洋紅",    "#000000", "#FF00FF"),
        ("神秘紫與霓虹粉",  "#6a0dad", "#ff0080"),
        ("霓虹粉與神秘紫",  "#ff0080", "#6a0dad"),
        ("鋼影與霓虹青",    "#2c2c34", "#00d4ff"),
        ("霓虹青與鋼影",    "#00d4ff", "#2c2c34"),
        ("萊姆閃與碳黑",    "#bfff00", "#222222"),
        ("皇室紫與黃金",    "#7b2cbf", "#f9d308"),
        ("黃金與皇室紫",    "#f9d308", "#7b2cbf"),
    ]

    LEVEL_SUPPORTED_EXT = ('.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac', '.wma', '.opus', '.alac')

    def __init__(self):
        super().__init__()
        global _vlc_instance

        log(f"MusicRoom __init__ 開始 (v{APP_VERSION})", 20)

        self.setWindowTitle(f"dem_player {APP_VERSION}")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.has_custom_border = True
        self.drag_position = QPoint()
        self.setFixedSize(900, 600)

        # 拖曳外框狀態
        self.drag_frame = None
        self._drag_press_pos = QPoint()
        self._drag_offset = QPoint()
        self._drag_started = False

        icon_path = resource_path("FPT.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        custom_font_family = load_custom_font()
        if custom_font_family:
            self.dos_font = QFont(custom_font_family, 10)
            self.dos_font.setBold(True)
        else:
            self.dos_font = QFont("Courier New", 10)
            self.dos_font.setBold(True)

        settings = migrate_old_files_if_needed()
        playlist_data = load_playlist_data()
        history_data = load_history_data()

        self.source_paths = playlist_data["source_paths"]
        self.favorites = playlist_data["favorites"]
        self.history_paths = history_data["history"]
        self.play_counts = history_data["play_counts"]

        self.current_theme_index = settings.get("theme_index", 0)
        self.show_play_counts = settings.get("show_play_counts", True)
        log_enabled = settings.get("log_enabled", True)
        self.show_duration = settings.get("show_duration", True)
        self.audio_level_mode = settings.get("audio_level_mode", "all")
        self.show_cover_art = settings.get("show_cover_art", True)
        self.show_audio_level = settings.get("show_audio_level", False)
        self.audio_level_source = settings.get("audio_level_source", "file")
        self.loop_mode = settings.get("loop_mode", 0)
        self.initial_volume = settings.get("volume", 50)
        self.window_mode = settings.get("window_mode", 0)
        self.background_mode = settings.get("background_mode", "transparent")
        self.is_always_on_top = settings.get("always_on_top", False)
        self.time_format = settings.get("time_format", TIME_FORMAT_MM_SS_CC)
        if self.time_format not in (TIME_FORMAT_MM_SS, TIME_FORMAT_MM_SS_CC):
            self.time_format = TIME_FORMAT_MM_SS_CC

        self.output_device = settings.get("output_device", "") or ""
        self.vlc_device = settings.get("vlc_device", "") or ""
        self.bass_device = settings.get("bass_device", "") or ""
        self.show_advanced_audio = bool(settings.get("show_advanced_audio", False))
        self.engine_mode = settings.get("engine_mode", ENGINE_MODE_NORMAL)
        if self.engine_mode not in (ENGINE_MODE_NORMAL, ENGINE_MODE_VLC, ENGINE_MODE_BASS):
            self.engine_mode = ENGINE_MODE_NORMAL

        global LOG_ENABLED, LOG_LEVEL
        LOG_ENABLED = bool(log_enabled)
        LOG_LEVEL = settings.get("log_level", 20)
        if LOG_ENABLED and LOG_FILE is None:
            init_log()

        log(f"設定: theme={self.current_theme_index}, loop={self.loop_mode}, "
            f"vol={self.initial_volume}, time_format={self.time_format}, "
            f"engine_mode={self.engine_mode}, "
            f"output_device='{self.output_device}', vlc_device='{self.vlc_device}', "
            f"bass_device='{self.bass_device}'", 20)
        log(f"來源: {len(self.source_paths)} 個路徑, 我的最愛: {len(self.favorites)} 個清單", 20)
        log(f"歷史: {len(self.history_paths)} 筆, {len(self.play_counts)} 筆播放次數", 20)

        if self.current_theme_index < 0 or self.current_theme_index >= len(self.THEMES):
            self.current_theme_index = 0
        self.bg_color = self.THEMES[self.current_theme_index][1]
        self.accent_color = self.THEMES[self.current_theme_index][2]

        if self.is_always_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        # VLC
        self.vlc_ok = False
        try:
            if _vlc_instance is None:
                _vlc_instance = vlc.Instance()
            self.vlc_instance = _vlc_instance
            self.vlc_player = self.vlc_instance.media_player_new()
            self.vlc_ok = True
            log("VLC 已初始化", 20)
        except Exception as e:
            log(f"VLC 初始化失敗: {e}", 40)
            self.vlc_instance = None
            self.vlc_player = None

        if self.vlc_player is not None:
            self.vlc_player.audio_set_volume(self.initial_volume)

        if not self.vlc_device and self.output_device:
            self.vlc_device = self.output_device
        if self.vlc_device and self.vlc_player is not None:
            if vlc_set_audio_device(self.vlc_player, self.vlc_device):
                log(f"[音訊] VLC 使用裝置 '{self.vlc_device}'", 20)
            else:
                log(f"[音訊] VLC 裝置 '{self.vlc_device}' 失敗，退回預設", 30)
                self.vlc_device = ""

        # BASS
        bass_target_id = self.bass_device or self.output_device
        bass_index = self._resolve_bass_index_from_id(bass_target_id)
        try:
            self.bass_engine = BassEngine(device_index=bass_index)
            self.bass_engine._end_callback = self.on_media_end
            self.bass_available = self.bass_engine.is_available()
            if self.bass_available:
                self.bass_device = bass_target_id
                log(f"[音訊] BASS 使用裝置索引 {bass_index}", 20)
            else:
                log("[音訊] BASS 無法使用", 30)
        except Exception as e:
            log(f"BASS 建立失敗: {e}", 40)
            self.bass_available = False

        # 選用引擎
        self.libopenmpt_available = False
        try:
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            self.libopenmpt_available = True
        except Exception:
            pass

        self.asap_available = False
        try:
            subprocess.run([resource_path("asapconv.exe"), '--help'], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            self.asap_available = True
        except Exception:
            pass

        self.zxtune_available = False
        try:
            zx_exe = resource_path("zxtune-cli.exe")
            if not os.path.exists(zx_exe):
                zx_exe = resource_path("zxtune123.exe")
            subprocess.run([zx_exe, '--help'], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            self.zxtune_available = True
        except Exception:
            pass

        self.furnace_available = False
        try:
            subprocess.run([resource_path("furnace.exe"), "--help"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            self.furnace_available = True
        except Exception:
            pass

        self.bg_pixmap = None

        self.folder_cache = load_cache()
        self._cache_dirty = False
        self._save_cache_timer = QTimer(self)
        self._save_cache_timer.setSingleShot(True)
        self._save_cache_timer.timeout.connect(self._write_cache)

        self.current_dir = None
        self.current_playlist = []
        self.current_track_index = -1
        self._pending_folder_list = []
        self.current_file_path = None
        self.current_track_info = None
        self.current_engine = 'vlc'
        self.temp_wav = None
        self.conv_thread = None
        self.spectrum_source_path = None

        self.convert_cache = OrderedDict()
        self.cache_max_size = 10

        self.loop_mode_names = ["關閉", "單曲", "清單"]

        self.show_settings = False
        self.left_visible = True

        self.sd_stream = None
        self._system_audio_data = None

        self._smooth_bass = 0.0
        self._smooth_mid = 0.0
        self._smooth_treble = 0.0
        self._smooth_volume = 0.0

        self._cue_end_timer = QTimer(self)
        self._cue_end_timer.setInterval(200)
        self._cue_end_timer.timeout.connect(self._check_cue_end)
        self._cue_end_ms = None

        try:
            self.build_ui()
        except Exception as e:
            log(f"build_ui 崩潰: {e}\n{traceback.format_exc()}", 40)

        try:
            self.apply_theme()
        except Exception as e:
            log(f"apply_theme 失敗: {e}", 40)

        self.audio_level_frame.setVisible(self.show_audio_level)
        self.text_eq.fix_widths(self.dos_font)
        self.text_eq.set_mode(self.audio_level_mode)
        self.cover_label.setVisible(False)
        self.loop_label.setText(f"循環: {self.loop_mode_names[self.loop_mode]}")

        self.setMouseTracking(True)
        self.file_list.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.settings_list.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.search_input.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.progress_text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.volume_text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        for lbl in self.findChildren(QLabel):
            if lbl not in (self.min_btn, self.close_btn):
                lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.volume_text.setValue(self.initial_volume)
        self.update_volume_to_actual()

        # 系統匣
        self.tray_icon = QSystemTrayIcon(self)
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.tray_icon.setToolTip(f"dem_player {APP_VERSION}")
        self.tray_menu = QMenu()
        self.tray_pause_action = QAction("停止")
        self.tray_pause_action.triggered.connect(self.toggle_pause)
        self.tray_prev_action = QAction("上一首")
        self.tray_prev_action.triggered.connect(self._tray_prev)
        self.tray_next_action = QAction("下一首")
        self.tray_next_action.triggered.connect(self.play_next_in_list)
        self.tray_quit_action = QAction("結束")
        self.tray_quit_action.triggered.connect(self.close)
        self.tray_menu.addAction(self.tray_pause_action)
        self.tray_menu.addAction(self.tray_prev_action)
        self.tray_menu.addAction(self.tray_next_action)
        self.tray_menu.addAction(self.tray_quit_action)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(lambda reason: None)
        self.tray_icon.show()

        try:
            self.show_source_list()
        except Exception as e:
            log(f"show_source_list 失敗: {e}", 40)

        try:
            self.set_normal_mode()
        except Exception as e:
            log(f"set_normal_mode 失敗: {e}", 40)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(250)

        self.spectrum_timer = QTimer(self)
        self.spectrum_timer.timeout.connect(self.update_spectrum_bars)
        self.spectrum_timer.start(50)

        if self.vlc_player is not None:
            try:
                self.vlc_player.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached, self.on_vlc_end)
            except Exception:
                pass

        if self.audio_level_source == "system":
            self.start_system_audio_capture()

        log("=== 播放器初始化成功 ===", 20)

    # ================== 音訊裝置輔助 ==================
    def _resolve_bass_index_from_id(self, device_id):
        if not device_id:
            return -1
        devices = bass_list_devices()
        needle = self._normalize_device_name(device_id)
        for idx, name in devices:
            if self._normalize_device_name(name) == needle:
                return idx
        for idx, name in devices:
            n = self._normalize_device_name(name)
            if needle and (needle in n or n in needle):
                return idx
        return -1

    @staticmethod
    def _normalize_device_name(s):
        if not s:
            return ""
        s = s.lower()
        s = re.sub(r"\(.*?\)", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _get_vlc_device_list(self):
        if self.vlc_instance is None:
            return []
        try:
            inst_ptr = getattr(self.vlc_instance, "_instance", None)
            if inst_ptr is None:
                return []
            val = inst_ptr.value if hasattr(inst_ptr, "value") else int(inst_ptr)
            for aout in (b"mmdevice", b"directsound", None):
                res = vlc_list_audio_devices(val, aout=aout)
                if res:
                    return res
            return []
        except Exception as e:
            log(f"[VLC] 裝置清單取得失敗: {e}", 30)
            return []

    def _get_bass_device_list(self):
        devices = bass_list_devices()
        return [(idx, name) for idx, name in devices]

    def _main_output_device_label(self):
        if not self.vlc_device and not self.bass_device:
            return "系統預設"
        if self.vlc_device == self.bass_device:
            for did, desc in self._get_vlc_device_list():
                if did == self.vlc_device:
                    return desc or self.vlc_device
            return self.vlc_device or "系統預設"
        return "混合"

    def _vlc_device_label(self):
        if not self.vlc_device:
            return "系統預設"
        for did, desc in self._get_vlc_device_list():
            if did == self.vlc_device:
                return desc or self.vlc_device
        return self.vlc_device

    def _bass_device_label(self):
        if not self.bass_device:
            return "系統預設"
        return self.bass_device

    def _switch_output_device(self, vlc_id, bass_id):
        log(f"[音訊] 切換請求: vlc='{vlc_id}', bass='{bass_id}'", 20)
        resume_track = self.current_track_info
        was_playing = False
        try:
            if self.current_engine == 'bass':
                was_playing = self.bass_engine.is_playing()
            elif self.vlc_player is not None:
                was_playing = self.vlc_player.is_playing()
        except Exception:
            was_playing = False

        try:
            self.stop_current_engine()
        except Exception:
            pass
        prevent_sleep(False)

        # 重建 VLC
        try:
            if self.vlc_player is not None:
                try:
                    self.vlc_player.stop()
                except Exception:
                    pass
                try:
                    self.vlc_player.release()
                except Exception:
                    pass
            if self.vlc_instance is None:
                self.vlc_instance = vlc.Instance()
            self.vlc_player = self.vlc_instance.media_player_new()
            self.vlc_player.audio_set_volume(self.volume_text.value())
            try:
                self.vlc_player.event_manager().event_attach(
                    vlc.EventType.MediaPlayerEndReached, self.on_vlc_end)
            except Exception:
                pass
            self.vlc_ok = True
            if vlc_id:
                ok = vlc_set_audio_device(self.vlc_player, vlc_id)
                if not ok:
                    log(f"[音訊] VLC 無法設定裝置 '{vlc_id}'，使用預設", 30)
                    vlc_id = ""
            log(f"[音訊] VLC 播放器已重建，device='{vlc_id}'", 20)
        except Exception as e:
            log(f"[音訊] VLC 重建失敗: {e}", 40)
            self.vlc_ok = False
            vlc_id = ""

        # 重建 BASS
        try:
            try:
                self.bass_engine.free()
            except Exception:
                pass
            bass_index = self._resolve_bass_index_from_id(bass_id) if bass_id else -1
            self.bass_engine = BassEngine(device_index=bass_index)
            self.bass_engine._end_callback = self.on_media_end
            self.bass_available = self.bass_engine.is_available()
            if not self.bass_available:
                log("[音訊] BASS 重建後無法使用", 30)
            else:
                log(f"[音訊] BASS 已重建，裝置索引={bass_index}", 20)
        except Exception as e:
            log(f"[音訊] BASS 重建失敗: {e}", 40)
            self.bass_available = False

        self.vlc_device = vlc_id or ""
        self.bass_device = bass_id or ""
        if self.vlc_device and self.vlc_device == self.bass_device:
            self.output_device = self.vlc_device
        else:
            self.output_device = ""
        self._save_settings()
        self.update_settings_list()

        if resume_track is not None:
            if was_playing:
                QTimer.singleShot(500, lambda t=resume_track: self.play_file(t))
                self.track_status.setText("正在切換音訊裝置...")
            else:
                self.track_status.setText("已變更音訊裝置")
        else:
            self.track_status.setText("已變更音訊裝置")

    def pick_main_device(self):
        devices = self._get_vlc_device_list()
        dlg = DevicePickerDialog(self, "輸出裝置 (VLC + BASS)", devices,
                                 self.accent_color, self.dos_font, current_id=self.vlc_device)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_id = dlg.selected_id or ""
            self._switch_output_device(new_id, new_id)

    def pick_vlc_device(self):
        devices = self._get_vlc_device_list()
        dlg = DevicePickerDialog(self, "VLC 裝置", devices,
                                 self.accent_color, self.dos_font, current_id=self.vlc_device)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_id = dlg.selected_id or ""
            self._switch_output_device(new_id, self.bass_device)

    def pick_bass_device(self):
        devices = self._get_bass_device_list()
        items = [(name, name) for idx, name in devices]
        dlg = DevicePickerDialog(self, "BASS 裝置", items,
                                 self.accent_color, self.dos_font, current_id=self.bass_device)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_name = dlg.selected_id or ""
            self._switch_output_device(self.vlc_device, new_name)

    # ================== 持久化 ==================
    def _current_settings_dict(self):
        global LOG_ENABLED, LOG_LEVEL
        return {
            "theme_index": self.current_theme_index,
            "show_play_counts": self.show_play_counts,
            "log_enabled": LOG_ENABLED,
            "log_level": LOG_LEVEL,
            "show_duration": self.show_duration,
            "audio_level_mode": self.audio_level_mode,
            "show_cover_art": self.show_cover_art,
            "show_audio_level": self.show_audio_level,
            "audio_level_source": self.audio_level_source,
            "loop_mode": self.loop_mode,
            "volume": self.volume_text.value() if hasattr(self, "volume_text") else self.initial_volume,
            "window_mode": self.window_mode,
            "background_mode": self.background_mode,
            "always_on_top": self.is_always_on_top,
            "time_format": self.time_format,
            "output_device": getattr(self, "output_device", ""),
            "vlc_device": getattr(self, "vlc_device", ""),
            "bass_device": getattr(self, "bass_device", ""),
            "show_advanced_audio": getattr(self, "show_advanced_audio", False),
            "engine_mode": getattr(self, "engine_mode", ENGINE_MODE_NORMAL),
        }

    def _save_settings(self):
        save_settings(self._current_settings_dict())

    def _save_playlist(self):
        save_playlist_data(self.source_paths, self.favorites)

    def _save_history(self):
        save_history_data(self.history_paths, self.play_counts)

    def _save_all_data(self):
        self._save_settings()
        self._save_playlist()
        self._save_history()

    # ================== 快取 ==================
    def _mark_cache_dirty(self):
        self._cache_dirty = True
        if not self._save_cache_timer.isActive():
            self._save_cache_timer.start(5000)

    def _write_cache(self):
        if self._cache_dirty:
            save_cache(self.folder_cache)
            self._cache_dirty = False

    def _tray_prev(self):
        if self.current_playlist and self.current_track_index > 0:
            self.current_track_index -= 1
            self.play_file(self.current_playlist[self.current_track_index])

    def minimize_to_tray(self):
        self.showMinimized()

    def update_volume_to_actual(self):
        vol = self.volume_text.value()
        if self.vlc_player is not None:
            self.vlc_player.audio_set_volume(vol)
        if hasattr(self, 'bass_engine') and self.bass_available and self.current_engine == 'bass':
            self.bass_engine.set_volume(vol)

    def mousePressEvent(self, event):
        if event.position().y() < 40 and event.button() == Qt.MouseButton.LeftButton:
            self._drag_press_pos = event.globalPosition().toPoint()
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._drag_started = False
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 拖曳中
        if self._drag_started and (event.buttons() & Qt.MouseButton.LeftButton):
            new_tl = event.globalPosition().toPoint() - self._drag_offset
            if self.drag_frame is not None:
                self.drag_frame.move(new_tl)
            event.accept()
            return

        if (event.buttons() & Qt.MouseButton.LeftButton) and event.position().y() < 40:
            delta = event.globalPosition().toPoint() - self._drag_press_pos
            if abs(delta.x()) > 3 or abs(delta.y()) > 3:
                self._drag_started = True
                if self.drag_frame is None:
                    self.drag_frame = DragFrame(self.accent_color)
                self.drag_frame.set_accent_color(self.accent_color)
                self.drag_frame.setGeometry(self.frameGeometry())
                self.drag_frame.show()
                new_tl = event.globalPosition().toPoint() - self._drag_offset
                self.drag_frame.move(new_tl)
                event.accept()
                return

        if event.position().y() < 40:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.BlankCursor)

    def mouseReleaseEvent(self, event):
        if self._drag_started and self.drag_frame is not None:
            target = self.drag_frame.pos()
            self.drag_frame.hide()
            self.move(target)
            self._drag_started = False
            event.accept()
            return
        self._drag_started = False
        super().mouseReleaseEvent(event)

    # ================== 介面 ==================
    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setObjectName("MainPlayerFrame")

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self.left_frame = QFrame()
        left_layout = QVBoxLayout(self.left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.left_stack = QStackedWidget()
        self.left_stack.setFont(self.dos_font)
        self.left_stack.setStyleSheet("background: transparent;")

        self.file_page = QWidget()
        file_layout = QVBoxLayout(self.file_page)
        file_layout.setContentsMargins(2, 2, 2, 2)
        file_layout.setSpacing(2)
        self.browser_label = QLabel("檔案瀏覽")
        self.browser_label.setFont(self.dos_font)
        file_layout.addWidget(self.browser_label)
        self.file_list = QListWidget()
        self.file_list.setFont(self.dos_font)
        self.file_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.file_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        file_layout.addWidget(self.file_list)
        self.path_label = QLabel("-")
        self.path_label.setFont(self.dos_font)
        self.path_label.setStyleSheet("border: none; padding: 2px;")
        file_layout.addWidget(self.path_label)
        self.file_page.setStyleSheet("background: transparent;")
        self.left_stack.addWidget(self.file_page)

        self.settings_page = QWidget()
        settings_layout = QVBoxLayout(self.settings_page)
        settings_layout.setContentsMargins(4, 8, 4, 8)
        settings_layout.setSpacing(6)
        title_label = QLabel("設定")
        title_label.setFont(self.dos_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_layout.addWidget(title_label)
        self.settings_list = QListWidget()
        self.settings_list.setFont(self.dos_font)
        self.settings_list.itemActivated.connect(self.on_setting_selected)
        settings_layout.addWidget(self.settings_list)
        self.settings_page.setStyleSheet("background: transparent;")
        self.left_stack.addWidget(self.settings_page)

        left_layout.addWidget(self.left_stack)
        main_layout.addWidget(self.left_frame, 2)

        right_outer_layout = QVBoxLayout()
        right_outer_layout.setContentsMargins(0, 0, 0, 0)
        right_outer_layout.setSpacing(0)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.min_btn = QPushButton("-")
        self.close_btn = QPushButton("X")
        for btn in (self.min_btn, self.close_btn):
            btn.setFixedSize(24, 24)
            btn.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
            btn.setStyleSheet(f"color: {self.accent_color}; background: transparent; border: 1px solid {self.accent_color};")
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.min_btn.clicked.connect(self.minimize_to_tray)
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.min_btn)
        btn_layout.addWidget(self.close_btn)
        right_outer_layout.addLayout(btn_layout)

        self.right_frame = QFrame()
        self.right_frame.setObjectName("RightPanel")
        right_layout = QVBoxLayout(self.right_frame)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(5)

        track_title_row = QHBoxLayout()
        track_label = QLabel("曲目:")
        track_label.setFont(self.dos_font)
        track_title_row.addWidget(track_label)
        self.track_title = ScrollingLabel("------------------------")
        self.track_title.setFont(self.dos_font)
        self.track_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        track_title_row.addWidget(self.track_title, 1)
        right_layout.addLayout(track_title_row)

        self.meta_label = QLabel("演出者: -   專輯: -   曲目#: -")
        self.meta_label.setFont(self.dos_font)
        right_layout.addWidget(self.meta_label)

        self.progress_text = TextBar(max_val=1000, bar_length=30, show_percent=False)
        self.progress_text.setFont(self.dos_font)
        right_layout.addWidget(self.progress_text)

        self.status_frame = QFrame()
        status_loop_layout = QHBoxLayout(self.status_frame)
        status_loop_layout.setContentsMargins(4, 2, 4, 2)
        self.track_status = QLabel("已停止")
        self.track_status.setFont(self.dos_font)
        status_loop_layout.addWidget(self.track_status)
        status_loop_layout.addStretch()
        self.loop_label = QLabel("循環: 關閉")
        self.loop_label.setFont(self.dos_font)
        status_loop_layout.addWidget(self.loop_label)
        right_layout.addWidget(self.status_frame)

        self.volume_text = TextBar(max_val=100, bar_length=20, show_percent=True)
        self.volume_text.prefix = "音量 (F2/F3)"
        self.volume_text.setFont(self.dos_font)
        right_layout.addWidget(self.volume_text)

        self.audio_level_frame = QFrame()
        audio_level_layout = QVBoxLayout(self.audio_level_frame)
        audio_level_layout.setContentsMargins(0, 0, 0, 0)
        self.audio_level_title = QLabel("音訊電平:")
        self.audio_level_title.setFont(self.dos_font)
        audio_level_layout.addWidget(self.audio_level_title)
        self.text_eq = TextEQWidget(self, accent_color=self.accent_color)
        audio_level_layout.addWidget(self.text_eq)
        right_layout.addWidget(self.audio_level_frame)

        self.keys_label = QLabel(
            "按鍵:\n"
            "[↑/↓] 瀏覽  [ENTER] 開啟  [BS] 返回\n"
            "[F1] 暫停  [F2/F3] 音量  [F4] 隱藏\n"
            "[F5] 循環  [F6] 模式  [F7] 設定\n"
            "[F8] 搜尋  [F9] 最愛  [Esc] 重設  [←/→] -/+1秒"
        )
        self.keys_label.setFont(self.dos_font)
        self.keys_label.setWordWrap(False)
        right_layout.addWidget(self.keys_label)

        self.search_frame = QFrame()
        search_layout = QHBoxLayout(self.search_frame)
        search_layout.setContentsMargins(4, 4, 4, 4)
        search_label = QLabel("搜尋:")
        search_label.setFont(self.dos_font)
        self.search_input = QLineEdit()
        self.search_input.setFont(self.dos_font)
        self.search_input.setPlaceholderText("...")
        self.search_input.returnPressed.connect(self.do_search)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        right_layout.addWidget(self.search_frame)

        self.mini_keys_label = QLabel("[F6] 模式  [F7] 設定  [F8] 搜尋  [F9] 最愛  [Esc] 重設")
        self.mini_keys_label.setFont(self.dos_font)
        self.mini_keys_label.setVisible(False)
        right_layout.addWidget(self.mini_keys_label)

        self.cover_label = QLabel()
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setMinimumHeight(120)
        self.cover_label.setMaximumHeight(180)
        self.cover_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.cover_label.setStyleSheet("background-color: transparent; border: none;")
        self.cover_label.setScaledContents(True)
        right_layout.addWidget(self.cover_label)

        self.right_stretch_item = right_layout.addStretch()
        right_outer_layout.addWidget(self.right_frame)
        main_layout.addLayout(right_outer_layout, 1)

        self.left_stack.setCurrentIndex(0)
        self.apply_background_image()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.background_mode == "image" and self.bg_pixmap and not self.bg_pixmap.isNull():
            scaled = self.bg_pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(0, 0, scaled)
            painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        if self.has_custom_border:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(QColor(self.accent_color), 2)
            painter.setPen(pen)
            painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        painter.end()
        super().paintEvent(event)

    def apply_background_image(self):
        if self.background_mode == "image":
            bg_path = resource_path("background.png")
            if os.path.isfile(bg_path):
                self.bg_pixmap = QPixmap(bg_path)
                if self.bg_pixmap.isNull():
                    self.bg_pixmap = None
                    self.background_mode = "solid"
            else:
                self.bg_pixmap = None
                self.background_mode = "solid"
        else:
            self.bg_pixmap = None

        if self.background_mode == "transparent":
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.centralWidget().setStyleSheet("background-color: rgba(0, 0, 0, 0.5);")
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            if self.background_mode == "solid":
                self.centralWidget().setStyleSheet("background-color: #000000;")
            else:
                self.centralWidget().setStyleSheet("background-color: transparent;")
        if hasattr(self, 'right_frame'):
            self.right_frame.setStyleSheet("background-color: transparent;")

    # ================== 設定介面 ==================
    def update_settings_list(self):
        self.settings_list.clear()
        top_state = "Y" if self.is_always_on_top else "N"
        self.settings_list.addItem(f"視窗置頂                             [{top_state}]")
        style_name = self.THEMES[self.current_theme_index][0]
        self.settings_list.addItem(f"主題風格                             [{style_name}]")
        level_state = "Y" if self.show_audio_level else "N"
        self.settings_list.addItem(f"音訊電平                             [{level_state}]")
        self.settings_list.addItem(f"音訊來源                             [{self.audio_level_source}]")
        self.settings_list.addItem(f"電平模式                             [{self.audio_level_mode}]")
        main_label = self._main_output_device_label()
        self.settings_list.addItem(f"輸出裝置                             [{main_label}]")
        if self.show_advanced_audio:
            self.settings_list.addItem(f"  VLC 裝置                           [{self._vlc_device_label()}]")
            self.settings_list.addItem(f"  BASS 裝置                          [{self._bass_device_label()}]")
            self.settings_list.addItem("  << 隱藏進階音訊")
        else:
            self.settings_list.addItem("進階音訊 >>")
        count_state = "Y" if self.show_play_counts else "N"
        self.settings_list.addItem(f"顯示播放次數                         [{count_state}]")
        self.settings_list.addItem(f"背景                                 [{self.background_mode}]")
        log_state = "Y" if LOG_ENABLED else "N"
        self.settings_list.addItem(f"儲存日誌                             [{log_state}]")
        dur_state = "Y" if self.show_duration else "N"
        self.settings_list.addItem(f"顯示時長                             [{dur_state}]")
        cover_state = "Y" if self.show_cover_art else "N"
        self.settings_list.addItem(f"顯示封面                             [{cover_state}]")
        time_label = "MM:SS.CC" if self.time_format == TIME_FORMAT_MM_SS_CC else "MM:SS"
        self.settings_list.addItem(f"時間格式                             [{time_label}]")
        engine_label = {ENGINE_MODE_NORMAL: "一般", ENGINE_MODE_VLC: "VLC", ENGINE_MODE_BASS: "BASS"}.get(self.engine_mode, "一般")
        self.settings_list.addItem(f"引擎模式                             [{engine_label}]")
        self.settings_list.addItem("--- 音樂資料夾 ---")
        for i, p in enumerate(self.source_paths):
            self.settings_list.addItem(f"移除資料夾                           [{i}] {p}")
        self.settings_list.addItem("新增音樂資料夾...")
        self.settings_list.addItem("重新整理檔案清單")
        self.settings_list.addItem("--- 維護 ---")
        self.settings_list.addItem("清除歷史紀錄")
        self.settings_list.addItem("清除播放次數")
        self.settings_list.addItem("清除我的最愛")
        self.settings_list.addItem("清除時長快取")
        self.settings_list.addItem("重設所有設定")
        self.settings_list.addItem("--- 關於 ---")
        self.settings_list.addItem(f"關於 dem_player {APP_VERSION}")

    def on_setting_selected(self, item):
        text = item.text()
        if text.startswith("視窗置頂"):
            self.toggle_always_on_top()
        elif text.startswith("主題風格"):
            self.cycle_theme()
        elif text.startswith("音訊來源"):
            self.toggle_audio_level_source()
        elif text.startswith("電平模式"):
            self.toggle_audio_level_mode()
        elif text.startswith("音訊電平"):
            self.toggle_audio_level_display()
        elif "輸出裝置" in text:
            self.pick_main_device()
        elif "進階音訊 >>" in text:
            self.show_advanced_audio = True
            self._save_settings()
        elif "<< 隱藏進階音訊" in text:
            self.show_advanced_audio = False
            self._save_settings()
        elif "VLC 裝置" in text:
            self.pick_vlc_device()
        elif "BASS 裝置" in text:
            self.pick_bass_device()
        elif text.startswith("顯示播放次數"):
            self.toggle_show_play_counts()
        elif text.startswith("背景"):
            self.cycle_background_mode()
        elif text.startswith("儲存日誌"):
            self.toggle_log_enabled()
        elif text.startswith("顯示時長"):
            self.show_duration = not self.show_duration
            self._save_settings()
            if self.current_dir:
                self.refresh_current_directory()
        elif text.startswith("顯示封面"):
            self.show_cover_art = not self.show_cover_art
            self._save_settings()
            self.load_cover_art(self.current_file_path)
        elif text.startswith("時間格式"):
            self.toggle_time_format()
        elif text.startswith("引擎模式"):
            self.toggle_engine_mode()
        elif text.startswith("移除資料夾"):
            m = re.search(r"\[(\d+)\]", text)
            if m:
                idx = int(m.group(1))
                if 0 <= idx < len(self.source_paths):
                    removed = self.source_paths.pop(idx)
                    self._save_playlist()
                    self.track_status.setText(f"已移除: {removed}")
                    log(f"[設定] 已移除來源資料夾: {removed}", 20)
        elif text.startswith("新增音樂資料夾"):
            folder = QFileDialog.getExistingDirectory(self, "選擇音樂資料夾")
            if folder:
                if folder not in self.source_paths:
                    self.source_paths.append(folder)
                    self._save_playlist()
                    self.track_status.setText(f"已新增: {folder}")
                    log(f"[設定] 已新增資料夾: {folder}", 20)
                else:
                    self.track_status.setText("資料夾已在清單中")
        elif text.startswith("重新整理檔案清單"):
            self.refresh_current_directory()
        elif text.startswith("清除歷史紀錄"):
            reply = QMessageBox.question(self, "確認", "確定要清除所有播放歷史嗎？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.history_paths = []
                self._save_history()
                self.track_status.setText("歷史紀錄已清除")
                log("[設定] 歷史紀錄已清除", 20)
        elif text.startswith("清除播放次數"):
            reply = QMessageBox.question(self, "確認", "確定要清除所有播放次數嗎？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.play_counts = {}
                self._save_history()
                self.track_status.setText("播放次數已清除")
                log("[設定] 播放次數已清除", 20)
        elif text.startswith("清除我的最愛"):
            reply = QMessageBox.question(self, "確認", "確定要清除所有我的最愛清單嗎？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.favorites = {}
                self._save_playlist()
                self.track_status.setText("我的最愛已清除")
                log("[設定] 我的最愛已清除", 20)
        elif text.startswith("清除時長快取"):
            reply = QMessageBox.question(self, "確認",
                "確定要清除時長快取嗎？時長標籤將重新掃描。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.folder_cache.clear()
                self._mark_cache_dirty()
                self._write_cache()
                if self.current_dir:
                    self.refresh_current_directory()
                self.track_status.setText("快取已清除")
                log("[設定] 時長快取已清除", 20)
        elif text.startswith("重設所有設定"):
            reply = QMessageBox.question(self, "確認", "確定要將所有設定重設為預設值嗎？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.current_theme_index = 0
                self.show_play_counts = True
                self.show_duration = True
                self.audio_level_mode = "all"
                self.show_cover_art = True
                self.show_audio_level = False
                self.audio_level_source = "file"
                self.loop_mode = 0
                self.background_mode = "transparent"
                self.is_always_on_top = False
                self.time_format = TIME_FORMAT_MM_SS_CC
                self.output_device = ""
                self.vlc_device = ""
                self.bass_device = ""
                self.show_advanced_audio = False
                self.engine_mode = ENGINE_MODE_NORMAL
                self.bg_color = self.THEMES[0][1]
                self.accent_color = self.THEMES[0][2]
                self.volume_text.setValue(50)
                self.apply_theme()
                self._save_settings()
                self.track_status.setText("設定已重設")
                log("[設定] 所有設定已重設為預設", 20)
        elif text.startswith("關於 dem_player"):
            self.show_about_dialog()
        self.update_settings_list()

    def toggle_time_format(self):
        if self.time_format == TIME_FORMAT_MM_SS_CC:
            self.time_format = TIME_FORMAT_MM_SS
        else:
            self.time_format = TIME_FORMAT_MM_SS_CC
        self._save_settings()
        log(f"[設定] 時間格式 = {self.time_format}", 20)
        self.update_ui()

    def toggle_engine_mode(self):
        if self.engine_mode == ENGINE_MODE_NORMAL:
            self.engine_mode = ENGINE_MODE_VLC
        elif self.engine_mode == ENGINE_MODE_VLC:
            self.engine_mode = ENGINE_MODE_BASS
        else:
            self.engine_mode = ENGINE_MODE_NORMAL
        self._save_settings()
        log(f"[設定] 引擎模式 = {self.engine_mode}", 20)

    def show_about_dialog(self):
        info = self._build_about_text()
        dlg = AboutDialog(self, info, self.accent_color, self.dos_font)
        dlg.exec()

    def _build_about_text(self):
        lines = []
        lines.append(f"dem_player {APP_VERSION}")
        lines.append("")
        lines.append("--- 環境 ---")
        lines.append(f"Python      : {sys.version.splitlines()[0]}")
        lines.append(f"平台         : {sys.platform}")
        lines.append(f"凍結         : {getattr(sys, 'frozen', False)}")
        lines.append(f"numpy       : {HAS_NUMPY}")
        lines.append(f"sounddevice : {HAS_SOUNDDEVICE}")
        lines.append(f"mutagen     : {HAS_MUTAGEN}" + ("" if HAS_MUTAGEN else "  (中繼資料已停用)"))
        lines.append(f"執行檔       : {sys.executable}")
        lines.append(f"工作目錄     : {os.getcwd()}")
        lines.append("")
        lines.append("--- 引擎 ---")
        lines.append(f"VLC         : {self.vlc_ok}")
        try:
            vlc_ver = vlc.libvlc_get_version()
            if isinstance(vlc_ver, bytes):
                vlc_ver = vlc_ver.decode("utf-8", errors="replace")
            lines.append(f"VLC 版本     : {vlc_ver}")
        except Exception:
            lines.append("VLC 版本     : -")
        lines.append(f"BASS        : {self.bass_available}")
        bass_midi_ok = False
        try:
            bass_midi_ok = self.bass_available and getattr(self.bass_engine, "bassmidi", None) is not None
        except Exception:
            bass_midi_ok = False
        lines.append(f"BASS MIDI   : {bass_midi_ok}")
        lines.append(f"ffmpeg      : {self.libopenmpt_available}")
        lines.append(f"asapconv    : {self.asap_available}")
        lines.append(f"zxtune      : {self.zxtune_available}")
        lines.append(f"furnace     : {self.furnace_available}")
        lines.append(f"引擎模式     : {self.engine_mode}")
        lines.append("")
        lines.append("--- 資料檔案 ---")
        lines.append(f"app_dir        : {app_dir()}")
        lines.append(f"settings.dpst  : {SETTINGS_FILE}")
        lines.append(f"play_list.dppls: {PLAYLIST_FILE}")
        lines.append(f"play_history   : {HISTORY_FILE}")
        lines.append(f"cache.dpch     : {CACHE_FILE}")
        lines.append(f"日誌資料夾      : {os.path.join(app_dir(), 'data')}")
        try:
            if LOG_FILE is not None:
                lines.append(f"日誌檔案        : {LOG_FILE.name}")
        except Exception:
            pass
        lines.append("")
        lines.append("--- 播放 ---")
        lines.append(f"目前引擎        : {self.current_engine}")
        lines.append(f"目前目錄        : {self.current_dir}")
        lines.append(f"目前檔案        : {self.current_file_path}")
        lines.append(f"播放清單長度    : {len(self.current_playlist)}")
        lines.append(f"曲目索引        : {self.current_track_index}")
        lines.append(f"循環模式        : {self.loop_mode_names[self.loop_mode]}")
        lines.append(f"音量            : {self.volume_text.value()}")
        lines.append(f"輸出裝置        : {self._main_output_device_label()}")
        lines.append(f"  VLC 實際      : {self._vlc_device_label()}")
        lines.append(f"  BASS 實際     : {self._bass_device_label()}")
        lines.append("")
        lines.append("--- 音訊電平 ---")
        lines.append(f"顯示音訊電平    : {self.show_audio_level}")
        lines.append(f"電平來源        : {self.audio_level_source}")
        lines.append(f"電平模式        : {self.audio_level_mode}")
        lines.append("")
        lines.append("--- 設定快照 ---")
        lines.append(f"主題            : {self.THEMES[self.current_theme_index][0]}")
        lines.append(f"時間格式        : {self.time_format}")
        lines.append(f"背景            : {self.background_mode}")
        lines.append(f"視窗置頂        : {self.is_always_on_top}")
        lines.append(f"顯示時長        : {self.show_duration}")
        lines.append(f"顯示封面        : {self.show_cover_art}")
        lines.append(f"顯示播放次數    : {self.show_play_counts}")
        lines.append(f"日誌啟用        : {LOG_ENABLED}")
        lines.append(f"日誌等級        : {LOG_LEVEL}")
        lines.append("")
        lines.append("--- 工作階段 ---")
        lines.append(f"來源            : {len(self.source_paths)}")
        lines.append(f"我的最愛        : {len(self.favorites)} 個清單")
        lines.append(f"歷史            : {len(self.history_paths)} 筆")
        lines.append(f"播放次數        : {len(self.play_counts)} 筆")
        lines.append(f"快取目錄        : {len(self.folder_cache)}")
        return "\n".join(lines)

    def cycle_background_mode(self):
        if self.background_mode == "transparent":
            self.background_mode = "solid"
        elif self.background_mode == "solid":
            if os.path.isfile(resource_path("background.png")):
                self.background_mode = "image"
            else:
                self.background_mode = "transparent"
        else:
            self.background_mode = "transparent"
        self.apply_background_image()
        self._save_settings()

    def toggle_audio_level_mode(self):
        self.audio_level_mode = "volume" if self.audio_level_mode == "all" else "all"
        self.text_eq.set_mode(self.audio_level_mode)
        self._save_settings()

    def toggle_log_enabled(self):
        global LOG_ENABLED, LOG_FILE
        LOG_ENABLED = not LOG_ENABLED
        if LOG_ENABLED:
            if LOG_FILE is None:
                init_log()
        else:
            close_log()
        self._save_settings()

    def toggle_audio_level_source(self):
        if self.audio_level_source == "file":
            if not HAS_SOUNDDEVICE:
                self.track_status.setText("未安裝 sounddevice")
                return
            self.audio_level_source = "system"
            self.start_system_audio_capture()
            if self.bass_available:
                self.bass_engine.close_decode_stream()
        else:
            self.audio_level_source = "file"
            self.stop_system_audio_capture()
        self._save_settings()

    def start_system_audio_capture(self):
        if not HAS_SOUNDDEVICE:
            return
        try:
            devices = sd.query_devices()
            loopback_device = None
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0 and (
                    'loopback' in dev['name'].lower() or
                    '立體聲混音' in dev['name'] or
                    'Stereo Mix' in dev['name']
                ):
                    loopback_device = i
                    break
            if loopback_device is None:
                loopback_device = sd.default.device[0]
            self.sd_stream = sd.InputStream(
                device=loopback_device, channels=2, samplerate=44100, blocksize=2048,
                callback=self._system_audio_callback, dtype='float32', latency='low')
            self.sd_stream.start()
            log("[系統音訊] 擷取已開始", 20)
        except Exception as e:
            log(f"[系統音訊] 失敗: {e}", 40)
            self.audio_level_source = "file"
            self._save_settings()

    def stop_system_audio_capture(self):
        if self.sd_stream is not None:
            try:
                self.sd_stream.stop()
                self.sd_stream.close()
            except Exception:
                pass
            self.sd_stream = None

    def _system_audio_callback(self, indata, frames, time, status):
        self._system_audio_data = indata.copy()

    def _calculate_system_spectrum(self):
        if not HAS_NUMPY or self._system_audio_data is None:
            return (0.0, 0.0, 0.0, 0.0)
        try:
            data = self._system_audio_data
            if data.shape[0] == 0:
                return (0.0, 0.0, 0.0, 0.0)
            if data.ndim > 1 and data.shape[1] > 1:
                mono = np.mean(data, axis=1)
            else:
                mono = data.flatten()
            fft_size = len(mono)
            if fft_size < 2048:
                return (0.0, 0.0, 0.0, 0.0)
            fft_result = np.fft.rfft(mono)
            amp = np.abs(fft_result)[:fft_size // 2]
            sample_rate = 44100
            freq_res = sample_rate / fft_size
            low_end = int(20 / freq_res)
            mid_end = int(4000 / freq_res)
            high_end = len(amp)

            def safe_avg(start, end):
                if start >= end:
                    return 0.0
                return float(np.mean(amp[start:end]))

            bass_val = safe_avg(low_end, mid_end // 4) if low_end < mid_end // 4 else 0.0
            mid_val = safe_avg(mid_end // 4, mid_end) if mid_end // 4 < mid_end else 0.0
            treble_val = safe_avg(mid_end, high_end) if mid_end < high_end else 0.0
            vol_val = float(np.sqrt(np.mean(mono ** 2)))
            scale = 0.5
            return (min(1.0, bass_val / scale),
                    min(1.0, mid_val / scale),
                    min(1.0, treble_val / scale),
                    min(1.0, vol_val * 2))
        except Exception as e:
            log(f"[系統音訊] 頻譜錯誤: {e}", 30)
            return (0.0, 0.0, 0.0, 0.0)

    def toggle_audio_level_display(self):
        if self.window_mode == 2:
            return
        self.show_audio_level = not self.show_audio_level
        self.audio_level_frame.setVisible(self.show_audio_level)
        self._save_settings()

    def cycle_theme(self):
        self.current_theme_index = (self.current_theme_index + 1) % len(self.THEMES)
        self.bg_color = self.THEMES[self.current_theme_index][1]
        self.accent_color = self.THEMES[self.current_theme_index][2]
        self.apply_theme()
        self._save_settings()
        if self.show_settings:
            self.update_settings_list()

    def toggle_always_on_top(self):
        self.is_always_on_top = not self.is_always_on_top
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.is_always_on_top)
        self.show()
        self._save_settings()

    def toggle_show_play_counts(self):
        self.show_play_counts = not self.show_play_counts
        self._save_settings()
        if self.current_dir == "MOST_PLAYED":
            self.show_most_played_list()

    def apply_theme(self):
        bg = self.bg_color
        c = self.accent_color
        font_family = self.dos_font.family()
        style = f"""
            QMainWindow {{ background-color: {bg}; }}
            QWidget {{ background-color: {bg}; color: {c}; font-family: '{font_family}', monospace; font-size: 10pt; font-weight: bold; }}
            QFrame {{ border: 2px solid {c}; padding: 4px; background-color: transparent; }}
            QListWidget {{ border: 2px solid {c}; background-color: transparent; color: {c}; outline: none; }}
            QListWidget::item:selected {{ background-color: {c}; color: {bg}; }}
            QSlider::groove:horizontal {{ border: 1px solid {c}; height: 6px; background: transparent; }}
            QSlider::handle:horizontal {{ background: {c}; border: 1px solid {c}; width: 10px; margin: -4px 0; }}
            QLineEdit {{ background-color: transparent; color: {c}; border: 1px solid {c}; padding: 2px; font-family: '{font_family}', monospace; font-size: 10pt; font-weight: bold; }}
            QLabel {{ background-color: transparent; }}
        """
        self.setStyleSheet(style)
        if hasattr(self, 'text_eq'):
            self.text_eq.set_accent_color(c)
        if hasattr(self, 'progress_text'):
            self.progress_text.set_accent_color(c)
        if hasattr(self, 'volume_text'):
            self.volume_text.set_accent_color(c)
        self.apply_background_image()
        if hasattr(self, 'min_btn'):
            for btn in (self.min_btn, self.close_btn):
                btn.setStyleSheet(f"color: {c}; background: transparent; border: 1px solid {c};")
        if self.drag_frame is not None:
            self.drag_frame.set_accent_color(c)

    # ================== 曲目模型 ==================
    @staticmethod
    def get_display_name(path):
        if path.startswith("http://") or path.startswith("https://"):
            name = path.rstrip('/').split('/')[-1]
            return name if name else path
        return os.path.basename(path)

    def make_track_key(self, track):
        if not isinstance(track, dict):
            return str(track)
        if track.get("cue_path"):
            return f"{track['cue_path']}#{track.get('cue_track_number', 0)}"
        return track.get("path", "")

    def _track_from_path(self, path, cue_info=None):
        return {
            "path": path,
            "cue_path": cue_info.get("cue_path") if cue_info else None,
            "cue_track_number": cue_info.get("number") if cue_info else None,
            "cue_title": cue_info.get("title") if cue_info else None,
            "cue_performer": cue_info.get("performer") if cue_info else None,
            "start_ms": cue_info.get("index01", 0) if cue_info else 0,
            "end_ms": cue_info.get("end_ms") if cue_info else None,
        }

    def format_track_display(self, track):
        path = track.get("path", "")
        if track.get("cue_path"):
            title = track.get("cue_title") or f"曲目 {track.get('cue_track_number', 0)}"
            performer = track.get("cue_performer") or ""
            base = f"{title}"
            if performer:
                base = f"{performer} - {title}"
            return base
        if path.startswith("http"):
            return self.get_display_name(path)
        return self.get_display_name(path).lower()

    def read_metadata(self, track):
        if not HAS_MUTAGEN:
            return None
        path = track.get("path")
        if not path or path.startswith("http") or not os.path.isfile(path):
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
                "title": track.get("cue_title") or first("title"),
                "artist": track.get("cue_performer") or first("artist"),
                "album": first("album"),
                "tracknumber": first("tracknumber"),
            }
        except Exception as e:
            log(f"[中繼] {path}: {e}", 30)
            return None

    # ================== 按鍵 ==================
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Backspace:
            if self.search_input.hasFocus():
                self.search_input.keyPressEvent(event)
                return
            self.go_back()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.search_input.hasFocus():
                self.search_input.keyPressEvent(event)
                return
            item = self.file_list.currentItem()
            if item:
                self.handle_selection(item)
        elif key == Qt.Key.Key_F1:
            self.toggle_pause()
        elif key == Qt.Key.Key_F2:
            self.adjust_volume(-1)
        elif key == Qt.Key.Key_F3:
            self.adjust_volume(1)
        elif key == Qt.Key.Key_F4:
            if self.window_mode != 2:
                self.toggle_left_visibility()
        elif key == Qt.Key.Key_F5:
            self.loop_mode = (self.loop_mode + 1) % 3
            self.loop_label.setText(f"循環: {self.loop_mode_names[self.loop_mode]}")
            self._save_settings()
        elif key == Qt.Key.Key_F6:
            self.cycle_window_mode()
        elif key == Qt.Key.Key_F7:
            if self.window_mode != 2:
                self.toggle_settings_page()
        elif key == Qt.Key.Key_F8:
            if self.window_mode == 2:
                return
            if self.search_input.hasFocus():
                self.search_input.clearFocus()
                self.file_list.setFocus()
            else:
                if self.show_settings:
                    self.toggle_settings_page()
                self.search_input.setFocus()
                self.search_input.selectAll()
        elif key == Qt.Key.Key_F9:
            if self.search_input.hasFocus():
                self.search_input.clearFocus()
                self.file_list.setFocus()
            self.handle_f9()
        elif key == Qt.Key.Key_Escape:
            self.reset_player()
        elif key == Qt.Key.Key_Left:
            self.seek_relative(-1000)
        elif key == Qt.Key.Key_Right:
            self.seek_relative(1000)
        else:
            if self.search_input.hasFocus():
                self.search_input.keyPressEvent(event)
            else:
                super().keyPressEvent(event)

    def handle_f9(self):
        item = self.file_list.currentItem()
        if not item:
            return
        track = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(track, dict):
            return
        target = track.get("path")
        if not target:
            return
        if not target.startswith("http") and not os.path.isfile(target):
            return
        if self.current_dir and self.current_dir.startswith("FAVORITES:"):
            lid = self.current_dir.split(":")[1]
            if lid in self.favorites and target in self.favorites[lid]:
                reply = QMessageBox.question(self, "確認刪除",
                    "確定要從我的最愛清單移除此曲目嗎？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self.favorites[lid].remove(target)
                    self._save_playlist()
                    self.track_status.setText(f"已從 {lid} 移除")
                    self.show_favorites_list(lid)
            else:
                self.track_status.setText("不在此清單中")
        else:
            num, ok = QInputDialog.getInt(self, "我的最愛", "輸入我的最愛清單編號 (0-512):", 1, 0, 512, 1)
            if not ok:
                return
            list_id = f"{num:03d}"
            if list_id not in self.favorites:
                self.favorites[list_id] = []
            if target not in self.favorites[list_id]:
                self.favorites[list_id].append(target)
                self._save_playlist()
                self.track_status.setText(f"已新增至 {list_id}")
            else:
                self.track_status.setText(f"已在 {list_id} 中")

    def toggle_left_visibility(self):
        self.left_visible = not self.left_visible
        if self.left_visible:
            self.left_stack.setVisible(True)
            self.browser_label.setVisible(True)
            self.left_frame.setStyleSheet("")
            self.file_list.setFocus()
        else:
            self.left_stack.setVisible(False)
            self.browser_label.setVisible(False)
            self.left_frame.setStyleSheet("background: transparent; border: none;")
            self.setFocus()

    def toggle_settings_page(self):
        if self.show_settings:
            self.left_stack.setCurrentIndex(0)
            self.show_settings = False
            self.file_list.setFocus()
        else:
            if self.search_input.hasFocus():
                self.search_input.clearFocus()
                self.file_list.setFocus()
            self.left_stack.setCurrentIndex(1)
            self.show_settings = True
            self.settings_list.setFocus()
            self.settings_list.setCurrentRow(0)
            self.update_settings_list()

    def do_search(self):
        keyword = self.search_input.text().strip().lower()
        if not keyword:
            for idx in range(self.file_list.count()):
                self.file_list.item(idx).setHidden(False)
        else:
            for idx in range(self.file_list.count()):
                item = self.file_list.item(idx)
                txt = item.text().lower()
                item.setHidden(keyword not in txt)
        self.search_input.setFocus()

    def reset_player(self):
        self.stop_current_engine()
        prevent_sleep(False)
        self.current_file_path = None
        self.current_track_info = None
        self.spectrum_source_path = None
        self.loop_mode = 0
        self.loop_label.setText("循環: 關閉")
        self.track_title.setText("------------------------")
        self.meta_label.setText("演出者: -   專輯: -   曲目#: -")
        self.track_status.setText("已停止")
        self.progress_text.setValue(0)
        self.cover_label.clear()
        self.cover_label.setVisible(False)
        if self.show_settings:
            self.toggle_settings_page()
        self.search_input.clear()
        for idx in range(self.file_list.count()):
            self.file_list.item(idx).setHidden(False)
        if self.search_input.hasFocus():
            self.search_input.clearFocus()
        if self.window_mode != 0:
            self.window_mode = 0
            self.set_normal_mode()
        else:
            self.show_source_list()
            self.set_normal_mode()
        self.file_list.setFocus()
        self._save_settings()

    def cycle_window_mode(self):
        self.window_mode = (self.window_mode + 1) % 4
        if self.window_mode == 0:
            self.set_normal_mode()
        elif self.window_mode == 1:
            self.set_fullscreen_mode()
        elif self.window_mode == 2:
            self.set_mini_mode()
        else:
            self.set_bar_mode()
        self._save_settings()

    def set_normal_mode(self):
        if self.isFullScreen():
            self.showNormal()
        self.setFixedSize(900, 600)
        self.left_frame.setMinimumWidth(500)
        self.right_frame.setMaximumWidth(360)
        self.left_frame.setVisible(True)
        self.right_frame.setVisible(True)
        self.track_title.setVisible(True)
        self.meta_label.setVisible(True)
        self.status_frame.setVisible(True)
        self.progress_text.setVisible(True)
        self.volume_text.setVisible(True)
        self.audio_level_frame.setVisible(self.show_audio_level)
        self.keys_label.setVisible(True)
        self.search_frame.setVisible(True)
        self.mini_keys_label.setVisible(False)
        self.cover_label.setVisible(self.show_cover_art and self.current_file_path is not None)
        self.setFontSize(10)
        self.apply_font_to_all()
        self.track_title.fixed_visible_chars = 40
        self.track_title.setText(self.track_title.full_text)
        self.text_eq.fix_widths(self.dos_font)
        self.progress_text.setBarLength(18)
        self.volume_text.setBarLength(17)
        if hasattr(self, 'right_stretch_item') and self.right_stretch_item:
            self.right_stretch_item.changeSize(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        if not self.left_visible:
            self.toggle_left_visibility()
        if self.show_settings:
            self.toggle_settings_page()
        self.file_list.setFocus()
        self.load_cover_art(self.current_file_path)
        self.update_now_playing_marker()

    def set_fullscreen_mode(self):
        self.left_frame.setMinimumWidth(0)
        self.right_frame.setMaximumWidth(QWIDGETSIZE_MAX)
        self.left_frame.setVisible(True)
        self.right_frame.setVisible(True)
        self.track_title.setVisible(True)
        self.meta_label.setVisible(True)
        self.status_frame.setVisible(True)
        self.progress_text.setVisible(True)
        self.volume_text.setVisible(True)
        self.audio_level_frame.setVisible(self.show_audio_level)
        self.keys_label.setVisible(True)
        self.search_frame.setVisible(True)
        self.mini_keys_label.setVisible(False)
        self.cover_label.setVisible(self.show_cover_art and self.current_file_path is not None)
        self.setFontSize(12)
        self.apply_font_to_all()
        self.track_title.fixed_visible_chars = 60
        self.track_title.setText(self.track_title.full_text)
        self.text_eq.fix_widths(self.dos_font)
        self.progress_text.setBarLength(50)
        self.volume_text.setBarLength(50)
        if hasattr(self, 'right_stretch_item') and self.right_stretch_item:
            self.right_stretch_item.changeSize(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        if not self.left_visible:
            self.toggle_left_visibility()
        if self.show_settings:
            self.toggle_settings_page()
        self.showFullScreen()
        self.update_now_playing_marker()

    def set_mini_mode(self):
        if self.isFullScreen():
            self.showNormal()
        self.left_frame.setMinimumWidth(0)
        self.right_frame.setMaximumWidth(QWIDGETSIZE_MAX)
        self.audio_level_frame.setVisible(False)
        if self.show_settings:
            self.toggle_settings_page()
        self.left_frame.setVisible(False)
        self.right_frame.setVisible(True)
        self.track_title.setVisible(True)
        self.meta_label.setVisible(False)
        self.status_frame.setVisible(True)
        self.progress_text.setVisible(True)
        self.volume_text.setVisible(True)
        self.keys_label.setVisible(False)
        self.search_frame.setVisible(False)
        self.mini_keys_label.setVisible(True)
        self.cover_label.setVisible(False)
        self.setFixedSize(380, 230)
        self.setFontSize(9)
        self.apply_font_to_all()
        self.track_title.fixed_visible_chars = 25
        self.track_title.setText(self.track_title.full_text)
        self.text_eq.fix_widths(self.dos_font)
        self.progress_text.setBarLength(18)
        self.volume_text.setBarLength(18)
        if hasattr(self, 'right_stretch_item') and self.right_stretch_item:
            self.right_stretch_item.changeSize(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.setFocus()

    def set_bar_mode(self):
        if self.isFullScreen():
            self.showNormal()
        self.left_frame.setMinimumWidth(0)
        self.right_frame.setMaximumWidth(QWIDGETSIZE_MAX)
        self.audio_level_frame.setVisible(False)
        if self.show_settings:
            self.toggle_settings_page()
        self.left_frame.setVisible(False)
        self.right_frame.setVisible(True)
        self.track_title.setVisible(True)
        self.meta_label.setVisible(False)
        self.status_frame.setVisible(True)
        self.progress_text.setVisible(True)
        self.volume_text.setVisible(True)
        self.keys_label.setVisible(False)
        self.search_frame.setVisible(False)
        self.mini_keys_label.setVisible(False)
        self.cover_label.setVisible(False)
        self.audio_level_frame.setVisible(False)
        self.setFixedSize(900, 200)
        self.setFontSize(10)
        self.apply_font_to_all()
        self.track_title.fixed_visible_chars = 90
        self.track_title.setText(self.track_title.full_text)
        self.text_eq.fix_widths(self.dos_font)
        self.progress_text.setBarLength(80)
        self.volume_text.setBarLength(75)
        if hasattr(self, 'right_stretch_item') and self.right_stretch_item:
            self.right_stretch_item.changeSize(0, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self.right_stretch_item.setSpacing(0)
        self.setFocus()

    def setFontSize(self, size):
        self.dos_font.setPointSize(size)

    def apply_font_to_all(self):
        for widget in self.findChildren(QLabel):
            widget.setFont(self.dos_font)
        self.file_list.setFont(self.dos_font)
        self.search_input.setFont(self.dos_font)
        for lbl in self.text_eq.labels:
            lbl.setFont(self.dos_font)
        self.text_eq.fix_widths(self.dos_font)
        if hasattr(self, 'progress_text'):
            self.progress_text.setFont(self.dos_font)
        if hasattr(self, 'volume_text'):
            self.volume_text.setFont(self.dos_font)
        if hasattr(self, 'meta_label'):
            self.meta_label.setFont(self.dos_font)

    # ================== 封面 ==================
    def load_cover_art(self, filepath):
        if not self.show_cover_art or not filepath or filepath.startswith("http"):
            self.cover_label.clear()
            self.cover_label.setVisible(False)
            return
        folder = os.path.dirname(filepath)
        candidates = ["cover.jpg", "cover.png", "folder.jpg", "folder.png", "front.jpg", "front.png"]
        pixmap = None
        for name in candidates:
            cover_path = os.path.join(folder, name)
            if os.path.isfile(cover_path):
                pixmap = QPixmap(cover_path)
                break
        if pixmap and not pixmap.isNull():
            max_h = 180
            self.cover_label.setPixmap(pixmap.scaled(
                self.cover_label.width(), max_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            self.cover_label.setVisible(self.window_mode not in (2, 3))
        else:
            self.cover_label.clear()
            self.cover_label.setVisible(False)

    # ================== 引擎選擇 ==================
    def _get_engine_for_file(self, path):
        ext = os.path.splitext(path)[1].lower()

        if ext in ('.dnm', '.ftm'):
            return 'chiptune_cli' if self.furnace_available else None

        if self.engine_mode == ENGINE_MODE_VLC:
            if ext in ('.sid', '.vgm', '.vgz'):
                return 'zxtune' if self.zxtune_available else 'vlc'
            if ext in ('.sap', '.cmc', '.cm3', '.cmr', '.cms', '.dmc', '.dlt',
                       '.mpt', '.mpd', '.rmt', '.tmc', '.tm8', '.tm2', '.fc'):
                return 'asap' if self.asap_available else 'vlc'
            if ext in ('.mt2', '.stm', '.ult', '.669', '.far'):
                return 'libopenmpt' if self.libopenmpt_available else 'vlc'
            return 'vlc'

        if self.engine_mode == ENGINE_MODE_BASS:
            if ext in ('.sid', '.vgm', '.vgz'):
                return 'zxtune' if self.zxtune_available else 'vlc'
            if ext in ('.sap', '.cmc', '.cm3', '.cmr', '.cms', '.dmc', '.dlt',
                       '.mpt', '.mpd', '.rmt', '.tmc', '.tm8', '.tm2', '.fc'):
                return 'asap' if self.asap_available else 'vlc'
            if ext in ('.mt2', '.stm', '.ult', '.669', '.far'):
                return 'libopenmpt' if self.libopenmpt_available else 'vlc'
            return 'bass' if self.bass_available else 'vlc'

        # ENGINE_MODE_NORMAL
        if self.show_audio_level and ext in self.LEVEL_SUPPORTED_EXT and self.bass_available:
            return 'bass'
        if ext in ('.mod', '.xm', '.it', '.s3m', '.mtm', '.umx', '.mo3'):
            return 'bass' if self.bass_available else 'vlc'
        if ext == '.mptm':
            return 'vlc'
        if ext in ('.mid', '.midi', '.rmi', '.kar'):
            return 'bass' if (self.bass_available and self.bass_engine.bassmidi is not None) else 'vlc'
        if ext in ('.sid', '.vgm', '.vgz'):
            return 'zxtune' if self.zxtune_available else 'vlc'
        if ext in ('.sap', '.cmc', '.cm3', '.cmr', '.cms', '.dmc', '.dlt',
                   '.mpt', '.mpd', '.rmt', '.tmc', '.tm8', '.tm2', '.fc'):
            return 'asap' if self.asap_available else 'vlc'
        if ext in ('.mt2', '.stm', '.ult', '.669', '.far'):
            return 'libopenmpt' if self.libopenmpt_available else 'vlc'
        return 'vlc'

    def stop_current_engine(self):
        self._cue_end_timer.stop()
        self._cue_end_ms = None
        if self.conv_thread and self.conv_thread.isRunning():
            self.conv_thread.requestInterruption()
            self.conv_thread.wait(1000)
            self.conv_thread = None
        if self.current_engine == 'bass':
            self.bass_engine.stop()
        elif self.current_engine in ('vlc', 'libopenmpt', 'asap', 'zxtune', 'chiptune_cli', 'cached'):
            if self.vlc_player is not None:
                self.vlc_player.stop()
        if self.bass_available:
            self.bass_engine.close_decode_stream()

    def _add_to_cache(self, original_key, wav_path):
        if original_key in self.convert_cache:
            old_wav = self.convert_cache.pop(original_key)
            if os.path.exists(old_wav):
                try:
                    os.remove(old_wav)
                except Exception:
                    pass
        elif len(self.convert_cache) >= self.cache_max_size:
            oldest_key = next(iter(self.convert_cache))
            oldest_wav = self.convert_cache.pop(oldest_key)
            if os.path.exists(oldest_wav):
                try:
                    os.remove(oldest_wav)
                except Exception:
                    pass
        self.convert_cache[original_key] = wav_path

    # ================== 播放 ==================
    def play_file(self, track_or_path):
        if isinstance(track_or_path, dict):
            track = track_or_path
        else:
            track = self._track_from_path(track_or_path)

        path = track.get("path")
        if not path:
            self.track_status.setText("無法播放 - 缺少路徑")
            return

        if not path.startswith("http") and not os.path.isfile(path):
            log(f"[播放] 略過遺失的檔案: {path}", 30)
            self.track_status.setText(f"遺失: {self.get_display_name(path)}")
            self._mark_now_playing(None)
            if self.current_playlist and self.loop_mode == 2:
                QTimer.singleShot(500, self.play_next_in_list)
            return

        engine = self._get_engine_for_file(path)

        if track.get("cue_path") and engine == 'bass' and track.get("end_ms"):
            self._cue_end_ms = track.get("end_ms")
            self._cue_end_timer.start()
        else:
            self._cue_end_ms = None
            self._cue_end_timer.stop()

        cache_key = self.make_track_key(track)
        if cache_key in self.convert_cache:
            cached_wav = self.convert_cache[cache_key]
            if os.path.exists(cached_wav):
                self.stop_current_engine()
                if self.vlc_player is None:
                    self.track_status.setText("無法播放 (無 VLC)")
                    return
                media = self.vlc_instance.media_new(cached_wav)
                self.vlc_player.set_media(media)
                if self.vlc_player.play() == -1:
                    self.track_status.setText("無法播放")
                    return
                QTimer.singleShot(300, self.update_volume_to_actual)
                self.current_file_path = path
                self.current_track_info = track
                self.current_engine = 'cached'
                self.spectrum_source_path = cached_wav
                self._update_track_display(track)
                self.track_status.setText("播放中 (快取)")
                prevent_sleep(True)
                self.add_to_history(path)
                QTimer.singleShot(1000, lambda: self._fetch_and_cache_duration(path))
                if self.current_playlist:
                    for i, t in enumerate(self.current_playlist):
                        if self.make_track_key(t) == cache_key:
                            self.current_track_index = i
                            break
                self.load_cover_art(path)
                self.update_now_playing_marker()
                return
            else:
                del self.convert_cache[cache_key]

        self.stop_current_engine()
        if self.temp_wav:
            try:
                os.remove(self.temp_wav)
            except Exception:
                pass
            self.temp_wav = None

        self.current_file_path = path
        self.current_track_info = track

        if engine is None:
            self.track_status.setText("無法播放 - 缺少所需引擎")
            self._mark_now_playing(None)
            return

        if self.current_playlist:
            for i, t in enumerate(self.current_playlist):
                if self.make_track_key(t) == cache_key:
                    self.current_track_index = i
                    break
            else:
                self.current_track_index = -1

        log(f"[播放] {path} engine={engine} start_ms={track.get('start_ms', 0)} "
            f"end_ms={track.get('end_ms')} mode={self.engine_mode}", 20)

        if engine in ('libopenmpt', 'asap', 'zxtune', 'chiptune_cli'):
            fname = os.path.basename(path)
            self.track_status.setText(f"載入中 [{fname}]")
            self._update_track_display(track)
            self.current_engine = engine
            self.conv_thread = ConversionThread(engine, path)
            self.conv_thread.finished.connect(lambda wav: self.on_conversion_finished(wav, engine))
            self.conv_thread.start()
            return

        if engine == 'bass':
            success = self.bass_engine.play(path, start_ms=track.get("start_ms", 0))
            if success:
                self.current_engine = 'bass'
                self.spectrum_source_path = path
                QTimer.singleShot(300, self.update_volume_to_actual)
                QTimer.singleShot(1000, lambda: self._fetch_and_cache_duration(path))
            else:
                log(f"[BASS] 退回 VLC 播放 {path}", 30)
                engine = 'vlc'
        if engine == 'vlc':
            if self.vlc_player is None:
                self.track_status.setText("無法播放 (無 VLC)")
                self._mark_now_playing(None)
                return
            if self.bass_available and not path.startswith("http"):
                self.bass_engine.open_decode_stream(path)
            media = self.vlc_instance.media_new(path)
            self.configure_midi_media(media, path)
            if track.get("cue_path"):
                start_ms = track.get("start_ms", 0) or 0
                end_ms = track.get("end_ms")
                if start_ms > 0:
                    media.add_option(f":start-time={start_ms / 1000.0:.3f}")
                if end_ms and end_ms > 0:
                    media.add_option(f":stop-time={end_ms / 1000.0:.3f}")
            self.vlc_player.set_media(media)
            if self.vlc_player.play() == -1:
                self.track_status.setText("無法播放")
                self._mark_now_playing(None)
                return
            self.current_engine = 'vlc'
            self.spectrum_source_path = path
            QTimer.singleShot(300, self.update_volume_to_actual)
            QTimer.singleShot(1000, lambda: self._fetch_and_cache_duration(path))

        self._update_track_display(track)
        self.track_status.setText("播放中")
        prevent_sleep(True)
        self.add_to_history(path)
        self.increment_play_count(path)
        self.load_cover_art(path)
        self.update_now_playing_marker()

    def _vlc_seek_ms(self, ms):
        try:
            if self.vlc_player is not None:
                self.vlc_player.set_time(int(ms))
        except Exception:
            pass

    def _update_track_display(self, track):
        path = track.get("path", "")
        if track.get("cue_path"):
            title = track.get("cue_title") or f"曲目 {track.get('cue_track_number', 0)}"
            performer = track.get("cue_performer") or ""
            if performer:
                self.track_title.setText(f"{performer} - {title}")
            else:
                self.track_title.setText(title)
        else:
            self.track_title.setText(self.get_display_name(path))
        meta = self.read_metadata(track)
        if meta:
            artist = meta.get("artist") or "-"
            album = meta.get("album") or "-"
            tn = meta.get("tracknumber") or "-"
            self.meta_label.setText(f"演出者: {artist}   專輯: {album}   曲目#: {tn}")
        else:
            self.meta_label.setText("演出者: -   專輯: -   曲目#: -")

    def _check_cue_end(self):
        if self._cue_end_ms is None:
            return
        try:
            if self.current_engine == 'bass':
                curr_ms, _ = self.bass_engine.get_time()
            else:
                return
            if curr_ms is not None and curr_ms >= self._cue_end_ms:
                self._cue_end_timer.stop()
                self._cue_end_ms = None
                self.on_media_end()
        except Exception:
            pass

    def _fetch_and_cache_duration(self, filepath):
        if filepath.startswith("http"):
            return
        folder = os.path.dirname(filepath) + "/"
        fname = os.path.basename(filepath)
        if folder in self.folder_cache:
            for cf in self.folder_cache[folder]["files"]:
                if cf["filename"] == fname and cf["duration_ms"] >= 0:
                    if os.path.exists(filepath) and os.path.getmtime(filepath) == cf["mtime"]:
                        return
        dur_ms = -1
        try:
            if self.current_engine == 'bass' and self.bass_available and self.bass_engine.is_playing():
                _, total_ms = self.bass_engine.get_time()
                if total_ms > 0:
                    dur_ms = total_ms
            elif self.vlc_player is not None and self.vlc_player.get_state() == vlc.State.Playing:
                total_ms = self.vlc_player.get_length()
                if total_ms > 0:
                    dur_ms = total_ms
        except Exception:
            pass
        if dur_ms <= 0:
            dur_ms = -1
        if folder not in self.folder_cache:
            self.folder_cache[folder] = {"scanned_mtime": os.path.getmtime(folder), "files": []}
        cache_entry = self.folder_cache[folder]
        cache_entry["files"] = [cf for cf in cache_entry["files"] if cf["filename"] != fname]
        cache_entry["files"].append({
            "filename": fname,
            "duration_ms": dur_ms,
            "mtime": os.path.getmtime(filepath) if dur_ms >= 0 else 0
        })
        cache_entry["scanned_mtime"] = os.path.getmtime(folder)
        self._mark_cache_dirty()
        if self.current_dir == os.path.dirname(filepath):
            self._update_item_duration(fname, dur_ms)

    def increment_play_count(self, filepath):
        if filepath:
            self.play_counts[filepath] = self.play_counts.get(filepath, 0) + 1
            self._save_history()

    def on_conversion_finished(self, wav, engine):
        if wav:
            self.temp_wav = wav
            track = self.current_track_info or self._track_from_path(self.current_file_path)
            self._add_to_cache(self.make_track_key(track), wav)
            if self.vlc_player is None:
                self.track_status.setText("無法播放 (無 VLC)")
                return
            media = self.vlc_instance.media_new(wav)
            self.vlc_player.set_media(media)
            self.spectrum_source_path = wav
            if self.show_audio_level and self.bass_available:
                self.bass_engine.open_decode_stream(wav)
            if self.vlc_player.play() == -1:
                self._play_with_vlc_fallback(self.current_file_path)
                return
            QTimer.singleShot(300, self.update_volume_to_actual)
            QTimer.singleShot(800, lambda: self._check_vlc_playback(wav))
            QTimer.singleShot(1500, lambda: self._fetch_and_cache_duration(self.current_file_path))
            self.load_cover_art(self.current_file_path)
            if self.current_track_info:
                self._update_track_display(self.current_track_info)
        else:
            self._play_with_vlc_fallback(self.current_file_path)

    def _check_vlc_playback(self, wav):
        if self.vlc_player is None:
            return
        state = self.vlc_player.get_state()
        if state != vlc.State.Playing:
            log("[轉換] VLC 失敗，退回", 30)
            self._play_with_vlc_fallback(self.current_file_path)
        else:
            self.track_status.setText("播放中")
            prevent_sleep(True)

    def _play_with_vlc_fallback(self, filepath):
        if self.current_engine == 'chiptune_cli':
            self.track_status.setText("無法播放 - VLC 無法播放 .dnm/.ftm")
            return
        if self.vlc_player is None or self.vlc_instance is None:
            self.track_status.setText("無法播放")
            return
        if not filepath.startswith("http") and not os.path.isfile(filepath):
            self.track_status.setText("無法播放 - 檔案遺失")
            return
        self.vlc_player.stop()
        media = self.vlc_instance.media_new(filepath)
        self.vlc_player.set_media(media)
        if self.vlc_player.play() == -1:
            self.track_status.setText("無法播放 - 不支援的格式")
        else:
            self.spectrum_source_path = filepath
            QTimer.singleShot(300, self.update_volume_to_actual)
            QTimer.singleShot(300, self._check_fallback_playback)
            QTimer.singleShot(1000, lambda: self._fetch_and_cache_duration(filepath))
            self.load_cover_art(filepath)

    def _check_fallback_playback(self):
        if self.vlc_player is None:
            return
        if self.vlc_player.get_state() != vlc.State.Playing:
            self.track_status.setText("無法播放 - VLC 失敗")
        else:
            self.track_status.setText("播放中 (VLC)")
            prevent_sleep(True)

    def toggle_pause(self):
        if self.current_engine == 'bass':
            if self.bass_engine.is_playing():
                self.bass_engine.pause()
                prevent_sleep(False)
                self.track_status.setText("已暫停")
            else:
                self.bass_engine.resume()
                prevent_sleep(True)
                self.track_status.setText("播放中")
        else:
            if self.vlc_player is not None:
                if self.vlc_player.is_playing():
                    self.vlc_player.pause()
                    prevent_sleep(False)
                    self.track_status.setText("已暫停")
                else:
                    self.vlc_player.play()
                    prevent_sleep(True)
                    self.track_status.setText("播放中")

    def adjust_volume(self, delta):
        new_vol = max(0, min(100, self.volume_text.value() + delta))
        self.volume_text.setValue(new_vol)
        if self.current_engine == 'bass':
            self.bass_engine.set_volume(new_vol)
        else:
            if self.vlc_player is not None:
                self.vlc_player.audio_set_volume(new_vol)
        self._save_settings()

    def seek_relative(self, delta_ms):
        if self.current_engine == 'bass':
            pos_ms, len_ms = self.bass_engine.get_time()
            if pos_ms >= 0 and len_ms > 0:
                target_ratio = max(0.0, min(1.0, (pos_ms + delta_ms) / len_ms))
                self.bass_engine.set_position(target_ratio)
        else:
            if self.vlc_player is not None:
                current = self.vlc_player.get_time()
                if current >= 0:
                    total = self.vlc_player.get_length()
                    target = current + delta_ms
                    if total > 0:
                        target = max(0, min(total, target))
                    self.vlc_player.set_time(target)

    def on_vlc_end(self, event):
        QTimer.singleShot(0, self.on_media_end)

    def on_media_end(self):
        if self.loop_mode == 1 and self.current_track_info:
            self.play_file(self.current_track_info)
        elif self.loop_mode == 2 and self.current_playlist:
            self.play_next_in_list()
        else:
            prevent_sleep(False)
            self.track_status.setText("已停止")
            self._mark_now_playing(None)

    def play_next_in_list(self):
        if not self.current_playlist:
            return
        n = len(self.current_playlist)
        for step in range(1, n + 1):
            idx = (self.current_track_index + step) % n
            track = self.current_playlist[idx]
            p = track.get("path") if isinstance(track, dict) else track
            if p and (p.startswith("http") or os.path.isfile(p)):
                self.current_track_index = idx
                self.play_file(track)
                return
        self.track_status.setText("清單中沒有可播放的曲目")
        self._mark_now_playing(None)

    def add_to_history(self, filepath):
        if filepath in self.history_paths:
            self.history_paths.remove(filepath)
        self.history_paths.insert(0, filepath)
        if len(self.history_paths) > 100:
            self.history_paths = self.history_paths[:100]
        self._save_history()

    def configure_midi_media(self, media, filepath):
        if filepath.startswith("http"):
            return
        ext = os.path.splitext(filepath)[1].lower()
        if ext in ('.mid', '.midi', '.rmi'):
            possible_fonts = [
                resource_path("soundfont.sf2"),
                os.path.expandvars(r"%SystemRoot%\system32\drivers\gm.dls"),
                r"C:\soundfonts\FluidR3_GM.sf2",
                r"C:\soundfonts\default.sf2",
                "/usr/share/sounds/sf2/FluidR3_GM.sf2",
                "/usr/share/sounds/sf2/default.sf2",
            ]
            sf2_path = next((p for p in possible_fonts if os.path.isfile(p)), None)
            if sf2_path:
                media.add_option(f':sout=#transcode{{acodec=s16l,channels=2,samplerate=44100}}:standard{{access=file,dst=-}}')
                media.add_option(f'--sout-fluidsynth-soundfont={sf2_path}')

    # ================== 清單 ==================
    @staticmethod
    def _make_audio_tag(duration_ms=None, show_duration=True):
        if not show_duration:
            return "[音訊]"
        if duration_ms is not None and duration_ms >= 0:
            s, _ = divmod(duration_ms, 1000)
            m, s = divmod(s, 60)
            return f"[音訊 {m:02d}:{s:02d}]"
        return "[音訊]"

    def _get_file_cached_duration(self, filepath):
        folder = os.path.dirname(filepath) + "/"
        if folder in self.folder_cache:
            fname = os.path.basename(filepath)
            for cf in self.folder_cache[folder]["files"]:
                if cf["filename"] == fname:
                    if os.path.exists(filepath) and os.path.getmtime(filepath) == cf["mtime"]:
                        return cf["duration_ms"]
                    return None
        return None

    def _make_item(self, track, prefix_text=""):
        path = track["path"]
        display = self.format_track_display(track)
        if path.startswith("http"):
            text = f"[網路] {prefix_text}{display}"
        elif not os.path.isfile(path):
            text = f"[遺失] {prefix_text}{display}"
        else:
            if track.get("cue_path"):
                text = f"[CUE] {prefix_text}{display}"
            else:
                dur = self._get_file_cached_duration(path)
                tag = self._make_audio_tag(dur, self.show_duration)
                text = f"{tag} {prefix_text}{display}"
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, track)
        return item

    def update_now_playing_marker(self):
        current_key = self.make_track_key(self.current_track_info) if self.current_track_info else None
        for idx in range(self.file_list.count()):
            item = self.file_list.item(idx)
            t = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(t, dict):
                continue
            text = item.text()
            if text.startswith("▶ "):
                text = text[2:]
            key = self.make_track_key(t)
            if current_key and key == current_key:
                item.setText("▶ " + text)
            else:
                item.setText(text)

    def _mark_now_playing(self, track):
        self.current_track_info = track
        self.update_now_playing_marker()

    def show_source_list(self):
        log("[介面] show_source_list", 20)
        self.current_dir = None
        self._pending_folder_list = []
        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        self.current_playlist = []
        for p in self.source_paths:
            if p.startswith("http://") or p.startswith("https://"):
                item = QListWidgetItem(f"[網路] {self.get_display_name(p)}")
            else:
                name = os.path.basename(p.rstrip('\\/')) or p
                item = QListWidgetItem(f"[檔案] {name.lower()}")
            item.setData(Qt.ItemDataRole.UserRole, {"path": p, "is_source": True})
            self.file_list.addItem(item)
        for lid in sorted(self.favorites.keys()):
            if self.favorites[lid]:
                item = QListWidgetItem(f"[清單{lid}] 我的最愛")
                item.setData(Qt.ItemDataRole.UserRole, {"path": f"FAVORITES:{lid}", "is_source": True})
                self.file_list.addItem(item)
        if self.history_paths:
            item = QListWidgetItem("[歷史]播放歷史")
            item.setData(Qt.ItemDataRole.UserRole, {"path": "HISTORY", "is_source": True})
            self.file_list.addItem(item)
        if self.play_counts:
            item = QListWidgetItem("[最常] 最常播放")
            item.setData(Qt.ItemDataRole.UserRole, {"path": "MOST_PLAYED", "is_source": True})
            self.file_list.addItem(item)
        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
        self.path_label.setText("-")
        self.file_list.setUpdatesEnabled(True)

    def show_most_played_list(self):
        log("[介面] show_most_played_list", 20)
        self.current_dir = "MOST_PLAYED"
        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        self.current_playlist = []
        self.current_track_index = -1
        back = QListWidgetItem("[..]  (返回)")
        back.setData(Qt.ItemDataRole.UserRole, {"path": "ACTION_BACK"})
        self.file_list.addItem(back)
        sorted_counts = sorted(self.play_counts.items(), key=lambda x: x[1], reverse=True)
        for filepath, count in sorted_counts:
            track = self._track_from_path(filepath)
            prefix = f"({count}) " if self.show_play_counts else ""
            self.file_list.addItem(self._make_item(track, prefix))
            self.current_playlist.append(track)
        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
        self.path_label.setText("最常播放")
        self.file_list.setUpdatesEnabled(True)
        self.update_now_playing_marker()

    def show_favorites_list(self, lid):
        log(f"[介面] show_favorites_list lid={lid}", 20)
        self.current_dir = f"FAVORITES:{lid}"
        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        self.current_playlist = []
        self.current_track_index = -1
        back = QListWidgetItem("[..]  (返回)")
        back.setData(Qt.ItemDataRole.UserRole, {"path": "ACTION_BACK"})
        self.file_list.addItem(back)
        for filepath in self.favorites.get(lid, []):
            track = self._track_from_path(filepath)
            self.file_list.addItem(self._make_item(track))
            self.current_playlist.append(track)
        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
        self.path_label.setText(f"我的最愛 {lid}")
        self.file_list.setUpdatesEnabled(True)
        self.update_now_playing_marker()

    def show_history_list(self):
        log("[介面] show_history_list", 20)
        self.current_dir = "HISTORY"
        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        self.current_playlist = []
        self.current_track_index = -1
        back = QListWidgetItem("[..]  (返回)")
        back.setData(Qt.ItemDataRole.UserRole, {"path": "ACTION_BACK"})
        self.file_list.addItem(back)
        for filepath in self.history_paths:
            track = self._track_from_path(filepath)
            self.file_list.addItem(self._make_item(track))
            self.current_playlist.append(track)
        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
        self.path_label.setText("播放歷史")
        self.file_list.setUpdatesEnabled(True)
        self.update_now_playing_marker()

    def show_m3u_list(self, m3u_path):
        log(f"[介面] show_m3u_list {m3u_path}", 20)
        self.current_dir = "M3U:" + m3u_path
        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        self.current_playlist = []
        self.current_track_index = -1
        back = QListWidgetItem("[..]  (返回)")
        back.setData(Qt.ItemDataRole.UserRole, {"path": "ACTION_BACK"})
        self.file_list.addItem(back)
        for it in parse_m3u(m3u_path):
            track = self._track_from_path(it)
            self.file_list.addItem(self._make_item(track))
            self.current_playlist.append(track)
        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
        self.path_label.setText(f"M3U: {os.path.basename(m3u_path)}")
        self.file_list.setUpdatesEnabled(True)
        self.update_now_playing_marker()

    def show_cue_list(self, cue_path):
        log(f"[介面] show_cue_list {cue_path}", 20)
        self.current_dir = "CUE:" + cue_path
        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        self.current_playlist = []
        self.current_track_index = -1
        back = QListWidgetItem("[..]  (返回)")
        back.setData(Qt.ItemDataRole.UserRole, {"path": "ACTION_BACK"})
        self.file_list.addItem(back)

        cue_tracks = parse_cue_file(cue_path)
        if not cue_tracks:
            self.track_status.setText("CUE 解析失敗")
        for c in cue_tracks:
            audio_file = c.get("file")
            if not audio_file:
                continue
            if not os.path.isabs(audio_file):
                audio_file = os.path.join(os.path.dirname(cue_path), audio_file)
            track = self._track_from_path(audio_file, cue_info={
                "cue_path": cue_path,
                "number": c["number"],
                "title": c.get("title", ""),
                "performer": c.get("performer", ""),
                "index01": c.get("index01", 0),
                "end_ms": c.get("end_ms"),
            })
            self.file_list.addItem(self._make_item(track))
            self.current_playlist.append(track)
        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
        self.path_label.setText(f"CUE: {os.path.basename(cue_path)}")
        self.file_list.setUpdatesEnabled(True)
        self.update_now_playing_marker()

    def show_directory(self, path):
        log(f"[介面] show_directory {path}", 20)
        self.current_dir = path
        self._pending_folder_list = []
        self.current_playlist = []
        self.current_track_index = -1
        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        back = QListWidgetItem("[..]  (返回)")
        back.setData(Qt.ItemDataRole.UserRole, {"path": "ACTION_BACK"})
        self.file_list.addItem(back)

        try:
            entries = sorted(os.listdir(path))
            valid_ext = (
                '.mp3', '.wav', '.ogg', '.m4a', '.flac',
                '.dnm', '.ftm', '.it', '.mid', '.midi', '.mod',
                '.mptm', '.mt2', '.rmi', '.s3m', '.sap', '.sid',
                '.tm8', '.xm', '.vgm', '.vgz', '.swf',
                '.opus', '.alac', '.aac', '.wma'
            )
            folders = [e for e in entries if os.path.isdir(os.path.join(path, e))]
            files = [e for e in entries if e.lower().endswith(valid_ext)]
            cue_files = [e for e in entries if e.lower().endswith(('.cue', '.cue.txt'))]
            m3u_files = [e for e in entries if e.lower().endswith(('.m3u', '.m3u8'))]

            for f in folders:
                item = QListWidgetItem(f"[目錄]  {f.lower()}/")
                item.setData(Qt.ItemDataRole.UserRole, {"path": os.path.join(path, f), "is_dir": True})
                self.file_list.addItem(item)

            for f in cue_files:
                cue_path = os.path.join(path, f)
                item = QListWidgetItem(f"[CUE]  {f.lower()}")
                item.setData(Qt.ItemDataRole.UserRole, {"path": cue_path, "is_cue": True})
                self.file_list.addItem(item)

            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in ('.dnm', '.ftm') and not self.furnace_available:
                    continue
                if ext in ('.sid', '.vgm', '.vgz') and not self.zxtune_available:
                    continue
                fpath = os.path.join(path, f)
                self._pending_folder_list.append(fpath)
                track = self._track_from_path(fpath)
                self.file_list.addItem(self._make_item(track))
                self.current_playlist.append(track)

            for f in m3u_files:
                item = QListWidgetItem(f"[M3U]  {f.lower()}")
                item.setData(Qt.ItemDataRole.UserRole, {"path": os.path.join(path, f), "is_m3u": True})
                self.file_list.addItem(item)

        except Exception as e:
            log(f"[目錄] 無法列出 {path}: {e}", 30)
            self.show_source_list()
            self.file_list.setUpdatesEnabled(True)
            return

        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
        self.path_label.setText(path)
        self.file_list.setUpdatesEnabled(True)

    def _update_item_duration(self, filename, dur_ms):
        for idx in range(self.file_list.count()):
            item = self.file_list.item(idx)
            t = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(t, dict):
                continue
            target = t.get("path")
            if target and os.path.basename(target) == filename:
                text = item.text()
                prefix = ""
                if text.startswith("▶ "):
                    prefix = "▶ "
                    text = text[2:]
                if text.startswith("[音訊"):
                    rest = text.split("]", 1)[1] if "]" in text else " " + filename.lower()
                else:
                    rest = " " + filename.lower()
                tag = self._make_audio_tag(dur_ms, self.show_duration)
                item.setText(f"{prefix}{tag}{rest}")
                break

    def refresh_current_directory(self):
        if self.current_dir and os.path.isdir(self.current_dir):
            self.show_directory(self.current_dir)
        elif self.current_dir and self.current_dir.startswith("CUE:"):
            self.show_cue_list(self.current_dir[4:])
        elif self.current_dir and self.current_dir.startswith("M3U:"):
            self.show_m3u_list(self.current_dir[4:])
        elif self.current_dir == "HISTORY":
            self.show_history_list()
        elif self.current_dir == "MOST_PLAYED":
            self.show_most_played_list()
        elif self.current_dir and self.current_dir.startswith("FAVORITES:"):
            self.show_favorites_list(self.current_dir.split(":")[1])
        else:
            self.show_source_list()

    def handle_selection(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            log(f"[介面] handle_selection 非 dict 資料: {data!r}", 30)
            return
        log(f"[介面] handle_selection path={data.get('path')}", 20)
        if data.get("path") == "ACTION_BACK":
            self.go_back()
            return
        if data.get("is_source"):
            p = data["path"]
            if p == "HISTORY":
                self.show_history_list()
            elif p == "MOST_PLAYED":
                self.show_most_played_list()
            elif p.startswith("FAVORITES:"):
                self.show_favorites_list(p.split(":")[1])
            elif p.startswith("http"):
                self.play_file(self._track_from_path(p))
            elif os.path.isdir(p):
                self.show_directory(p)
            elif os.path.isfile(p):
                self.play_file(self._track_from_path(p))
            else:
                log(f"[介面] handle_selection 未知來源路徑: {p}", 30)
                self.track_status.setText(f"遺失: {self.get_display_name(p)}")
            return
        if data.get("is_dir"):
            self.show_directory(data["path"])
            return
        if data.get("is_m3u"):
            self.show_m3u_list(data["path"])
            return
        if data.get("is_cue"):
            self.show_cue_list(data["path"])
            return
        self.play_file(data)

    def go_back(self):
        if self.current_dir is None:
            return
        if self.current_dir in ("HISTORY", "MOST_PLAYED") or self.current_dir.startswith("FAVORITES:"):
            self.show_source_list()
        elif self.current_dir.startswith("CUE:"):
            cue_path = self.current_dir[4:]
            parent_dir = os.path.dirname(cue_path)
            if any(os.path.abspath(parent_dir) == os.path.abspath(p) for p in self.source_paths) or parent_dir == cue_path:
                self.show_source_list()
            else:
                self.show_directory(parent_dir)
        elif self.current_dir.startswith("M3U:"):
            m3u_path = self.current_dir[4:]
            parent_dir = os.path.dirname(m3u_path)
            if any(os.path.abspath(parent_dir) == os.path.abspath(p) for p in self.source_paths) or parent_dir == m3u_path:
                self.show_source_list()
            else:
                self.show_directory(parent_dir)
        else:
            parent = os.path.dirname(self.current_dir)
            if os.path.abspath(self.current_dir) in [os.path.abspath(p) for p in self.source_paths] or parent == self.current_dir:
                self.show_source_list()
            else:
                self.show_directory(parent)

    # ================== 頻譜 ==================
    def update_spectrum_bars(self):
        if not self.show_audio_level:
            self.text_eq.set_levels(0.0, 0.0, 0.0, 0.0)
            return

        if self.engine_mode == ENGINE_MODE_VLC:
            self.text_eq.set_levels(0.0, 0.0, 0.0, 0.0)
            return

        if self.audio_level_source == "system":
            b, m, t, v = self._calculate_system_spectrum()
        else:
            b, m, t, v = 0.0, 0.0, 0.0, 0.0
            source = self.spectrum_source_path if self.spectrum_source_path else self.current_file_path
            if not source:
                self.text_eq.set_levels(0.0, 0.0, 0.0, 0.0)
                return

            if self.current_engine == 'bass' and self.bass_engine.is_playing():
                if not source.startswith("http"):
                    if not self.bass_engine._decode_handle or self.bass_engine._decode_filepath != source:
                        self.bass_engine.open_decode_stream(source)
                    if self.bass_engine._decode_handle:
                        curr_ms, _ = self.bass_engine.get_time()
                        if curr_ms >= 0:
                            b, m, t = self.bass_engine.get_spectrum_bands_from_decode(curr_ms)
                left, right = self.bass_engine.get_level()
                v = (left + right) / 2.0
            elif self.current_engine in ('vlc', 'libopenmpt', 'asap', 'zxtune', 'chiptune_cli', 'cached'):
                if self.bass_available and source and not source.startswith("http"):
                    if not self.bass_engine._decode_handle or self.bass_engine._decode_filepath != source:
                        self.bass_engine.open_decode_stream(source)
                    if self.bass_engine._decode_handle and self.vlc_player is not None:
                        curr_ms = self.vlc_player.get_time()
                        if curr_ms >= 0:
                            b, m, t = self.bass_engine.get_spectrum_bands_from_decode(curr_ms)
                v = 0.0

        smoothing = 0.3
        self._smooth_bass = self._smooth_bass + (b - self._smooth_bass) * smoothing
        self._smooth_mid = self._smooth_mid + (m - self._smooth_mid) * smoothing
        self._smooth_treble = self._smooth_treble + (t - self._smooth_treble) * smoothing
        self._smooth_volume = self._smooth_volume + (v - self._smooth_volume) * smoothing
        self.text_eq.set_levels(self._smooth_bass, self._smooth_mid, self._smooth_treble, self._smooth_volume)

    # ================== 時間 ==================
    def format_time(self, ms):
        if ms is None or ms < 0:
            return self._time_placeholder()
        total_seconds = ms // 1000
        m, s = divmod(total_seconds, 60)
        if self.time_format == TIME_FORMAT_MM_SS_CC:
            centis = (ms % 1000) // 10
            return f"{m:02d}:{s:02d}.{centis:02d}"
        else:
            return f"{m:02d}:{s:02d}"

    def _time_placeholder(self):
        if self.time_format == TIME_FORMAT_MM_SS_CC:
            return "--:--.--"
        return "--:--"

    def update_ui(self):
        state = vlc.State.Stopped
        curr_ms = 0
        total_ms = -1
        if self.current_engine in ('vlc', 'libopenmpt', 'asap', 'zxtune', 'chiptune_cli', 'cached'):
            if self.vlc_player is not None:
                try:
                    state = self.vlc_player.get_state()
                    pos = self.vlc_player.get_position() or 0
                    curr_ms = self.vlc_player.get_time() or 0
                    total_ms = self.vlc_player.get_length() or -1
                except Exception:
                    pos = 0
                if state == vlc.State.Playing:
                    self.progress_text.setValue(int(pos * 1000))
                    if self.track_status.text() not in ("已暫停", "播放中 (快取)"):
                        self.track_status.setText("播放中")
                elif state == vlc.State.Paused:
                    self.track_status.setText("已暫停")
                else:
                    if self.track_status.text() not in ("播放中 (快取)",):
                        self.track_status.setText("已停止")
        elif self.current_engine == 'bass':
            if self.bass_engine.is_playing():
                pos = self.bass_engine.get_position()
                self.progress_text.setValue(int(pos * 1000))
                curr_ms, total_ms = self.bass_engine.get_time()
                self.track_status.setText("播放中")
            else:
                self.track_status.setText("已停止")

        curr_str = self.format_time(curr_ms)
        total_str = self.format_time(total_ms) if total_ms > 0 else self._time_placeholder()
        bar_text = self.progress_text.text().split("]")[0] + "]"
        self.progress_text.setText(f"{bar_text} {curr_str} / {total_str}")

        if self.current_file_path:
            track_name = self.get_display_name(self.current_file_path)
            self.tray_icon.setToolTip(f"dem_player - {track_name}")
        else:
            self.tray_icon.setToolTip(f"dem_player {APP_VERSION}")

    def closeEvent(self, event):
        log("=== 播放器關閉中 ===", 20)
        self.timer.stop()
        self.spectrum_timer.stop()
        self._save_cache_timer.stop()
        self._cue_end_timer.stop()
        self._write_cache()
        self.stop_system_audio_capture()
        self.stop_current_engine()
        if self.conv_thread and self.conv_thread.isRunning():
            self.conv_thread.requestInterruption()
            self.conv_thread.wait(1000)
        self.bass_engine.free()
        for wav in self.convert_cache.values():
            if os.path.exists(wav):
                try:
                    os.remove(wav)
                except Exception:
                    pass
        try:
            self.tray_icon.hide()
        except Exception:
            pass
        if self.drag_frame is not None:
            try:
                self.drag_frame.hide()
                self.drag_frame.deleteLater()
            except Exception:
                pass
            self.drag_frame = None
        self._save_all_data()
        close_log()
        super().closeEvent(event)


# ================== 主程式 ==================
if __name__ == "__main__":
    try:
        apply_cpu_affinity()
        init_log()
        log("=== 播放器啟動 ===", 20)
        log(f"版本 {APP_VERSION}", 20)
        log(f"app_dir = {app_dir()}", 20)
        log(f"SETTINGS_FILE = {SETTINGS_FILE}", 20)
        log(f"PLAYLIST_FILE = {PLAYLIST_FILE}", 20)
        log(f"HISTORY_FILE = {HISTORY_FILE}", 20)
        log(f"CACHE_FILE = {CACHE_FILE}", 20)
        log(f"Python {sys.version}, 平台: {sys.platform}", 20)
        log(f"Frozen={getattr(sys, 'frozen', False)}, numpy={HAS_NUMPY}, sounddevice={HAS_SOUNDDEVICE}, mutagen={HAS_MUTAGEN}", 20)
        os.environ["QT_OPENGL"] = "software"
        os.environ["QT_QPA_PLATFORM"] = "windows"
        os.environ["QT_SCALE_FACTOR"] = "1"
        log("Qt 環境已設定", 20)
        app = QApplication(sys.argv)
        icon_path = resource_path("FPT.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        win = MusicRoom()
        win.show()
        log("視窗顯示成功", 20)
        sys.exit(app.exec())
    except Exception as e:
        log(f"致命錯誤: {e}\n{traceback.format_exc()}", 40)
        print(f"\n程式崩潰: {e}")
        print(traceback.format_exc())
        sys.exit(1)
