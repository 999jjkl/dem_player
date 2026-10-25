# dem_player

A keyboard-first, frameless music player for Windows. Python + PySide6.

It is a small desktop player: fast keys, a lot of formats (including tracker modules and chiptunes), themes, and a borderless window.

---

## Overview

`dem_player` browses local folders, plays files, CUE sheets, M3U playlists and stream URLs. It keeps favorites, history and play counts, can show an audio level, and runs as one window only.

- **One window** — a second launch sends the file to the window that is already open.
- **Keys first** — almost everything is a key. The mouse drags the window, and is used in the Add Colour window and in warning dialogs.
- **Several decoders** — miniaudio, then FFmpeg, OpenMPT, FluidSynth, Furnace, ASAP, ZXTune.

---

## Features

- File browser, CUE tracks, M3U (UTF-8 / UTF-16 / GBK), stream URLs
- Favorites: lists `001`–`512`, each can be exported as M3U
- History: last 100 paths
- Play counts, and a Most Played view
- Metadata and cover art when `mutagen` is installed
- 16 built-in themes, plus up to 24 colours you add
- Background: `transparent`, `aero`, `solid`, or `image`
- Audio level from the file, or from the system (`sounddevice`)
- Window modes: Normal, Fullscreen, Mini, Bar
- Output device picker
- Drag and drop files or folders
- Windows “Open with”, without becoming the default player
- Old data files are migrated on startup

Opening Settings does **not** stop the song. Mini and Bar cannot open Settings.

---

## Formats

| Backend | What it plays |
|---|---|
| **miniaudio** | `.mp3` `.wav` `.flac` `.ogg` |
| **FFmpeg** | `.m4a` `.aac` `.wma` `.opus` `.alac` `.ape` `.ac3` `.mp2` `.mpga`, and `http` `https` `mms` `rtmp` `rtsp` URLs |
| **OpenMPT** | `.mod` `.xm` `.it` `.s3m` `.mptm` `.mpt` `.mt2` and other tracker files |
| **FluidSynth** | `.mid` `.midi` `.rmi` `.kar` (needs a SoundFont) |
| **Furnace** | `.dnm` `.ftm` |
| **ASAP** | `.sap` `.tm8` `.tm2` and other Atari 8-bit files |
| **ZXTune** | `.sid` `.vgm` `.vgz` |
| **CUE** | `.cue` `.cue.txt` |

If a tool is missing, that format fails and the status line says so.

---

## Requirements

- Windows
- Python 3.10 or newer (3.9 may work)

```bat
pip install -r requirements.txt
```

That installs PySide6, miniaudio, mutagen, numpy, sounddevice, and pyfluidsynth.

`numpy` and `sounddevice` are only needed for the audio-level bars. `mutagen` is only needed for tags, cover art, and duration probing.

---

## Run

```bat
python main.py
```

