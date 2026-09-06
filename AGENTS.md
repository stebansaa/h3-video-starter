# Instructions for the video production agent

Read `START_HERE.md`, then the relevant runbook before acting. Use the repository
skill `.agents/skills/h3-video/SKILL.md` for this workflow; if it is not listed,
read it directly. These instructions
apply throughout this repository. User instructions and current session
authorization take precedence. The included historical production is evidence,
not current permission to spend money or operate someone else's resources.

## Establish the current state

- On a new host, run `python3 scripts/first_session.py` and follow
  `docs/first-session.md` to resolve missing prerequisites. Confirm the actual
  session's file/terminal/network and creative tools separately. The default
  check is offline; `--check-auth` verifies RunPod read access only.
- Work from this repository root. Read `projects/NAME/session.json` and
  `PROGRESS.md` if a project exists; inspect actual run state before resuming.
- The final included example is `examples/bitcoin-contest/final.mp4`. Preserve
  `examples/`, the reference library, the baseline plans and `script.txt`.
  Make new work with `python3 scripts/new_project.py NAME`.
- Run the offline quickstart in `README.md` before the first new production.
  Read `docs/production-record.md` and `docs/production-lessons.md` for what was
  actually measured and what remains uncertain.
- `docs/live-handoff-trial.md` records a fresh-agent first-clip test and the
  resulting guide fixes. Its budget and cleanup records are historical evidence.
- The historical HappyHorse instruction at the bottom of `script.txt` is not
  part of this implementation. Preserve spoken dialogue; H3 is the renderer.

## Preparation and infrastructure

- Never download or run H3 or ASR weights on the user's local computer. Use the
  provided remote Linux NVIDIA server. Local FFmpeg editing is supported.
- Finish the script, shot plan, references, offline validation and upload
  preparation before renting a GPU. Follow `docs/new-video.md`.
- Follow `docs/runpod-runbook.md` for a fresh live price/availability check,
  explicit session budget, private SSH tunnel, hardware checks and shutdown.
  Do not infer today's costs or balance from historical reports.
- The public credential loader reads the process environment, `.env`, then
  legacy `key.env`. Never print credentials or include them in archives or Git.
  No private helper from another checkout is required.
- MCP and external RunPod skills are optional; the Python client is complete
  for this workflow. See `docs/codex-mcp.md` for optional connection setup and
  the distinction between MCP OAuth, process environment and our `.env` loader.
- Use the pinned reference revision with `--with-references`. A generic
  ComfyUI installation does not establish this graph's required contract.
  Run live `preflight --references ...` before generation. Do not invent graphs.
- Use `reference-preview` (640×384/24 fps/20 steps) as the tested baseline.
  Higher resolution and alternative continuity methods are experiments.

## Continuity and generation

- Starting images govern wardrobe, props and staging; character clips govern
  identity/voice references. Inspect all image changes before paid rendering.
  Read the exact reference mapping in `docs/assets.md`.
- Retain the order in `shot.characters`: three paired video/audio slots, then
  a fourth character's face image and standalone audio. The opening image is
  Picture 1 and a frame-zero AddGuide; the fourth character image is Picture 2.
- Use the preceding raw last frame only for a matching camera angle. Use a
  fixed approved starting image for a new angle. No audio latent crosses clips.
- Start with the first clip using `--through 01a`; show it for review. Test a
  subsequent join (through `01c` in the example) before committing to a full
  production. Obey a user's existing preview/full-render authorization.
- Resume the same run with unchanged inputs. Never overwrite accepted raw
  footage, remove an active lock, edit a fingerprint or blindly repeat a paid
  POST after an uncertain response. See recovery instructions.
- Update session progress, resource ownership, budget deadline, run paths,
  review decisions and the next action so another session can continue.

## Review and delivery

- Follow `docs/quality-and-editing.md`. Silence prompts are unreliable: seven
  of fourteen recorded source takes needed edits for added or repeated speech.
- Inspect visual continuity and actual dialogue. Remote `small.en` ASR helps,
  but can miss quiet words and misrecognize names. Use an independent segment
  pass for ambiguity. Never supply desired text as an ASR prompt and call that
  independent verification. Do not claim to have listened if audio is unavailable.
- Preserve raw clips. Bind mandatory frame edits to source SHA-256 using
  `review --cuts`. Deliver with `scripts/assemble_episode.py --cuts ... --mix ...`.
  The plain assembler rejects sources that have required edits.
- Mix audience on one scene timeline, with fades, dialogue ducking and room
  tone. Use PCM intermediates and encode the final audio once. Laughs may span
  picture cuts. Do not hide unwanted speech under laughter.
- Recheck the final mixed track, full decode, frame count, dimensions, stereo,
  duration agreement, peaks and ending. Record the hash of the actual delivery.
  Technical pass alone does not establish correct acting, lip sync or voices.
- Download all needed evidence before stopping ephemeral storage. Stop and
  confirm EXITED, then delete only disposable resources owned by this session
  when their use is complete. Storage can remain billable after GPU shutdown.
- Give the user an absolute clickable path to the final export plus an honest
  quality summary and measured session cost. Do not substitute an older draft.
