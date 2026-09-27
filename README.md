# dem_player

A keyboard-first music player built with Python and PySide6.  
It focuses on quick local playback, flexible format support, theme customization, and a compact desktop UI.

---

## English

### Overview
`dem_player` is a feature-rich music player designed for fast keyboard control and a borderless workflow. It can browse local folders, play many common and niche formats, support playlists and favorites, and offer real-time audio visualization.

### Features
- Keyboard-driven UI and shortcuts
- Local folder browser and playlist support
- Favorites and play-history tracking
- Play counts and metadata display
- Theme / background customization
- Real-time audio level visualization
- Cover art and track info display
- Borderless and compact window modes
- Automatic migration of older data files

### Playback Backends
The project uses:
- miniaudio for common formats
- FFmpeg for additional format support
- libopenmpt / openmpt123 for MOD/XM/IT/S3M/MPTM-style formats
- FluidSynth for MIDI / RMI playback
- Furnace / ASAP / ZXTune for chiptune and niche formats

### Requirements
- Python 3.8 or newer
- Windows (primary supported platform)

Install required Python packages:
```bash
python -m pip install PySide6
```

Optional packages for extra features:
```bash
python -m pip install numpy sounddevice mutagen
```

- `numpy` — audio visualization
- `sounddevice` — system audio capture
- `mutagen` — metadata and cover art

### Sidecar Tools
Place the following files next to `music_player.py` or the packaged `.exe`:

| File / Tool | Purpose |
|-------------|---------|
| `ffmpeg.exe` | decode extra formats |
| `ffprobe.exe` | optional ffmpeg support checks |
| `openmpt123.exe` | MOD / XM / IT / S3M / MPTM playback |
| `libopenmpt.dll` | native openmpt library |
| `fluidsynth.exe` | MIDI rendering |
| `libfluidsynth-3.dll` | FluidSynth runtime |
| `soundfont.sf2` | MIDI soundfont |
| `furnace.exe` | DNM / FTM support |
| `asapconv.exe` | ASAP format conversion |
| `zxtune-cli.exe` | SID / VGM conversion/play support |
| `zxtune123.exe` | backup runner |
| `font.ttf` | custom font |
| `FPT.ico` | app/tray icon |
| `background.png` | default background |
| `Background/custom_background.png` | optional custom background |

Useful links:
- FFmpeg: https://github.com/BtbN/FFmpeg-Builds/releases
- openmpt: https://github.com/OpenMPT/openmpt
- FluidSynth: https://www.fluidsynth.org/
- Furnace: https://github.com/tildearrow/furnace/releases
- ASAP: https://asap.sourceforge.net/
- ZXTune: https://zxtune.bitbucket.io/

### Running
```bash
python music_player.py
```

On first launch, the app creates data files such as:
- `data/settings.dpj`
- `data/play_list.dpj`
- `data/play_history.dpj`
- `data/cache.dpj`

If legacy files are detected from older versions, they are migrated automatically and renamed with `*_old2.*`.

### Quick Start
- When you set up the player for the first time: press `F7`, choose `Add Music Folder...`, and add one or more music folders.

1. Launch the player.
2. Press `F7` to open Settings.
3. Select Add Music Folder... to add a folder.
4. Use arrow keys to navigate and press Enter to play.
5. Most operations are keyboard-first. Mouse is mainly for dragging, resizing, and tray behavior.

### Shortcut Keys
| Key | Action |
|-----|--------|
| ↑ / ↓ | Move up / down |
| Enter | Open / play selected item |
| Backspace | Go back / delete search text |
| F1 | Play / pause |
| F2 | Volume -1 |
| F3 | Volume +1 |
| F4 | Toggle left panel |
| F5 | Loop mode |
| F6 | Window mode |
| F7 | Toggle settings |
| F8 | Focus search |
| F9 | Favorites |
| Esc | Reset player |
| ← / → | Seek backward / forward |

### Settings
The settings page includes:
- Always on Top
- Theme selection
- Audio level display
- Audio level source
- Audio level mode
- Output device selection
- Show play counts
- Background image
- Log saving
- Show duration
- Show cover art
- Time format

Maintenance actions include:
- clear history
- clear favorite lists
- clear play counts
- clear duration cache
- reset all settings

### Data and Logs
- Running directly from Python: data folder is beside `music_player.py`
- Running packaged `.exe`: data folder is beside the executable
- Logs are kept under:
  `data/logs/player_data_%H.%M.%S-%d.%m.%Y.log`

### Acknowledgements
- PySide6
- miniaudio
- FFmpeg
- openmpt / libopenmpt
- FluidSynth
- Furnace / ASAP / ZXTune

