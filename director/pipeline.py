import contextlib
import fcntl
import math
import time
import uuid
from pathlib import Path

from . import media
from .common import DirectorError, ROOT, digest, file_digest, read_json, safe_id, write_json
from .http import APIError
from .plan import FPS, frame_count, select_shots, validate
from .workflow import PROFILES, build, preflight


@contextlib.contextmanager
def run_lock(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / ".lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise DirectorError("Another process is operating this run.") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def fingerprint(plan, profile, seed, shot_id, reference, references=None):
    # Include implementation files, dependencies and image bytes: changed code or
    # prompts cannot silently reuse an accepted clip from an older run.
    return digest({"plan": plan, "profile": profile, "seed": seed, "shot": shot_id,
                   "reference": file_digest(reference) if reference else None,
                   "references": references,
                   "reference_model": read_json(ROOT / "config/reference-model.lock.json") if references else None,
                   "reference_code": file_digest(ROOT / "director/references.py") if references else None,
                   "models": read_json(ROOT / "config/models.lock.json"),
                   "workflow_code": file_digest(ROOT / "director/workflow.py"),
                   "prompt_code": file_digest(ROOT / "director/plan.py")})


def render(plan, client, directory, profile="preview", seed=1001, shot_id=None,
           reference=None, timeout=1800, poll_interval=5, references=None, through=None):
    if any(not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0 for x in (timeout, poll_interval)):
        raise DirectorError("Polling timeout and interval must be finite positive seconds.")
    validate(plan)
    if profile not in PROFILES:
        raise DirectorError("Unknown profile.")
    selected = select_shots(plan, shot_id)
    if through is not None and through not in [s["id"] for s in selected]:
        raise DirectorError("Unknown stopping shot: " + str(through))
    assets = None
    if references:
        from .references import load, load_sequence
        if read_json(references).get("version") == 2:
            assets = load_sequence(references, selected)
            first_assets = assets["shots"][selected[0]["id"]]
            if reference and (len(selected) != 1 or first_assets["anchor_mode"] != "previous"):
                raise DirectorError("A sequence first-frame override is only for one continuation shot.")
            if first_assets["anchor_mode"] == "previous" and not reference:
                raise DirectorError("Selected continuation requires the preceding clip's --first-frame.")
        else:
            if len(selected) != 1 or reference:
                raise DirectorError("Use version 1 references with exactly one shot and no separate --first-frame.")
            assets = load(references, selected[0])
            reference = assets["first_frame"]
    # Catch an invalid seed, missing media executable or reference before any job.
    build(plan, selected[0], seed, "preflight", profile)
    media.executable("ffmpeg")
    media.executable("ffprobe")
    fp = fingerprint(plan, profile, seed, shot_id, reference, assets)
    directory = Path(directory)
    with run_lock(directory):
        state_path = directory / "state.json"
        state = read_json(state_path) if state_path.exists() else {
            "version": 1, "fingerprint": fp, "run_id": "run_" + uuid.uuid4().hex[:16],
            "created_at": time.time(), "shots": {}, "profile": profile,
            "shot_order": [s["id"] for s in selected],
        }
        if state.get("recorded_example"):
            raise DirectorError("Recorded examples are for offline replay. Render into a new run directory.")
        if state["fingerprint"] != fp:
            raise DirectorError("Plan, seed, reference or implementation changed. Use a new run directory.")
        if state.get("comfy_url", client.http.base) != client.http.base:
            raise DirectorError("Run belongs to a different ComfyUI URL; restore the original tunnel/URL.")
        state["comfy_url"] = client.http.base
        write_json(state_path, state)
        write_json(directory / "plan.json", plan)
        previous = None
        for index, shot in enumerate(selected):
            sid = safe_id(shot["id"])
            record = state["shots"].get(sid)
            folder = directory / sid
            folder.mkdir(exist_ok=True)
            clip = folder / "clip.mp4"
            if record and record.get("status") == "complete":
                if record.get("review") == "rejected":
                    raise DirectorError("Shot was rejected: " + sid + ". Prepare another take before continuing this chain.")
                if not clip.exists() or file_digest(clip) != record["sha256"]:
                    raise DirectorError("Saved clip is missing or modified: " + sid)
                previous = clip
                if sid == through:
                    break
                continue
            if record is None:
                anchor = reference if index == 0 else None
                current_assets = assets["shots"][sid] if assets and assets.get("version") == 2 else assets
                fixed_anchor = current_assets and current_assets.get("anchor_mode", "fixed") == "fixed"
                if fixed_anchor:
                    anchor = current_assets["first_frame"]
                elif index and shot["continuity"] == "previous":
                    anchor = folder / "first_frame.png"
                    media.last_frame(previous, anchor)
                remote_image = client.upload(anchor) if anchor else None
                remote_videos = None
                if current_assets:
                    from .references import prepare
                    prepared = prepare(current_assets, folder / "references")
                    write_json(folder / "reference-inputs.json", dict(current_assets, actual_first_frame=str(anchor),
                                                                     actual_first_frame_sha256=file_digest(anchor)))
                    remote_videos = [{"character": r["character"], "video": client.upload_video(r["path"])} for r in prepared]
                graph = build(plan, shot, (seed + index) % 2**64,
                              state["run_id"] + "_" + sid, profile, remote_image, remote_videos)
                preflight(graph, client.info())
                write_json(folder / "workflow.api.json", graph)
                # Persist before POST, including a correlation token for recovery.
                record = {"status": "submitting", "request_id": str(uuid.uuid4()),
                          "seed": (seed + index) % 2**64}
                state["shots"][sid] = record
                write_json(state_path, state)
                try:
                    record["prompt_id"] = client.submit(graph, record["request_id"])
                except APIError as exc:
                    record["status"] = "submission_unknown" if exc.ambiguous else "rejected"
                    write_json(state_path, state)
                    raise
                except DirectorError:
                    record["status"] = "rejected"
                    write_json(state_path, state)
                    raise
                record["status"] = "queued"
                write_json(state_path, state)
            if record["status"] == "rejected":
                raise DirectorError("Submission was rejected. Fix the setup and use a new run directory.")
            if not record.get("prompt_id") and record["status"] not in ("downloaded", "technical_failure"):
                recovered = client.recover(record["request_id"])
                if not recovered:
                    raise DirectorError("Submission state is unknown. No matching job in queue/history; do not automatically resubmit. Inspect the server, then use a new run if it never accepted the job.")
                record.update(prompt_id=recovered, status="queued")
                write_json(state_path, state)
            if record["status"] in ("downloaded", "technical_failure"):
                if not clip.is_file() or file_digest(clip) != record["sha256"]:
                    raise DirectorError("Downloaded clip is missing or modified: " + sid)
            else:
                history_path = folder / "history.json"
                # Download retries can use already persisted history after the
                # server restarts. No new generation is needed.
                entry = read_json(history_path) if history_path.exists() else client.wait(record["prompt_id"], timeout=timeout, interval=poll_interval)
                submitted = entry.get("prompt", [])
                if len(submitted) < 4 or not isinstance(submitted[3], dict) or submitted[3].get("director_request_id") != record["request_id"]:
                    raise DirectorError("Job history belongs to a different request. Verify the server/tunnel before downloading.")
                write_json(history_path, entry)
                client.download(entry, clip)
                record.update(status="downloaded", sha256=file_digest(clip))
                write_json(state_path, state)
            try:
                quality = media.check(clip, frame_count(shot["seconds"]) / FPS, PROFILES[profile][:2])
            except DirectorError as exc:
                quality = {"technical_pass": False, "problems": [str(exc)]}
            write_json(folder / "qc.json", quality)
            record["status"] = "downloaded" if quality["technical_pass"] else "technical_failure"
            write_json(state_path, state)
            if quality["technical_pass"]:
                media.last_frame(clip, folder / "last_frame.png")
                media.contact_sheet(clip, folder / "contact_sheet.jpg")
                record.update(status="complete", review="pending")
            write_json(state_path, state)
            if not quality["technical_pass"]:
                raise DirectorError("Technical checks failed for " + sid + "; inspect qc.json.")
            previous = clip
            if sid == through:
                break
        return state


def review(directory, shot_id, decision, note, required_edit=None):
    if decision not in ("accepted", "rejected") or not note.strip():
        raise DirectorError("Review requires an accepted/rejected decision and a note.")
    with run_lock(directory):
        path = Path(directory) / "state.json"
        state = read_json(path)
        record = state["shots"].get(shot_id)
        if not record or record.get("status") != "complete":
            raise DirectorError("Shot has not completed technical checks.")
        if required_edit is not None:
            from .cuts import keep_ranges
            clip = Path(directory) / shot_id / "clip.mp4"
            if (required_edit.get("source_sha256") != record["sha256"] or
                    file_digest(clip) != record["sha256"] or not required_edit.get("reason")):
                raise DirectorError("Required edit must identify the unchanged source and its reason.")
            keep_ranges(required_edit["keep_frames"], round(media.probe(clip)["duration"] * 24))
            record["required_edit"] = required_edit
        record.update(review=decision, review_note=note, reviewed_at=time.time())
        write_json(path, state)


def assemble_run(directory, output, allow_unreviewed=False):
    with run_lock(directory):
        directory = Path(directory)
        state = read_json(directory / "state.json")
        paths = []
        for sid in state["shot_order"]:
            record = state["shots"].get(sid, {})
            if record.get("status") != "complete":
                raise DirectorError("Incomplete shot: " + sid)
            if record.get("required_edit"):
                raise DirectorError("Shot requires frame edits: use scripts/assemble_episode.py with --cuts.")
            if record.get("review") == "rejected" or (record.get("review") != "accepted" and not allow_unreviewed):
                raise DirectorError("Shot needs creative review: " + sid + ". Use --allow-unreviewed only for a draft.")
            path = directory / sid / "clip.mp4"
            if file_digest(path) != record["sha256"]:
                raise DirectorError("Clip changed since generation: " + sid)
            paths.append(path)
        return media.assemble(paths, output, PROFILES[state["profile"]][:2])
