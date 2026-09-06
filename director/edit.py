"""Scene-level sound edit: preserve picture timing and mix audience across cuts."""
import math
import os
import tempfile
from pathlib import Path

from . import media
from .common import DirectorError, file_digest, write_json


def assemble_scene(paths, output, dimensions=(640, 384), cues=(), end_hold_frames=0):
    """Mix separate audience cues over level-matched dialogue and quiet room tone.

    Cue times are on the finished scene timeline, so a laugh can span a picture
    cut. Sidechain compression reduces laughter under actual dialogue. No speech
    is trimmed, overlapped, time-stretched or shifted relative to its picture.
    """
    output = Path(output).resolve()
    if output.exists() or not paths:
        raise DirectorError("Provide clips and a new output path.")
    paths = [Path(p).resolve() for p in paths]
    if output in paths:
        raise DirectorError("Output must not replace a source clip.")
    if type(end_hold_frames) is not int or not 0 <= end_hold_frames <= 120:
        raise DirectorError("Ending hold must be 0–120 frames at 24 fps.")
    durations = []
    for path in paths:
        quality = media.check(path, dimensions=dimensions)
        if not quality["technical_pass"]:
            raise DirectorError("Invalid source clip: " + str(path))
        durations.append(quality["duration"])
    duration = sum(durations) + end_hold_frames / 24
    for cue in cues:
        for name in ("at", "seconds"):
            if type(cue.get(name)) not in (int, float) or not math.isfinite(cue[name]):
                raise DirectorError("Audience cue times must be finite numbers.")
        if cue["at"] < 0 or cue["at"] >= duration or cue["seconds"] <= 0 or not Path(cue["path"]).is_file():
            raise DirectorError("Invalid audience cue.")
        gain = cue.get("gain_db", 0)
        if type(gain) not in (int, float) or not math.isfinite(gain) or not -12 <= gain <= 6:
            raise DirectorError("Audience gain must be between -12 and +6 dB.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="director-scene-", dir=output.parent) as temporary:
        tmp = Path(temporary)
        picture = tmp / "picture.mp4"
        media.assemble(paths, picture, dimensions)
        for i, (path, seconds) in enumerate(zip(paths, durations)):
            # Sample-exact lengths keep dialogue aligned across all fourteen cuts.
            samples = round(seconds * 48000)
            media.run([media.executable("ffmpeg"), "-v", "error", "-i", path, "-vn", "-af",
                       "loudnorm=I=-20:TP=-3:LRA=11,aresample=48000,apad,atrim=end_sample={},"
                       "afade=t=in:d=0.012,afade=t=out:st={}:d=0.012".format(samples, max(0, seconds - 0.012)),
                       "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", tmp / (str(i) + ".wav")])
        listing = tmp / "dialogue.txt"
        listing.write_text("".join("file '{}.wav'\n".format(i) for i in range(len(paths))))
        dialogue = tmp / "dialogue.wav"
        media.run([media.executable("ffmpeg"), "-v", "error", "-f", "concat", "-safe", "1", "-i", listing,
                   "-c:a", "pcm_s16le", dialogue])
        # Assemble one audience stem; it has no boundaries tied to picture cuts.
        audience = tmp / "audience.wav"
        args = [media.executable("ffmpeg"), "-v", "error", "-f", "lavfi", "-i",
                "anullsrc=r=48000:cl=stereo:d={}".format(duration)]
        filters, labels = [], ["[0:a]"]
        for i, cue in enumerate(cues, 1):
            args += ["-t", str(cue["seconds"]), "-i", str(Path(cue["path"]).resolve())]
            filters.append("[{}:a]aresample=48000,loudnorm=I=-27:TP=-8:LRA=7,aresample=48000,volume={}dB,"
                           "afade=t=in:d=0.12,afade=t=out:st={}:d=0.55,adelay={}|{}[l{}]".format(
                               i, cue.get("gain_db", 0), max(0, cue["seconds"] - 0.55), round(cue["at"] * 1000), round(cue["at"] * 1000), i))
            labels.append("[l{}]".format(i))
        filters.append("{}amix=inputs={}:duration=first:normalize=0[aud]".format("".join(labels), len(labels)))
        args += ["-filter_complex", ";".join(filters), "-map", "[aud]", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", audience]
        media.run(args)
        mixed = tmp / "mixed.mp4"
        # The very quiet, continuous brown-noise bed masks changes in background
        # noise without inserting pauses. It is an editing asset, not model audio.
        final_filter = (
            "[1:a]apad,atrim=end_sample={samples},asplit=2[dialogue][detector];"
            "[2:a][detector]sidechaincompress=threshold=0.018:ratio=8:attack=8:release=280:makeup=1[ducked];"
            "[3:a]highpass=f=80,lowpass=f=700,pan=stereo|c0=c0|c1=c0[room];"
            "[dialogue][ducked][room]amix=inputs=3:duration=first:normalize=0,"
            "alimiter=limit=0.891:level=false:latency=true,afade=t=out:st={fade}:d=0.3[mix]"
        ).format(samples=round(duration * 48000), fade=max(0, duration - 0.3))
        media.run([media.executable("ffmpeg"), "-v", "error", "-i", picture, "-i", dialogue, "-i", audience,
                   "-f", "lavfi", "-i", "anoisesrc=color=brown:amplitude=0.018:sample_rate=48000:duration={}:seed=1701".format(duration),
                   "-filter_complex", final_filter, "-map", "0:v:0", "-map", "[mix]", "-vf",
                   "tpad=stop_mode=clone:stop={},fade=t=out:st={}:d=0.3".format(
                       end_hold_frames, max(0, duration - 0.3 - 1 / 24)), "-c:v", "libx264", "-crf", "18",
                   "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-t", str(duration),
                   "-movflags", "+faststart", mixed])
        quality = media.check(mixed, duration, dimensions)
        if not quality["technical_pass"]:
            raise DirectorError("Mixed scene failed technical checks.")
        os.replace(mixed, output)
    write_json(output.with_suffix(".edit.json"), {
        "sources": [{"path": str(p), "sha256": file_digest(p), "seconds": d} for p, d in zip(paths, durations)],
        "cues": list(cues), "dialogue_lufs_target": -20, "audience_lufs_target": -27,
        "end_hold_frames": end_hold_frames,
        "room_tone": "quiet synthetic brown noise, 80–700 Hz", "speech_timing_changed": False,
        "output_sha256": file_digest(output), "quality": quality})
    return quality
