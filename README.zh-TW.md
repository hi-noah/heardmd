# heardmd

[English](README.md) | 繁體中文

把會議錄音或錄影轉成 **markdown 逐字稿**，標上**講者**和**時間碼**。需要的話，再交給 Claude Code 潤飾成好讀、但**不刪減內容**的會議紀錄，並以**你自己的筆記和文件當背景資料**，把人名和專有名詞寫對。

- **轉錄全在本機**：[whisper.cpp](https://github.com/ggml-org/whisper.cpp) v1.9.5 + `large-v3-turbo`（Metal 加速），講者分離用 [pyannote.audio](https://github.com/pyannote/pyannote-audio) 3.3.2。錄音不會離開你的電腦。
- **支援中文和英文**：中文輸出繁體，可以中英夾雜（繁體轉換用 [OpenCC](https://github.com/BYVoid/OpenCC) 1.4.2）。
- **潤飾是選配**：以無頭模式執行 [Claude Code](https://claude.com/claude-code)，用的是你自己的 Claude 帳號。逐字稿的**文字**會送到 Anthropic，錄音檔不會。
- **改了什麼都看得到**：潤飾不做摘要。推測的修正會附上原字，文末列出值得回頭對照錄音的地方和時間碼。
- 所有程式、模型和快取都裝在這個資料夾裡，刪掉資料夾就移除乾淨（見[移除](#移除)）。

> 目前只支援 Apple Silicon 的 macOS。

---

## 安裝

需要：Apple Silicon 的 Mac、Xcode Command Line Tools（`xcode-select --install`）、約 2.6 GB 空間、一個 Hugging Face 帳號。

```bash
git clone <this repo> ~/tools/heardmd
cd ~/tools/heardmd
./install.sh
```

`install.sh` 會依序安裝 uv、Python 3.12 和套件，下載並編譯 whisper.cpp，下載 Whisper 模型（1.6 GB，下載前會先問你），最後執行 `heardmd doctor` 檢查。可以隨時重新執行，已完成的步驟會跳過。

### 設定 Hugging Face（必要，只要做一次）

講者分離模型放在 Hugging Face 上，要先同意使用條款才能下載。

1. 登入 [Hugging Face](https://huggingface.co)，到 [segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) 和 [speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) 兩個頁面，按同意使用條款。
2. 到 [Access Tokens](https://huggingface.co/settings/tokens) 按 **Create new token**，類型選 **Read**，複製那串 `hf_` 開頭的 token（只會顯示一次）。
3. 執行 `bin/heardmd login`，貼上 token（畫面不會顯示），按 Enter。token 只存在 `cache/hf/token`，權限設為只有你自己能讀。

### 設定 Claude Code（只有潤飾需要）

1. 依 [Claude Code 官網](https://claude.com/claude-code)的說明安裝。
2. 在終端機執行一次 `claude`，依畫面登入你的 Claude 帳號（訂閱帳號或 API key 都可以）。
3. 執行 `claude auth status`，看到 `"loggedIn": true` 就完成了。

潤飾的用量算在你自己的帳號上：訂閱帳號會消耗用量額度，API key 則按用量計費。

### 確認一切正常

```bash
bin/heardmd doctor
```

會逐項檢查 whisper.cpp、模型、Python 套件、Hugging Face 權限、Claude Code 登入狀態和私人 guide，並告訴你哪裡要修。不花 Claude 用量，也不會下載任何東西。

想直接打 `heardmd` 就能用，可以在 `~/.zshrc` 加一行（移除時記得刪掉）：

```bash
alias heardmd="$HOME/tools/heardmd/bin/heardmd"
```

程式的訊息和說明是英文的。

---

## 使用

```
heardmd run <錄音>               完整流程：先轉錄，再交給 Claude Code 潤飾
heardmd transcribe <錄音>        只轉錄      → <原檔名>_transcript.md
heardmd polish <逐字稿.md>       只潤飾      → <原檔名>_polished.md
heardmd doctor                   檢查安裝與設定
heardmd login                    設定 Hugging Face token
```

大部分時候只要用 `heardmd run`。`transcribe` 適合只要原始逐字稿的時候（不需要 Claude 帳號）；`polish` 用來重新潤飾已有的逐字稿，例如換一份 guide 或換一個推理強度。

支援的格式：

- 音檔：m4a、mp3、wav、aac、flac、ogg、opus、aiff
- 影片（只取音軌）：mp4、mov、mkv、webm

### 只轉錄

```bash
heardmd transcribe ~/recordings/2026-1110.m4a
```

會在錄音旁產生 `2026-1110_transcript.md`，這是**原始逐字稿**：whisper 的逐字輸出，不刪字也不改寫（中文只做簡轉繁）。原始錄音只讀取，不會被修改、移動或刪除。

| 選項 | 說明 |
|---|---|
| `-l zh` / `-l en` | 錄音語言（預設 `zh`） |
| `-n 3` / `--speakers 3` | 講者人數（預設 2） |
| `--min-speakers 2 --max-speakers 5` | 不確定人數時，給一個範圍讓模型判斷 |
| `--start 600 --duration 300` | 只處理一段（秒），適合先試跑 |
| `-o 路徑.md` | 指定輸出位置 |
| `--overwrite` | 輸出檔已存在時覆寫（預設會拒絕） |
| `--opencc s2twp` | 中文連用詞一起轉成台灣用語（預設 `s2tw` 只轉字形） |

### 完整流程：轉錄並潤飾

```bash
heardmd run ~/recordings/2026-1110.m4a --guide weekly
```

1. 把錄音轉成 `2026-1110_transcript.md`。這個檔案已經存在的話，就直接用，不重新轉錄。
2. 以無頭模式呼叫 Claude Code，依 [`agent-guides/general.md`](agent-guides/general.md) 和你的私人 guide 潤飾。
3. 輸出 `<原檔名>_polished.md`。已有同名檔案時，改存成 `_polished-2.md`，不會覆蓋。

| 選項 | 說明 |
|---|---|
| `-g` / `--guide <名稱>` | 使用 `agent-guides/private/<名稱>.md`。只有一份私人 guide 時可以省略 |
| `-l zh` / `-l en` | 錄音語言（預設取私人 guide 的 `language`，再預設 `zh`） |
| `-n <人數>` | 講者人數（預設取私人 guide 的 `speakers`，再預設 2） |
| `--effort <強度>` | Claude 的推理強度：`low`、`medium`、`high`、`xhigh`、`max`。越高想得越久、越慢（預設用 Claude Code 目前的設定） |
| `--model <模型>` | 指定 Claude 模型（預設用 Claude Code 目前的設定） |
| `--dry-run` | 只顯示會怎麼執行，不轉錄也不呼叫 Claude |

### 只潤飾

```bash
heardmd polish ~/recordings/2026-1110_transcript.md --effort high
```

潤飾一份已有的原始逐字稿。可以用的選項和 `run` 一樣：`--guide`、`--effort`、`--model`、`--dry-run`。

參考耗時（Apple M4）：轉錄約為錄音長度的 1/6。潤飾 43 分鐘的會議，`medium` 強度約 4 分鐘，`xhigh` 約 11 分鐘。執行期間會防止 Mac 閒置睡眠（指令結束就自動解除），但**闔上螢幕仍會睡眠**，長檔案請保持螢幕打開。

每次潤飾的完整紀錄存在 `cache/logs/`。

#### 權限：Claude 能碰什麼

潤飾時，Claude Code 以 `dontAsk` 模式執行，沒有事先允許的動作一律拒絕：

- **只能讀**：私人 guide 的 `read_dirs`、原始逐字稿所在的資料夾、輸出資料夾。
- **只能寫**：這次的輸出檔，一個檔案。
- 只開放讀檔、搜尋、寫檔這幾個工具。Bash、上網、子代理、MCP 伺服器都不能用。

### Agent guide：通用和私人

這些檔案是寫給 Claude 的指引，不是給你看的說明文件。

| 檔案 | 內容 | 進版控 |
|---|---|---|
| `agent-guides/general.md` | 每種錄音都適用的規則：刪口頭禪、標點、處理辨識錯誤（有把握才改，推測的附上原字）、修正講者分段、輸出格式、中英文各自的細節。以英文撰寫 | ✅ |
| `agent-guides/private/<名稱>.md` | 這類會議的講者角色、背景資料、用語慣例；兩份衝突時以這份為準 | ❌（`.gitignore` 排除） |

建立私人 guide：

```bash
mkdir -p agent-guides/private
cp agent-guides/private.example.md agent-guides/private/weekly.md
```

開頭 `---` 之間是 heardmd 讀的設定，後面是用白話寫給 Claude 的說明，可以用任何語言寫（Claude 會用同一種語言回報）：

```yaml
---
output_dir: ~/Documents/meetings/polished   # 潤飾版存放的資料夾（不寫就放在逐字稿旁邊）
read_dirs:                                   # Claude 可以讀的背景資料
  - ~/Documents/meetings/notes
speakers: 2                                  # 轉錄時的講者人數
language: zh                                 # 錄音語言：zh 或 en
---
```

不同類型的會議（例如週會、訪談、課堂）各寫一份，用 `--guide` 切換。改完可以執行 `heardmd doctor` 檢查設定。

---

## 原始逐字稿格式

```markdown
**SPEAKER_00** [00:00:00]
對,就包括這些問題,…

**SPEAKER_01** [00:05:06]
我覺得我們先處理剛剛你說的那個問題 …
```

- 講者依第一次開口的順序編號，不猜姓名。
- 時間碼是原始檔案的時間（用 `--start` 時也一樣）。同一位講者連續講的話只標一個開始時間。
- 同一段發言中，停頓 3 秒以上，或累積約 200 字（英文約 600 字元）時，會在 whisper 的分段處換段落。

## 處理流程

1. 用 ffmpeg 轉成 16kHz 單聲道 wav，暫存在 `cache/tmp/`，結束後刪除。程式被中斷也會刪；萬一殘留，下次執行時會清掉超過一天的。
2. whisper.cpp 依指定的語言轉錄，輸出每段文字、時間，以及每個字詞的時間。
3. pyannote 判斷每段時間是誰在講話。
4. 合併：一段 whisper 文字裡如果換了人，只在**標點**或 whisper 的「 - 」換人標記處切開，每個子句歸給時間重疊最多的講者。切開後拼回去必須和原文一字不差，不符就保留整段。
5. 只有中文：OpenCC 把殘留的簡體字轉成繁體。whisper 的輸出本來就幾乎都是繁體，但 OpenCC 會把繁體裡本來就合法的字也「轉換」掉，把「只是」轉成「隻是」、「干擾」轉成「幹擾」。所以 [`data/opencc_keep.txt`](data/opencc_keep.txt) 裡的 203 個字會保留 whisper 的原字；這份清單由 [`data/make_opencc_keep.py`](data/make_opencc_keep.py) 從 OpenCC 的字典產生。

### 對 pyannote 的一處調整

pyannote 會把「至少有 12 個聲紋特徵」的群當成一位講者，這個門檻不隨錄音長度變化，而且它也會替極短的聲音片段算聲紋。實測 88 分鐘的會議（7834 個特徵）中，有 50 個來自這種極短片段，它們彼此相似、和兩位講者都不像，於是自成一群「講者」。指定 2 人時，pyannote 只好把兩位真正的講者併成一人。

heardmd 把門檻改成「至少佔全部特徵的 1%」（短錄音仍維持 12）。代價是：長錄音中講話時間不到全場約 1% 的人，會被併到別的講者。

### 已知限制

- 一份錄音只能指定一種語言。中文夾雜英文詞沒問題，但整段換成另一種語言時，whisper 只在檔案開頭判斷一次語言，換掉的那段會轉得很差。
- 「嗯」「對」這類很短的插話，常常沒轉出來，或併進主講者的句子裡。
- whisper 有時一段長達 30 秒、包含兩個人的話，只能在標點或「 - 」處切開，所以換人的位置可能差一兩句。
- 專有名詞可能聽錯，原始逐字稿不會修正，這是潤飾的工作。
- 潤飾採「有把握就直接改」，偶爾會改得太有自信，而且從潤飾版上看不出來。重要的段落，請對照原始逐字稿或錄音確認。

---

## 資料夾結構

```
bin/heardmd             唯一的指令（run、transcribe、polish、doctor、login）
src/
  transcribe.py         轉錄
  polish.py             潤飾：組合 guide、設定權限、呼叫 claude -p
  doctor.py             檢查安裝與設定
data/
  opencc_keep.txt       OpenCC 不能轉換的字
  make_opencc_keep.py   從 OpenCC 的字典重新產生上面的清單
agent-guides/
  general.md            給 Claude 的通用潤飾規則
  private.example.md    私人 guide 範本
  private/              你的私人 guide（不進版控）
install.sh              安裝
env.sh                  把所有快取導向本資料夾
pyproject.toml, uv.lock
```

`install.sh` 產生的（都不進版控）：

| 路徑 | 大小 | 內容 |
|---|---|---|
| `models/` | 1.6 GB | Whisper 模型 |
| `.venv/` | 約 850 MB | Python 虛擬環境（PyTorch、pyannote、OpenCC、ffmpeg） |
| `vendor/whisper.cpp/` | 約 100 MB | whisper.cpp 原始碼與編譯好的 `whisper-cli` |
| `.tools/` | 約 100 MB | uv 和 Python 3.12 |
| `cache/` | 約 60 MB | pyannote 模型、Hugging Face token、潤飾紀錄、暫存檔 |

`env.sh` 會把 uv、Python、Hugging Face、pyannote、PyTorch、matplotlib 的快取都指到 `cache/`，`bin/heardmd` 每次執行都會先載入它。

---

## 移除

```bash
rm -rf ~/tools/heardmd
```

逐字稿和潤飾版放在錄音旁或你設定的 `output_dir`，不會被刪除。

資料夾外可能留下的東西：

| 位置 | 怎麼移除 |
|---|---|
| Hugging Face 網站上的 token | 到 [Access Tokens](https://huggingface.co/settings/tokens) 刪除 |
| pyannote 模型的使用條款同意 | 不需處理；要取消，到 [Gated repos](https://huggingface.co/settings/gated-repos) |
| 自己加在 `~/.zshrc` 的 alias | 刪掉那一行 |

heardmd 不會安裝 Homebrew 套件或系統 Python 套件，也不會修改 shell 設定檔。

---

## 技術架構

| 領域 | 工具 |
|---|---|
| 語音辨識 | [whisper.cpp](https://github.com/ggml-org/whisper.cpp) v1.9.5、`large-v3-turbo` 模型、Metal |
| 講者分離 | [pyannote.audio](https://github.com/pyannote/pyannote-audio) 3.3.2、`speaker-diarization-3.1`、PyTorch（MPS） |
| 繁簡轉換 | [OpenCC](https://github.com/BYVoid/OpenCC) 1.4.2 |
| 音訊與影片解碼 | ffmpeg（透過 imageio-ffmpeg） |
| 逐字稿潤飾 | [Claude Code](https://claude.com/claude-code)，無頭模式（`claude -p`） |
| 環境 | [uv](https://github.com/astral-sh/uv)、Python 3.12 |
| 開發工具 | 以 Claude（Claude Code）加速開發 |

---

## 授權

heardmd 採用 [MIT 授權](LICENSE)。

- [`data/opencc_keep.txt`](data/opencc_keep.txt) 由 [OpenCC](https://github.com/BYVoid/OpenCC) 的字典產生（Apache License 2.0）。
- whisper.cpp（MIT）、Whisper 模型和 pyannote 模型都不包含在這個 repo 裡；它們由 `install.sh` 和 pyannote 另外下載，適用各自的授權與使用條款。
