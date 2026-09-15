 dem_player User Guide
 Version: 0.19.9
 Main program: music_player.py
============================================================
I. Quick Start
------------------------------------------------------------
1. Install Python dependencies:
   pip install PyQt6 python-vlc numpy sounddevice mutagen

   Required:
   - PyQt6
   - python-vlc

   Optional:
   - numpy        : for system audio spectrum
   - sounddevice  : for system audio capture
   - mutagen      : for reading ID3 / album / artist tags

2. Prepare external files and place them in the same directory as music_player.py:
   - VLC: libvlc.dll, libvlccore.dll, plugins/ directory
   - BASS: bass.dll, bassmidi.dll, soundfont.sf2
   - Conversion engines:
     - ffmpeg.exe        : some module formats
     - asapconv.exe      : ASAP / Atari formats
     - zxtune-cli.exe    : SID / VGM
     - zxtune123.exe     : SID / VGM backup
     - furnace.exe       : .dnm / .ftm
   - Optional resources:
     - font.ttf          : custom font
     - FPT.ico           : window / tray icon
     - background.png    : for background image mode
     - soundfont.sf2     : MIDI soundfont

3. Run:
   python music_player.py

4. On first launch, old data is automatically migrated:
   - Old data.json, data.txt, list.txt, love.txt, Cache.json
     are converted to new data files.
   - Old files are usually renamed to *_old2.*.
   - New data files:
     settings.dpst
     play_list.dppls
     play_history_counts.dpphc
     cache.dpch

5. After entering the program:
   - Use F7 to go to the settings page.
   - Select Add Music Folder... to add a music folder.
   - Use arrow keys to select tracks, Enter to play.
   - Main operation is keyboard-based.

============================================================
II. Directory and File Placement
============================================================
Recommended directory structure:

Your folder/
├─ music_player.py
├─ font.ttf
├─ FPT.ico
├─ background.png
├─ libvlc.dll
├─ libvlccore.dll
├─ plugins/
│  └─ ... VLC plugins ...
├─ bass.dll
├─ bassmidi.dll
├─ soundfont.sf2
├─ ffmpeg.exe
├─ asapconv.exe
├─ zxtune-cli.exe
├─ furnace.exe
└─ data/
   └─ player_data_*.log

Data files are written to the "program directory":
- Running .py directly: the directory containing music_player.py.
- Packaged as .exe: the directory containing the .exe.
- Logs: data/player_data_%H.%M.%S-%d.%m.%Y.log.

============================================================
III. Interface Operations
============================================================
Left panel:
- FILE BROWSER: file browsing.
- SETTING: settings page.
- F4: show / hide left panel.
- F7: switch between file page / settings page.

Right panel:
- Track: current track title; scrolls if too long.
- Artist / Album / Track#: music tags.
- Progress bar: current progress and time.
- Loop: loop mode.
- Volume: volume.
- Audio Level: text spectrum.
- Shortcut hints.
- Cover art: displayed if the folder contains cover.jpg, folder.jpg, etc.

Window operations:
- The window is borderless.
- Hold the left mouse button in the top ~40px area of the window to drag.
- While dragging, an outline is shown; the window actually moves after release.
- Top right:
  - : minimize.
  - X: close program.
- System tray icon:
  - Right-click menu: stop, Previous song, Next song, quit.
  - Left click currently does nothing.

Note:
The program sets file_list, settings_list, search_input, progress_text,
volume_text, and most QLabels to mouse-transparent.
Therefore, lists and the settings page are mainly operated by keyboard, not mouse clicks.
The mouse is mainly used to drag the title bar and click the top-right buttons.

============================================================
IV. Shortcut Key List
============================================================
Key            Function
------------------------------------------------------------
↑ / ↓          Move up / down in list
Enter          Open folder / play selected item / open CUE / M3U
Backspace      Return to previous level; when search box has focus, delete character
F1             Toggle play / pause
F2             Volume -1
F3             Volume +1
F4             Show / hide left panel
F5             Loop mode: OFF -> SINGLE -> LIST
F6             Window mode: Normal -> Fullscreen -> Mini -> Bar
F7             Toggle settings page
F8             Focus search box; press again to unfocus
F9             Add / remove favorite
Esc            Reset player state
← / →          Seek back / forward 1 second

When the search box has focus:
- Normal characters are input to the search box.
- Enter executes search.
- Backspace deletes character.

============================================================
V. Settings Page Description
============================================================
Use F7 to enter the settings page, use ↑ / ↓ to select, Enter to execute.

