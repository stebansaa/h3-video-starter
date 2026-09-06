# Troubleshooting and recovery

| Symptom | Check and next action |
| --- | --- |
| New Codex session lacks setup | Start with `scripts/first_session.py` and `docs/first-session.md`. Missing keys/MCP do not block offline preparation. |
| H3 skill is not listed | Read `.agents/skills/h3-video/SKILL.md` explicitly or restart Codex in this checkout. Keep the skill with its repository resources. |
| MCP login works but Python auth fails | MCP OAuth and the Python credential loader are separate. Set this user's API key privately and run `first_session.py --check-auth`; see `docs/codex-mcp.md`. |
| Billing response has no balance, or catalog has no stock | Billing is spending history. Use the minimal GraphQL balance query and explicit catalog availability filters in `docs/runpod-quote.md`. |
| OpenAPI download returns 403 | Use the repository HTTP client or the credential-free curl command in `docs/runpod-quote.md`; plain urllib's default request failed in the live trial. |
| FFmpeg not found | Run `director doctor`; install media tools explicitly or set `FFMPEG` and `FFPROBE` to executable paths. Nothing downloads automatically. |
| Package integrity fails | Restore the named shipped file from the same release. Create personal work under `projects/` instead of editing the baseline. Intentional maintainer changes require a regenerated manifest. |
| Models reported missing | Confirm `--with-references`, the reference lock revision and successful remote downloads. A T2V checkpoint is not the Ref2VA checkpoint. |
| Weight download log is quiet | Inspect remote partial-file sizes, modification times and the owned process. The Xet log can remain quiet while bytes advance; wait for verified completion before starting ComfyUI. |
| Unknown AddGuide or reference input | Compare live `/object_info` with the reference fixture and pinned source. Do not guess a replacement node or install random custom nodes. |
| GPU/RAM/CPU guard fails | Inspect actual container allocation and CUDA torch build. Request a suitable host; do not remove guards to force this stack onto insufficient hardware. |
| Connection refused through tunnel | Check remote setup completion, ComfyUI log, remote loopback 8189, tunnel ownership and local bind port. Setup/model hashing can take time. |
| Uncertain pod creation | Keep the saved `unknown` request state. List pods and match the unique request name before any retry. A dropped response can still have created a billable pod. |
| Uncertain ComfyUI submission | Preserve run state and submission token; inspect queue/history. Resume through the pipeline's recovery. Do not blindly enqueue again after a timeout. |
| Run locked | Inspect the original render process. Reviews mutate state and must wait until the batch ends. Remove a stale lock only after confirming the owner is gone and preserving state. |
| Fingerprint changed | Use a new run for changed plan, seed or assets. Do not edit the fingerprint. Fork only an unchanged reviewed prefix when appropriate. |
| Missing transcript | Preserve the ComfyUI output basename from `history.json`; download ASR files into the exact `--transcripts` directory. Avoid an accidentally nested SCP directory. |
| Stale transcript after edits | Transcribe the actual revised file with a new hash; use a separate output directory for comparison/segment passes. The watcher only notices new basenames, so invoke the transcriber explicitly for changed files. |
| Assembly rejects mandatory edits | Supply the matching `--cuts` manifest. If the boundaries changed, verify them and record `review --cuts` again. Do not erase the requirement. |
| Extra/repeated words | Confirm with source/segment ASR and actual review. Cut only isolated unwanted speech; reroll missing, overlapping or wrong-speaker delivery. |
| Clothes change | Correct the starting image against `image.png`; vague repeated costume text is insufficient. Source clips are identity references, not wardrobe authority. |
| Four-character graph is wrong | Keep image-guide Picture 1 before fourth-character Picture 2; use three paired video/audio references plus the fourth standalone audio. |
| Abrupt laugh join | Request no generated audience, then use the continuous scene mix. Inspect word timing; do not crossfade away dialogue. |
| Resume after stopping temporary pod | Container data is gone. Install on a fresh suitable server, preflight, then use the preserved local run and reference files. Completed local clips can be reused. |

Record each failure and resolution in the current project's progress file.
For a ComfyUI error retain `workflow.api.json`, job history and the relevant
server log without credentials. Tests can establish transport/graph correctness;
they cannot show that a new prompt will produce a good performance.

The detailed original guide is archived at `history/original-technical-guide.md`.
Its paths, private helper assumptions and some commands describe the original
workspace. Current root instructions and runbooks take precedence.
