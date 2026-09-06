"""Read project credentials as data; never source a shell file or echo values."""
import os
from pathlib import Path
from .common import ROOT, DirectorError


def value(name, root=ROOT):
    configured = os.environ.get(name)
    if configured:
        return configured
    for filename in (".env", "key.env"):
        path = Path(root) / filename
        if not path.is_file():
            continue
        found = {}
        for number, raw in enumerate(path.read_text().splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                if filename == "key.env" and not found:
                    key, item = "RUNPOD_API_KEY", line
                else:
                    raise DirectorError("Invalid credential file syntax at line " + str(number))
            else:
                key, item = (part.strip() for part in line.split("=", 1))
            if item.startswith(("'", '"')):
                if len(item) < 2 or item[-1] != item[0]:
                    raise DirectorError("Unclosed credential quote at line " + str(number))
                item = item[1:-1]
            else:
                item = item.split("#", 1)[0].strip()
            if key in found:
                raise DirectorError("Duplicate setting in credential file at line " + str(number))
            found[key] = item
        if found.get(name):
            return found[name]
    return None