Settings items:
- Always on Top: window always on top Y/N.
- Style: cycle themes.
- Audio Level: whether to show spectrum.
- Audio Level Source: file / system.
- Audio Level Mode: all / volume.
- Output Device: main output device, VLC + BASS synchronized.
- Advanced Audio >>: expand advanced audio.
  - VLC Device: select VLC device separately.
  - BASS Device: select BASS device separately.
  - << Hide Advanced Audio: collapse.
- Show Play Counts: whether Most Played shows play counts.
- Background: transparent / solid / image.
- Log Save: whether to write logs.
- Show Duration: whether to show [AUD mm:ss].
- Show Cover Art: whether to show cover art.
- Time Format: MM:SS.CC / MM:SS.
- Engine Mode: Normal / VLC / BASS.

--- Music Folders ---
- Remove Folder [i]: remove the i-th source folder.
- Add Music Folder...: add a music folder.
- Refresh File List: refresh the current directory.

--- Maintenance ---
- Clear History: clear history.
- Clear Play Counts: clear play counts.
- Clear Favorites: clear favorites.
- Clear Duration Cache: clear duration cache.
- Reset All Settings: reset all settings.

--- About ---
- About dem_player: about this program.

============================================================
VI. Playback Engines and Format Support
============================================================
Engine Mode:
- Normal: auto select.
- VLC: prefer VLC.
- BASS: prefer BASS; fall back to VLC if BASS is unavailable.

Normal mode selection logic:
- If Audio Level is enabled and the format is supported, prefer BASS.
- .mod, .xm, .it, .s3m, .mtm, .umx, .mo3: BASS.
- .mid, .midi, .rmi, .kar: BASS MIDI,
  requires bassmidi.dll + soundfont.sf2.
- .sid, .vgm, .vgz: ZXTune.
- .sap, .cmc, .cm3, .cmr, .cms, .dmc, .dlt,
  .mpt, .mpd, .rmt, .tmc, .tm8, .tm2, .fc: ASAP.
- .mt2, .stm, .ult, .669, .far: libopenmpt / ffmpeg.
- .dnm, .ftm: Furnace.
- Others: VLC.

Supported extensions:
.mp3 .wav .ogg .m4a .flac .dnm .ftm .it .mid .midi .mod
.mptm .mt2 .rmi .s3m .sap .sid .tm8 .xm .vgm .vgz .swf
.opus .alac .aac .wma

Some formats only appear in the list if the corresponding engine exists.

============================================================
VII. File Browsing, M3U, CUE, Favorites, History
============================================================
Source list:
The home page displays:
- [FILE]: music folders you added.
- [LISTxxx] favorites: favorites list.
- [HISTORY]: playback history.
- [MOST] Most Played: play count ranking.

Inside a folder:
- [DIR]: subfolders.
- [CUE]: CUE files.
- [M3U]: M3U / M3U8 playlists.
- [AUD] or [AUD mm:ss]: audio files.
- [..]: return to previous level.

M3U:
Supports:
- Local relative paths.
- Absolute paths.
- http:// / https:// network streams.

CUE:
Supports parsing:
- FILE
- TRACK
- TITLE
- PERFORMER
- INDEX 01

CUE segmented playback:
- VLC: uses :start-time / :stop-time.
- BASS: uses a timer to check end_ms.

Favorites:
- In a normal list, press F9: enter a number 0~512,
  stored as three digits, e.g. 001.
- On the FAVORITES: page, press F9: remove the currently selected item.

History and play counts:
- Successful playback is added to history, max 100 entries, newest first.
- Play counts are incremented.
- Most Played is sorted by play count.

============================================================
VIII. Audio Output Devices
============================================================
Main output device:
Settings page -> Output Device:
- Lists available VLC devices.
- Selecting one synchronizes VLC and BASS.
- System Default means the default device.

Advanced audio:
Settings page -> Advanced Audio >>:
- VLC Device: only changes VLC.
- BASS Device: only changes BASS.
- BASS devices are matched by name.

When switching devices:
- Current playback stops.
- VLC player and BASS engine are rebuilt.
- If it was playing, it tries to resume playback after 500ms.

============================================================
IX. Audio Spectrum / Audio Level
============================================================
After enabling Audio Level, the right side displays:
- Bass:
- Mid:
- Treble:
- Volume:

Source = file:
- BASS playback: take BASS level directly.
- VLC playback: use an extra BASS decode stream for FFT
  to get Bass / Mid / Treble.
- Requires BASS to be available.

