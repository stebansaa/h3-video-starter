"""Fallback stop watchdog. It never creates or deletes a pod."""
import argparse
import json
import os
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from director.common import DirectorError, write_json
from director.credentials import value
from director.runpod import RunPod


def main():
    p = argparse.ArgumentParser()
    p.add_argument("pod_id")
    p.add_argument("--deadline", type=float, required=True, help="Absolute Unix timestamp, includes setup time")
    p.add_argument("--state", required=True, help="New local watchdog status file")
    args = p.parse_args()
    if not time.time() < args.deadline <= time.time() + 12 * 3600:
        raise DirectorError("Deadline must be in the next twelve hours.")
    client = RunPod(value("RUNPOD_API_KEY"))
    path = Path(args.state)
    path.parent.mkdir(parents=True, exist_ok=True)
    status = {"pod_id": args.pod_id, "deadline": args.deadline, "watchdog_pid": os.getpid(), "status": "watching"}
    with path.open("x") as f:
        json.dump(status, f)
    while True:
        try:
            pod = client.get(args.pod_id)
            if pod.get("status") == "EXITED":
                status["status"] = "stopped_confirmed"
                write_json(path, status)
                return
            if time.time() >= args.deadline:
                client.stop(args.pod_id)
                status["status"] = "stop_requested"
                write_json(path, status)
        except DirectorError as exc:
            if str(exc).endswith("HTTP 404"):
                status["status"] = "pod_absent"
                write_json(path, status)
                return
            status.update(status="retrying_control_plane", last_error=str(exc))
            write_json(path, status)
        time.sleep(15)


if __name__ == "__main__":
    main()
