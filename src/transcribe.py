"""Local meeting transcriber: whisper.cpp (large-v3-turbo) + pyannote diarization.

Usage: heardmd transcribe <audio or video file> [--language zh|en] [--speakers N]
                          [--start SEC --duration SEC] [--output PATH]
"""

import argparse
import datetime as dt
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WHISPER_CLI = ROOT / "vendor/whisper.cpp/build/bin/whisper-cli"
WHISPER_MODEL = ROOT / "models/ggml-large-v3-turbo.bin"
DIARIZATION_MODEL = "pyannote/speaker-diarization-3.1"
# Formats verified to decode with the bundled ffmpeg (audio and video containers).
SUPPORTED = {".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".opus", ".aiff",
             ".mp4", ".mov", ".mkv", ".webm"}
# Per transcript language: Whisper's initial prompt (for zh it nudges Whisper
# toward Traditional characters; OpenCC below guarantees it) and the paragraph
# length that starts a new paragraph (CJK characters carry more per character).
LANGUAGES = {
    "zh": {"prompt": "以下是繁體中文的會議逐字稿。", "paragraph_chars": 200},
    "en": {"prompt": "The following is a transcript of a meeting.", "paragraph_chars": 600},
}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def fmt_ts(sec, ms=False):
    sec = max(sec, 0.0)
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    base = f"{h:02d}:{m:02d}:{s:02d}"
    return f"{base}.{int((sec % 1) * 10)}" if ms else base


