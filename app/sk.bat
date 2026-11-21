@echo off
rem  Command-line StruKit:  sk.bat --version   /   sk.bat preflight ...   /   sk.bat run ...
setlocal
set "SK=%~dp0..\"
if not exist "%SK%runtime\python.exe" (echo Run strukit.bat once first, to set it up. & exit /b 1)
"%SK%runtime\python.exe" -X utf8 -m strukit %*
