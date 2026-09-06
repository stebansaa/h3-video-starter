> Archived original workspace guide, 2026-09-06. Historical commands and paths
> are retained for context. Use the current [runbook](../runpod-runbook.md),
> [root README](../../README.md) and [AGENTS.md](../../AGENTS.md) for this starter.

# Seinfeld clip director

Project lessons and operating instructions are in [root AGENTS.md](../../AGENTS.md).

Prepare shots locally; generate them later on a RunPod GPU running ComfyUI.
The local client uses Python 3.9+ standard library, FFmpeg and ffprobe. It does
not load AI models. **No model weights are included or downloaded by local
planning, exporting, testing, bundling, or rendering.**

`script.txt` is the unchanged source. `plans/episode.json` preserves all 43
speaking turns in 14 realistically timed clips (116.25 seconds including H3
frame rounding). The duplicate “I’m out” is preserved. HappyHorse-specific
instructions and stale dialogue examples are excluded from generated prompts.
The bitcoiner stays off-screen because the source contains no shot of him.

## Local preparation and tests

```sh
python3 -m director plan
python3 -m director export --out runs/prepared
python3 -m director doctor
python3 -m unittest discover -s tests -v
```

Tests make requests only to temporary localhost HTTP servers. They simulate
RunPod/ComfyUI protocols and use real FFmpeg for encoding, decoding, frame
extraction, contact sheets and assembly. They never contact a paid API.

If FFmpeg/ffprobe are missing, install them with your normal package manager,
set `FFMPEG`/`FFPROBE` to existing binaries, or explicitly install the local test
tools (small executable downloads, no AI weights):

```sh
python3 scripts/install_test_media.py
python3 -m unittest discover -s tests -v
```

The optional installer uses `static-ffmpeg==3.0`. Those binaries live in the
ignored `.venv`, and are excluded from the upload bundle. The runtime never
downloads them automatically.

## What is implemented

- Native ComfyUI H3 T2V and first-frame I2V graphs, native audio decoding and MP4 saving.
- Ref2VA character references and a native starting-image guide, for one shot or a complete sequence.
- Stable character/speaker descriptions, verbatim timed dialogue, deterministic seeds.
- 512×384 previews, 640×384 reference previews, and a 1024×768 quality profile.
- Live node/model/connection preflight against `/object_info`, including native v3 codec choices.
- Multipart image upload, queue submission, polling, output download, technical QC.
- Atomic run checkpoints, run locking, clip checksums, interrupted job recovery,
  and local recovery after a clip has downloaded even if server history is lost.
- GET retries; paid POSTs are never automatically retried after an uncertain response.
- Last-frame continuity, selective shot rendering, explicit creative review, draft/final assembly.

## Character references and starting image

For a single shot, `--references` accepts a local JSON manifest. Paths resolve
relative to that manifest; clips must follow the shot's character order. Each
clip needs its own character speaking with clear audio. Use one to four clips.
The first three use native paired video/audio references; the fourth supplies
its first face frame and a separate audio reference. For example:

```json
{
  "version": 1,
  "shot": "01a",
  "first_frame": "start.png",
  "clips": [
    {"character": "Jerry", "path": "jerry.mp4", "seconds": 3.25},
    {"character": "George", "path": "george.mp4", "seconds": 3.25},
    {"character": "Kramer", "path": "kramer.mp4", "seconds": 2.65}
  ]
}
```

Optional `start` selects a position in seconds within each source. Cuts of
2–6 seconds are normalized together with their soundtracks to 24 fps, stereo
32 kHz and the model's frame grid. Source file bytes and cut settings form part
of the run fingerprint; changing them requires a new run directory.

On the **RunPod server only**, opt into the pinned AddGuide implementation and
the additional ~21 GB Ref2VA checkpoint. The encoder and VAEs are reused; an
existing FL2VA checkpoint stays on disk, but this mode does not download it:

```sh
python3 scripts/setup_server.py --with-references --install --download-models --fast-downloads
python3 scripts/setup_server.py --with-references --start
```

Then, through the private ComfyUI tunnel, run the local client:

```sh
python3 -m director render --plan plans/opening-reference.json \
  --shot 01a --profile reference-preview --seed 1001 \
  --references references/opening-v2/manifest.json --run runs/reference-clip
```

The image is both a visual reference and an actual frame-zero guide. Character
videos and their paired soundtracks enter the native Ref2VA node with explicit
prompt assignments. This path does not train a LoRA or carry audio across
separate generated shots. Offline tests verify transport and wiring; creative
quality still requires review of the real GPU output. The original trial is
preserved in `runs/first-clip`.

