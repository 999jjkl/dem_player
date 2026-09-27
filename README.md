# dem_player

A feature-rich, keyboard-driven music player written in Python and PySide6. It supports multiple playback engines (VLC, BASS, and native), many audio formats, a highly customizable interface, and a keyboard-first, borderless desktop experience.

---

## English

### Features
- Multi-engine playback: VLC, BASS, or native engine
- Wide format support for MP3, FLAC, WAV, OGG, MIDI, SID, VGM, Atari, and more
- Keyboard-centric interface with extensive shortcut support
- Customizable themes with transparent, solid, or image backgrounds
- Real-time audio spectrum visualization (requires numpy and sounddevice)
- Playlist management, favorites, and play counts
- Metadata display, cover art, and track info (requires mutagen)
- System tray integration and compact window modes
- Automatic migration of older data formats on first launch

### Requirements
- Python 3.8 or higher
- Windows (primary target; other platforms may require extra configuration)

Required Python packages:
```bash
python -m pip install PySide6 python-vlc
```

Optional packages for extended features:
```bash
python -m pip install numpy sounddevice mutagen
```

- numpy: audio spectrum visualization
- sounddevice: system audio capture
- mutagen: metadata, tags, album/artist/cover art

### External runtime files
Place the following files in the same directory as `music_player.py` or the packaged `.exe`:

| File / Folder | Purpose |
|---------------|---------|
| `libvlc.dll` | VLC runtime |
| `libvlccore.dll` | VLC core runtime |
| `plugins/` | VLC plugin directory |
| `bass.dll` | BASS audio library |
| `bassmidi.dll` | BASS MIDI support |
| `soundfont.sf2` | MIDI soundfont |
| `ffmpeg.exe` | Conversion engine for some formats |
| `asapconv.exe` | ASAP / Atari format conversion |
| `zxtune-cli.exe` | SID / VGM playback |
| `zxtune123.exe` | SID / VGM backup |
| `furnace.exe` | `.dnm` / `.ftm` support |
| `font.ttf` | Optional custom font |
| `FPT.ico` | Optional window / tray icon |
| `background.png` | Optional background image |

Useful download links:
- Furnace: https://github.com/tildearrow/furnace/releases
- VLC: https://www.videolan.org/vlc/
- BASS: https://www.un4seen.com/
- FFmpeg: https://github.com/BtbN/FFmpeg-Builds/releases
- ASAP: https://asap.sourceforge.net/
- ZXTune: https://zxtune.bitbucket.io/

### Running
```bash
python music_player.py
```

On first launch, the player creates the following data files:
- `settings.dpst`
- `play_list.dppls`
- `play_history_counts.dpphc`
- `cache.dpch`

If an older version is detected, it automatically migrates legacy files such as `data.json`, `data.txt`, `list.txt`, `love.txt`, and `Cache.json` into the new format. Old files are renamed with `*_old2.*`.

### Quick Start
1. Launch the player.
2. Press F7 to open Settings.
3. Select Add Music Folder... to add a folder.
4. Use arrow keys to navigate and press Enter to play.
5. Most operations are keyboard-first; mouse use is mainly for drag/resize and tray controls.

### Shortcut Keys
| Key | Function |
|-----|----------|
| ↑ / ↓ | Move up / down |
| Enter | Open folder / play selected / open CUE / M3U |
| Backspace | Return to previous level / delete character in search |
| F1 | Toggle play / pause |
| F2 | Volume −1 |
| F3 | Volume +1 |
| F4 | Show / hide left panel |
| F5 | Loop mode: OFF → SINGLE → LIST |
| F6 | Window mode: Normal → Fullscreen → Mini → Bar |
| F7 | Toggle settings page |
| F8 | Focus search box / unfocus |
| F9 | Add / remove favorite |
| Esc | Reset player state |
| ← / → | Seek backward / forward 1 second |

When the search box is focused, normal characters are entered and Enter executes a search.

### Settings Page
The settings page includes options such as:
- Always on Top
- Style / themes
- Audio level display
- Audio level source
- Output device selection
- Show play counts
- Background mode
- Log saving
- Show duration
- Show cover art
- Time format
- Engine mode: Normal / VLC / BASS

Maintenance options include clearing history, favorites, play counts, duration cache, and resetting all settings.

### Configuration
Data files are stored in the program directory:
- Running `.py` directly: same folder as `music_player.py`
- Running a packaged `.exe`: same folder as the `.exe`
- Logs: `data/player_data_%H.%M.%S-%d.%m.%Y.log`

### Acknowledgements
- Built with PySide6 and python-vlc
- Uses VLC and BASS for audio playback
- Format conversion powered by FFmpeg, ASAP, ZXTune, and Furnace

---

## 繁體中文 (zh-TW)

