import json
import math
import os
import shutil
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from .common import DirectorError


def executable(name):
    configured = os.environ.get(name.upper())
    found = configured or shutil.which(name)
    if not found:
        # Local test tools can be installed explicitly; never download at runtime.
        bins = Path(__file__).resolve().parent.parent.glob(".venv/lib/python*/site-packages/static_ffmpeg/bin/*/" + name)
        found = next((str(p) for p in bins if p.is_file()), None)
    if not found or not os.access(found, os.X_OK):
        raise DirectorError("Install {} or set {} to its executable path.".format(name, name.upper()))
    return found


def run(args, timeout=600):
    try:
        result = subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DirectorError("Media command failed: " + type(exc).__name__) from None
    if result.returncode:
        raise DirectorError("Media command failed:\n" + result.stderr[-2000:])
    return result


def probe(path):
    result = run([executable("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", Path(path).resolve()])
    data = json.loads(result.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not video:
        raise DirectorError("No video stream in " + str(path))
    try:
        result = {"width": video["width"], "height": video["height"],
                  "fps": float(Fraction(video["avg_frame_rate"])),
                  "duration": float(video.get("duration") or data["format"]["duration"]),
                  "audio": audio is not None, "audio_channels": audio.get("channels", 0) if audio else 0,
                  "audio_duration": float(audio.get("duration") or data["format"]["duration"]) if audio else 0}
        if any(not math.isfinite(result[k]) or result[k] <= 0 for k in ("width", "height", "fps", "duration")):
            raise ValueError("Invalid video metrics")
        if audio and (not math.isfinite(result["audio_duration"]) or result["audio_duration"] <= 0):
            raise ValueError("Invalid audio metrics")
        return result
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        raise DirectorError("Unusable video/audio metadata in " + str(path)) from None


def check(path, expected_seconds=None, dimensions=None):
    result = probe(path)
    problems = []
    if not result["audio"]:
        problems.append("Missing native audio stream")
    elif result["audio_channels"] != 2:
        problems.append("Expected native stereo audio (two channels)")
    if abs(result["fps"] - 24) > 0.01:
        problems.append("Expected 24 fps")
    if dimensions and (result["width"], result["height"]) != tuple(dimensions):
        problems.append("Unexpected frame size")
    if expected_seconds is not None and abs(result["duration"] - expected_seconds) > 0.25:
        problems.append("Unexpected video duration")
    if result["audio"] and abs(result["audio_duration"] - result["duration"]) > 0.3:
        problems.append("Audio/video durations differ by more than 0.3s")
    # Fully decode to catch a truncated/corrupt stream; metadata alone is insufficient.
    try:
        run([executable("ffmpeg"), "-v", "error", "-xerror", "-i", Path(path).resolve(), "-f", "null", "-"])
    except DirectorError:
        problems.append("Video/audio decoding failed")
    result["problems"] = problems
    result["technical_pass"] = not problems
    result["creative_review"] = "pending: verify dialogue, faces, voices, acting and continuity"
    return result


def last_frame(source, destination):
    counted = run([executable("ffprobe"), "-v", "error", "-select_streams", "v:0", "-count_frames",
                   "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", Path(source).resolve()])
    try:
        count = int(counted.stdout.strip())
        if count <= 0:
            raise ValueError()
    except ValueError:
        raise DirectorError("Could not count decoded video frames.") from None
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="director-frame-", dir=destination.parent) as tmp:
        frame = Path(tmp) / "frame.png"
        run([executable("ffmpeg"), "-v", "error", "-y", "-i", Path(source).resolve(),
             "-vf", "select=eq(n\\,{})".format(count - 1), "-frames:v", "1", frame])
        if not frame.is_file() or not frame.stat().st_size:
            raise DirectorError("Could not extract final frame.")
        os.replace(frame, destination)


def contact_sheet(source, destination):
    info = probe(source)
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="director-sheet-", dir=destination.parent) as tmp:
        sheet = Path(tmp) / "sheet.jpg"
        run([executable("ffmpeg"), "-v", "error", "-y", "-i", Path(source).resolve(),
             "-vf", "fps=6/{:.6f},scale=320:-2,tile=3x2".format(info["duration"]),
             "-frames:v", "1", sheet])
        if not sheet.is_file() or not sheet.stat().st_size:
            raise DirectorError("Could not create contact sheet.")
        os.replace(sheet, destination)


def assemble(paths, output, dimensions=(512, 384)):
    if not paths:
        raise DirectorError("No clips to assemble.")
    w, h = dimensions
    if w <= 0 or h <= 0 or w % 2 or h % 2:
        raise DirectorError("Assembly dimensions must be positive even integers.")
    output = Path(output).resolve()
    if output.exists():
        raise DirectorError("Output already exists: " + str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    # Normalize each segment to a common codec/timebase. Hard cuts preserve lines;
    # no crossfade consumes dialogue, no automatic trimming assumes real silence.
    with tempfile.TemporaryDirectory(prefix="director-assemble-", dir=output.parent) as tmp:
        temp = Path(tmp)
        for i, path in enumerate(paths):
            quality = check(path)
            if not quality["technical_pass"]:
                raise DirectorError("Cannot assemble invalid clip: " + str(path))
            run([executable("ffmpeg"), "-v", "error", "-y", "-i", Path(path).resolve(),
                 "-map", "0:v:0", "-map", "0:a:0", "-vf",
                 "scale={}:{}:force_original_aspect_ratio=decrease,pad={}:{}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24".format(w, h, w, h),
                 "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
                 "-af", "apad,atrim=end_sample={}".format(round(quality["duration"] * 48000)),
                 "-t", str(quality["duration"]), temp / (str(i) + ".mkv")])
        # Generated numeric names avoid concat's path-escaping ambiguities.
        listing = temp / "concat.txt"
        # PCM intermediates avoid adding AAC padding/encoder delay at every cut.
        listing.write_text("".join("file '{}.mkv'\n".format(i) for i in range(len(paths))))
        merged = temp / "merged.mp4"
        run([executable("ffmpeg"), "-v", "error", "-f", "concat", "-safe", "1", "-i", listing,
             "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", merged])
        quality = check(merged, sum(probe(p)["duration"] for p in paths), dimensions)
        if not quality["technical_pass"]:
            raise DirectorError("Assembled video failed checks: " + "; ".join(quality["problems"]))
        os.replace(merged, output)
    return quality
