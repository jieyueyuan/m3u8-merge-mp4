# m3u8-merge-mp4 🎬

把 `.m3u8`（HLS 播放清单 + ts 分段）批量合成 `.mp4` 的 Windows 小工具。
零安装 Python 依赖，唯一外部依赖是 [ffmpeg](https://ffmpeg.org/)。

**核心策略：优先无损封装（stream copy，秒出、画质零损失），失败自动降级为 libx264+aac 重编码。**

## 三种用法，任选一种

### 1. 拖拽 bat（最省事）

把 m3u8 **文件或整个文件夹** 拖到 `拖我一把-把m3u8拖进来.bat` 图标上。

- 拖文件夹会自动递归扫描其中所有 `.m3u8`
- mp4 输出到各源文件所在目录
- 需要 bat 与 `m3u8_to_mp4.py` 在同一目录

### 2. 双击 bat（单文件走天下）

把 `双击合成-当前文件夹.bat` **复制进** m3u8 所在的文件夹，双击。

- 纯 bat + ffmpeg，不依赖仓库里其他任何文件，随手拷一个就能用
- 自动处理该文件夹内全部 `.m3u8`；已存在的同名 mp4 自动跳过
- 坏文件不会中断批次，最后汇总 `N ok / N failed`

### 3. GUI 窗口版

双击 `m3u8合成器GUI.py`（需 Python 3.8+，tkinter 自带）：

- 按钮添加文件/文件夹，进度条、日志、停止键
- 可选输出目录、覆盖策略、强制 copy / 强制重编码 / 自动
- 无黑窗口，适合不想碰命令行的人

## 命令行用法（功能最全）

```bash
# 多个文件
python m3u8_to_mp4.py a.m3u8 b.m3u8

# 扫描整个目录（-r 递归），指定输出目录
python m3u8_to_mp4.py -i "D:\videos" -o "D:\out" -r

# 并发 4 路 / 强制只无损 / 强制重编码
python m3u8_to_mp4.py -i "D:\videos" --copy --jobs 4
python m3u8_to_mp4.py -i "D:\videos" --reencode --crf 20 --preset fast

# 网络 m3u8（自动断线重连）
python m3u8_to_mp4.py --url "https://example.com/index.m3u8"
```

常用参数：

| 参数 | 说明 |
|---|---|
| `--copy` / `--reencode` / `--auto` | 封装策略（默认 auto：先 copy，失败自动重编码） |
| `--crf 23` `--preset medium` | 重编码质量/速度档 |
| `--jobs 4` | 并发合成数 |
| `-o 目录` | 统一输出目录 |
| `--ffmpeg 路径` | 手动指定 ffmpeg.exe |
| `--timeout 秒` | 单任务超时（默认 7200） |

## 依赖

- **ffmpeg**（必须）：`winget install Gyan.FFmpeg`，或从 [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) 下载完整版解压后加入 PATH。脚本也会自动探测常见安装位置。
- **Python 3.8+**（仅方式 1/3/命令行需要；方式 2 纯 bat 不需要）。Windows 安装包默认带 tkinter。

## 工作原理与注意事项

- 标准 HLS（H.264/AAC 的 .ts 分段）用 `-c copy` 直接封进 mp4，加 `-bsf:a aac_adtstoasc` 修正音频码流头——**没有这个过滤器，封出来的 mp4 会没声音**，这是很多人手动转失败的原因。
- 转换前先解析清单检查本地 ts 分段是否齐全；缺分段直接报错，**不会产出半个视频**。
- 输出带 `-movflags +faststart`，mp4 适合网络播放/预览。
- copy 失败（分段编码不一致、时间戳断裂等）在 auto 模式下自动降级重编码。
- 分集想拼成一部：把各集 mp4 用 ffmpeg concat 即可（本工具输出已统一为 mp4，拼接很直接）。
- 本工具处理**本地文件与 http(s) m3u8**；加密流（EXT-X-KEY）需先拿到密钥，超出本工具范围。

## 文件清单

```
拖我一把-把m3u8拖进来.bat    方式1：拖拽入口
双击合成-当前文件夹.bat      方式2：扔进文件夹双击（独立单文件）
m3u8_to_mp4.py              命令行引擎 / 方式1的后端
m3u8合成器GUI.py             方式3：tkinter 窗口版
```

## 常见问题

**Q: 提示找不到 ffmpeg？**
A: 安装后**重开**终端/程序（PATH 变化不影响已打开的进程），或用 `--ffmpeg` 指定 ffmpeg.exe 完整路径，或把 ffmpeg.exe+ffprobe.exe 放到脚本同目录。

**Q: 双击 bat 一闪而过？**
A: 正常路径不会闪退（结尾有 pause）；若闪退，在资源管理器地址栏输入 `cmd` 回车，从命令行手动运行 bat 看报错。

**Q: mp4 有了但没声音/花屏？**
A: 说明走了 copy 封装但源分段编码特殊，强制重编码再来一次：`python m3u8_to_mp4.py 文件 --reencode`。

**Q: 拖了文件夹没反应？**
A: 拖文件夹要用「拖我一把」版（递归扫描）；「双击合成」版只处理 bat 自己所在的文件夹。

## 许可

MIT —— 随便用、随便改，出处留一下就行。
