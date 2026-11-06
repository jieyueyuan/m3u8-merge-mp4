[🇨🇳 中文](README.md) · [🇺🇸 English](README.en.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md)

# m3u8-merge-mp4 🎬

A small Windows tool that batch-merges `.m3u8` (HLS playlists + segments) into `.mp4`.
No Python packages to install — the only external dependency is [ffmpeg](https://ffmpeg.org/).

**Strategy: lossless remux first (stream copy — instant, zero quality loss), automatic libx264+aac re-encode fallback.**

## Four ways to use it — pick any

### 1. Drag & drop bat (easiest)

Drag m3u8 **files or whole folders** onto `拖我一把-把m3u8拖进来.bat`.

- Dropping a folder scans it recursively for `.m3u8`
- mp4 is written next to each source
- Keep this bat next to `m3u8_to_mp4.py`

### 2. Double-click bat (single self-contained file)

Copy `双击合成-当前文件夹.bat` **into** the folder containing your m3u8 files, then double-click it.

- Pure bat + ffmpeg, no other files required — carry just this one around
- Processes every `.m3u8` in its own folder; existing mp4s are skipped
- A broken file doesn't stop the batch; ends with a `N ok / N failed` summary

### 3. GUI app

Double-click `m3u8合成器GUI.py` (needs Python 3.8+; tkinter is bundled):

- Buttons to add files/folders, progress bar, log, stop button
- Optional output dir, overwrite policy, remux-only / re-encode / auto modes
- No console window — friendliest for non-command-line users

## Command line (most features)

```bash
# several files
python m3u8_to_mp4.py a.m3u8 b.m3u8

# scan a directory (-r recursive), custom output dir
python m3u8_to_mp4.py -i "D:\videos" -o "D:\out" -r

# 4 in parallel / remux only / force re-encode
python m3u8_to_mp4.py -i "D:\videos" --copy --jobs 4
python m3u8_to_mp4.py -i "D:\videos" --reencode --crf 20 --preset fast

# network m3u8 (auto reconnect)
python m3u8_to_mp4.py --url "https://example.com/index.m3u8"
```

Key options:

| Flag | Meaning |
|---|---|
| `--copy` / `--reencode` / `--auto` | remux only (fail fast) / force re-encode / default: copy then fallback |
| `--crf 23` `--preset medium` | re-encode quality / speed |
| `--jobs 4` | parallel merges |
| `-o DIR` | unified output directory |
| `--ffmpeg PATH` | explicit ffmpeg.exe |
| `--timeout SEC` | per-task timeout (default 7200) |
| `--lang zh\|en\|ja\|ko` | force message language |

## Message language (中文 / English / 日本語 / 한국어)

All runtime messages **follow your system UI language automatically**. To force one:

```bash
set M3U8_LANG=en        # CMD (works for CLI / GUI / drag-drop bat)
$env:M3U8_LANG="ja"     # PowerShell
export M3U8_LANG=ko     # bash
# or: python m3u8_to_mp4.py ... --lang en
```

The double-click bat reads its texts from `lang_zh.txt` / `lang_en.txt` / `lang_ja.txt` / `lang_ko.txt` next to it (plain KEY=VALUE, freely editable). With no lang files it falls back to built-in English, so a lone copied bat still works.

## Requirements

- **ffmpeg** (required): `winget install Gyan.FFmpeg`, or grab a full build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add it to PATH. Scripts also probe common install locations.
- **Python 3.8+** (only for ways 1/3/CLI; way 2, the pure bat, needs neither). The Windows installer bundles tkinter.

## How it works & caveats

- Standard HLS (H.264/AAC .ts) is remuxed with `-c copy` plus `-bsf:a aac_adtstoasc` to fix the audio stream header — **without that bitstream filter the mp4 has no sound**, the classic reason manual conversions "fail".
- Local playlists are pre-checked for missing segments; missing ones abort with a clear error — **no half-baked videos are produced**.
- Output uses `-movflags +faststart` (good for streaming/preview).
- Copy failures (mismatched segment encodings, broken timestamps…) fall back to re-encode in auto mode.
- Want episodes in one file? Remux each to mp4 first, then `ffmpeg concat` them — trivial since outputs are uniform mp4.
- Handles local files and http(s) m3u8. Encrypted streams (EXT-X-KEY) need the key first and are out of scope.

## Files

```
拖我一把-把m3u8拖进来.bat             way 1: drag & drop entry
双击合成-当前文件夹.bat               way 2: drop-into-folder + double-click
m3u8_to_mp4.py                        CLI engine / backend of way 1
m3u8合成器GUI.py                       way 3: tkinter GUI
lang_zh.txt lang_en.txt lang_ja.txt lang_ko.txt   way-2 texts (4 languages)
README.md README.en.md README.ja.md README.ko.md  docs in 4 languages
```

File names are kept in Chinese intentionally (they are the shipped tool names); behavior and messages are fully localized.

## FAQ

**Q: "ffmpeg not found"?**
A: After installing, **reopen** the terminal/app (PATH changes don't reach running processes), or pass `--ffmpeg`, or drop ffmpeg.exe + ffprobe.exe next to the scripts.

**Q: bat window flashes and closes?**
A: Normal paths end with `pause`. If it crashes early, type `cmd` in the Explorer address bar and run the bat from there to see the error.

**Q: mp4 has no audio / artifacts?**
A: Source segments are unusual; run again forcing re-encode: `python m3u8_to_mp4.py FILE --reencode`.

**Q: Dropped a folder, nothing happened?**
A: Folder drops are handled by the drag-drop bat (recursive). The double-click bat only scans its own folder.

## License

MIT — use it, modify it, keep a credit if you like.
