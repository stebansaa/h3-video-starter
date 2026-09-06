# Standing Room Only — two-shot draft

An independent agent prepared this two-shot Jerry/George scene using only a
clean copy of the repository and its `h3-video` skill. George argues that a
standing desk should charge less rent. The offline plan/reference checks passed;
no new AI footage was generated during that offline trial. A later independent
live test generated only the first shot; see its [preview and review evidence](../standing-desk-preview).
These five draft input files remain unchanged. The full scene has not been rendered.

The requested shots round to 226 and 192 frames at 24 fps: 17.416667 seconds
before editing. The mix adds a 48-frame final hold. Both shots use the included
Jerry/George reference clips. The first uses `window-two-v2.png`; the second
continues from the first generated clip's raw last frame.

Validate the draft from the repository root:

```sh
python3 scripts/check_project.py --plan examples/standing-desk-draft/plan.json \
  --references examples/standing-desk-draft/references.json --profile reference-preview
```

To use it for production, ask Codex to copy these five input files into a new
project under `projects/`, create a current session/progress record and follow
the first-session and RunPod runbooks. Choose a fresh run directory and seed.
Generate only through `01a` for a first-clip-only authorization. The empty cuts
manifest is correct until newly generated footage has been reviewed.

See [the trial record](../../docs/onboarding-trial.json) for the observed checks
and limitations. Its file paths describe the isolated trial workspace; only
the portable draft inputs are retained here.
