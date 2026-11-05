"""heardmd doctor: check that everything heardmd needs is installed and set up.

Costs no Claude usage and downloads nothing: the Hugging Face check only asks
the API whether the token may access the two gated pyannote models.
"""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from polish import GUIDES, LANGUAGES, PRIVATE, ROOT, expand, parse_guide  # noqa: E402
from transcribe import DIARIZATION_MODEL, WHISPER_CLI, WHISPER_MODEL  # noqa: E402

MODEL_SHA1 = "4af2b29d7ec73d781377bfd1758ca957a807e941"
GATED = ["pyannote/segmentation-3.0", DIARIZATION_MODEL]
problems = 0


def ok(msg):
    print(f"  ✅ {msg}")


def warn(msg, fix=None):
    print(f"  ⚠️  {msg}" + (f"\n      → {fix}" if fix else ""))


def fail(msg, fix):
    global problems
    problems += 1
    print(f"  ❌ {msg}\n      → {fix}")


def section(title):
    print(f"\n{title}")


def check_install():
    section("Transcription")
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        ok("macOS on Apple Silicon")
    else:
        fail(f"This is {platform.system()} {platform.machine()}",
             "heardmd currently supports only macOS on Apple Silicon")
    if WHISPER_CLI.exists():
        ok("whisper.cpp is built")
    else:
        fail("whisper-cli not found", "run ./install.sh")
    if not WHISPER_MODEL.exists():
        fail("Whisper model not found", "run ./install.sh")
    else:
        h = hashlib.sha1()
        with WHISPER_MODEL.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 24), b""):
                h.update(chunk)
        if h.hexdigest() == MODEL_SHA1:
            ok("Whisper model is intact (SHA1 matches)")
        else:
            fail("Whisper model SHA1 does not match; the file may be damaged",
                 f"delete {WHISPER_MODEL} and run ./install.sh")
    missing = []
    warnings.filterwarnings("ignore")
    for mod in ("torch", "pyannote.audio", "opencc", "imageio_ffmpeg", "soundfile", "yaml"):
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    if missing:
        fail("Missing Python packages: " + ", ".join(missing), "run ./install.sh")
    else:
        ok("Python packages are installed")


def check_huggingface():
    section("Hugging Face (speaker identification models)")
    from huggingface_hub import auth_check, constants

    if not Path(constants.HF_TOKEN_PATH).is_file():
        fail("No token set", "create a Read token as described in README "
                             "(Set up Hugging Face), then run heardmd login")
        return
    ok("Token is set")
    for repo in GATED:
        try:
            auth_check(repo)
            ok(f"Can access {repo}")
        except Exception as e:
            name = type(e).__name__
            if "Gated" in name:
                fail(f"The terms of {repo} have not been accepted",
                     f"log in and accept them at https://huggingface.co/{repo}")
            elif "Repository" in name or "401" in str(e):
                fail(f"The token cannot access {repo} (it may have been revoked)",
                     "create a new Read token and run heardmd login")
            else:
                warn(f"Could not check {repo} ({name}; offline?)",
                     "transcription still works if the models were downloaded before")


def check_claude():
    section("Claude Code (for polishing; not needed to transcribe)")
    claude = shutil.which("claude")
    if not claude:
        warn("The claude command was not found, so heardmd run and heardmd polish cannot work",
             "install and log in as described in README (Set up Claude Code)")
        return
    ok(f"Installed: {claude}")
    try:
        r = subprocess.run([claude, "auth", "status"], capture_output=True, text=True, timeout=30)
        status = json.loads(r.stdout)
    except Exception:
        warn("Could not check the login status", "run claude auth status")
        return
    if status.get("loggedIn"):
        ok(f"Logged in ({status.get('authMethod', '?')})")
    else:
        fail("Claude Code is not logged in", "run claude in a terminal and follow the login steps")


def check_guides():
    section("Agent guides")
    if (GUIDES / "general.md").is_file():
        ok("General guide: agent-guides/general.md")
    else:
        fail("agent-guides/general.md not found", "download the project again")
    found = sorted(PRIVATE.glob("*.md"))
    if not found:
        warn("No private guide yet: polishing keeps SPEAKER labels and reads no background material",
             "cp agent-guides/private.example.md agent-guides/private/<name>.md, then edit it")
        return
    for p in found:
        try:
            settings, _ = parse_guide(p)
        except ValueError as e:
            fail(str(e), "fix the settings block between the --- lines")
            continue
        lang = settings.get("language", "zh")
        if lang not in LANGUAGES:  # heardmd run/polish refuse to use this guide
            fail(f"Private guide '{p.stem}': language must be {' or '.join(LANGUAGES)}, not {lang}",
                 "fix language in the settings block")
            continue
        issues = []
        out_dir = settings.get("output_dir")
        if out_dir and not expand(out_dir).is_dir():
            issues.append(f"output_dir does not exist: {out_dir} (output will go next to the transcript)")
        for d in settings.get("read_dirs") or []:
            if not expand(d).is_dir():
                issues.append(f"a read_dirs folder does not exist: {d}")
        spk = settings.get("speakers")
        if spk is not None and not (isinstance(spk, int) and spk > 0):
            issues.append(f"speakers should be a positive whole number, not {spk}")
        if issues:
            warn(f"Private guide '{p.stem}': " + "; ".join(issues))
        else:
            ok(f"Private guide '{p.stem}' (language {lang})")
    if len(found) > 1:
        print("      There are several private guides; choose one with --guide")


def main():
    print(f"heardmd doctor ({ROOT})")
    check_install()
    check_huggingface()
    check_claude()
    check_guides()
    print()
    if problems:
        print(f"{problems} problem(s) to fix; see the → lines above.")
        sys.exit(1)
    print("All good.")


if __name__ == "__main__":
    os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
    main()
