[🇨🇳 中文](README.md) · [🇺🇸 English](README.en.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md)

# m3u8-merge-mp4 🎬

`.m3u8`(HLS 플레이리스트 + 세그먼트)을 일괄로 `.mp4`에 병합하는 Windows 소형 도구.
Python 추가 설치 불필요 — 유일한 외부 의존성은 [ffmpeg](https://ffmpeg.org/)입니다.

**전략: 먼저 무손실 Remux(stream copy — 즉시, 화질 손실 0), 실패 시 libx264+aac 재인코딩으로 자동 전환.**

## 사용법 4가지, 편하게 선택

### 1. 드래그 & 드롭 bat (가장 쉬움)

m3u8 **파일이나 폴더째로** `拖我一把-把m3u8拖进来.bat` 아이콘에 끌어놓기.

- 폴더를 놓으면 하위까지 재귀적으로 `.m3u8` 탐색
- mp4는 각 원본 옆에 출력
- 이 bat은 `m3u8_to_mp4.py`와 같은 폴더에 두기

### 2. 더블클릭 bat (단일 파일 완결)

`双击合成-当前文件夹.bat`를 m3u8이 있는 **폴더 안에 복사** 후 더블클릭.

- pure bat + ffmpeg만. 다른 파일 불필요, 이것 하나만 들고 다니기 가능
- 그 폴더의 모든 `.m3u8` 처리, 이미 있는 mp4는 건너뜀
- 깨진 파일이 있어도 중단하지 않고, 마지막에 `N 성공 / N 실패` 요약

### 3. GUI 앱

`m3u8合成器GUI.py` 더블클릭 (Python 3.8+ 필요, tkinter 기본 포함):

- 파일/폴더 추가 버튼, 진행바, 로그, 중지 버튼
- 출력 폴더·덮어쓰기 정책·Remux전용/재인코딩/자동 모드 선택
- 콘솔 창 없음 — 명령줄이 익숙하지 않은 분께 최적

## 명령줄 (기능 최다)

```bash
python m3u8_to_mp4.py a.m3u8 b.m3u8                       # 여러 파일
python m3u8_to_mp4.py -i "D:\videos" -o "D:\out" -r       # 폴더 탐색(-r 재귀) + 출력 지정
python m3u8_to_mp4.py -i "D:\videos" --copy --jobs 4      # Remux 전용 · 4병렬
python m3u8_to_mp4.py -i "D:\videos" --reencode --crf 20 --preset fast
python m3u8_to_mp4.py --url "https://example.com/index.m3u8"  # 네트워크 m3u8(자동 재연결)
```

주요 옵션:

| 플래그 | 의미 |
|---|---|
| `--copy` / `--reencode` / `--auto` | Remux 전용(실패 시 오류) / 재인코딩 강제 / 기본: copy→자동 강등 |
| `--crf 23` `--preset medium` | 재인코딩 품질/속도 |
| `--jobs 4` | 병렬 수 |
| `-o DIR` | 출력 폴더 통일 |
| `--ffmpeg PATH` | ffmpeg.exe 직접 지정 |
| `--timeout SEC` | 작업당 제한 시간(기본 7200) |
| `--lang zh\|en\|ja\|ko` | 메시지 언어 강제 |

## 표시 언어 (中文 / English / 日本語 / 한국어)

모든 실행 메시지은 **시스템 UI 언어를 자동 따름**. 강제 방법:

```bash
set M3U8_LANG=en        # CMD (GUI·드래그 bat 포함 모든 입구에 적용)
$env:M3U8_LANG="ja"     # PowerShell
export M3U8_LANG=ko     # bash
# 또는: python m3u8_to_mp4.py ... --lang ko
```

더블클릭 bat의 문구는 같은 폴더의 `lang_zh.txt / lang_en.txt / lang_ja.txt / lang_ko.txt`(KEY=VALUE 형식, 자유 편집)에서 읽습니다. lang 파일이 전부 없으면 내장 영어로 폴백하므로, bat 단독 복사도 그대로 동작합니다.

## 필요 환경

- **ffmpeg** (필수): `winget install Gyan.FFmpeg`, 또는 [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) full 빌드를 압축해제한 뒤 PATH에 추가. 스크립트는 일반 설치 위치도 자동 탐지.
- **Python 3.8+** (방법 1/3/CLI만. 방법 2 pure bat은 불필요). Windows 설치판은 tkinter 기본 포함.

## 원리와 주의점

- 표준 HLS(H.264/AAC .ts)는 `-c copy` + `-bsf:a aac_adtstoasc`(오디오 스트림 헤더 교정)로 Remux. **이 필터가 없으면 mp4에 소리가 안 나옵니다** — 수동 변환이 "실패"하는 단골 원인.
- 로컬 플레이리스트는 미리 세그먼트 결손 점검. 없으면 명시적 오류로 중단, **중간에 끊긴 영상은 만들지 않습니다**.
- 출력은 `-movflags +faststart` 부착(스트리밍/미리보기에 적합).
- copy 실패(세그먼트 간 인코딩 불일치·타임스탬프 파손 등)는 auto 모드에서 재인코딩으로 강등.
- 여러 편을 하나로 합치고 싶다면: 각 편을 mp4로 만든 뒤 `ffmpeg concat`. 출력이 통일된 mp4라 간단합니다.
- 로컬 파일과 http(s) m3u8 지원. 암호화 스트림(EXT-X-KEY)은 키 확보가 먼저로, 이 도구 범위 밖.

## 파일 구성

```
拖我一把-把m3u8拖进来.bat              방법 1: 드래그 입구
双击合成-当前文件夹.bat                방법 2: 폴더에 넣고 더블클릭
m3u8_to_mp4.py                         CLI 엔진 / 방법 1의 백엔드
m3u8合成器GUI.py                        방법 3: tkinter GUI
lang_zh.txt lang_en.txt lang_ja.txt lang_ko.txt   방법 2의 4언어 문구
README.md README.en.md README.ja.md README.ko.md  4언어 문서
```

파일 이름은 배포 시 중국어 그대로 유지(동작·표시는 완전 현지화).

## FAQ

**Q: "ffmpeg을 찾을 수 없음"**
A: 설치 후 터미널/앱을 **다시 열기**(PATH 반영). 또는 `--ffmpeg` 지정, ffmpeg.exe+ffprobe.exe를 스크립트와 같은 폴더에 놓기.

**Q: bat 창이 잠깐 떴다가 사라짐**
A: 정상 경로면 끝에 pause 있음. 크래시라면 Explorer 주소창에 `cmd`를 입력해 거기서 bat을 실행, 오류 확인.

**Q: mp4에 소리가 없음/화면 깨짐**
A: 세그먼트가 특수한 경우. 재인코딩 강제로 재실행: `python m3u8_to_mp4.py FILE --reencode`.

**Q: 폴더를 놔도 반응 없음**
A: 폴더 처리는 드래그판 bat(재귀 탐색)만. 더블클릭판은 자기가 든 폴더만 처리합니다.

## 라이선스

MIT — 자유롭게 사용·수정. 출처를 남겨주시면 감사하겠습니다.
