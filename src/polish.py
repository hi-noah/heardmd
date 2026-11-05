"""heardmd run / heardmd polish: have Claude Code polish a transcript unattended,
following agent-guides/general.md plus a private guide.

  heardmd run <recording>      transcribe first (unless a transcript exists), then polish
  heardmd polish <transcript>  polish an existing *_transcript.md only

Claude runs headless (`claude -p`) in "dontAsk" permission mode, so anything not
explicitly allowed below is refused instead of prompting:
  - reads:  only the private guide's read_dirs, the transcript's folder and the
            output folder (passed as --add-dir / working directory)
  - writes: only the one output file (an Edit(<path>) rule covers Write and Edit)
  - only the Read, Grep, Glob, Write and Edit tools exist; Bash, web access,
    subagents and MCP servers are not available.
"""
import argparse
import datetime
import json
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GUIDES = ROOT / "agent-guides"
PRIVATE = GUIDES / "private"
LOG_DIR = ROOT / "cache" / "logs"
LANGUAGES = {"zh": "Chinese", "en": "English"}
EFFORTS = ["low", "medium", "high", "xhigh", "max"]


def die(msg):
    sys.exit(f"Error: {msg}")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_guide(arg):
    """Return (path, settings dict, body text) of the private guide, or (None, {}, "")."""
    if arg:
        p = Path(arg).expanduser()
        if not p.is_file():
            p = PRIVATE / f"{arg.removesuffix('.md')}.md"
        if not p.is_file():
            names = ", ".join(sorted(f.stem for f in PRIVATE.glob("*.md"))) or "(none)"
            die(f"No private guide named '{arg}'. agent-guides/private/ has: {names}")
    else:
        found = sorted(PRIVATE.glob("*.md"))
        if len(found) > 1:
            die("agent-guides/private/ has several guides; choose one with --guide: "
                + ", ".join(f.stem for f in found))
        if not found:
            log("No private guide: using the general guide only (speakers keep their "
                "SPEAKER labels; output goes next to the transcript)")
            return None, {}, ""
        p = found[0]
    try:
        settings, body = parse_guide(p)
    except ValueError as e:
        die(str(e))
    return p.resolve(), settings, body


def parse_guide(path):
    """Split a private guide into (settings from the --- block, body text).
    Raises ValueError when the settings block is not valid YAML."""
    text = Path(path).read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return {}, text.strip()
    try:
        settings = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"The settings block at the top of {path} is not valid YAML: {e}") from e
    if not isinstance(settings, dict):
        raise ValueError(f"The settings block at the top of {path} should be 'name: value' lines")
    return settings, text[m.end():].strip()


def header_field(transcript, *names):
    """A field from a transcript's header ("- Language: en"); older transcripts
    use Chinese field names ("- 語言：en")."""
    head = transcript.read_text(encoding="utf-8")[:2000]
    for name in names:
        m = re.search(rf"^- {name}[:：]\s*(.+)$", head, re.M)
        if m:
            return m.group(1).strip()
    return None


def resolve_transcript(src, speakers, language):
    """Return (transcript, recording or None, stem). Runs transcribe if needed."""
    if src.suffix.lower() == ".md":
        stem = src.stem.removesuffix("_transcript")
        source = header_field(src, "Source", "原始檔案")
        return src, (Path(source.strip("`")) if source else None), stem
    transcript = src.with_name(f"{src.stem}_transcript.md")
    if transcript.exists():
        log(f"Using the existing transcript: {transcript.name}")
    else:
        # Same interpreter and environment; `heardmd run` already keeps the Mac awake.
        cmd = [sys.executable, str(ROOT / "src/transcribe.py"), str(src), "-l", language]
        if speakers:
            cmd += ["-n", str(speakers)]
        log("Transcribing first (about 1/6 of the recording's length; keep the lid open)")
        if subprocess.run(cmd).returncode != 0 or not transcript.exists():
            die("Transcription failed; nothing was polished")
    return transcript, src, src.stem


def free_output_path(folder, stem):
    out = folder / f"{stem}_polished.md"
    n = 2
    while out.exists():  # never overwrite an earlier polish
        out = folder / f"{stem}_polished-{n}.md"
        n += 1
    return out


