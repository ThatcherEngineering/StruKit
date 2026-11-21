@echo off
rem  Puts a "StruKit" shortcut (Thatcher Engineering icon) on your Desktop.
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'StruKit.lnk')); $s.TargetPath=(Join-Path $env:WINDIR 'System32\wscript.exe'); $s.Arguments='\"%~dp0app\launch.vbs\"'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0app\strukit.ico'; $s.Description='StruKit - structural calculations'; $s.Save()" && echo The StruKit icon is on your Desktop. Double-click it to use StruKit.
if /i not "%~1"=="quiet" pause
