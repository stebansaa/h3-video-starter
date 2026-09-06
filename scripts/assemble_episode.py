"""Assemble reviewed episode clips with audience cues on the scene timeline."""
import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from director.common import DirectorError, read_json, write_json, file_digest
from director.edit import assemble_scene
from director.media import probe
from director.pipeline import run_lock
from director.workflow import PROFILES
from director.cuts import cut_clip, keep_ranges, retained_transcript


def word_error(expected, actual):
    def words(text):
        return re.findall(r"[a-z0-9']+", text.lower().replace("’", "'"))
    a, b = words(expected), words(actual)
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        nxt = [i]
        for j, y in enumerate(b, 1):
            nxt.append(min(nxt[-1] + 1, row[j] + 1, row[j - 1] + (x != y)))
        row = nxt
    return row[-1] / max(1, len(a))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--transcripts", default=str(ROOT / "reports/episode-transcripts"))
    p.add_argument("--through")
    p.add_argument("--no-audience", action="store_true")
    p.add_argument("--cuts", help="Reviewed frame ranges to retain, bound to source clip hashes")
    p.add_argument("--mix", help="Project audience library and after-shot cues; paths relative to this file")
    p.add_argument("--end-hold-frames", type=int, help="Override the mix's final reaction hold, at 24 fps")
    args = p.parse_args()
    directory = Path(args.run)
    with run_lock(directory), tempfile.TemporaryDirectory(prefix="episode-cuts-") as temporary:
        state = read_json(directory / "state.json")
        plan = read_json(directory / "plan.json")
        shots = {s["id"]: s for s in plan["shots"]}
        order = state["shot_order"]
        mix = read_json(args.mix) if args.mix else {"version": 1, "library": {}, "after_shots": {}}
        if mix.get("version") != 1 or not isinstance(mix.get("library"), dict) or not isinstance(mix.get("after_shots"), dict):
            raise DirectorError("Unsupported audience mix configuration.")
        if set(mix["after_shots"]) - set(order):
            raise DirectorError("Audience cue names an unknown shot.")
        mix_root = Path(args.mix).resolve().parent if args.mix else ROOT
        end_hold = args.end_hold_frames if args.end_hold_frames is not None else mix.get("end_hold_frames", 0)
        edits = read_json(args.cuts) if args.cuts else {"version": 1, "shots": {}}
        if edits.get("version") != 1 or not isinstance(edits.get("shots"), dict):
            raise DirectorError("Unsupported frame edit manifest.")
        if set(edits["shots"]) - set(order):
            raise DirectorError("Frame edit names an unknown shot.")
        if args.through:
            if args.through not in order:
                raise DirectorError("Unknown stopping shot.")
            order = order[:order.index(args.through) + 1]
        paths, cues, report, source_records = [], [], [], []
        offset = 0.0
        reactions = mix["after_shots"]
        for sid in order:
            record = state["shots"].get(sid, {})
            if record.get("status") != "complete" or record.get("review") != "accepted":
                raise DirectorError("Shot is incomplete or unreviewed: " + sid)
            clip = directory / sid / "clip.mp4"
            if file_digest(clip) != record["sha256"]:
                raise DirectorError("Clip changed after review: " + sid)
            duration = probe(clip)["duration"]
            history = read_json(directory / sid / "history.json")
            outputs = history["outputs"]["14"]
            files = outputs.get("images") or outputs.get("videos") or []
            if not files:
                raise DirectorError("Missing server output metadata for " + sid)
            transcript_path = Path(args.transcripts) / (Path(files[0]["filename"]).stem + ".json")
            transcript = read_json(transcript_path)
            original = clip
            edit = edits["shots"].get(sid)
            if record.get("required_edit") and edit != record["required_edit"]:
                raise DirectorError("Mandatory reviewed frame edit missing or changed: " + sid)
            source_record = {"shot": sid, "path": str(original.resolve()), "sha256": record["sha256"]}
            if edit:
                if edit.get("source_sha256") != record["sha256"] or not edit.get("reason"):
                    raise DirectorError("Frame edit lacks matching source hash or review reason: " + sid)
                ranges = keep_ranges(edit["keep_frames"], round(duration * 24))
                clip = Path(temporary) / (sid + ".mov")
                cut_clip(original, clip, ranges, edit["source_sha256"])
                duration = sum(b - a for a, b in ranges) / 24
                transcript = retained_transcript(transcript, ranges)
                source_record.update(keep_frames=ranges, reason=edit["reason"], edited_sha256=file_digest(clip))
            source_record["seconds"] = duration
            source_records.append(source_record)
            expected = " ".join(d["text"] for d in shots[sid]["dialogue"])
            last_word = max((w["end"] for s in transcript["segments"] for w in s["words"]), default=duration)
            report.append({"shot": sid, "expected": expected, "transcript": transcript["text"],
                           "uncut_transcript": transcript.get("source_text", transcript["text"]),
                           "word_error_rate": word_error(expected, transcript["text"]),
                           "start": offset, "seconds": duration, "last_recognized_word_end": last_word})
            if not args.no_audience and sid in reactions:
                kind = reactions[sid]
                cue = mix["library"].get(kind)
                if not isinstance(cue, dict):
                    raise DirectorError("Unknown audience sample: " + str(kind))
                # Leave the whole spoken line intact; the laughter stem may
                # continue into the next picture and ducks under its dialogue.
                at = offset + min(duration - 0.1, last_word + 0.16)
                cues.append({"path": str((mix_root / cue["path"]).resolve()),
                             "at": at, "seconds": cue["seconds"], "after_shot": sid,
                             "gain_db": cue.get("gain_db", 0)})
            paths.append(clip)
            offset += duration
        quality = assemble_scene(paths, args.out, PROFILES[state["profile"]][:2], cues, end_hold)
        edit_path = Path(args.out).with_suffix(".edit.json")
        metadata = read_json(edit_path)
        metadata.update(sources=source_records, frame_edits=edits,
                        speech_timing_changed=any("keep_frames" in s for s in source_records),
                        av_sync_preserved=True)
        write_json(edit_path, metadata)
        write_json(Path(args.out).with_suffix(".dialogue.json"), report)
        print(json.dumps({"output": args.out, "shots": len(paths), "audience_cues": len(cues), "quality": quality}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (DirectorError, OSError, ValueError, KeyError) as exc:
        print("Error: " + str(exc), file=sys.stderr)
        sys.exit(1)
