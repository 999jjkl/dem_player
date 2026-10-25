# dem_player

A keyboard-first, frameless music player built with Python + PySide6 for Windows.

A compact desktop player that focuses on fast keyboard control, a wide range of audio formats (including tracker modules and chiptunes), customizable themes, and a slick borderless UI.

---

## Overview

`dem_player` is a frameless, single-instance, keyboard-driven music player. It supports local folder browsing, playlists, favorites, play history and play counts, optional audio-level visualization (from file or system capture), multiple window modes, transparent/aero/solid/custom-image backgrounds, and automatic migration from older data formats.

- **Single instance** — Opening another file while the player is running hands the path to the existing window via a local socket.
- **Keyboard-first** — Almost everything is reachable from the keyboard; the mouse is mainly for dragging, resizing, and the tray.
- **Extensible backends** — Different formats fall through a chain of decoders (miniaudio → FFmpeg → openmpt → FluidSynth → Furnace/ASAP/ZXTune) with per-backend fallback.

---

## Features

- **Keyboard-driven UI** with a visible key legend on the main screen.
- **Local folder browser** with file, CUE, M3U, and stream URL support.
- **Playlists** — Import/export M3U (UTF-8 / UTF-16 / GBK tolerant).
- **Favorites** — Up to 512 numbered lists (`001`–`512`), each exportable as M3U.
- **History** — Last 100 played paths, re-playable from the browser.
- **Play counts** — Sorted "Most Played" view.
- **Metadata & cover art** — Optional via `mutagen` (title, artist, album, track#; local `cover.jpg` / `folder.png` / etc.).
- **Themes** — 16 built-in color themes + up to 24 user-defined custom themes.
- **Backgrounds** — `transparent`, `aero` (frosted glass), `solid`, or `image` (custom PNG ≤ 5 MB, auto-resized to 3840 px max).
- **Audio-level visualization** — "all" (bass/mid/treble/volume) or "volume" only; sourced from the file or system capture (`sounddevice` loopback).
- **Window modes** — Normal (900×600), Fullscreen, Mini (380×230), Bar (900×200).
- **Output device selection** — Pick any Windows playback endpoint.
- **Single instance** — IPC via `QLocalServer`/`QLocalSocket` (`dem_player_single`).
- **Drag & drop** — Files and folders onto the window or exe.
- **Windows "Open with"** — Register as an explorer handler without stealing the default player.
- **Data auto-migration** — Old `.dpst`/`.dppls`/`.dpphc`/`.dpch` and older `.json` / `.txt` files migrate transparently.

---

## Supported Formats

Routing is extension-based with per-backend fallback:

| Backend | Extensions / Purpose |
|---|---|
| **miniaudio** | `.mp3`, `.wav`, `.flac`, `.ogg` |
| **FFmpeg** | `.m4a`, `.aac`, `.wma`, `.opus`, `.alac`, `.ape`, `.ac3`, `.mp2`, `.mpga` — plus **stream URLs** (`http://`, `https://`, `mms://`, `mmsh://`, `rtmp://`, `rtmps://`, `rtsp://`) |
| **OpenMPT** | `.mod`, `.xm`, `.it`, `.s3m`, `.mtm`, `.umx`, `.mo3`, `.mptm`, `.mpt`, `.stm`, `.669`, `.far`, `.ult`, `.mt2`, `.okt`, `.ptm`, `.med`, `.dbm`, `.digi`, `.dmf`, `.dsm`, `.imf`, `.j2b`, `.mdl`, `.psm`, `.amf`, `.ams`, `.mmcmp` |
| **FluidSynth** | `.mid`, `.midi`, `.rmi`, `.kar` — requires `soundfont.sf2` |
| **Furnace** | `.dnm`, `.ftm` |
| **ASAP** | `.sap`, `.cmc`, `.cm3`, `.cmr`, `.cms`, `.dmc`, `.dlt`, `.mpd`, `.rmt`, `.tmc`, `.tm8`, `.tm2`, `.fc` |
| **ZXTune** | `.sid`, `.vgm`, `.vgz` |
| **CUE** | `.cue`, `.cue.txt` (per-track playback with `index01` / `end_ms` slicing) |

---

## Requirements

- **Windows** (primary supported platform)
- **Python 3.9+** (recommended 3.10 or newer)

Install the Python packages directly:
pip install PySide6 miniaudio numpy sounddevice mutagen


- `PySide6` — required
- `miniaudio` — required for default playback
- `numpy` — optional (audio-level visualization)
- `sounddevice` — optional (system audio capture for visualization)
- `mutagen` — optional (metadata, cover art, CUE duration probing)

---

## Running from Source

python main.py

On first launch, `data/` is created next to `main.py` (or next to the `.exe` if frozen) with:

- `data/settings.dpj`
- `data/play_list.dpj`
- `data/play_history.dpj`
- `data/cache.dpj`
- `data/logs/player_data_%H.%M.%S-%d.%m.%Y.log`

Old-format files are migrated automatically and renamed with an `_old2` or `.bak` suffix.

---

## Building a Standalone EXE

`build.bat`:

1. Installs runtime dependencies and `pyinstaller>=6.11`.
2. Runs `pyinstaller --noconfirm --clean dem_player.spec`.
3. Copies sidecar tools next to `dist\dem_player\dem_player.exe`.

The resulting onedir bundle lives at `dist\dem_player\`. To share the player, copy the whole folder — not just the exe.

To optionally keep playlists, copy your `data\` folder next to `dem_player.exe`.

> **Note:** The spec deliberately excludes QtWebEngine, 3D modules, QML, Quick, Charts, and similar heavy Qt extras. `ffmpeg`, `soundfonts`, and other large tools are **not** bundled by PyInstaller; `build.bat` copies them from the project root.

---

## Sidecar Tools

Place the following files next to `main.py` or next to the built `dem_player.exe` to enable their features. `build.bat` attempts to copy them automatically from the project root.

| File / Tool | Purpose |
|---|---|
| `ffmpeg.exe` | Decode extra formats (M4A/AAC/WMA/OPUS/APE/…) and stream URLs |
| `ffprobe.exe` | Optional FFmpeg check |
| `openmpt123.exe` | Render MOD/XM/IT/S3M/MPTM/… to WAV |
| `libopenmpt.dll` | Native openmpt library (ctypes fallback) |
| `openmpt-mpg123.dll` | Optional MPG123 support library |
| `fluidsynth.exe` | Render MIDI/RMI to WAV (needs a SoundFont) |
| `libfluidsynth-3.dll` | FluidSynth runtime |
| `SDL3.dll` | FluidSynth runtime dependency |
| `sndfile.dll` | FluidSynth runtime dependency |
| `soundfont.sf2` (or `FluidR3_GM.sf2`, `weedsgm3.sf2`) | Required for MIDI/RMI playback |
| `furnace.exe` | DNM / FTM rendering |
| `asapconv.exe` | ASAP format conversion |
| `zxtune-cli.exe` (or `zxtune123.exe`) | SID / VGM / VGZ conversion |
| `font.ttf` | Custom UI font (falls back to Courier New) |
| `FPT.ico` | App / tray icon |
| `background.png` / `Background.png` | Default background image |
| `Background/custom_background.png` | Portable custom background (auto-managed by the app) |

**Download links**

- **FFmpeg**: <https://github.com/BtbN/FFmpeg-Builds/releases>
- **OpenMPT / libopenmpt**: <https://github.com/OpenMPT/openmpt>
- **FluidSynth**: <https://www.fluidsynth.org/>
- **SoundFonts**: <https://musical-artifacts.com/> (look for GeneralUser GS, FluidR3_GM, or weedsgm3)
- **Furnace**: <https://github.com/tildearrow/furnace/releases>
- **ASAP**: <https://asap.sourceforge.net/>
- **ZXTune**: <https://zxtune.bitbucket.io/>

If a required sidecar is missing, the corresponding format fails gracefully with a clear message in the status line.

---

## Data Files

| File | Purpose |
|---|---|
| `data/settings.dpj` | All UI / playback settings (JSON) |
| `data/play_list.dpj` | Source folders + favorites |
| `data/play_history.dpj` | Playback history (max 100) + play counts |
| `data/cache.dpj` | Folder scan cache and known durations |
| `data/logs/player_data_%H.%M.%S-%d.%m.%Y.log` | Session log |

- **`cache.dpj`** — Auto-managed. Delete it (or use `Clear Duration Cache` in Settings) to force a rescan.
- **`Background/custom_background.png`** — Portable copy of the user's chosen background; the absolute path is never stored, so moving the app folder is safe.

---

## Keyboard Shortcuts

Main window:

| Key | Action |
|---|---|
| `↑` / `↓` | Move selection in the file browser |
| `Enter` | Open / play the selected item |
| `Backspace` | Go back one level (or delete a char while search is focused) |
| `F1` | Play / pause |
| `F2` | Volume −1 |
| `F3` | Volume +1 |
| `F4` | Toggle left panel (ignored in mini mode) |
| `F5` | Cycle loop mode: `OFF → SINGLE → LIST → RANDOM` |
| `F6` | Cycle window mode: `Normal → Fullscreen → Mini → Bar` |
| `F7` | Toggle Settings (ignored in mini / bar modes) |
| `F8` | Focus search (ignored in mini mode) |
| `F9` | Add the selected track to a favorites list (or remove it if currently viewing that list) |
| `F10` | Scan durations for the currently open folder |
| `Esc` | Reset the player (stop, clear, return to source list) |
| `←` / `→` | Seek −1 s / +1 s |

Settings page:

| Key | Action |
|---|---|
| `←` / `→` | Switch between setting pages |
| `Esc` | Close editor, then exit Settings |
| `Enter` (in a choice list) | Apply the selected value |
| `←` / `→` (while editing a custom theme) | Switch HEX ⇄ RGB input mode |

---

## Settings Overview

The settings page is organized into five pages (navigate with `←` / `→`):

### General
- Always on Top
- Allow Screensaver While Playing
- Theme (16 built-ins + custom)
- Time format (`MM:SS` or `MM:SS.CC`)

### Audio
- Output Device (System Default or any Windows playback endpoint)
- Audio Level (on/off)
- Audio Level Source (`file` or `system`)
- Audio Level Mode (`all` = bass/mid/treble/volume, or `volume` only)

### Display
- Background: `transparent` | `aero` | `solid` | `image`
- Aero Opacity (0–100 %)
- Background Image → pick a PNG ≤ 5 MB / ≤ 3840 px
- Clear Background Image
- Show Duration
- Show Cover Art
- Show Play Counts

### Library
- Add Music Folder…
- Remove Folder (per source)
- Refresh File List
- Scan This Folder Durations (same as `F10`)

### Options
- Log Save (enable/disable, live)
- Register Open With (per-user `HKCU`, does **not** steal default)
- Clear History
- Clear Play Counts
- Clear Favorites
- Clear Duration Cache
- Reset All Settings
- About

Each destructive action asks for confirmation.

---

## Window Modes

| Mode | Size | Contents |
|---|---|---|
| **Normal** | 900×600 fixed | Full layout (file list + right panel) |
| **Fullscreen** | Screen | Same layout, larger fonts |
| **Mini** | 380×230 fixed | Right panel only, no cover art |
| **Bar** | 900×200 fixed | Right panel only, minimal legend |

The window is frameless. Drag from the top 40 px to move; a ghost outline (`DragFrame`) follows the mouse. Below the top strip the cursor is hidden to keep the UI clean.

---

## Themes

- **16 built-in** color pairs (Black & White, Black & Green, …, Royal Violet & Golden Wealth).
- **Custom themes** — up to 24, added via Settings → Themes → Add Colour…, entered in **HEX** (`#RRGGBB`) or **RGB** (`R,G,B`, 0–255). Switch input modes with `←` / `→`.

---

## Single-Instance Behavior (Open With / Drag & Drop)

The player uses `QLocalServer` + `QLocalSocket` on the name `dem_player_single`:

1. On launch, if another instance is already listening, the new process sends `PLAY\n<path1>\n<path2>…` (or `ACTIVATE` with no paths) and **exits**.
2. The already-running window brings itself to the foreground and opens the files.
3. If no listener exists, the process creates the server and runs normally.

This means double-clicking an MP3 in Explorer only ever results in **one** `dem_player` window.

### Registering "Open with"

- From the Settings page: **Options → Register Open With**.
- Or from the command line:

register_openwith.bat


The bat registers under `HKCU\Software\Classes\Applications\dem_player.exe` — **per-user**, no admin rights needed, and it does **not** change the default handler for any extension.

Supported extensions in the `SupportedTypes` key:

mp3 wav flac ogg m4a aac wma opus
mid midi rmi kar
mod xm it s3m mptm mpt mt2 stm
ftm dnm sap sid tm8 vgm vgz
m3u m3u8


---

## Logging

Every session writes `data/logs/player_data_<time>.log` when `Log Save` is enabled in Settings. The About dialog shows the current log path along with detected sidecar tools, engine name, play state, and active settings.

---

## License

No license is currently declared in the repository. Please contact the repository owner before redistribution.

---

## Credits

- **PySide6** — Qt bindings for the GUI
- **miniaudio** — Direct decode for MP3 / WAV / FLAC / OGG
- **FFmpeg** — Everything else, and stream URLs
- **libopenmpt / openmpt123** — Tracker modules
- **FluidSynth** — MIDI / RMI rendering
- **Furnace** — DNM / FTM
- **ASAP** — 8-bit Atari formats
- **ZXTune** — SID / VGM / VGZ
- **mutagen** — Metadata and duration probing
- **numpy** + **sounddevice** — Audio-level visualization

---

# 繁體中文 (zh-TW)

## 簡介

`dem_player` 是一款以**鍵盤操作為核心**、無邊框的桌面音樂播放器，使用 Python + PySide6 開發，主要支援 Windows。

- **單一實例** — 已開啟時，任何「以這個程式開啟」的檔案會交給現有視窗。
- **鍵盤優先** — 幾乎所有操作都能用鍵盤完成；滑鼠主要負責拖曳、視窗縮放、系統匣。
- **多後端解碼** — 依格式自動選擇 miniaudio / FFmpeg / openmpt / FluidSynth / Furnace / ASAP / ZXTune。

## 主要功能

- 本地資料夾瀏覽、M3U 播放清單、CUE 分軌、串流網址
- 收藏清單（編號 `001`–`512`，可匯出 M3U）
- 播放歷史（最多 100 筆）與播放次數統計
- Metadata / 封面圖（需 `mutagen`）
- 16 組內建主題 + 最多 24 組自訂主題
- 背景模式：`transparent` / `aero` / `solid` / `image`
- 音頻等級顯示：可從**檔案**或**系統擷取**分析
- 四種視窗模式：Normal、Fullscreen、Mini、Bar
- 輸出裝置選擇（WASAPI 端點）
- Windows「以這個程式開啟」登錄（不會搶走預設播放器）
- 舊版資料自動遷移

## 支援格式

| 後端 | 格式 |
|---|---|
| **miniaudio** | `.mp3` `.wav` `.flac` `.ogg` |
| **FFmpeg** | `.m4a` `.aac` `.wma` `.opus` `.alac` `.ape` `.ac3` `.mp2` `.mpga`，以及串流 URL |
| **OpenMPT** | `.mod` `.xm` `.it` `.s3m` `.mtm` `.mptm` `.mpt` 等追蹤器格式 |
| **FluidSynth** | `.mid` `.midi` `.rmi` `.kar`（需 `soundfont.sf2`） |
| **Furnace** | `.dnm` `.ftm` |
| **ASAP** | `.sap` `.tm8` `.tm2` 等 8-bit Atari 格式 |
| **ZXTune** | `.sid` `.vgm` `.vgz` |
| **CUE** | `.cue` / `.cue.txt` 分軌 |

## 系統需求

- Windows
- Python 3.9+（建議 3.10 以上）

pip install PySide6 miniaudio numpy sounddevice mutagen


- `numpy`、`sounddevice`、`mutagen` 為選用功能（音頻可視化、系統音訊擷取、metadata）。

## 執行

python main.py

首次啟動會在 `main.py`（或 exe）旁建立 `data/` 資料夾：

- `data/settings.dpj`
- `data/play_list.dpj`
- `data/play_history.dpj`
- `data/cache.dpj`
- `data/logs/player_data_*.log`

舊版檔案會自動遷移，並以 `_old2` / `.bak` 重新命名保留。

## 打包成獨立 EXE

build.bat

輸出位於 `dist\dem_player\dem_player.exe`。分享時請複製**整個資料夾**。

## 需要放在同目錄的工具

`ffmpeg.exe`、`ffprobe.exe`、`openmpt123.exe`、`libopenmpt.dll`、`fluidsynth.exe`、`libfluidsynth-3.dll`、`SDL3.dll`、`sndfile.dll`、`soundfont.sf2`、`furnace.exe`、`asapconv.exe`、`zxtune-cli.exe` / `zxtune123.exe`、`font.ttf`、`FPT.ico`、`background.png`。

`Background/custom_background.png` 為使用者自訂背景（由程式自動管理；僅支援 PNG、≤ 5 MB、最長邊自動縮至 3840 px）。

## 快速鍵

| 按鍵 | 功能 |
|---|---|
| `↑` / `↓` | 上下移動 |
| `Enter` | 開啟 / 播放 |
| `Backspace` | 返回上一層 / 刪除搜尋字元 |
| `F1` | 播放 / 暫停 |
| `F2` / `F3` | 音量 −1 / +1 |
| `F4` | 顯示 / 隱藏左側面板 |
| `F5` | 循環模式（OFF / SINGLE / LIST / RANDOM） |
| `F6` | 視窗模式（Normal / Fullscreen / Mini / Bar） |
| `F7` | 設定 |
| `F8` | 搜尋 |
| `F9` | 加入 / 移除收藏 |
| `F10` | 掃描目前資料夾時長 |
| `Esc` | 重設播放器 |
| `←` / `→` | 倒退 / 前進 1 秒 |

設定頁：`←` / `→` 切換分頁、`Esc` 離開、`Enter` 套用。

## 設定頁面

- **General** — 常駐最前、允許螢幕保護、主題、時間格式
- **Audio** — 輸出裝置、音頻等級顯示、音訊來源、音頻等級模式
- **Display** — 背景模式、Aero 不透明度、背景圖片、顯示時長 / 封面 / 播放次數
- **Library** — 新增 / 移除資料夾、重新整理、掃描時長
- **Options** — Log、登錄「以這個程式開啟」、清除歷史 / 次數 / 最愛 / 快取、重設、About

## 單一實例 / 以這個程式開啟

程式使用 `QLocalServer`（名稱 `dem_player_single`）達成單一實例。已開啟時再開第二個檔案，會直接把路徑交給現有視窗並結束新行程。

登錄「以這個程式開啟」有兩種方法：

1. 設定頁 → **Options → Register Open With**
2. 執行專案根目錄的 `register_openwith.bat`

登錄只在 `HKCU` 底下進行（不需管理員權限），**不會**變成該副檔名的預設程式。

## 致謝

PySide6、miniaudio、FFmpeg、OpenMPT / libopenmpt、FluidSynth、Furnace、ASAP、ZXTune、mutagen、numpy、sounddevice。

---

## Why I made this

I was playing *Touhou 5: Mystic Square* and really liked the Music Room layout, so I built `dem_player` as a compact, keyboard-driven local player inspired by it.

*This README.md is use AI made 
