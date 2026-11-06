@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
rem ============================================================
rem  Self-contained: merge every .m3u8 IN THIS FOLDER to .mp4.
rem  Copy this bat into the folder with your m3u8 files and
rem  double-click. Needs ffmpeg in PATH only.
rem
rem  Languages (zh/en/ja/ko): optionally place lang_zh.txt /
rem  lang_en.txt / lang_ja.txt / lang_ko.txt NEXT TO THIS BAT.
rem  Selection: env M3U8_LANG > system UI language > en.
rem  With no lang files present it still works (built-in English).
rem ============================================================

rem ---------- detect system UI language (first entry of user profile languages) ----------
set "SYSLANG=en"
for /f "tokens=3" %%V in ('reg query "HKCU\Control Panel\International\User Profile" /v Languages 2^>nul ^| find "Languages"') do set "LOCLINE=%%V"
if defined LOCLINE (
    for /f "delims=,-" %%P in ("!LOCLINE!") do set "PRE=%%P"
    if /i "!PRE!"=="zh" set "SYSLANG=zh"
    if /i "!PRE!"=="ja" set "SYSLANG=ja"
    if /i "!PRE!"=="ko" set "SYSLANG=ko"
    if /i "!PRE!"=="en" set "SYSLANG=en"
)
set "LANG=%SYSLANG%"
if defined M3U8_LANG set "LANG=%M3U8_LANG:~0,2%"

rem ---------- load lang file if present ----------
if exist "%~dp0lang_%LANG%.txt" (
    for /f "usebackq eol=# tokens=1* delims==" %%K in ("%~dp0lang_%LANG%.txt") do set "L_%%~K=%%L"
)

rem ---------- built-in English fallback for anything missing ----------
if not defined L_TITLE    set "L_TITLE=m3u8 to mp4 (this folder)"
if not defined L_NOFF      set "L_NOFF=[ERROR] ffmpeg not found in PATH. Install: winget install Gyan.FFmpeg"
if not defined L_EXIST     set "L_EXIST=skip: mp4 already exists (delete it to redo)"
if not defined L_FALLBACK  set "L_FALLBACK=copy failed, re-encoding..."
if not defined L_COPYOK    set "L_COPYOK=OK: mp4 (lossless copy)"
if not defined L_ENCOK     set "L_ENCOK=OK: mp4 (re-encoded)"
if not defined L_ENCFAIL   set "L_ENCFAIL=FAIL:"
if not defined L_NONE      set "L_NONE=No .m3u8 found in this folder. Put this bat next to your m3u8 files."
if not defined L_DONE      set "L_DONE=Done:"
if not defined L_OK        set "L_OK=ok"
if not defined L_FAILED    set "L_FAILED=failed"
if not defined L_NFOUND    set "L_NFOUND=found"
if not defined L_LOC       set "L_LOC=Output mp4 is in this folder."

echo === !L_TITLE! ===

set "FF="
for /f "delims=" %%R in ('where ffmpeg 2^>nul') do if not defined FF set "FF=%%R"
if not defined FF (
    echo !L_NOFF!
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
        echo     !L_EXIST!
    ) else (
        "%FF%" -y -hide_banner -loglevel error -i "%%F" -c copy -bsf:a aac_adtstoasc -movflags +faststart "!BASE!.mp4"
        if !ERRORLEVEL! neq 0 (
            echo     !L_FALLBACK!
            "%FF%" -y -hide_banner -loglevel error -i "%%F" -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 192k -movflags +faststart "!BASE!.mp4"
            if !ERRORLEVEL! neq 0 (
                if exist "!BASE!.mp4" del "!BASE!.mp4"
                echo     !L_ENCFAIL! %%F
                set /a FAIL+=1
            ) else (
                echo     !L_ENCOK!
                set /a OK+=1
            )
        ) else (
            echo     !L_COPYOK!
            set /a OK+=1
        )
    )
)

popd
echo.
if %N%==0 (
    echo !L_NONE!
) else (
    echo !L_DONE! %OK% !L_OK! / %FAIL% !L_FAILED! / %N% !L_NFOUND!. !L_LOC!
)
pause
