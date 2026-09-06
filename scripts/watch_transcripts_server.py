"""Watch completed ComfyUI outputs on the remote server and transcribe them."""
import platform
import subprocess
import sys
import time
from pathlib import Path

if platform.system() != "Linux" or not Path("/dev/nvidiactl").exists():
    raise SystemExit("Remote Linux NVIDIA server only.")

source = Path("/workspace/seinfield-runtime/ComfyUI/output/director")
out = Path("/workspace/episode-transcripts")
deadline = time.time() + 5 * 3600
while time.time() < deadline:
    # Skip a file still being written. Completed H3 clips are small, and this
    # check adds five seconds before attempting to read the MP4 index.
    pending = [p for p in source.glob("*.mp4") if time.time() - p.stat().st_mtime > 5
               and not (out / (p.stem + ".json")).exists()]
    if pending:
        subprocess.run([sys.executable, str(Path(__file__).with_name("transcribe_server.py")),
                        *map(str, pending), "--out", str(out)], timeout=600)
    time.sleep(20)
