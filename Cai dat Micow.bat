@echo off
chcp 65001 >nul
rem Cai dat Micow: tao moi truong Python o %USERPROFILE%\.micow\venv va bieu tuong Desktop
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1" %*
pause
