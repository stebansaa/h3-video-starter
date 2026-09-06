import http.client
import json
import math
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from .common import DirectorError


class APIError(DirectorError):
    def __init__(self, message, ambiguous=False):
        super().__init__(message)
        self.ambiguous = ambiguous


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward credentials or repeat paid POSTs through redirects.
        return None


class HTTP:
    def __init__(self, base, token=None, timeout=30, retries=3):
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise DirectorError("HTTP timeout must be finite positive seconds.")
        if type(retries) is not int or retries < 0:
            raise DirectorError("HTTP retry count must be a nonnegative integer.")
        url = urllib.parse.urlsplit(base)
        if url.scheme not in ("https", "http") or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise DirectorError("Use an HTTP(S) base URL without credentials, query or fragment.")
        if url.scheme == "http" and url.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise DirectorError("Use HTTPS for remote services, or an SSH tunnel to localhost.")
        self.base, self.token, self.timeout, self.retries = base.rstrip("/"), token, timeout, retries
        self.opener = urllib.request.build_opener(NoRedirect)

    def request(self, method, path, data=None, content_type="application/json", destination=None, deadline=None):
        headers = {"Accept": "application/json", "User-Agent": "seinfield-director/1.0"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if data is not None:
            headers["Content-Type"] = content_type
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        attempts = self.retries + 1 if method == "GET" else 1
        for attempt in range(attempts):
            remaining = deadline - time.monotonic() if deadline is not None else self.timeout
            if remaining <= 0:
                raise APIError("Request deadline exceeded.")
            try:
                req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
                with self.opener.open(req, timeout=min(self.timeout, remaining)) as response:
                    if destination is not None:
                        count = 0
                        with open(destination, "wb") as f:
                            for block in iter(lambda: response.read(1024 * 1024), b""):
                                f.write(block)
                                count += len(block)
                        expected = response.headers.get("Content-Length")
                        if not count or (expected is not None and count != int(expected)):
                            raise APIError("Incomplete output download.")
                        return count
                    raw = response.read()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                code = exc.code
                exc.close()
                retryable = code in (408, 429, 500, 502, 503, 504)
                if method == "GET" and retryable and attempt + 1 < attempts:
                    self._backoff(attempt, deadline)
                    continue
                # Do not echo response bodies, which can contain secrets/workflows.
                raise APIError("{} {} returned HTTP {}".format(method, path.split("?")[0], code),
                               ambiguous=method != "GET" and (code >= 500 or code == 408)) from None
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError, http.client.HTTPException):
                if method == "GET" and attempt + 1 < attempts:
                    self._backoff(attempt, deadline)
                    continue
                raise APIError("Network failure during {} {}; inspect server/job state before retrying a submission.".format(method, path.split("?")[0]),
                               ambiguous=method != "GET") from None
            except (ValueError, json.JSONDecodeError):
                raise APIError("Invalid JSON or download metadata from service.", ambiguous=method != "GET") from None

    @staticmethod
    def _backoff(attempt, deadline):
        delay = min(2 ** attempt, 8)
        if deadline is not None:
            delay = min(delay, max(0, deadline - time.monotonic()))
        time.sleep(delay)