The first run creates `data\` next to `main.py` (or next to the exe):

- `data\settings.dpj`
- `data\play_list.dpj`
- `data\play_history.dpj`
- `data\cache.dpj`
- `data\logs\player_data_%H.%M.%S-%d.%m.%Y.log`

Older `.dpst` / `.dppls` / `.dpphc` / `.dpch` files are migrated and kept with an `_old2` or `.bak` name.

---

## Build an exe

```bat
build.bat
```

This installs PyInstaller, builds `dem_player.spec`, and copies sidecar tools that are sitting in the project folder.

Output: `dist\dem_player\dem_player.exe`

Share the **whole** `dist\dem_player` folder, not the exe alone. To keep playlists, copy your `data\` folder next to the exe.

Qt WebEngine is not packed. `ffmpeg.exe` and the SoundFont are copied by `build.bat` only if they are already in the project folder.

---

## Tools to put next to the program

| File | For |
|---|---|
| `ffmpeg.exe` | extra formats and stream URLs |
| `ffprobe.exe` | optional |
| `openmpt123.exe` | tracker modules |
| `libopenmpt.dll` | OpenMPT |
| `openmpt-mpg123.dll` | optional |
| `fluidsynth.exe` | MIDI / RMI |
| `libfluidsynth-3.dll` `SDL3.dll` `sndfile.dll` | FluidSynth |
| `soundfont.sf2` or `FluidR3_GM.sf2` or `weedsgm3.sf2` | MIDI instruments |
| `furnace.exe` | DNM / FTM |
| `asapconv.exe` | SAP and related |
| `zxtune123.exe` or `zxtune-cli.exe` | SID / VGM / VGZ |
| `font.ttf` | UI font, or Courier New |
| `FPT.ico` | window and tray icon |
| `background.png` | built-in background |
| `Background\custom_background.png` | your background (the app writes this) |

Downloads:

- FFmpeg — https://github.com/BtbN/FFmpeg-Builds/releases
- OpenMPT — https://lib.openmpt.org/
- FluidSynth — https://github.com/FluidSynth/fluidsynth/releases
- SoundFonts — https://musical-artifacts.com/
- Furnace — https://github.com/tildearrow/furnace/releases
- ASAP — https://asap.sourceforge.net/
- ZXTune — https://zxtune.bitbucket.io/

These programs are **not** part of dem_player. Keep their own license files when you share them.

---

## Data

| File | Holds |
|---|---|
| `data\settings.dpj` | theme, volume, folders, custom colours |
| `data\play_list.dpj` | source folders and favorites |
| `data\play_history.dpj` | last 100 tracks and play counts |
| `data\cache.dpj` | scanned durations |
| `data\logs\` | one log per session, if Log Save is on |

Delete `cache.dpj`, or use **Clear Duration Cache**, to scan durations again.

---

## Keys

| Key | Action |
|---|---|
| `↑` `↓` | move in the list |
| `Enter` | open or play |
| `Backspace` | go up, or delete a search character |
| `F1` | play / pause |
| `F2` `F3` | volume −1 / +1 |
| `F4` | hide or show the file list |
| `F5` | loop: OFF → SINGLE → LIST → RANDOM |
| `F6` | window: Normal → Fullscreen → Mini → Bar |
| `F7` | Settings (not in Mini or Bar). Also leaves Settings |
| `F8` | search |
| `F9` | add to favorites, or remove if you are inside that list |
| `F10` | scan durations in the open folder |
| `Esc` | reset the player, and set the theme to Black & White |
| `←` `→` | seek −1 s / +1 s |

`F4` and `F8` do nothing in Mini. `F7` does nothing in Mini and Bar.

Inside Settings the list does not use the mouse.

| Key | Action |
|---|---|
| `←` `→` | previous / next page |
| `↑` `↓` | move |
| `Enter` | change the selected row |
| `Esc` or `F7` | close a list, then leave Settings |

Yes/No rows flip on Enter. Clear, reset, and remove-folder ask in a warning window. **Yes** confirms.

**Add Colour** is its own window. The mouse works only there. You can type HEX (`#RRGGBB`) or RGB (`R,G,B`), or press a colour button. The name (`Custom 01`, …) is chosen by the app and saved in `settings.dpj`.

---

## Settings pages

1. **General** — always on top, screensaver while playing, themes, time format
2. **Audio** — output device, audio level, source (`file` / `system`), mode (`all` / `volume`)
3. **Preference** — background, aero opacity, background image, duration, cover, play counts
4. **Library** — add or remove a music folder, refresh, scan durations
5. **Options** — log, Open with, clear history / counts / favorites / cache, reset, About

---

## Window sizes

| Mode | Size |
|---|---|
| Normal | 900×600 |
| Fullscreen | the screen |
| Mini | 380×230, no Settings |
| Bar | 900×200, no Settings |

The window has no title bar. Drag the top edge to move it, unless it is maximized or fullscreen.

---

## Open with

Settings → **Options → Register Open With**, or run `register_openwith.bat`.

This writes under `HKCU` only. It does not need Administrator, and it does not take the default player.

If dem_player is already open, the new file is sent to that window (`dem_player_single`) and the second process exits.

---

## License

**GNU General Public License v3.0 or later** (`GPL-3.0-or-later`). Not GPL-2.

Copyright (C) 2026 999jjkl.

You can use, copy, change, and share this program. If you share it, or a program based on it, you must:

- use GPL version 3, or a later version if one is published (not version 2)
- give people the source code, or a written offer for the source
- keep the copyright and license notices
- mark files you changed

There is **no warranty**.

The full text is in [LICENSE](LICENSE).

`mutagen` allows GPL-2 or later, so it can be used under GPL-3. PySide6 / Qt is LGPL-3.0, which fits GPL-3 and does **not** fit a GPL-2-only license. That is why this project is GPL-3, not GPL-2.

ffmpeg, Furnace, ASAP, FluidSynth, OpenMPT, and ZXTune that you download stay under **their** licenses. Put those license files in the folder when you give the exe to someone else.

---

## Credits

| Piece | License of that piece |
|---|---|
| PySide6 / Qt | LGPL-3.0 |
| miniaudio | MIT |
| mutagen | GPL-2.0-or-later |
| numpy | BSD-3-Clause |
| sounddevice | MIT |
| FFmpeg | GPL or LGPL, depending on the build you download |
| libopenmpt | BSD-3-Clause |
| FluidSynth | LGPL-2.1 |
| Furnace | GPL-2.0-or-later |
| ASAP | GPL-2.0-or-later |
| ZXTune | its own free-software license; keep its file |

---

## Why I made this

I was playing *Touhou 5: Mystic Square* and liked the Music Room, so I made a small keyboard player in that shape.

---

# 繁體中文

## 簡介

`dem_player` 是一個以鍵盤為主、沒有標題列的 Windows 音樂播放器，用 Python 和 PySide6 寫成。

