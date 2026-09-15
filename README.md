# dem_player

**dem_player** is a feature-rich, keyboard-driven music player built with Python and PySide6. It supports a wide range of audio formats through multiple playback engines (VLC, BASS, and native), offers extensive customization, and provides a sleek, borderless interface with a focus on usability.

---

## Features

- **Multi-Engine Playback**: Supports VLC, BASS, and a native engine for maximum format compatibility.
- **Wide Format Support**: Plays MP3, FLAC, WAV, OGG, MIDI, SID, VGM, Atari formats, and many more via external conversion tools.
- **Keyboard-Centric UI**: Nearly all operations are accessible via keyboard shortcuts (see [Shortcut Keys](#shortcut-keys)).
- **Customizable Themes**: Multiple built-in styles with options for transparent, solid, or image backgrounds.
- **Audio Visualization**: Real-time audio spectrum display (requires `numpy` and `sounddevice`).
- **Playlist & Favorites**: Create playlists, mark favorites, and track play counts.
- **Metadata Display**: Shows track title, artist, album, cover art, and duration (requires `mutagen`).
- **System Tray Integration**: Control playback and minimize to tray.
- **Data Migration**: Automatically migrates old data formats on first launch.

---

## Installation

### Prerequisites

- Python 3.8 or higher
- Windows OS (primary platform; other platforms may require additional configuration)

### Python Dependencies

Install the required Python packages:

```bash
python -m pip install PySide6 python-vlc
```

Optional dependencies for enhanced features:

```bash
python -m pip install numpy sounddevice mutagen
```

- `numpy` — for system audio spectrum analysis
- `sounddevice` — for system audio capture
- `mutagen` — for reading ID3/album/artist tags

### External Files

Place the following files in the same directory as `music_player.py`:

| File / Folder | Purpose |
|---------------|---------|
| `libvlc.dll` | VLC runtime |
| `libvlccore.dll` | VLC core runtime |
| `plugins/` | VLC plugins directory |
| `bass.dll` | BASS audio library |
| `bassmidi.dll` | BASS MIDI support |
| `soundfont.sf2` | MIDI soundfont |
| `ffmpeg.exe` | Conversion engine for some module formats |
| `asapconv.exe` | ASAP / Atari format conversion |
| `zxtune-cli.exe` | SID / VGM playback |
| `zxtune123.exe` | SID / VGM backup |
| `furnace.exe` | .dnm / .ftm format support |
| `font.ttf` | Optional custom font |
| `FPT.ico` | Window / tray icon (optional) |
| `background.png` | Background image (optional) |

# Where to get 

(https://github.com/tildearrow/furnace/releases)
(https://www.videolan.org/vlc/)
(https://www.un4seen.com/)
(https://musical-artifacts.com/)
(https://github.com/BtbN/FFmpeg-Builds/releases)
(https://asap.sourceforge.net/)
(https://zxtune.bitbucket.io/)

### Running

```bash
python music_player.py
```
On first launch, the player automatically create (`settings.dpst`, `play_list.dppls`, `play_history_counts.dpphc`, `cache.dpch`)
If you previously used an older version, the player will automatically migrates old data files (`data.json`, `data.txt`, `list.txt`, `love.txt`, `Cache.json`) to the new format (`settings.dpst`, `play_list.dppls`, `play_history_counts.dpphc`, `cache.dpch`). Old files are renamed to `*_old2.*`.

---

## Usage

### Quick Start

1. Launch the player.
2. Press **F7** to open the settings page.
3. Select **Add Music Folder...** to add a music folder.
4. Use **arrow keys** to navigate tracks, **Enter** to play.
5. The interface is primarily keyboard-operated; use the mouse mainly to drag the window or click the minimize/close buttons.

### Interface Overview

- **Left Panel**: File browser and settings page (toggle with **F4**).
- **Right Panel**: Track information, progress bar, loop mode, volume, audio level, cover art.
- **System Tray**: Right-click for stop, previous, next, and quit options.

### Shortcut Keys

| Key | Function |
|-----|----------|
| ↑ / ↓ | Move up / down in list |
| Enter | Open folder / play selected / open CUE / M3U |
| Backspace | Return to previous level; delete character in search box |
| F1 | Toggle play / pause |
| F2 | Volume −1 |
| F3 | Volume +1 |
| F4 | Show / hide left panel |
| F5 | Loop mode: OFF → SINGLE → LIST |
| F6 | Window mode: Normal → Fullscreen → Mini → Bar |
| F7 | Toggle settings page |
| F8 | Focus search box; press again to unfocus |
| F9 | Add / remove favorite |
| Esc | Reset player state |
| ← / → | Seek back / forward 1 second |

When the search box is focused, normal characters are input, **Enter** executes search, and **Backspace** deletes characters.

### Settings Page (F7)

| Setting | Description |
|---------|-------------|
| Always on Top | Window stays above others |
| Style | Cycle through themes |
| Audio Level | Show / hide spectrum |
| Audio Level Source | File or system audio |
| Audio Level Mode | All or volume-only |
| Output Device | Main output device (VLC + BASS synchronized) |
| Advanced Audio | Expand for separate VLC and BASS device selection |
| Show Play Counts | Show play counts in Most Played |
| Background | Transparent / solid / image |
| Log Save | Enable or disable logging |
| Show Duration | Show `[AUD mm:ss]` |
| Show Cover Art | Display cover art |
| Time Format | `MM:SS.CC` or `MM:SS` |
| Engine Mode | Normal / VLC / BASS |

**Maintenance** options include clearing history, play counts, favorites, duration cache, and resetting all settings.

---

## Configuration

Data files are stored in the program directory:

- Running `.py` directly: the directory containing `music_player.py`.
- Packaged as `.exe`: the directory containing the `.exe`.
- Logs: `data/player_data_%H.%M.%S-%d.%m.%Y.log`.

---

## Acknowledgements

- Built with [PySide6](https://pypi.org/project/PySide6/) and [python-vlc](https://github.com/oaubert/python-vlc).
- Uses [VLC](https://www.videolan.org/vlc/) and [BASS](https://www.un4seen.com/) for audio playback.
- Format conversion powered by [FFmpeg](https://ffmpeg.org/), [ASAP](https://asap.sourceforge.net/), [ZXTune](https://zxtune.bitbucket.io/), and [Furnace](https://github.com/tildearrow/furnace).

---

## Why i make this

When I was playing Touhou 5, I really liked its Musicroom ui interface layout,so i make dem_player.
