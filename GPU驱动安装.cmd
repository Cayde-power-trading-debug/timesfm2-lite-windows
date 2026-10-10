@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" -Task Driver
if errorlevel 1 echo 操作失败，请查看上方错误。
pause
