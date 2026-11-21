@echo off
rem ---------------------------------------------------------------------------
rem  StruKit first-time setup. Run automatically by strukit.bat - nothing to do by hand.
rem
rem  Downloads the official Windows Python runtime (python.org) and the math and PDF
rem  libraries StruKit uses (pypi.org), checks every file against the
rem  size or SHA-256 listed in downloads.txt, and unpacks them into ..\runtime.
rem  Nothing is installed on Windows: delete the runtime folder and it is gone.
rem
rem  No internet on this PC? Put the files named in downloads.txt into
rem  app\downloads\ yourself and run StruKit again - it uses them instead.
rem ---------------------------------------------------------------------------
setlocal EnableExtensions DisableDelayedExpansion
set "APP=%~dp0"
for %%I in ("%~dp0..") do set "ROOT=%%~fI\"
set "RT=%ROOT%runtime"
set "DL=%APP%downloads"

echo.
echo  StruKit is setting itself up (first run only, about 35 MB to download)...
echo.

where curl.exe >nul 2>nul || (echo  STOPPED: this Windows has no curl.exe - Windows 10 ^(1803^) or newer is needed. & exit /b 1)
where tar.exe  >nul 2>nul || (echo  STOPPED: this Windows has no tar.exe - Windows 10 ^(1803^) or newer is needed. & exit /b 1)

if exist "%RT%" rmdir /s /q "%RT%"
mkdir "%RT%\lib" || (echo  STOPPED: can't create %RT% - is the folder read-only? & exit /b 1)
if not exist "%DL%" mkdir "%DL%"

for /f "usebackq eol=# tokens=1-3" %%a in ("%APP%downloads.txt") do (
    call :fetch "%%a" "%%b" "%%c" || exit /b 1
)

rem --- Python runtime --------------------------------------------------------
for %%z in ("%DL%\python-*-embed*-amd64.zip") do (
    echo  unpacking %%~nxz
    tar -xf "%%z" -C "%RT%" || (echo  STOPPED: could not unpack %%~nxz & exit /b 1)
)
if not exist "%RT%\python.exe" (echo  STOPPED: python.exe is missing after unpacking the runtime. & exit /b 1)

rem --- libraries (a .whl is a zip) -------------------------------------------
for %%w in ("%DL%\*.whl") do (
    echo  unpacking %%~nxw
    tar -xf "%%w" -C "%RT%\lib" || (echo  STOPPED: could not unpack %%~nxw & exit /b 1)
)

rem --- tell Python where to look: its own zip, lib\, and the StruKit code in app\ -----
for %%p in ("%RT%\python3*._pth") do (
    > "%%p" (
        echo python312.zip
        echo .
        echo lib
        echo ..\app
    )
)

rem --- prove it works --------------------------------------------------------
"%RT%\python.exe" -c "import numpy, reportlab, PIL, strukit.gui.calc, strukit.calcsheet; print('  check: Python', __import__('sys').version.split()[0], '- numpy', numpy.__version__, '- reportlab', reportlab.__version__, '- StruKit', strukit.__version__)" || (
    echo  STOPPED: the runtime was unpacked but StruKit would not start.
    exit /b 1
)
copy /y "%APP%downloads.txt" "%RT%\installed.txt" >nul
echo.
echo  Setup finished. (The downloaded files in app\downloads can be deleted.)
echo.
exit /b 0


rem ---------------------------------------------------------------------------
:fetch  file  check  url
set "F=%DL%\%~1"
set "CHECK=%~2"
if exist "%F%" call :verify "%F%" "%CHECK%" && (echo  have      %~1 & exit /b 0)
echo  download  %~1
curl.exe -L -f -s -S --retry 2 -o "%F%" "%~3"
if errorlevel 1 (
    echo.
    echo  STOPPED: could not download %~1
    echo           from %~3
    echo  If this PC's internet is filtered, download that file in a browser, put it in
    echo  %DL%
    echo  and run StruKit again.
    if exist "%F%" del "%F%"
    exit /b 1
)
call :verify "%F%" "%CHECK%" && exit /b 0
echo  STOPPED: %~1 did not match its published checksum - not using it.
del "%F%"
exit /b 1

:verify  path  check   (check = 64-hex SHA-256, or size:NNN bytes)
set "V=%~2"
if /i "%V:~0,5%"=="size:" (
    if "%~z1"=="%V:~5%" exit /b 0
    exit /b 1
)
set "H="
for /f "skip=1 delims=" %%h in ('certutil -hashfile "%~1" SHA256') do if not defined H set "H=%%h"
set "H=%H: =%"
if /i "%H%"=="%V%" exit /b 0
exit /b 1
