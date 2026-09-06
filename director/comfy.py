import os
import math
import time
import urllib.parse
import uuid
from pathlib import Path

from .common import DirectorError, file_digest
from .http import APIError, HTTP


class Comfy:
    def __init__(self, url, token=None, timeout=30):
        self.http = HTTP(url, token, timeout)

    def info(self):
        return self.http.request("GET", "/object_info")

    def submit(self, graph, request_id):
        result = self.http.request("POST", "/prompt", {
            "prompt": graph, "client_id": request_id,
            "extra_data": {"director_request_id": request_id},
        })
        # ComfyUI can accept valid output branches while reporting node_errors
        # for other branches. A returned prompt_id must never be discarded.
        if isinstance(result, dict) and isinstance(result.get("prompt_id"), str) and result["prompt_id"]:
            return result["prompt_id"]
        if isinstance(result, dict) and result.get("error"):
            raise DirectorError("ComfyUI rejected the workflow; run preflight against this server.")
        raise APIError("ComfyUI omitted a valid prompt_id; submission state is unknown.", ambiguous=True)

    def recover(self, request_id):
        """Find an accepted submission after a lost HTTP response or local crash."""
        queue = self.http.request("GET", "/queue")
        history = self.http.request("GET", "/history")
        entries = list(queue.get("queue_running", [])) + list(queue.get("queue_pending", []))
        entries += [v.get("prompt", []) for v in history.values()]
        matches = set()
        for e in entries:
            if len(e) > 3 and isinstance(e[3], dict) and e[3].get("director_request_id") == request_id:
                matches.add(e[1])
        if len(matches) > 1:
            raise DirectorError("Multiple jobs match this request; reconcile manually.")
        return next(iter(matches), None)

    def wait(self, prompt_id, timeout=1800, interval=5):
        if any(not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0 for x in (timeout, interval)):
            raise DirectorError("Polling timeout and interval must be finite positive seconds.")
        end = time.monotonic() + timeout
        while True:
            try:
                result = self.http.request("GET", "/history/" + urllib.parse.quote(prompt_id, safe=""), deadline=end)
            except APIError:
                if time.monotonic() >= end:
                    break
                raise
            if not isinstance(result, dict):
                raise DirectorError("Malformed ComfyUI history response; job state is retained for recovery.")
            entry = result.get(prompt_id)
            if entry:
                status = entry.get("status", {})
                messages = status.get("messages", [])
                if status.get("status_str") == "error" or any(m[0] in ("execution_error", "execution_interrupted") for m in messages):
                    details = next((m[1] for m in messages if m[0] == "execution_error"), {})
                    raise DirectorError("Generation failed at {} ({})".format(details.get("node_type", "unknown node"), details.get("exception_type", "interrupted/error")))
                if status.get("completed"):
                    return entry
            remaining = end - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(interval, remaining))
        raise DirectorError("Timed out waiting for job " + prompt_id + ". Job may still be running; resume this run to reconnect.")

    def upload(self, path):
        return self._upload(path, (".png", ".jpg", ".jpeg", ".webp"), 50)

    def upload_video(self, path):
        # ComfyUI's upload/image multipart route also accepts files used by
        # native LoadVideo. Media is normalized and checked before this call.
        return self._upload(path, (".mp4",), 100)

    def _upload(self, path, extensions, max_mb):
        path = Path(path)
        if not path.is_file() or path.suffix.lower() not in extensions:
            raise DirectorError("Reference must be a local file of type: " + ", ".join(extensions))
        if path.stat().st_size > max_mb * 1024 * 1024:
            raise DirectorError("Reference exceeds {} MB.".format(max_mb))
        name = "director_" + file_digest(path)[:24] + path.suffix.lower()
        boundary = "director-" + uuid.uuid4().hex
        body = ('--{}\r\nContent-Disposition: form-data; name="image"; filename="{}"\r\nContent-Type: application/octet-stream\r\n\r\n'.format(boundary, name)).encode()
        body += path.read_bytes() + ('\r\n--{}\r\nContent-Disposition: form-data; name="type"\r\n\r\ninput\r\n--{}--\r\n'.format(boundary, boundary)).encode()
        result = self.http.request("POST", "/upload/image", body, "multipart/form-data; boundary=" + boundary)
        if not result.get("name"):
            raise DirectorError("Upload response has no image name.")
        return "/".join(v for v in (result.get("subfolder", ""), result["name"]) if v)

    def download(self, entry, destination):
        # Native SaveVideo may serialize its preview as `images`; VHS uses `gifs`.
        candidates = []
        for output in entry.get("outputs", {}).values():
            for key in ("images", "videos", "gifs"):
                for item in output.get(key, []):
                    if Path(item.get("filename", "")).suffix.lower() in (".mp4", ".webm", ".mkv", ".mov") and item.get("type") == "output":
                        if item not in candidates:
                            candidates.append(item)
        if len(candidates) != 1:
            raise DirectorError("Expected one saved video; found {}.".format(len(candidates)))
        item = candidates[0]
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_suffix(destination.suffix + ".part")
        try:
            query = urllib.parse.urlencode({k: item.get(k, "") for k in ("filename", "subfolder", "type")})
            self.http.request("GET", "/view?" + query, destination=temp)
            os.replace(temp, destination)
        finally:
            if temp.exists():
                temp.unlink()
        return item
