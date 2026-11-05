# Polishing a meeting transcript: general guide

This guide applies to every recording. There is also a **private guide** that describes this kind of meeting: who the speakers are, what background material to read, and how terms are spelled. **When the two disagree, the private guide wins.**

## 0. The task

`heardmd transcribe` writes `<name>_transcript.md`, the **raw transcript**: whisper's word-for-word output, with fillers, repetitions and recognition errors left in. Speakers are labeled `SPEAKER_00`, `SPEAKER_01`, and each run of speech by one speaker carries a single timestamp. It is the evidence; **never modify it**.

Write a separate **polished transcript**: it should read like a clean set of meeting notes, stay faithful to what was said, and keep the timestamps so a reader can go back to the recording.

## 1. Read the background material

Many recognition errors are proper nouns: names, paper titles, acronyms, product or system names. Context alone cannot fix them, so before writing, read the background material the private guide lists, to learn what the meeting is about and how its terms are written.

- Use the material only to **confirm terms and understand context**. It does not tell you what was actually said; never copy its content into the polished transcript.
- If a term is still unclear afterwards, search for that one term in the folders you may read. Do not read whole folders.
- **Never treat AI-generated polished transcripts or summaries as a source**, including earlier output of this tool: their wording may be wrong, and relying on them spreads the errors.
- Notes written after the meeting, possibly from this very recording, must not be used to correct the same recording; that would be circular. The private guide says which sections to skip.
- If you find a clear spelling, use it; if not, handle the term as described in section 3.

## 2. Identify the speakers

- If the private guide defines roles (for example 【主持人】【來賓】 or [Host] [Guest]), decide who is who from **their role across the whole meeting**: who reports, who asks, who concludes. Do not guess turn by turn, and do not decide by who speaks first.
- State the mapping and a one-line reason at the top of the polished transcript.
- If you cannot tell, keep the `SPEAKER_00` labels and say why. If the private guide defines no roles, keep the SPEAKER labels.

## 3. Polishing rules

The goal is a transcript the reader can get through smoothly, like well-kept meeting notes, while every sentence stays true to what the speaker meant.

**Clean up the speech:**
- Remove fillers, verbal tics and stutter-like repetition (examples per language in section 6). Keep meaningful answers such as 「對」「好」, "yes", "right".
- Add punctuation, form complete sentences, and break paragraphs by topic. Punctuation style is in section 6.
- Write in **the same language as the raw transcript**; never translate. In a Chinese transcript, keep English terms in English: common nouns in lower case, proper nouns as they are normally written.
- This is an edit, not a summary: keep every point, example, question and answer. Do not merge them into key points, and do not add anything that was not said. Expected length is in section 6; much less than half of the original means too much was cut.

**Handle recognition errors.** The raw transcript has many errors. Too many markers make the text unreadable, but a wrong guess can change the meaning without the reader noticing. Handle each error by how sure you are:

1. **Sure: fix it silently.** This covers anything found in the background material or the private guide, found by searching, or obvious from context or common knowledge, e.g. 「鐵紋」→「貼文」, 「六度關心一度」→「六度分隔」, "Cuban eighties" → "Kubernetes". This is the usual case.
2. **A reasonable guess that might be wrong and affects the meaning:** write the guess followed by the original words, e.g. 「時程從畢業往回推一年〔原：往回推一念〕」 or "run three rounds [orig: run three grounds]". The reader sees at a glance what changed without opening the raw transcript.
3. **Unintelligible:**
   - If it is just a fragment and removing it does not change the sentence's meaning, remove it.
   - If it matters to the meaning, keep the original words and mark them 〔聽不清：原字〕 or [inaudible: original words].

Keep markers few and useful. An hour-long meeting usually needs a dozen or so, never hundreds. Before adding one, ask: what can the reader decide from seeing it? If nothing, fix or remove the text by the rules above.

**Check that a rewrite keeps the meaning.** For example, the raw 「要先排時程會在要決定預算還要前面嗎」 means "should scheduling come before deciding the budget?", and the reply that follows confirms it. Do not smooth it into 「還是要放在前面？」 ("or should it go first?"), which means something else. When a sentence is unclear, read the questions and answers around it; that usually settles what was meant.

## 4. Fix speaker turns

The diarization (pyannote) often misses very short interjections: a one-second question or reply from the other person gets merged into the previous speaker's paragraph. If the flow of the conversation clearly shows a change of speaker (a question and its answer, how one addresses the other, "you said…"), split that sentence out and give it to the right speaker, reusing the paragraph's timestamp. If unsure, leave it.

