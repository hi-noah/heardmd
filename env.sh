# Keep every tool's data inside this folder. Sourced by bin/heardmd and install.sh.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
export UV_CACHE_DIR="$ROOT/cache/uv"
export UV_PYTHON_INSTALL_DIR="$ROOT/.tools/python"
export UV_PYTHON_PREFERENCE=only-managed
export UV_PROJECT_ENVIRONMENT="$ROOT/.venv"
export UV_TOOL_DIR="$ROOT/cache/uv-tools"
export XDG_CACHE_HOME="$ROOT/cache"
export HF_HOME="$ROOT/cache/hf"
export TORCH_HOME="$ROOT/cache/torch"
export PYANNOTE_CACHE="$ROOT/cache/pyannote"
export MPLCONFIGDIR="$ROOT/cache/matplotlib"
export PYTHONPYCACHEPREFIX="$ROOT/cache/pycache"
export HF_HUB_DISABLE_TELEMETRY=1
export PATH="$ROOT/bin:$ROOT/.tools/bin:$PATH"
