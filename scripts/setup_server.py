"""Explicit, server-only setup. Default invocation prints a plan and changes nothing.

Model downloads are reachable only with --download-models, on a CUDA Linux server.
This script is not imported or invoked by the local render client.
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from director.common import DirectorError, file_digest, read_json, write_json


def command(args, **kwargs):
    subprocess.run([str(x) for x in args], check=True, **kwargs)


def host_limits():
    """Use container limits, not just the physical host's advertised memory/CPUs."""
    meminfo = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    ram = int(meminfo['MemTotal'].split()[0]) * 1024
    for name in ('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory/memory.limit_in_bytes'):
        path = Path(name)
        if path.is_file():
            value = path.read_text().strip()
            if value.isdigit():
                ram = min(ram, int(value))
    cpus = float(len(os.sched_getaffinity(0)))
    quota = Path('/sys/fs/cgroup/cpu.max')
    if quota.is_file():
        amount, period = quota.read_text().split()
        if amount != 'max':
            cpus = min(cpus, int(amount) / int(period))
    else:
        quota = Path('/sys/fs/cgroup/cpu/cpu.cfs_quota_us')
        period = Path('/sys/fs/cgroup/cpu/cpu.cfs_period_us')
        if quota.is_file() and period.is_file() and int(quota.read_text()) > 0:
            cpus = min(cpus, int(quota.read_text()) / int(period.read_text()))
    return {'system_ram_bytes': ram, 'vcpus': cpus}


def probe_server(python):
    code = """import json, torch
ready = torch.cuda.is_available()
devices = []
if ready:
    for i in range(torch.cuda.device_count()):
        p = torch.cuda.get_device_properties(i)
        devices.append({'name': p.name, 'memory_bytes': p.total_memory,
                        'capability': [p.major, p.minor]})
print(json.dumps({'torch': torch.__version__, 'cuda': torch.version.cuda,
                  'cuda_available': ready, 'devices': devices}))
"""
    result = json.loads(subprocess.check_output([str(python), '-c', code], text=True))
    result.update(host_limits())
    return result


def validate_hardware(report, lock):
    problems = []
    if report.get('system_ram_bytes', 0) < lock['min_system_ram_gb'] * 10**9:
        problems.append('need at least {} GB allocated system RAM'.format(lock['min_system_ram_gb']))
    if report.get('vcpus', 0) < lock['min_vcpus']:
        problems.append('need at least {} allocated vCPUs'.format(lock['min_vcpus']))
    try:
        cuda = tuple(int(n) for n in (report.get('cuda') or '').split('.')[:2])
    except ValueError:
        cuda = ()
    if not report.get('cuda_available') or cuda < tuple(map(int, lock['cuda_minimum'].split('.'))):
        problems.append('need working CUDA {}+ PyTorch'.format(lock['cuda_minimum']))
    devices = report.get('devices', [])
    if len(devices) != 1:
        problems.append('this configuration expects exactly one visible GPU')
    elif devices[0].get('memory_bytes', 0) < lock['min_vram_gb'] * 10**9:
        problems.append('need at least {} GB VRAM'.format(lock['min_vram_gb']))
    if problems:
        raise DirectorError('Server hardware check failed: ' + '; '.join(problems))


