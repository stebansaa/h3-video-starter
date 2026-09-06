import argparse
import json
import os
import sys
from pathlib import Path

from .common import DirectorError, ROOT, read_json, write_json
from .comfy import Comfy
from .plan import FPS, frame_count, load_plan, select_shots
from .workflow import PROFILES, build, preflight


def parser():
    p = argparse.ArgumentParser(description="Prepare and operate native H3 clips on a ComfyUI server.")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("plan", "export", "preflight", "render"):
        c = sub.add_parser(name)
        c.add_argument("--plan", default=str(ROOT / "plans/episode.json"))
        c.add_argument("--shot", help="Select one shot; omitted means all shots")
        c.add_argument("--profile", choices=PROFILES, default="preview")
        c.add_argument("--seed", type=int, default=1001)
        if name == "export":
            c.add_argument("--out", default="runs/prepared")
        if name in ("preflight", "render"):
            c.add_argument("--url", default=os.environ.get("COMFY_URL", "http://127.0.0.1:8188"))
        if name == "preflight":
            c.add_argument("--references", help="Preflight the actual character-reference workflow")
        if name == "render":
            c.add_argument("--run", required=True, help="Persistent local run directory; reuse to resume")
            c.add_argument("--first-frame", help="Optional local image for the first selected shot")
            c.add_argument("--references", help="Version 1 single-shot or version 2 sequence reference manifest")
            c.add_argument("--timeout", type=float, default=1800)
            c.add_argument("--through", help="Stop after this shot for review; resume the same run later")
    c = sub.add_parser("review")
    c.add_argument("--run", required=True)
    c.add_argument("--shot", required=True)
    c.add_argument("--decision", choices=("accepted", "rejected"), required=True)
    c.add_argument("--note", required=True)
    c.add_argument("--cuts", help="Bind acceptance to this shot's required frame edits")
    c = sub.add_parser("assemble")
    c.add_argument("--run", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--allow-unreviewed", action="store_true", help="Assemble a draft before creative review")
    c = sub.add_parser("doctor")
    c.add_argument("--url", help="Optional read-only live server check")
    c = sub.add_parser("pod-config")
    c.add_argument("--public-key", required=True)
    c.add_argument("--network-volume-id")
    c.add_argument("--data-center-id")
    c.add_argument("--gpu-id", default="NVIDIA GeForce RTX 5090")
    c.add_argument("--temporary", action="store_true", help="200 GB disposable container disk; no persistent mount")
    c.add_argument("--out", default="runs/pod-request.json")
    c = sub.add_parser("pod-create")
    c.add_argument("--config", required=True)
    c.add_argument("--state", default="runs/pod-state.json")
    c.add_argument("--execute", action="store_true", help="Actually rent a GPU; otherwise show request only")
    sub.add_parser("pod-list")
    for name in ("pod-get", "pod-check", "pod-stop"):
        c = sub.add_parser(name)
        c.add_argument("pod_id")
        if name == "pod-check":
            c.add_argument("--gpu-id", default="NVIDIA GeForce RTX 5090")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    result = None
    if args.command in ("plan", "export", "preflight", "render"):
        plan = load_plan(args.plan)
        shots = select_shots(plan, args.shot)
        if args.command == "plan":
            result = {"title": plan["title"], "shots": [{"id": s["id"], "seconds": round(frame_count(s["seconds"]) / FPS, 3), "turns": len(s["dialogue"])} for s in shots],
                      "total_seconds": round(sum(frame_count(s["seconds"]) / FPS for s in shots), 3), "profile": args.profile}
        elif args.command == "export":
            for i, shot in enumerate(shots):
                first = "UPLOAD_PREVIOUS_LAST_FRAME.png" if i and shot["continuity"] == "previous" else None
                graph = build(plan, shot, (args.seed + i) % 2**64, "prepared_" + shot["id"], args.profile, first)
                write_json(Path(args.out) / (shot["id"] + ".api.json"), graph)
            result = {"exported": len(shots), "directory": args.out, "note": "Continuations contain a placeholder image name; render uploads the actual previous frame."}
        else:
            client = Comfy(args.url, os.environ.get("COMFY_API_KEY"))
            if args.command == "preflight":
                info = client.info()
                if args.references:
                    from .references import load, load_sequence
                    raw = read_json(args.references)
                    if raw.get("version") == 2:
                        assets = load_sequence(args.references, plan["shots"])["shots"]
                    else:
                        if len(shots) != 1:
                            raise DirectorError("Select one shot for a version 1 reference manifest.")
                        assets = {shots[0]["id"]: load(args.references, shots[0])}
                    result = []
                    for shot in shots:
                        refs = [{"character": c["character"], "video": "placeholder.mp4"} for c in assets[shot["id"]]["clips"]]
                        result.append(preflight(build(plan, shot, args.seed, "preflight", args.profile,
                                                      "placeholder.png", refs), info, check_files=False))
                else:
                    result = [preflight(build(plan, s, args.seed, "preflight", args.profile), info) for s in shots]
                    preflight(build(plan, shots[0], args.seed, "preflight", args.profile, "placeholder.png"), info, check_files=False)
            else:
                from .pipeline import render
                result = render(plan, client, args.run, args.profile, args.seed, args.shot, args.first_frame,
                                args.timeout, references=args.references, through=args.through)
    elif args.command == "review":
        from .pipeline import review
        required_edit = read_json(args.cuts)["shots"][args.shot] if args.cuts else None
        review(args.run, args.shot, args.decision, args.note, required_edit)
        result = {"shot": args.shot, "review": args.decision}
    elif args.command == "assemble":
        from .pipeline import assemble_run
        result = assemble_run(args.run, args.out, args.allow_unreviewed)
    elif args.command == "doctor":
        from .media import executable, run
        result = {"python": sys.version.split()[0], "weights_downloaded_by_doctor": False}
        for tool in ("ffmpeg", "ffprobe"):
            try:
                result[tool] = run([executable(tool), "-version"]).stdout.splitlines()[0]
            except DirectorError as exc:
                result[tool] = str(exc)
        if args.url:
            client = Comfy(args.url, os.environ.get("COMFY_API_KEY"))
            plan = load_plan(ROOT / "plans/episode.json")
            result["server"] = preflight(build(plan, plan["shots"][0], 1, "doctor"), client.info())
    elif args.command.startswith("pod-"):
        from .runpod import RunPod, pod_config, public_pod, check_pod
        if args.command == "pod-config":
            payload = pod_config(Path(args.public_key).read_text(), args.network_volume_id, args.data_center_id,
                                 args.gpu_id, args.temporary)
            write_json(args.out, payload)
            result = {"request_file": args.out, "created": False}
        elif args.command == "pod-create" and not args.execute:
            result = {"request": read_json(args.config), "created": False, "note": "--execute creates a billable GPU Pod."}
        else:
            from .credentials import value
            rp = RunPod(value("RUNPOD_API_KEY"))
            if args.command == "pod-create":
                result = rp.create(read_json(args.config), args.state)
            elif args.command == "pod-list":
                result = [public_pod(p) for p in rp.list()]
            elif args.command == "pod-get":
                result = public_pod(rp.get(args.pod_id))
            elif args.command == "pod-check":
                result = check_pod(rp.get(args.pod_id), args.gpu_id)
            else:
                rp.stop(args.pod_id)
                result = {"stop_requested": args.pod_id, "note": "Confirm status EXITED with pod-get; storage may remain billable."}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (DirectorError, OSError, KeyError, ValueError) as exc:
        print("Error: " + str(exc), file=sys.stderr)
        sys.exit(1)
