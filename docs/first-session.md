# First session on a new person's computer

This guide connects the repository instructions to the tools actually available
in the new Codex session. The repository includes its own skill and direct API
client. It does not transfer another person's plugins, logins or permissions.

## 1. Load the project instructions

Open the cloned folder in Codex, or enter it in a terminal before starting
Codex. Ask it to read `AGENTS.md`, `START_HERE.md` and use `$h3-video`.
The skill is shipped at `.agents/skills/h3-video/SKILL.md` and links to the
operating guides. It works from this repository without a separate global
installation. Keep it with the repository; copying only the skill folder loses
its code, guides and assets.

Codex discovers repository skills under `.agents/skills`. If the skill does not
appear, restart in the clone or explicitly ask Codex to read that `SKILL.md`
file and follow it. If cloning during an existing chat, explicitly read the
root instructions; instruction discovery occurs at session startup.
[Skills documentation](https://learn.chatgpt.com/docs/build-skills),
[AGENTS.md documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

The prompt to give a fresh session is:

> Read AGENTS.md and START_HERE.md. Use the repository's h3-video skill, or read
> .agents/skills/h3-video/SKILL.md explicitly if it is not listed. Check this
> environment and guide me through any missing setup. Prepare a new video about
> [IDEA] using the included cast. Complete the offline checks first. Give me a
> current estimate before paid work; my initial GPU budget is [AMOUNT] USD.
> Generate only the first clip for my review, and stop the GPU while waiting.

## 2. Inspect local prerequisites without a key

Use a local Codex client with workspace/terminal access, or a supplied development
environment that supports the same operations. A chat that can only discuss
files cannot run this workflow. Check actual capabilities rather than assuming
every Codex client exposes the same tools:

| Capability | Agent action if unavailable |
| --- | --- |
| Read/write project files and execute commands | Help the user open the clone in a Codex environment with terminal access |
| Network and SSH permitted by that environment | Resolve its actual access restriction before connecting to RunPod; do not disable safeguards globally |
| Inspect images | Arrange user review of contact sheets/starting images if the agent cannot inspect them |
| Generate/edit starting images | Reuse included approved assets when suitable, or obtain new images through available image tools/user-provided files |
| Listen to/watch previews | Have the user review playback; report the limits of ASR and frame-only review |
| RunPod MCP tools | Optional: continue with the shipped Python API client, or follow the MCP guide when that route is requested |

Run from the clone root:

```sh
python3 scripts/first_session.py
```

The default command checks Python, OS, release integrity, FFmpeg/ffprobe,
git/SSH transfer tools and whether an API key is configured. It makes no network
requests, installs nothing and never prints credentials. The local client needs
Python 3.9+; remote ComfyUI needs Python 3.12+. If Python itself is missing,
install it using the user's normal system setup first.

An exit code of 0 means **local offline prerequisites passed**, not permission
or readiness to rent a GPU. Missing RunPod credentials do not block offline work.
Use `--json` for a structured report or `--require-server-tools` when checking
that git/SSH transfer prerequisites are also present. Agent permissions and
image/audio capabilities are listed as separate checks because this script
cannot inspect the active Codex tool list.

If FFmpeg/ffprobe are missing, follow the reported install step. The included
`python3 scripts/install_test_media.py` explicitly installs media binaries into
`.venv`; it never installs model weights. Then rerun the first-session check.

Next run the README's test, reference-validation and replay commands. All should
work without a RunPod key or MCP. The replay is an existing-media edit, not a new
AI video. Create the new project and adapt its script/reference plan as described
in `new-video.md` while account setup is pending.

## 3. Connect this user's account only when needed

For a new RunPod render, provide the [RunPod settings link](https://console.runpod.io/user/settings)
so the user can open it in their chosen browser and obtain their own API key.
Store it privately in `.env`, copied from `.env.example`. Do not ask them to
paste it into chat, expose it in shell arguments, or commit it. The loader also
supports `RUNPOD_API_KEY` in the process environment and legacy `key.env`.

When the key is in place, run:

```sh
python3 scripts/first_session.py --check-auth --require-server-tools
```

This adds one authenticated, read-only `GET /pods` and suppresses returned account
and resource details. A pass proves read access only. It does not prove funding,
write permission, GPU availability, SSH reachability or live model readiness.
The command creates no resources and downloads no models.

The next agent actions are to [check the current rate, balance and available GPU](runpod-quote.md);
record the user's budget and scope; prepare the concrete pod request; then follow
`runpod-runbook.md` through remote hardware checks, installation, live reference
preflight and the authorized preview. A provided suitable server can skip RunPod
account/provisioning steps and use its own SSH access.

MCP is optional. The separate [MCP guide](codex-mcp.md) explains how to connect it
and why a successful MCP login does not automatically authenticate our Python
commands. No plugin installation or Codex configuration change is performed by
the first-session script.

## 4. Leave a useful handoff

Record which prerequisites passed, actual available creative tools, account
auth status, project/run paths, budget scope and next action in the project's
progress file. Record failures and resolutions without secrets. Keep an explicit
preview checkpoint: opening the first MP4 for the user is part of the process.
Use the storage-specific stop/download instructions before waiting for review.

The release checks exercise code and recorded media in an isolated checkout.
They do not establish that every fresh Codex host will have the same permissions,
or that fresh model output will have the same acting quality. The live acceptance
test is a new small preview after those host/account checks.
