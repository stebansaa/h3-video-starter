"""Prepare short character references locally; never download model weights."""
import json
import math
from pathlib import Path

from . import media
from .common import DirectorError, file_digest, read_json, write_json
import tempfile


def load(path, shot):
    path = Path(path).resolve()
    value = read_json(path)
    if value.get("version") != 1 or value.get("shot") != shot["id"]:
        raise DirectorError("Reference manifest must have version 1 and match the selected shot.")

    def asset(name):
        if not isinstance(name, str) or not name.strip():
            raise DirectorError("Reference manifest requires local file paths.")
        result = (path.parent / name).resolve()
        if not result.is_file():
            raise DirectorError("Missing reference file: " + str(result))
        return str(result)

    first = asset(value.get("first_frame"))
    if Path(first).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        raise DirectorError("Starting image must be PNG, JPEG or WebP.")
    image = json.loads(media.run([media.executable("ffprobe"), "-v", "error", "-select_streams", "v:0",
                                 "-show_entries", "stream=width,height", "-of", "json", first]).stdout)["streams"][0]
    if image["width"] < 32 or image["height"] < 32:
        raise DirectorError("Starting image is too small.")
    clips = value.get("clips", [])
    if not isinstance(clips, list) or not 1 <= len(clips) <= 4:
        raise DirectorError("Provide one to four character reference clips.")
    if [c.get("character") for c in clips] != shot["characters"]:
        raise DirectorError("Reference clips must follow the shot's character order: " + ", ".join(shot["characters"]))
    result = {"first_frame": first, "first_frame_sha256": file_digest(first), "clips": []}
    for clip in clips:
        source = asset(clip.get("path"))
        start, seconds = clip.get("start", 0), clip.get("seconds", 3.25)
        if any(type(n) not in (int, float) or not math.isfinite(n) for n in (start, seconds)) or start < 0 or not 2 <= seconds <= 6:
            raise DirectorError("Reference start must be nonnegative and duration between 2 and 6 seconds.")
        # Snap DOWN so neither the video nor paired soundtrack exceeds the cut.
        frames = math.floor(seconds * 24)
        frames -= (frames - 5) % 17
        info = media.probe(source)
        duration = frames / 24
        if not info["audio"] or start + duration > info["duration"] + 0.02:
            raise DirectorError("Reference needs an audio stream and enough video for the requested cut: " + source)
        result["clips"].append({"character": clip["character"], "path": source,
                                "sha256": file_digest(source), "start": start, "frames": frames})
    return result


def prepare(assets, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    output = []
    for index, clip in enumerate(assets["clips"]):
        destination = directory / ("character_{}.mp4".format(index + 1))
        duration = clip["frames"] / 24
        # Short 24fps clips keep the reference token cost bounded. Both streams
        # are cut together; AAC stereo at the VAE's 32 kHz rate is kept paired.
        media.run([media.executable("ffmpeg"), "-v", "error", "-xerror", "-y",
                   "-ss", clip["start"], "-i", clip["path"], "-t", duration,
                   "-map", "0:v:0", "-map", "0:a:0", "-vf",
                   "scale=w='max(32,round(iw*min(1,512/max(iw,ih))/32)*32)':h='max(32,round(ih*min(1,512/max(iw,ih))/32)*32)',setsar=1,fps=24",
                   "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-ar", "32000", "-ac", "2", "-movflags", "+faststart", destination])
        qc = media.check(destination, duration)
        if not qc["technical_pass"]:
            raise DirectorError("Prepared reference failed checks: " + str(destination))
        output.append({"character": clip["character"], "path": str(destination)})
    return output


def load_sequence(path, shots):
    """Validate every source before a paid request; starting frames may chain.

    Version 2 has a character library and per-shot starting-image paths. A null
    starting image means use the preceding accepted/generated ending frame.
    """
    path = Path(path).resolve()
    value = read_json(path)
    if value.get("version") != 2 or not isinstance(value.get("characters"), dict) or not isinstance(value.get("shots"), dict):
        raise DirectorError("Sequence references require version 2, characters and shots.")
    library = value["characters"]
    fixed = [v.get("first_frame") for v in value["shots"].values() if isinstance(v, dict) and v.get("first_frame")]
    if not fixed:
        raise DirectorError("Sequence needs at least one starting image.")
    result = {"version": 2, "shots": {}}
    # Reuse the thoroughly tested image/video validation with absolute paths.
    with tempfile.TemporaryDirectory(prefix="director-reference-validation-") as tmp:
        manifest = Path(tmp) / "manifest.json"
        for shot in shots:
            if shot["id"] not in value["shots"]:
                raise DirectorError("Missing reference configuration for " + shot["id"])
            config = value["shots"][shot["id"]]
            if not isinstance(config, dict):
                raise DirectorError("Invalid shot reference configuration.")
            first = config.get("first_frame")
            if not first and shot["continuity"] != "previous":
                raise DirectorError("New camera angle needs a starting image: " + shot["id"])
            clips = []
            for character in shot["characters"]:
                source = library.get(character)
                if not isinstance(source, dict) or not isinstance(source.get("path"), str):
                    raise DirectorError("Missing character reference: " + character)
                clips.append(dict(source, character=character, path=str((path.parent / source["path"]).resolve())))
            write_json(manifest, {"version": 1, "shot": shot["id"],
                                  "first_frame": str((path.parent / (first or fixed[0])).resolve()), "clips": clips})
            assets = load(manifest, shot)
            assets["anchor_mode"] = "fixed" if first else "previous"
            result["shots"][shot["id"]] = assets
    return result
