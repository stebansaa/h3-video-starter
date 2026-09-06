# Prepare a new video

Run commands from the repository root. The scaffold keeps the supplied example
immutable and creates an editable project with relative reference paths:

```sh
python3 scripts/new_project.py my-video --title "My scene"
```

`projects/my-video/script.txt` and `plan.json` initially contain the Bitcoin
Contest example. The agent must adapt them to the requested story. This command
does not call an LLM or create a new screenplay automatically.
The scaffold initializes neutral production notes for the tested reference
profile, replacing historical story-specific notes and old quality settings.

## The project contract

| File | What the agent maintains |
| --- | --- |
| `script.txt` | Approved dialogue and action |
| `plan.json` | Shot order, duration, cast, speaker IDs, exact dialogue, blocking and wardrobe |
| `references.json` | Character assets and starting image for each reset |
| `mix.json` | Audience sample library, after-shot cues and ending hold |
| `cuts.json` | Initially empty; reviewed frame edits for newly generated footage |
| `session.json` | Phase, run path, seed, budget, resource IDs, deadline and next action |
| `PROGRESS.md` | Human-readable decisions, completed work, review results and remaining work |

The baseline `plan.json` schema is version 1; the sequence reference manifest
is version 2. Paths in `references.json` and `mix.json` resolve relative to
those files. Keep shot IDs aligned across all three files. For new shots, add
reference entries even when they are `{}` continuations. Remove obsolete
audience cues when removing shots. Keep the reference character keys aligned
with the cast in the plan.

Use 5–15 requested seconds per shot and `director.plan.frame_count` for the
actual duration: H3's frame grid is `17k+5`, at 24 fps. The baseline request totals
116.25 seconds before editing. The density check assumes roughly 2.4 words/sec
plus speaker pauses; it is a planning heuristic, not a promise of delivery speed.

Each character description includes a stable speaker ID, face, voice and
wardrobe. Keep exact dialogue in the `dialogue` array. `action` describes the
camera, blocking and reactions; `state` records clothing and props. Keep the
style/set instructions repeated through the workflow builder. Avoid excessive
empty time: H3 sometimes fills intended silence with extra speech.

## Starting images and cast references

`image.png` governs the example's appearance. Use approved derived images for
new camera angles. Compare clothing pattern, collar, sleeve length, trousers,
hair, accessories, room layout and hand/prop placement against the original.
The included correction prompts show the degree of specificity that was needed.

Set `continuity: "reset"` with a fixed `first_frame` for a new angle. Use
`continuity: "previous"` and an empty reference entry for a matching-angle
continuation. The renderer uploads the previous clip's last frame. A fixed image
can also deliberately override continuity when a shot must be re-established.
All characters need reference clips with useful face coverage and clear speech.
The supplied clips are face/voice references; source clothing and dialogue are
explicitly excluded in the prompt, with imperfect model compliance.

Prepare all shots before generation, including late scenes. Validate offline:

```sh
python3 scripts/check_project.py --plan projects/my-video/plan.json \
  --references projects/my-video/references.json --profile reference-preview
python3 -m director plan --plan projects/my-video/plan.json --profile reference-preview
```

When editing the script, update the plan's `source_sha256` to its actual bytes
and compare the ordered dialogue against the approved script. This field is
provenance; the general plan validator does not parse free-form screenplay text.
The included regression test checks the original script's 43 turns.

## A resumable session

Before spending, add the current authorization and quote to `session.json`:
`budget_usd`, `authorized_scope`, `hourly_rate_usd`, `storage_allowance_usd`,
`authorized_at`, `deadline_epoch`, `pod_state_file` and `owns_disposable_pod`.
Record the actual creation time and pod ID after provisioning. Never record a
secret in this file. A copied number is not authorization by itself.

After each batch, update the phase, accepted/rejected shots, required edits,
ASR evidence, current cost estimate, resource status and next action. Use the
saved `runs/my-video/state.json` as the operational record; do not hand-edit
its fingerprint or completed clip hashes.

Start with `--through 01a` for the copied plan. After preview approval, render
through `01c` to inspect the first same-angle join; `01b` itself resets to a new
interior image. For a different plan, choose equivalent stopping shot IDs.
Then follow the runbook for subsequent batches. New inputs or reroll seeds need
a new run directory. `director.takes.fork_reviewed_prefix` can preserve an
unchanged, accepted prefix; read its function signature before using it.

`projects/`, `runs/` and `output/` are ignored by default. To publish a new
example later, curate its assets and sanitized records into a new directory
under `examples/`, and regenerate the release inventory. Do not commit the
entire private working directory.
