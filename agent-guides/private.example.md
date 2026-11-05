---
# Settings read by `heardmd run` and `heardmd polish` (YAML). Paths may start with ~.
#
# output_dir: folder for the polished transcript. If omitted, it goes next to
#             the raw transcript.
# read_dirs:  folders of background material Claude may read. Claude can read
#             only these, the raw transcript's folder and output_dir.
# speakers:   number of speakers, used when a recording still has to be
#             transcribed (heardmd transcribe -n).
# language:   language of the recording: zh (Chinese, may mix in English;
#             output in Traditional Chinese) or en (English). Default zh.
output_dir: ~/Documents/meetings/polished
read_dirs:
  - ~/Documents/meetings/notes
speakers: 2
language: en
---
# Private guide: <the kind of meeting, e.g. "weekly sync" or "customer interview">

Copy this file to `agent-guides/private/<name>.md` and edit it. `agent-guides/private/` is not tracked by git.
Choose it with `--guide <name>` (for `heardmd run` or `heardmd polish`); if it is the only file in `agent-guides/private/`, it is used automatically.

Everything below is passed to Claude as written. Plain language is fine, in any language; Claude reports back in the language you use here. Where it disagrees with `agent-guides/general.md`, this file wins.

## Speakers

(Example) Usually three people, labeled [Host], [PM] and [Engineer]. The host opens and closes the meeting and hands over; the PM mostly talks about requirements and schedules…

## Background material

(Example) First read `~/Documents/meetings/notes/project-overview.md`, then the notes from the two meetings before this one (files are named by date).

## Terms

(Example)
- The product is **Acme Cloud** (not ACME cloud)
- "deploy", not "the ploy"
