#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m3u8_to_mp4.py — 批量把 m3u8 合成 mp4

用法示例：
  python m3u8_to_mp4.py "D:\\videos\\a.m3u8" "D:\\videos\\b.m3u8"      # 指定多个文件
  python m3u8_to_mp4.py -i "D:\\videos"                                # 扫描整个文件夹里所有 .m3u8
  python m3u8_to_mp4.py -i "D:\\videos" -o "D:\\mp4out" -r             # 输出目录 + 递归 + 删除中间ts
  python m3u8_to_mp4.py -i "D:\\videos" --copy --jobs 4                # 直接流复制(最快)，4 个并发

依赖：ffmpeg（需要在 PATH 里，或用 --ffmpeg 指定 ffmpeg.exe 的完整路径）

两种合成模式：
  1. --copy（默认先尝试）：不重新编码，直接把 ts/分段 封装进 mp4，速度极快、无损。
     适用于标准 HLS（fMP4/TS，编码为 H.264/AAC）。
  2. 重编码 fallback：如果 copy 失败（分段编码不兼容、时间戳断裂等），
     自动改用 libx264 + aac 重新编码（慢但兼容性最好）。
     也可以直接 --reencode 强制走这条路。

本地 m3u8（清单里写的是相对路径的 .ts）和网络 m3u8（http/https 的 ts）都支持。
"""

import argparse
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Windows 控制台默认 GBK，防止打印中文/符号时崩溃
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def find_ffmpeg(explicit: str | None) -> str:
    """定位 ffmpeg 可执行文件"""
    if explicit:
        p = Path(explicit)
        if p.exists():
            return str(p)
        sys.exit(f"[错误] 找不到指定的 ffmpeg: {explicit}")
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    # Windows 常见安装位置兜底搜索
    if os.name == "nt":
        for base in (r"C:\ffmpeg\bin", r"D:\ffmpeg\bin",
                     os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links")):
            cand = Path(base) / "ffmpeg.exe"
            if cand.exists():
                return str(cand)
    sys.exit("[错误] 未找到 ffmpeg。请安装后加入 PATH，或用 --ffmpeg 指定 ffmpeg.exe 路径。\n"
             "  安装参考: winget install Gyan.FFmpeg  或 https://www.gyan.dev/ffmpeg/builds/")
    return ""  # 不会走到


def probe_ffprobe(ffmpeg: str) -> str | None:
    """根据 ffmpeg 路径推测 ffprobe"""
    p = Path(ffmpeg)
    cand = p.with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    return str(cand) if cand.exists() else shutil.which("ffprobe")


def is_network_m3u8(path_or_url: str) -> bool:
    return bool(re.match(r"^https?://", path_or_url, re.I))


def run(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout,
    )


def check_segments_local(m3u8: Path) -> list[str]:
    """检查本地 m3u8 清单里引用的相对路径分段是否都存在，返回缺失列表。"""
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
        seg = (m3u8.parent / line)
        if not seg.exists():
            missing.append(line)
    return missing


def build_output_name(src: str, outdir: Path | None, base_dir: Path | None) -> Path:
    """决定输出 mp4 的路径"""
    if is_network_m3u8(src):
        # 从 URL 里取文件名，取不到就用时间戳
        name = Path(src.split("?")[0].rstrip("/")).name
        if not name.lower().endswith(".m3u8"):
            name = f"download_{abs(hash(src)) % 100000:05d}.m3u8"
    else:
        name = Path(src).name
    stem = Path(name).stem
    if outdir:
        return outdir / f"{stem}.mp4"
    if base_dir is not None:
        return base_dir / f"{stem}.mp4"
    return Path(src).with_suffix("").parent / f"{stem}.mp4" if not is_network_m3u8(src) \
        else Path.cwd() / f"{stem}.mp4"


def encode_cmd(ffmpeg: str, src: str, dst: Path, mode: str,
               crf: int, preset: str, extra: list[str], jobs: int) -> list[str]:
    common = ["-y", "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats"]
    # 输入前置参数（网络源加大超时重试）
    input_opts: list[str] = []
    if is_network_m3u8(src):
        input_opts += ["-reconnect", "1", "-reconnect_streamed", "1",
                       "-reconnect_delay_max", "10"]
    if mode == "copy":
        codec_opts = ["-c", "copy", "-bsf:a", "aac_adtstoasc"]
    else:
        codec_opts = ["-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                      "-c:a", "aac", "-b:a", "192k"]
    return [ffmpeg, *input_opts, "-i", src, *codec_opts, *extra,
            "-movflags", "+faststart", *common, str(dst)]


def convert_one(ffmpeg: str, src: str, dst: Path, args) -> tuple[bool, str, Path]:
    """把单个 m3u8 合成为 mp4，返回 (成功?, 信息, 输出路径)"""
    stem = dst.stem
    tmp = dst.with_name(f"{stem}.partial.mp4")
    mode = args.mode  # 'copy' | 'reencode' | 'auto'

    # 本地清单先检查分段完整性，早发现早报错
    if not is_network_m3u8(src):
        missing = check_segments_local(Path(src))
        if missing:
            return False, f"清单引用的分段文件缺失 {len(missing)} 个，例如: {missing[0]}", dst

    def _run(cmd: list[str]) -> tuple[bool, str]:
        try:
            r = run(cmd, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            return False, f"超时（>{args.timeout}s）"
        except Exception as e:
            return False, str(e)
        if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
            return True, ""
        err_tail = (r.stderr or "").strip().splitlines()[-3:]
        return False, " | ".join(err_tail) if err_tail else f"ffmpeg 退出码 {r.returncode}"

    # copy / auto 模式先走无损封装
    if mode in ("copy", "auto"):
        cmd = encode_cmd(ffmpeg, src, tmp, "copy", args.crf, args.preset,
                         args.ffparam, args.jobs)
        ok, msg = _run(cmd)
        if ok:
            os.replace(tmp, dst)
            return True, "stream copy（无损、未重编码）", dst
        if mode == "copy":
            tmp.unlink(missing_ok=True)
            return False, f"copy 失败: {msg}", dst
        # auto：清理后降级为重编码
        tmp.unlink(missing_ok=True)
        print(f"    [auto] copy 失败({msg[:80]})，降级为重新编码 ...")

    cmd = encode_cmd(ffmpeg, src, tmp, "reencode", args.crf, args.preset,
                     args.ffparam, args.jobs)
    ok, msg = _run(cmd)
    if ok:
        os.replace(tmp, dst)
        return True, "re-encode（libx264+aac）", dst
    tmp.unlink(missing_ok=True)
    return False, f"重编码失败: {msg}", dst


def collect_inputs(args) -> list[str]:
    sources: list[str] = []
    if args.input_dir:
        d = Path(args.input_dir)
        if not d.is_dir():
            sys.exit(f"[错误] 目录不存在: {d}")
        pattern = "**/*.m3u8" if args.recursive else "*.m3u8"
        sources += [str(p) for p in sorted(d.glob(pattern))]
    for f in (args.files or []):
        # 拖进来的是文件夹时，自动扫描其中的 m3u8（支持 bat 拖拽用法）
        p = Path(f)
        if p.is_dir():
            sources += [str(x) for x in sorted(p.rglob("*.m3u8"))]
        else:
            sources.append(f)
    if not sources:
        sys.exit("[错误] 没有输入。给文件路径，或用 -i 目录，或 --url 网络地址。")
    # 去重保持顺序
    seen, uniq = set(), []
    for s in sources:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def main():
    ap = argparse.ArgumentParser(
        description="批量 m3u8 合成 mp4（优先无损 stream copy，失败自动重编码）",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    ap.add_argument("files", nargs="*", help="一个或多个 .m3u8 文件路径")
    ap.add_argument("-i", "--input-dir", help="扫描该目录下所有 .m3u8")
    ap.add_argument("-o", "--output-dir", help="输出目录（默认与各自源文件同目录）")
    ap.add_argument("-r", "--recursive", action="store_true", help="配合 -i 递归子目录")
    ap.add_argument("--url", action="append", default=[], help="网络 m3u8 地址（可多次）")
    ap.add_argument("--ffmpeg", help="ffmpeg 可执行文件路径")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--copy", dest="mode", action="store_const", const="copy",
                      help="只允许无损封装，不重编码（失败即报错）")
    mode.add_argument("--reencode", dest="mode", action="store_const", const="reencode",
                      help="强制重新编码")
    mode.add_argument("--auto", dest="mode", action="store_const", const="auto",
                      help="默认：先 copy，失败自动降级重编码")
    ap.set_defaults(mode="auto")
    ap.add_argument("--crf", type=int, default=23, help="重编码质量 0-51，越小越好，默认 23")
    ap.add_argument("--preset", default="medium",
                    help="重编码速度档 ultrafast..veryslow，默认 medium")
    ap.add_argument("--jobs", type=int, default=1, help="并发合成数量，默认 1")
    ap.add_argument("--timeout", type=int, default=7200, help="单个任务超时秒数，默认 7200")
    ap.add_argument("--ffparam", nargs="*", default=[],
                    help="透传给 ffmpeg 的额外参数，如 --ffparam -vf scale=1920:-2")
    args = ap.parse_args()

    # --url 并入 files
    args.files = list(args.files) + list(args.url)

    ffmpeg = find_ffmpeg(args.ffmpeg)
    outdir = Path(args.output_dir) if args.output_dir else None
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)

    sources = collect_inputs(args)
    print(f"共 {len(sources)} 个待合成任务 | ffmpeg: {ffmpeg} | 模式: {args.mode}\n")

    tasks = [(s, build_output_name(s, outdir, None)) for s in sources]

    results = []
    if args.jobs <= 1:
        for i, (src, dst) in enumerate(tasks, 1):
            print(f"[{i}/{len(tasks)}] {src}")
            ok, msg, dst2 = convert_one(ffmpeg, src, dst, args)
            tag = "✔" if ok else "✘"
            print(f"    {tag} {dst2.name}  ({msg})")
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
                tag = "✔" if ok else "✘"
                print(f"[{done}/{len(tasks)}] {tag} {src} -> {dst2.name} ({msg})")
                results.append((src, ok, msg))

    fails = [r for r in results if not r[1]]
    print(f"\n完成：成功 {len(results) - len(fails)} / {len(results)}")
    if fails:
        print("失败清单：")
        for src, _, msg in fails:
            print(f"  - {src}: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
