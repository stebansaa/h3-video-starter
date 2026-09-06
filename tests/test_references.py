import ast
import copy
import json
import tempfile
import unittest
from pathlib import Path

from director import media
from director.common import ROOT, DirectorError, read_json, write_json
from director.comfy import Comfy
from director.pipeline import render
from director.plan import load_plan
from director.references import load, prepare
from director.workflow import build, preflight
from tests.fake_server import FakeServer


class ReferenceContractTests(unittest.TestCase):
    def setUp(self):
        self.plan = load_plan(ROOT / "plans/episode.json")
        self.shot = self.plan["shots"][0]
        self.refs = [{"character": c, "video": "reference.mp4"} for c in self.shot["characters"]]
        self.info = read_json(ROOT / "tests/fixtures/object_info_references.json")

    def graph(self):
        return build(self.plan, self.shot, 1001, "reference_test", first_frame="reference.png", reference_videos=self.refs)

    def test_references_keep_audio_pairs_and_anchor_at_zero(self):
        graph = self.graph()
        preflight(graph, self.info)
        for index, character in enumerate(self.shot["characters"]):
            inputs = graph["5"]["inputs"]
            video = inputs["ref_videos.ref_video_" + str(index)]
            audio = inputs["ref_video_audios.ref_video_audio_" + str(index)]
            self.assertEqual(video[0], audio[0])
            self.assertEqual((video[1], audio[1]), (0, 1))
            self.assertIn("{}: use <Video {}>".format(character, index + 1), inputs["prompt"])
        self.assertEqual(graph["16"]["inputs"]["frame_idx"], 0)
        self.assertEqual(graph["7"]["inputs"]["conditioning"], ["16", 0])
        self.assertEqual(graph["10"]["inputs"]["latent_image"], ["5", 1])
        self.assertEqual(graph["13"]["inputs"]["audio"], ["12", 0])

    def test_old_server_missing_guides_fails(self):
        info = copy.deepcopy(self.info)
        del info["MiniMaxH3AddGuide"]
        with self.assertRaisesRegex(DirectorError, "Missing node MiniMaxH3AddGuide"):
            preflight(self.graph(), info)

    def test_wrong_dynamic_slots_and_audio_types_fail(self):
        graph = self.graph()
        graph["5"]["inputs"]["ref_videos.ref_video_3"] = ["21", 0]
        with self.assertRaisesRegex(DirectorError, "not supported"):
            preflight(graph, self.info)
        graph = self.graph()
        graph["5"]["inputs"]["ref_video_audios.ref_video_audio_0"] = ["21", 0]
        with self.assertRaisesRegex(DirectorError, "Incompatible output"):
            preflight(graph, self.info)
        graph = self.graph()
        graph["7"]["inputs"]["conditioning"] = ["16", 1]
        with self.assertRaisesRegex(DirectorError, "Incompatible output"):
            preflight(graph, self.info)

    def test_missing_image_or_misordered_character_rejected(self):
        with self.assertRaises(DirectorError):
            build(self.plan, self.shot, 1, "bad", reference_videos=self.refs)
        with self.assertRaises(DirectorError):
            build(self.plan, self.shot, 1, "bad", first_frame="reference.png", reference_videos=self.refs[::-1])

    def test_new_fixture_input_names_match_pinned_source(self):
        classes = {}
        for filename in ("nodes_minimax_h3.py", "nodes_video.py"):
            tree = ast.parse((ROOT / "vendor/h3-guides" / filename).read_text())
            classes.update({n.name: n for n in tree.body if isinstance(n, ast.ClassDef)})
        for kind in ("MiniMaxH3AddGuide", "MiniMaxH3ReferenceToVideo", "LoadVideo", "GetVideoComponents"):
            schema = next(n for n in classes[kind].body if isinstance(n, ast.FunctionDef) and n.name == "define_schema")
            names = {n.args[0].value for n in ast.walk(schema) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and n.func.attr == "Input" and n.args and isinstance(n.args[0], ast.Constant)}
            for group in self.info[kind]["input"].values():
                self.assertTrue(set(group).issubset(names), kind)

    def test_autogrow_names_match_upstream_expansion(self):
        # Execute the upstream expansion itself without importing PyTorch or
        # ComfyUI. The callback captures the actual names sent to its parser.
        tree = ast.parse((ROOT / "vendor/h3-guides/_io.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Autogrow")
        fn = copy.deepcopy(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_expand_schema_for_dynamic"))
        fn.decorator_list = []
        for arg in fn.args.args:
            arg.annotation = None
        fn.returns = None
        calls = []
        namespace = {"finalize_prefix": lambda prefix, name=None: ".".join((prefix or []) + ([name] if name else [])),
                     "parse_class_inputs": lambda out, live, new, prefix: calls.append((new, prefix))}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "upstream-autogrow", "exec"), namespace)
        for group, definition in self.info["MiniMaxH3ReferenceToVideo"]["input"]["optional"].items():
            if definition[0] != "COMFY_AUTOGROW_V3":
                continue
            live = self.graph()["5"]["inputs"]
            if not any(k.startswith(group + ".") for k in live):
                continue
            out = {"required": {}, "optional": {}}
            namespace[fn.name](out, live, definition, "optional", [group])
            for key in live:
                if key.startswith(group + "."):
                    self.assertIn(key, out["optional"])


class ReferenceMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.video = cls.root / "source.mp4"
        cls.image = cls.root / "start.png"
        media.run([media.executable("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=512x384:rate=24",
                   "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=32000", "-t", "5.1666667", "-c:v", "libx264",
                   "-c:a", "aac", "-ac", "2", cls.video])
        media.last_frame(cls.video, cls.image)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def manifest(self):
        path = self.root / "manifest.json"
        write_json(path, {"version": 1, "shot": "01a", "first_frame": "start.png", "clips": [
            {"character": c, "path": "source.mp4", "start": 0.25, "seconds": 3.25}
            for c in ("Jerry", "George", "Kramer")]})
        return path

    def test_trim_resample_pair_and_full_reference_render_resume(self):
        plan = load_plan(ROOT / "plans/episode.json")
        plan["shots"] = [copy.deepcopy(plan["shots"][0])]
        plan["shots"][0].update(seconds=5, dialogue=[{"speaker": "Jerry", "text": "Where?"}])
        manifest = self.manifest()
        assets = load(manifest, plan["shots"][0])
        with tempfile.TemporaryDirectory() as temp, FakeServer(self.video.read_bytes()) as server:
            server.info = read_json(ROOT / "tests/fixtures/object_info_references.json")
            client = Comfy(server.url)
            state = render(plan, client, temp, shot_id="01a", references=manifest, poll_interval=0.01)
            self.assertEqual(state["shots"]["01a"]["status"], "complete")
            self.assertEqual(len(server.jobs), 1)
            self.assertEqual(len(server.uploads), 4)
            prepared = Path(temp) / "01a/references/character_1.mp4"
            self.assertTrue(media.check(prepared, assets["clips"][0]["frames"] / 24)["technical_pass"])
            render(plan, client, temp, shot_id="01a", references=manifest, poll_interval=0.01)
            self.assertEqual(len(server.jobs), 1)
            self.assertEqual(len(server.uploads), 4)
            value = read_json(manifest)
            value["clips"][0]["start"] = 0.5
            write_json(manifest, value)
            with self.assertRaisesRegex(DirectorError, "changed"):
                render(plan, client, temp, shot_id="01a", references=manifest)
            self.assertEqual(len(server.jobs), 1)

    def test_bad_assets_fail_before_any_api_requests(self):
        plan = load_plan(ROOT / "plans/episode.json")
        manifest = self.manifest()
        value = read_json(manifest)
        value["clips"][1]["start"] = 100
        write_json(manifest, value)
        with tempfile.TemporaryDirectory() as temp, FakeServer() as server:
            with self.assertRaises(DirectorError):
                render(plan, Comfy(server.url), temp, shot_id="01a", references=manifest)
            self.assertFalse(server.posts)
            self.assertFalse(server.jobs)
        value["clips"][1]["start"] = 0
        value["clips"] = value["clips"][::-1]
        write_json(manifest, value)
        with self.assertRaises(DirectorError):
            load(manifest, plan["shots"][0])


if __name__ == "__main__":
    unittest.main()
