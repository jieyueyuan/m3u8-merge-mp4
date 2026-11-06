@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
rem ============================================================
rem  Drag m3u8 files or folders onto this .bat icon.
rem  They are merged to .mp4 (stream copy first, auto fallback).
rem  Or double-click and paste a path when prompted.
rem ============================================================

set "SCRIPT=%~dp0m3u8_to_mp4.py"

if not exist "%SCRIPT%" (
    echo [ERROR] m3u8_to_mp4.py not found next to this bat.
    pause
    exit /b 1
)

rem ---- pick the first Python that actually runs ----
set "PYCMD="
for %%C in (python python3 "%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe") do (
    if not defined PYCMD (
        for /f "delims=" %%R in ('%%C -c "print(1)" 2^>nul') do (
            if "%%R"=="1" set "PYCMD=%%C"
        )
    )
)
if not defined PYCMD (
    echo [ERROR] Python not found. Install: winget install Python.Python.3.12
    pause
    exit /b 1
)

set "ARGS="
:loop
if "%~1"=="" goto run
set "ARGS=!ARGS! "%~1""
shift
goto :loop

:run
if not defined ARGS (
    set /p "ONE=Paste m3u8 file or folder path ^(or drag files onto this icon^): "
    if not defined ONE ( echo Nothing entered. & pause & exit /b 1 )
    set "ARGS="!ONE!""
)

echo.
echo ============ START ============
%PYCMD% "%SCRIPT%" !ARGS!
echo ============ DONE (exit !ERRORLEVEL!) ============
pause
endlocal
