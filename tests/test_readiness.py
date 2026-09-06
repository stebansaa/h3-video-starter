"""Deployment contracts and a full-length opening-shot simulation; no GPU/weights."""
import copy
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from director import media
from director.common import ROOT, DirectorError, read_json
from director.http import APIError
from director.plan import load_plan
from director.runpod import RunPod, check_pod, pod_config
from scripts.setup_server import host_limits, main as setup, validate_hardware
from tests.fake_server import FakeServer


def assert_request_contract(test, payload):
    """Check request fields recursively against unmodified live OpenAPI schemas.

    Covers the types/composition/constraints used by this request, not a general
    JSON Schema validator. Handler-level exclusivity is checked separately.
    """
    schemas = read_json(ROOT / 'vendor/runpod-v2-contract.json')['schemas']

    def resolve(schema):
        if '$ref' in schema:
            return resolve(schemas[schema['$ref'].split('/')[-1]])
        result = dict(schema)
        for part in schema.get('allOf', []):
            part = resolve(part)
            result['properties'] = dict(result.get('properties', {}), **part.get('properties', {}))
            result['required'] = list(set(result.get('required', []) + part.get('required', [])))
            if 'type' in part:
                result['type'] = part['type']
        return result

    def check(value, schema):
        schema = resolve(schema)
        types = {'integer': (int,), 'number': (int, float), 'string': (str,),
                 'array': (list,), 'object': (dict,), 'boolean': (bool,), 'null': (type(None),)}
        kind = schema.get('type', 'object' if 'properties' in schema else None)
        if kind:
            kinds = kind if isinstance(kind, list) else [kind]
            test.assertIn(type(value), tuple(t for k in kinds for t in types[k]))
        if 'enum' in schema:
            test.assertIn(value, schema['enum'])
        for key, fn in (('minimum', test.assertGreaterEqual), ('maximum', test.assertLessEqual)):
            if key in schema:
                fn(value, schema[key])
        if 'pattern' in schema:
            test.assertRegex(value, schema['pattern'])
        if 'minLength' in schema:
            test.assertGreaterEqual(len(value), schema['minLength'])
        if isinstance(value, dict):
            test.assertTrue(set(schema.get('required', [])).issubset(value))
            properties = schema.get('properties', {})
            for key, item in value.items():
                if key in properties:
                    check(item, properties[key])
                else:
                    additional = schema.get('additionalProperties', False)
                    test.assertIsInstance(additional, dict, 'Unknown request field: ' + key)
                    check(item, additional)
        elif isinstance(value, list):
            if 'maxItems' in schema:
                test.assertLessEqual(len(value), schema['maxItems'])
            for item in value:
                check(item, schema['items'])

    check(payload, schemas['CreatePodRequest'])
    test.assertTrue(payload.get('image'))
    test.assertEqual(set(payload['mounts']) & {'network', 'persistent'}, set(payload['mounts']))
    test.assertEqual(len(payload['mounts']), 1)


def suitable_hardware():
    return {'system_ram_bytes': 64 * 1024**3, 'vcpus': 8, 'cuda_available': True,
            'cuda': '13.0', 'devices': [{'name': 'RTX 5090', 'memory_bytes': 32 * 1024**3}]}


