# dem_player User Guide (Version: 0.19.10)

## Quick Start & Installation
To get your music playing, you will need to set up the Python environment and audio engines:
*   Install the necessary Python dependencies by running `pip install PySide6 python-vlc numpy sounddevice mutagen`.
*   Ensure all required external files, such as `libvlc.dll`, `bass.dll`, and conversion engines like `ffmpeg.exe` or `zxtune-cli.exe`, are placed in the exact same directory as `music_player.py`.
*   When you run the program for the first time, your older data files (like `data.json` or `Cache.json`) will automatically be migrated to the new formats.

## Interface & Navigation
dem_player features a dual-panel layout but is uniquely designed to be driven by your keyboard rather than your mouse. 
*   **Left Panel:** This area houses your File Browser and Settings; you can toggle between them quickly by pressing `F7`.
*   **Right Panel:** This side displays your scrolling track title, metadata, progress bar, and a dynamic text-based audio spectrum.
*   **Mouse Usage:** Because the lists and menus are mostly "mouse-transparent," your mouse is primarily used to drag the borderless window by clicking its top 40 pixels, or to use the top-right window controls.

## Essential Keyboard Shortcuts
Master these key bindings to control your playback seamlessly:

| Key | Function |
| :--- | :--- |
| **Up / Down** | Move up or down in the current list |
| **Enter** | Play the selected track or open a folder |
| **F1** | Toggle Play / Pause |
| **F2 / F3** | Decrease / Increase Volume |
| **F4** | Show or hide the left panel |
| **F5** | Cycle loop modes (OFF, SINGLE, LIST) |
| **F8** | Focus the search box to find a track |
| **F9** | Add or remove a track from your favorites |

## Audio Engines & Formats
The player is built to handle a massive variety of formats by routing them through the best available engine. In "Normal" mode, the player automatically selects the engine: it prefers BASS for tracker modules (`.mod`, `.it`) and MIDI, ZXTune for chiptunes (`.sid`, `.vgm`), ASAP for Atari formats, and falls back to VLC for standard audio files.
