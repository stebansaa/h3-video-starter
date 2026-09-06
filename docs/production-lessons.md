# Detailed production lessons

These notes capture the completed 2026-09-06 production. Treat measured settings
as a reproducible baseline, not a guarantee of future model behavior or pricing.
User instructions and existing session authorization take precedence.

## Start here

- Read root `README.md` for commands and `docs/production-record.md` for measured
  results. Inspect the current files and run state before planning new work.
- The delivered example is `examples/bitcoin-contest/final.mp4`. Files containing
  `review-draft`, earlier runs and superseded reference images are not the final.
- Tested production inputs: `plans/episode-reference-v2.json` and
  `references/episode-v1/manifest-v2.json`; source takes: `examples/bitcoin-contest/run`.
  Preserve them. New plans, changed inputs and new seeds belong in new runs.
- Preserve `script.txt` and its intended dialogue. HappyHorse text in that source
  is historical; this implementation uses native ComfyUI MiniMax H3.
- Do not infer perpetual spending authorization from an old run. Within a
  currently authorized production, perform routine setup, checks, edits and
  cleanup autonomously; review checkpoints do not require repeated permission.

## Local preparation and server setup

- Never download or load H3, ASR or other model weights on the user's Mac.
  Planning, reference preparation, FFmpeg editing and tests run locally; weights
  and model inference belong on the provided remote server.
- Finish scripts, reference images, manifests, offline validation and upload
  bundles before renting a GPU. Validate every shot's assets before submission,
  including assets used late in the sequence.
- Keep keys out of prompts, logs, archives and documentation. `key.env` and
  `.local/` are private. Use the prepared credential loader without printing its
  result. Do not reuse OAuth tokens as general API credentials.
- Read `docs/runpod-runbook.md` and applicable RunPod skills if available. Recheck live
  availability, allocation, price and balance for each new paid session.
- Use the pinned setup scripts and lock files. Reference mode uses the ComfyUI
  revision in `config/reference-model.lock.json`, which differs from the base
  revision in `config/server.lock.json`. It needs the Ref2VA checkpoint and
  `MiniMaxH3AddGuide`; a generic ComfyUI image alone is insufficient.
- The successful reference run used a PRO 6000 Blackwell MIG 48 GB allocation,
  CUDA 13+, 125 GB system RAM and a 200 GB temporary container disk. The selected
  instance advertised 8 vCPUs but provided about 6.8 CPU cores by cgroup quota.
  Check real VRAM, RAM and CPU quota on the server; preserve setup guards.
- That reference stack downloaded about 42.47 GB of weights remotely. Allow for
  runtime/install overhead as well. Persistent pod disks and network volumes
  have different placement and lifetime rules; do not assume they are portable.
- The project REST v2 provisioning code supports minimum CUDA/RAM/vCPU filters
  absent from the connected MCP creation tool at the time of this production.
  Ensure the chosen provisioning method actually enforces those requirements.
- Keep ComfyUI on remote loopback and use a private SSH tunnel. The tested ports
  were local 8188 to remote 8189; verify ownership before reusing or closing them.

## Reference and continuity contract

- The tested profile is `reference-preview`: 640×384, 24 fps, 20 steps. Do not
  silently upscale or switch to the unvalidated full-episode quality profile.
- Reuse `director.workflow.build`; do not invent an API graph for each shot.
  Run live preflight against the actual `/object_info`, including model names,
  dotted autogrow fields, dynamic codec options and linked output types.
- Use the user's `image.png` as the appearance/wardrobe authority. Generate new
  camera angles from approved images, inspect them, and correct drift before
  video generation. A repeated wardrobe description alone is insufficient.
- Check shirt pattern, collar, sleeve length, trousers, hair, accessories, set
  layout, prop placement and which hand holds a prop. This production required
  correcting George's added shirt pattern and restoring Kramer's shirt panels.
- Treat character reference clips as face/voice references; the starting image
  controls wardrobe and staging. The prompt explicitly ignores source dialogue,
  source laughter and source clothing, but those instructions are not a guarantee.
- Each reference should isolate the intended character with clear speech. The
  tested source cuts were 2.65–3.25 seconds. `director.references` validates and
  prepares paired video/audio on the model's frame grid at 24 fps/32 kHz stereo.
- Preserve reference order exactly as `shot.characters`. H3 accepts three paired
  video/audio references. The fourth character uses its first face frame and a
  standalone audio input, not a nonexistent fourth video slot.
- In `director/workflow.py`, the opening image is `ref_images.ref_image_0`
  (`<Picture 1>`). Insert it before the fourth character's image at
  `ref_images.ref_image_1` (`<Picture 2>`). The fourth soundtrack is
  `ref_audios.ref_audio_0`, labeled `<Audio 4>` after the three paired soundtracks.
- The opening image is also an actual frame-zero `MiniMaxH3AddGuide`; supplying
  it only as a reference does not establish the same starting-frame constraint.
- Fixed starting images establish new angles. Same-angle continuations use the
  preceding last frame. This production does **not** carry audio/video latents
  between shots, use Context Loop, or train a LoRA. Do not claim otherwise.

## Generate in reviewable batches

- Start with a representative small batch that includes a speaker change and a
  continuity join. Use `render --through SHOT_ID`, then resume the same command
  and run directory with a later stopping point. Reuse completed outputs.
- The pipeline holds its run lock throughout rendering. Inspect completed media
  while it runs, but record state-changing reviews between batches. Never remove
  an active lock or edit fingerprints to force a resume.
- Keep explicit speaker IDs, exact dialogue, listening reactions and silent
  margins. Use `director.plan.frame_count` for H3's `17k+5` frame grid, rather
  than manually assuming the requested seconds equal the rendered duration.