`--fast-downloads` uses the server's Hugging Face Xet client with parallel
transfers, then checks each downloaded file's size and SHA-256. It remains
behind the Linux/CUDA server guard. Omit the flag to use the resumable curl
transport. Reference previews permit 6 allocated CPU cores, accommodating
RunPod's 8-vCPU MIG instances whose cgroup quota is 6.8 cores; the 64 GB RAM,
32 GB VRAM and CUDA 13 requirements remain enforced.
- RunPod REST v2 request preparation, create/list/get/check/stop, with redacted response storage.
- Remote hardware checks before installation, model downloads, or startup.
- An upload bundle and explicit server-only setup/download/start commands.

This first version uses ComfyUI's native nodes. Context Loop, Ref2VA audio
continuation, automatic vision/audio judgement, and automatic creative rerolls
are not implemented. The agent can inspect contact sheets and clips, record a
review, and render another take with a different seed. Technical QC checks
streams, stereo channel count, frame rate, duration, dimensions and full decoding; it cannot certify
correct faces, exact speech, voices or comedy timing.

## Full scene production and editing

The complete production uses `plans/episode-reference-v2.json` and
`references/episode-v1/manifest-v2.json`. A version 2 reference manifest maps
character names to source clips and shot IDs to optional starting images.
Fixed images establish each camera angle; other shots use the previous clip's
ending frame. All images derive their wardrobe from the user's `image.png`.
Every asset is validated before the first paid request.

```sh
python3 -m director render --plan plans/episode-reference-v2.json \
  --profile reference-preview --seed 2001 \
  --references references/episode-v1/manifest-v2.json --run runs/full-episode-v2
```

Use `--through SHOT_ID` to pause after a clip, then resume with the same
arguments and directory. Completed clips are reused. Changing a plan or source
requires a new run; `director.takes.fork_reviewed_prefix` can copy a reviewed,
unchanged prefix after checking prompts and asset hashes.

Generation prompts request dialogue without a laugh track. The scene editor
normalizes dialogue, uses sample-exact PCM intermediates, and mixes audience
reactions on one continuous timeline. Laughter fades and ducks under speech,
including when it spans a picture cut. A quiet room-tone bed covers the scene.

Automatic transcripts run only on the remote Linux NVIDIA server using
`scripts/transcribe_server.py`; no ASR weights are downloaded locally. Review
the contact sheets and transcripts, then record each accepted clip with
`director review`. The production's explicit frame edits are in
`plans/episode-cuts-v1.json`: they retain reviewed frame ranges, remove unwanted
generated speech, and apply identical cuts to picture and audio. Source clips
remain intact, and every edit is bound to its source checksum.

```sh
python3 scripts/assemble_episode.py --run runs/full-episode-v2 \
  --cuts plans/episode-cuts-v1.json --end-hold-frames 48 \
  --transcripts reports/episode-transcripts-final --out output/the-bitcoin-contest.mp4
```

Assembly requires accepted clips and their downloaded transcript JSON files.
It writes video, edit provenance and a dialogue comparison. ASR can miss quiet
words or misrecognize crypto names; it does not establish voice identity.
The production checks include a fresh transcription of edited sections and
real FFmpeg tests that verify audio and picture remain synchronized after
disjoint cuts. No upscaling is applied to the 640×384 production.
The final 48-frame reaction hold gives the closing laugh two seconds to finish;
the picture then reaches full black on its last frame.

## RunPod provisioning, later

The Python `director pod-*` commands use REST v2 and need `RUNPOD_API_KEY` in
the shell environment. Codex's authenticated MCP connection can list and manage
Pods, but its current creation tool omits minimum RAM, vCPU, and CUDA filters.
Use the Python provisioning path below to enforce this project's hardware
requirements. MCP OAuth does not authenticate the Python client, so a RunPod
API key is still needed for this path. Do not extract or repurpose OAuth tokens.
The H3 open-weight
workflow does not require a MiniMax, HappyHorse, or LLM API key. ComfyUI can be
reached through an SSH tunnel, without exposing its unauthenticated HTTP API.
If a server already exists, skip Pod creation and upload the bundle to it.

Create a project SSH key locally when preparing a new checkout; reuse the
existing `.local/runpod_ed25519` key if already prepared. Never overwrite it
while a Pod uses it:

```sh
mkdir -p .local
ssh-keygen -t ed25519 -f .local/runpod_ed25519 -N ''
python3 -m director pod-config --public-key .local/runpod_ed25519.pub
python3 -m director pod-create --config runs/pod-request.json
```

The last command is a dry run. The request selects one Secure Cloud RTX 5090,
CUDA 13.0-or-newer host, at least 64 GB system RAM and eight vCPUs,
150 GB container disk, 100 GB `/workspace` volume disk, the pinned CUDA 13
RunPod image, and SSH port 22 only. A 32 GB GPU will need model offloading;
runtime and quality remain to be measured. The code does **not** guarantee
GPU availability or impose a provider-enforced dollar cap.
The container disk allowance follows the official ComfyUI template guide;
the earlier 30 GB allowance has been replaced. Both disks incur storage costs.
Regenerate older request JSON with `pod-config`; v1 payloads are refused.

To attach an existing network volume instead, pass `--network-volume-id ID`
and optionally `--data-center-id ID` to `pod-config`. A Pod volume survives a
stop but is lost on termination; a network volume is independently retained.
Confirm current availability, quote and experiment budget before renting.

With credentials configured privately, this explicit command creates a billable Pod:

```sh
python3 -m director pod-create --config runs/pod-request.json --execute
python3 -m director pod-list
python3 -m director pod-get POD_ID
```

Wait for `RUNNING`, then run `python3 -m director pod-check POD_ID` before
uploading. The check verifies allocated GPU/RAM/vCPUs, host CUDA, pinned image,
and direct SSH availability. Read the address and port from `ssh.direct.host`
and `ssh.direct.port` in the v2 response. Publishing `22/tcp` replaces reliance
on the removed v1 public-IP placement flag; direct SSH must still be verified
on the allocated Pod. If creation loses its
response, `runs/pod-state.json` retains the unique name. Find that name with
`pod-list`; do not create another Pod blindly. Failed bootstrap or generation
does not automatically stop the GPU. Stop it when finished or abandoning a test:

```sh
python3 -m director pod-stop POD_ID
python3 -m director pod-get POD_ID
```

Confirm status `EXITED`. Storage charges can continue after GPU shutdown.
The client intentionally has no automatic terminate/delete operation.

## Upload and setup on the GPU server

Use the verified prepared archive. To build a separate archive, use
`scripts/bundle.py --out` with an unused filename; it refuses to overwrite one.

```sh
scp -i .local/runpod_ed25519 -P SSH_PORT runs/seinfield-server.tar.gz root@SERVER_IP:/workspace/
ssh -i .local/runpod_ed25519 -p SSH_PORT root@SERVER_IP
```

On the server:

```sh
cd /workspace
tar --no-same-owner -xzf seinfield-server.tar.gz
cd seinfield
python3 scripts/setup_server.py
python3 scripts/setup_server.py --check
python3 scripts/setup_server.py --install
python3 scripts/setup_server.py --download-models
python3 scripts/setup_server.py --start
```

The first invocation prints a plan and changes nothing. `--check` inspects the
server without installing or downloading. All active modes validate the actual
CUDA runtime, one GPU with at least 32 GB VRAM, and at least 64 GB allocated
system RAM / eight vCPUs. Memory and CPU checks include container cgroup limits,
so a large physical host cannot hide a small allocation. These are hardware
checks, not a model-loading or CUDA-kernel test. Mutations require a
Linux NVIDIA server. `--install` creates an isolated pinned ComfyUI checkout
and a venv reusing the image's CUDA 13 PyTorch, installs ComfyUI dependencies,
and checks them. The server must provide Python 3.12+, `venv`, git, curl,
FFmpeg/ffprobe and CUDA 13 PyTorch. The pinned RunPod image is intended to
provide these; its actual startup behavior still needs a live smoke test.

**Only `--download-models` downloads weights**, into the server's persistent
`/workspace/seinfield-runtime/ComfyUI/models`. The four selected files total
42,470,585,471 bytes (42.47 GB / 39.55 GiB). Each has a pinned Hugging Face
revision, exact byte count and SHA-256. Interrupted downloads resume. A complete
verified `.part` file is promoted without another download. Free-space checks
account for partial transfers and replacements of corrupt files. Existing
files are hashed before reuse and again before server startup. No Turbo LoRA or Ref2VA weights are
required for this baseline. A failed hash leaves `.part` for inspection.