def ffmpeg_exe():
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def to_wav(src, dst, start=None, duration=None):
    cmd = [ffmpeg_exe(), "-nostdin", "-hide_banner", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", str(start)]
    cmd += ["-i", str(src)]
    if duration is not None:
        cmd += ["-t", str(duration)]
    cmd += ["-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-y", str(dst)]
    subprocess.run(cmd, check=True)


def transcribe(wav, out_base, threads, language):
    cmd = [
        str(WHISPER_CLI),
        "-m", str(WHISPER_MODEL),
        "-f", str(wav),
        "-l", language,
        "-t", str(threads),
        "--prompt", LANGUAGES[language]["prompt"],
        # Full JSON includes per-token timestamps, used to split a segment where
        # the speaker changes. (DTW timestamps would need -nfa, which made the
        # transcript noticeably worse: dropped sentences, repetition loops.)
        "-ojf",
        "-of", str(out_base),
        "-np",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Tokens can hold partial UTF-8 sequences; surrogateescape keeps the raw
    # bytes so they can be rejoined losslessly.
    raw = Path(f"{out_base}.json").read_bytes().decode("utf-8", "surrogateescape")
    data = json.loads(raw)
    segments = []
    for seg in data.get("transcription", []):
        start, end = seg["offsets"]["from"] / 1000, seg["offsets"]["to"] / 1000
        tokens = []
        for tok in seg.get("tokens", []):
            if tok["text"].startswith("[_"):
                continue
            clamp = lambda x: min(max(x, start), end)
            tokens.append({"bytes": tok["text"].encode("utf-8", "surrogateescape"),
                           "from": clamp(tok["offsets"]["from"] / 1000),
                           "to": clamp(tok["offsets"]["to"] / 1000)})
        text = seg["text"].encode("utf-8", "surrogateescape").decode("utf-8", "replace").strip()
        if text:
            segments.append({"start": start, "end": end, "text": text, "tokens": tokens})
    return segments


def diarize(wav, num_speakers, min_speakers, max_speakers):
    warnings.filterwarnings("ignore")
    # pyannote 3.3 checkpoints (official pyannote repos) predate torch>=2.6's
    # weights_only default and need full unpickling to load.
    os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
    import soundfile as sf
    import torch
    from pyannote.audio import Pipeline

    try:
        pipeline = Pipeline.from_pretrained(DIARIZATION_MODEL)
    except Exception as e:
        hint = ""
        if any(k in str(e) for k in ("gated", "401", "403", "token", "authorized")):
            hint = (
                "\nAccept the terms of pyannote/segmentation-3.0 and "
                "pyannote/speaker-diarization-3.1 on Hugging Face, then run `heardmd login` "
                "with a Read token. `heardmd doctor` checks this."
            )
        sys.exit(f"Could not load {DIARIZATION_MODEL}: {e}{hint}")
    if pipeline is None:
        sys.exit("Could not load the diarization model (invalid token, or the model terms "
                 "were not accepted). Run `heardmd doctor`.")
    if torch.backends.mps.is_available():
        pipeline.to(torch.device("mps"))

    audio, sr = sf.read(str(wav), dtype="float32")
    file = {"waveform": torch.from_numpy(audio).unsqueeze(0), "sample_rate": sr}
    _tune_clustering(pipeline)
    if min_speakers or max_speakers:
        annotation = pipeline(file, min_speakers=min_speakers, max_speakers=max_speakers)
    else:
        annotation = pipeline(file, num_speakers=num_speakers)
    turns = [(t.start, t.end, lab) for t, _, lab in annotation.itertracks(yield_label=True)]
    # Renumber labels by first appearance so SPEAKER_00 is whoever speaks first.
    order = {}
    for _, _, label in sorted(turns):
        order.setdefault(label, f"SPEAKER_{len(order):02d}")
    return [(s, e, order[label]) for s, e, label in turns]


MIN_SPEAKER_SHARE = 0.01  # a cluster needs >= 1% of the embeddings to count as a speaker


def _tune_clustering(pipeline):
    """Keep slivers of speech from merging two real speakers.

    pyannote embeds every local speaker that is active for even a few frames
    of a 10 s chunk. Embeddings of such slivers are alike and far from every
    real voice, so they can form a cluster of their own. When that gives more
    clusters than the speakers requested, pyannote walks its dendrogram until
    the count fits, which merges the two closest clusters: the real speakers.

    - 88-min meeting (7834 embeddings): 50 sliver embeddings (median 0.03 s of
      speech, vs ~9-10 s for real speech) formed a cluster; the real speakers
      were 0.39 apart (cosine), the slivers 1.16-1.21 from both.
    - 122-min meeting (11003 embeddings): 111 sliver embeddings (median
      0.44 s), 1.01% of all, formed a cluster; the real speakers (5362 and
      2172 embeddings, 0.38 apart) were merged into one label.

    Two changes:
    1. A cluster needs MIN_SPEAKER_SHARE of the embeddings to count as a
       speaker (pyannote's fixed default is 12 however long the recording).
       Short files keep the default of 12.
    2. If there are still more speakers than requested, keep the largest
       clusters and reassign the smallest ones to their nearest kept speaker,
       instead of merging speakers. With fewer speakers than requested,
       pyannote's own search runs unchanged.
    """
    import numpy as np
    from scipy.spatial.distance import cdist

    clustering = pipeline.clustering
    default = clustering.min_cluster_size
    original = clustering.cluster

    def cluster(embeddings, min_clusters, max_clusters, num_clusters=None):
        clustering.min_cluster_size = max(default, round(MIN_SPEAKER_SHARE * len(embeddings)))
        wanted_max = num_clusters or max_clusters
        # Clusters at pyannote's distance threshold, small ones already reassigned.
        labels = original(embeddings.copy(), 1, max(len(embeddings), 1), None)
        found = labels.max() + 1
        if found < (num_clusters or min_clusters):
            return original(embeddings, min_clusters, max_clusters, num_clusters)
        if found <= wanted_max:
            return labels
        sizes = np.bincount(labels)
        keep = np.argsort(-sizes)[:wanted_max]
        unit = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        centroids = np.vstack([unit[labels == k].mean(0) for k in keep])
        for k in set(range(found)) - set(keep):
            centroid = unit[labels == k].mean(0, keepdims=True)
            labels[labels == k] = keep[np.argmin(cdist(centroid, centroids, "cosine"))]
        return np.unique(labels, return_inverse=True)[1]

    clustering.cluster = cluster


def segment_speaker(start, end, turns):
    """Speaker with the most temporal overlap, else the nearest turn."""
    overlap = {}
    for s, e, label in turns:
        o = min(end, e) - max(start, s)
        if o > 0:
            overlap[label] = overlap.get(label, 0) + o
    if overlap:
        return max(overlap, key=overlap.get)
    if turns:
        mid = (start + end) / 2
        return min(turns, key=lambda t: min(abs(mid - t[0]), abs(mid - t[1])))[2]
    return "SPEAKER_UNKNOWN"


CLAUSE_END = tuple("，。？！、；：,.?!;:")
PARAGRAPH_GAP = 3.0  # seconds of silence that start a new paragraph


def _decodes(chunks):
    try:
        b"".join(chunks).decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def split_segment(seg, turns):
    """Split one Whisper segment where the speaker changes.

    Cuts happen only at clause boundaries (after punctuation, or before
    Whisper's " - " turn marker), so words are never broken apart; each clause
    goes to the speaker with the most overlap. Text is only cut, never edited:
    the pieces concatenate back to the original segment.
    """
    tokens = seg["tokens"]
    whole = [{"start": seg["start"], "end": seg["end"], "text": seg["text"],
              "speaker": segment_speaker(seg["start"], seg["end"], turns)}]
    if not tokens:
        return whole

    clauses = [[0, 0]]  # [first_idx, last_idx]
    for i in range(1, len(tokens)):
        prev = tokens[i - 1]["bytes"].decode("utf-8", "ignore").rstrip()
        cur = tokens[i]["bytes"].decode("utf-8", "ignore").lstrip()
        boundary = (prev.endswith(CLAUSE_END) or cur.startswith("-")) and _decodes(
            [t["bytes"] for t in tokens[clauses[-1][0]:i]])
        if boundary:
            clauses.append([i, i])
        else:
            clauses[-1][1] = i

    pieces = []
    for a, b in clauses:
        start = seg["start"] if a == 0 else tokens[a]["from"]
        end = seg["end"] if b == len(tokens) - 1 else tokens[b + 1]["from"]
        label = segment_speaker(start, max(end, start + 0.01), turns)
        if pieces and pieces[-1]["speaker"] == label:
            pieces[-1]["b"], pieces[-1]["end"] = b, end
        else:
            pieces.append({"a": a, "b": b, "start": start, "end": end, "speaker": label})
    for p in pieces:
        p["text"] = b"".join(t["bytes"] for t in tokens[p.pop("a"):p.pop("b") + 1]).decode(
            "utf-8", "replace").strip()
    pieces = [p for p in pieces if p["text"]]

    joined = "".join(p["text"] for p in pieces).replace(" ", "")
    if not pieces or joined != seg["text"].replace(" ", ""):
        return whole  # safety net: fall back to the untouched segment
    return pieces


def assign_speakers(segments, turns):
    out = []
    for seg in segments:
        out.extend(split_segment(seg, turns))
    return out


def to_traditional(segments, config):
    """Convert any Simplified characters to Traditional without touching
    characters that are already valid Traditional.

    Whisper already writes Traditional Chinese here, and OpenCC treats its
    input as Simplified: it turned 「就是只是」 into 「就是隻是」 and 「干擾」 into
    「幹擾」. So any character listed in data/opencc_keep.txt (characters valid in
    both scripts) is kept as whisper wrote it; every other change is applied.
    """
    import opencc

    cc = opencc.OpenCC(config)
    keep_file = ROOT / "data/opencc_keep.txt"
    # One character per line, optionally followed by a note.
    keep = {l[0] for l in keep_file.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")}
    for seg in segments:
        src = seg["text"]
        out = cc.convert(src)
        if len(out) == len(src):  # s2tw maps character for character
            out = "".join(s if s in keep else o for s, o in zip(src, out))
        seg["text"] = out  # s2twp can change length; then use OpenCC as is
    return segments


def render_markdown(src, segments, args, offset, n_found):
    lang = args.language
    lines = [f"# {src.stem} transcript", ""]
    lines.append(f"- Source: `{src}`")
    lines.append(f"- Created: {dt.datetime.now():%Y-%m-%d %H:%M}")
    lines.append(f"- Language: {lang}")
    lines.append("- Transcription: whisper.cpp large-v3-turbo"
                 + (" (OpenCC to Traditional Chinese)" if lang == "zh" else ""))
    if args.min_speakers or args.max_speakers:
        spk = f"{args.min_speakers or '?'}–{args.max_speakers or '?'} speakers"
    else:
        spk = f"{args.speakers} speakers requested"
    lines.append(f"- Diarization: {DIARIZATION_MODEL} ({spk}, {n_found} found)")
    if args.start is not None or args.duration is not None:
        end = f"{fmt_ts(offset + args.duration)}" if args.duration else "end"
        lines.append(f"- Range: {fmt_ts(offset)} – {end} (timestamps are times in the source file)")
    lines += ["- Raw automatic transcript, not edited by hand.", "", "---", ""]

    # One timestamp per speaker turn: consecutive segments of the same speaker
    # are joined (whitespace only, text untouched). Within a turn, a new
    # paragraph starts at a segment boundary after a pause of PARAGRAPH_GAP
    # seconds or once the paragraph reaches the language's paragraph length.
    # Chinese joins without a space after punctuation; English always needs one.
    max_chars = LANGUAGES[lang]["paragraph_chars"]
    turns = []
    for seg in segments:
        if turns and turns[-1]["speaker"] == seg["speaker"]:
            turn = turns[-1]
            if (seg["start"] - turn["end"] >= PARAGRAPH_GAP
                    or len(turn["paras"][-1]) >= max_chars):
                turn["paras"].append(seg["text"])
            else:
                prev = turn["paras"][-1]
                glue = CLAUSE_END + (" ",) if lang == "zh" else (" ",)
                sep = "" if prev.endswith(glue) else " "
                turn["paras"][-1] = prev + sep + seg["text"]
            turn["end"] = seg["end"]
        else:
            turns.append({"speaker": seg["speaker"], "start": seg["start"],
                          "end": seg["end"], "paras": [seg["text"]]})
    for turn in turns:
        lines.append(f"**{turn['speaker']}** [{fmt_ts(turn['start'] + offset)}]")
        lines += [p + "\n" for p in turn["paras"]]
    return "\n".join(lines)


def login():
    from huggingface_hub import login as hf_login

    import getpass

    print("Paste a Hugging Face Read token (input is hidden). "
          "It is stored only in this folder, at cache/hf/token.")
    # Pass the token explicitly: the interactive prompt ignores
    # add_to_git_credential and offers to store it in the macOS Keychain.
    hf_login(token=getpass.getpass("token: ").strip(), add_to_git_credential=False)
    from huggingface_hub import constants

    for f in (constants.HF_TOKEN_PATH, constants.HF_STORED_TOKENS_PATH):
        if os.path.exists(f):
            os.chmod(f, 0o600)  # plain-text token: owner-only


def main():
    p = argparse.ArgumentParser(prog="heardmd transcribe", description="Local transcription with speaker labels (whisper.cpp + pyannote)")
    p.add_argument("input", nargs="?", help="audio or video file (m4a, mp3, wav, mp4, mov, webm, ...)")
    p.add_argument("-l", "--language", choices=sorted(LANGUAGES), default="zh",
                   help="language of the recording: zh = Chinese (default; Traditional output, English terms OK), en = English")
    p.add_argument("-n", "--speakers", type=int, default=2, help="number of speakers (default 2)")
    p.add_argument("--min-speakers", type=int, help="if unsure: minimum number of speakers")
    p.add_argument("--max-speakers", type=int, help="if unsure: maximum number of speakers")
    p.add_argument("--start", type=float, help="start at this second (for trial runs)")
    p.add_argument("--duration", type=float, help="process only this many seconds (for trial runs)")
    p.add_argument("-o", "--output", help="output path (default: <name>_transcript.md next to the input)")
    p.add_argument("--overwrite", action="store_true", help="overwrite an existing output file")
    p.add_argument("--opencc", default="s2tw",
                   help="OpenCC config for Chinese (default s2tw converts characters only; "
                        "s2twp also converts vocabulary to Taiwan usage)")
    p.add_argument("--threads", type=int, default=min(8, os.cpu_count() or 4))
    p.add_argument("--keep-temp", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--login", action="store_true", help="set the Hugging Face token (once)")
    args = p.parse_args()

    if args.login:
        login()
        return
    if not args.input:
        p.error("give a file to transcribe")

    src = Path(args.input).expanduser().resolve()
    if not src.is_file():
        sys.exit(f"File not found: {src}")
    if src.suffix.lower() not in SUPPORTED:
        sys.exit(f"Unsupported format {src.suffix}; supported: {', '.join(sorted(SUPPORTED))}")
    out = Path(args.output).expanduser().resolve() if args.output else src.with_name(f"{src.stem}_transcript.md")
    if out == src:
        sys.exit("The output path must differ from the input file")
    if out.exists() and not args.overwrite:
        sys.exit(f"Output already exists: {out} (add --overwrite to replace it)")
    for f in (WHISPER_CLI, WHISPER_MODEL):
        if not f.exists():
            sys.exit(f"Missing {f}; run ./install.sh")

    tmp_root = ROOT / "cache/tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    for stale in tmp_root.glob("job-*"):  # left behind by a killed run
        if time.time() - stale.stat().st_mtime > 86400:
            shutil.rmtree(stale, ignore_errors=True)
    # Turn termination signals into SystemExit so the cleanup below still runs.
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: sys.exit(1))
    tmp = Path(tempfile.mkdtemp(prefix="job-", dir=tmp_root))
    t0 = time.time()
    try:
        wav = tmp / "audio.wav"
        log(f"Converting to 16 kHz mono wav: {src.name}")
        to_wav(src, wav, args.start, args.duration)

        log(f"Transcribing (whisper.cpp large-v3-turbo, language: {args.language})…")
        segments = transcribe(wav, tmp / "whisper", args.threads, args.language)
        log(f"Transcribed {len(segments)} segments")

        log("Identifying speakers (pyannote)…")
        turns = diarize(wav, args.speakers, args.min_speakers, args.max_speakers)
        (tmp / "diarization.json").write_text(json.dumps(turns))  # kept with --keep-temp
        n_found = len({t[2] for t in turns})
        log(f"Found {n_found} speakers in {len(turns)} turns")

        segments = assign_speakers(segments, turns)
        if args.language == "zh":
            segments = to_traditional(segments, args.opencc)
        md = render_markdown(src, segments, args, args.start or 0.0, n_found)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        log(f"Done in {time.time() - t0:.0f} s: {out}")
    finally:
        if not args.keep_temp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
