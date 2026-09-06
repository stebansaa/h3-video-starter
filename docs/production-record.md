# Recorded production: The Bitcoin Contest

Completed 2026-09-06. These are historical measurements from the supplied
production, not a current GPU quote or a guarantee for future renders.

| Item | Recorded value |
| --- | --- |
| Final export | `examples/bitcoin-contest/final.mp4` |
| Duration | 97.208333 seconds |
| Video | 640×384, 24 fps, 2,333 frames, H.264 |
| Audio | Stereo AAC; single final encode from PCM intermediates |
| Source shots / scripted turns | 14 / 43 |
| Raw planned duration | 116.25 seconds after H3 frame rounding |
| Sources needing dialogue edits | 7 |
| Audience cues / ending hold | 10 / 48 frames |
| GPU | PRO 6000 Blackwell MIG 48 GB |
| Advertised / actual CPU allocation | 8 vCPU / approximately 6.8 cgroup cores |
| System RAM / temporary disk | 125 GB / 200 GB |
| Reference weight bytes | Approximately 42.47 GB, downloaded only remotely |
| Generation profile | `reference-preview`, 20 steps |
| Accepted-shot execution total | Approximately 55.4 minutes |
| Pod allocation time | Approximately 96.2 minutes |
| Historical hourly GPU rate | $1.09 |
| Estimated GPU plus temporary container storage | $1.79 |
| Original code tests | 70 passed |

Final SHA-256:
`fc663bb2b89cfd062f88475243db9e9ab012e9d1040434ae04ee377bf4e12893`.

The opening was reused from an accepted earlier take. A first continuation
used the wrong view; the retained replacement resets to the corrected interior
image. All later takes and their exact seeds/graphs are preserved under the
example's `run/` directory. The saved example state is marked `recorded_example`
and refuses new generation: replay it offline or start a fresh project/run.
It is not a portable checkpoint of the now-deleted remote GPU service.

The final technical check fully decoded the export, confirmed its frame count,
dimensions and stereo soundtrack, and measured a −2.9 dB peak and black final
frame. Frames, transcripts and technical metrics were reviewed. Voice timbre
was not independently listened to by the agent. Full-track ASR missed a quiet
“Yeah” recovered in a source-tail pass; crypto spellings and “hold/whole” remained
recognition/pronunciation ambiguities. Read the evidence instead of treating a
green technical status as a promise of perfect acting or speaker identity.

The disposable production pod was stopped and deleted. An older saved stopped
pod was outside that cleanup scope and its separate storage was not included in
the $1.79 estimate. Account IDs, balances, SSH credentials and private connection
details are intentionally absent from this portable package.

## Changes made for this portable starter

- Public credential loading replaces a private local helper.
- Configurable GPU identifiers cover the actual MIG allocation as well as 5090;
  a temporary-disk option reproduces the recorded storage shape.
- Reference-aware live preflight checks the graph that will actually render.
- Audience samples/cues are project configuration instead of fixed episode IDs.
- Required frame edits are now enforced by source hash and review state.
- ASR caching uses media SHA-256, model and segment selection.
- The complete offline replay, new-project scaffold, runbooks, integrity
  manifest and CI checks provide a repeatable handoff.
- A repository-local `h3-video` skill and first-session check guide a new Codex
  host through missing prerequisites. Explicit MCP instructions distinguish
  configuration, successful authentication and the direct Python API route.

This packaging pass did not generate new AI footage or test a fresh paid GPU
installation. Current release validation is recorded in `release-checks.json`.
