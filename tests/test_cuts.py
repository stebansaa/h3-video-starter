import array
import subprocess
import tempfile
import unittest
from pathlib import Path

from director import media
from director.common import DirectorError, file_digest
from director.cuts import cut_clip, keep_ranges, retained_transcript


class FrameEditTests(unittest.TestCase):
    def test_disjoint_edit_keeps_matching_picture_and_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "source.mov", root / "edited.mov"
            args = [media.executable("ffmpeg"), "-v", "error"]
            for color, frequency in (("red", 440), ("blue", 880), ("green", 1320)):
                args += ["-f", "lavfi", "-i", "color=c={}:s=128x96:r=24:d=1".format(color),
                         "-f", "lavfi", "-i", "sine=frequency={}:sample_rate=48000:duration=1".format(frequency)]
            args += ["-filter_complex", "[0:v][1:a][2:v][3:a][4:v][5:a]concat=n=3:v=1:a=1[v][a]",
                     "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-c:a", "pcm_s16le", "-ac", "2", source]
            media.run(args)
            digest = file_digest(source)
            quality = cut_clip(source, output, [[12, 24], [48, 60]], digest)
            self.assertEqual(quality["duration"], 1.0)
            self.assertEqual(file_digest(source), digest)
            frames = subprocess.run([media.executable("ffmpeg"), "-v", "error", "-i", str(output),
                                     "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                    capture_output=True, check=True).stdout
            self.assertEqual(len(frames), 24 * 3)
            self.assertGreater(frames[0], 200)  # Red section retained first.
            self.assertGreater(frames[12 * 3 + 1], 100)  # Green section next; blue removed.
            raw = subprocess.run([media.executable("ffmpeg"), "-v", "error", "-i", str(output), "-vn",
                                  "-ac", "1", "-f", "s16le", "-"], capture_output=True, check=True).stdout
            samples = array.array("h", raw)
            self.assertEqual(len(samples), 48000)
            for first, last, expected in ((4800, 19200, 132), (28800, 43200, 396)):
                crossings = sum(samples[i - 1] <= 0 < samples[i] for i in range(first, last))
                self.assertLessEqual(abs(crossings - expected), 2)
            with self.assertRaises(DirectorError):
                cut_clip(source, root / "bad.mov", [[0, 24]], "changed-hash")

    def test_ranges_and_transcript_mapping(self):
        for invalid in ([], [[-1, 20]], [[0, 73]], [[20, 20]], [[0, 30], [20, 40]], [[0.0, 20]]):
            with self.assertRaises(DirectorError):
                keep_ranges(invalid, 72)
        transcript = {"text": "Keep remove retain", "segments": [{"words": [
            {"word": " Keep", "start": .6, "end": .9},
            {"word": " remove", "start": 1.2, "end": 1.8},
            {"word": " retain", "start": 2.1, "end": 2.4}]}]}
        edited = retained_transcript(transcript, [[12, 24], [48, 60]])
        self.assertEqual(edited["text"], "Keep retain")
        self.assertAlmostEqual(edited["segments"][0]["words"][1]["start"], .6)


if __name__ == "__main__":
    unittest.main()