def describe(tool, inp, out):
    """One short progress line for a tool call."""
    path = inp.get("file_path", "")
    if tool == "Read":
        return f"read {Path(path).name}"
    if tool == "Write":
        return "created the output file" if path == str(out) else f"tried to write {path}"
    if tool == "Edit":
        return "wrote polished text" if path == str(out) else f"tried to edit {path}"
    if tool == "Grep":
        return f"searched for '{inp.get('pattern', '')}'"
    if tool == "Glob":
        return f"listed files {inp.get('pattern', '')}"
    return f"used {tool}"


def main():
    # bin/heardmd passes the subcommand first: "run" or "polish".
    mode = sys.argv.pop(1) if len(sys.argv) > 1 and sys.argv[1] in ("run", "polish") else "run"
    if mode == "run":
        p = argparse.ArgumentParser(
            prog="heardmd run",
            description="Full pipeline: transcribe the recording (skipped if its transcript "
                        "already exists), then have Claude Code polish the transcript.")
        p.add_argument("input", help="audio or video file (m4a, mp3, wav, mp4, mov, ...)")
        p.add_argument("-n", "--speakers", type=int,
                       help="number of speakers (default: the private guide's speakers, else 2)")
        p.add_argument("-l", "--language", choices=sorted(LANGUAGES),
                       help="language of the recording (default: the private guide's language, else zh)")
    else:
        p = argparse.ArgumentParser(
            prog="heardmd polish",
            description="Have Claude Code polish an existing raw transcript. "
                        "To transcribe and polish a recording, use heardmd run.")
        p.add_argument("input", help="raw transcript (*_transcript.md)")
        p.set_defaults(speakers=None, language=None)
    p.add_argument("-g", "--guide", help="private guide name (agent-guides/private/<name>.md) or path")
    p.add_argument("--model", help="Claude model (default: Claude Code's current setting)")
    p.add_argument("--effort", choices=EFFORTS,
                   help="Claude's reasoning effort; higher thinks longer and is slower "
                        "(default: Claude Code's current setting)")
    p.add_argument("--dry-run", action="store_true",
                   help="show what would run, without transcribing or calling Claude")
    args = p.parse_args()

    claude = shutil.which("claude")
    if not claude and not args.dry_run:
        die("The claude command was not found. Install Claude Code and log in "
            "(see README), then check with heardmd doctor.")

    src = expand(args.input)
    if not src.is_file():
        die(f"File not found: {src}")
    is_transcript = src.suffix.lower() == ".md"
    if mode == "polish" and not is_transcript:
        die(f"{src.name} is a recording. heardmd polish takes a *_transcript.md; "
            f"to transcribe and polish in one go, use: heardmd run {args.input}")
    if mode == "run" and is_transcript:
        die(f"{src.name} is a transcript. heardmd run takes a recording; "
            f"to polish this transcript, use: heardmd polish {args.input}")
    guide_path, settings, guide_body = load_guide(args.guide)
    speakers = args.speakers or settings.get("speakers")
    language = args.language or settings.get("language") or "zh"
    if language not in LANGUAGES:
        die(f"The private guide's language is '{language}'; supported: {', '.join(LANGUAGES)}")

    if args.dry_run and not is_transcript:
        transcript = src.with_name(f"{src.stem}_transcript.md")
        recording, stem = src, src.stem
    else:
        transcript, recording, stem = resolve_transcript(src, speakers, language)
    if transcript.exists():  # the transcript's own header is the final word
        language = header_field(transcript, "Language", "語言") or "zh"

    out_dir = expand(settings["output_dir"]) if settings.get("output_dir") else transcript.parent
    if not out_dir.is_dir():
        log(f"output_dir does not exist: {out_dir}; writing next to the transcript instead")
        out_dir = transcript.parent
    out = free_output_path(out_dir, stem)

    read_dirs = []
    for d in [*(settings.get("read_dirs") or []), transcript.parent]:
        d = expand(d)
        if not d.is_dir():
            log(f"Skipping a folder that does not exist: {d}")
        elif d not in read_dirs and d != out_dir:
            read_dirs.append(d)

    system = (GUIDES / "general.md").read_text(encoding="utf-8")
    if guide_body:
        system += ("\n\n# Private guide (wins where it disagrees with the general guide above)\n\n"
                   + guide_body)

    prompt = "\n".join([
        "Polish this raw transcript following the general guide and the private guide "
        "in the system prompt.",
        f"- Raw transcript: {transcript}",
        f"- Recording: {recording or '(unknown)'}",
        f"- File name (often contains the meeting date): {stem}",
        f"- Transcript language: {language} ({LANGUAGES.get(language, language)})",
        f"- Today: {datetime.date.today().isoformat()}",
        f"- Output file: {out} (does not exist yet; it is the only file you may write)",
        "- This is an unattended run: nobody can answer questions or grant more permissions. "
        "Skip any file you are not allowed to read, decide by the guides, and explain "
        "your decisions in the final report.",
    ])

    cmd = [claude or "claude", "-p", prompt,
           "--append-system-prompt", system,
           # Only file tools exist in the session (no web, subagents, Bash, ...).
           "--tools", "Read,Grep,Glob,Write,Edit",
           "--permission-mode", "dontAsk",
           # A leading // marks an absolute path in permission rules.
           "--allowedTools", f"Edit(/{out})",
           "--disallowedTools", "Bash",
           "--strict-mcp-config",
           "--no-session-persistence",
           "--output-format", "stream-json", "--verbose"]
    for d in read_dirs:
        cmd += ["--add-dir", str(d)]
    if args.model:
        cmd += ["--model", args.model]
    if args.effort:
        cmd += ["--effort", args.effort]

    log(f"Private guide: {guide_path or '(none)'}")
    log(f"Transcript: {transcript} (language: {language})")
    log(f"Effort: {args.effort or 'Claude Code default'}")
    log(f"Output: {out}")
    log("Claude may read: " + ", ".join(str(d) for d in [out_dir, *read_dirs]))
    if args.dry_run:
        print("\n--- command (prompt and system prompt omitted) ---")
        print(" ".join(a if a not in (prompt, system) else "<…>" for a in cmd))
        print("\n--- prompt ---\n" + prompt)
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{stem}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    log(f"Polishing (an hour-long meeting takes about 5–15 minutes, depending on effort). "
        f"Full log: {log_path}")
    t0 = time.time()
    result, denied, batches = None, 0, 0
    # stdin=DEVNULL: otherwise claude -p waits 3 s for piped input before starting.
    proc = subprocess.Popen(cmd, cwd=out_dir, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
    try:
        with log_path.open("w", encoding="utf-8") as f:
            for line in proc.stdout:
                f.write(line)
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    print(line, end="")  # CLI errors are plain text
                    continue
                if ev.get("type") == "result":
                    result = ev
                for c in (ev.get("message") or {}).get("content") or []:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use":
                        if c["name"] == "Edit" and c["input"].get("file_path") == str(out):
                            batches += 1
                        log(f"  {describe(c['name'], c['input'], out)}")
                    elif c.get("type") == "tool_result" and "denied" in str(c.get("content", "")):
                        denied += 1
                        log("  (permission denied)")
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        die(f"Interrupted. Partial output, if any: {out}")
    finally:
        if proc.poll() is None:
            proc.terminate()

    mins = (time.time() - t0) / 60
    print()
    if result and result.get("result"):
        print(result["result"].strip())
        print()
    if not out.exists() or out.stat().st_size == 0:
        die(f"No polished transcript was written ({mins:.1f} min). See the log: {log_path}")
    if result is None or result.get("is_error"):
        log(f"Claude reported an error; the polished transcript may be incomplete: {out}")
    usage = (result or {}).get("usage") or {}
    tokens = sum(usage.get(k, 0) for k in ("input_tokens", "output_tokens",
                                           "cache_creation_input_tokens", "cache_read_input_tokens"))
    log(f"Done in {mins:.1f} min ({batches} appends, {denied} permission denials, "
        f"about {tokens:,} tokens): {out}")
    sys.exit(0 if result and not result.get("is_error") else 1)


def expand(p):
    return Path(str(p)).expanduser().resolve()


if __name__ == "__main__":
    main()
