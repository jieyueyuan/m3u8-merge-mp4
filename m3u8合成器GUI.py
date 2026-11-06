#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m3u8 合成器（GUI 版）— double-click to run, no command line needed.

语言 / Languages: zh / en / ja / ko
  自动跟随系统界面语言；可用环境变量 M3U8_LANG=zh|en|ja|ko 覆盖。
  Follows the system UI language; override with env M3U8_LANG.

依赖 / Requires: Python 3.8+ (tkinter bundled) and ffmpeg
  (winget install Gyan.FFmpeg, or put ffmpeg.exe next to this script).
"""

import ctypes
import locale
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

# ======================================================================
# i18n (zh / en / ja / ko)
# ======================================================================
STRINGS = {
    "zh": {
        "title": "m3u8 → mp4 合成器",
        "add_files": "添加 m3u8 文件", "add_dir": "添加文件夹",
        "remove_sel": "移除选中", "clear": "清空列表",
        "options": "选项",
        "mode_auto": "自动（先无损封装，失败自动重编码）",
        "mode_copy": "仅无损封装 copy（最快，失败即报错）",
        "mode_reenc": "强制重编码（兼容性最好，最慢）",
        "outdir_lbl": "输出目录:", "browse": "浏览…",
        "outdir_hint": "留空 = 输出到各源文件所在目录",
        "overwrite": "覆盖已有同名 mp4",
        "start": "▶ 开始合成", "stop": "■ 停止",
        "need_files": "请添加 m3u8 文件",
        "log": "日志",
        "found_ff": "已找到 ffmpeg: {p}",
        "no_ff_warn": "[警告] 未找到 ffmpeg。安装：winget install Gyan.FFmpeg 或把 ffmpeg.exe 放到本程序同目录后重启。",
        "n_tasks": "共 {n} 个任务",
        "added_n": "新增 {a} 个，共 {n} 个任务",
        "pick_files": "选择 m3u8 文件", "hls": "HLS 清单", "all": "所有文件",
        "pick_dir": "选择包含 m3u8 的文件夹", "pick_out": "输出目录",
        "no_ff_title": "缺少 ffmpeg",
        "no_ff_body": "未找到 ffmpeg.exe。\n\n安装方法（任选一）：\n  1) 打开命令行执行:  winget install Gyan.FFmpeg\n  2) 下载 https://www.gyan.dev/ffmpeg/builds/ 完整版，解压后把\n     bin\\ffmpeg.exe 所在目录加入 PATH，或直接把 ffmpeg.exe\n     和 ffprobe.exe 复制到本程序同目录。\n然后重新打开本程序。",
        "need_files_title": "提示", "need_files_body": "请先添加 m3u8 文件（或文件夹）",
        "stopping": "正在停止…",
        "stopped": "已停止，剩余任务未执行。",
        "skipped": "    跳过：已存在 {n}",
        "ok": "    ✔ {n}  ({m})",
        "cancelled": "    已取消",
        "fail": "    ✘ {m}",
        "miss_seg": "清单引用的分段缺失 {k} 个，例如: {s}",
        "res_copy": "无损封装，未重编码",
        "res_enc": "重编码完成",
        "copy_fail": "copy 失败: {m}",
        "auto_fallback": "    [自动降级] copy 失败 → 重新编码",
        "ffmpeg_fail": "ffmpeg 失败",
        "spawn_fail": "无法启动 ffmpeg: {m}",
        "exit_code": "退出码 {c}",
        "done_fmt": "完成：成功 {ok} / 失败 {fail} / 跳过 {skip}（共 {n}）",
        "fail_title": "有失败项",
        "fail_body": "{n} 个文件失败，详见日志。\n可改用「强制重编码」再跑一次。",
    },
    "en": {
        "title": "m3u8 → mp4 Merger",
        "add_files": "Add m3u8 files", "add_dir": "Add folder",
        "remove_sel": "Remove selected", "clear": "Clear list",
        "options": "Options",
        "mode_auto": "Auto (lossless remux first, re-encode on failure)",
        "mode_copy": "Remux only / stream copy (fastest, fail fast)",
        "mode_reenc": "Force re-encode (best compatibility, slowest)",
        "outdir_lbl": "Output dir:", "browse": "Browse…",
        "outdir_hint": "Empty = save beside each source file",
        "overwrite": "Overwrite existing mp4",
        "start": "▶ Start", "stop": "■ Stop",
        "need_files": "Add m3u8 files to start",
        "log": "Log",
        "found_ff": "ffmpeg found: {p}",
        "no_ff_warn": "[warning] ffmpeg not found. Install: winget install Gyan.FFmpeg, or put ffmpeg.exe next to this program and restart.",
        "n_tasks": "{n} task(s)",
        "added_n": "Added {a}, total {n} task(s)",
        "pick_files": "Select m3u8 files", "hls": "HLS playlist", "all": "All files",
        "pick_dir": "Select folder containing m3u8", "pick_out": "Output directory",
        "no_ff_title": "ffmpeg missing",
        "no_ff_body": "ffmpeg.exe was not found.\n\nInstall one of:\n  1) Run in a terminal:  winget install Gyan.FFmpeg\n  2) Download the full build from https://www.gyan.dev/ffmpeg/builds/,\n     add bin\\ to PATH, or copy ffmpeg.exe and ffprobe.exe\n     next to this program.\nThen restart this app.",
        "need_files_title": "Info", "need_files_body": "Add m3u8 files (or a folder) first.",
        "stopping": "Stopping…",
        "stopped": "Stopped; remaining tasks skipped.",
        "skipped": "    skipped: {n} already exists",
        "ok": "    ✔ {n}  ({m})",
        "cancelled": "    cancelled",
        "fail": "    ✘ {m}",
        "miss_seg": "playlist references {k} missing segment(s), e.g.: {s}",
        "res_copy": "lossless remux",
        "res_enc": "re-encoded",
        "copy_fail": "copy failed: {m}",
        "auto_fallback": "    [auto] copy failed -> re-encoding",
        "ffmpeg_fail": "ffmpeg failed",
        "spawn_fail": "cannot start ffmpeg: {m}",
        "exit_code": "exit code {c}",
        "done_fmt": "Done: {ok} ok / {fail} failed / {skip} skipped (of {n})",
        "fail_title": "Some failures",
        "fail_body": "{n} file(s) failed, see log.\nTry 'Force re-encode' mode.",
    },
    "ja": {
        "title": "m3u8 → mp4 変換ツール",
        "add_files": "m3u8 ファイルを追加", "add_dir": "フォルダを追加",
        "remove_sel": "選択を削除", "clear": "一覧をクリア",
        "options": "オプション",
        "mode_auto": "自動（まず可逆カプセリング、失敗時は再エンコード）",
        "mode_copy": "カプセリングのみ copy（最速、失敗時はエラー）",
        "mode_reenc": "再エンコード強制（互換性最高、最遅）",
        "outdir_lbl": "出力先:", "browse": "参照…",
        "outdir_hint": "空白 = 各ソースファイルの隣に保存",
        "overwrite": "同名 mp4 を上書き",
        "start": "▶ 変換開始", "stop": "■ 停止",
        "need_files": "m3u8 ファイルを追加してください",
        "log": "ログ",
        "found_ff": "ffmpeg を検出: {p}",
        "no_ff_warn": "[警告] ffmpeg が見つかりません。winget install Gyan.FFmpeg でインストールするか、ffmpeg.exe を本プログラムと同じフォルダに置いて再起動してください。",
        "n_tasks": "タスク {n} 件",
        "added_n": "{a} 件追加、合計 {n} 件",
        "pick_files": "m3u8 ファイルを選択", "hls": "HLSプレイリスト", "all": "すべてのファイル",
        "pick_dir": "m3u8 を含むフォルダを選択", "pick_out": "出力ディレクトリ",
        "no_ff_title": "ffmpeg が見つかりません",
        "no_ff_body": "ffmpeg.exe が見つかりません。\n\nいずれかでインストール：\n  1) コマンドラインで:  winget install Gyan.FFmpeg\n  2) https://www.gyan.dev/ffmpeg/builds/ から full ビルドをダウンロードし、\n     bin\\ を PATH に追加、または ffmpeg.exe と ffprobe.exe を\n     本プログラムと同じフォルダにコピー。\nその後このアプリを再起動してください。",
        "need_files_title": "お知らせ", "need_files_body": "先に m3u8 ファイル（またはフォルダ）を追加してください。",
        "stopping": "停止中…",
        "stopped": "停止しました。残りのタスクは未実行です。",
        "skipped": "    スキップ：{n} は既存",
        "ok": "    ✔ {n}  ({m})",
        "cancelled": "    キャンセル",
        "fail": "    ✘ {m}",
        "miss_seg": "プレイリストのセグメント {k} 個が見つかりません（例: {s}）",
        "res_copy": "可逆カプセリング（再エンコードなし）",
        "res_enc": "再エンコード完了",
        "copy_fail": "copy 失敗: {m}",
        "auto_fallback": "    [自動] copy 失敗 → 再エンコードへ",
        "ffmpeg_fail": "ffmpeg 失敗",
        "spawn_fail": "ffmpeg を起動できません: {m}",
        "exit_code": "終了コード {c}",
        "done_fmt": "完了：成功 {ok} / 失敗 {fail} / スキップ {skip}（計 {n}）",
        "fail_title": "失敗あり",
        "fail_body": "{n} 件失敗しました。ログを確認してください。\n「再エンコード強制」で再実行できます。",
    },
    "ko": {
        "title": "m3u8 → mp4 병합 도구",
        "add_files": "m3u8 파일 추가", "add_dir": "폴더 추가",
        "remove_sel": "선택 삭제", "clear": "목록 비우기",
        "options": "옵션",
        "mode_auto": "자동(무손실Remux 우선, 실패 시 재인코딩)",
        "mode_copy": "Remux만 / stream copy(최고속, 실패 시 오류)",
        "mode_reenc": "재인코딩 강제(호환성 최고, 가장 느림)",
        "outdir_lbl": "출력 폴더:", "browse": "찾아보기…",
        "outdir_hint": "비워두면 각 원본 파일 옆에 저장",
        "overwrite": "동일 이름 mp4 덮어쓰기",
        "start": "▶ 병합 시작", "stop": "■ 중지",
        "need_files": "m3u8 파일을 추가하세요",
        "log": "로그",
        "found_ff": "ffmpeg 발견: {p}",
        "no_ff_warn": "[경고] ffmpeg을 찾을 수 없습니다. winget install Gyan.FFmpeg으로 설치하거나 ffmpeg.exe를 이 프로그램과 같은 폴더에 놓고 재시작하세요.",
        "n_tasks": "작업 {n}개",
        "added_n": "{a}개 추가, 총 {n}개 작업",
        "pick_files": "m3u8 파일 선택", "hls": "HLS 플레이리스트", "all": "모든 파일",
        "pick_dir": "m3u8가 들어 있는 폴더 선택", "pick_out": "출력 디렉토리",
        "no_ff_title": "ffmpeg 없음",
        "no_ff_body": "ffmpeg.exe를 찾을 수 없습니다.\n\n설치 방법(하나라도):\n  1) 터미널에서:  winget install Gyan.FFmpeg\n  2) https://www.gyan.dev/ffmpeg/builds/ 에서 full 빌드 다운로드 후\n     bin\\을 PATH에 추가하거나, ffmpeg.exe와 ffprobe.exe를\n     이 프로그램과 같은 폴더에 복사.\n그 후 이 앱을 다시 시작하세요.",
        "need_files_title": "알림", "need_files_body": "먼저 m3u8 파일(또는 폴더)을 추가하세요.",
        "stopping": "중지 중…",
        "stopped": "중지됨. 남은 작업은 실행되지 않았습니다.",
        "skipped": "    건너무: {n} 이미 존재",
        "ok": "    ✔ {n}  ({m})",
        "cancelled": "    취소됨",
        "fail": "    ✘ {m}",
        "miss_seg": "플레이리스트가 참조하는 세그먼트 {k}개 없음, 예: {s}",
        "res_copy": "무손실 Remux(재인코딩 없음)",
        "res_enc": "재인코딩 완료",
        "copy_fail": "copy 실패: {m}",
        "auto_fallback": "    [자동] copy 실패 → 재인코딩 전환",
        "ffmpeg_fail": "ffmpeg 실패",
        "spawn_fail": "ffmpeg을 시작할 수 없음: {m}",
        "exit_code": "종료 코드 {c}",
        "done_fmt": "완료: 성공 {ok} / 실패 {fail} / 건너무 {skip} (총 {n})",
        "fail_title": "실패 항목 있음",
        "fail_body": "{n}개 파일 실패, 로그를 확인하세요.\n'재인코딩 강제' 모드로 다시 실행할 수 있습니다.",
    },
}

UI_LANGUAGES = {0x04: "zh", 0x09: "en", 0x11: "ja", 0x12: "ko"}


def detect_lang():
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


def find_ffmpeg():
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
    local = Path(__file__).resolve().parent / "ffmpeg.exe"
    return str(local) if local.exists() else None


def probe_duration(ffmpeg_path, src):
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
        root.title(t("title"))
        root.geometry("760x580")
        root.minsize(600, 460)

        self.sources = []
        self.busy = False
        self.cancel = threading.Event()
        self.cur_idx = 0
        self.cur_total = 1
        self.msgq = queue.Queue()

        bar = ttk.Frame(root, padding=(10, 10, 10, 4))
        bar.pack(fill="x")
        ttk.Button(bar, text=t("add_files"), command=self.add_files).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text=t("add_dir"), command=self.add_dir).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text=t("remove_sel"), command=self.remove_sel).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text=t("clear"), command=self.clear).pack(side="left")

        lbframe = ttk.Frame(root, padding=(10, 0, 10, 4))
        lbframe.pack(fill="both", expand=True)
        self.lb = tk.Listbox(lbframe, selectmode="extended", height=9)
        scroll = ttk.Scrollbar(lbframe, command=self.lb.yview)
        self.lb.configure(yscrollcommand=scroll.set)
        self.lb.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        opt = ttk.LabelFrame(root, text=t("options"), padding=10)
        opt.pack(fill="x", padx=10, pady=4)
        self.mode = tk.StringVar(value="auto")
        ttk.Radiobutton(opt, text=t("mode_auto"), variable=self.mode, value="auto")\
            .grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Radiobutton(opt, text=t("mode_copy"), variable=self.mode, value="copy")\
            .grid(row=1, column=0, columnspan=4, sticky="w")
        ttk.Radiobutton(opt, text=t("mode_reenc"), variable=self.mode, value="reencode")\
            .grid(row=2, column=0, columnspan=4, sticky="w")

        ttk.Label(opt, text=t("outdir_lbl")).grid(row=3, column=0, sticky="e", pady=(8, 0))
        self.outdir = tk.StringVar()
        ttk.Entry(opt, textvariable=self.outdir, width=34).grid(row=3, column=1, columnspan=2, sticky="we", pady=(8, 0))
        ttk.Button(opt, text=t("browse"), command=self.pick_out).grid(row=3, column=3, sticky="w", padx=(6, 0), pady=(8, 0))
        ttk.Label(opt, text=t("outdir_hint")).grid(row=4, column=1, columnspan=3, sticky="w")
        opt.columnconfigure(1, weight=1)

        self.overwrite = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text=t("overwrite"), variable=self.overwrite)\
            .grid(row=5, column=0, columnspan=4, sticky="w", pady=(6, 0))

        bottom = ttk.Frame(root, padding=(10, 6))
        bottom.pack(fill="x")
        self.progress = ttk.Progressbar(bottom, mode="determinate", maximum=100.0)
        self.progress.pack(fill="x", pady=(0, 6))
        row = ttk.Frame(bottom)
        row.pack(fill="x")
        self.btn_go = ttk.Button(row, text=t("start"), command=self.start)
        self.btn_go.pack(side="left")
        self.btn_stop = ttk.Button(row, text=t("stop"), command=self.stop, state="disabled")
        self.btn_stop.pack(side="left", padx=6)
        self.status = tk.StringVar(value=t("need_files"))
        ttk.Label(row, textvariable=self.status).pack(side="left", padx=12)

        logf = ttk.LabelFrame(root, text=t("log"), padding=6)
        logf.pack(fill="both", padx=10, pady=(4, 10))
        self.log = tk.Text(logf, height=8, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

        self.ffmpeg = find_ffmpeg()
        if self.ffmpeg:
            self.log_line(t("found_ff", p=self.ffmpeg))
        else:
            self.log_line(t("no_ff_warn"))

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
        self.status.set(t("n_tasks", n=len(self.sources)))

    def add_files(self):
        fs = filedialog.askopenfilenames(
            title=t("pick_files"),
            filetypes=[(t("hls"), "*.m3u8"), (t("all"), "*.*")])
        for f in fs:
            p = Path(f)
            if p not in self.sources:
                self.sources.append(p)
        self.refresh_list()

    def add_dir(self):
        d = filedialog.askdirectory(title=t("pick_dir"))
        if not d:
            return
        n = 0
        for p in sorted(Path(d).rglob("*.m3u8")):
            if p not in self.sources:
                self.sources.append(p)
                n += 1
        self.refresh_list()
        self.status.set(t("added_n", a=n, n=len(self.sources)))

    def pick_out(self):
        d = filedialog.askdirectory(title=t("pick_out"))
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
            messagebox.showerror(t("no_ff_title"), t("no_ff_body"))
            return
        if not self.sources:
            messagebox.showinfo(t("need_files_title"), t("need_files_body"))
            return
        self.busy = True
        self.cancel.clear()
        self.btn_go.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.progress.configure(value=0)
        threading.Thread(target=self.worker, daemon=True).start()

    def stop(self):
        self.cancel.set()
        self.status.set(t("stopping"))

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
                self.msgq.put(("log", t("stopped")))
                break
            self.cur_idx = idx
            self.msgq.put(("log", "[{}/{}] {}".format(idx, total, src)))
            dst = (outdir / (src.stem + ".mp4")) if outdir else src.with_name(src.stem + ".mp4")
            if dst.exists() and not self.overwrite.get():
                self.msgq.put(("log", t("skipped", n=dst.name)))
                skip += 1
                self.msgq.put(("progress", idx / total * 100.0))
                continue
            success, msg = self.convert(src, dst)
            if success:
                ok += 1
                self.msgq.put(("log", t("ok", n=dst.name, m=msg)))
            elif self.cancel.is_set():
                self.msgq.put(("log", t("cancelled")))
            else:
                fail += 1
                self.msgq.put(("log", t("fail", m=msg)))
            self.msgq.put(("progress", idx / total * 100.0))

        self.msgq.put(("done", (ok, fail, skip, len(jobs), self.cancel.is_set())))

    def convert(self, src, dst):
        tmp = dst.with_name(dst.stem + ".partial.mp4")
        mode = self.mode.get()

        if src.exists():
            missing = self.check_segments(src)
            if missing:
                return False, t("miss_seg", k=len(missing), s=missing[0])

        dur = probe_duration(self.ffmpeg, src) or 0.0
        copy_opts = ["-c", "copy", "-bsf:a", "aac_adtstoasc"]
        enc_opts = ["-c:v", "libx264", "-preset", X264_PRESET, "-crf", X264_CRF,
                    "-c:a", "aac", "-b:a", AAC_BITRATE]

        if mode in ("copy", "auto"):
            good, msg = self.run_ffmpeg(src, tmp, copy_opts, dur)
            if good:
                os.replace(tmp, dst)
                return True, t("res_copy")
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            if mode == "copy":
                return False, t("copy_fail", m=msg[:160])
            if self.cancel.is_set():
                return False, t("cancelled")
            self.msgq.put(("log", t("auto_fallback")))

        good, msg = self.run_ffmpeg(src, tmp, enc_opts, dur)
        if good:
            os.replace(tmp, dst)
            return True, t("res_enc")
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        return False, (msg[:200] or t("ffmpeg_fail"))

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
        cmd = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostats",
               "-progress", "pipe:1", "-y", "-i", str(src)]
        if str(src).lower().startswith(("http://", "https://")):
            cmd += ["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "10"]
        cmd += codec_opts + ["-movflags", "+faststart", str(dst)]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace")
        except OSError as e:
            return False, t("spawn_fail", m=e)

        errbuf = []

        def drain_err():
            assert proc.stderr is not None
            for line in proc.stderr:
                line = line.rstrip()
                if line:
                    errbuf.append(line)
                    self.msgq.put(("log", "    " + line))

        th = threading.Thread(target=drain_err, daemon=True)
        th.start()

        assert proc.stdout is not None
        for line in proc.stdout:
            if self.cancel.is_set():
                proc.terminate()
                break
            k, _, v = line.strip().partition("=")
            if k in ("out_time_ms", "out_time_us") and dur > 0:
                try:
                    us = int(v)
                    t_sec = us / 1_000_000
                    pct = min(99.5, t_sec / dur * 100)
                    overall = (self.cur_idx - 1 + pct / 100) / self.cur_total * 100
                    self.msgq.put(("progress", overall))
                except ValueError:
                    pass
        th.join(timeout=5)
        code = proc.wait()
        good = code == 0 and Path(dst).exists() and Path(dst).stat().st_size > 0
        msg = " | ".join(errbuf[-2:]) if errbuf else t("exit_code", c=code)
        if self.cancel.is_set():
            return False, t("cancelled")
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
                    self.status.set(t("done_fmt", ok=ok, fail=fail, skip=skip, n=total))
                    if fail:
                        messagebox.showwarning(t("fail_title"), t("fail_body", n=fail))
        except queue.Empty:
            pass
        self.root.after(120, self.poll_queue)


def main():
    if sys.version_info < (3, 8):
        print("Python 3.8+ required")
        sys.exit(1)
    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetProcessDPIAware()
        except Exception:
            pass
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
