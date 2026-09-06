import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from director.common import ROOT, DirectorError, file_digest, read_json, write_json
from director.credentials import value
from director.pipeline import review, assemble_run
from director.runpod import pod_config, check_pod


class StarterTests(unittest.TestCase):
    def test_credentials_are_data_and_environment_takes_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.env').write_text('RUNPOD_API_KEY="literal-$(echo-never-executed)"\n')
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(value('RUNPOD_API_KEY', root), 'literal-$(echo-never-executed)')
            with patch.dict(os.environ, {'RUNPOD_API_KEY': 'environment-value'}, clear=True):
                self.assertEqual(value('RUNPOD_API_KEY', root), 'environment-value')
            (root / '.env').write_text('RUNPOD_API_KEY="do-not-echo-this\n')
            with patch.dict(os.environ, {}, clear=True), self.assertRaises(DirectorError) as caught:
                value('RUNPOD_API_KEY', root)
            self.assertNotIn('do-not-echo-this', str(caught.exception))

    def test_legacy_key_file_is_supported_without_private_helpers(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            (Path(tmp) / 'key.env').write_text('fake-test-key\n')
            self.assertEqual(value('RUNPOD_API_KEY', tmp), 'fake-test-key')

    def test_mig_allocation_matches_request_and_keeps_hardware_guards(self):
        gpu = 'NVIDIA RTX PRO 6000 Blackwell Server Edition MIG 2g.48gb'
        request = pod_config('ssh-ed25519 AAAA test', gpu_id=gpu, temporary=True)
        self.assertEqual(request['disk'], 200)
        self.assertNotIn('mounts', request)
        self.assertEqual(request['gpu']['minRamPerGpu'], 64)
        pod = {'status': 'RUNNING', 'image': request['image'], 'cudaVersion': '13.2',
               'gpu': {'id': gpu, 'count': 1, 'memory': 125, 'vcpuCount': 8},
               'ssh': {'direct': {'host': '203.0.113.1', 'port': 2222}}}
        self.assertEqual(check_pod(pod, gpu)['status'], 'passed')
        with self.assertRaises(DirectorError):
            check_pod(pod)
        pod['gpu']['memory'] = 32
        with self.assertRaises(DirectorError):
            check_pod(pod, gpu)

    def test_required_edits_are_hash_bound_and_block_plain_assembly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);(root / 'a').mkdir();clip = root / 'a/clip.mp4'
            clip.write_bytes(b'controlled fixture; media probing is mocked')
            record = {'status': 'complete', 'review': 'pending', 'sha256': file_digest(clip)}
            write_json(root / 'state.json', {'shot_order': ['a'], 'profile': 'reference-preview', 'shots': {'a': record}})
            edit = {'source_sha256': record['sha256'], 'keep_frames': [[24, 96]], 'reason': 'Remove extra speech'}
            with patch('director.pipeline.media.probe', return_value={'duration': 5.0}):
                review(root, 'a', 'accepted', 'Only with this edit', edit)
            self.assertEqual(read_json(root / 'state.json')['shots']['a']['required_edit'], edit)
            with self.assertRaisesRegex(DirectorError, 'requires frame edits'):
                assemble_run(root, root / 'bad.mp4')
            with self.assertRaises(DirectorError):
                review(root, 'a', 'accepted', 'Wrong source', dict(edit, source_sha256='bad'))

    def test_recorded_example_refuses_to_omit_mandatory_cuts(self):
        from scripts.assemble_episode import main
        ex = ROOT / 'examples/bitcoin-contest'
        with tempfile.TemporaryDirectory() as tmp, patch.object(sys, 'argv', [
                'assemble_episode.py', '--run', str(ex / 'run'), '--transcripts', str(ex / 'transcripts'),
                '--out', str(Path(tmp) / 'bad.mp4')]):
            with self.assertRaisesRegex(DirectorError, 'Mandatory reviewed frame edit'):
                main()

    def test_transcript_cache_rechecks_changed_media_and_segment_selection(self):
        from scripts.transcribe_server import main
        calls = []
        class Model:
            def __init__(self, *args, **kwargs): pass
            def transcribe(self, path, **kwargs):
                calls.append((path, kwargs))
                return [], types.SimpleNamespace(language='en')
        original_exists = Path.exists
        def exists(path):
            return True if str(path) == '/dev/nvidiactl' else original_exists(path)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);source = root / 'clip.mp4';source.write_bytes(b'first')
            argv = ['transcribe_server.py', str(source), '--out', str(root / 'transcripts')]
            with patch('scripts.transcribe_server.platform.system', return_value='Linux'), \
                    patch.object(Path, 'exists', exists), \
                    patch.dict(sys.modules, {'faster_whisper': types.SimpleNamespace(WhisperModel=Model)}), \
                    patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()):
                main();main()
                self.assertEqual(len(calls), 1)
                source.write_bytes(b'revised')
                main()
                self.assertEqual(len(calls), 2)
                argv += ['--clip-timestamps', '1,2']
                main()
                self.assertEqual(len(calls), 3)
                self.assertNotIn('initial_prompt', calls[-1][1])


if __name__ == '__main__':
    unittest.main()
