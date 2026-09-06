# H3 video starter

[![Offline verification](https://github.com/stebansaa/h3-video-starter/actions/workflows/offline.yml/badge.svg)](https://github.com/stebansaa/h3-video-starter/actions/workflows/offline.yml)

A working example and an agent runbook for making short videos with native
MiniMax H3 on a remote RunPod GPU. Clone this folder, open a Codex session in it,
and read [AGENTS.md](AGENTS.md). The local tools use Python's standard library,
FFmpeg and ffprobe; model weights stay on the remote server.

**Start by watching [the completed example](examples/bitcoin-contest/final.mp4).**
It is a 97.21-second scene made from 14 generated shots. This repository includes
the original script, four character reference clips, all starting images,
laughter samples, raw takes, reviewed cuts, transcripts and final export.

A separate [fresh-agent live test](docs/live-handoff-trial.md) also generated
[this new first-clip preview](examples/standing-desk-preview/preview.mp4) using
only the repository's instructions. Its raw take, detected dialogue issue,
corrective edit, runtime evidence and cleanup record are included.

## Give Codex this instruction

Paste this into a new Codex session:

> Clone https://github.com/stebansaa/h3-video-starter, enter the repository
> and read AGENTS.md and START_HERE.md.
> Use the included h3-video skill. Run scripts/first_session.py and help me
> resolve any missing setup. Read its SKILL.md directly if it is not listed.
> Run the offline checks and reproduce the included edit first. Then help me
> make a new video about [MY IDEA], using the included cast and visual style.
> Prepare the script, references and first-shot plan before renting a GPU.
> Show me a current cost estimate. My initial GPU budget is [AMOUNT] USD.
> Generate only the first clip for my review before continuing. Keep model
> weights on the remote server, and stop the GPU while waiting for me.

The agent needs terminal, network and SSH access for a new GPU render. The
repository provides direct commands and a local `h3-video` skill; a RunPod
plugin is optional. [First-session setup](docs/first-session.md) explains what
must be checked on a new host, and [MCP setup](docs/codex-mcp.md) explains that
optional connection and its separate authentication. The script
writing and creative review are performed by the agent/user, not an autonomous
script-writing service hidden in this package.

## Try it without API keys

From the repository root, with Python 3.9+ and FFmpeg/ffprobe installed. Local
commands assume macOS or Linux; a Windows host needs a suitable Linux shell.
The remote ComfyUI installation requires Python 3.12+.

```sh
python3 scripts/first_session.py
python3 scripts/verify_package.py
python3 -m unittest discover -s tests -v
python3 scripts/check_project.py
python3 scripts/replay_example.py
```

If media tools are missing, run `python3 scripts/install_test_media.py` first.
That explicitly downloads FFmpeg executables into `.venv`; it does not download
AI models. Offline replay writes `output/replayed-example.mp4`. It rebuilds the
edit from recorded takes, including all seven mandatory edits and ten audience
cues. Re-encoding/mixing can change the file hash, including between repeat
runs; byte-identical output is not a readiness requirement. The recorded final
export remains included unchanged.

To prepare a separate editable project:

```sh
python3 scripts/new_project.py my-video --title "My new scene"
```

This copies the example plan and script as a starting point. Adapt them before
generation. Your working files live in `projects/my-video`, which is ignored by
Git along with credentials, new runs and output. The included reference media
and recorded example **are tracked by Git**; no model files or Git LFS pointers
are needed to replay the example.

## Where to go next

| File | Purpose |
| --- | --- |
| [START_HERE.md](START_HERE.md) | Human and Codex onboarding |
| [docs/first-session.md](docs/first-session.md) | Prerequisite checks and guided setup on a new host |
| [docs/codex-mcp.md](docs/codex-mcp.md) | Optional MCP connection, credentials and skill discovery |
| [docs/runpod-runbook.md](docs/runpod-runbook.md) | Credentials, budget, server setup, rendering and cleanup |
| [docs/runpod-quote.md](docs/runpod-quote.md) | Verified direct API calls for price, stock and account balance |
| [docs/new-video.md](docs/new-video.md) | Script, shot planning, references and resumable sessions |
| [docs/quality-and-editing.md](docs/quality-and-editing.md) | Review, ASR, exact cuts, sound continuity and delivery |
| [docs/production-lessons.md](docs/production-lessons.md) | Detailed lessons from the completed production |
| [docs/assets.md](docs/assets.md) | Exact assets, provenance and superseded images |
| [docs/production-record.md](docs/production-record.md) | Historical settings, results, cost and limitations |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Recovery and common failure modes |
| [docs/release-checks.json](docs/release-checks.json) | Results of the clean-clone verification |
| [docs/onboarding-trial.json](docs/onboarding-trial.json) | Independent agent handoff trial and observed gaps |
| [examples/standing-desk-draft](examples/standing-desk-draft) | Validated two-shot draft; first-shot live test available separately |
| [docs/live-handoff-trial.md](docs/live-handoff-trial.md) | Fresh-agent generation, observed gaps, fixes and review limitations |
| [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) | Source and license scope |

The tested path is native Ref2VA plus a starting-image guide at 640×384,
24 fps and 20 steps. It uses last-frame continuity between matching angles.
It does not use a LoRA, Context Loop or continuing audio/video latents.
Offline checks validate the code and recorded edit. Fresh model output still
needs a paid preview and creative review; identical seeds do not guarantee
identical performance on different hardware or software.