Source = system:
- Use sounddevice to capture system audio.
- Looks for loopback, stereo mix, Stereo Mix.
- Requires numpy and sounddevice.
- If not found, falls back to file.

Mode:
- all: display Bass / Mid / Treble / Volume.
- volume: display only Volume.

Note:
If Engine Mode = VLC, the spectrum resets to zero
to avoid extra decoding load.

============================================================
X. Data Files and Migration
============================================================
New data files:
- settings.dpst: settings.
- play_list.dppls: source folders and favorites.
- play_history_counts.dpphc: history and play counts.
- cache.dpch: folder duration scan cache.

Legacy support:
- Cache.json, Cache_old2.json
- data.json, data_old2.json
- data.txt, data_old2.txt
- list.txt, list_old2.txt
- love.txt, love_old2.txt

On first launch, if the new files do not exist, migration happens automatically.
If all three main new files exist, no migration occurs.

These are JSON format and can be manually edited after closing the program.

============================================================
XI. Logs
============================================================
- Enabled by default.
- Path: data/player_data_%H.%M.%S-%d.%m.%Y.log
- Can be toggled in the settings page with Log Save.
- Default log level is INFO = 20.
- Can record:
  - Startup / shutdown.
  - Data migration.
  - VLC / BASS initialization.
  - Playing files.
  - Errors and exceptions.

If the program crashes, first check the latest log in data/.

============================================================
XII. Packaging as EXE
============================================================
PyInstaller can be used. Windows example:

pyinstaller --noconfirm --windowed --name dem_player ^
  --add-data "font.ttf;." ^
  --add-data "FPT.ico;." ^
  --add-data "background.png;." ^
  --add-data "soundfont.sf2;." ^
  --add-binary "bass.dll;." ^
  --add-binary "bassmidi.dll;." ^
  --add-binary "libvlc.dll;." ^
  --add-binary "libvlccore.dll;." ^
  --add-data "plugins;plugins" ^
  --add-binary "ffmpeg.exe;." ^
  --add-binary "asapconv.exe;." ^
  --add-binary "zxtune-cli.exe;." ^
  --add-binary "furnace.exe;." ^
  music_player.py

Note:
- On Windows, the --add-data separator is ;.
- VLC usually needs the entire plugins/ directory, not just libvlc.dll.
- After packaging, resources are in _MEIPASS; the program uses resource_path() to find them.
- Data files are written to the directory containing the .exe.
- If an optional file is missing, the corresponding --add-* can be omitted.

============================================================
XIII. FAQ
============================================================
1. Program crashes
   Check data/player_data_*.log.
   The most common cause is missing VLC / BASS DLLs or a bitness mismatch.

2. VLC fails to initialize
   Check:
   - libvlc.dll
   - libvlccore.dll
   - plugins/
   - Same bitness as Python / EXE, e.g. both 64-bit.

3. BASS unavailable
   Check:
   - bass.dll
   - bassmidi.dll (only needed for MIDI)
   - soundfont.sf2

4. No MIDI sound
   Requires bassmidi.dll + soundfont.sf2.
   If BASS MIDI is unavailable, it falls back to VLC.

5. Spectrum not moving
   Check:
   - Audio Level is enabled.
   - numpy is installed.
   - BASS is available.
   - Engine Mode is not VLC.
   - If Audio Level Source is set to system,
     sounddevice and Stereo Mix / loopback are required.

6. Cannot play .dnm / .ftm
   Requires furnace.exe.

7. Cannot play SID / VGM
   Requires zxtune-cli.exe or zxtune123.exe.

8. Cannot play ASAP formats
   Requires asapconv.exe.

9. Cannot play MT2 / STM / ULT / 669 / FAR
   Requires ffmpeg.exe.

10. List cannot be clicked with the mouse
    This is by design. Use ↑ / ↓ and Enter.
    The mouse is mainly for title bar dragging and the top-right buttons.

11. Data not saved
    Make sure the program directory is writable.
    If placed in Program Files, you may need to move it to another directory or run as administrator.

============================================================
XIV. Recommended Usage Flow
============================================================
1. Install dependencies.
2. Place VLC / BASS / conversion engines and resources.
3. Run python music_player.py.
4. F7 -> Add Music Folder... to add music.
5. Use ↑ / ↓ to select a folder, Enter to enter.
6. Select a track, Enter to play.
7. F1 pause, F2 / F3 adjust volume, F5 change loop.
8. F8 search, F9 favorite.
9. F6 switch window mode.
10. The settings page can adjust audio device, theme, background, spectrum, and engine mode.
11. On close, settings, history, play counts, and cache are saved automatically.
