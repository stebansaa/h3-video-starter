# Review and edit the generated scene

Technical success is not creative success. Check actual faces, costumes, props,
speakers, lips, pauses and dialogue before accepting a shot. Contact sheets and
transcription narrow the search; they cannot certify voice identity or acting.
Ask for the user's preview review when the current scope requires it. If the
agent cannot receive audio, state that limitation instead of claiming to listen.

## Transcription on the remote server

Prepare a separate small ASR environment on the GPU server. This avoids changing
the pinned ComfyUI environment:

```sh
python3 -m venv --system-site-packages /workspace/episode-asr-venv
/workspace/episode-asr-venv/bin/python -m pip install faster-whisper==1.2.1
cd /workspace/seinfield
/workspace/episode-asr-venv/bin/python scripts/transcribe_server.py \
  /workspace/seinfield-runtime/ComfyUI/output/director \
  --model small.en --out /workspace/episode-transcripts
```

ASR runs on CPU in the remote pod to reduce GPU contention. Its model cache is
`/workspace/episode-asr-models`; do not run this setup on the local computer.
The script refuses a non-Linux/NVIDIA host before importing or downloading a
model. It uses unprompted English transcription and saves word timestamps.
You can run `scripts/watch_transcripts_server.py` with that same Python for
background transcription of newly completed clips. The watcher uses the standard
paths above and stops after five hours; run the transcriber explicitly for a
changed existing output or a second pass.

Use `small.en` as the current default. The recorded evidence includes base.en
passes followed by selective small.en corrections. A cache entry is reused only
when media SHA-256, model and segment selection match. Use a separate output
directory for alternative passes so the first evidence remains available.

For a quiet or ambiguous phrase, run an unprompted segment pass:

```sh
/workspace/episode-asr-venv/bin/python scripts/transcribe_server.py /workspace/PATH_TO_CLIP.mp4 \
  --model small.en --clip-timestamps '7,10.125' --out /workspace/segment-checks
```

Those example timestamps must be adjusted to the actual source. Never seed ASR
with the expected screenplay and then use its transcript as independent proof.
Proper names, crypto vocabulary and short responses can be misrecognized.
The completed scene's quiet “Yeah” was missed in full-track ASR but detected in
a source-tail pass. Missing/overlapping actual dialogue needs a reroll; a single
ASR mismatch is not sufficient evidence by itself.

Download transcripts locally, preserving their generated output filenames:

```sh
scp -i .local/h3_ed25519 -P SSH_PORT -r root@SSH_HOST:/workspace/episode-transcripts projects/my-video/transcripts
```

Run this first copy when the local destination does not exist. On later syncs,
copy the files into that directory without nesting another `episode-transcripts`
folder. The assembler maps each shot's `history.json` output basename to its
transcript; renaming all transcripts to shot IDs breaks that mapping.

## Reviews and precise edits

Record reviews between render batches; the renderer holds the run lock while
working. For an accepted shot with no edits:

```sh
python3 -m director review --run runs/my-video --shot 01a --decision accepted \
  --note 'Reviewed picture and dialogue; describe evidence and any remaining limitations.'
```

If human review is still pending, create a separate provisional preview without
marking the source accepted. The [single-clip example](single-clip-preview.md)
shows the tested PCM cut and exact-24-fps export, including the timestamp issue
caught during the fresh-agent trial.

The review note must reflect what was actually checked. Keep raw source MP4s
unchanged. For cleanly removable extra speech, put the retained integer frame
ranges in `projects/my-video/cuts.json`:

```json
{
  "version": 1,
  "shots": {
    "01a": {
      "source_sha256": "ACTUAL_SOURCE_CLIP_SHA256",
      "keep_frames": [[12, 110], [132, 205]],
      "reason": "Describe unwanted material and the evidence for these boundaries"
    }
  }
}
```

These are illustrative boundaries, not reusable cut instructions. Ranges are
zero-based, start-inclusive and end-exclusive at 24 fps. They must fit this
source and retain complete spoken words with margins. `director.cuts.cut_clip`
cuts audio and video together; it cannot repair voice swaps or missing lines.
Bind acceptance to the exact required edit:

```sh
python3 -m director review --run runs/my-video --shot 01a --decision accepted \
  --cuts projects/my-video/cuts.json --note 'Accepted only with the specified reviewed cuts.'
```

The state now records `required_edit`. The episode assembler requires a matching
cut entry, and plain `director assemble` refuses this source. If a required cut
changes, review it again. Never copy the recorded example's cuts to a new take.
After a tail trim, inspect the next shot's pose and continuity; its generation
was conditioned on the original last frame. Regenerate dependent footage up to
the next fixed starting image if the changed join is unacceptable.

## Sound continuity and assembly

Request clean production dialogue from H3. Put audience on a continuous scene
timeline afterwards. `mix.json` maps sample names to paths, duration and gain,
then names which shot each cue follows. It uses the last recognized word plus
0.16 seconds as a timing suggestion; inspect and adjust if ASR timing is wrong.
Laughs can span picture cuts and duck under the following dialogue. The mixer
adds quiet room tone and fades. It targets dialogue at −20 LUFS and audience
at −27 LUFS before per-cue gains, as a baseline for review.

```sh
python3 scripts/assemble_episode.py --run runs/my-video \
  --transcripts projects/my-video/transcripts --cuts projects/my-video/cuts.json \
  --mix projects/my-video/mix.json --out output/my-video-review-v1.mp4
```

All selected shots must be complete and accepted. Use `--through SHOT_ID` for
a reviewed prefix and `--end-hold-frames 0` for a preview without the final hold.
Omit `--mix` for no audience cues; `--no-audience` disables samples from an
otherwise supplied mix. Outputs are never silently overwritten.

The renderer's native audio stops at each clip boundary; this mix smooths
ambience and laughter, but cannot guarantee consistent voice timbre. Picture
joins are hard cuts. PCM intermediates avoid adding AAC encoder padding at
each join; the final soundtrack is encoded once. The example ends with a
48-frame reaction hold and fade to black.

## Final review and delivery

Upload the edited export or its dialogue track to the server and transcribe it
again into a separate directory. This caught repeated/unrelated speech missed
in raw-clip checks during the original production. Preserve that transcript
and its source hash. Do not accept solely on aggregate word-error rate.

The assembler performs full decode, size, fps, stereo and duration checks and
writes `.edit.json` and `.dialogue.json` beside the output. Also verify frame
count, end frame, audio peaks, edited word boundaries and important speaker
changes in the actual delivery. A later replacement needs a new verification
report tied to its SHA-256. Keep drafts explicitly named and preserve evidence.

Provide the final absolute path, review limitations, resource cleanup status
and measured cost. The recorded example's verification and limitations are in
`examples/bitcoin-contest/verification-original.json`.