def inspect_model(item, models_dir):
    """Inspect local bytes only; model downloads are never implied by inspection."""
    relative = Path(item["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise DirectorError("Model path must stay within the models directory.")
    target = Path(models_dir) / relative
    part = target.with_suffix(target.suffix + ".part")
    status = {"target": target, "part": part, "remaining_bytes": 0}
    if target.is_file() and target.stat().st_size == item["size"] and file_digest(target) == item["sha256"]:
        return dict(status, action="reuse")
    part_size = part.stat().st_size if part.is_file() else 0
    if part_size > item["size"]:
        raise DirectorError("Oversized partial model: " + str(part))
    if part_size == item["size"]:
        if file_digest(part) != item["sha256"]:
            raise DirectorError("Completed partial model has an invalid checksum: " + str(part))
        return dict(status, action="promote")
    # A corrupt existing target stays intact until its replacement verifies.
    # Only the missing part of the replacement needs additional free space.
    return dict(status, action="download", remaining_bytes=item["size"] - part_size)


def download_model(item, models_dir, inspection=None):
    inspection = inspection or inspect_model(item, models_dir)
    target, part = inspection["target"], inspection["part"]
    if inspection["action"] == "reuse":
        return "verified_existing"
    target.parent.mkdir(parents=True, exist_ok=True)
    if inspection["action"] == "promote":
        os.replace(part, target)
        return "verified_partial_promoted"
    # curl resumes partial transfers; never print an HF credential or save it in config.
    command(["curl", "--fail", "--location", "--retry", "3", "--connect-timeout", "30",
             "--speed-time", "120", "--speed-limit", "1024", "--continue-at", "-", "--output", part, item["url"]])
    if part.stat().st_size != item["size"] or file_digest(part) != item["sha256"]:
        raise DirectorError("Model checksum/size mismatch: " + item["path"] + ". Inspect/remove the .part file before retrying.")
    os.replace(part, target)
    return "downloaded_verified"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default="/workspace/seinfield-runtime")
    p.add_argument("--check", action="store_true", help="Inspect GPU, CUDA and container RAM/CPU limits without installing or downloading")
    p.add_argument("--install", action="store_true", help="Install pinned ComfyUI and its dependencies on this GPU server")
    p.add_argument("--download-models", action="store_true", help="Download/verify ~42 GB of weights on this GPU server")
    p.add_argument("--fast-downloads", action="store_true", help="Use the server's Hugging Face Xet downloader, with checksum verification")
    p.add_argument("--start", action="store_true", help="Start the prepared ComfyUI server in foreground")
    p.add_argument("--with-references", action="store_true", help="Use pinned native AddGuide support and the additional Ref2VA checkpoint")
    args = p.parse_args(argv)
    lock = read_json(ROOT / "config/server.lock.json")
    models = read_json(ROOT / "config/models.lock.json")
    if args.with_references:
        references = read_json(ROOT / "config/reference-model.lock.json")
        lock["comfy_revision"] = references["comfy_revision"]
        lock["min_vcpus"] = references["min_vcpus"]
        models["files"] = [references["file"]] + [x for x in models["files"]
                            if x["path"] != "diffusion_models/" + models["roles"]["diffusion"]]
    location = Path(args.root).resolve()
    comfy = location / "ComfyUI"
    python = location / "venv/bin/python"
    report = {"runtime_directory": str(location), "comfy_revision": lock["comfy_revision"],
              "model_bytes": sum(x["size"] for x in models["files"]), "listen": "127.0.0.1:8189",
              "actions": {"check": args.check, "install": args.install, "download_models": args.download_models, "start": args.start}}
    print(json.dumps(report, indent=2), flush=True)
    if not any((args.check, args.install, args.download_models, args.start)):
        return
    if platform.system() != "Linux" or not shutil.which("nvidia-smi"):
        raise DirectorError("Setup mutations require a Linux NVIDIA GPU server. Local preparation never needs model weights.")
    if sys.version_info < (3, 12):
        raise DirectorError("Use Python 3.12+ for the remote ComfyUI installation.")
    command(["nvidia-smi"])
    hardware = probe_server(python if python.exists() else sys.executable)
    print(json.dumps({'hardware': hardware}, indent=2), flush=True)
    validate_hardware(hardware, lock)
    report['hardware'] = hardware
    if args.install:
        location.mkdir(parents=True, exist_ok=True)
        for binary in ("git", "curl", "ffmpeg", "ffprobe"):
            if not shutil.which(binary):
                raise DirectorError("Install missing server prerequisite: " + binary)
        if not comfy.exists():
            command(["git", "clone", "--depth", "1", "--no-checkout", "--filter=blob:none", lock["comfy_repository"], comfy])
        current = subprocess.check_output(["git", "-C", str(comfy), "status", "--porcelain"], text=True)
        # An unpopulated --no-checkout clone lists every tracked file as deleted.
        ready = (comfy / "main.py").exists()
        if ready and current.strip():
            raise DirectorError("ComfyUI checkout has local changes; refusing to overwrite it.")
        command(["git", "-C", comfy, "fetch", "--depth", "1", "origin", lock["comfy_revision"]])
        command(["git", "-C", comfy, "checkout", "--detach", lock["comfy_revision"]])
        if not python.exists():
            command([sys.executable, "-m", "venv", "--system-site-packages", location / "venv"])
        # Reuse the image's CUDA 13 PyTorch instead of fetching a second GPU stack.
        command([python, "-c", "import torch; assert torch.cuda.is_available(), 'CUDA unavailable'; assert tuple(map(int, torch.version.cuda.split('.')[:2])) >= (13,0), 'Need CUDA 13 PyTorch for int8_convrot'"])
        constraints = location / "torch-constraints.txt"
        installed = subprocess.check_output([python, "-c", "import importlib.metadata as m; print('\\n'.join(p+'=='+m.version(p) for p in ('torch','torchvision','torchaudio')))"], text=True)
        constraints.write_text(installed)
        command([python, "-m", "pip", "install", "-c", constraints, "-r", comfy / "requirements.txt"])
        command([python, "-m", "pip", "check"])
        inventory = subprocess.check_output([python, "-m", "pip", "freeze"], text=True)
        (location / "installed-requirements.txt").write_text(inventory)
        write_json(location / "setup.json", report)
    if args.download_models:
        if not comfy.is_dir():
            raise DirectorError("Run --install first.")
        inspections = [inspect_model(x, comfy / "models") for x in models["files"]]
        # Xet has its own cache and cannot reuse curl's .part file. Reserve the
        # full missing file sizes when changing transports.
        missing = (sum(item["size"] for item, check in zip(models["files"], inspections) if check["action"] != "reuse")
                   if args.fast_downloads else sum(x["remaining_bytes"] for x in inspections))
        if shutil.disk_usage(comfy).free < missing + 5 * 1024**3:
            raise DirectorError("Insufficient disk space for missing weights plus 5 GiB headroom.")
        for item, inspection in zip(models["files"], inspections):
            if args.fast_downloads and inspection["action"] != "reuse":
                # The Hub client is installed with ComfyUI, only on the remote
                # server. Explicit file names and a pinned revision bound scope.
                code = "from huggingface_hub import hf_hub_download; import sys; hf_hub_download(repo_id=sys.argv[1], revision=sys.argv[2], filename=sys.argv[3], local_dir=sys.argv[4], token=False)"
                environment = dict(os.environ, HF_XET_HIGH_PERFORMANCE="1", HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
                                   HF_HUB_DISABLE_TELEMETRY="1", HF_HUB_DISABLE_XET="0")
                command([python, "-c", code, models["repository"], models["revision"], item["path"], comfy / "models"], env=environment)
                if inspect_model(item, comfy / "models")["action"] != "reuse":
                    raise DirectorError("Downloaded model failed size/SHA-256 verification: " + item["path"])
                print(item["path"], "downloaded and verified with Xet", flush=True)
            else:
                print(item["path"], download_model(item, comfy / "models", inspection), flush=True)
    if args.start:
        if not python.exists():
            raise DirectorError("Run --install first.")
        current = subprocess.check_output(["git", "-C", str(comfy), "rev-parse", "HEAD"], text=True).strip()
        if current != lock["comfy_revision"]:
            raise DirectorError("ComfyUI revision differs from the lock file.")
        for item in models["files"]:
            if inspect_model(item, comfy / "models")["action"] != "reuse":
                raise DirectorError("Missing or unverified weight; run --download-models: " + item["path"])
        os.chdir(comfy)
        os.execv(str(python), [str(python), "main.py", "--listen", "127.0.0.1", "--port", "8189", "--lowvram", "--disable-auto-launch"])


if __name__ == "__main__":
    try:
        main()
    except (DirectorError, subprocess.CalledProcessError) as exc:
        print("Error: " + str(exc), file=sys.stderr)
        sys.exit(1)
