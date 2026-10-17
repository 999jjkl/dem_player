@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if /I "%~1"=="debug" (
    set DEM_PLAYER_CONSOLE=1
    echo [build] debug console ON
) else (
    set DEM_PLAYER_CONSOLE=0
)

echo [build] installing PyInstaller + runtime deps
python -m pip install -r requirements.txt "pyinstaller>=6.11" || goto :fail

echo [build] pyinstaller onedir
python -m PyInstaller --noconfirm --clean dem_player.spec || goto :fail

set "OUT=dist\dem_player"
if not exist "%OUT%\dem_player.exe" (
    echo [build] exe missing: %OUT%\dem_player.exe
    goto :fail
)

echo [build] copying sidecar tools next to the exe
for %%F in (
    ffmpeg.exe
    ffprobe.exe
    openmpt123.exe
    libopenmpt.dll
    openmpt-mpg123.dll
    fluidsynth.exe
    libfluidsynth-3.dll
    SDL3.dll
    sndfile.dll
    furnace.exe
    asapconv.exe
    zxtune123.exe
    zxtune-cli.exe
    font.ttf
    FPT.ico
    Background.png
    background.png
    soundfont.sf2
    FluidR3_GM.sf2
    weedsgm3.sf2
) do (
    if exist "%%~F" (
        copy /Y "%%~F" "%OUT%\%%~F" >nul
        echo   + %%~F
    ) else (
        echo   - %%~F skipped
    )
)

echo.
echo [build] DONE
echo        Run:  %CD%\%OUT%\dem_player.exe
echo        Copy the whole folder  dist\dem_player  to share it.
echo        Optional: copy your  data\  folder next to the exe to keep playlists.
echo        If furnace.exe was missing last time, copy it into that folder now.
echo.
pause
exit /b 0

:fail
echo [build] FAILED
pause
exit /b 1
