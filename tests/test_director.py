import ast
import copy
import contextlib
import io
import json
import math
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from director import media
from director.common import DirectorError, ROOT, file_digest, read_json, write_json
from director.comfy import Comfy
from director.http import APIError, HTTP
from director.pipeline import assemble_run, render, review, run_lock
from director.plan import frame_count, load_plan, prompt_for, validate
from director.runpod import RunPod, pod_config
from director.workflow import build, preflight
from tests.fake_server import FakeServer


def sample_plan():
    plan = copy.deepcopy(load_plan(ROOT / "plans/episode.json"))
    shot = copy.deepcopy(plan["shots"][4])
    shot.update(id="test_a", seconds=5, dialogue=[{"speaker": "Jerry", "text": "Bitcoiners."}], continuity="reset")
    other = copy.deepcopy(shot)
    other.update(id="test_b", continuity="previous")
    plan["shots"] = [shot, other]
    return plan


class PlanAndContractTests(unittest.TestCase):
    def setUp(self):
        self.plan = load_plan(ROOT / "plans/episode.json")

    def test_all_source_dialogue_preserved_in_order(self):
        source = (ROOT / "script.txt").read_text().split("CRITICAL HAPPYHORSE INSTRUCTIONS")[0]
        quoted = re.findall(r"(?m)^“(.*)”$", source)
        planned = [d["text"] for s in self.plan["shots"] for d in s["dialogue"]]
        self.assertEqual(quoted, planned)
        self.assertEqual(file_digest(ROOT / "script.txt"), self.plan["source_sha256"])

    def test_timing_matches_real_upstream_grid(self):
        tree = ast.parse((ROOT / "vendor/nodes_minimax_h3.py").read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "align_frame_count")
        namespace = {}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "upstream-grid", "exec"), namespace)
        for seconds in [5, 5.01, 6, 7, 9.3, 12, 15]:
            n = frame_count(seconds)
            self.assertEqual(n, namespace["align_frame_count"](math.ceil(seconds * 24)))
            self.assertGreaterEqual(n / 24, seconds)
            self.assertLessEqual(n, 362)
        for invalid in [0, 4, 16, float("nan"), float("inf"), True]:
            with self.assertRaises(DirectorError):
                frame_count(invalid)

    def test_bad_plans_fail_before_submission(self):
        for mutate in (lambda p: p["shots"].append(p["shots"][0]),
                       lambda p: p["shots"][0].update(seconds=5),
                       lambda p: p["shots"][0].update(id="../escape"),
                       lambda p: p["shots"][0]["dialogue"][0].update(speaker="Unknown")):
            plan = copy.deepcopy(self.plan)
            mutate(plan)
            with self.assertRaises(DirectorError):
                validate(plan)

    def test_all_workflows_preflight_and_keep_audio_path(self):
        info = read_json(ROOT / "tests/fixtures/object_info.json")
        for profile in ("preview", "quality"):
            for shot in self.plan["shots"]:
                graph = build(self.plan, shot, 42, "test", profile, "reference.png")
                preflight(graph, info)
                self.assertEqual(graph["12"]["inputs"]["samples"], graph["11"]["inputs"]["samples"])
                self.assertEqual(graph["13"]["inputs"]["audio"], ["12", 0])
                for d in shot["dialogue"]:
                    self.assertIn(d["text"], graph["5"]["inputs"]["prompt"])

    def test_native_connections_match_official_template(self):
        template = read_json(ROOT / "vendor/video_minimax_h3_t2v.json")["definitions"]["subgraphs"][0]
        nodes = {n["id"]: n for n in template["nodes"]}
        upstream_edges = set()
        for link in template["links"]:
            if link["origin_id"] in nodes and link["target_id"] in nodes:
                src, dst = nodes[link["origin_id"]], nodes[link["target_id"]]
                upstream_edges.add((src["type"], link["origin_slot"], dst["type"], dst["inputs"][link["target_slot"]]["name"]))
        graph = build(self.plan, self.plan["shots"][0], 1, "test")
        for node in graph.values():
            for name, val in node["inputs"].items():
                if not isinstance(val, list) or node["class_type"] == "SaveVideo":
                    continue
                edge = (graph[val[0]]["class_type"], val[1], node["class_type"], name)
                # Turbo switches are intentionally resolved to the base UNET locally.
                if edge[0] != "UNETLoader":
                    self.assertIn(edge, upstream_edges)

    def test_fixture_input_names_match_pinned_native_source(self):
        classes = {}
        for path in (ROOT / "vendor").glob("*.py"):
            for node in ast.parse(path.read_text()).body:
                if isinstance(node, ast.ClassDef):
                    classes[node.name] = node
        fixture = read_json(ROOT / "tests/fixtures/object_info.json")
        for kind, info in fixture.items():
            methods = classes[kind].body
            schema = next((n for n in methods if isinstance(n, ast.FunctionDef) and n.name == "define_schema"), None)
            if schema is None:
                schema = next(n for n in methods if isinstance(n, ast.FunctionDef) and n.name == "INPUT_TYPES")
                names = {n.value for n in ast.walk(schema) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
            else:
                names = {n.args[0].value for n in ast.walk(schema)
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                         and n.func.attr == "Input" and n.args and isinstance(n.args[0], ast.Constant)}
            for key in list(info["input"]["required"]) + list(info["input"]["optional"]):
                self.assertIn(key, names, kind + "." + key)

    def test_preflight_detects_missing_weights_nodes_and_bad_links(self):
        original = read_json(ROOT / "tests/fixtures/object_info.json")
        graph = build(self.plan, self.plan["shots"][0], 1, "test")
        info = copy.deepcopy(original)
        info["UNETLoader"]["input"]["required"]["unet_name"][0] = []
        with self.assertRaisesRegex(DirectorError, "Unavailable value"):
            preflight(graph, info)
        info = copy.deepcopy(original)
        del info["MiniMaxH3ImageToVideo"]
        with self.assertRaisesRegex(DirectorError, "Missing node"):
            preflight(graph, info)
        graph["13"]["inputs"]["audio"] = ["11", 0]
        with self.assertRaisesRegex(DirectorError, "Incompatible"):
            preflight(graph, original)

    def test_real_dynamic_codec_schema_and_invalid_option(self):
        info = read_json(ROOT / "tests/fixtures/object_info.json")
        self.assertEqual(info["SaveVideo"]["input"]["required"]["codec"][0], "COMFY_DYNAMICCOMBO_V3")
        graph = build(self.plan, self.plan["shots"][0], 1, "test")
        preflight(graph, info)
        graph["14"]["inputs"]["codec"] = "not-a-codec"
        with self.assertRaisesRegex(DirectorError, "dynamic option"):
            preflight(graph, info)

    def test_model_lock_contains_metadata_not_weights(self):
        lock = read_json(ROOT / "config/models.lock.json")
        self.assertEqual(len(lock["files"]), 4)
        for f in lock["files"]:
            self.assertRegex(f["sha256"], r"^[0-9a-f]{64}$")
            self.assertIn(lock["revision"], f["url"])
        self.assertFalse(list((ROOT / "vendor").rglob("*.safetensors")))

    def test_pod_request_matches_public_runpod_openapi_schema(self):
        from tests.test_readiness import assert_request_contract
        for volume in (None, 'volume-test'):
            assert_request_contract(self, pod_config("ssh-ed25519 AAAA test", volume, "US-TX-3"))


class ProtocolTests(unittest.TestCase):
    def graph(self):
        p = sample_plan()
        return build(p, p["shots"][0], 1, "test")

    def test_submit_poll_download_native_video_in_images(self):
        with FakeServer() as server, tempfile.TemporaryDirectory() as tmp:
            c = Comfy(server.url)
            pid = c.submit(self.graph(), "correlation")
            entry = c.wait(pid, timeout=1, interval=0.01)
            c.download(entry, Path(tmp) / "video.mp4")
            self.assertEqual((Path(tmp) / "video.mp4").read_bytes(), server.video)
            self.assertEqual(c.recover("correlation"), pid)

    def test_dropped_post_is_never_retried_and_can_recover(self):
        with FakeServer() as server:
            server.drop_response = True
            c = Comfy(server.url)
            with self.assertRaises(APIError) as error:
                c.submit(self.graph(), "lost-response")
            self.assertTrue(error.exception.ambiguous)
            self.assertEqual(len(server.posts), 1)
            self.assertEqual(c.recover("lost-response"), "job-1")

    def test_rejected_post_is_not_retried(self):
        with FakeServer() as server:
            server.reject = True
            with self.assertRaises(APIError) as error:
                Comfy(server.url).submit(self.graph(), "rejected")
            self.assertFalse(error.exception.ambiguous)
            self.assertEqual(len(server.posts), 1)

    def test_transient_read_failures_retry(self):
        with FakeServer() as server, patch("director.http.time.sleep"):
            server.transient_gets = 2
            self.assertIn("MiniMaxH3ImageToVideo", Comfy(server.url).info())
            self.assertEqual(server.transient_gets, 0)

    def test_redirect_is_not_followed_with_credentials(self):
        with FakeServer() as server:
            server.redirect = "https://example.invalid/collect"
            with self.assertRaisesRegex(APIError, "HTTP 302"):
                Comfy(server.url, "secret").info()

    def test_malformed_submission_is_uncertain_and_recoverable(self):
        with FakeServer() as server:
            server.malformed_response = True
            c = Comfy(server.url)
            with self.assertRaises(APIError) as error:
                c.submit(self.graph(), "malformed")
            self.assertTrue(error.exception.ambiguous)
            self.assertEqual(c.recover("malformed"), "job-1")
            self.assertEqual(len(server.jobs), 1)

    def test_accepted_job_with_node_warnings_keeps_its_id(self):
        with FakeServer() as server:
            server.accepted_warnings = True
            pid = Comfy(server.url).submit(self.graph(), "accepted-with-warnings")
            self.assertEqual(pid, "job-1")
            self.assertEqual(len(server.jobs), 1)

    def test_execution_failure_and_timeout(self):
        with FakeServer() as server:
            server.fail_job = True
            c = Comfy(server.url)
            pid = c.submit(self.graph(), "failure")
            with self.assertRaisesRegex(DirectorError, "OutOfMemoryError"):
                c.wait(pid, timeout=1)
            server.pending = True
            with self.assertRaisesRegex(DirectorError, "still be running"):
                c.wait(pid, timeout=0.02, interval=0.01)

    def test_http_retries_respect_poll_deadline(self):
        with FakeServer() as server:
            c = Comfy(server.url)
            pid = c.submit(self.graph(), "deadline")
            server.history_status = 503
            started = time.monotonic()
            with self.assertRaisesRegex(DirectorError, "still be running"):
                c.wait(pid, timeout=0.05, interval=0.01)
            self.assertLess(time.monotonic() - started, 0.5)

    def test_empty_or_multiple_outputs_rejected(self):
        with FakeServer() as server, tempfile.TemporaryDirectory() as tmp:
            c = Comfy(server.url)
            with self.assertRaisesRegex(DirectorError, "found 0"):
                c.download({"outputs": {}}, Path(tmp) / "out.mp4")

    def test_download_truncation_keeps_existing_destination(self):
        with FakeServer() as server, tempfile.TemporaryDirectory() as tmp:
            server.download_truncated = True
            c = Comfy(server.url)
            pid = c.submit(self.graph(), "truncate")
            path = Path(tmp) / "clip.mp4"
            path.write_bytes(b"previous")
            with self.assertRaises(APIError):
                c.download(c.wait(pid), path)
            self.assertEqual(path.read_bytes(), b"previous")
            self.assertFalse(path.with_suffix(".mp4.part").exists())

    def test_error_messages_do_not_include_secrets(self):
        with FakeServer() as server:
            server.unauthorized = True
            with self.assertRaises(APIError) as error:
                Comfy(server.url, "api-key-secret").info()
            self.assertNotIn("sensitive-server-content", str(error.exception))
            self.assertNotIn("api-key-secret", str(error.exception))

    def test_insecure_remote_urls_rejected(self):
        for url in ("http://remote.example", "https://user:secret@example.com", "https://example.com?key=secret"):
            with self.assertRaises(DirectorError):
                HTTP(url)

    def test_runpod_create_list_stop_and_response_redaction(self):
        with FakeServer() as server, tempfile.TemporaryDirectory() as tmp:
            rp = RunPod("secret", server.url + "/v2")
            payload = pod_config("ssh-ed25519 AAAA test")
            state = Path(tmp) / "pod.json"
            created = rp.create(payload, state)
            self.assertEqual(created["pod"]["id"], "pod-test")
            self.assertNotIn("not-for-logs", state.read_text())
            self.assertNotIn("env", created["pod"])
            self.assertEqual(len(rp.list()), 1)
            rp.stop("pod-test")
            self.assertEqual(rp.get('pod-test')['status'], 'EXITED')
            self.assertEqual(json.loads(server.posts[-1][1]), {'action': 'stop'})
            with self.assertRaisesRegex(DirectorError, "exists"):
                rp.create(payload, state)

    def test_runpod_uncertain_create_persists_state_without_retry(self):
        with FakeServer() as server, tempfile.TemporaryDirectory() as tmp:
            server.drop_response = True
            state = Path(tmp) / "pod.json"
            with self.assertRaises(APIError):
                RunPod("secret", server.url + "/v2").create(pod_config("ssh-ed25519 AAAA"), state)
            self.assertEqual(read_json(state)["status"], "unknown")
            self.assertEqual(len(server.posts), 1)


class RealMediaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Tests fail clearly if the optional media tools are not installed.
        cls.tmp = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.tmp.name) / "synthetic.mp4"
        media.run([media.executable("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=512x384:rate=24",
                   "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", str(124 / 24),
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", cls.fixture])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_full_two_shot_pipeline_resume_review_and_real_assembly(self):
        with FakeServer(self.fixture.read_bytes()) as server, tempfile.TemporaryDirectory() as tmp:
            p = sample_plan()
            directory = Path(tmp) / "run"
            c = Comfy(server.url)
            state = render(p, c, directory, poll_interval=0.01)
            self.assertEqual(len(server.jobs), 2)
            self.assertEqual(len(server.uploads), 1)
            self.assertIn(b"\x89PNG", server.uploads[0])
            self.assertTrue((directory / "test_b/contact_sheet.jpg").exists())
            with self.assertRaisesRegex(DirectorError, "creative review"):
                assemble_run(directory, Path(tmp) / "final.mp4")
            render(p, c, directory)
            self.assertEqual(len(server.jobs), 2, "resume must not generate duplicates")
            for sid in state["shot_order"]:
                review(directory, sid, "accepted", "Synthetic protocol test; no model quality claim")
            quality = assemble_run(directory, Path(tmp) / "final.mp4")
            self.assertTrue(quality["technical_pass"])
            self.assertAlmostEqual(quality["duration"], 248 / 24, delta=0.15)
            self.assertEqual(quality["audio_channels"], 2)
            with self.assertRaisesRegex(DirectorError, "changed"):
                render(p, c, directory, seed=2002)

    def test_resume_recovers_lost_submission_without_new_job(self):
        with FakeServer(self.fixture.read_bytes()) as server, tempfile.TemporaryDirectory() as tmp:
            p = sample_plan()
            c = Comfy(server.url)
            server.drop_response = True
            with self.assertRaises(APIError):
                render(p, c, tmp, shot_id="test_a")
            server.drop_response = False
            render(p, c, tmp, shot_id="test_a")
            self.assertEqual(len(server.jobs), 1)

    def test_missing_audio_fails_technical_qc(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "silent.mp4"
            media.run([media.executable("ffmpeg"), "-v", "error", "-i", self.fixture, "-an", "-c:v", "copy", path])
            self.assertFalse(media.check(path)["technical_pass"])

    def test_corrupt_media_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.mp4"
            path.write_bytes(b"not a movie")
            with self.assertRaises(DirectorError):
                media.check(path)

    def test_saved_clip_tamper_detected_and_run_lock(self):
        with FakeServer(self.fixture.read_bytes()) as server, tempfile.TemporaryDirectory() as tmp:
            c = Comfy(server.url)
            p = sample_plan()
            render(p, c, tmp, shot_id="test_a")
            (Path(tmp) / "test_a/clip.mp4").write_bytes(b"modified")
            with self.assertRaisesRegex(DirectorError, "modified"):
                render(p, c, tmp, shot_id="test_a")
            with run_lock(tmp):
                with self.assertRaisesRegex(DirectorError, "Another process"):
                    render(p, c, tmp, shot_id="test_a")

    def test_resume_finishes_downloaded_clip_after_history_is_lost(self):
        with FakeServer(self.fixture.read_bytes()) as server, tempfile.TemporaryDirectory() as tmp:
            c = Comfy(server.url)
            with patch("director.pipeline.media.contact_sheet", side_effect=DirectorError("interrupted local processing")):
                with self.assertRaisesRegex(DirectorError, "interrupted local"):
                    render(sample_plan(), c, tmp, shot_id="test_a")
            server.jobs.clear()
            old_posts = len(server.posts)
            state = render(sample_plan(), c, tmp, shot_id="test_a", timeout=0.02, poll_interval=0.01)
            self.assertEqual(state["shots"]["test_a"]["status"], "complete")
            self.assertEqual(len(server.posts), old_posts)

    def test_invalid_timeout_fails_before_any_submission(self):
        with FakeServer(self.fixture.read_bytes()) as server, tempfile.TemporaryDirectory() as tmp:
            for n, timeout in enumerate([float("nan"), float("inf"), 0, -1]):
                with self.assertRaisesRegex(DirectorError, "finite positive"):
                    render(sample_plan(), Comfy(server.url), Path(tmp) / str(n), shot_id="test_a", timeout=timeout)
            self.assertEqual(len(server.posts), 0)

    def test_mono_audio_is_not_reported_as_native_stereo(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mono.mp4"
            media.run([media.executable("ffmpeg"), "-v", "error", "-i", self.fixture, "-c:v", "copy", "-ac", "1", path])
            self.assertFalse(media.check(path)["technical_pass"])

    def test_failed_frame_extraction_cannot_reuse_stale_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "frame.png"
            target.write_bytes(b"previous frame")
            with patch("director.media.run", return_value=subprocess.CompletedProcess([], 0, "124\n", "")):
                with self.assertRaisesRegex(DirectorError, "extract final frame"):
                    media.last_frame(self.fixture, target)
            self.assertEqual(target.read_bytes(), b"previous frame")

    def test_last_frame_matches_the_actual_last_decoded_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "frame.png"
            media.last_frame(self.fixture, target)
            expected = media.run([media.executable("ffmpeg"), "-v", "error", "-i", self.fixture,
                                  "-map", "0:v:0", "-vf", "select=eq(n\\,123),format=rgb24", "-f", "framemd5", "-"])
            actual = media.run([media.executable("ffmpeg"), "-v", "error", "-i", target,
                                "-map", "0:v:0", "-vf", "format=rgb24", "-f", "framemd5", "-"])
            def checksum(result):
                return [line.split(",")[-1].strip() for line in result.stdout.splitlines() if not line.startswith("#")]
            self.assertEqual(checksum(actual), checksum(expected))

    def test_rejected_shot_cannot_be_reused_for_continuation(self):
        with FakeServer(self.fixture.read_bytes()) as server, tempfile.TemporaryDirectory() as tmp:
            c = Comfy(server.url)
            render(sample_plan(), c, tmp, shot_id="test_a")
            review(tmp, "test_a", "rejected", "Wrong dialogue")
            posts = len(server.posts)
            with self.assertRaisesRegex(DirectorError, "Shot was rejected"):
                render(sample_plan(), c, tmp, shot_id="test_a")
            self.assertEqual(len(server.posts), posts)


class PackagingTests(unittest.TestCase):
    def test_server_setup_default_never_mutates_or_downloads(self):
        from scripts.setup_server import main
        with patch("scripts.setup_server.command") as command, patch("scripts.setup_server.download_model") as download:
            with contextlib.redirect_stdout(io.StringIO()):
                main([])
            command.assert_not_called()
            download.assert_not_called()

    def test_server_setup_refuses_downloads_on_local_mac(self):
        from scripts.setup_server import main
        with patch("scripts.setup_server.platform.system", return_value="Darwin"), patch("scripts.setup_server.download_model") as download, patch("scripts.setup_server.command") as command:
            for args in (["--download-models"], ["--download-models", "--fast-downloads", "--with-references"]):
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(DirectorError, "Linux NVIDIA"):
                    main(args)
            download.assert_not_called()
            command.assert_not_called()

    def test_model_download_verifies_bytes_and_reuses_existing(self):
        from scripts.setup_server import download_model
        import hashlib
        content = b"tiny test fixture, not model weights"
        item = {"path": "vae/test.safetensors", "size": len(content), "sha256": hashlib.sha256(content).hexdigest(), "url": "https://example.invalid/test"}
        with tempfile.TemporaryDirectory() as tmp:
            def download(args):
                Path(args[args.index("--output") + 1]).write_bytes(content)
            with patch("scripts.setup_server.command", side_effect=download) as call:
                self.assertEqual(download_model(item, tmp), "downloaded_verified")
                self.assertEqual(download_model(item, tmp), "verified_existing")
                self.assertEqual(call.call_count, 1)

    def test_bundle_excludes_environment_weights_runs_and_venv(self):
        from scripts.bundle import bundle
        with tempfile.TemporaryDirectory() as tmp:
            path = bundle(Path(tmp) / "code.tar.gz")
            with tarfile.open(path) as archive:
                names = archive.getnames()
                self.assertIn("seinfield/config/models.lock.json", names)
                self.assertIn("seinfield/director/__main__.py", names)
                for name in names:
                    self.assertFalse(any(x in name for x in (".env", ".venv", "/runs/", ".safetensors", "__pycache__")), name)

    def test_completed_partial_model_is_promoted_without_network(self):
        from scripts.setup_server import download_model
        import hashlib
        content = b"tiny complete partial fixture"
        item = {"path": "test.safetensors", "size": len(content), "sha256": hashlib.sha256(content).hexdigest(), "url": "https://example.invalid/test"}
        with tempfile.TemporaryDirectory() as tmp:
            part = Path(tmp) / "test.safetensors.part"
            part.write_bytes(content)
            with patch("scripts.setup_server.command") as call:
                download_model(item, tmp)
                call.assert_not_called()
            self.assertEqual((Path(tmp) / "test.safetensors").read_bytes(), content)

    def test_disk_budget_accounts_for_partial_and_corrupt_targets(self):
        from scripts.setup_server import inspect_model
        import hashlib
        good = b"correct model fixture"
        item = {"path": "test.safetensors", "size": len(good), "sha256": hashlib.sha256(good).hexdigest()}
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "test.safetensors"
            target.write_bytes(b"x" * len(good))
            self.assertEqual(inspect_model(item, tmp)["remaining_bytes"], len(good))
            part = Path(tmp) / "test.safetensors.part"
            part.write_bytes(good[:5])
            self.assertEqual(inspect_model(item, tmp)["remaining_bytes"], len(good) - 5)
            target.write_bytes(good)
            self.assertEqual(inspect_model(item, tmp)["remaining_bytes"], 0)
            self.assertEqual(inspect_model(item, tmp)["action"], "reuse")

    def test_invalid_full_partial_model_is_not_promoted(self):
        from scripts.setup_server import download_model
        import hashlib
        good = b"valid fixture"
        item = {"path": "test.safetensors", "size": len(good), "sha256": hashlib.sha256(good).hexdigest()}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "test.safetensors.part").write_bytes(b"x" * len(good))
            with self.assertRaisesRegex(DirectorError, "invalid checksum"):
                download_model(item, tmp)
            self.assertFalse((Path(tmp) / "test.safetensors").exists())


if __name__ == "__main__":
    unittest.main()
