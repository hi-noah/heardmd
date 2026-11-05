# heardmd

English | [繁體中文](README.zh-TW.md)

Turn meeting recordings into **markdown transcripts** with **speaker labels** and **timestamps**. Optionally, have Claude Code polish them into readable notes that **keep everything that was said**, using **your own notes and documents as background** to get names and terms right.

- **Transcription runs locally**: [whisper.cpp](https://github.com/ggml-org/whisper.cpp) v1.9.5 with `large-v3-turbo` (Metal-accelerated), and [pyannote.audio](https://github.com/pyannote/pyannote-audio) 3.3.2 for speaker identification. Recordings never leave your computer.
- **Chinese and English**: Chinese is written in Traditional characters and may mix in English terms (conversion by [OpenCC](https://github.com/BYVoid/OpenCC) 1.4.2).
- **Polishing is optional**: it runs [Claude Code](https://claude.com/claude-code) headless with your own Claude account. The transcript **text** is sent to Anthropic; the recording is not.
- **Every change is visible**: polishing never summarizes. Guessed corrections keep the original words next to them, and a list at the end gives timestamps for everything worth checking against the recording.
- Programs, models and caches all live in this folder; deleting the folder removes them (see [Uninstall](#uninstall)).

> Currently macOS on Apple Silicon only.

---

## Install

You need: a Mac with Apple Silicon, the Xcode Command Line Tools (`xcode-select --install`), about 2.6 GB of disk space, and a Hugging Face account.

```bash
git clone <this repo> ~/tools/heardmd
cd ~/tools/heardmd
./install.sh
```

`install.sh` installs uv, Python 3.12 and the packages, downloads and builds whisper.cpp, downloads the Whisper model (1.6 GB; it asks first), and finally runs `heardmd doctor`. Run it again any time; finished steps are skipped.

### Set up Hugging Face (required, once)

The speaker identification models are hosted on Hugging Face and need their terms accepted before download.

1. Log in to [Hugging Face](https://huggingface.co) and accept the terms on the [segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) and [speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) pages.
2. Under [Access Tokens](https://huggingface.co/settings/tokens), click **Create new token**, choose type **Read**, and copy the token that starts with `hf_` (it is shown only once).
3. Run `bin/heardmd login`, paste the token (it is not displayed) and press Enter. The token is stored only in `cache/hf/token`, readable only by you.

### Set up Claude Code (only for polishing)

1. Install Claude Code by following the instructions on the [Claude Code site](https://claude.com/claude-code).
2. Run `claude` once in a terminal and log in to your Claude account (a subscription or an API key both work).
3. Run `claude auth status`; `"loggedIn": true` means you are done.

Polishing counts against your own account: a subscription uses your plan's usage limits; an API key is billed per use.

### Check that everything works

```bash
bin/heardmd doctor
```

It checks whisper.cpp, the model, the Python packages, Hugging Face access, the Claude Code login and your private guides, and tells you what to fix. It costs no Claude usage and downloads nothing.

To type just `heardmd`, add an alias to `~/.zshrc` (remove it when uninstalling):

```bash
alias heardmd="$HOME/tools/heardmd/bin/heardmd"
```

---

## Usage

```
heardmd run <recording>          full pipeline: transcribe, then polish with Claude Code
heardmd transcribe <recording>   transcribe only        → <name>_transcript.md
heardmd polish <transcript.md>   polish only            → <name>_polished.md
heardmd doctor                   check the installation and setup
heardmd login                    set the Hugging Face token
```

Most of the time you only need `heardmd run`. `transcribe` is for when you want just the raw transcript (it needs no Claude account); `polish` re-polishes a transcript you already have, for example with another guide or effort level.

Supported formats:

- Audio: m4a, mp3, wav, aac, flac, ogg, opus, aiff
- Video (audio track only): mp4, mov, mkv, webm

### Transcribe only

```bash
heardmd transcribe ~/recordings/2026-1110.m4a
```

This writes `2026-1110_transcript.md` next to the recording: the **raw transcript**, whisper's word-for-word output with nothing removed or rewritten (Chinese is only converted to Traditional characters). The recording is only read; it is never changed, moved or deleted.

| Option | Meaning |
|---|---|
| `-l zh` / `-l en` | Language of the recording (default `zh`) |
| `-n 3` / `--speakers 3` | Number of speakers (default 2) |
| `--min-speakers 2 --max-speakers 5` | If unsure, give a range and let the model decide |
| `--start 600 --duration 300` | Process only part of the file (seconds); handy for a trial run |
| `-o path.md` | Output path |
| `--overwrite` | Replace an existing output file (refused by default) |
| `--opencc s2twp` | For Chinese, also convert vocabulary to Taiwan usage (default `s2tw` converts characters only) |

### Full pipeline: transcribe and polish

```bash
heardmd run ~/recordings/2026-1110.m4a --guide weekly
```

1. The recording is transcribed into `2026-1110_transcript.md`. If that file already exists, it is used and transcription is skipped.
2. Claude Code runs headless and polishes it following [`agent-guides/general.md`](agent-guides/general.md) and your private guide.
3. The result is `<name>_polished.md`. If that exists, it is saved as `_polished-2.md` and so on; nothing is overwritten.

| Option | Meaning |
|---|---|
| `-g` / `--guide <name>` | Use `agent-guides/private/<name>.md`. Optional when there is only one private guide |
| `-l zh` / `-l en` | Language of the recording (default: the private guide's `language`, else `zh`) |
| `-n <count>` | Number of speakers (default: the private guide's `speakers`, else 2) |
| `--effort <level>` | Claude's reasoning effort: `low`, `medium`, `high`, `xhigh`, `max`. Higher thinks longer and is slower (default: Claude Code's current setting) |
| `--model <model>` | Claude model (default: Claude Code's current setting) |
| `--dry-run` | Show what would run, without transcribing or calling Claude |

### Polish only

```bash
heardmd polish ~/recordings/2026-1110_transcript.md --effort high
```

Polishes a raw transcript you already have. It takes the same `--guide`, `--effort`, `--model` and `--dry-run` options as `run`.

Timing on an Apple M4: transcription takes about 1/6 of the recording's length. Polishing a 43-minute meeting took about 4 minutes at `medium` effort and about 11 minutes at `xhigh`. The Mac is kept from idle-sleeping while a command runs (released when it ends), but **closing the lid still puts it to sleep**; keep it open for long files.

The full log of each polish run is saved in `cache/logs/`.

#### What Claude can touch

While polishing, Claude Code runs in `dontAsk` mode: anything not allowed in advance is refused.

- **Read only**: the private guide's `read_dirs`, the raw transcript's folder and the output folder.
- **Write only**: this run's output file, one file.
- Only the file tools (read, search, write) are available. Bash, web access, subagents and MCP servers are not.

### Agent guides: general and private

These files are instructions for Claude, not documentation for you.

| File | Contents | In git |
|---|---|---|
| `agent-guides/general.md` | Rules for every recording: removing fillers, punctuation, handling recognition errors (fix only when sure; keep the original words next to guesses), fixing speaker turns, output format, Chinese- and English-specific details | ✅ |
| `agent-guides/private/<name>.md` | This kind of meeting's speaker roles, background material and spellings. Wins where it disagrees with the general guide | ❌ (in `.gitignore`) |

Create a private guide:

```bash
mkdir -p agent-guides/private
cp agent-guides/private.example.md agent-guides/private/weekly.md
```

The block between the `---` lines holds settings read by heardmd; the rest is plain-language guidance for Claude, in any language (Claude reports back in that language):

```yaml
---
output_dir: ~/Documents/meetings/polished   # where polished transcripts go (default: next to the transcript)
read_dirs:                                   # background material Claude may read
  - ~/Documents/meetings/notes
speakers: 2                                  # number of speakers when transcribing
language: en                                 # language of the recordings: zh or en
---
```

Write one per kind of meeting (weekly sync, interviews, lectures…) and switch with `--guide`. Run `heardmd doctor` afterwards to check the settings.

---

## Raw transcript format

```markdown
**SPEAKER_00** [00:00:00]
So, um, thanks for joining. I wanted to, uh, check on the migration…

**SPEAKER_01** [00:00:08]
Yeah, so, um, we moved the billing service last week…
```

- Speakers are numbered in the order they first speak; no names are guessed.
- Timestamps are times in the source file (also with `--start`). A run of speech by one speaker has a single start time.
- Within a turn, a new paragraph starts at a whisper segment after a pause of 3 seconds or more, or after about 200 Chinese characters (about 600 characters in English).

## How it works

1. ffmpeg converts the input to 16 kHz mono wav in `cache/tmp/`, deleted afterwards (also when interrupted; leftovers older than a day are cleaned up on the next run).
2. whisper.cpp transcribes in the chosen language, with times for every segment and word.
3. pyannote works out who is speaking when.
4. Merging: if a whisper segment contains a change of speaker, it is split only at **punctuation** or at whisper's " - " turn marker, and each clause goes to the speaker with the most overlap. The pieces must join back to the exact original text, otherwise the segment is kept whole.
5. Chinese only: OpenCC converts any remaining Simplified characters. Whisper already writes Traditional characters, but OpenCC would also "convert" characters that are valid in Traditional Chinese, turning 「只是」 into 「隻是」 and 「干擾」 into 「幹擾」. The 203 characters in [`data/opencc_keep.txt`](data/opencc_keep.txt) are therefore kept as whisper wrote them; [`data/make_opencc_keep.py`](data/make_opencc_keep.py) regenerates the list from OpenCC's dictionary.

### A change to pyannote

pyannote treats any cluster of at least 12 voice embeddings as a speaker, regardless of the recording's length, and it also computes embeddings for tiny slivers of sound. In an 88-minute meeting (7,834 embeddings), 50 came from such slivers; they resembled each other and neither real speaker, so they formed a "speaker" of their own. With 2 speakers requested, pyannote then had to merge the two real speakers into one.

heardmd changes the threshold to "at least 1% of all embeddings" (short recordings keep 12). The trade-off: in a long recording, someone who speaks for less than about 1% of the time is merged into another speaker.

### Known limitations

- One language per recording. English terms inside Chinese speech are fine, but if the conversation switches language for a whole stretch, whisper (which detects the language only once, at the start) transcribes that stretch poorly.
- Very short interjections such as "mm" or 「對」 are often missed or merged into the main speaker's sentence.
- Whisper sometimes produces a 30-second segment spanning two speakers that can only be split at punctuation or " - ", so a change of speaker may be off by a sentence or two.
- Proper nouns may be misheard. The raw transcript never corrects them; that is the polishing step's job.
- Polishing fixes errors it is sure about without marking them, and occasionally it is too sure; the polished text will not show this. Check important passages against the raw transcript or the recording.

---

## Folder layout

```
bin/heardmd             the only command (run, transcribe, polish, doctor, login)
src/
  transcribe.py         transcription
  polish.py             polishing: combines the guides, sets permissions, runs claude -p
  doctor.py             checks the installation and setup
data/
  opencc_keep.txt       characters OpenCC must not convert
  make_opencc_keep.py   regenerates that list from OpenCC's dictionary
agent-guides/
  general.md            general polishing rules for Claude
  private.example.md    template for a private guide
  private/              your private guides (not in git)
install.sh              installer
env.sh                  points every cache at this folder
pyproject.toml, uv.lock
```

Created by `install.sh` (none of it is in git):

| Path | Size | Contents |
|---|---|---|
| `models/` | 1.6 GB | Whisper model |
| `.venv/` | about 850 MB | Python environment (PyTorch, pyannote, OpenCC, ffmpeg) |
| `vendor/whisper.cpp/` | about 100 MB | whisper.cpp source and the built `whisper-cli` |
| `.tools/` | about 100 MB | uv and Python 3.12 |
| `cache/` | about 60 MB | pyannote models, the Hugging Face token, polish logs, temporary files |

`env.sh` points the caches of uv, Python, Hugging Face, pyannote, PyTorch and matplotlib at `cache/`; `bin/heardmd` loads it on every run.

---

## Uninstall

```bash
rm -rf ~/tools/heardmd
```

Transcripts and polished transcripts are next to the recordings or in your `output_dir`, and are not deleted.

Things that may remain outside the folder:

| Where | How to remove |
|---|---|
| Your token on the Hugging Face site | Delete it under [Access Tokens](https://huggingface.co/settings/tokens) |
| Accepted terms of the pyannote models | Nothing to do; to withdraw, see [Gated repos](https://huggingface.co/settings/gated-repos) |
| An alias you added to `~/.zshrc` | Delete that line |

heardmd installs no Homebrew packages or system Python packages and does not change your shell configuration.

---

## Tech stack

| Area | Tools |
|---|---|
| Speech recognition | [whisper.cpp](https://github.com/ggml-org/whisper.cpp) v1.9.5, `large-v3-turbo` model, Metal |
| Speaker identification | [pyannote.audio](https://github.com/pyannote/pyannote-audio) 3.3.2, `speaker-diarization-3.1`, PyTorch (MPS) |
| Chinese script conversion | [OpenCC](https://github.com/BYVoid/OpenCC) 1.4.2 |
| Audio and video decoding | ffmpeg (via imageio-ffmpeg) |
| Transcript polishing | [Claude Code](https://claude.com/claude-code), headless (`claude -p`) |
| Environment | [uv](https://github.com/astral-sh/uv), Python 3.12 |
| Tooling | Development accelerated by Claude (Claude Code) |

---

## License

heardmd is released under the [MIT License](LICENSE).

- [`data/opencc_keep.txt`](data/opencc_keep.txt) is derived from the [OpenCC](https://github.com/BYVoid/OpenCC) dictionary (Apache License 2.0).
- whisper.cpp (MIT), the Whisper model and the pyannote models are not part of this repository; `install.sh` and pyannote download them, under their own licenses and terms.
