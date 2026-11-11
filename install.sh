#!/bin/bash
# heardmd setup: uv, Python 3.12, packages, whisper.cpp and the Whisper model,
# all inside this folder.
# Safe to re-run: finished steps are skipped. Usage: ./install.sh [--yes]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
YES=0; [[ "${1:-}" == "--yes" ]] && YES=1

WHISPER_TAG=v1.9.5   # 2026-11-03 master failed to compile Metal shaders on macOS 15
MODEL=models/ggml-large-v3-turbo.bin
MODEL_URL=https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin
MODEL_SHA1=4af2b29d7ec73d781377bfd1758ca957a807e941

step() { printf '\n== %s\n' "$1"; }
confirm() {  # confirm "<question>"
  [[ $YES == 1 ]] && return 0
  read -r -p "$1 [y/N] " a; [[ "$a" == [yY]* ]]
}

[[ "$(uname -s)-$(uname -m)" == "Darwin-arm64" ]] || { echo "heardmd currently supports only macOS on Apple Silicon"; exit 1; }
for c in git curl xcrun; do
  command -v $c >/dev/null || { echo "$c is missing. Install the Xcode Command Line Tools first: xcode-select --install"; exit 1; }
done

step "1/5 uv (package manager, about 30 MB, in .tools/bin)"
if [[ -x .tools/bin/uv ]]; then
  echo "Already installed, skipping"
else
  receipt="$HOME/.config/uv/uv-receipt.json"; had_receipt=0; [[ -e "$receipt" ]] && had_receipt=1
  curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR="$ROOT/.tools/bin" UV_NO_MODIFY_PATH=1 sh
  # The installer leaves a receipt outside this folder; remove it unless it was already there.
  [[ $had_receipt == 0 ]] && rm -f "$receipt" && rmdir "$HOME/.config/uv" 2>/dev/null || true
fi

source "$ROOT/env.sh"

step "2/5 Python 3.12 and packages (about 900 MB: PyTorch, pyannote, OpenCC, ffmpeg)"
uv python install 3.12 --no-bin   # --no-bin: don't add python3.12 to ~/.local/bin
uv sync --frozen

step "3/5 whisper.cpp $WHISPER_TAG (about 100 MB of source; builds whisper-cli locally)"
if [[ -x vendor/whisper.cpp/build/bin/whisper-cli ]]; then
  echo "Already built, skipping"
else
  [[ -d vendor/whisper.cpp ]] || git clone --depth 1 --branch "$WHISPER_TAG" https://github.com/ggml-org/whisper.cpp vendor/whisper.cpp
  # cmake is only needed to build; uvx runs it temporarily (cached under cache/).
  uvx cmake -S vendor/whisper.cpp -B vendor/whisper.cpp/build \
    -DCMAKE_C_COMPILER="$(xcrun --find clang)" -DCMAKE_CXX_COMPILER="$(xcrun --find clang++)" \
    -DCMAKE_OSX_SYSROOT="$(xcrun --show-sdk-path)" -DCMAKE_BUILD_TYPE=Release \
    -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DBUILD_SHARED_LIBS=OFF -DWHISPER_SDL2=OFF
  uvx cmake --build vendor/whisper.cpp/build -j --target whisper-cli
fi

step "4/5 Whisper model large-v3-turbo (1.6 GB)"
if [[ -f "$MODEL" ]]; then
  echo "Already downloaded, skipping"
else
  confirm "Download the 1.6 GB Whisper model?" || { echo "Cancelled. Run ./install.sh again to continue."; exit 1; }
  mkdir -p models
  curl -L --fail -o "$MODEL.part" "$MODEL_URL" && mv "$MODEL.part" "$MODEL"
fi
echo "Checking the model…"
[[ "$(shasum -a 1 "$MODEL" | cut -d' ' -f1)" == "$MODEL_SHA1" ]] || { echo "Model SHA1 mismatch: delete $MODEL and run again"; exit 1; }
echo "SHA1 OK"

step "5/5 Hugging Face token (needed by the speaker identification models)"
if [[ -s cache/hf/token ]]; then
  echo "Already set, skipping"
else
  cat <<'MSG'
Not set yet. Please:
  1. Log in at https://huggingface.co and accept the terms on both pages:
     https://huggingface.co/pyannote/segmentation-3.0
     https://huggingface.co/pyannote/speaker-diarization-3.1
  2. Create a token of type Read at https://huggingface.co/settings/tokens and copy it
  3. Run bin/heardmd login and paste the token
MSG
fi

step "Check (heardmd doctor)"
bin/heardmd doctor || true

if ! ls agent-guides/private/*.md >/dev/null 2>&1; then
  cat <<'MSG'

To use polishing, also create a private guide (speaker roles, background material,
where to save the output):
  mkdir -p agent-guides/private && cp agent-guides/private.example.md agent-guides/private/<name>.md
then edit it as the file explains.
MSG
fi
# install.sh never edits shell configuration (deleting this folder must remove
# everything), so print the alias line for this folder instead.
alias_line="alias heardmd=\"$ROOT/bin/heardmd\""
existing="$(grep '^alias heardmd=' "$HOME/.zshrc" 2>/dev/null || true)"
if [[ -n "$existing" ]]; then
  cat <<MSG

~/.zshrc already has a heardmd alias:
$existing
If it does not point to this folder ($ROOT), replace it with:
  $alias_line
MSG
else
  cat <<MSG

To type just heardmd instead of $ROOT/bin/heardmd,
add an alias to ~/.zshrc (this line is for this folder), then open a new terminal window:
  echo '$alias_line' >> ~/.zshrc
MSG
fi
printf '\nDone. See README.md, or run bin/heardmd help.\n'
