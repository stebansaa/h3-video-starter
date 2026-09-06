"""Explicit frame edits, keeping source video and audio on the same clock."""
from pathlib import Path

from . import media
from .common import DirectorError, file_digest


def keep_ranges(ranges, total_frames):
    if not isinstance(ranges, list) or not ranges:
        raise DirectorError("An edit needs at least one retained frame range.")
    previous = 0
    for pair in ranges:
        if (not isinstance(pair, list) or len(pair) != 2 or
                any(type(n) is not int for n in pair)):
            raise DirectorError("Frame ranges must contain two integers.")
        start, end = pair
        if start < previous or end <= start or end > total_frames:
            raise DirectorError("Frame ranges must be ordered, disjoint and inside the clip.")
        previous = end
    return ranges


def retained_transcript(transcript, ranges):
    """Map retained ASR words onto the edited clip without inventing new text."""
    words = []
    offset = 0.0
    for first, last in ranges:
        start, end = first / 24, last / 24
        for segment in transcript["segments"]:
            for word in segment["words"]:
                # Word midpoints decide inclusion; ASR boundaries are estimates.
                midpoint = (word["start"] + word["end"]) / 2
                if start <= midpoint < end:
                    words.append(dict(word, start=offset + max(0, word["start"] - start),
                                      end=offset + min(end, word["end"]) - start))
        offset += end - start
    return {"text": "".join(w["word"] for w in words).strip(),
            "segments": [{"words": words}], "source_text": transcript["text"]}


def cut_clip(source, destination, ranges, expected_hash=None):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists() or source == destination:
        raise DirectorError("Frame edit needs a new output path.")
    if expected_hash and file_digest(source) != expected_hash:
        raise DirectorError("Source changed after frame edit review.")
    info = media.check(source)
    if not info["technical_pass"]:
        raise DirectorError("Cannot edit invalid source video.")
    ranges = keep_ranges(ranges, round(info["duration"] * 24))
    filters, labels = [], []
    for i, (start, end) in enumerate(ranges):
        filters.append("[0:v]trim=start_frame={}:end_frame={},setpts=PTS-STARTPTS[v{}]".format(start, end, i))
        filters.append("[0:a]aresample=48000,atrim=start_sample={}:end_sample={},asetpts=PTS-STARTPTS,"
                       "afade=t=in:d=0.006,afade=t=out:st={}:d=0.006[a{}]".format(
                           start * 2000, end * 2000, (end - start) / 24 - 0.006, i))
        labels.append("[v{}][a{}]".format(i, i))
    filters.append("{}concat=n={}:v=1:a=1[v][a]".format("".join(labels), len(ranges)))
    destination.parent.mkdir(parents=True, exist_ok=True)
    media.run([media.executable("ffmpeg"), "-v", "error", "-i", source,
               "-filter_complex", ";".join(filters), "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", "-r", "24",
               "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", destination])
    expected = sum(b - a for a, b in ranges) / 24
    quality = media.check(destination, expected, (info["width"], info["height"]))
    if not quality["technical_pass"] or abs(quality["duration"] - expected) > 0.001:
        raise DirectorError("Frame edit failed timing or decode checks.")
    return quality
