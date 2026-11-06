#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m3u8_to_mp4.py — batch merge m3u8 (HLS) playlists into mp4 files.

语言 / Languages: zh / en / ja / ko
  自动检测系统界面语言；可用 --lang zh|en|ja|ko 或环境变量 M3U8_LANG 覆盖。
  Auto-detects UI language; override with --lang or M3U8_LANG env var.

用法 / Usage:
  python m3u8_to_mp4.py "D:\\videos\\a.m3u8" "D:\\videos\\b.m3u8"
  python m3u8_to_mp4.py -i "D:\\videos" -r
  python m3u8_to_mp4.py -i "D:\\videos" --copy --jobs 4
  python m3u8_to_mp4.py --url "https://example.com/index.m3u8"

依赖：ffmpeg（PATH 或 --ffmpeg 指定）。优先无损 stream copy，失败自动重编码。
Requires ffmpeg. Tries lossless stream copy first, falls back to re-encode.
"""

import argparse
import concurrent.futures
import ctypes
import locale
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Windows 控制台默认 GBK/CP936 等，防止打印多语言字符时崩溃
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ======================================================================
# i18n  (zh / en / ja / ko)
# ======================================================================
STRINGS = {
    "zh": {
        "ffmpeg_err": "[错误] 未找到 ffmpeg。请安装后加入 PATH，或用 --ffmpeg 指定 ffmpeg.exe 路径。\n  安装参考: winget install Gyan.FFmpeg  或 https://www.gyan.dev/ffmpeg/builds/",
        "ffmpeg_missing": "[错误] 找不到指定的 ffmpeg: {p}",
        "no_input": "[错误] 没有输入。给文件路径，或用 -i 目录，或 --url 网络地址。",
        "dir_missing": "[错误] 目录不存在: {d}",
        "header": "共 {n} 个待合成任务 | ffmpeg: {ff} | 模式: {mode}",
        "copy_ok": "stream copy（无损、未重编码）",
        "reenc_ok": "re-encode（libx264+aac）",
        "auto_note": "    [auto] copy 失败({m})，降级为重新编码 ...",
        "miss_seg": "清单引用的分段文件缺失 {k} 个，例如: {s}",
        "timeout": "超时（>{t}s）",
        "copy_fail": "copy 失败: {m}",
        "reenc_fail": "重编码失败: {m}",
        "done": "\n完成：成功 {ok} / {n}",
        "fail_list": "失败清单：",
    },
    "en": {
        "ffmpeg_err": "[error] ffmpeg not found. Install it and add to PATH, or point --ffmpeg to ffmpeg.exe.\n  Install: winget install Gyan.FFmpeg  or https://www.gyan.dev/ffmpeg/builds/",
        "ffmpeg_missing": "[error] specified ffmpeg not found: {p}",
        "no_input": "[error] no input. Give file paths, or -i DIR, or --url.",
        "dir_missing": "[error] directory not found: {d}",
        "header": "{n} task(s) to merge | ffmpeg: {ff} | mode: {mode}",
        "copy_ok": "stream copy (lossless, no re-encode)",
        "reenc_ok": "re-encode (libx264+aac)",
        "auto_note": "    [auto] copy failed ({m}), falling back to re-encode ...",
        "miss_seg": "playlist references {k} missing segment file(s), e.g.: {s}",
        "timeout": "timed out (>{t}s)",
        "copy_fail": "copy failed: {m}",
        "reenc_fail": "re-encode failed: {m}",
        "done": "\nDone: {ok}/{n} succeeded",
        "fail_list": "Failures:",
    },
    "ja": {
        "ffmpeg_err": "[エラー] ffmpeg が見つかりません。インストールして PATH に追加するか、--ffmpeg で ffmpeg.exe を指定してください。\n  インストール: winget install Gyan.FFmpeg  または https://www.gyan.dev/ffmpeg/builds/",
        "ffmpeg_missing": "[エラー] 指定された ffmpeg が見つかりません: {p}",
        "no_input": "[エラー] 入力がありません。ファイルを指定するか、-i でディレクトリ、--url でネットワークアドレスを指定してください。",
        "dir_missing": "[エラー] ディレクトリが見つかりません: {d}",
        "header": "変換タスク {n} 件 | ffmpeg: {ff} | モード: {mode}",
        "copy_ok": "stream copy（可逆カプセリング、再エンコードなし）",
        "reenc_ok": "再エンコード完了（libx264+aac）",
        "auto_note": "    [auto] copy 失敗({m})、再エンコードに切り替えます ...",
        "miss_seg": "プレイリストが参照するセグメントファイルが {k} 個見つかりません（例: {s}）",
        "timeout": "タイムアウト（>{t}秒）",
        "copy_fail": "copy 失敗: {m}",
        "reenc_fail": "再エンコード失敗: {m}",
        "done": "\n完了：成功 {ok} / {n}",
        "fail_list": "失敗一覧：",
    },
    "ko": {
        "ffmpeg_err": "[오류] ffmpeg을 찾을 수 없습니다. 설치 후 PATH에 추가하거나 --ffmpeg로 ffmpeg.exe 경로를 지정하세요.\n  설치: winget install Gyan.FFmpeg  또는 https://www.gyan.dev/ffmpeg/builds/",
        "ffmpeg_missing": "[오류] 지정된 ffmpeg을 찾을 수 없습니다: {p}",
        "no_input": "[오류] 입력이 없습니다. 파일 경로, -i 디렉토리, 또는 --url을 사용하세요.",
        "dir_missing": "[오류] 디렉토리를 찾을 수 없습니다: {d}",
        "header": "병합 작업 {n}개 | ffmpeg: {ff} | 모드: {mode}",
        "copy_ok": "stream copy(무손실, 재인코딩 없음)",
        "reenc_ok": "재인코딩 완료(libx264+aac)",
        "auto_note": "    [auto] copy 실패({m}), 재인코딩으로 전환합니다 ...",
        "miss_seg": "플레이리스트가 참조하는 세그먼트 파일 {k}개 없음, 예: {s}",
        "timeout": "시간 초과(>{t}초)",
        "copy_fail": "copy 실패: {m}",
        "reenc_fail": "재인코딩 실패: {m}",
        "done": "\n완료: 성공 {ok} / {n}",
        "fail_list": "실패 목록:",
    },
}

# Windows PRIMARY_LANGID -> 语言（检测“系统界面语言”，而非区域格式）
UI_LANGUAGES = {0x04: "zh", 0x09: "en", 0x11: "ja", 0x12: "ko"}


def detect_lang():
    """显式覆盖 > 系统 UI 语言 > locale 前缀 > en"""
    o = (os.environ.get("M3U8_LANG") or "").strip().lower()[:2]
    if o in STRINGS:
        return o
    if os.name == "nt":
        try:
            primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
            if primary in UI_LANGUAGES:
                return UI_LANGUAGES[primary]
        except Exception:
            pass
    try:
        p = (locale.getlocale()[0] or "").lower().replace("_", "-").split("-")[0]
        if p in STRINGS:
            return p
    except Exception:
        pass
    return "en"


LANG = detect_lang()


def t(key, **kw):
    s = STRINGS[LANG].get(key, STRINGS["en"].get(key, key))
    return s.format(**kw) if kw else s


# ======================================================================
# 核心逻辑（与语言无关）
# ======================================================================
def find_ffmpeg(explicit):
    if explicit:
        p = Path(explicit)
        if p.exists():
            return str(p)
        sys.exit(t("ffmpeg_missing", p=explicit))
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    if os.name == "nt":
        for g in (r"C:\ffmpeg\bin\ffmpeg.exe", r"D:\ffmpeg\bin\ffmpeg.exe",
                  os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe"),
                  os.path.expandvars(r"%ProgramFiles%\ffmpeg\bin\ffmpeg.exe")):
            if g and Path(g).exists():
                return g
    sys.exit(t("ffmpeg_err"))


def is_network(src):
    return bool(re.match(r"^https?://", str(src), re.I))


def run(cmd, timeout=None):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def check_segments_local(m3u8):
    missing = []
    try:
        text = m3u8.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return missing
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"^(https?://|file:///|data:)", line, re.I):
            continue
        if not (m3u8.parent / line).exists():
            missing.append(line)
    return missing


def build_output_name(src, outdir):
    if is_network(src):
        name = Path(str(src).split("?")[0].rstrip("/")).name
        if not name.lower().endswith(".m3u8"):
            name = "download_%05d.m3u8" % (abs(hash(src)) % 100000)
    else:
        name = Path(src).name
    stem = Path(name).stem
    if outdir:
        return outdir / (stem + ".mp4")
    if is_network(src):
        return Path.cwd() / (stem + ".mp4")
    return Path(src).parent / (stem + ".mp4")


def encode_cmd(ffmpeg, src, dst, mode, crf, preset, extra):
    input_opts = []
    if is_network(src):
        input_opts = ["-reconnect", "1", "-reconnect_streamed", "1",
                      "-reconnect_delay_max", "10"]
    if mode == "copy":
        codec_opts = ["-c", "copy", "-bsf:a", "aac_adtstoasc"]
    else:
        codec_opts = ["-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                      "-c:a", "aac", "-b:a", "192k"]
    return [ffmpeg] + input_opts + ["-i", str(src)] + codec_opts + extra + \
        ["-movflags", "+faststart", "-y", "-hide_banner", "-loglevel", "error", str(dst)]


def convert_one(ffmpeg, src, dst, args):
    if not is_network(src):
        missing = check_segments_local(Path(src))
        if missing:
            return False, t("miss_seg", k=len(missing), s=missing[0]), dst

    tmp = dst.with_name(dst.stem + ".partial.mp4")
    mode = args.mode

    def _run(cmd):
        try:
            r = run(cmd, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            return False, t("timeout", t=args.timeout)
        except Exception as e:
            return False, str(e)
        if r.returncode == 0 and Path(tmp).exists() and Path(tmp).stat().st_size > 0:
            return True, ""
        tail = (r.stderr or "").strip().splitlines()[-3:]
        return False, " | ".join(tail) if tail else "ffmpeg exit %d" % r.returncode

    if mode in ("copy", "auto"):
        ok, msg = _run(encode_cmd(ffmpeg, src, tmp, "copy", args.crf, args.preset, args.ffparam))
        if ok:
            os.replace(tmp, dst)
            return True, t("copy_ok"), dst
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        if mode == "copy":
            return False, t("copy_fail", m=msg), dst
        print(t("auto_note", m=msg[:80]))

    ok, msg = _run(encode_cmd(ffmpeg, src, tmp, "reencode", args.crf, args.preset, args.ffparam))
    if ok:
        os.replace(tmp, dst)
        return True, t("reenc_ok"), dst
    try:
        tmp.unlink(missing_ok=True)
    except OSError:
        pass
    return False, t("reenc_fail", m=msg), dst


def collect_inputs(args):
    sources = []
    if args.input_dir:
        d = Path(args.input_dir)
        if not d.is_dir():
            sys.exit(t("dir_missing", d=d))
        pattern = "**/*.m3u8" if args.recursive else "*.m3u8"
        sources += [str(p) for p in sorted(d.glob(pattern))]
    for f in (args.files or []):
        p = Path(f)
        if p.is_dir():
            sources += [str(x) for x in sorted(p.rglob("*.m3u8"))]
        else:
            sources.append(f)
    if not sources:
        sys.exit(t("no_input"))
    seen, uniq = set(), []
    for s in sources:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def main():
    global LANG
    ap = argparse.ArgumentParser(
        description="Batch merge m3u8 (HLS) into mp4. Languages: zh/en/ja/ko (auto-detect, "
                    "--lang to force; env M3U8_LANG also works).")
    ap.add_argument("files", nargs="*", help="one or more .m3u8 files or folders")
    ap.add_argument("-i", "--input-dir", help="scan a directory for *.m3u8")
    ap.add_argument("-o", "--output-dir", help="output directory (default: beside each source)")
    ap.add_argument("-r", "--recursive", action="store_true", help="with -i, scan subdirectories")
    ap.add_argument("--url", action="append", default=[], help="network m3u8 URL (repeatable)")
    ap.add_argument("--ffmpeg", help="path to ffmpeg executable")
    ap.add_argument("--lang", choices=sorted(STRINGS), help="message language (default: auto-detect)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--copy", dest="mode", action="store_const", const="copy",
                      help="stream copy only (fail fast)")
    mode.add_argument("--reencode", dest="mode", action="store_const", const="reencode",
                      help="force re-encode")
    mode.add_argument("--auto", dest="mode", action="store_const", const="auto",
                      help="default: copy first, auto fallback")
    ap.set_defaults(mode="auto")
    ap.add_argument("--crf", type=int, default=23)
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=7200)
    ap.add_argument("--ffparam", nargs="*", default=[])
    args = ap.parse_args()

    if args.lang:
        LANG = args.lang

    args.files = list(args.files) + list(args.url)
    ffmpeg = find_ffmpeg(args.ffmpeg)
    outdir = Path(args.output_dir) if args.output_dir else None
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)

    sources = collect_inputs(args)
    print(t("header", n=len(sources), ff=ffmpeg, mode=args.mode))
    print()

    tasks = [(s, build_output_name(s, outdir)) for s in sources]
    results = []
    if args.jobs <= 1:
        for i, (src, dst) in enumerate(tasks, 1):
            print("[%d/%d] %s" % (i, len(tasks), src))
            ok, msg, dst2 = convert_one(ffmpeg, src, dst, args)
            print("    %s %s  (%s)" % ("✔" if ok else "✘", dst2.name, msg))
            results.append((src, ok, msg))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
            futs = {ex.submit(convert_one, ffmpeg, src, dst, args): src
                    for src, dst in tasks}
            done = 0
            for fut in concurrent.futures.as_completed(futs):
                src = futs[fut]
                ok, msg, dst2 = fut.result()
                done += 1
                print("[%d/%d] %s %s -> %s (%s)" %
                      (done, len(tasks), "✔" if ok else "✘", src, dst2.name, msg))
                results.append((src, ok, msg))

    fails = [r for r in results if not r[1]]
    print(t("done", ok=len(results) - len(fails), n=len(results)))
    if fails:
        print(t("fail_list"))
        for src, _, msg in fails:
            print("  - %s: %s" % (src, msg))
        sys.exit(1)


if __name__ == "__main__":
    main()
