"""Optional dialogue QC. All ASR weights stay on the remote Linux GPU server."""
import argparse
import json
import platform
import time
import hashlib
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("inputs", nargs="+")
    p.add_argument("--out", default="/workspace/episode-transcripts")
    p.add_argument("--model", default="small.en")
    p.add_argument("--clip-timestamps", help="Optional unprompted segment pass, e.g. 7,10.125")
    args = p.parse_args()
    if platform.system() != "Linux" or not Path("/dev/nvidiactl").exists():
        raise SystemExit("ASR runs only on the remote Linux NVIDIA server; no local model downloads.")
    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=4,
                         download_root="/workspace/episode-asr-models")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for value in args.inputs:
        source = Path(value)
        sources = sorted(p for p in source.iterdir() if p.suffix.lower() in (".mp4", ".mov", ".wav")) if source.is_dir() else [source]
        for path in sources:
            destination = out / (path.stem + ".json")
            digest = hashlib.sha256()
            with path.open("rb") as f:
                for block in iter(lambda: f.read(1024 * 1024), b""):
                    digest.update(block)
            signature = {"source_sha256": digest.hexdigest(), "model": args.model,
                         "clip_timestamps": args.clip_timestamps}
            if destination.exists():
                existing = json.loads(destination.read_text())
                if all(existing.get(k) == v for k, v in signature.items()):
                    continue
            start = time.time()
            options = {"clip_timestamps": args.clip_timestamps} if args.clip_timestamps else {}
            segments, info = model.transcribe(str(path), language="en", beam_size=5,
                word_timestamps=True, condition_on_previous_text=False, vad_filter=False, **options)
            records = []
            for s in segments:
                records.append({"start": s.start, "end": s.end, "text": s.text,
                    "no_speech_prob": s.no_speech_prob, "avg_logprob": s.avg_logprob,
                    "words": [{"start": w.start, "end": w.end, "word": w.word,
                               "probability": w.probability} for w in (s.words or [])]})
            data = {"source": str(path), "model": args.model, "language": info.language,
                    "segments": records, "elapsed": time.time() - start,
                    "text": " ".join(s["text"].strip() for s in records),
                    "note": "Automatic transcription, not proof of speaker identity or exact delivery."}
            data.update(signature)
            temp = destination.with_suffix(".tmp")
            temp.write_text(json.dumps(data, indent=2))
            temp.replace(destination)
            print(json.dumps({"file": path.name, "text": data["text"]}), flush=True)


if __name__ == "__main__":
    main()