- Put no markers in the body. List every reassignment at the end under the speaker-reassignment heading, so the body stays clean.
- Delete back-channel 「嗯」「對」/"mm", "right" instead of making them separate turns.
- After fixing, merge adjacent turns by the same speaker and keep the earlier timestamp. But if the earlier timestamp is far (over a minute) from where the merged speech actually occurs, keep the turns separate with their own timestamps, so the reader does not look in the wrong place in the recording.

## 5. Output format

Chinese transcript:

```markdown
# <name> 會議逐字稿（潤飾版）

原始錄音：`<recording path>`
講者：SPEAKER_00 = <角色>、SPEAKER_01 = <角色>（依對話內容推定：<one-line reason>）
說明：已刪除口頭禪、補標點、修正辨識錯誤；〔原：…〕是推測的修正，〔聽不清：…〕是無法辨識的地方，都列在文末待確認。

---

**【<角色>】** 00:00:00
First paragraph…

Second paragraph…

**【<角色>】** 00:06:41
…

---

## 附註

### 講者改判
- 00:14:38「這是什麼意思？」→ <角色>（<why>）

### 待確認
- 00:21:16「實驗要跑幾輪〔原：能數〕」：<why this guess>
```

English transcript: the same structure with English labels: `# <name> Meeting Transcript (Polished)`, `Recording:`, `Speakers:`, `Note:`, speaker lines like `**[Role]** 00:00:00`, `## Notes`, `### Speaker reassignments`, `### To verify`.

- Speaker line: the role in bold, followed on the same line by the `hh:mm:ss` timestamp. The text starts on the next line, with no blank line in between. Without roles, write `**【SPEAKER_00】**` or `**[SPEAKER_00]**`.
- Keep the order of turns from the raw transcript; never move paragraphs around.
- List only notes that exist; omit a notes section that would be empty.

## 6. Language-specific details

The `Language:` line at the top of the raw transcript gives its language (older transcripts write it as `語言：`; no such line means Chinese).

| | Chinese (zh) | English (en) |
|---|---|---|
| Punctuation | Full-width （，。？！、：「」） | ASCII (, . ? ! : " ") |
| Fillers | 就是、然後、那個、這樣子、嗯、對對對、「一個一個一個」 | um, uh, you know, like (as filler), I mean, sort of, kind of, sentence-initial "so", repeated words ("the the") |
| Wording | Taiwan Traditional Chinese usage | The spelling the private guide specifies (US or UK); otherwise as in the raw transcript |
| Markers | 〔原：…〕〔聽不清：…〕 | [orig: …] [inaudible: …] |
| Length after polishing | About 60–70% of the raw transcript | About 70–80% (English has fewer fillers) |

## 7. Working through a long transcript

The raw transcript of an hour-long meeting runs to tens of thousands of characters. Write as you read; do not work out the whole thing in your head first. Past runs spent 7–11 minutes planning and drafting before writing anything, then rewrote the finished file twice, taking over 15 minutes, while writing the content itself took only a few minutes. Work in this order:

1. Read the whole raw transcript and the background material. At this point decide only two things: the speaker mapping, and the spelling of a few recurring terms. Do not plan each passage or draft anything; the polishing happens while writing each batch below.
2. Create the output file with Write, containing the header (title, details, `---`).
3. Go through the raw transcript in order, in batches of about 30 turns (or about 10,000 characters of raw text). Append each batch with Edit: use the last two or three lines of the file as `old_string` (they must match uniquely) and those lines plus the new content as `new_string`. Continue to the last turn. Finish every batch; never skip a passage. Note speaker reassignments and items to verify as you go.
4. Append the notes section the same way.
5. Use Grep to confirm that the polished transcript's last timestamp matches the raw transcript's last turn, so nothing was skipped. Do not reread the whole polished file.

**Never rewrite the whole file.** If something earlier needs fixing, change only that passage with Edit.

## 8. Finishing and reporting

- Write only the one output file you were given; do not create or change any other file.
- In an unattended run (the instructions say so), nobody can answer questions: make decisions yourself following the two guides, and explain them in the final report.
- Finish with a short report, written in the language the private guide is written in (English if there is no private guide), whatever the transcript's language:
  - the output file
  - the speaker mapping and the reason
  - how many speaker reassignments and items to verify
  - **terms to add to the private guide**: spellings the private guide lacks that recurred or are likely to go wrong again, one per line, as "correct spelling ← spelling in the raw transcript". Write "none" if there are none.