class DeploymentReadinessTests(unittest.TestCase):
    def test_runpod_requests_use_the_identifier_accepted_by_the_live_api(self):
        with FakeServer() as server:
            server.required_user_agent = 'seinfield-director/1.0'
            self.assertEqual(RunPod('fake', server.url + '/v2').list(), [])

    def test_v2_hardware_filters_and_mounts_are_preserved(self):
        p = pod_config('ssh-ed25519 AAAA test')
        assert_request_contract(self, p)
        self.assertEqual(p['gpu']['minRamPerGpu'], 64)
        self.assertEqual(p['gpu']['minVcpuCountPerGpu'], 8)
        self.assertEqual(p['gpu']['minCudaVersion'], '13.0')
        self.assertEqual(p['disk'], 150)
        self.assertEqual(p['ports'], ['22/tcp'])
        self.assertEqual(p['env']['PUBLIC_KEY'], 'ssh-ed25519 AAAA test')
        network = pod_config('ssh-ed25519 AAAA test', 'volume-test', 'US-TX-3')
        assert_request_contract(self, network)
        self.assertNotIn('persistent', network['mounts'])

    def test_old_request_rejected_before_billable_submission(self):
        with FakeServer() as server, tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(DirectorError, 'regenerate'):
                RunPod('fake', server.url + '/v2').create({'name': 'old', 'imageName': 'old'}, Path(tmp) / 'state.json')
            self.assertEqual(server.posts, [])

    def test_v2_list_rejects_a_legacy_envelope(self):
        client = RunPod('fake')
        with patch.object(client.http, 'request', return_value=[]):
            with self.assertRaises(APIError):
                client.list()

    def test_allocated_host_must_match_and_expose_direct_ssh(self):
        p = {'status': 'RUNNING', 'image': read_json(ROOT / 'config/server.lock.json')['image'],
             'gpu': {'id': 'NVIDIA GeForce RTX 5090', 'count': 1, 'memory': 64, 'vcpuCount': 8},
             'cudaVersion': '13.2', 'ssh': {'direct': {'host': '203.0.113.1', 'port': 2222}}}
        self.assertEqual(check_pod(p)['status'], 'passed')
        for mutate in (lambda x: x.update(status='ERROR'), lambda x: x['gpu'].update(memory=35),
                       lambda x: x.update(cudaVersion='12.9'), lambda x: x['ssh'].update(direct=None)):
            bad = copy.deepcopy(p)
            mutate(bad)
            with self.assertRaises(DirectorError):
                check_pod(bad)

    def test_hardware_checks_reject_unsuitable_runtime(self):
        lock = read_json(ROOT / 'config/server.lock.json')
        validate_hardware(suitable_hardware(), lock)
        for changes in ({'system_ram_bytes': 35 * 1024**3}, {'vcpus': 4}, {'cuda': '12.8'},
                        {'cuda_available': False}, {'devices': []},
                        {'devices': [{'memory_bytes': 24 * 1024**3}]}):
            with self.assertRaises(DirectorError):
                validate_hardware(dict(suitable_hardware(), **changes), lock)

    def test_container_limits_override_larger_physical_host(self):
        files = {'/proc/meminfo': 'MemTotal: 536870912 kB\n',
                 '/sys/fs/cgroup/memory.max': str(35 * 1024**3),
                 '/sys/fs/cgroup/cpu.max': '400000 100000'}
        with patch.object(Path, 'read_text', lambda p: files[str(p)]), \
             patch.object(Path, 'is_file', lambda p: str(p) in files), \
             patch('scripts.setup_server.os.sched_getaffinity', return_value=set(range(64)), create=True):
            self.assertEqual(host_limits(), {'system_ram_bytes': 35 * 1024**3, 'vcpus': 4})

    def test_unsuitable_server_is_rejected_before_install_or_download(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch('scripts.setup_server.platform.system', return_value='Linux'), \
             patch('scripts.setup_server.shutil.which', return_value='/usr/bin/fake'), \
             patch('scripts.setup_server.sys.version_info', (3, 12, 3)), \
             patch('scripts.setup_server.probe_server', return_value=dict(suitable_hardware(), cuda='12.8')), \
             patch('scripts.setup_server.command') as command, \
             patch('scripts.setup_server.download_model') as download, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp) / 'not-created'
            with self.assertRaisesRegex(DirectorError, 'hardware check'):
                setup(['--root', str(root), '--install', '--download-models'])
            command.assert_called_once_with(['nvidia-smi'])
            download.assert_not_called()
            self.assertFalse(root.exists())

    def test_readonly_server_check_does_not_create_runtime(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch('scripts.setup_server.platform.system', return_value='Linux'), \
             patch('scripts.setup_server.shutil.which', return_value='/usr/bin/fake'), \
             patch('scripts.setup_server.sys.version_info', (3, 12, 3)), \
             patch('scripts.setup_server.probe_server', return_value=suitable_hardware()), \
             patch('scripts.setup_server.command'), contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp) / 'not-created'
            setup(['--root', str(root), '--check'])
            self.assertFalse(root.exists())

    def test_xet_download_checks_hash_and_reuses_only_valid_files(self):
        import hashlib
        lock = read_json(ROOT / 'config/server.lock.json')
        models = {'repository': 'test/repo', 'revision': 'pinned', 'files': [
            {'path': 'diffusion_models/test.safetensors', 'size': 4,
             'sha256': hashlib.sha256(b'good').hexdigest()}]}
        with tempfile.TemporaryDirectory() as tmp, \
             patch('scripts.setup_server.platform.system', return_value='Linux'), \
             patch('scripts.setup_server.shutil.which', return_value='/usr/bin/fake'), \
             patch('scripts.setup_server.sys.version_info', (3, 12, 3)), \
             patch('scripts.setup_server.probe_server', return_value=suitable_hardware()), \
             patch('scripts.setup_server.read_json', side_effect=lambda p: models if p.name == 'models.lock.json' else lock), \
             contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            target = root / 'ComfyUI/models/diffusion_models/test.safetensors'
            target.parent.mkdir(parents=True)
            payload = [b'evil']
            transfers = []

            def command(args, **kwargs):
                if '-c' in args:
                    transfers.append(args)
                    target.write_bytes(payload[0])

            with patch('scripts.setup_server.command', side_effect=command):
                arguments = ['--root', tmp, '--download-models', '--fast-downloads']
                with self.assertRaisesRegex(DirectorError, 'SHA-256'):
                    setup(arguments)
                payload[0] = b'good'
                setup(arguments)
                self.assertEqual(len(transfers), 2)
                setup(arguments)
                self.assertEqual(len(transfers), 2)


class OpeningClipTest(unittest.TestCase):
    def test_actual_opening_cli_renders_one_shot_and_resumes_without_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / 'synthetic-opening.mp4'
            media.run([media.executable('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
                       'testsrc2=size=512x384:rate=24', '-f', 'lavfi', '-i',
                       'sine=frequency=440:sample_rate=48000', '-t', str(277 / 24),
                       '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ac', '2', fixture])
            with FakeServer(fixture.read_bytes()) as server:
                command = [sys.executable, '-m', 'director', 'render', '--shot', '01a',
                           '--url', server.url, '--run', str(root / 'run'), '--timeout', '10']
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                state = json.loads(result.stdout)
                self.assertEqual(state['shot_order'], ['01a'])
                self.assertEqual(state['shots']['01a']['review'], 'pending')
                self.assertEqual(len(server.jobs), 1)
                graph = next(iter(server.jobs.values()))['prompt'][2]
                self.assertEqual(graph['5']['inputs']['length'], 277)
                self.assertNotIn('first_frame', graph['5']['inputs'])
                for line in load_plan(ROOT / 'plans/episode.json')['shots'][0]['dialogue']:
                    self.assertIn(line['text'], graph['5']['inputs']['prompt'])
                qc = read_json(root / 'run/01a/qc.json')
                self.assertTrue(qc['technical_pass'])
                self.assertEqual(qc['audio_channels'], 2)
                self.assertTrue((root / 'run/01a/contact_sheet.jpg').is_file())
                resumed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
                self.assertEqual(resumed.returncode, 0, resumed.stderr)
                self.assertEqual(len(server.jobs), 1)
