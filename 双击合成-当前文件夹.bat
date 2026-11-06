@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
rem ============================================================
rem  Self-contained: merge every .m3u8 IN THIS FOLDER to .mp4.
rem  Usage: copy this bat into the folder with your m3u8 files,
rem         then double-click. No other files needed.
rem  Needs: ffmpeg in PATH only.
rem  Method: stream copy first (fast, lossless); if that fails,
rem          auto re-encode with libx264+aac.
rem ============================================================

set "FF="
for /f "delims=" %%R in ('where ffmpeg 2^>nul') do if not defined FF set "FF=%%R"
if not defined FF (
    echo [ERROR] ffmpeg not found in PATH.
    echo         Install: winget install Gyan.FFmpeg
    pause
    exit /b 1
)

set /a N=0, OK=0, FAIL=0
pushd "%~dp0"

for %%F in (*.m3u8) do (
    set /a N+=1
    set "BASE=%%~nF"
    echo [!N!] %%F
    if exist "!BASE!.mp4" (
        echo     skip: !BASE!.mp4 already exists
        echo     ^(delete it first if you want to redo^)
    ) else (
        "%FF%" -y -hide_banner -loglevel error -i "%%F" -c copy -bsf:a aac_adtstoasc -movflags +faststart "!BASE!.mp4"
        if !ERRORLEVEL! neq 0 (
            echo     copy failed, re-encoding...
            "%FF%" -y -hide_banner -loglevel error -i "%%F" -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 192k -movflags +faststart "!BASE!.mp4"
            if !ERRORLEVEL! neq 0 (
                if exist "!BASE!.mp4" del "!BASE!.mp4"
                echo     FAIL: %%F
                set /a FAIL+=1
            ) else (
                echo     OK: !BASE!.mp4 ^(re-encoded^)
                set /a OK+=1
            )
        ) else (
            echo     OK: !BASE!.mp4 ^(lossless copy^)
            set /a OK+=1
        )
    )
)

popd
echo.
if %N%==0 (
    echo No .m3u8 found in this folder. ^(Make sure this bat sits next to your m3u8 files^)
) else (
    echo Done: %OK% ok / %FAIL% failed / %N% found. Output mp4 is in this folder.
)
pause
