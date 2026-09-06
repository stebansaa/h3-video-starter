---
name: h3-video
description: Guide a user through creating, previewing, reviewing and finishing a video with this H3 video starter repository and a remote RunPod or supplied GPU server. Use for first-session setup, adapting its scripts and references, generating shots, continuity, editing or resuming production; not for unrelated video tools or general RunPod administration.
---

# H3 video production

Use this skill from the H3 video starter checkout. Its repository root is three
directories above this skill folder. Keep the skill with the repository: it uses
the shipped scripts, media and guides. Read [AGENTS.md](../../../AGENTS.md) and
[START_HERE.md](../../../START_HERE.md), then only the guides needed for the
current phase. Paths in commands below are relative to the repository root.

## First session

Run `python3 scripts/first_session.py`. It is offline by default. Explain missing
prerequisites and complete authorized local preparation; a missing API key does
not prevent script writing, asset checks or replay. The report does not establish
network permissions, image/audio tools, funding or GPU readiness: inspect the
actual tools available in this session and follow
[first-session setup](../../../docs/first-session.md).

The default workflow uses the shipped Python API client. RunPod MCP is optional.
Do not depend on a previous user's plugins, logins, global skills or remembered
server IDs. If MCP is available or requested, use the
[MCP guide](../../../docs/codex-mcp.md); an MCP OAuth login does not supply the
API credential used by these scripts. Do not copy private Codex configuration.

Run the README's offline tests and recorded replay once for a new checkout.
Replaying existing takes is not new AI generation. The included example state
is an immutable record; generate into a fresh project/run.

## Prepare or resume

Read [new-video planning](../../../docs/new-video.md). For a fresh video, use
`python3 scripts/new_project.py NAME`, adapt the copied script and plan, and keep
references and audience cues aligned with shot IDs. For existing work, inspect
`projects/NAME/session.json`, `PROGRESS.md` and actual run state before acting.
Do not restart completed work or infer new spending permission from old records.

Validate every shot's references before renting. Images control wardrobe and
staging; source clips provide face/voice references. New angles need approved
images. The included prompts and [asset map](../../../docs/assets.md) explain
the original corrections. Use the native workflow builder and the tested
`reference-preview` profile. Preserve its three paired references plus fourth
character face/audio mapping; the starting image stays Picture 1 and frame-zero
AddGuide. Matching-angle continuations use the previous last frame.

## Preview and generation

Follow the [RunPod runbook](../../../docs/runpod-runbook.md). Complete preparation,
then verify API access, current GPU/rate/balance and the user's session budget.
Within an authorized scope, perform routine setup, generation and cleanup without
asking for the same permission again. Keep all model weights/inference on the
remote server and ComfyUI behind the SSH tunnel. Run reference-aware live
preflight; local tests alone cannot establish server readiness.

For preview-only scope, render through the first shot and return that clip for
review. In the baseline this is `--through 01a`; select the actual ID for another
plan. Download evidence and stop the GPU while waiting. Temporary storage is
lost on stop, so follow the selected storage lifecycle. After continuation is
authorized, test a continuity join before a full run. Preserve checkpoints and
completed clips; uncertain paid submissions require reconciliation before retry.

## Review, finish and hand off

Use [quality and editing](../../../docs/quality-and-editing.md) and consult
[production lessons](../../../docs/production-lessons.md) for relevant failures.
H3 can add words during requested silence. Check source and final-track ASR on
the remote server; do not treat ASR as proof of voices or seed it with expected
dialogue. State any inability to listen or inspect images.

Keep raw takes unchanged. Bind required cuts to their source hashes using
`review --cuts`; assemble with the project cut and mix manifests. Continuous
audience/room tone and PCM intermediates handle audio joins. The renderer does
not carry audio latents, train LoRAs or automatically judge creative quality.

Verify the actual final export and its hash. Preserve needed records before
shutdown, confirm stopped/deleted resources within this session's ownership,
and record cost and remaining limitations. Update project progress with the
next concrete action. Deliver a clickable absolute output path. Use
[troubleshooting](../../../docs/troubleshooting.md) for recovery.