- 已經開著再開一次，檔案會交給同一個視窗。
- 幾乎全部用鍵盤。滑鼠用來拖視窗；加顏色那個視窗、以及清除前的警告，才用滑鼠。
- 格式會自己交給 miniaudio、FFmpeg、OpenMPT、FluidSynth、Furnace、ASAP 或 ZXTune。

## 功能

- 資料夾、M3U、CUE、串流網址
- 收藏 `001`–`512`，可匯出 M3U
- 最近 100 首、播放次數
- 有 mutagen 才讀歌名、專輯、封面
- 16 個內建主題，自己最多再加 24 個顏色
- 背景：`transparent` / `aero` / `solid` / `image`
- 音量條可以跟檔案，也可以跟系統聲音。音量開到 0 仍然會動
- 四種視窗：Normal、Fullscreen、Mini、Bar
- 可選輸出裝置
- 「用這個程式開啟」不會搶走預設播放器
- 舊的設定檔會自動搬過來
- 進入設定時歌不會停。Mini 和 Bar 不能開設定

## 格式

| 後端 | 格式 |
|---|---|
| miniaudio | `.mp3` `.wav` `.flac` `.ogg` |
| FFmpeg | `.m4a` `.aac` `.wma` `.opus` `.alac` `.ape` `.ac3`，以及串流網址 |
| OpenMPT | `.mod` `.xm` `.it` `.s3m` `.mptm` `.mt2` 等 |
| FluidSynth | `.mid` `.midi` `.rmi` `.kar`（要有 SoundFont） |
| Furnace | `.dnm` `.ftm` |
| ASAP | `.sap` `.tm8` `.tm2` 等 |
| ZXTune | `.sid` `.vgm` `.vgz` |
| CUE | `.cue` `.cue.txt` |

## 怎樣行

```bat
pip install -r requirements.txt
python main.py
```

需要 Windows 和 Python 3.10 或更新。第一次會在程式旁邊建立 `data\`。

打包：

```bat
build.bat
```

成品在 `dist\dem_player\`。要給人就複製**整個資料夾**。

`ffmpeg.exe`、`openmpt123.exe`、`fluidsynth.exe`、SoundFont、`furnace.exe`、`asapconv.exe`、`zxtune123.exe` 要放在程式旁邊，`build.bat` 會順便複製已經放在專案裡的那些檔。

## 按鍵

| 按鍵 | 做什麼 |
|---|---|
| `↑` `↓` | 移動 |
| `Enter` | 開啟 / 播放 |
| `Backspace` | 返回 |
| `F1` | 播放 / 暫停 |
| `F2` `F3` | 音量 |
| `F4` | 顯示或收起左邊清單 |
| `F5` | 循環：OFF / SINGLE / LIST / RANDOM |
| `F6` | 視窗模式 |
| `F7` | 設定。在設定裡再按一次也是離開 |
| `F8` | 搜尋 |
| `F9` | 加入或移出收藏 |
| `F10` | 掃描這個資料夾的時長 |
| `Esc` | 重設播放器，並把主題改回 Black & White |
| `←` `→` | 前後 1 秒 |

Mini 不能用 `F4`、`F8`。Mini 和 Bar 不能用 `F7`。

設定裡：`←` `→` 換頁，`↑` `↓` 移動，`Enter` 改那一項，`Esc` 或 `F7` 返回。設定清單本身不用滑鼠。

是／否直接切換。清除、重設、移除資料夾會先出警告，要按 **Yes**。

**Add Colour** 是另一個視窗，只有那裡可以用滑鼠。可輸入 HEX 或 RGB，也可以按色塊。名稱由程式取（Custom 01…），存進 `settings.dpj`。

## 設定五頁

1. **General** — 永遠在最前、播放時允許螢幕保護、主題、時間格式
2. **Audio** — 輸出裝置、音量條、來源、模式
3. **Preference** — 背景、Aero 透明度、背景圖、時長、封面、播放次數
4. **Library** — 加入或移除資料夾、重新整理、掃描時長
5. **Options** — 日誌、「用這個程式開啟」、清除、重設、About

## 授權

**GNU General Public License 第 3 版或更新的版本**（`GPL-3.0-or-later`）。不是第 2 版。

Copyright (C) 2026 999jjkl。

可以自由使用、複製、修改、散佈。散佈時必須用 GPL 第 3 版（或日後的更新版本，不是第 2 版），附上源碼，保留版權聲明。沒有任何保證。全文在 [LICENSE](LICENSE)。

Qt 是 LGPL-3，不能配「只准 GPL-2」。mutagen 寫明第 2 版或更新，所以可以按第 3 版一起用。

你另外下載的 ffmpeg、Furnace、ASAP、FluidSynth、OpenMPT、ZXTune **不是**這個授權能改寫的，那些檔要保留它們自己的授權。

## 為什麼做這個

玩《東方怪綺談》的時候很喜歡 Music Room，所以做了一個鍵盤為主的小播放器。

*this readme use ai
