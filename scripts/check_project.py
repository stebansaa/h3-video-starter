"""Validate a project's inputs and pinned graph contract without an API key."""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from director.common import DirectorError, read_json
from director.plan import load_plan, frame_count
from director.references import load_sequence
from director.workflow import build, preflight, PROFILES


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--plan", default=str(ROOT / "plans/episode-reference-v2.json"))
    p.add_argument("--references", default=str(ROOT / "references/episode-v1/manifest-v2.json"))
    p.add_argument("--profile", choices=PROFILES, default="reference-preview")
    args = p.parse_args()
    plan = load_plan(args.plan)
    assets = load_sequence(args.references, plan["shots"])["shots"]
    schema = read_json(ROOT / "tests/fixtures/object_info_references.json")
    for shot in plan["shots"]:
        refs = [{"character": c["character"], "video": "placeholder.mp4"} for c in assets[shot["id"]]["clips"]]
        preflight(build(plan, shot, 1, "offline", args.profile, "placeholder.png", refs), schema, check_files=False)
    print(json.dumps({"offline_pass": True, "shots": len(plan["shots"]),
                      "seconds_before_editing": sum(frame_count(s["seconds"]) for s in plan["shots"]) / 24,
                      "profile": args.profile, "paid_requests": 0, "model_downloads": 0,
                      "next": "Before rendering, run live preflight with --references against your server."}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (DirectorError, OSError, ValueError, KeyError) as exc:
        raise SystemExit("Project check failed: " + str(exc))
