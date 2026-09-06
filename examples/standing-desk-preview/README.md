# Fresh-agent first-clip test

Watch [the edited preview](preview.mp4). A fresh-context agent generated it on
September 6, 2026, from the first shot of [this two-shot draft](../standing-desk-draft).
It used the clean repository, its local skill, a privately configured RunPod
key and a $2 test budget. No MCP, global RunPod skill or prior production chat
was used. The second shot was not generated.

| Check | Observed result |
| --- | --- |
| Offline tests | All 85 passed before provisioning |
| Fresh remote setup | Pinned ComfyUI installed; 42.47 GB of weights downloaded and hash-verified remotely |
| Live workflow preflight | Reference-aware checks passed |
| Generation | One shot, seed 6090601, reference-preview, 20 steps; 259.935 seconds of execution |
| Raw clip | 226 frames, 9.416667 seconds, 640×384, 24 fps, stereo |
| Edited preview | 181 frames, 7.541667 seconds, full decode and technical checks passed |
| Cost | Approximately $0.43 including setup and temporary storage; billing record had not posted |
| Cleanup | Owned pod stopped, separately confirmed EXITED, deleted and confirmed absent; supervisor independently checked |

## What the review caught

The [raw take](raw-clip.mp4) contains extra opening speech before both scripted
lines. Full unprompted ASR, an independent opening-segment pass, visible mouth
movement and the audio-energy measurements identified a removable prefix.
The agent found the issue independently; the supervisor then requested the
documented correction and another ASR pass of the actual edited file.

The retained range is **[45,226)** at 24 fps, starting at 1.875 seconds in a quiet
gap, with approximately 0.375 seconds before intended speech energy. This is
a cut for this exact raw file, not a reusable rule for new footage. The final
unprompted transcript contains both requested lines with no added phrase:

> A standing desk should charge less rent. I'm not even using the chair.
> You're renting a desk?

Human playback review of voices, lip-sync and acting is still pending. The
agent and supervisor inspected frames; neither claimed to have listened.
This was one fresh first-clip test on the same local host, not a wholly new
Codex installation or a fresh multishot production. The longer included edit
was also replayed successfully from recorded footage.

## Evidence

- [Final verification](verification.json), [source-bound cuts](cuts.json),
  [final transcript](preview-transcript.json), [final contact sheet](preview-contact-sheet.jpg).
- [Raw technical QC](qc.json), [raw transcript](raw-transcript.json),
  [opening segment transcript](opening-transcript.json),
  [opening audio energy](opening-audio-energy.json), [raw contact sheet](contact_sheet.jpg).
- Exact native [workflow](workflow.api.json), [job history](history.json),
  [reference mapping and hashes](reference-inputs.json),
  [runtime setup](runtime/setup.json) and [installed packages](runtime/installed-requirements.txt).
- [Cost calculation and limits](cost.json), [cleanup confirmation](cleanup.json).

Source paths in review/reference records were normalized for portability.
Source and delivery SHA-256 values remain unchanged. Workflow upload filenames
record this run; let the director prepare/upload fresh assets for another run.
The package inventory is historical evidence, not a replacement installer.

The [offline edit recipe](../../docs/single-clip-preview.md) reproduces this
preview with the shipped cut helper and FFmpeg while leaving review pending.

The handoff gaps and fixes are described in [the trial report](../../docs/live-handoff-trial.md).
