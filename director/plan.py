import math
import re

from .common import DirectorError, read_json, safe_id

FPS = 24


def frame_count(seconds):
    """H3's native grid is 17k+5; round up so dialogue never loses time."""
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not math.isfinite(seconds) or not 5 <= seconds <= 15:
        raise DirectorError("Shot duration must be 5–15 seconds.")
    n = math.ceil(seconds * FPS)
    return n + (5 - n) % 17


def speech_seconds(dialogue):
    # A planning heuristic, not a guarantee of synthesized speech speed.
    words = sum(len(re.findall(r"\S+", line["text"])) for line in dialogue)
    return words / 2.4 + max(0, len(dialogue) - 1) * 0.4


def validate(plan):
    if plan.get("version") != 1:
        raise DirectorError("Unsupported plan version.")
    safe_id(plan["id"])
    if not plan.get("shots"):
        raise DirectorError("Plan has no shots.")
    if not isinstance(plan.get("style"), str) or not plan["style"].strip():
        raise DirectorError("Plan requires a style instruction.")
    ids = set()
    for shot in plan["shots"]:
        sid = safe_id(shot["id"])
        if sid in ids:
            raise DirectorError("Duplicate shot: " + sid)
        ids.add(sid)
        frame_count(shot["seconds"])
        if shot.get("continuity") not in ("reset", "previous"):
            raise DirectorError("Invalid continuity for " + sid)
        if not shot.get("action"):
            raise DirectorError("Missing action for " + sid)
        if not shot.get("characters") or any(c not in plan["characters"] for c in shot["characters"]):
            raise DirectorError("Unknown character in " + sid)
        for line in shot["dialogue"]:
            if line["speaker"] not in shot["characters"] or not line["text"].strip():
                raise DirectorError("Invalid speaker or empty dialogue in " + sid)
        if speech_seconds(shot["dialogue"]) + 1.0 > shot["seconds"]:
            raise DirectorError("Dialogue is too dense for " + sid + "; split it or increase duration.")
    if plan["shots"][0]["continuity"] != "reset":
        raise DirectorError("The first shot must establish a new scene.")
    return plan


def load_plan(path):
    return validate(read_json(path))


def prompt_for(plan, shot):
    cast = "\n".join("{}: {}".format(c, plan["characters"][c]) for c in shot["characters"])
    seconds = frame_count(shot["seconds"]) / FPS
    lines = [plan["style"], "Set: " + plan["set"], "Cast and permanent speaker IDs:\n" + cast,
             "Blocking: " + shot["action"], "Appearance state: " + shot.get("state", "Use standard character descriptions."),
             "Duration: {:.3f} seconds, 24 fps. Timeline:".format(seconds),
             "[0.00s–0.50s] Silent establishing/reaction beat. No speech."]
    cursor = 0.5
    for line in shot["dialogue"]:
        end = cursor + len(line["text"].split()) / 2.4
        lines.append('[{:.2f}s–{:.2f}s] {} alone says exactly: “{}”'.format(cursor, end, line["speaker"], line["text"]))
        cursor = end + 0.4
    lines += ["After the last line, hold a silent reaction through {:.3f}s; no extra words.".format(seconds),
              "Audio: natural conversational English, quiet room tone. Only the identified speaker talks; other mouths remain still. "
              "Keep each voice attached to its own character. Clean production dialogue only. "
              "No audience, laughter, laugh track, applause, narration, added dialogue, music, or overlapping speech. "
              "Leave the opening and ending reaction beats free of speech and vocal sounds for editing. "
              "Use small reaction pauses. No subtitles or on-screen text."]
    return "\n\n".join(lines)


def select_shots(plan, shot_id=None):
    if shot_id is None:
        return plan["shots"]
    selected = [s for s in plan["shots"] if s["id"] == shot_id]
    if not selected:
        raise DirectorError("Unknown shot: " + shot_id)
    return selected
