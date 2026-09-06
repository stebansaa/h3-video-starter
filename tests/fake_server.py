"""Local protocol simulator, not a model or proof of GPU compatibility."""
import copy
import json
import socket
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from director.common import ROOT, read_json
from director.workflow import preflight


class FakeServer:
    def __init__(self, video=b"fake video"):
        self.video = video
        self.jobs = {}
        self.posts = []
        self.uploads = []
        self.info = read_json(ROOT / "tests/fixtures/object_info.json")
        self.reject = False
        self.drop_response = False
        self.fail_job = False
        self.pending = False
        self.download_truncated = False
        self.unauthorized = False
        self.history_polls = 0
        self.history_status = 200
        self.transient_gets = 0
        self.malformed_response = False
        self.accepted_warnings = False
        self.redirect = None
        self.pods = []
        self.required_user_agent = None
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send_json(self, value, status=200):
                body = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = urllib.parse.urlsplit(self.path).path
                if outer.required_user_agent and self.headers.get('User-Agent') != outer.required_user_agent:
                    return self.send_json({'detail': 'request identifier required'}, 403)
                if outer.unauthorized:
                    return self.send_json({"secret": "sensitive-server-content"}, 401)
                if path == "/object_info":
                    if outer.redirect:
                        self.send_response(302)
                        self.send_header("Location", outer.redirect)
                        self.end_headers()
                        return
                    if outer.transient_gets:
                        outer.transient_gets -= 1
                        return self.send_json({}, 503)
                    return self.send_json(outer.info)
                if path == "/queue":
                    return self.send_json({"queue_running": [j["prompt"] for j in outer.jobs.values()] if outer.pending else [], "queue_pending": []})
                if path == "/history":
                    return self.send_json({} if outer.pending else outer.jobs)
                if path.startswith("/history/"):
                    outer.history_polls += 1
                    if outer.history_status != 200:
                        return self.send_json({}, outer.history_status)
                    pid = path.split("/")[-1]
                    return self.send_json({pid: outer.jobs[pid]} if pid in outer.jobs and not outer.pending else {})
                if path == "/view":
                    query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    if query.get("type") != ["output"]:
                        return self.send_json({}, 400)
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(outer.video) + (10 if outer.download_truncated else 0)))
                    self.end_headers()
                    self.wfile.write(outer.video)
                    return
                if path == "/v2/pods":
                    return self.send_json({"pods": outer.pods})
                if path.startswith("/v2/pods/"):
                    return self.send_json(outer.pods[0])
                return self.send_json({}, 404)

            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                outer.posts.append((self.path, raw))
                if self.path == "/upload/image":
                    # Confirm the real client sends a multipart file with a digest name.
                    import re
                    name = re.search(rb'filename="([^"]+)"', raw).group(1).decode()
                    outer.uploads.append(raw)
                    if name.endswith(".mp4"):
                        outer.info["LoadVideo"]["input"]["required"]["file"][0].append(name)
                    else:
                        outer.info["LoadImage"]["input"]["required"]["image"][0].append(name)
                    return self.send_json({"name": name, "subfolder": "", "type": "input"})
                body = json.loads(raw) if raw else {}
                if self.path == "/prompt":
                    if outer.reject:
                        return self.send_json({"error": "invalid", "node_errors": {"5": "bad"}}, 400)
                    try:
                        preflight(body["prompt"], outer.info)
                    except Exception:
                        return self.send_json({"error": "schema mismatch"}, 400)
                    pid = "job-" + str(len(outer.jobs) + 1)
                    outer.jobs[pid] = {"prompt": [1, pid, body["prompt"], body["extra_data"], ["14"]],
                        "status": {"completed": True, "status_str": "error" if outer.fail_job else "success",
                                   "messages": [["execution_error", {"node_type": "SamplerCustomAdvanced", "exception_type": "OutOfMemoryError"}]] if outer.fail_job else []},
                        "outputs": {"14": {"images": [{"filename": "clip.mp4", "subfolder": "director", "type": "output"}]}}}
                    if outer.drop_response:
                        self.connection.shutdown(socket.SHUT_RDWR)
                        self.connection.close()
                        return
                    if outer.malformed_response:
                        return self.send_json({"unexpected": "response without job ID"})
                    return self.send_json({"prompt_id": pid, "number": 1,
                                           "node_errors": {"unused": {"errors": []}} if outer.accepted_warnings else {}})
                if self.path == "/v2/pods":
                    if "imageName" in body or "gpu" not in body:
                        return self.send_json({"title": "Invalid v2 request"}, 422)
                    pod = dict(body, id="pod-test", status="RUNNING", cost=0.99,
                               ssh={"direct": {"host": "203.0.113.1", "port": 2222, "username": "root"}},
                               env={"SECRET": "not-for-logs"})
                    outer.pods.append(pod)
                    if outer.drop_response:
                        self.connection.shutdown(socket.SHUT_RDWR)
                        self.connection.close()
                        return
                    return self.send_json(pod, 201)
                if self.path == "/v2/pods/pod-test/action" and body == {"action": "stop"}:
                    outer.pods[0]["status"] = "EXITED"
                    return self.send_json(outer.pods[0])
                return self.send_json({}, 404)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:" + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