### 功能
- 多播放引擎支援：VLC、BASS、原生引擎
- 廣泛格式支援：MP3、FLAC、WAV、OGG、MIDI、SID、VGM、Atari 等
- 以鍵盤為主的操作體驗，支援大量快捷鍵
- 可自訂主題：透明、純色、圖片背景
- 即時音頻頻譜顯示（需安裝 numpy 和 sounddevice）
- 播放清單、收藏夾、播放次數統計
- 歌曲資訊、封面���曲目資料（需 mutagen）
- 系統匣整合與精簡模式
- 首次啟動時自動遷移舊資料格式

### 安裝需求
- Python 3.8 或以上
- Windows（主要支援平台；其他平台可能需要額外設定）

安裝所需套件：
```bash
python -m pip install PySide6 python-vlc
```

額外功能可選套件：
```bash
python -m pip install numpy sounddevice mutagen
```

- numpy：音頻頻譜分析
- sounddevice：系統音訊擷取
- mutagen：讀取標籤 / 封面 / 歌手 / 專輯資訊

### 外部執行檔與資源
將以下檔案放在 `music_player.py` 或打包後 `.exe` 同一目錄中：

| 檔案 / 資料夾 | 用途 |
|---------------|------|
| `libvlc.dll` | VLC 執行庫 |
| `libvlccore.dll` | VLC 核心執行庫 |
| `plugins/` | VLC 插件目錄 |
| `bass.dll` | BASS 音訊函式庫 |
| `bassmidi.dll` | BASS MIDI 支援 |
| `soundfont.sf2` | MIDI 音色庫 |
| `ffmpeg.exe` | 部分格式轉檔引擎 |
| `asapconv.exe` | ASAP / Atari 格式轉換 |
| `zxtune-cli.exe` | SID / VGM 播放 |
| `zxtune123.exe` | SID / VGM 備用工具 |
| `furnace.exe` | `.dnm` / `.ftm` 支援 |
| `font.ttf` | 可選自訂字型 |
| `FPT.ico` | 可選視窗 / 系統匣圖示 |
| `background.png` | 可選背景圖片 |

常用下載來源：
- Furnace: https://github.com/tildearrow/furnace/releases
- VLC: https://www.videolan.org/vlc/
- BASS: https://www.un4seen.com/
- FFmpeg: https://github.com/BtbN/FFmpeg-Builds/releases
- ASAP: https://asap.sourceforge.net/
- ZXTune: https://zxtune.bitbucket.io/

### 執行方式
```bash
python music_player.py
```

首次啟動時，程式會建立以下資料：
- `settings.dpst`
- `play_list.dppls`
- `play_history_counts.dpphc`
- `cache.dpch`

若偵測到舊版本資料，會自動遷移舊檔（例如 `data.json`、`data.txt`、`list.txt`、`love.txt`、`Cache.json`），並將舊檔改名為 `*_old2.*`。

### 快速使用
1. 啟動播放器。
2. 按 F7 開啟設定頁。
3. 選擇 Add Music Folder... 加入音樂資料夾。
4. 使用方向鍵瀏覽，Enter 播放。
5. 以鍵盤操作為主，滑鼠主要用於拖曳視窗與最小化 / 關閉。

### 快捷鍵
| Key | 功能 |
|-----|------|
| ↑ / ↓ | 上下移動 |
| Enter | 開啟資料夾 / 播放所選項目 / 開啟 CUE / M3U |
| Backspace | 回上一層 / 刪除搜尋字元 |
| F1 | 播放 / 暫停 |
| F2 | 音量 −1 |
| F3 | 音量 +1 |
| F4 | 顯示 / 隱藏左側面板 |
| F5 | 循環模式：OFF → SINGLE → LIST |
| F6 | 視窗模式：Normal → Fullscreen → Mini → Bar |
| F7 | 開關設定頁 |
| F8 | 聚焦 / 取消搜尋框 |
| F9 | 新增 / 移除最愛 |
| Esc | 重設播放器狀態 |
| ← / → | 倒退 / 前進 1 秒 |

當搜尋框聚焦時，可直接輸入內容，按 Enter 執行搜尋。

### 設定頁面
設定頁包含以下內容：
- 常駐最前
- 風格 / 主題
- 音頻等級顯示
- 音頻來源
- 輸出裝置選擇
- 顯示播放次數
- 背景模式
- 記錄存檔
- 顯示時長
- 顯示封面
- 時間格式
- 引擎模式：Normal / VLC / BASS

維護選項包含：清除歷史紀錄、收藏、播放次數、時長快取，以及重設所有設定。

### 資料位置與日誌
- 直接執行 `.py`：資料放在 `music_player.py` 同目錄
- 執行打包後 `.exe`：資料放在 `.exe` 同目錄
- 日誌位置：`data/player_data_%H.%M.%S-%d.%m.%Y.log`

### 致謝
- 使用 PySide6 與 python-vlc 開發
- 以 VLC 與 BASS 作為播放引擎
- 透過 FFmpeg、ASAP、ZXTune、Furnace 提供特殊格式支援

---

## Why I made this
When I was playing Touhou 5, I really liked the Musicroom UI layout, so I made dem_player.

## 為什麼做這個
當我在玩 Touhou 5 時，我很喜歡 Musicroom 的 UI 佈局，因此我做了 dem_player。
