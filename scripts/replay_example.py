"""Rebuild the recorded example offline from its actual reviewed source clips."""
import argparse
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from director import media
from director.common import DirectorError


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(ROOT / "output/replayed-example.mp4"))
    args = p.parse_args()
    example = ROOT / "examples/bitcoin-contest"
    subprocess.run([sys.executable, str(ROOT / "scripts/assemble_episode.py"),
                    "--run", str(example / "run"), "--cuts", str(example / "cuts.json"),
                    "--mix", str(ROOT / "plans/episode-mix.json"),
                    "--transcripts", str(example / "transcripts"), "--out", args.out], check=True)
    info = media.probe(args.out)
    if abs(info["duration"] - 2333 / 24) > 0.001:
        raise DirectorError("Replay duration does not match the recorded edit.")
    print("Offline replay complete: " + str(Path(args.out).resolve()))
    print("Uses recorded footage; no new AI generation, credentials or model downloads.")


if __name__ == "__main__":
    main()
