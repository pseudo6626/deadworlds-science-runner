from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from deadworlds_compute.bundle import load_bundle
from deadworlds_compute.runner import execute
from deadworlds_compute.transport import (
    USER_AGENT,
    store_artifact_via_capability,
    submit_compute_result,
)

ROOT = Path(__file__).resolve().parents[1]


class Handler(BaseHTTPRequestHandler):
    artifact = b""
    submitted = None

    def _json(self, payload, status=200):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        assert self.headers.get("User-Agent") == USER_AGENT
        n = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(n))
        assert self.headers.get("X-Deadworlds-Capability") == "smoke-token"
        if self.path == "/submit":
            Handler.submitted = body
            assert body["transport"]["provider"] == "GOOGLE_DRIVE_RESUMABLE"
            assert body["transport"]["mime_type"] == "application/octet-stream"
            assert body["transport"]["file_name"] == "draws.npz"
            assert "_result_path" not in body
            self._json({"ok": True, "status": "COMPLETE", "compute_job_id": "smoke-job"})
            return
        sha = body["artifact_sha256"]
        size = body["byte_size"]
        self._json({
            "provider": "google_drive_resumable",
            "session_url": f"http://127.0.0.1:{self.server.server_port}/upload",
            "expected_sha256": sha,
            "expected_size": size,
            "mime_type": body["mime_type"],
        })

    def do_PUT(self):
        assert self.headers.get("User-Agent") == USER_AGENT
        n = int(self.headers.get("Content-Length", "0"))
        Handler.artifact = self.rfile.read(n)
        digest = hashlib.sha256(Handler.artifact).hexdigest()
        md5 = hashlib.md5(Handler.artifact).hexdigest()
        self._json({
            "id": "drive-smoke-file",
            "name": "draws.npz",
            "mimeType": "application/octet-stream",
            "size": str(n),
            "sha256Checksum": digest,
            "md5Checksum": md5,
            "webViewLink": "https://drive.google.com/file/d/drive-smoke-file/view",
        })

    def log_message(self, *args):
        return


def test_transport_round_trip(tmp_path):
    Handler.artifact = b""
    Handler.submitted = None
    package = json.loads((ROOT / "examples" / "worker_issued_smoke_job.json").read_text())
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        bundle_path = tmp_path / "bundle.json"
        bundle_path.write_text(json.dumps({
            "package": package,
            "transport": {
                "provider": "google_drive_resumable",
                "lease_request_url": f"http://127.0.0.1:{server.server_port}/lease",
                "lease_token": "smoke-token",
            },
            "submission": {
                "url": f"http://127.0.0.1:{server.server_port}/submit",
                "token": "smoke-token",
            },
        }))
        bundle = load_bundle(bundle_path)
        artifact = tmp_path / "artifact.bin"
        artifact.write_bytes(b"deadworlds-compute-transport-smoke")
        receipt = store_artifact_via_capability(bundle.transport, bundle.job, artifact)
        assert receipt.file_id == "drive-smoke-file"
        assert receipt.sha256 == hashlib.sha256(artifact.read_bytes()).hexdigest()
        assert receipt.md5 == hashlib.md5(artifact.read_bytes()).hexdigest()
        assert Handler.artifact == artifact.read_bytes()

        result = execute(bundle.job, tmp_path / "run", transport=bundle.transport)
        submitted = submit_compute_result(bundle.submission, result)
        assert submitted["status"] == "COMPLETE"
        assert Handler.submitted["artifact_ref"] == "gdrive://drive-smoke-file"
        assert Handler.submitted["transport"]["sha256_checksum"] == Handler.submitted["artifact_sha256"]
        assert Handler.submitted["transport"]["mime_type"] == "application/octet-stream"
        assert Handler.submitted["transport"]["file_name"] == "draws.npz"
    finally:
        server.shutdown()
        thread.join(timeout=2)
