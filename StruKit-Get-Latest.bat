@echo off
rem StruKit-Get-Latest - brings the StruKit on this computer up to the latest build on GitHub.
rem Double-click it for an update now. The scheduled task runs it as "StruKit-Get-Latest.bat quiet" (no pauses).
rem How it works: C:\ZET-G\StruKit is a download copy of the ready-to-run build (GitHub ThatcherEngineering/StruKit,
rem branch "release"). When that copy is newer than what is installed, its files are copied into the StruKit folder
rem (the one named in C:\ZET-G\StruKit-target.txt), VERSION.txt last. Job folders, project files and the Python
rem runtime are not touched. It runs from a temporary copy so it can safely replace itself.
if /i not "%~1"=="--run" ( copy /y "%~f0" "%TEMP%\StruKit-Get-Latest-run-%~1.bat" >nul & call "%TEMP%\StruKit-Get-Latest-run-%~1.bat" --run %1 & exit /b )
setlocal
set "Q="
if /i "%~2"=="quiet" set "Q=1"
if defined Q ( set "GCM_INTERACTIVE=never" & set "GIT_TERMINAL_PROMPT=0" )
title StruKit - get latest build
set "G=C:\Program Files\Git\cmd\git.exe"
set "PATH=C:\Program Files\Git\cmd;%PATH%"
set "R=C:\ZET-G\StruKit"
set "L=C:\ZET-G\StruKit-update.log"
set "H=C:\ZET-G\StruKit-update-history.log"
set "MODE=manual"
if defined Q set "MODE=auto"
if not exist "%G%" ( echo Git is not installed on this computer. & if not defined Q pause & exit /b 1 )
if not exist "%R%\.git" ( echo StruKit is not linked to GitHub on this computer yet - run Install-StruKit.bat first. & if not defined Q pause & exit /b 1 )
set "T="
if exist "C:\ZET-G\StruKit-target.txt" set /p T=<"C:\ZET-G\StruKit-target.txt"
if not defined T ( echo C:\ZET-G\StruKit-target.txt is missing - run Install-StruKit.bat again. & if not defined Q pause & exit /b 1 )
if not exist "%T%\" ( echo The StruKit folder "%T%" was not found - run Install-StruKit.bat again from the StruKit folder. & echo %DATE% %TIME% %MODE% NO-TARGET >> "%H%" & if not defined Q pause & exit /b 1 )
cd /d "%R%"
echo StruKit-Get-Latest %MODE% %DATE% %TIME% > "%L%"

echo Checking GitHub for a newer StruKit ...
git fetch origin release >> "%L%" 2>&1
if errorlevel 1 (
  echo Could not reach GitHub - check the internet connection.
  echo %DATE% %TIME% %MODE% NO-CONNECTION >> "%H%"
  if not defined Q pause
  exit /b 1
)
rem the download copy is never edited by hand: it is simply set to what GitHub has
git reset -q --hard origin/release >> "%L%" 2>&1
if errorlevel 1 (
  echo Update FAILED - nothing was changed. Tell Claude and send C:\ZET-G\StruKit-update.log.
  echo %DATE% %TIME% %MODE% FAILED-RESET >> "%H%"
  if not defined Q pause
  exit /b 1
)
set "NEW="
for /f %%i in ('git rev-parse --short HEAD') do set "NEW=%%i"
set "INS=none"
if exist "%T%\app\INSTALLED-COMMIT.txt" set /p INS=<"%T%\app\INSTALLED-COMMIT.txt"

echo.
if "%INS%"=="%NEW%" (
  echo Already up to date.
  echo %DATE% %TIME% %MODE% %NEW% UP-TO-DATE >> "%H%"
  goto show
)

echo Installing the new build into "%T%" ...
robocopy "%R%" "%T%" /E /XD .git /XF VERSION.txt INSTALLED-COMMIT.txt /R:2 /W:2 /NFL /NDL /NJH /NJS /NP >> "%L%" 2>&1
if errorlevel 8 goto copyfail
rem the program folder is made to match exactly, so a file removed from StruKit goes from this computer too
robocopy "%R%\app\strukit" "%T%\app\strukit" /MIR /XD __pycache__ /R:2 /W:2 /NFL /NDL /NJH /NJS /NP >> "%L%" 2>&1
if errorlevel 8 goto copyfail
rem VERSION.txt last: it says a build is installed only once every file of it is in place
copy /y "%R%\app\VERSION.txt" "%T%\app\VERSION.txt" >nul
if errorlevel 1 goto copyfail
>"%T%\app\INSTALLED-COMMIT.txt" echo %NEW%
echo UPDATED.
echo %DATE% %TIME% %MODE% %INS% -^> %NEW% UPDATED >> "%H%"
goto show

:copyfail
echo Update FAILED while copying files. StruKit may be part old, part new: run this again.
echo Tell Claude and send C:\ZET-G\StruKit-update.log.
echo %DATE% %TIME% %MODE% %INS% FAILED-COPY ^(installing %NEW%^) >> "%H%"
if not defined Q pause
exit /b 1

:show
echo.
echo StruKit now on this computer:
if exist "%T%\app\VERSION.txt" type "%T%\app\VERSION.txt"
echo.
if not defined Q pause
exit /b 0
