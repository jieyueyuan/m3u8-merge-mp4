#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m3u8 合成器（GUI 版）— 双击运行即可，不需要命令行。

功能
  * 「添加 m3u8 文件」/「添加文件夹」批量导入
  * 优先无损封装（stream copy，秒出、画质零损失），失败自动降级重编码
  * 实时进度 + 日志；输出可选目录；可覆盖/跳过同名结果

依赖
  * Python 3.8+（tkinter 是自带的，Windows 安装包默认包含）
  * ffmpeg（在 PATH 里，或安装：winget install Gyan.FFmpeg）
"""

import os
import shutil
import subprocess
import sys
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

# 重编码参数（改这里即可）
X264_PRESET = "medium"
X264_CRF = "23"
AAC_BITRATE = "192k"


def find_ffmpeg():
    """定位 ffmpeg.exe"""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    if os.name == "nt":
        guesses = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"D:\ffmpeg\bin\ffmpeg.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe"),
            os.path.expandvars(r"%ProgramFiles%\ffmpeg\bin\ffmpeg.exe"),
        ]
        for g in guesses:
            if g and Path(g).exists():
                return g
    # 最后尝试同目录放一个 ffmpeg.exe
    local = Path(__file__).resolve().parent / "ffmpeg.exe"
    return str(local) if local.exists() else None


def probe_duration(ffmpeg_path, src):
    """取视频总时长（秒），失败返回 0"""
    ffprobe = Path(ffmpeg_path).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if not ffprobe.exists():
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return 0.0
    try:
        r = subprocess.run([str(ffprobe), "-v", "error", "-show_entries",
                            "format=duration", "-of", "csv=p=0", str(src)],
                           capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return 0.0


class App:
    def __init__(self, root):
        self.root = root
        root.title("m3u8 → mp4 合成器")
        root.geometry("760x580")
        root.minsize(600, 460)

        self.sources = []          # list[Path]
        self.busy = False
        self.cancel = threading.Event()
        self.cur_idx = 0
        self.cur_total = 1
        self.msgq = queue.Queue()

        # ---- 顶部按钮 ----
        bar = ttk.Frame(root, padding=(10, 10, 10, 4))
        bar.pack(fill="x")
        ttk.Button(bar, text="添加 m3u8 文件", command=self.add_files).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="添加文件夹", command=self.add_dir).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="移除选中", command=self.remove_sel).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="清空列表", command=self.clear).pack(side="left")

        # ---- 列表 ----
        lbframe = ttk.Frame(root, padding=(10, 0, 10, 4))
        lbframe.pack(fill="both", expand=True)
        self.lb = tk.Listbox(lbframe, selectmode="extended", height=9)
        scroll = ttk.Scrollbar(lbframe, command=self.lb.yview)
        self.lb.configure(yscrollcommand=scroll.set)
        self.lb.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # ---- 选项 ----
        opt = ttk.LabelFrame(root, text="选项", padding=10)
        opt.pack(fill="x", padx=10, pady=4)
        self.mode = tk.StringVar(value="auto")
        ttk.Radiobutton(opt, text="自动（先无损封装，失败自动重编码）",
                        variable=self.mode, value="auto").grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Radiobutton(opt, text="仅无损封装 copy（最快，失败即报错）",
                        variable=self.mode, value="copy").grid(row=1, column=0, columnspan=4, sticky="w")
        ttk.Radiobutton(opt, text="强制重编码（兼容性最好，最慢）",
                        variable=self.mode, value="reencode").grid(row=2, column=0, columnspan=4, sticky="w")

        ttk.Label(opt, text="输出目录:").grid(row=3, column=0, sticky="e", pady=(8, 0))
        self.outdir = tk.StringVar()
        ttk.Entry(opt, textvariable=self.outdir, width=34).grid(row=3, column=1, columnspan=2, sticky="we", pady=(8, 0))
        ttk.Button(opt, text="浏览…", command=self.pick_out).grid(row=3, column=3, sticky="w", padx=(6, 0), pady=(8, 0))
        ttk.Label(opt, text="留空 = 输出到各源文件所在目录").grid(row=4, column=1, columnspan=3, sticky="w")
        opt.columnconfigure(1, weight=1)

        self.overwrite = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text="覆盖已有同名 mp4", variable=self.overwrite)\
            .grid(row=5, column=0, columnspan=4, sticky="w", pady=(6, 0))

        # ---- 进度 & 控制 ----
        bottom = ttk.Frame(root, padding=(10, 6))
        bottom.pack(fill="x")
        self.progress = ttk.Progressbar(bottom, mode="determinate", maximum=100.0)
        self.progress.pack(fill="x", pady=(0, 6))
        row = ttk.Frame(bottom)
        row.pack(fill="x")
        self.btn_go = ttk.Button(row, text="▶ 开始合成", command=self.start)
        self.btn_go.pack(side="left")
        self.btn_stop = ttk.Button(row, text="■ 停止", command=self.stop, state="disabled")
        self.btn_stop.pack(side="left", padx=6)
        self.status = tk.StringVar(value="请添加 m3u8 文件")
        ttk.Label(row, textvariable=self.status).pack(side="left", padx=12)

        # ---- 日志 ----
        logf = ttk.LabelFrame(root, text="日志", padding=6)
        logf.pack(fill="both", padx=10, pady=(4, 10))
        self.log = tk.Text(logf, height=8, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

        # ffmpeg 自检
        self.ffmpeg = find_ffmpeg()
        if self.ffmpeg:
            self.log_line("已找到 ffmpeg: {}".format(self.ffmpeg))
        else:
            self.log_line("[警告] 未找到 ffmpeg。安装：winget install Gyan.FFmpeg "
                          "或把 ffmpeg.exe 放到本程序同目录后重启。")

        self.root.after(120, self.poll_queue)

    # ================= UI 辅助 =================
    def log_line(self, s):
        self.log.configure(state="normal")
        self.log.insert("end", str(s) + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def refresh_list(self):
        self.lb.delete(0, "end")
        for p in self.sources:
            self.lb.insert("end", str(p))
        self.status.set("共 {} 个任务".format(len(self.sources)))

    def add_files(self):
        fs = filedialog.askopenfilenames(
            title="选择 m3u8 文件",
            filetypes=[("HLS 清单", "*.m3u8"), ("所有文件", "*.*")])
        for f in fs:
            p = Path(f)
            if p not in self.sources:
                self.sources.append(p)
        self.refresh_list()

    def add_dir(self):
        d = filedialog.askdirectory(title="选择包含 m3u8 的文件夹")
        if not d:
            return
        n = 0
        for p in sorted(Path(d).rglob("*.m3u8")):
            if p not in self.sources:
                self.sources.append(p)
                n += 1
        self.refresh_list()
        self.status.set("新增 {} 个，共 {} 个任务".format(n, len(self.sources)))

    def pick_out(self):
        d = filedialog.askdirectory(title="输出目录")
        if d:
            self.outdir.set(d)

    def remove_sel(self):
        for i in reversed(self.lb.curselection()):
            del self.sources[i]
        self.refresh_list()

    def clear(self):
        self.sources = []
        self.refresh_list()

    # ================= 合成流程 =================
    def start(self):
        if self.busy:
            return
        if not self.ffmpeg:
            self.ffmpeg = find_ffmpeg()
        if not self.ffmpeg:
            messagebox.showerror(
                "缺少 ffmpeg",
                "未找到 ffmpeg.exe。\n\n"
                "安装方法（任选一）：\n"
                "  1) 打开命令行执行:  winget install Gyan.FFmpeg\n"
                "  2) 下载 https://www.gyan.dev/ffmpeg/builds/ 完整版，解压后把\n"
                "     bin\\ffmpeg.exe 所在目录加入 PATH，或直接把 ffmpeg.exe\n"
                "     和 ffprobe.exe 复制到本程序同目录。\n"
                "然后重新打开本程序。")
            return
        if not self.sources:
            messagebox.showinfo("提示", "请先添加 m3u8 文件（或文件夹）")
            return
        self.busy = True
        self.cancel.clear()
        self.btn_go.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.progress.configure(value=0)
        threading.Thread(target=self.worker, daemon=True).start()

    def stop(self):
        self.cancel.set()
        self.status.set("正在停止…")

    def worker(self):
        jobs = list(self.sources)
        total = len(jobs)
        self.cur_total = total
        ok = skip = fail = 0
        outdir = Path(self.outdir.get()) if self.outdir.get().strip() else None
        if outdir:
            outdir.mkdir(parents=True, exist_ok=True)

        for idx, src in enumerate(jobs, 1):
            if self.cancel.is_set():
                self.msgq.put(("log", "已停止，剩余任务未执行。"))
                break
            self.cur_idx = idx
            self.msgq.put(("log", "[{}/{}] {}".format(idx, total, src)))
            dst = (outdir / (src.stem + ".mp4")) if outdir else src.with_name(src.stem + ".mp4")
            if dst.exists() and not self.overwrite.get():
                self.msgq.put(("log", "    跳过：已存在 {}".format(dst.name)))
                skip += 1
                self.msgq.put(("progress", idx / total * 100.0))
                continue
            success, msg = self.convert(src, dst)
            if success:
                ok += 1
                self.msgq.put(("log", "    ✔ {}  ({})".format(dst.name, msg)))
            elif self.cancel.is_set():
                self.msgq.put(("log", "    已取消"))
            else:
                fail += 1
                self.msgq.put(("log", "    ✘ {}".format(msg)))
            self.msgq.put(("progress", idx / total * 100.0))

        self.msgq.put(("done", (ok, fail, skip, len(jobs), self.cancel.is_set())))

    def convert(self, src, dst):
        """返回 (成功?, 说明)"""
        tmp = dst.with_name(dst.stem + ".partial.mp4")
        mode = self.mode.get()

        # 本地清单：先检查分段是否齐全，缺了就早报错，免得产出半个视频
        if src.exists():
            missing = self.check_segments(src)
            if missing:
                return False, "清单引用的分段缺失 {} 个，例如: {}".format(len(missing), missing[0])

        dur = probe_duration(self.ffmpeg, src) or 0.0
        copy_opts = ["-c", "copy", "-bsf:a", "aac_adtstoasc"]
        enc_opts = ["-c:v", "libx264", "-preset", X264_PRESET, "-crf", X264_CRF,
                    "-c:a", "aac", "-b:a", AAC_BITRATE]

        if mode in ("copy", "auto"):
            good, msg = self.run_ffmpeg(src, tmp, copy_opts, dur)
            if good:
                os.replace(tmp, dst)
                return True, "无损封装，未重编码"
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            if mode == "copy":
                return False, "copy 失败: {}".format(msg[:160])
            if self.cancel.is_set():
                return False, "已取消"
            self.msgq.put(("log", "    [自动降级] copy 失败 → 重新编码"))

        good, msg = self.run_ffmpeg(src, tmp, enc_opts, dur)
        if good:
            os.replace(tmp, dst)
            return True, "重编码完成"
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        return False, msg[:200] or "ffmpeg 失败"

    @staticmethod
    def check_segments(src):
        missing = []
        try:
            text = Path(src).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return missing
        base = Path(src).parent
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith(("http://", "https://", "file:///", "data:")):
                continue
            if not (base / line).exists():
                missing.append(line)
        return missing[:5]

    def run_ffmpeg(self, src, dst, codec_opts, dur):
        """跑一次 ffmpeg；stdout 读进度，stderr 单独线程排空（防死锁）。"""
        cmd = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostats",
               "-progress", "pipe:1", "-y", "-i", str(src)]
        if str(src).lower().startswith(("http://", "https://")):
            cmd += ["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "10"]
        cmd += codec_opts + ["-movflags", "+faststart", str(dst)]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace")
        except OSError as e:
            return False, "无法启动 ffmpeg: {}".format(e)

        errbuf = []

        def drain_err():
            assert proc.stderr is not None
            for line in proc.stderr:
                line = line.rstrip()
                if line:
                    errbuf.append(line)
                    self.msgq.put(("log", "    " + line))

        t = threading.Thread(target=drain_err, daemon=True)
        t.start()

        assert proc.stdout is not None
        for line in proc.stdout:
            if self.cancel.is_set():
                proc.terminate()
                break
            k, _, v = line.strip().partition("=")
            if k in ("out_time_ms", "out_time_us") and dur > 0:
                try:
                    us = int(v) if k == "out_time_us" else int(v)
                    t_sec = us / 1_000_000 if k == "out_time_ms" else us / 1_000_000
                    pct = min(99.5, t_sec / dur * 100)
                    overall = (self.cur_idx - 1 + pct / 100) / self.cur_total * 100
                    self.msgq.put(("progress", overall))
                except ValueError:
                    pass
        t.join(timeout=5)
        code = proc.wait()
        good = code == 0 and Path(dst).exists() and Path(dst).stat().st_size > 0
        msg = " | ".join(errbuf[-2:]) if errbuf else ("退出码 {}".format(code))
        if self.cancel.is_set():
            return False, "已取消"
        return good, msg

    # ================= 队列轮询 =================
    def poll_queue(self):
        try:
            while True:
                kind, payload = self.msgq.get_nowait()
                if kind == "log":
                    self.log_line(payload)
                elif kind == "progress":
                    self.progress.configure(value=min(100.0, float(payload)))
                elif kind == "done":
                    ok, fail, skip, total, cancelled = payload
                    self.busy = False
                    self.btn_go.configure(state="normal")
                    self.btn_stop.configure(state="disabled")
                    self.progress.configure(value=100.0 if not cancelled else self.progress["value"])
                    self.status.set("完成：成功 {} / 失败 {} / 跳过 {}（共 {}）".format(ok, fail, skip, total))
                    if fail:
                        messagebox.showwarning("有失败项",
                                               "{} 个文件失败，详见日志。\n可改用「强制重编码」再跑一次。".format(fail))
        except queue.Empty:
            pass
        self.root.after(120, self.poll_queue)


def main():
    if sys.version_info < (3, 8):
        print("需要 Python 3.8 及以上")
        sys.exit(1)
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
