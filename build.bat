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
call :copy_if ffmpeg.exe
call :copy_if ffprobe.exe
call :copy_if openmpt123.exe
call :copy_if libopenmpt.dll
call :copy_if openmpt-mpg123.dll
call :copy_if fluidsynth.exe
call :copy_if libfluidsynth-3.dll
call :copy_if SDL3.dll
call :copy_if sndfile.dll
call :copy_if furnace.exe
call :copy_if asapconv.exe
call :copy_if zxtune123.exe
call :copy_if zxtune-cli.exe
call :copy_if font.ttf
call :copy_if FPT.ico
call :copy_if Background.png
call :copy_if background.png
call :copy_if soundfont.sf2
call :copy_if FluidR3_GM.sf2
call :copy_if weedsgm3.sf2

echo.
echo [build] DONE
echo        Run:  %CD%\%OUT%\dem_player.exe
echo        Copy the whole folder  dist\dem_player  to share it.
echo        Optional: copy your  data\  folder next to the exe to keep playlists.
echo.
pause
exit /b 0

:copy_if
if exist "%~1" (
    copy /Y "%~1" "%OUT%\%~1" >nul
    echo   + %~1
) else (
    echo   - %~1  (not in this folder, skipped)
)
exit /b 0

:fail
echo [build] FAILED
pause
exit /b 1
