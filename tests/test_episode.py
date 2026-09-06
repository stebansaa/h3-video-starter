import copy
import json
import tempfile
import unittest
from pathlib import Path

from director import media
from director.common import ROOT, DirectorError, read_json, write_json
from director.comfy import Comfy
from director.edit import assemble_scene
from director.pipeline import render
from director.references import load_sequence
from director.workflow import build, preflight
from director.takes import fork_reviewed_prefix
from director.pipeline import review
from tests.fake_server import FakeServer


class FourCharacterContractTests(unittest.TestCase):
    def test_fourth_character_uses_image_and_audio_after_three_paired_videos(self):
        plan = read_json(ROOT / "plans/episode.json")
        shot = next(s for s in plan["shots"] if s["id"] == "05a")
        graph = build(plan, shot, 1, "four_cast", first_frame="reference.png",
                      reference_videos=[{"character": c, "video": "reference.mp4"} for c in shot["characters"]])
        preflight(graph, read_json(ROOT / "tests/fixtures/object_info_references.json"))
        inputs = graph["5"]["inputs"]
        self.assertNotIn("ref_videos.ref_video_3", inputs)
        self.assertEqual(inputs["ref_audios.ref_audio_0"], ["27", 1])
        self.assertEqual(inputs["ref_images.ref_image_1"], ["27", 0])
        self.assertEqual([k for k in inputs if k.startswith("ref_images.")],
                         ["ref_images.ref_image_0", "ref_images.ref_image_1"])
        self.assertIn("<Picture 2>", inputs["prompt"])
        self.assertIn("<Audio 4>", inputs["prompt"])


class EpisodeMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.video = cls.root / "source.mp4"
        cls.image = cls.root / "start.png"
        media.run([media.executable("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=512x384:rate=24",
                   "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=32000", "-t", "5.1666667",
                   "-c:v", "libx264", "-c:a", "aac", "-ac", "2", cls.video])
        media.last_frame(cls.video, cls.image)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def sequence(self):
        plan = read_json(ROOT / "plans/episode.json")
        base = copy.deepcopy(plan["shots"][0])
        base.update(seconds=5, dialogue=[{"speaker": "Jerry", "text": "Where?"}])
        plan["shots"] = [dict(base, id="01a", continuity="reset"),
                         dict(base, id="01b", continuity="previous"),
                         dict(base, id="01c", continuity="reset")]
        manifest = self.root / "sequence.json"
        write_json(manifest, {"version": 2,
            "characters": {c: {"path": "source.mp4", "seconds": 2.65} for c in base["characters"]},
            "shots": {"01a": {"first_frame": "start.png"}, "01b": {}, "01c": {"first_frame": "start.png"}}})
        return plan, manifest

    def test_pause_resume_continuation_and_camera_reset_submit_once(self):
        plan, manifest = self.sequence()
        with tempfile.TemporaryDirectory() as tmp, FakeServer(self.video.read_bytes()) as server:
            server.info = read_json(ROOT / "tests/fixtures/object_info_references.json")
            client = Comfy(server.url)
            state = render(plan, client, tmp, references=manifest, through="01b", poll_interval=0.01)
            self.assertEqual(len(server.jobs), 2)
            self.assertEqual(state["shot_order"], ["01a", "01b", "01c"])
            self.assertTrue((Path(tmp) / "01b/first_frame.png").exists())
            state = render(plan, client, tmp, references=manifest, poll_interval=0.01)
            self.assertEqual(len(server.jobs), 3)
            self.assertTrue(all(r["status"] == "complete" for r in state["shots"].values()))
            reset = read_json(Path(tmp) / "01c/reference-inputs.json")
            self.assertEqual(reset["actual_first_frame"], str(self.image.resolve()))
            render(plan, client, tmp, references=manifest, poll_interval=0.01)
            self.assertEqual(len(server.jobs), 3)
            # Tampered source must block even when the clips have completed.
            val = read_json(manifest)
            val["characters"]["Jerry"]["start"] = 0.25
            write_json(manifest, val)
            with self.assertRaisesRegex(DirectorError, "changed"):
                render(plan, client, tmp, references=manifest)

    def test_bad_later_reference_blocks_all_paid_requests(self):
        plan, manifest = self.sequence()
        val = read_json(manifest)
        val["shots"]["01c"]["first_frame"] = "missing.png"
        write_json(manifest, val)
        with tempfile.TemporaryDirectory() as tmp, FakeServer() as server:
            with self.assertRaises(DirectorError):
                render(plan, Comfy(server.url), tmp, references=manifest)
            self.assertFalse(server.posts)

    def test_revision_reuses_only_unchanged_reviewed_prefix(self):
        plan, manifest = self.sequence()
        with tempfile.TemporaryDirectory() as tmp, FakeServer(self.video.read_bytes()) as server:
            server.info = read_json(ROOT / "tests/fixtures/object_info_references.json")
            original, revised = Path(tmp) / "original", Path(tmp) / "revised"
            client = Comfy(server.url)
            state = render(plan, client, original, references=manifest, through="01a", poll_interval=0.01)
            review(original, "01a", "accepted", "Test reviewed prefix")
            changed = copy.deepcopy(plan)
            changed["shots"][1]["action"] = "A clearer angle."
            fork_reviewed_prefix(original, revised, changed, manifest, "01a", seed=2001)
            state2 = render(changed, client, revised, references=manifest, seed=2001, through="01b", poll_interval=0.01)
            self.assertEqual(len(server.jobs), 2)
            self.assertEqual(state2["shots"]["01a"]["sha256"], state["shots"]["01a"]["sha256"])
            changed["shots"][0]["dialogue"][0]["text"] = "Different words."
            with self.assertRaisesRegex(DirectorError, "Prompt changed"):
                fork_reviewed_prefix(original, Path(tmp) / "bad", changed, manifest, "01a")

    def test_mix_preserves_duration_stereo_and_cue_across_picture_cut(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "scene.mp4"
            cue = {"path": str(self.video), "at": 4.7, "seconds": 2.0, "gain_db": -3}
            quality = assemble_scene([self.video, self.video], output, (512, 384), [cue])
            self.assertTrue(quality["technical_pass"])
            self.assertAlmostEqual(quality["duration"], 10.333333, places=3)
            self.assertEqual(quality["audio_channels"], 2)
            self.assertFalse(read_json(output.with_suffix(".edit.json"))["speech_timing_changed"])
            # Verify the rendered track contains real, finite audio samples.
            import subprocess, array
            decoded = subprocess.run([media.executable("ffmpeg"), "-v", "error", "-i", str(output), "-vn",
                                      "-f", "s16le", "-acodec", "pcm_s16le", "-"], capture_output=True, check=True).stdout
            samples = array.array("h", decoded)
            self.assertGreater(max(abs(s) for s in samples), 100)
            self.assertLess(max(abs(s) for s in samples), 32767)
            with self.assertRaises(DirectorError):
                assemble_scene([self.video], output, (512, 384))

    def test_ending_hold_extends_picture_and_audio_then_reaches_black(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ending.mp4"
            quality = assemble_scene([self.video], output, (512, 384), end_hold_frames=48)
            self.assertAlmostEqual(quality["duration"], 7.166667, places=3)
            self.assertAlmostEqual(quality["audio_duration"], quality["duration"], places=2)
            import subprocess
            frames = subprocess.run([media.executable("ffmpeg"), "-v", "error", "-i", str(output),
                                     "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                    capture_output=True, check=True).stdout
            self.assertEqual(len(frames), 172 * 3)
            self.assertLessEqual(max(frames[-3:]), 1)


if __name__ == "__main__":
    unittest.main()
