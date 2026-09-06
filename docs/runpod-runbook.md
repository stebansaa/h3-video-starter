# RunPod generation runbook

This is an agent-operated workflow. Local preparation, API orchestration and
editing run in the checkout; H3 and ASR run on a remote Linux NVIDIA GPU server.
On a new host, follow `first-session.md` and run the README's offline checks
first. `codex-mcp.md` documents optional tools; no MCP connection is required
by this Python workflow. Commands below assume project `my-video`;
substitute its actual name and resource values. Never copy resource IDs from an
older session.

## 1. Prepare and quote before renting

Use Python 3.9+ locally, FFmpeg/ffprobe and SSH. Create `.env` from `.env.example`
and enter your own RunPod API key privately. `director.credentials.value` reads
environment variables first, then `.env`, then legacy `key.env`, without sourcing
shell commands. The loader is part of this repository. For a read-only auth check:

```sh
python3 scripts/first_session.py --check-auth --require-server-tools
```

Recheck live GPU availability, price and balance. Follow the copyable read-only
calls in [price, availability and balance](runpod-quote.md); no MCP is needed.
The client uses `https://api.runpod.io/v2`. Its `/billing` endpoint reports
spending history, **not available credit**; the balance query uses RunPod's
documented GraphQL API. Catalog availability requires explicit query parameters.
Never print a complete credential-bearing pod response; `pod-list/get/check`
use the filtered `public_pod` representation.

The successful complete production used a PRO 6000 Blackwell MIG 48 GB instance
at a historical $1.09/hour. A 5090 with 32 GB VRAM is also supported by the
configuration. Select the **exact current GPU ID**, not a guessed marketing name.
Request at least 64 GB system RAM, 8 advertised vCPUs and CUDA 13+. Remote
reference-mode checks allow at least 6 actual cgroup CPU cores; the successful
instance had approximately 6.8. It still requires 32 GB VRAM and 64 GB RAM.

The reference weight download is about 42.47 GB, remotely only. Setup/inference
time, retries and idle review time are billable; an individual clip's inference
time is not the whole cold-start bill. Estimate from the actual hourly quote,
setup allowance and storage, and record a session budget/deadline before creation.
Historical $1.79 for the complete run is evidence, not a current price guarantee.

Choose storage deliberately:

- Default `pod-config` uses 150 GB container disk plus 100 GB persistent storage
  at `/workspace`. This is useful when stopping for a preview and resuming later.
- `--temporary` uses a single 200 GB container disk and no persistent mount,
  matching the completed production. Stopping/restarting loses container data;
  download everything needed before stopping and expect setup again on resumption.
- A network volume can be supplied with `--network-volume-id` and compatible
  `--data-center-id`; it has its own lifecycle and placement. Do not create one
  merely because an earlier example used storage.