---

## 繁體中文 (zh-TW)

### 簡介
`dem_player` 是一款以鍵盤操作為核心的音樂播放器，重點在於快速播放、本地資料夾瀏覽、可自訂主題，以及簡潔的桌面介面。

### 功能
- 鍵盤優先的操作方式
- 本地資料夾瀏覽與播放清單
- 收藏清單與播放歷史
- 播放次數統計與 metadata 顯示
- 主題與背景自訂
- 即時音頻等級顯示
- 封面圖與曲目資訊
- 無邊框 / 精簡視窗模式
- 舊版資料自動遷移

### 播放後端
本專案使用：
- miniaudio
- FFmpeg
- libopenmpt / openmpt123
- FluidSynth
- Furnace / ASAP / ZXTune

### 系統需求
- Python 3.8 或以上
- Windows（主要支援平台）

安裝必要套件：
```bash
python -m pip install PySide6
```

可選增強功能：
```bash
python -m pip install numpy sounddevice mutagen
```

- `numpy`：音頻可視化
- `sounddevice`：系統音訊擷取
- `mutagen`：metadata / 封面資料

### 需要放在同目錄的工具
| 檔案 / 工具 | 用途 |
|-------------|------|
| `ffmpeg.exe` | 解碼更多格式 |
| `ffprobe.exe` | ffmpeg 檢查 |
| `openmpt123.exe` | MOD / XM / IT / S3M / MPTM |
| `libopenmpt.dll` | libopenmpt 執行庫 |
| `fluidsynth.exe` | MIDI 渲染 |
| `libfluidsynth-3.dll` | FluidSynth 執行庫 |
| `soundfont.sf2` | MIDI 音色庫 |
| `furnace.exe` | DNM / FTM |
| `asapconv.exe` | ASAP 格式轉換 |
| `zxtune-cli.exe` | SID / VGM |
| `zxtune123.exe` | 備用執行器 |
| `font.ttf` | 自訂字型 |
| `FPT.ico` | 應用程式/系統匣圖示 |
| `background.png` | 預設背景 |
| `Background/custom_background.png` | 自訂背景 |

### 執行方式
```bash
python music_player.py
```

首次啟動時會建立：
- `data/settings.dpj`
- `data/play_list.dpj`
- `data/play_history.dpj`
- `data/cache.dpj`

若偵測到舊版資料，程式會自動轉移並保留舊檔為 `*_old2.*`。

### 快速使用
- 首次設定時請按 `F7`，選擇 `Add Music Folder...`，並加入一個或多個音樂資料夾。

1. 啟動播放器。
2. 按 `F7` 開啟設定頁。
3. 選擇 Add Music Folder... 加入音樂資料夾。
4. 使用方向鍵瀏覽，Enter 播放。
5. 大多數操作都以鍵盤為主，滑鼠主要用於拖曳與系統匣操作。

### 快捷鍵
| 按鍵 | 功能 |
|------|------|
| ↑ / ↓ | 上下移動 |
| Enter | 開啟 / 播放 |
| Backspace | 返回上一層 / 刪除搜尋文字 |
| F1 | 播放 / 暫停 |
| F2 | 音量 -1 |
| F3 | 音量 +1 |
| F4 | 顯示 / 隱藏左側面板 |
| F5 | 循環模式 |
| F6 | 視窗模式 |
| F7 | 設定 |
| F8 | 搜尋框 |
| F9 | 收藏 |
| Esc | 重設播放器 |
| ← / → | 倒退 / 前進 |

### 設定
設定頁支援：
- 常駐最前
- 主題切換
- 音頻等級顯示
- 音訊來源
- 輸出裝置選擇
- 顯示播放次數
- 背景圖片
- 記錄儲存
- 顯示時長
- 顯示封面
- 時間格式

維護功能包括：
- 清除歷史
- 清除最愛
- 清除播放次數
- 清除時長快取
- 重設所有設定

### 資料與日誌
- 直接執行 Python：資料位於 `music_player.py` 同目錄下的 `data/`
- 打包成 `.exe`：資料位於執行檔同目錄下
- 日誌位置：
  `data/logs/player_data_%H.%M.%S-%d.%m.%Y.log`

### 致謝
- PySide6
- miniaudio
- FFmpeg
- openmpt / libopenmpt
- FluidSynth
- Furnace / ASAP / ZXTune

---

## Why I made this

When I was playing Touhou 5, I really liked the Musicroom-style UI layout, so I made `dem_player` as a compact, keyboard-driven player for local music.

