"""Create an upload archive containing code/config only. No models or secrets."""
import argparse
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from director.common import DirectorError


def bundle(output):
    output = Path(output)
    if output.exists():
        raise DirectorError("Archive already exists: " + str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    files = [ROOT / "AGENTS.md", ROOT / "README.md", ROOT / "START_HERE.md", ROOT / "script.txt"]
    for folder in ("director", "scripts", "config", "plans", "docs", ".agents/skills/h3-video"):
        files += [p for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".json", ".md", ".sh", ".yaml") and "__pycache__" not in p.parts]
    with tarfile.open(output, "w:gz") as archive:
        for path in sorted(files):
            if path.is_symlink():
                raise DirectorError("Bundle refuses symlinks: " + str(path))
            archive.add(path, arcname="seinfield/" + str(path.relative_to(ROOT)), recursive=False)
    return output


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="runs/seinfield-server.tar.gz")
    args = p.parse_args()
    print(bundle(args.out))
