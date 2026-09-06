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

## 1. Have these tools ready

Use a local terminal on macOS or Linux, with Git and Python 3.9+ installed.
On Windows, use a Linux environment such as WSL for these commands. You also
need Codex with access to the project files and terminal; remote generation
requires network and SSH access. Your computer does not need an NVIDIA GPU.
Codex can help install FFmpeg/ffprobe during the offline setup below.

If you do not have the Codex CLI, follow the
[official installation guide](https://learn.chatgpt.com/docs/codex/cli).
Its macOS/Linux installation command is:

```sh
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

Reopen your terminal if instructed by the installer. RunPod account setup can
wait until after the script discussion and offline preparation.

## 2. Clone the repository and enter it

Run these commands in your terminal:

```sh
git clone https://github.com/stebansaa/h3-video-starter.git
cd h3-video-starter
```

All commands below run from this directory. The public clone includes the code,
instructions and reference media; it does not download model weights.

## 3. Create your script file

The original, complete script is included as [script.txt](script.txt). To use it
as your default, make an editable project copy:

```sh
python3 scripts/new_project.py my-video --title "My video"
```

This creates `projects/my-video/script.txt` containing the original script,
alongside the planning files Codex will maintain. Run this once per project;
if `my-video` already exists, continue using it or choose a different name.

Open **`projects/my-video/script.txt`** in any plain-text editor. For example:

```sh
nano projects/my-video/script.txt
```

In nano, save with Ctrl+O, Enter, then exit with Ctrl+X. You can leave the
example as-is, change its dialogue and scenes, or replace its entire contents.
If you already wrote your script elsewhere, copy that file into the project
(replace the quoted source path with your own):

```sh
cp "/absolute/path/to/my-script.txt" projects/my-video/script.txt
```

Include as much of the following as you know; Codex can help fill in gaps:

- The title, premise, approximate length and visual style.
- The characters, locations, wardrobe and props that must remain consistent.
- Each scene's action, exact dialogue labeled by speaker, and reaction pauses.
- Camera ideas, starting images or reference-clip paths you want to use.
- Sound and laughter preferences, the ending, and anything that must not change.

Plain text is enough; you do not need to write JSON or a ComfyUI workflow.
Save it as a `.txt` file, not a rich-text document. Your project copy is ignored
by Git, while the root `script.txt` remains the unchanged example used by the
release checks. Keep new personal reference files under your project as well.

The original script mentions **HappyHorse, 720p and 4:3**. Those are historical
production directions. This repository's tested preview uses **MiniMax H3 at
640×384, 24 fps and 20 steps**. Codex should discuss any requested format change
and split dense dialogue into workable shots, preserving your approved lines.
The included cast and sets already have reference assets; new characters or
locations may require new clips and starting images before generation.

## 4. Start Codex and point it to your script

Still in `h3-video-starter`, start Codex:

```sh
codex
```

On first launch, complete the offered sign-in flow. Then paste the following
**into Codex**, not into your shell. Change `my-video` if you chose another name:

> Read AGENTS.md and START_HERE.md. Use the included h3-video skill; if it is
> not listed, read .agents/skills/h3-video/SKILL.md directly.
> My project is projects/my-video and my script is
> projects/my-video/script.txt. Read the entire script and use that file as
> the source for the video. The project already exists; preserve my edits.
> First summarize the intended video and discuss the script, timing, cast,
> references and any unclear or conflicting directions with me.
> Run scripts/first_session.py, help resolve missing setup, and run the
> offline checks and recorded-example replay. Once we agree on the script,
> update this project's shot plan, references and sound plan to match it.
> Guide me through RunPod account, API-key and credit setup when needed.
> Show me a current estimate for setup plus the first clip before paid work.
> Do not rent a GPU or generate paid assets until I approve a budget and scope.
> Keep all model weights on the remote server.

If you use the Codex desktop app, open the cloned `h3-video-starter` folder and
paste the same prompt. If Python/setup prevented step 3, start Codex anyway and
ask it to resolve that prerequisite and create the project before you edit it.

**Editing the text file alone does not change what the renderer generates.**
Codex must translate the agreed script into `projects/my-video/plan.json` and
keep references and sound cues aligned. The renderer consumes that plan. Ask
Codex to compare its planned dialogue with your text before the first render.
If you change the script later, tell Codex to reread it and update the plan.

## 5. Set up RunPod with Codex

RunPod supplies the remote GPU. The repository's Python client lets Codex
create and operate the pod, install the pinned H3 setup, submit shots, download
results and shut it down. You can let Codex handle those steps through the
[RunPod runbook](docs/runpod-runbook.md) after agreeing on a budget.

1. Open the [RunPod console](https://console.runpod.io/) in your preferred
   browser and create or sign in to your own account.
2. Open **Settings → API Keys → Create API Key**. The key needs access to read
   and manage Pods, including creation, stopping and cleanup; a read-only or
   Serverless-only key is insufficient. Have Codex guide you through the
   current permission choices using the
   [official API-key guide](https://docs.runpod.io/get-started/api-keys).
3. Ask Codex to create `.env` from `.env.example` **only if `.env` does not
   already exist**. Open `.env` privately in your editor and put your key after
   `RUNPOD_API_KEY=`. Save it, then tell Codex, “The key is in .env.” Keep the
   key out of chat, script files and Git. This file is already ignored by Git.
4. Ask Codex to run `python3 scripts/first_session.py --check-auth --require-server-tools`.
   This makes a read-only account check and creates no pod. A successful read
   does not establish write permissions, available funds or GPU readiness.
5. Have Codex check current availability and quote the **whole first-preview
   session**: GPU setup/download time, generation, review work, storage and a
   retry allowance. Open **Billing** in RunPod and add sufficient credits for
   that plan. [RunPod billing](https://docs.runpod.io/accounts-billing/billing)
   explains credit requirements. Your Codex usage is billed separately from
   RunPod; topping up one does not fund the other.

No separate MiniMax API key is needed for this self-hosted workflow. RunPod MCP
and plugins are optional; the included direct Python API path is sufficient.
See [MCP setup](docs/codex-mcp.md) if you choose to connect one. A plugin's OAuth
login does not automatically supply the key this project's Python client uses.

Before creation, Codex should explain the chosen GPU and storage plan. The
reference weights take about **42.47 GB on the remote server**, plus runtime and
working space. For a preview followed by a later full render, persistent storage
can retain setup between sessions, with ongoing storage charges. Temporary
container storage is lost on stop and requires setup again. See
[RunPod storage lifetimes](https://docs.runpod.io/pods/storage/types).

If you already have a suitable remote Linux NVIDIA server, give Codex its SSH
connection details instead; it can follow the remote setup portion of the
runbook without creating a new RunPod pod.

## 6. Approve one preview, review it, then continue

After Codex has presented a current estimate, replace the amount and paste:

> Proceed with projects/my-video. I approve up to [AMOUNT] USD of RunPod
> spending for setup, the first-clip preview and cleanup. Generate only the
> first clip. Use the agreed script and references, download the clip and
> review records, and stop the GPU before waiting for my feedback. Confirm
> shutdown, report the session cost and any remaining storage charges, and
> give me the local video path so I can watch it.

Codex should handle SSH, remote model installation, live workflow checks and
the render within that scope. Watch and listen to the preview for dialogue,
voices, performance, clothing and image quality. H3 generates picture and audio
together; the review may identify unwanted speech that needs a cut or a new take.

Once the preview looks right, discuss an updated budget for a continuity sample
and the remaining video. Tell Codex explicitly when to proceed. It should reuse
accepted takes, test a join between clips, keep wardrobe consistent, and mix
laughter across the complete scene. The first-preview budget does not authorize
the whole video. After delivery, verify that the session's GPU is stopped and
that any retained storage and its ongoing cost are intentional.

To resume another day, start Codex in this repository and say:

> Read AGENTS.md, projects/my-video/PROGRESS.md and session.json in that
> project. Reread projects/my-video/script.txt and inspect the saved run.
> Tell me what is complete, what remains, and whether any resource is still
> running or incurring storage charges before taking a paid action.

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

Your working files live in `projects/my-video`, which is ignored by Git along
with credentials, new runs and output. The included reference media
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
