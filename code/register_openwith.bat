@echo off
REM Register dem_player.exe so Explorer "Open with" lists it.
set "EXE=%~dp0dem_player.exe"
if not exist "%EXE%" set "EXE=%~dp0dist\dem_player\dem_player.exe"
if not exist "%EXE%" (
  echo No dem_player.exe next to this bat.
  echo Build with build.bat first, then run this again.
  echo Until then you can still run:  python main.py "song.mp3"
  pause
  exit /b 1
)
reg add "HKCU\Software\Classes\Applications\dem_player.exe\shell\open\command" /ve /d "\"%EXE%\" \"%%1\"" /f >nul
reg add "HKCU\Software\Classes\Applications\dem_player.exe" /v FriendlyAppName /d "dem_player" /f >nul
for %%E in (mp3 wav flac ogg m4a aac wma opus mid midi rmi mod xm it s3m mptm mp3) do (
  reg add "HKCU\Software\Classes\.%%E\OpenWithList\dem_player.exe" /f >nul
)
echo Registered:
echo   %EXE%
echo Right-click a song - Open with - dem_player
pause
