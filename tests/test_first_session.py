import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from director.http import APIError
from scripts import first_session


class FirstSessionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {}, clear=True))
        self.stack.enter_context(patch.object(first_session, "verify", return_value={"verified_files": 1}))
        self.stack.enter_context(patch.object(first_session.platform, "system", return_value="Linux"))
        self.binaries = self.stack.enter_context(patch.object(first_session, "binary_ready", return_value=True))
        self.request = self.stack.enter_context(patch("director.http.HTTP.request"))

    def test_no_key_does_not_block_offline_work_or_contact_runpod(self):
        report = first_session.inspect(self.root)
        self.assertTrue(report["offline_ready"])
        self.assertFalse(report["ready_to_rent_gpu"])
        self.assertEqual(report["runpod_credentials"]["status"], "missing")
        self.request.assert_not_called()

    def test_present_key_is_not_mistaken_for_verified_auth(self):
        secret = "private-test-value-never-show"
        (self.root / ".env").write_text("RUNPOD_API_KEY=" + secret + "\n")
        report = first_session.inspect(self.root)
        self.assertEqual(report["runpod_credentials"]["status"], "present_not_verified")
        self.assertNotIn(secret, json.dumps(report))
        self.request.assert_not_called()

    def test_explicit_auth_uses_only_a_read_and_redacts_account_response(self):
        (self.root / ".env").write_text("RUNPOD_API_KEY=private-test-key\n")
        self.request.return_value = {"pods": [{"id": "private-account-resource", "env": {"TOKEN": "hidden-response-token"}}]}
        report = first_session.inspect(self.root, check_auth=True)
        self.request.assert_called_once_with("GET", "/pods")
        self.assertEqual(report["runpod_credentials"]["status"], "verified_read_access")
        self.assertEqual(report["read_only_api_requests"], 1)
        self.assertFalse(report["ready_to_rent_gpu"])
        for private in ("private-test-key", "private-account-resource", "hidden-response-token"):
            self.assertNotIn(private, json.dumps(report))

    def test_failed_auth_reports_failure_without_provider_exception_text(self):
        (self.root / ".env").write_text("RUNPOD_API_KEY=private-test-key\n")
        self.request.side_effect = APIError("private-provider-detail")
        report = first_session.inspect(self.root, check_auth=True)
        self.assertEqual(report["runpod_credentials"]["status"], "read_check_failed")
        self.assertNotIn("private-provider-detail", json.dumps(report))
        self.assertEqual(report["paid_requests"], 0)

    def test_missing_media_tools_produce_actionable_offline_failure(self):
        self.binaries.side_effect = lambda name: name != "ffprobe"
        report = first_session.inspect(self.root)
        self.assertFalse(report["offline_ready"])
        self.assertTrue(any("install_test_media.py" in x for x in report["next_steps"]))
        self.assertFalse(report["software_installed"])
        self.request.assert_not_called()

    def test_bad_credential_file_does_not_leak_or_prevent_offline_planning(self):
        (self.root / ".env").write_text('RUNPOD_API_KEY="private-unclosed-value\n')
        report = first_session.inspect(self.root, check_auth=True)
        self.assertTrue(report["offline_ready"])
        self.assertEqual(report["runpod_credentials"]["status"], "file_unreadable_or_invalid")
        self.assertNotIn("private-unclosed-value", json.dumps(report))
        self.request.assert_not_called()

    def test_cli_distinguishes_offline_readiness_from_requested_server_checks(self):
        self.binaries.side_effect = lambda name: name != "ssh"
        report = first_session.inspect(self.root)
        with patch.object(first_session, "inspect", return_value=report), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(first_session.main(["--json"]), 0)
            self.assertEqual(first_session.main(["--require-server-tools", "--json"]), 1)
            self.assertEqual(first_session.main(["--check-auth", "--json"]), 1)

    def test_modified_release_is_not_reported_ready(self):
        with patch.object(first_session, "verify", side_effect=ValueError("changed file")):
            report = first_session.inspect(self.root)
        self.assertFalse(report["offline_ready"])
        self.assertFalse(report["checks"]["package_integrity"])
        self.request.assert_not_called()

    def test_new_project_drops_historical_notes_without_changing_baseline(self):
        from director.common import ROOT
        from scripts import new_project
        paths = ("plans/episode-reference-v2.json", "plans/episode-mix.json",
                 "references/episode-v1/manifest-v2.json", "script.txt")
        for name in paths:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        source = self.root / paths[0]
        before = source.read_bytes()
        with patch.object(new_project, "ROOT", self.root):
            project = new_project.create("fresh-story")
        plan = json.loads((project / "plan.json").read_text())
        old_notes = json.loads(before)["production_notes"]
        self.assertFalse(set(plan["production_notes"]) & set(old_notes))
        self.assertEqual(plan["id"], "fresh-story")
        self.assertEqual(json.loads((project / "cuts.json").read_text())["shots"], {})
        self.assertEqual(source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
