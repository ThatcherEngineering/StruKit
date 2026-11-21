@echo off
rem  StruKit - double-click to open the StruKit window.
rem  The drawing tools call it as  strukit.bat preflight ... / run ... / --version  (no window, no pause).
rem  strukit.bat --serve   server only (no window), address printed;  --open <file.strukit>;  --port N
setlocal EnableExtensions DisableDelayedExpansion
title StruKit
set "SK=%~dp0"
set "CMD="
for %%c in (preflight run version --version -h --help) do if /i "%~1"=="%%c" set "CMD=1"
if not exist "%SK%runtime\python.exe" goto setup
fc /b "%SK%app\downloads.txt" "%SK%runtime\installed.txt" >nul 2>nul || goto setup
goto run
:setup
if defined CMD (
    rem  a quiet command from the drawing tools: never set up (or pause) in a window nobody can see
    echo FAILED StruKit is not set up on this computer yet: double-click strukit.bat in the StruKit folder once, let it finish, then run this again.
    exit /b 3
)
call "%SK%app\setup.bat" || goto fail
:run
if "%~1"=="" (
    start "" "%SK%runtime\pythonw.exe" -m strukit.gui
    exit /b
)
if /i "%~1"=="--setup-only" exit /b 0
if /i "%~1"=="--serve" (
    "%SK%runtime\python.exe" -X utf8 -m strukit.gui %*
    exit /b %errorlevel%
)
if /i "%~1"=="--open" goto gui
if /i "%~1"=="--port" goto gui
"%SK%runtime\python.exe" -X utf8 -m strukit %*
exit /b %errorlevel%
:gui
start "" "%SK%runtime\pythonw.exe" -m strukit.gui %*
exit /b
:fail
echo.
echo  StruKit could not set itself up - see the message above.
echo.
pause
exit /b 1
