@echo off
rem Install-StruKit.bat - double-click once on each computer. It can be run from anywhere (the Desktop is fine).
rem It puts StruKit in Documents\strukit (beside HydroKit), links this computer to StruKit on GitHub, sets up the
rem automatic update (every 2 hours), downloads the Python runtime StruKit needs (about 35 MB, once), puts a
rem StruKit icon on the Desktop and opens StruKit. Running it again is safe.
setlocal EnableExtensions
title Install StruKit
set "G=C:\Program Files\Git\cmd\git.exe"
set "PATH=C:\Program Files\Git\cmd;%PATH%"
set "R=C:\ZET-G\StruKit"
set "DOCS="
for /f "usebackq delims=" %%d in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('MyDocuments')"`) do set "DOCS=%%d"
if not defined DOCS ( echo  STOPPED: could not find the Documents folder. Tell Claude. & pause & exit /b 1 )
set "T=%DOCS%\strukit"
echo.
echo  StruKit will be installed and kept up to date in:
echo    %T%
echo.
if not exist "%G%" ( echo  STOPPED: Git is not installed on this computer ^(HydroKit's update needs it too^). Tell Claude. & pause & exit /b 1 )
if not exist "C:\ZET-G" mkdir "C:\ZET-G"
if not exist "%T%" mkdir "%T%"
if not exist "%T%\" ( echo  STOPPED: could not create %T%. Tell Claude. & pause & exit /b 1 )
if exist "%R%\.git" goto linked
echo  Getting StruKit from GitHub ^(a sign-in window may open the first time^) ...
git clone --branch release --single-branch https://github.com/ThatcherEngineering/StruKit "%R%"
if errorlevel 1 ( echo. & echo  STOPPED: could not get StruKit from GitHub. Nothing was changed. Tell Claude what the lines above say. & pause & exit /b 1 )
:linked
>"C:\ZET-G\StruKit-target.txt" echo %T%
echo  Setting up the automatic update ...
schtasks /Create /TN "StruKit update from GitHub" /TR "C:\Windows\System32\conhost.exe --headless cmd.exe /c C:\ZET-G\StruKit\StruKit-Get-Latest.bat quiet" /SC HOURLY /MO 2 /F >nul
if errorlevel 1 ( echo  The automatic update could not be set up. StruKit-Get-Latest.bat still works by hand. Tell Claude. )
echo.
call "%R%\StruKit-Get-Latest.bat" quiet
if not exist "%T%\strukit.bat" ( echo  STOPPED: the StruKit files did not arrive in %T%. Tell Claude and send C:\ZET-G\StruKit-update.log. & pause & exit /b 1 )
echo.
call "%T%\strukit.bat" --setup-only
if errorlevel 1 ( echo  STOPPED: StruKit's setup did not finish. Tell Claude what the lines above say. & pause & exit /b 1 )
call "%T%\Make-Desktop-Shortcut.bat" quiet
echo.
echo  StruKit is installed. Opening it now ...
call "%T%\strukit.bat"
echo.
echo  Done. This window can be closed. From now on use the StruKit icon on the Desktop.
pause
exit /b 0
