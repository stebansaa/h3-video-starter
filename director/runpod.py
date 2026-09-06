import json
import os
import urllib.parse
import uuid
from pathlib import Path

from .common import DirectorError, ROOT, read_json, write_json
from .http import APIError, HTTP


class RunPod:
    def __init__(self, key, base="https://api.runpod.io/v2"):
        if not key:
            raise DirectorError("Set RUNPOD_API_KEY for infrastructure operations.")
        self.http = HTTP(base, key)

    def list(self):
        result = self.http.request("GET", "/pods")  # rp-migrate: ignore — relative to the v2 base
        if not isinstance(result, dict) or not isinstance(result.get("pods"), list):
            raise APIError("RunPod v2 response omitted the Pods list.")
        return result["pods"]

    def get(self, pod_id):
        return self.http.request("GET", "/pods/" + urllib.parse.quote(pod_id, safe=""))  # rp-migrate: ignore — v2 base

    def stop(self, pod_id):
        return self.http.request("POST", "/pods/" + urllib.parse.quote(pod_id, safe="") + "/action", {"action": "stop"})  # rp-migrate: ignore — v2 action

    def create(self, payload, state_path):
        if not isinstance(payload, dict) or not payload.get("image") or not isinstance(payload.get("gpu"), dict):
            raise DirectorError("Expected a v2 GPU Pod request; regenerate it with pod-config.")
        # Never repeat a possibly successful create after a dropped connection.
        state_path = Path(state_path)
        pending = {"name": payload["name"], "status": "submitting"}
        state_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with state_path.open("x") as f:
                json.dump(pending, f)
                f.flush()
                os.fsync(f.fileno())
        except FileExistsError:
            raise DirectorError("Pod state file exists; inspect/recover it before creating another Pod.") from None
        try:
            pod = self.http.request("POST", "/pods", payload)  # rp-migrate: ignore — v2 base
            if not isinstance(pod, dict) or not isinstance(pod.get("id"), str) or not pod["id"]:
                raise APIError("RunPod response omitted the Pod ID.", ambiguous=True)
        except APIError as exc:
            pending["status"] = "unknown" if exc.ambiguous else "rejected"
            write_json(state_path, pending)
            raise
        pending.update(status="created", pod=public_pod(pod))
        write_json(state_path, pending)
        return pending


def public_pod(pod):
    # Full API responses can contain environment variables, including secrets.
    return {k: pod[k] for k in ("id", "name", "status", "actions", "cost", "gpu", "image",
                                "ssh", "mounts", "cloud", "dataCenterId", "cudaVersion") if k in pod}  # rp-migrate: ignore — v2 Pod fields


def check_pod(pod, expected_gpu="NVIDIA GeForce RTX 5090"):
    """Verify the allocated host and direct SSH before uploading/installing models."""
    lock = read_json(ROOT / "config/server.lock.json")
    problems = []
    gpu = pod.get('gpu') or {}
    if pod.get('status') != 'RUNNING':
        problems.append('Pod is not RUNNING')
    if gpu.get('id') != expected_gpu or gpu.get('count') != 1:
        problems.append('allocated GPU does not match the requested single GPU')
    if gpu.get('memory', 0) < lock['min_system_ram_gb'] or gpu.get('vcpuCount', 0) < lock['min_vcpus']:  # rp-migrate: ignore — nested v2 GPU fields
        problems.append('allocated RAM/CPU is below the request')
    try:
        cuda = tuple(map(int, (pod.get('cudaVersion') or '').split('.')))
    except ValueError:
        cuda = ()
    if cuda < tuple(map(int, lock['cuda_minimum'].split('.'))):
        problems.append('host CUDA version is missing or too old')
    if pod.get('image') != lock['image']:
        problems.append('image does not match the pinned build')
    direct = (pod.get('ssh') or {}).get('direct') or {}
    if not direct.get('host') or type(direct.get('port')) is not int or not 1 <= direct['port'] <= 65535:
        problems.append('direct SSH is not available yet')
    if problems:
        raise DirectorError('Pod check failed: ' + '; '.join(problems))
    return {'status': 'passed', 'pod': public_pod(pod)}


def pod_config(public_key, network_volume_id=None, data_center_id=None,
               gpu_id="NVIDIA GeForce RTX 5090", temporary=False):
    key = public_key.strip()
    if not key.startswith(("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-")) or "\n" in key:
        raise DirectorError("Provide an SSH public key, not a private key.")
    lock = read_json(ROOT / "config/server.lock.json")
    if not isinstance(gpu_id, str) or not gpu_id.strip():
        raise DirectorError("Provide a GPU identifier from the live catalog.")
    if temporary and network_volume_id:
        raise DirectorError("Temporary container storage and a network volume are separate choices.")
    payload = {"name": "seinfield-" + uuid.uuid4().hex[:12],
               "image": lock["image"],
               "gpu": {"id": gpu_id, "count": 1,
                       "minCudaVersion": lock["cuda_minimum"],  # rp-migrate: ignore — nested under gpu in v2
                       "minRamPerGpu": lock["min_system_ram_gb"], "minVcpuCountPerGpu": lock["min_vcpus"]},
               "cloud": "SECURE", "disk": lock["container_disk_gb"],
               "mounts": {"persistent": {"size": lock["volume_disk_gb"], "path": "/workspace"}},
               "ports": ["22/tcp"], "env": {"PUBLIC_KEY": key}}
    if network_volume_id:
        payload["mounts"] = {"network": [{"volumeId": network_volume_id, "path": "/workspace"}]}
    if data_center_id:
        payload["dataCenterIds"] = [data_center_id]
    if temporary:
        payload.pop("mounts")
        payload["disk"] = 200
    return payload
