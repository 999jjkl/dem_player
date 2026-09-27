"""dem_player 0.21 — PySide6 UI. Playback via audio.AudioEngine (no VLC / no BASS)."""
import sys
import os
import shutil
import re
import traceback
from collections import OrderedDict

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QFrame, QSlider, QSizePolicy,
    QInputDialog, QLineEdit, QStackedWidget, QPushButton, QMessageBox,
    QSystemTrayIcon, QMenu, QStyle, QFileDialog, QDialog, QTextEdit,
    QDialogButtonBox
)
from PySide6.QtCore import Qt, QTimer, QEvent, Slot, QPoint
from PySide6.QtGui import (
    QFont, QKeyEvent, QFontDatabase, QPainter, QColor, QPen, QFontMetrics,
    QPixmap, QIcon, QAction, QGuiApplication, QTextCursor, QTextCharFormat,
    QImageReader
)

from core import (
    APP_VERSION, TIME_FORMAT_MM_SS, TIME_FORMAT_MM_SS_CC,
    app_dir, data_path, resource_path, logs_dir,
    init_log, log, close_log,
    parse_cue_file, parse_m3u, read_metadata as core_read_metadata,
    prevent_sleep, apply_cpu_affinity, HAS_MUTAGEN,
)
import core as core_mod
from storage import (
    SETTINGS_FILE, PLAYLIST_FILE, HISTORY_FILE, CACHE_FILE,
    BACKGROUND_DIR, CUSTOM_BACKGROUND_FILENAME, BG_MAX_BYTES, BG_MAX_DIM,
    DEFAULT_SETTINGS,
    load_settings, save_settings, load_playlist_data, save_playlist_data,
    load_history_data, save_history_data, load_cache, save_cache,
    migrate_old_files_if_needed,
)
from audio import (
    AudioEngine, list_output_devices, HAS_MINIAUDIO,
    probe_ffmpeg, probe_openmpt, probe_fluidsynth, probe_soundfont,
)
from converters import ConversionThread, FurnaceConverter, AsapConverter, ZxtuneConverter

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

QWIDGETSIZE_MAX = 16777215

# ---------- custom font ----------
def load_custom_font():
    font_path = resource_path("font.ttf")
    if os.path.isfile(font_path):
        try:
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    print(f"[Font] Loaded custom font: {families[0]}")
                    return families[0]
        except Exception as e:
            print(f"[Font] Failed to load custom font: {e}")
    return None


# ---------- drag frame ----------
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


# ---------- scrolling label ----------
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


# ---------- text bar ----------
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


# ---------- text EQ ----------
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
        self.names = ["Bass:", "Mid:", "Treble:", "Volume:"]
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