- **Silence prompts did not reliably produce silence.** Seven of fourteen final
  source takes needed edits for added speech or repetition. Long pauses are not
  automatically usable edit handles, even with “no added words” in the prompt.
- If a clip has missing dialogue, overlapping speech, the wrong speaker, identity
  drift or poor acting, consider another take. Cleanly isolated unwanted speech
  can be removed with a reviewed edit. Trimming is not a fix for every defect.
- Use `director.takes.fork_reviewed_prefix` to retain an unchanged accepted
  prefix when revising later shots. It checks prompts, references and clip hashes.
  Its scope is a contiguous prefix, not arbitrary take replacement.
- A changed ending frame can affect subsequent continuation shots. Preserve the
  ending frame when possible; inspect dependent joins after a tail trim or reroll,
  and regenerate dependent footage when needed up to the next fixed-angle reset.
- After an uncertain paid POST response, inspect saved request/job IDs and server
  history before resubmitting. Preserve the existing recovery and checksum logic.

## Dialogue review and editing

- Inspect contact sheets for appearance and blocking; inspect denser frames around
  suspect speaker changes. A contact sheet cannot certify voice identity, lip sync
  or natural performance. Do not claim to have listened when audio input is unavailable.
- Run ASR on the remote server. `small.en` recovered short responses missed by
  `base.en`, including both “No” reactions. Use a second pass for suspect clips and
  an unprompted segment pass for quiet words; preserve the original evidence.
- ASR also invents or misses words. “Bitcoiners,” “Dexscreener,” contractions and
  “hold”/“whole” were ambiguous. Do not reroll or delete dialogue solely because
  one transcript differs. Do not feed the desired script as an ASR prompt and
  then treat that transcript as independent confirmation.
- Check the **final mixed track**, not just source clips. It exposed an extra
  “At first?” echo and an unrelated opening phrase missed in earlier checks.
  The full pass still missed a quiet “Yeah” detected in a source-tail pass.
- Keep raw clips immutable. Record retained integer frame ranges, source hashes
  and reasons in a cut manifest. Use `director.cuts` to cut picture and audio
  together. ASR word boundaries are estimates: leave margins and verify the
  actual edited media with a fresh transcription.
- If accepting a source only with mandatory edits, record `review --cuts ...`
  and describe that condition in the review note. The starter enforces the
  saved required edit; plain `director assemble` rejects those sources.
  Deliver through `scripts/assemble_episode.py --cuts ... --mix ...`.
- Request clean dialogue without a generated laugh track. Mix audience reactions
  on one scene timeline, with fades and ducking under speech, so laughs can span
  picture cuts. Add quiet continuous room tone; avoid dialogue crossfades that
  consume words or create overlapping speakers.
- Preserve sample-exact PCM intermediates. Encoding every segment separately to
  AAC introduced padding at joins in testing. The current assembly avoids that
  accumulated timing error and encodes the final soundtrack once.
- The tested mix targets dialogue at −20 LUFS and audience at −27 LUFS, with
  per-cue gains. These are a baseline for review, not universal mix settings.
- A final reaction hold can give laughter time to finish. The tested hold is 48
  frames; the fade reaches full black on the last frame. Ordinary shot boundaries
  remain hard cuts, which may expose pose jumps after internal edits.

## Verification, delivery and cost control

- Run relevant offline tests after code changes. Use `python3 -m unittest discover
  -v` for a full check when warranted; the original production passed 70 tests.
  The starter includes additional portability checks; see `docs/release-checks.json`.
  Avoid rerunning the whole suite merely while waiting for a GPU job.
- Check the actual final export: full decode, frame count, dimensions, 24 fps,
  stereo, audio/video duration agreement, audio peak level and final black frame.
  Recheck edited sections and the mixed-track transcript after corrective edits.
- Preserve drafts with explicit names. Replacing an export invalidates its old
  verification/hash association; regenerate the report for the delivered bytes.
- Finish with a clickable **absolute** path to the final file. The authoritative
  production report, edit manifest and verification must identify the same export.
- Prepare code and reference assets separately; code-only bundles cannot reproduce
  a reference production by themselves. Include this `AGENTS.md` in new code
  bundles. Do not archive credentials, model weights or accidental private files.
- Before shutdown, download accepted/rejected takes, final exports, ASR results,
  histories and setup records needed for review. Complete CPU checks while GPU
  generation is underway when possible to reduce idle rental time.
- Record the session's authorized budget, live rate and start time. Use the
  prepared stop watchdog as a fallback, not as a replacement for active cleanup.
- Once no GPU work remains, stop the temporary pod and verify `EXITED`. Delete
  disposable session resources within their authorized scope and confirm removal.
  Do not delete an older saved pod or volume merely because it is stopped.
- Close the session's tunnel/watchdog after verifying process ownership. Confirm
  cleanup with the API; SSH disconnection alone does not prove billing stopped.
- Historical measurement: accepted-shot execution totaled about 55.4 minutes;
  the temporary pod was allocated for about 96.2 minutes. Estimated cost including
  temporary container storage was $1.79. This is not a per-video price guarantee.
  Storage on the original stopped pod remained billable separately. Never treat
  the recorded balance or hourly rates as current account information.

## Experiments for the next quality pass

These are hypotheses, not established improvements. Test one variable on a small
representative sample before changing a complete production:

- Tighter dialogue durations and fewer speaking characters per shot may reduce
  added speech and voice swaps. Do not assume unused generated time will be quiet.
- Closer speaker coverage and planned reaction cutaways may hide edit joins better
  than repeatedly cutting within the same wide shot.
- Cleaner/shorter voice references may help, but reference audio causing the
  unrelated speech has not been isolated as the cause.
- Compare any continuity extension, higher resolution or LoRA against this native
  reference baseline before adopting it. None was proven better in this run.
