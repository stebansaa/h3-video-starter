"""Explicitly reuse a reviewed prefix when revising later shots."""
import copy
import shutil
import time
import uuid
from pathlib import Path

from .common import DirectorError, file_digest, read_json, write_json
from .pipeline import fingerprint, run_lock
from .plan import prompt_for, validate
from .references import load_sequence


def fork_reviewed_prefix(source, destination, plan, references, through, seed=1001):
    """No API calls. Refuse reuse if dialogue, prompt or reference bytes changed.

    Only a contiguous reviewed prefix is kept; all dependent later shots are
    generated anew. Original runs and rejected takes remain intact.
    """
    validate(plan)
    assets = load_sequence(references, plan["shots"])
    ids = [s["id"] for s in plan["shots"]]
    if through not in ids:
        raise DirectorError("Unknown prefix end.")
    keep = ids[:ids.index(through) + 1]
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        raise DirectorError("Fork destination already exists.")
    with run_lock(source):
        old = read_json(source / "state.json")
        old_plan = read_json(source / "plan.json")
        if old["shot_order"][:len(keep)] != keep:
            raise DirectorError("Reused shots must be the same ordered prefix.")
        old_shots = {s["id"]: s for s in old_plan["shots"]}
        records = {}
        for shot in plan["shots"][:len(keep)]:
            sid = shot["id"]
            record = old["shots"].get(sid, {})
            if record.get("status") != "complete" or record.get("review") != "accepted":
                raise DirectorError("Reused shot must be reviewed and accepted: " + sid)
            if prompt_for(plan, shot) != prompt_for(old_plan, old_shots[sid]):
                raise DirectorError("Prompt changed for reused shot: " + sid)
            clip = source / sid / "clip.mp4"
            if file_digest(clip) != record["sha256"]:
                raise DirectorError("Reused clip was modified: " + sid)
            before = read_json(source / sid / "reference-inputs.json")
            after = assets["shots"][sid]
            for key in ("first_frame_sha256", "clips", "anchor_mode"):
                if before.get(key) != after.get(key):
                    raise DirectorError("References changed for reused shot: " + sid)
            records[sid] = dict(copy.deepcopy(record), adopted_from=str(source / sid))
        state = {"version": 1, "fingerprint": fingerprint(plan, old["profile"], seed, None, None, assets),
                 "run_id": "run_" + uuid.uuid4().hex[:16], "created_at": time.time(),
                 "shots": records, "profile": old["profile"], "shot_order": ids,
                 "comfy_url": old["comfy_url"], "forked_from": str(source), "base_seed": seed}
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.mkdir()  # exclusive; never replace an existing run
        write_json(destination / "state.json", {"fingerprint": "fork_in_progress"})
        for sid in keep:
            shutil.copytree(source / sid, destination / sid)
            if file_digest(destination / sid / "clip.mp4") != records[sid]["sha256"]:
                raise DirectorError("Copied clip failed checksum.")
        write_json(destination / "plan.json", plan)
        write_json(destination / "state.json", state)
    return state