# ---------- about / device dialogs ----------
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
        self.setWindowTitle(f"About dem_player {APP_VERSION}")
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
        self.copy_btn = btns.addButton("Copy Info", QDialogButtonBox.ButtonRole.ActionRole)
        self.close_btn = btns.addButton("Close", QDialogButtonBox.ButtonRole.AcceptRole)
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

        default_item = QListWidgetItem("System Default")
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
        ok_btn = btns.addButton("Apply", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = btns.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
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


# ---------- main window ----------
class MusicRoom(QMainWindow):
    THEMES = [
        ("Black & White",      "#000000", "#FFFFFF"),
        ("Black & Green",      "#000000", "#00FF00"),
        ("Black & Red",        "#000000", "#FF0000"),
        ("Black & Orange",     "#000000", "#FFA500"),
        ("Black & Blue",       "#000000", "#0084ff"),
        ("Black & Purple",     "#000000", "#d000ff"),
        ("Black & Cyan",       "#000000", "#00FFFF"),
        ("Black & Yellow",     "#000000", "#FFFF00"),
        ("Black & Magenta",    "#000000", "#FF00FF"),
        ("Mystic Purple & Neon Pink",       "#6a0dad", "#ff0080"),
        ("Neon Pink & Mystic Purple",       "#ff0080", "#6a0dad"),
        ("Steel Shadow & Neon cyan",     "#2c2c34", "#00d4ff"),
        ("Neon cyan & Steel Shadow",     "#00d4ff", "#2c2c34"),
        ("Lime Flash & Carbon Black",     "#bfff00", "#222222"),
        ("Royal Violet & Golden Wealth",     "#7b2cbf", "#f9d308"),
        ("Golden Wealth & Royal Violet",     "#f9d308", "#7b2cbf"),
    ]

    LEVEL_SUPPORTED_EXT = ('.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac', '.wma', '.opus', '.alac')

    def __init__(self):
        super().__init__()

        log(f"MusicRoom __init__ started (v{APP_VERSION})", 20)

        self.setWindowTitle(f"dem_player {APP_VERSION}")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.has_custom_border = True
        self.drag_position = QPoint()
        self.setFixedSize(900, 600)

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
        self.custom_background_path = settings.get("custom_background_path", "") or ""
        self.is_always_on_top = settings.get("always_on_top", False)
        self.time_format = settings.get("time_format", TIME_FORMAT_MM_SS_CC)
        if self.time_format not in (TIME_FORMAT_MM_SS, TIME_FORMAT_MM_SS_CC):
            self.time_format = TIME_FORMAT_MM_SS_CC

        self.output_device = settings.get("output_device", "") or ""
        self.show_advanced_audio = False
        self.engine_mode = "auto"

        core_mod.LOG_ENABLED = bool(log_enabled)
        core_mod.LOG_LEVEL = settings.get("log_level", 20)
        if core_mod.LOG_ENABLED and core_mod.LOG_FILE is None:
            init_log()

        log(f"Settings: theme={self.current_theme_index}, loop={self.loop_mode}, "
            f"vol={self.initial_volume}, time_format={self.time_format}, "
            f"output_device='{self.output_device}'", 20)
        log(f"Sources: {len(self.source_paths)} paths, Favorites: {len(self.favorites)} lists", 20)
        log(f"History: {len(self.history_paths)} entries, {len(self.play_counts)} play counts", 20)

        if self.current_theme_index < 0 or self.current_theme_index >= len(self.THEMES):
            self.current_theme_index = 0
        self.bg_color = self.THEMES[self.current_theme_index][1]
        self.accent_color = self.THEMES[self.current_theme_index][2]

        if self.is_always_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.furnace_available = FurnaceConverter.available()
        self.asap_available = AsapConverter.available()
        self.zxtune_available = ZxtuneConverter.available()
        self.libopenmpt_available = bool(probe_openmpt())
        self.fluidsynth_available = bool(probe_fluidsynth())
        self.soundfont_available = bool(probe_soundfont())
        self.ffmpeg_available = bool(probe_ffmpeg())

        def _qt_on_end():
            QTimer.singleShot(0, self.on_media_end)

        self.audio_engine = AudioEngine(device_name=self.output_device, on_end=_qt_on_end)
        self.audio_engine.set_volume(self.initial_volume)
        log(f"[Audio] engine ready miniaudio={HAS_MINIAUDIO} device='{self.output_device}'", 20)


        self.bg_pixmap = None
        self._bg_scaled = None
        self._bg_scaled_for = None

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
        self.current_engine = 'miniaudio'
        self.temp_wav = None
        self.conv_thread = None
        self.spectrum_source_path = None

        self.convert_cache = OrderedDict()
        self.cache_max_size = 10

        self.loop_mode_names = ["OFF", "SINGLE", "LIST"]

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

        # --- end-of-track tracking (fix for PySide6) ---
        self._media_end_handled = False

        try:
            self.build_ui()
        except Exception as e:
            log(f"build_ui CRASHED: {e}\n{traceback.format_exc()}", 40)

        try:
            self.apply_theme()
        except Exception as e:
            log(f"apply_theme failed: {e}", 40)

        self.audio_level_frame.setVisible(self.show_audio_level)
        self.text_eq.fix_widths(self.dos_font)
        self.text_eq.set_mode(self.audio_level_mode)
        self.cover_label.setVisible(False)
        self.loop_label.setText(f"Loop: {self.loop_mode_names[self.loop_mode]}")

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

        # Tray
        self.tray_icon = QSystemTrayIcon(self)
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.tray_icon.setToolTip(f"dem_player {APP_VERSION}")
        self.tray_menu = QMenu()
        self.tray_pause_action = QAction("stop")
        self.tray_pause_action.triggered.connect(self.toggle_pause)
        self.tray_prev_action = QAction("Previous song")
        self.tray_prev_action.triggered.connect(self._tray_prev)
        self.tray_next_action = QAction("Next song")
        self.tray_next_action.triggered.connect(self.play_next_in_list)
        self.tray_quit_action = QAction("quit")
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
            log(f"show_source_list failed: {e}", 40)

        try:
            self.set_normal_mode()
        except Exception as e:
            log(f"set_normal_mode failed: {e}", 40)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(250)

        self.spectrum_timer = QTimer(self)
        self.spectrum_timer.timeout.connect(self.update_spectrum_bars)
        self.spectrum_timer.start(50)

        if self.audio_level_source == "system":
            self.start_system_audio_capture()

        log("=== Player Init Completed Successfully ===", 20)

    # ================== AUDIO DEVICE HELPERS ==================

    @staticmethod
    def _normalize_device_name(s):
        if not s:
            return ""
        s = s.lower()
        s = re.sub(r"\(.*?\)", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _main_output_device_label(self):
        if not self.output_device:
            return "System Default"
        for did, desc in list_output_devices():
            if str(did) == str(self.output_device) or desc == self.output_device:
                return desc or did
        return self.output_device

    def _switch_output_device(self, device_id):
        log(f"[Audio] Switch request: '{device_id}'", 20)
        resume_track = self.current_track_info
        was_playing = False
        try:
            was_playing = self.audio_engine.is_playing()
        except Exception:
            was_playing = False
        try:
            self.stop_current_engine()
        except Exception:
            pass
        prevent_sleep(False)
        self.output_device = device_id or ""
        self.audio_engine.set_device_name(self.output_device)
        self._save_settings()
        self.update_settings_list()
        if resume_track is not None:
            if was_playing:
                QTimer.singleShot(400, lambda t=resume_track: self.play_file(t))
                self.track_status.setText("Switching audio device...")
            else:
                self.track_status.setText("Audio device changed")
        else:
            self.track_status.setText("Audio device changed")

    def pick_main_device(self):
        devices = list_output_devices()
        dlg = DevicePickerDialog(
            self, "Output Device", devices,
            self.accent_color, self.dos_font, current_id=self.output_device)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_id = dlg.selected_id or ""
            self._switch_output_device(new_id)

    def _current_settings_dict(self):
        return {
            "theme_index": self.current_theme_index,
            "show_play_counts": self.show_play_counts,
            "log_enabled": core_mod.LOG_ENABLED,
            "log_level": core_mod.LOG_LEVEL,
            "show_duration": self.show_duration,
            "audio_level_mode": self.audio_level_mode,
            "show_cover_art": self.show_cover_art,
            "show_audio_level": self.show_audio_level,
            "audio_level_source": self.audio_level_source,
            "loop_mode": self.loop_mode,
            "volume": self.volume_text.value() if hasattr(self, "volume_text") else self.initial_volume,
            "window_mode": self.window_mode,
            "background_mode": self.background_mode,
            "custom_background_path": getattr(self, "custom_background_path", ""),
            "always_on_top": self.is_always_on_top,
            "time_format": self.time_format,
            "output_device": getattr(self, "output_device", ""),
            "engine_mode": "auto",
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

    # ================== CACHE ==================
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
        self.audio_engine.set_volume(vol)
    def mousePressEvent(self, event):
        if event.position().y() < 40 and event.button() == Qt.MouseButton.LeftButton:
            self._drag_press_pos = event.globalPosition().toPoint()
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._drag_started = False
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
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

    # ================== UI ==================
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
        self.browser_label = QLabel("FILE BROWSER")
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
        title_label = QLabel("SETTING")
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
        track_label = QLabel("Track:")
        track_label.setFont(self.dos_font)
        track_title_row.addWidget(track_label)
        self.track_title = ScrollingLabel("------------------------")
        self.track_title.setFont(self.dos_font)
        self.track_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        track_title_row.addWidget(self.track_title, 1)
        right_layout.addLayout(track_title_row)

        self.meta_label = QLabel("Artist: -   Album: -   Track#: -")
        self.meta_label.setFont(self.dos_font)
        right_layout.addWidget(self.meta_label)

        self.progress_text = TextBar(max_val=1000, bar_length=30, show_percent=False)
        self.progress_text.setFont(self.dos_font)
        right_layout.addWidget(self.progress_text)

        self.status_frame = QFrame()
        status_loop_layout = QHBoxLayout(self.status_frame)
        status_loop_layout.setContentsMargins(4, 2, 4, 2)
        self.track_status = QLabel("Stopped")
        self.track_status.setFont(self.dos_font)
        status_loop_layout.addWidget(self.track_status)
        status_loop_layout.addStretch()
        self.loop_label = QLabel("Loop: OFF")
        self.loop_label.setFont(self.dos_font)
        status_loop_layout.addWidget(self.loop_label)
        right_layout.addWidget(self.status_frame)

        self.volume_text = TextBar(max_val=100, bar_length=20, show_percent=True)
        self.volume_text.prefix = "Volume (F2/F3)"
        self.volume_text.setFont(self.dos_font)
        right_layout.addWidget(self.volume_text)

        self.audio_level_frame = QFrame()
        audio_level_layout = QVBoxLayout(self.audio_level_frame)
        audio_level_layout.setContentsMargins(0, 0, 0, 0)
        self.audio_level_title = QLabel("Audio Level:")
        self.audio_level_title.setFont(self.dos_font)
        audio_level_layout.addWidget(self.audio_level_title)
        self.text_eq = TextEQWidget(self, accent_color=self.accent_color)
        audio_level_layout.addWidget(self.text_eq)
        right_layout.addWidget(self.audio_level_frame)

        self.keys_label = QLabel(
            "Keys:\n"
            "[↑/↓] Nav  [ENTER] Open  [BS] Back\n"
            "[F1] Pause  [F2/F3] Vol  [F4] Hide\n"
            "[F5] Loop   [F6] Mode    [F7] Settings\n"
            "[F8] Search [F9] Favs  [Esc] Reset  [←/→] -/+1s"
        )
        self.keys_label.setFont(self.dos_font)
        self.keys_label.setWordWrap(False)
        right_layout.addWidget(self.keys_label)

        self.search_frame = QFrame()
        search_layout = QHBoxLayout(self.search_frame)
        search_layout.setContentsMargins(4, 4, 4, 4)
        search_label = QLabel("search:")
        search_label.setFont(self.dos_font)
        self.search_input = QLineEdit()
        self.search_input.setFont(self.dos_font)
        self.search_input.setPlaceholderText("...")
        self.search_input.returnPressed.connect(self.do_search)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        right_layout.addWidget(self.search_frame)

        self.mini_keys_label = QLabel("[F6] Mode  [F7] Settings  [F8] Search  [F9] Favs  [Esc] Reset")
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
        if (self.background_mode == "image"
                and self.bg_pixmap and not self.bg_pixmap.isNull()):
            cur = self.size()
            if self._bg_scaled is None or self._bg_scaled_for != cur:
                self._bg_scaled = self.bg_pixmap.scaled(
                    cur,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)
                self._bg_scaled_for = cur
            painter.drawPixmap(0, 0, self._bg_scaled)
            painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        if self.has_custom_border:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(QColor(self.accent_color), 2)
            painter.setPen(pen)
            painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        painter.end()
        super().paintEvent(event)

    def apply_background_image(self):
        self.bg_pixmap = None
        self._bg_scaled = None
        self._bg_scaled_for = None

        if self.background_mode == "image":
            custom_path = getattr(self, "custom_background_path", "") or ""
            if custom_path and os.path.isfile(custom_path):
                pm = QPixmap(custom_path)
                if not pm.isNull():
                    self.bg_pixmap = pm
            if self.bg_pixmap is None:
                builtin = resource_path("background.png")
                if os.path.isfile(builtin):
                    pm = QPixmap(builtin)
                    if not pm.isNull():
                        self.bg_pixmap = pm
            if self.bg_pixmap is None:
                self.background_mode = "solid"

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
        self.update()

    # ================== SETTINGS UI ==================

    def update_settings_list(self):
        self.settings_list.clear()
        top_state = "Y" if self.is_always_on_top else "N"
        self.settings_list.addItem(f"Always on Top                        [{top_state}]")
        style_name = self.THEMES[self.current_theme_index][0]
        self.settings_list.addItem(f"Style                                [{style_name}]")
        level_state = "Y" if self.show_audio_level else "N"
        self.settings_list.addItem(f"Audio Level                          [{level_state}]")
        self.settings_list.addItem(f"Audio Level Source                   [{self.audio_level_source}]")
        self.settings_list.addItem(f"Audio Level Mode                     [{self.audio_level_mode}]")
        main_label = self._main_output_device_label()
        self.settings_list.addItem(f"Output Device                        [{main_label}]")
        count_state = "Y" if self.show_play_counts else "N"
        self.settings_list.addItem(f"Show Play Counts                     [{count_state}]")
        self.settings_list.addItem("Background Image...")
        self.settings_list.addItem("Clear Background Image")
        _bg_state = self.background_mode
        if (self.background_mode == "image"
                and getattr(self, "custom_background_path", "")
                and os.path.isfile(self.custom_background_path)):
            _bg_state = "image (custom)"
        self.settings_list.addItem(f"Background                           [{_bg_state}]")
        log_state = "Y" if core_mod.LOG_ENABLED else "N"
        self.settings_list.addItem(f"Log Save                             [{log_state}]")
        dur_state = "Y" if self.show_duration else "N"
        self.settings_list.addItem(f"Show Duration                        [{dur_state}]")
        cover_state = "Y" if self.show_cover_art else "N"
        self.settings_list.addItem(f"Show Cover Art                       [{cover_state}]")
        time_label = "MM:SS.CC" if self.time_format == TIME_FORMAT_MM_SS_CC else "MM:SS"
        self.settings_list.addItem(f"Time Format                          [{time_label}]")
        self.settings_list.addItem("--- Music Folders ---")
        for i, p in enumerate(self.source_paths):
            self.settings_list.addItem(f"Remove Folder                        [{i}] {p}")
        self.settings_list.addItem("Add Music Folder...")
        self.settings_list.addItem("Refresh File List")
        self.settings_list.addItem("--- Maintenance ---")
        self.settings_list.addItem("Clear History")
        self.settings_list.addItem("Clear Play Counts")
        self.settings_list.addItem("Clear Favorites")
        self.settings_list.addItem("Clear Duration Cache")
        self.settings_list.addItem("Reset All Settings")
        self.settings_list.addItem("--- About ---")
        self.settings_list.addItem(f"About dem_player {APP_VERSION}")
    def on_setting_selected(self, item):
        text = item.text()
        if text.startswith("Always on Top"):
            self.toggle_always_on_top()
        elif text.startswith("Style"):
            self.cycle_theme()
        elif text.startswith("Audio Level Source"):
            self.toggle_audio_level_source()
        elif text.startswith("Audio Level Mode"):
            self.toggle_audio_level_mode()
        elif text.startswith("Audio Level"):
            self.toggle_audio_level_display()
        elif "Output Device" in text:
            self.pick_main_device()
        elif text.startswith("Show Play Counts"):
            self.toggle_show_play_counts()
        elif text.startswith("Background Image..."):
            self.pick_background_image()
        elif text.startswith("Clear Background Image"):
            self.clear_background_image()
        elif text.startswith("Background"):
            self.cycle_background_mode()
        elif text.startswith("Log Save"):
            self.toggle_log_enabled()
        elif text.startswith("Show Duration"):
            self.show_duration = not self.show_duration
            self._save_settings()
            if self.current_dir:
                self.refresh_current_directory()
        elif text.startswith("Show Cover Art"):
            self.show_cover_art = not self.show_cover_art
            self._save_settings()
            self.load_cover_art(self.current_file_path)
        elif text.startswith("Time Format"):
            self.toggle_time_format()
        elif text.startswith("Remove Folder"):
            m = re.search(r"\[(\d+)\]", text)
            if m:
                idx = int(m.group(1))
                if 0 <= idx < len(self.source_paths):
                    removed = self.source_paths[idx]
                    reply = QMessageBox.question(
                        self,
                        "Confirm Removal",
                        f"Remove this music folder from the list?\n\n{removed}\n\n"
                        f"(Removed from the list only. Files on disk are NOT deleted.)",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                    self.source_paths.pop(idx)
                    self._save_playlist()
                    self.track_status.setText(f"Removed: {removed}")
                    log(f"[Settings] Removed source folder: {removed}", 20)
        elif text.startswith("Add Music Folder"):
            folder = QFileDialog.getExistingDirectory(self, "Select music folder")
            if folder:
                if folder not in self.source_paths:
                    self.source_paths.append(folder)
                    self._save_playlist()
                    self.track_status.setText(f"Added: {folder}")
                    log(f"[Settings] Added folder: {folder}", 20)
                else:
                    self.track_status.setText("Folder already in list")
        elif text.startswith("Refresh File List"):
            self.refresh_current_directory()
        elif text.startswith("Clear History"):
            reply = QMessageBox.question(self, "Confirm", "Clear all play history?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.history_paths = []
                self._save_history()
                self.track_status.setText("History cleared")
                log("[Settings] History cleared", 20)
        elif text.startswith("Clear Play Counts"):
            reply = QMessageBox.question(self, "Confirm", "Clear all play counts?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.play_counts = {}
                self._save_history()
                self.track_status.setText("Play counts cleared")
                log("[Settings] Play counts cleared", 20)
        elif text.startswith("Clear Favorites"):
            reply = QMessageBox.question(self, "Confirm", "Clear all favorites lists?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.favorites = {}
                self._save_playlist()
                self.track_status.setText("Favorites cleared")
                log("[Settings] Favorites cleared", 20)
        elif text.startswith("Clear Duration Cache"):
            reply = QMessageBox.question(self, "Confirm",
                "Clear duration cache? Duration labels will be re-scanned.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.folder_cache.clear()
                self._mark_cache_dirty()
                self._write_cache()
                if self.current_dir:
                    self.refresh_current_directory()
                self.track_status.setText("Cache cleared")
                log("[Settings] Duration cache cleared", 20)
        elif text.startswith("Reset All Settings"):
            reply = QMessageBox.question(self, "Confirm", "Reset all settings to default?",
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
                self.custom_background_path = ""
                try:
                    _p = os.path.join(BACKGROUND_DIR, CUSTOM_BACKGROUND_FILENAME)
                    if os.path.exists(_p):
                        os.remove(_p)
                except Exception as e:
                    log(f"[BG] reset remove failed: {e}", 30)
                self.is_always_on_top = False
                self.time_format = TIME_FORMAT_MM_SS_CC
                self.output_device = ""
                self.engine_mode = "auto"
                self.bg_color = self.THEMES[0][1]
                self.accent_color = self.THEMES[0][2]
                self.volume_text.setValue(50)
                self.apply_theme()
                self._save_settings()
                self.track_status.setText("Settings reset")
                log("[Settings] All settings reset to default", 20)
        elif text.startswith("About dem_player"):
            self.show_about_dialog()
        self.update_settings_list()

    def toggle_time_format(self):
        if self.time_format == TIME_FORMAT_MM_SS_CC:
            self.time_format = TIME_FORMAT_MM_SS
        else:
            self.time_format = TIME_FORMAT_MM_SS_CC
        self._save_settings()
        log(f"[Settings] Time format = {self.time_format}", 20)
        self.update_ui()

    def show_about_dialog(self):
        info = self._build_about_text()
        try:
            dlg = AboutDialog(self, info, self.accent_color, self.dos_font)
            dlg.exec()
        except Exception as e:
            log(f"[About] dialog failed: {e}", 40)
            QMessageBox.information(self, f"About dem_player {APP_VERSION}", info)


    def _build_about_text(self):
        yesno = lambda v: "yes" if v else "no"
        window_names = {0: "normal", 1: "fullscreen", 2: "mini", 3: "bar"}
        theme_name = self.THEMES[self.current_theme_index][0] if 0 <= self.current_theme_index < len(self.THEMES) else "-"
        log_path = ""
        try:
            if core_mod.LOG_FILE is not None:
                log_path = getattr(core_mod.LOG_FILE, "name", "") or ""
        except Exception:
            log_path = ""
        custom_ok = bool(getattr(self, "custom_background_path", "")) and os.path.isfile(self.custom_background_path)
        backend = self.audio_engine.current_name or getattr(self, "current_engine", "") or "-"
        paused = False
        playing = False
        try:
            playing = self.audio_engine.is_playing()
            paused = self.audio_engine.is_paused()
        except Exception:
            pass
        if paused:
            play_state = "paused"
        elif playing:
            play_state = "playing"
        else:
            play_state = "stopped"

        lines = []
        lines.append(f"dem_player {APP_VERSION}")
        lines.append("")
        lines.append("--- Environment ---")
        lines.append(f"Python      : {sys.version.splitlines()[0]}")
        lines.append(f"Platform    : {sys.platform}")
        lines.append(f"Frozen      : {getattr(sys, 'frozen', False)}")
        lines.append(f"numpy       : {HAS_NUMPY}")
        lines.append(f"sounddevice : {HAS_SOUNDDEVICE}")
        lines.append(f"mutagen     : {HAS_MUTAGEN}" + ("" if HAS_MUTAGEN else "  (metadata disabled)"))
        lines.append(f"miniaudio   : {HAS_MINIAUDIO}")
        lines.append(f"executable  : {sys.executable}")
        lines.append(f"cwd         : {os.getcwd()}")
        lines.append("")
        lines.append("--- Engines (open-source) ---")
        lines.append("miniaudio   : MP3 / WAV / FLAC / OGG")
        lines.append(f"FFmpeg      : {probe_ffmpeg() or 'MISSING  (put ffmpeg.exe next to player)'}")
        lines.append(f"libopenmpt  : {probe_openmpt() or 'MISSING  (put openmpt123.exe for MOD/XM/IT/S3M/MPTM)'}")
        lines.append(f"FluidSynth  : {probe_fluidsynth() or 'MISSING  (put fluidsynth.exe or libfluidsynth-3.dll)'}")
        lines.append(f"soundfont   : {probe_soundfont() or 'MISSING  (put soundfont.sf2 for MIDI/RMI)'}")
        lines.append(f"furnace     : {self.furnace_available}")
        lines.append(f"asapconv    : {self.asap_available}")
        lines.append(f"zxtune      : {self.zxtune_available}")
        lines.append(f"engine mode : {self.engine_mode}")
        lines.append(f"current     : {backend}")
        lines.append("")
        lines.append("--- Data Files ---")
        lines.append(f"app_dir        : {app_dir()}")
        lines.append(f"settings.dpj   : {SETTINGS_FILE}")
        lines.append(f"play_list.dpj  : {PLAYLIST_FILE}")
        lines.append(f"play_history   : {HISTORY_FILE}")
        lines.append(f"cache.dpj      : {CACHE_FILE}")
        lines.append(f"log dir        : {logs_dir()}")
        lines.append(f"log file       : {log_path or '-'}")
        lines.append("")
        lines.append("--- Playback ---")
        lines.append(f"current engine : {backend}")
        lines.append(f"play state     : {play_state}")
        lines.append(f"current dir    : {self.current_dir}")
        lines.append(f"current file   : {self.current_file_path}")
        lines.append(f"playlist len   : {len(self.current_playlist)}")
        lines.append(f"track index    : {self.current_track_index}")
        lines.append(f"loop mode      : {self.loop_mode_names[self.loop_mode]}")
        lines.append(f"volume         : {self.volume_text.value()}")
        lines.append(f"output device  : {self._main_output_device_label()}")
        lines.append(f"  actual       : {self.audio_engine.device_name or 'System Default'}")
        lines.append("")
        lines.append("--- Audio Level ---")
        lines.append(f"show audio lvl : {self.show_audio_level}")
        lines.append(f"level source   : {self.audio_level_source}")
        lines.append(f"level mode     : {self.audio_level_mode}")
        lines.append("")
        lines.append("--- Settings Snapshot ---")
        lines.append(f"theme          : {theme_name}")
        lines.append(f"time format    : {self.time_format}")
        lines.append(f"window mode    : {window_names.get(self.window_mode, self.window_mode)}")
        lines.append(f"background     : {self.background_mode}")
        lines.append(f"custom bg      : {yesno(custom_ok)}")
        if custom_ok:
            lines.append(f"custom bg path : {self.custom_background_path}")
        lines.append(f"always on top  : {self.is_always_on_top}")
        lines.append(f"show duration  : {self.show_duration}")
        lines.append(f"show cover art : {self.show_cover_art}")
        lines.append(f"show play cnt  : {self.show_play_counts}")
        lines.append(f"log enabled    : {core_mod.LOG_ENABLED}")
        lines.append(f"log level      : {core_mod.LOG_LEVEL}")
        lines.append("")
        lines.append("--- Session ---")
        lines.append(f"sources       : {len(self.source_paths)}")
        lines.append(f"favorites     : {len(self.favorites)} lists")
        lines.append(f"history       : {len(self.history_paths)} entries")
        lines.append(f"play_counts   : {len(self.play_counts)} entries")
        lines.append(f"cache dirs    : {len(self.folder_cache)}")
        return "\n".join(lines)

    def cycle_background_mode(self):
        has_img = (
            (getattr(self, "custom_background_path", "")
             and os.path.isfile(self.custom_background_path))
            or os.path.isfile(resource_path("background.png"))
        )
        if self.background_mode == "transparent":
            self.background_mode = "solid"
        elif self.background_mode == "solid":
            self.background_mode = "image" if has_img else "transparent"
        else:
            self.background_mode = "transparent"
        self.apply_background_image()
        self._save_settings()

    def pick_background_image(self):
        src, _ = QFileDialog.getOpenFileName(
            self, "Select Background Image (PNG only, <= 5MB)", "", "PNG Image (*.png)")
        if not src:
            return

        if os.path.splitext(src)[1].lower() != ".png":
            QMessageBox.warning(self, "Cannot Use This Image", "Only PNG files are accepted")
            return

        try:
            src_size = os.path.getsize(src)
        except OSError as e:
            QMessageBox.warning(self, "Cannot Use This Image", f"Cannot read file: {e}")
            return
        if src_size > BG_MAX_BYTES:
            QMessageBox.warning(self, "Cannot Use This Image", "PNG file exceeds 5MB")
            return

        reader = QImageReader(src)
        reader.setAutoTransform(True)
        if not reader.canRead():
            QMessageBox.warning(self, "Cannot Use This Image", "Not a valid PNG image")
            return
        size = reader.size()
        if not size.isValid() or size.width() <= 0 or size.height() <= 0:
            QMessageBox.warning(self, "Cannot Use This Image", "Not a valid PNG image")
            return

        try:
            os.makedirs(BACKGROUND_DIR, exist_ok=True)
        except OSError as e:
            QMessageBox.warning(self, "Cannot Use This Image", f"Cannot create directory: {e}")
            return

        dst = os.path.join(BACKGROUND_DIR, CUSTOM_BACKGROUND_FILENAME)
        tmp = dst + ".tmp"
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass

        w, h = size.width(), size.height()
        need_resize = (w > BG_MAX_DIM) or (h > BG_MAX_DIM)

        if need_resize:
            img = reader.read()
            if img.isNull():
                QMessageBox.warning(self, "Cannot Use This Image", "PNG decode failed")
                return
            if w >= h:
                new_w, new_h = BG_MAX_DIM, max(1, int(round(h * BG_MAX_DIM / w)))
            else:
                new_h, new_w = BG_MAX_DIM, max(1, int(round(w * BG_MAX_DIM / h)))
            img = img.scaled(new_w, new_h,
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            if not img.save(tmp, "PNG"):
                QMessageBox.warning(self, "Cannot Use This Image", "PNG save failed")
                return
        else:
            try:
                shutil.copyfile(src, tmp)
            except Exception as e:
                QMessageBox.warning(self, "Cannot Use This Image", f"Copy failed: {e}")
                return

        try:
            final_size = os.path.getsize(tmp)
        except OSError:
            final_size = -1
        if final_size < 0 or final_size > BG_MAX_BYTES:
            try:
                os.remove(tmp)
            except OSError:
                pass
            QMessageBox.warning(self, "Cannot Use This Image", "PNG file exceeds 5MB")
            return

        try:
            os.replace(tmp, dst)
        except OSError as e:
            try:
                os.remove(tmp)
            except OSError:
                pass
            QMessageBox.warning(self, "Cannot Use This Image", f"Replace failed: {e}")
            return

        self.custom_background_path = dst
        if self.background_mode != "image":
            self.background_mode = "image"
        self.apply_background_image()
        self.update()
        self._save_settings()
        self.track_status.setText(
            f"Background: {os.path.basename(src)} ({final_size/1024:.0f} KB"
            + (", resized" if need_resize else "") + ")")
        log(f"[BG] set custom background: {src} -> {dst} "
            f"({final_size} bytes, resized={need_resize})", 20)

    def clear_background_image(self):
        _p = os.path.join(BACKGROUND_DIR, CUSTOM_BACKGROUND_FILENAME)
        if not getattr(self, "custom_background_path", "") and not os.path.isfile(_p):
            QMessageBox.information(self, "Info", "No custom background image is set")
            return
        reply = QMessageBox.question(
            self, "Confirm", "Clear the custom background image?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if os.path.exists(_p):
                os.remove(_p)
        except Exception as e:
            log(f"[BG] remove failed: {e}", 30)

        self.custom_background_path = ""
        self.apply_background_image()
        self.update()
        self._save_settings()
        self.track_status.setText("Custom background cleared")
        log("[BG] custom background cleared", 20)

    def toggle_audio_level_mode(self):
        self.audio_level_mode = "volume" if self.audio_level_mode == "all" else "all"
        self.text_eq.set_mode(self.audio_level_mode)
        self._save_settings()


    def toggle_log_enabled(self):
        core_mod.LOG_ENABLED = not core_mod.LOG_ENABLED
        if core_mod.LOG_ENABLED:
            if core_mod.LOG_FILE is None:
                init_log()
        else:
            close_log()
        self._save_settings()

    def toggle_audio_level_source(self):
        if self.audio_level_source == "file":
            if not HAS_SOUNDDEVICE:
                self.track_status.setText("sounddevice not installed")
                return
            self.audio_level_source = "system"
            self.start_system_audio_capture()
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
            log("[SystemAudio] Capture started", 20)
        except Exception as e:
            log(f"[SystemAudio] Failed: {e}", 40)
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
            log(f"[SystemAudio] Spectrum error: {e}", 30)
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

    # ================== TRACK MODEL ==================
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
            title = track.get("cue_title") or f"Track {track.get('cue_track_number', 0)}"
            performer = track.get("cue_performer") or ""
            base = f"{title}"
            if performer:
                base = f"{performer} - {title}"
            return base
        if path.startswith("http"):
            return self.get_display_name(path)
        return self.get_display_name(path).lower()

    def read_metadata(self, track):
        return core_read_metadata(track)

    # ================== KEYS ==================
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
            self.loop_label.setText(f"Loop: {self.loop_mode_names[self.loop_mode]}")
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
                reply = QMessageBox.question(self, "Confirm deletion",
                    "Remove this track from the favorites list?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self.favorites[lid].remove(target)
                    self._save_playlist()
                    self.track_status.setText(f"Removed from {lid}")
                    self.show_favorites_list(lid)
            else:
                self.track_status.setText("Not in this list")
        else:
            num, ok = QInputDialog.getInt(self, "Favorites", "Enter favorites list number (0-512):", 1, 0, 512, 1)
            if not ok:
                return
            list_id = f"{num:03d}"
            if list_id not in self.favorites:
                self.favorites[list_id] = []
            if target not in self.favorites[list_id]:
                self.favorites[list_id].append(target)
                self._save_playlist()
                self.track_status.setText(f"Added to {list_id}")
            else:
                self.track_status.setText(f"Already in {list_id}")

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
        self.loop_label.setText("Loop: OFF")
        self.track_title.setText("------------------------")
        self.meta_label.setText("Artist: -   Album: -   Track#: -")
        self.track_status.setText("Stopped")
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

    # ================== COVER ==================
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

    # ================== ENGINE SELECT ==================

    def _get_engine_for_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in (".dnm", ".ftm"):
            return "chiptune_cli" if self.furnace_available else None
        if ext in (".sid", ".vgm", ".vgz"):
            return "zxtune" if self.zxtune_available else None
        # .mpt is OpenMPT / MultiTracker — not ASAP. Keep it on audio → openmpt123.
        if ext in (".sap", ".cmc", ".cm3", ".cmr", ".cms", ".dmc", ".dlt",
                   ".mpd", ".rmt", ".tmc", ".tm8", ".tm2", ".fc"):
            return "asap" if self.asap_available else None
        return "audio"

    def stop_current_engine(self):
        self._media_end_handled = True
        self._cue_end_timer.stop()
        self._cue_end_ms = None
        if self.conv_thread and self.conv_thread.isRunning():
            self.conv_thread.requestInterruption()
            self.conv_thread.wait(1000)
            self.conv_thread = None
        self.audio_engine.stop()
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

    # ================== PLAY ==================

    def play_file(self, track_or_path):
        if isinstance(track_or_path, dict):
            track = track_or_path
        else:
            track = self._track_from_path(track_or_path)

        path = track.get("path")
        if not path:
            self.track_status.setText("Cannot play - missing path")
            return

        if not path.startswith("http") and not os.path.isfile(path):
            log(f"[Play] Missing file skipped: {path}", 30)
            self.track_status.setText(f"Missing: {self.get_display_name(path)}")
            self._mark_now_playing(None)
            if self.current_playlist and self.loop_mode == 2:
                QTimer.singleShot(500, self.play_next_in_list)
            return

        engine = self._get_engine_for_file(path)
        if track.get("cue_path") and track.get("end_ms"):
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
                ok = self.audio_engine.play(cached_wav, start_ms=0)
                if not ok:
                    err = self.audio_engine.last_error or "Cannot play"
                    self.track_status.setText(f"Cannot play - {err}")
                    return
                QTimer.singleShot(200, self.update_volume_to_actual)
                self.current_file_path = path
                self.current_track_info = track
                self.current_engine = self.audio_engine.current_name or "cached"
                self.spectrum_source_path = cached_wav
                self._update_track_display(track)
                self.track_status.setText("Playing (cached)")
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
                self._media_end_handled = False
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
            ext = os.path.splitext(path)[1].lower()
            if ext in (".sid", ".vgm", ".vgz"):
                msg = "Need zxtune123.exe next to the player for SID/VGM"
            elif ext in (".dnm", ".ftm"):
                msg = "Need furnace.exe next to the player for DNM/FTM"
            elif ext in (".sap", ".tm8", ".tm2"):
                msg = "Need asapconv.exe next to the player for SAP/TM8"
            else:
                msg = "Cannot play - required engine missing"
            self.track_status.setText(msg)
            self._mark_now_playing(None)
            return

        if self.current_playlist:
            for i, t in enumerate(self.current_playlist):
                if self.make_track_key(t) == cache_key:
                    self.current_track_index = i
                    break
            else:
                self.current_track_index = -1

        log(f"[Play] {path} engine={engine} start_ms={track.get('start_ms', 0)}", 20)

        if engine in ("chiptune_cli", "asap", "zxtune"):
            fname = os.path.basename(path)
            self.track_status.setText(f"Loading [{fname}]")
            self._update_track_display(track)
            self.current_engine = engine
            self._media_end_handled = False
            self.conv_thread = ConversionThread(engine, path)
            self.conv_thread.finished.connect(lambda wav: self.on_conversion_finished(wav, engine))
            self.conv_thread.start()
            return

        start_ms = track.get("start_ms", 0) or 0
        ok = self.audio_engine.play(path, start_ms=start_ms)
        if not ok:
            err = self.audio_engine.last_error or "unsupported format"
            self.track_status.setText(f"Cannot play - {err}")
            self._mark_now_playing(None)
            return
        self.current_engine = self.audio_engine.current_name or "audio"
        self.spectrum_source_path = path
        QTimer.singleShot(200, self.update_volume_to_actual)
        QTimer.singleShot(1000, lambda: self._fetch_and_cache_duration(path))
        self._update_track_display(track)
        self.track_status.setText("Playing")
        prevent_sleep(True)
        self.add_to_history(path)
        self.increment_play_count(path)
        self.load_cover_art(path)
        self.update_now_playing_marker()
        self._media_end_handled = False
    def _update_track_display(self, track):
        path = track.get("path", "")
        if track.get("cue_path"):
            title = track.get("cue_title") or f"Track {track.get('cue_track_number', 0)}"
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
            self.meta_label.setText(f"Artist: {artist}   Album: {album}   Track#: {tn}")
        else:
            self.meta_label.setText("Artist: -   Album: -   Track#: -")


    def _check_cue_end(self):
        if self._cue_end_ms is None:
            return
        try:
            curr_ms, _ = self.audio_engine.get_time()
            if curr_ms is not None and curr_ms >= 0 and curr_ms >= self._cue_end_ms:
                self._cue_end_timer.stop()
                self._cue_end_ms = None
                self.on_media_end()
        except Exception:
            pass

    def _fetch_and_cache_duration(self, filepath):
        if not filepath or filepath.startswith("http"):
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
            _, total_ms = self.audio_engine.get_time()
            if total_ms and total_ms > 0:
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
            ok = self.audio_engine.play(wav)
            if not ok:
                self.track_status.setText("Cannot play - conversion output failed")
                return
            self.current_engine = self.audio_engine.current_name or engine
            self.spectrum_source_path = wav
            QTimer.singleShot(200, self.update_volume_to_actual)
            QTimer.singleShot(1500, lambda: self._fetch_and_cache_duration(self.current_file_path))
            self.load_cover_art(self.current_file_path)
            if self.current_track_info:
                self._update_track_display(self.current_track_info)
            self.track_status.setText("Playing")
            prevent_sleep(True)
            self._media_end_handled = False
        else:
            self.track_status.setText("Cannot play - converter failed")

    def toggle_pause(self):
        if self.audio_engine.is_playing():
            self.audio_engine.pause()
            prevent_sleep(False)
            self.track_status.setText("Paused")
        elif self.audio_engine.is_paused():
            self.audio_engine.resume()
            prevent_sleep(True)
            self.track_status.setText("Playing")

    def adjust_volume(self, delta):
        new_vol = max(0, min(100, self.volume_text.value() + delta))
        self.volume_text.setValue(new_vol)
        self.audio_engine.set_volume(new_vol)
        self._save_settings()

    def seek_relative(self, delta_ms):
        pos_ms, len_ms = self.audio_engine.get_time()
        if pos_ms is None or pos_ms < 0 or not len_ms or len_ms <= 0:
            return
        target_ratio = max(0.0, min(1.0, (pos_ms + delta_ms) / len_ms))
        self.audio_engine.set_position(target_ratio)

    @Slot()
    def on_media_end(self):
        if self._media_end_handled:
            return
        self._media_end_handled = True
        if self.loop_mode == 1 and self.current_track_info:
            self.play_file(self.current_track_info)
        elif self.loop_mode == 2 and self.current_playlist:
            self.play_next_in_list()
        else:
            prevent_sleep(False)
            self.track_status.setText("Stopped")
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
        self.track_status.setText("No playable track in list")
        self._mark_now_playing(None)

    def add_to_history(self, filepath):
        if filepath in self.history_paths:
            self.history_paths.remove(filepath)
        self.history_paths.insert(0, filepath)
        if len(self.history_paths) > 100:
            self.history_paths = self.history_paths[:100]
        self._save_history()

    @staticmethod
    def _make_audio_tag(duration_ms=None, show_duration=True):
        if not show_duration:
            return "[AUD]"
        if duration_ms is not None and duration_ms >= 0:
            s, _ = divmod(duration_ms, 1000)
            m, s = divmod(s, 60)
            return f"[AUD {m:02d}:{s:02d}]"
        return "[AUD]"

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
            text = f"[WEB] {prefix_text}{display}"
        elif not os.path.isfile(path):
            text = f"[MISS] {prefix_text}{display}"
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
        log("[UI] show_source_list", 20)
        self.current_dir = None
        self._pending_folder_list = []
        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        self.current_playlist = []
        for p in self.source_paths:
            if p.startswith("http://") or p.startswith("https://"):
                item = QListWidgetItem(f"[WEB] {self.get_display_name(p)}")
            else:
                name = os.path.basename(p.rstrip('\\/')) or p
                item = QListWidgetItem(f"[FILE] {name.lower()}")
            item.setData(Qt.ItemDataRole.UserRole, {"path": p, "is_source": True})
            self.file_list.addItem(item)
        for lid in sorted(self.favorites.keys()):
            if self.favorites[lid]:
                item = QListWidgetItem(f"[LIST{lid}] favorites")
                item.setData(Qt.ItemDataRole.UserRole, {"path": f"FAVORITES:{lid}", "is_source": True})
                self.file_list.addItem(item)
        if self.history_paths:
            item = QListWidgetItem("[HISTORY]HISTORY")
            item.setData(Qt.ItemDataRole.UserRole, {"path": "HISTORY", "is_source": True})
            self.file_list.addItem(item)
        if self.play_counts:
            item = QListWidgetItem("[MOST] Most Played")
            item.setData(Qt.ItemDataRole.UserRole, {"path": "MOST_PLAYED", "is_source": True})
            self.file_list.addItem(item)
        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
        self.path_label.setText("-")
        self.file_list.setUpdatesEnabled(True)

    def show_most_played_list(self):
        log("[UI] show_most_played_list", 20)
        self.current_dir = "MOST_PLAYED"
        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        self.current_playlist = []
        self.current_track_index = -1
        back = QListWidgetItem("[..]  (GO BACK)")
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
        self.path_label.setText("MOST PLAYED")
        self.file_list.setUpdatesEnabled(True)
        self.update_now_playing_marker()

    def show_favorites_list(self, lid):
        log(f"[UI] show_favorites_list lid={lid}", 20)
        self.current_dir = f"FAVORITES:{lid}"
        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        self.current_playlist = []
        self.current_track_index = -1
        back = QListWidgetItem("[..]  (GO BACK)")
        back.setData(Qt.ItemDataRole.UserRole, {"path": "ACTION_BACK"})
        self.file_list.addItem(back)
        for filepath in self.favorites.get(lid, []):
            track = self._track_from_path(filepath)
            self.file_list.addItem(self._make_item(track))
            self.current_playlist.append(track)
        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
        self.path_label.setText(f"FAVORITES {lid}")
        self.file_list.setUpdatesEnabled(True)
        self.update_now_playing_marker()

    def show_history_list(self):
        log("[UI] show_history_list", 20)
        self.current_dir = "HISTORY"
        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        self.current_playlist = []
        self.current_track_index = -1
        back = QListWidgetItem("[..]  (GO BACK)")
        back.setData(Qt.ItemDataRole.UserRole, {"path": "ACTION_BACK"})
        self.file_list.addItem(back)
        for filepath in self.history_paths:
            track = self._track_from_path(filepath)
            self.file_list.addItem(self._make_item(track))
            self.current_playlist.append(track)
        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
        self.path_label.setText("PLAY HISTORY")
        self.file_list.setUpdatesEnabled(True)
        self.update_now_playing_marker()

    def show_m3u_list(self, m3u_path):
        log(f"[UI] show_m3u_list {m3u_path}", 20)
        self.current_dir = "M3U:" + m3u_path
        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        self.current_playlist = []
        self.current_track_index = -1
        back = QListWidgetItem("[..]  (GO BACK)")
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
        log(f"[UI] show_cue_list {cue_path}", 20)
        self.current_dir = "CUE:" + cue_path
        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        self.current_playlist = []
        self.current_track_index = -1
        back = QListWidgetItem("[..]  (GO BACK)")
        back.setData(Qt.ItemDataRole.UserRole, {"path": "ACTION_BACK"})
        self.file_list.addItem(back)

        cue_tracks = parse_cue_file(cue_path)
        if not cue_tracks:
            self.track_status.setText("CUE parse failed")
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
        log(f"[UI] show_directory {path}", 20)
        self.current_dir = path
        self._pending_folder_list = []
        self.current_playlist = []
        self.current_track_index = -1
        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        back = QListWidgetItem("[..]  (GO BACK)")
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
                item = QListWidgetItem(f"[DIR]  {f.lower()}/")
                item.setData(Qt.ItemDataRole.UserRole, {"path": os.path.join(path, f), "is_dir": True})
                self.file_list.addItem(item)

            for f in cue_files:
                cue_path = os.path.join(path, f)
                item = QListWidgetItem(f"[CUE]  {f.lower()}")
                item.setData(Qt.ItemDataRole.UserRole, {"path": cue_path, "is_cue": True})
                self.file_list.addItem(item)

            for f in files:
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
            log(f"[Dir] Failed to list {path}: {e}", 30)
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
                if text.startswith("[AUD"):
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
            log(f"[UI] handle_selection non-dict data: {data!r}", 30)
            return
        log(f"[UI] handle_selection path={data.get('path')}", 20)
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
                log(f"[UI] handle_selection unknown source path: {p}", 30)
                self.track_status.setText(f"Missing: {self.get_display_name(p)}")
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

    # ================== SPECTRUM ==================

    def update_spectrum_bars(self):
        if not self.show_audio_level:
            self.text_eq.set_levels(0.0, 0.0, 0.0, 0.0)
            return
        if self.audio_level_source == "system":
            b, m, t, v = self._calculate_system_spectrum()
        else:
            b, m, t = self.audio_engine.get_spectrum_bands()
            left, right = self.audio_engine.get_level()
            v = (left + right) / 2.0
        smoothing = 0.3
        self._smooth_bass = self._smooth_bass + (b - self._smooth_bass) * smoothing
        self._smooth_mid = self._smooth_mid + (m - self._smooth_mid) * smoothing
        self._smooth_treble = self._smooth_treble + (t - self._smooth_treble) * smoothing
        self._smooth_volume = self._smooth_volume + (v - self._smooth_volume) * smoothing
        self.text_eq.set_levels(self._smooth_bass, self._smooth_mid, self._smooth_treble, self._smooth_volume)
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
        curr_ms = 0
        total_ms = -1
        pos = 0.0
        playing = self.audio_engine.is_playing()
        paused = self.audio_engine.is_paused()
        if playing or paused:
            try:
                pos = self.audio_engine.get_position() or 0
                curr_ms, total_ms = self.audio_engine.get_time()
            except Exception:
                pos = 0
            self.progress_text.setValue(int(pos * 1000))
            if paused:
                self.track_status.setText("Paused")
            else:
                status = self.track_status.text() or ""
                if status not in ("Paused", "Playing (cached)") and not status.startswith("Loading"):
                    self.track_status.setText("Playing")
        else:
            status = self.track_status.text() or ""
            converting = bool(self.conv_thread and self.conv_thread.isRunning())
            if (
                self.current_file_path
                and not self._media_end_handled
                and not converting
                and not status.startswith("Loading")
                and status not in ("Paused",)
            ):
                QTimer.singleShot(0, self.on_media_end)
        curr_str = self.format_time(curr_ms if curr_ms is not None else 0)
        total_str = self.format_time(total_ms) if total_ms and total_ms > 0 else self._time_placeholder()
        bar_text = self.progress_text.text().split("]")[0] + "]"
        self.progress_text.setText(f"{bar_text} {curr_str} / {total_str}")
        if self.current_file_path:
            track_name = self.get_display_name(self.current_file_path)
            self.tray_icon.setToolTip(f"dem_player - {track_name}")
        else:
            self.tray_icon.setToolTip(f"dem_player {APP_VERSION}")

    def closeEvent(self, event):
        log("=== Player closing ===", 20)
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
        self.audio_engine.free()
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


if __name__ == "__main__":
    try:
        apply_cpu_affinity()
        init_log()
        log("=== Player Starting ===", 20)
        log(f"Version {APP_VERSION}", 20)
        log(f"app_dir = {app_dir()}", 20)
        log(f"SETTINGS_FILE = {SETTINGS_FILE}", 20)
        log(f"PLAYLIST_FILE = {PLAYLIST_FILE}", 20)
        log(f"HISTORY_FILE = {HISTORY_FILE}", 20)
        log(f"CACHE_FILE = {CACHE_FILE}", 20)
        log(f"Python {sys.version}, Platform: {sys.platform}", 20)
        log(f"Frozen={getattr(sys, 'frozen', False)}, numpy={HAS_NUMPY}, sounddevice={HAS_SOUNDDEVICE}, mutagen={HAS_MUTAGEN}", 20)
        os.environ["QT_OPENGL"] = "software"
        if sys.platform == "win32":
            os.environ["QT_QPA_PLATFORM"] = "windows"
        os.environ["QT_SCALE_FACTOR"] = "1"
        log("Qt environment set", 20)
        app = QApplication(sys.argv)
        icon_path = resource_path("FPT.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        win = MusicRoom()
        win.show()
        log("Window shown successfully", 20)
        sys.exit(app.exec())
    except Exception as e:
        log(f"Fatal error: {e}\n{traceback.format_exc()}", 40)
        print(f"\n程序崩潰: {e}")
        print(traceback.format_exc())
        sys.exit(1)
