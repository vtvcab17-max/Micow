@echo off
chcp 65001 >nul
set "MH=%MICOW_HOME%"
if "%MH%"=="" set "MH=%USERPROFILE%\.micow"
set "PYW=%MH%\venv\Scripts\python.exe"
if not exist "%PYW%" (
  echo Chua cai Micow. Bam dup "Cai dat Micow.bat" truoc.
  pause
  exit /b 1
)
title Micow - dong cua so nay de tat
"%PYW%" -m micow serve --open