Keep `--start` running in `tmux` or a supervised session on the server. It listens
on localhost port 8189 so it does not conflict with the template's ComfyUI.
Keep the template's separate ComfyUI instance idle during the test so it does
not compete for GPU memory.
The pinned image's public configuration metadata confirms its CUDA 13 PyTorch
2.10 stack; the image layers and models were not downloaded during local review.
Python package versions are recorded after installation; the image, ComfyUI
revision and model artifacts are pinned, but transitive Python dependencies
are resolved at install time and still require live compatibility validation.

Open the tunnel from the local machine:

```sh
ssh -i .local/runpod_ed25519 -p SSH_PORT -N -L 8188:127.0.0.1:8189 root@SERVER_IP
```

## First actual clip, later

In another local terminal, with the tunnel running:

```sh
python3 -m director doctor --url http://127.0.0.1:8188
python3 -m director preflight --shot 01a
python3 -m director render --shot 01a --run runs/first-clip
```

Shot 01a is the opening: Kramer spots a crypto trader across the street,
Jerry asks “Where?”, and Kramer points out the window. It generates 11.542
seconds at the default 512×384 preview profile and establishes its picture
from text. Supply `--first-frame
path/to/frame.png` if a suitable reference image is available.

Inspect these artifacts in `runs/first-clip/01a/`:

- `clip.mp4`: generated video with audio.
- `contact_sheet.jpg`, `last_frame.png`: visual review aids.
- `workflow.api.json`, `history.json`, `qc.json`: request, execution and technical evidence.

```sh
python3 -m director review --run runs/first-clip --shot 01a --decision accepted --note "Verified dialogue, speakers and identities"
python3 -m director assemble --run runs/first-clip --out runs/first-clip.mp4
```

Record acceptance only after inspecting the result. To try another take:

```sh
python3 -m director render --shot 01a --seed 2002 --run runs/first-clip-take2
```

Use a new directory for changed seeds, prompts, profiles or initial references.
Rerun the **same** command and directory to resume an interrupted job. Pending
submission tokens recover via ComfyUI queue/history; if the server lost that
history, the client stops with an uncertainty error instead of duplicating a
possibly billable job. Completed downloads are checkpointed separately, so a
local contact-sheet or frame-extraction interruption does not require a new
generation. Valid finite polling deadlines also bound HTTP retry waits; poll
timeout does not cancel a server job or stop a Pod.

After the user reviews and approves the opening clip, omit `--shot` to generate
the full plan. Each
continuation uploads the previous clip's last frame; deliberate scene resets
establish new camera blocking or introduce characters. Image continuity does
not preserve an audio latent, so cross-clip voice consistency needs review.
The final edit uses hard cuts without trimming dialogue. Assembly refuses
unreviewed/rejected shots unless `--allow-unreviewed` is explicitly used for a
draft (rejected shots still block). Resuming a run also refuses to reuse a
rejected shot for continuation. Rerendering a continuity dependency requires
rerendering its subsequent continuation shots; don't splice a mismatched take
into an accepted chain without reviewing the following clips.

## Verification boundaries and sources

Offline tests prove local orchestration/media behavior against a protocol
simulator, plus selected contracts from pinned upstream source/templates.
They do not run a model, emulate CUDA, authenticate with RunPod, measure VRAM,
or prove H3 can deliver the desired likenesses, voices and exact dialogue.
`tests/fixtures/object_info.json` is a reduced source-based fixture, **not** a
captured live GPU response. Live `preflight` always uses the real server schema.

Primary references checked September 5, 2026:

- [ComfyUI H3 native workflows and requirements](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)
- [Official ComfyUI model artifacts](https://huggingface.co/Comfy-Org/MiniMax-H3)
- [Official T2V workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_t2v.json)
- [ComfyUI HTTP routes](https://docs.comfy.org/development/comfyui-server/comms_routes)
- [RunPod REST API](https://docs.runpod.io/api-reference/overview)
- [RunPod REST v2 OpenAPI contract](https://api.runpod.io/v2/openapi.json)
- [RunPod ComfyUI deployment](https://docs.runpod.io/tutorials/pods/comfyui)
- [RunPod Pod lifecycle](https://docs.runpod.io/pods/manage-pods)
- [RunPod image tags](https://hub.docker.com/r/runpod/comfyui/tags)

Pinned upstream files under `vendor/` are reference material for offline
contract tests, not imported model code. ComfyUI source retains its upstream
GPL-3.0 license in `vendor/LICENSE`. See `vendor/provenance.json` for revisions
and file hashes. The upload bundle contains only our director, script, plan,
configuration, setup scripts and this README.
