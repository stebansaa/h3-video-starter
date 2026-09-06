# A provisional single-clip edit

Use this path for a separate preview while human creative review is pending;
it does not mark the raw shot accepted. For accepted episode shots, keep using
`review --cuts` and `assemble_episode.py` as described in
[quality and editing](quality-and-editing.md).

The following offline example reproduces the live trial's cut using its
included raw media. Run the Python block from the repository root after media
setup. It needs no key, GPU or AI weights. Use new destination names for a
repeat run; existing outputs are preserved.

```python
import json
from pathlib import Path
from director.common import read_json
from director.cuts import cut_clip
from director.media import check, executable, run

source = Path("examples/standing-desk-preview")
work = Path("output/standing-desk-preview-check")
work.mkdir(parents=True, exist_ok=True)
edit = read_json(source / "cuts.json")["shots"]["01a"]
intermediate = work / "trimmed-pcm.mkv"
delivery = work / "preview.mp4"
cut_clip(source / "raw-clip.mp4", intermediate, edit["keep_frames"],
         expected_hash=edit["source_sha256"])
run([executable("ffmpeg"), "-n", "-v", "error", "-i", intermediate,
     "-map", "0:v:0", "-map", "0:a:0",
     "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "24",
     "-c:a", "aac", "-ar", "48000", "-ac", "2",
     "-movflags", "+faststart", delivery])
quality = check(delivery, 181 / 24, (640, 384))
assert quality["technical_pass"], quality
frames = json.loads(run([executable("ffprobe"), "-v", "error", "-select_streams", "v:0",
                         "-count_frames", "-show_entries", "stream=nb_read_frames,r_frame_rate,avg_frame_rate",
                         "-of", "json", delivery]).stdout)["streams"][0]
assert int(frames["nb_read_frames"]) == 181, frames
assert frames["avg_frame_rate"] == "24/1", frames
print(json.dumps({"output": str(delivery), "quality": quality, "frames": frames}, indent=2))
```

The helper cuts picture and PCM audio together with short boundary fades.
Final H.264 encoding explicitly sets 24 fps and encodes AAC once. During the
live trial, an initial manual `-c:v copy` export inherited the MKV intermediate's
millisecond timestamps, yielding an average 24.0021 fps. Re-encoding with `-r 24`
produced exact 24 fps and 181 frames. This was a manual conversion issue; the
shipped episode assembler was not used for this trim and was not implicated.

These frame boundaries apply only to the included source hash. For another
clip, select its own boundaries from actual picture/audio review, independent
ASR and margins, then verify its expected count/duration. Do not remove missing
or overlapping desired words to make a transcript appear correct. After an
actual new edit, transcribe the **final exported bytes** on the remote server
and bind the transcript to their SHA-256 before cleanup. Human listening and
lip-sync review remain separate from these technical checks.
