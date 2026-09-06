"""Optional: install FFmpeg/ffprobe into this project's .venv for offline tests.

Downloads small media executables, never AI models. No runtime auto-downloads.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    python = ROOT / ".venv/bin/python"
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")], check=True)
    subprocess.run([str(python), "-m", "pip", "install", "static-ffmpeg==3.0"], check=True)
    subprocess.run([str(python), "-c", "import static_ffmpeg.run; print(static_ffmpeg.run.get_or_fetch_platform_executables_else_raise())"], check=True)

