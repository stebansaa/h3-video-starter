"""Inspect a new checkout without installing software or creating GPU resources.

Default: local checks only. --check-auth adds one read-only RunPod GET /pods.
Agent permissions, creative tools, funding and a live GPU remain separate checks.
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from director.common import DirectorError
from director.credentials import value
from director.media import executable
from director.runpod import RunPod
from scripts.verify_package import verify


def binary_ready(name):
    """Execute only harmless version/help probes, with a short timeout."""
    try:
        path = executable(name) if name in ("ffmpeg", "ffprobe") else shutil.which(name)
        if not path:
            return False
        flag = "-version" if name in ("ffmpeg", "ffprobe") else "-V" if name == "ssh" else "--version"
        if name in ("scp", "ssh-keygen"):
            # These tools have no portable version flag; do not invoke a command
            # that might transfer files or generate keys just to detect them.
            return os.access(path, os.X_OK)
        return subprocess.run([path, flag], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=5).returncode == 0
    except (DirectorError, OSError, subprocess.TimeoutExpired):
        return False


def inspect(root=ROOT, check_auth=False):
    root = Path(root)
    checks = {"python_3_9_or_newer": sys.version_info >= (3, 9),
              "supported_local_os": platform.system() in ("Darwin", "Linux")}
    steps = []
    try:
        verify(root)
        checks["package_integrity"] = True
    except (OSError, ValueError, KeyError, TypeError):
        checks["package_integrity"] = False
        steps.append("Run python3 scripts/verify_package.py; restore missing/changed release files before using the baseline.")
    for name in ("ffmpeg", "ffprobe", "git", "ssh", "scp", "ssh-keygen"):
        checks[name] = binary_ready(name)
    if not checks["python_3_9_or_newer"]:
        steps.append("Use local Python 3.9 or newer; remote ComfyUI needs Python 3.12 or newer.")
    if not checks["supported_local_os"]:
        steps.append("Use macOS or Linux for these commands; on Windows use an appropriate Linux environment.")
    if not checks["ffmpeg"] or not checks["ffprobe"]:
        steps.append("Install FFmpeg/ffprobe, or run python3 scripts/install_test_media.py explicitly; it downloads media tools, not AI weights.")
    missing = [name for name in ("git", "ssh", "scp", "ssh-keygen") if not checks[name]]
    if missing:
        steps.append("For server operation, install the missing tools: " + ", ".join(missing) + ".")

    key = None
    credential = {"present": False, "status": "missing"}
    try:
        key = value("RUNPOD_API_KEY", root)
        if key:
            credential.update(present=True, status="present_not_verified")
    except (DirectorError, OSError, UnicodeError):
        credential["status"] = "file_unreadable_or_invalid"
        steps.append("Correct the private .env/key.env syntax or permissions; never print its contents.")
    requests = 0
    if check_auth and key:
        try:
            client = RunPod(key)
            client.http.timeout = 15
            client.http.retries = 0
            requests = 1
            client.list()
            credential["status"] = "verified_read_access"
        except (DirectorError, OSError, ValueError):
            # Do not include provider bodies, account objects or exception text.
            credential["status"] = "read_check_failed"
            steps.append("RunPod's read-only auth check failed. Check the key, network access and RunPod availability; no pod was created.")
    if not key:
        steps.append("Offline work needs no key. Before a new RunPod render, enter your own RUNPOD_API_KEY privately in .env and run this check with --check-auth.")
    elif not check_auth:
        steps.append("The key is present but unverified. Run python3 scripts/first_session.py --check-auth before RunPod operations.")
    if credential["status"] == "verified_read_access":
        steps.append("Read access works. Check current balance, GPU availability, rate and this session's authorized budget before a paid request; write access is not proven by a GET.")

    offline = all(checks[x] for x in ("python_3_9_or_newer", "supported_local_os", "package_integrity", "ffmpeg", "ffprobe"))
    server_tools = all(checks[x] for x in ("git", "ssh", "scp", "ssh-keygen"))
    if offline:
        steps.append("Run the offline tests, validate references and replay the example using START_HERE.md.")
    return {"version": 1, "checks": checks, "offline_ready": offline,
            "server_tools_present": server_tools, "runpod_credentials": credential,
            "mcp": {"required": False, "status": "not_probed",
                    "note": "Direct Python API path is available; the active agent must inspect its actual MCP tools if using the optional connection."},
            "agent_checks": [
                "Confirm this session can read/edit the checkout and run terminal commands.",
                "Confirm network and SSH access are permitted before remote work; these were not tested by the offline check.",
                "Confirm image inspection is available; new angles need image generation/editing tools or user-supplied images.",
                "Confirm how the user will watch/listen to previews; ASR and contact sheets alone do not prove voices or acting."
            ],
            "next_steps": steps, "ready_to_rent_gpu": False,
            "read_only_api_requests": requests, "paid_requests": 0,
            "model_downloads": 0, "software_installed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-auth", action="store_true", help="Make one read-only GET to RunPod; no resources are created")
    parser.add_argument("--require-server-tools", action="store_true", help="Also fail if git/SSH transfer tools are missing")
    parser.add_argument("--json", action="store_true", help="Machine-readable report without credentials or account details")
    args = parser.parse_args(argv)
    report = inspect(check_auth=args.check_auth)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("First-session check: " + ("local prerequisites ready" if report["offline_ready"] else "local setup needed"))
        for name, passed in report["checks"].items():
            print("  {}: {}".format(name, "OK" if passed else "NEEDS SETUP"))
        print("RunPod credentials: " + report["runpod_credentials"]["status"])
        print("MCP: optional; not probed. GPU readiness: requires further live/budget checks.")
        for step in report["next_steps"]:
            print("- " + step)
        print("Agent must also confirm:")
        for step in report["agent_checks"]:
            print("- " + step)
        print("Paid requests: 0. Model downloads: 0. Software installed: no.")
    passed = report["offline_ready"]
    if args.require_server_tools:
        passed = passed and report["server_tools_present"]
    if args.check_auth:
        passed = passed and report["runpod_credentials"]["status"] == "verified_read_access"
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
