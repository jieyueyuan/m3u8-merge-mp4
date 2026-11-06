[🇨🇳 中文](README.md) · [🇺🇸 English](README.en.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md)

# m3u8-merge-mp4 🎬

`.m3u8`（HLSプレイリスト＋セグメント）を一括で `.mp4` に合成する Windows 用小型ツール。
Python の追加インストールは不要 — 唯一の外部依存は [ffmpeg](https://ffmpeg.org/) です。

**方針：まず可逆カプセリング（stream copy・一瞬・画質劣化ゼロ）、失敗時は libx264+aac 再エンコードへ自動切替。**

## 使い方は4通り、お好きに

### 1. ドラッグ＆ドロップ bat（最も簡単）

m3u8 **ファイルやフォルダごと** `拖我一把-把m3u8拖进来.bat` のアイコンに放り込む。

- フォルダを落とすと再帰的に `.m3u8` を探索
- mp4 は各ソースの隣に出力
- この bat は `m3u8_to_mp4.py` と同じフォルダに置くこと

### 2. ダブルクリック bat（単体で完結）

`双击合成-当前文件夹.bat` を m3u8 が置いてある**フォルダの中にコピー**してダブルクリック。

- pure bat + ffmpeg のみ。他のファイル不要で、これ1つ持ち運べる
- そのフォルダ内の全 `.m3u8` を処理。既存 mp4 はスキップ
- 壊れたファイルがあっても中断せず、最後に `N 成功 / N 失敗` のまとめ表示

### 3. GUI アプリ

`m3u8合成器GUI.py` をダブルクリック（Python 3.8+ が必要、tkinter は同梱）：

- ファイル／フォルダ追加ボタン、進捗バー、ログ、停止ボタン
- 出力先・上書き政策・カプセリング限定／再エンコード／自動 モード選択
- コンソールなし — コマンドラインに馴染みのない方に最適

## コマンドライン（多機能）

```bash
python m3u8_to_mp4.py a.m3u8 b.m3u8                       # 複数ファイル
python m3u8_to_mp4.py -i "D:\videos" -o "D:\out" -r       # フォルダ走査（-r 再帰）＋出力先指定
python m3u8_to_mp4.py -i "D:\videos" --copy --jobs 4      # カプセリングのみ・4並列
python m3u8_to_mp4.py -i "D:\videos" --reencode --crf 20 --preset fast
python m3u8_to_mp4.py --url "https://example.com/index.m3u8"  # ネット m3u8（自動再接続）
```

主なオプション：

| オプション | 意味 |
|---|---|
| `--copy` / `--reencode` / `--auto` | カプセリングのみ（失敗時エラー）／再エンコード強制／既定：copy→自動降格 |
| `--crf 23` `--preset medium` | 再エンコード品質／速度 |
| `--jobs 4` | 並列数 |
| `-o DIR` | 出力フォルダ統一 |
| `--ffmpeg PATH` | ffmpeg.exe 明示 |
| `--timeout SEC` | 1タスクの上限時間（既定 7200） |
| `--lang zh\|en\|ja\|ko` | メッセージ言語の強制 |

## 表示言語（中文 / English / 日本語 / 한국어）

すべての実行時メッセージは**システムUI言語に自動追従**。強制するには：

```bash
set M3U8_LANG=zh        # CMD（GUI・ドラッグbat も含む全入口で有効）
$env:M3U8_LANG="ja"     # PowerShell
export M3U8_LANG=ko     # bash
# または python m3u8_to_mp4.py ... --lang ja
```

ダブルクリック bat の文言は同 folder の `lang_zh.txt / lang_en.txt / lang_ja.txt / lang_ko.txt`（KEY=VALUE 形式、自由に編集可）から読み込みます。lang ファイルが全て無い場合は内蔵英語にフォールバックするので、bat 単体コピーでもそのまま動きます。

## 必要環境

- **ffmpeg**（必須）：`winget install Gyan.FFmpeg`、または [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) の full build を解凍して PATH へ。スクリプトは一般的なインストール位置も自動探索。
- **Python 3.8+**（方法1/3/CLI のみ。方法2の pure bat は不要）。Windows 版インストーラーは tkinter 同梱。

## 仕組みと注意点

- 標準 HLS（H.264/AAC の .ts）は `-c copy` ＋ `-bsf:a aac_adtstoasc`（音声ストリームヘッダ修正）でカプセリング。**このフィルタが無いと mp4 から音が出ない**——手作業変換が「失敗」する定番の原因です。
- ローカルプレイリストは事前にセグメント欠損チェック。欠けていれば明確なエラーで中止し、**途中で切れた動画は作られません**。
- 出力は `-movflags +faststart` 付き（配信・プレビュー向き）。
- copy 失敗（セグメント間のエンコード不一致・タイムスタンプ破損等）は auto モードで再エンコードに降格。
- 複数話を1本に連結したい場合：各話を mp4 にしてから `ffmpeg concat`。出力が統一 mp4 なので簡単です。
- ローカルファイルと http(s) m3u8 に対応。暗号化配信（EXT-X-KEY）は鍵の入手が必要で本ツールの対象外。

## ファイル構成

```
拖我一把-把m3u8拖进来.bat             方法1：ドラッグ入口
双击合成-当前文件夹.bat               方法2：folder に入れてダブルクリック
m3u8_to_mp4.py                        CLI エンジン／方法1 のバックエンド
m3u8合成器GUI.py                       方法3：tkinter GUI
lang_zh.txt lang_en.txt lang_ja.txt lang_ko.txt   方法2 の4言語文言
README.md README.en.md README.ja.md README.ko.md  4言語ドキュメント
```

ファイル名はリリース時の中文名のまま（動作・表示は完全にローカライズ済み）。

## FAQ

**Q: 「ffmpeg が見つからない」**
A: インストール後にターミナル／アプリを**再起動**（PATH 反映）。または `--ffmpeg` で指定、ffmpeg.exe＋ffprobe.exe をスクリプトと同 folder に置く。

**Q: bat の窓が一瞬で消える**
A: 正常系は最後に pause あり。クラッシュ時は Explorer のアドレスバーに `cmd` と打ち、そこから bat を実行してエラーを確認。

**Q: mp4 に音がない／ノイズ**
A: セグメントが特殊なため。再エンコード強制で再実行：`python m3u8_to_mp4.py FILE --reencode`。

**Q: フォルダを落としても無反応**
A: フォルダ対応はドラッグ版 bat（再帰走査）のみ。ダブルクリック版は自分の入っている folder だけ処理します。

## ライセンス

MIT — 自由に使用・改変可。出処を残していただければ嬉しいです。