RunPod documents these lifetimes in [storage types](https://docs.runpod.io/pods/storage/types).
Stopped persistent storage can remain billable. Deleting a pod deletes its pod
volume; independently managed network volumes require separate ownership-aware cleanup.

## 2. Prepare a concrete request and create within the authorized budget

Create a project SSH key locally (the private directory is ignored):

```sh
mkdir -p .local runs
ssh-keygen -t ed25519 -f .local/h3_ed25519 -N '' -C h3-video-session
python3 scripts/bundle.py --out runs/server-code.tar.gz
python3 -m director pod-config --public-key .local/h3_ed25519.pub \
  --gpu-id 'EXACT_CURRENT_GPU_ID' --out runs/my-video-pod-request.json
python3 -m director pod-create --config runs/my-video-pod-request.json \
  --state runs/my-video-pod.json
```

The last command is a dry run. Review its rate/requirements against the live
quote and the user's authorization. Add `--execute` to the same command only
within that authorized scope. It creates a billable pod. Do not repeat it with
a different state file after an uncertain response; see troubleshooting.

Record the returned pod ID in the session. Set a deadline covering setup and
generation, with reserve for cleanup and storage. Launch the fallback watchdog
locally using an absolute Unix timestamp selected from that budget:

```sh
nohup python3 scripts/watch_pod.py POD_ID --deadline UNIX_TIMESTAMP \
  --state runs/my-video-watchdog.json > runs/my-video-watchdog.log 2>&1 &
```

This is a stop watchdog, not a provider-enforced dollar cap. It needs the local
computer awake and online and the control plane reachable. Active supervision
and verified shutdown remain necessary. A watchdog stop loses temporary disk
data; complete downloads before its deadline.

Poll until ready using these read-only commands:

```sh
python3 -m director pod-get POD_ID
python3 -m director pod-check POD_ID --gpu-id 'EXACT_CURRENT_GPU_ID'
```

Use the returned `ssh.direct.host` and `ssh.direct.port`. Verify the SSH host
key normally; do not disable host-key checking globally. The requested image is
pinned by digest in `config/server.lock.json`, and only SSH is publicly exposed.

## 3. Upload and install on the remote server

Upload the code-only archive (no secrets, weights or media):

```sh
scp -i .local/h3_ed25519 -P SSH_PORT runs/server-code.tar.gz root@SSH_HOST:/workspace/server-code.tar.gz
ssh -i .local/h3_ed25519 -p SSH_PORT root@SSH_HOST
```

Inside that **remote SSH shell**:

```sh
cd /workspace
tar -xzf server-code.tar.gz
cd /workspace/seinfield
python3 --version
python3 scripts/setup_server.py --with-references --check
```

The image must provide Python 3.12+, working CUDA 13+ PyTorch, git, curl, ffmpeg
and ffprobe. If git/curl/media binaries are missing, install those small system
prerequisites on the server before continuing. The setup checks actual GPU,
memory and cgroup CPU allocation before installation or weight downloads.

The code archive contains the runtime and runbooks; it intentionally excludes
the media library and test fixtures. Run offline checks on the full local
checkout. `render` automatically uploads prepared character media and starting
frames through the private ComfyUI connection, so no manual reference upload
is needed. If running the director on the server instead, transfer the full
sanitized repository as well.

Still on the **remote server**, run installation and downloads in a detached
process so a terminal interruption does not kill long setup:

```sh
nohup python3 scripts/setup_server.py --with-references --install \
  --download-models --fast-downloads > /workspace/h3-setup.log 2>&1 &
```

Monitor `/workspace/h3-setup.log` and the process until it finishes successfully.
Do not infer completion from a disconnected SSH session or a quiet log. Setup
can remain quiet while Xet transfers a large file; in the live handoff trial,
growing partial files and recent modification times established progress. Check
remote file sizes/timestamps and the owned setup/download process before
deciding that it has stalled. Do not launch a duplicate download merely because
the log has not changed. Setup
pins ComfyUI, constrains the image's torch packages and records the installed
package inventory. It verifies every model's size and SHA-256. Upstream Python
dependencies can still change; a fresh install plus live preflight is required.
Omit `--fast-downloads` for resumable curl transfers if Xet is unreliable.

After successful setup, start the reference server (also remotely):

```sh
nohup python3 scripts/setup_server.py --with-references --start \
  > /workspace/h3-comfy.log 2>&1 &
```

It listens on `127.0.0.1:8189`, separate from any image-provided ComfyUI service.
The start command verifies the revision and model hashes; startup can take time.
Do not repeatedly start additional copies while the first process is checking.

## 4. Tunnel, preflight and render locally

Back in a **local terminal**, keep this SSH tunnel open while using the director:

```sh
ssh -i .local/h3_ed25519 -p SSH_PORT -N -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 -L 127.0.0.1:8188:127.0.0.1:8189 root@SSH_HOST
```

Use another local terminal/session for commands. Check ownership if local port
8188 is occupied. Choose a different local port and pass the corresponding
`--url` if necessary. Do not expose ComfyUI on a public unauthenticated port.

```sh
python3 -m director preflight --plan projects/my-video/plan.json \
  --references projects/my-video/references.json --profile reference-preview \
  --url http://127.0.0.1:8188
python3 -m director render --plan projects/my-video/plan.json \
  --references projects/my-video/references.json --profile reference-preview \
  --seed 3001 --run runs/my-video --through 01a --url http://127.0.0.1:8188
```

Use the selected seed consistently when resuming. The reference preflight
checks the actual model names, nodes, dynamic inputs and links. An ordinary
`doctor --url` or T2V-only preflight is insufficient for this reference graph.
Render retrieves the MP4, last frame, contact sheet, history and technical QC.
Preview `runs/my-video/01a/clip.mp4` before continuing.

## 5. Review, finish and clean up

Follow `quality-and-editing.md` for server ASR, per-shot review, frame edits and
final assembly. Use later `--through` IDs with the same run to continue approved
batches. Completed outputs are reused. No continuation or full-video spending
is implied by a first-clip-only authorization.

Before waiting for the user, download the clip and supporting files, stop the
GPU and verify `EXITED`. With persistent `/workspace` storage, resume this same
pod later via RunPod's `start` action, start ComfyUI, reopen the tunnel and run
preflight. With temporary storage, prepare a fresh server and continue from
the locally saved run after live preflight.

When GPU work is finished, preserve accepted/rejected takes, transcripts, setup
logs, installed requirements, workflow histories, final export and verification.
Then:

```sh
python3 -m director pod-stop POD_ID
python3 -m director pod-get POD_ID
```

Poll until `EXITED`. For a disposable pod created by this session, delete it
after downloads and confirm removal. The client can make the REST v2 delete
without placing the API key in shell arguments; run from the local root only
after verifying that `runs/my-video-pod.json` is this session's owned pod:

```python
from director.common import read_json
from director.credentials import value
from director.runpod import RunPod
from urllib.parse import quote

record = read_json("runs/my-video-pod.json")
pod_id = record["pod"]["id"]
client = RunPod(value("RUNPOD_API_KEY"))
assert client.get(pod_id)["status"] == "EXITED"
client.http.request("DELETE", "/pods/" + quote(pod_id, safe=""))
```

Confirm a subsequent GET returns 404 or the ID is absent from `pod-list`. Never
delete a saved pod/volume belonging to another session. Close only this session's
tunnel/watchdog after checking process ownership. Record cleanup confirmation,
elapsed allocation and costs in the project progress file.
