"""Create an editable project using the included cast, sets and reference library."""
import argparse
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from director.common import read_json, write_json, safe_id, DirectorError


def create(name, title=None):
    safe_id(name)
    directory = ROOT / "projects" / name
    if directory.exists():
        raise DirectorError("Project exists; choose a new name or continue the existing project.")
    plan = read_json(ROOT / "plans/episode-reference-v2.json")
    plan["id"] = name
    plan["title"] = title or name
    plan["production_notes"] = [
        "This is an editable scaffold. Adapt the copied example script, dialogue and shot/reference/mix IDs before generation.",
        "Tested baseline: reference-preview, 640x384, 24 fps, 20 steps. Higher-resolution profiles require their own preview validation.",
        "Approved starting images govern wardrobe and staging; character clips supply face/voice references.",
        "Matching-angle continuations use the preceding raw last frame. No audio/video latent continuation or LoRA is used.",
    ]
    manifest = read_json(ROOT / "references/episode-v1/manifest-v2.json")
    original = ROOT / "references/episode-v1"
    for ref in manifest["characters"].values():
        ref["path"] = os.path.relpath((original / ref["path"]).resolve(), directory)
    for shot in manifest["shots"].values():
        if shot.get("first_frame"):
            shot["first_frame"] = os.path.relpath((original / shot["first_frame"]).resolve(), directory)
    mix = read_json(ROOT / "plans/episode-mix.json")
    for ref in mix["library"].values():
        ref["path"] = os.path.relpath((ROOT / "plans" / ref["path"]).resolve(), directory)
    directory.mkdir(parents=True)
    write_json(directory / "plan.json", plan)
    write_json(directory / "references.json", manifest)
    write_json(directory / "mix.json", mix)
    write_json(directory / "cuts.json", {"version": 1, "shots": {}})
    write_json(directory / "session.json", {"version": 1, "status": "planning",
        "run": "runs/" + name, "profile": "reference-preview", "seed": 3001,
        "budget_usd": None, "pod_id": None, "preview_through": "01a",
        "next": "Adapt the copied example dialogue and shot plan, then validate. No paid work is authorized by this file."})
    (directory / "script.txt").write_text((ROOT / "script.txt").read_text())
    (directory / "PROGRESS.md").write_text("# " + name + "\n\nPlanning only. The copied script is an example; adapt it before generation.\n"
        "Keep shot IDs aligned across plan, references and mix. Do not reuse recorded-example cuts for new footage.\n")
    return directory


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("name")
    p.add_argument("--title")
    args = p.parse_args()
    try:
        print(create(args.name, args.title))
    except (DirectorError, OSError) as exc:
        raise SystemExit(str(exc))
