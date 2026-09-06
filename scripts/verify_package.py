"""Check the shipped files against the release manifest; no network or models."""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def verify(root=ROOT):
    root = Path(root).resolve()
    manifest = json.loads((root / "PACKAGE_MANIFEST.json").read_text())
    total = 0
    for item in manifest["files"]:
        path = root / item["path"]
        if path.is_symlink() or root not in path.resolve().parents:
            raise ValueError("Unsafe package path: " + item["path"])
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(block)
        if path.stat().st_size != item["bytes"] or digest.hexdigest() != item["sha256"]:
            raise ValueError("Shipped file changed: " + item["path"])
        total += item["bytes"]
    return {"verified_files": len(manifest["files"]), "bytes": total,
            "paid_requests": 0, "model_downloads": 0}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
