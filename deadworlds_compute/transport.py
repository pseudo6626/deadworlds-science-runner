from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import ComputeJob, sha256_file

TRANSPORT_VERSION = "deadworlds-compute-transport-v0.2.0"
USER_AGENT = "deadworlds-science-runner/0.9.0"


@dataclass(frozen=True)
class TransportCapability:
    provider: str
    lease_request_url: str
    lease_token: str


@dataclass(frozen=True)
class SubmissionCapability:
    url: str
    token: str


@dataclass(frozen=True)
class DriveUploadReceipt:
    file_id: str
    name: str
    mime_type: str
    size: int
    sha256: str
    md5: str | None = None
    web_view_link: str | None = None

    @property
    def artifact_ref(self) -> str:
        return f"gdrive://{self.file_id}"


def _request_json(req: urllib.request.Request, *, timeout: int = 60) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code} from {req.full_url}: {detail[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error calling {req.full_url}: {exc.reason}") from exc
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Expected JSON from {req.full_url}, got {body[:200]!r}") from exc


def request_drive_upload_lease(
    capability: TransportCapability,
    job: ComputeJob,
    artifact_path: Path,
    *,
    artifact_sha256: str | None = None,
    mime_type: str | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    if capability.provider != "google_drive_resumable":
        raise ValueError(f"Unsupported transport provider: {capability.provider}")
    path = artifact_path.resolve()
    digest = artifact_sha256 or sha256_file(path)
    mime = mime_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    payload = {
        "transport_version": TRANSPORT_VERSION,
        "analysis_id": job.analysis_id,
        "comparison_group_id": job.group_id,
        "candidate_model_id": job.model_id,
        "job_manifest_sha256": job.expected_hashes["job_manifest_sha256"],
        "artifact_sha256": digest,
        "byte_size": path.stat().st_size,
        "filename": path.name,
        "mime_type": mime,
    }
    req = urllib.request.Request(
        capability.lease_request_url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers={
            "X-Deadworlds-Capability": capability.lease_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    lease = _request_json(req, timeout=timeout)
    required = ["provider", "session_url", "expected_sha256", "expected_size", "mime_type"]
    missing = [k for k in required if k not in lease]
    if missing:
        raise RuntimeError(f"Upload lease missing fields: {missing}")
    if lease["provider"] != "google_drive_resumable":
        raise RuntimeError("Upload lease provider mismatch")
    if str(lease["expected_sha256"]).lower() != digest.lower():
        raise RuntimeError("Upload lease SHA-256 binding mismatch")
    if int(lease["expected_size"]) != path.stat().st_size:
        raise RuntimeError("Upload lease byte-size binding mismatch")
    return lease


def _drive_put(
    session_url: str,
    data: bytes,
    *,
    content_type: str,
    content_range: str,
    timeout: int,
) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(
        session_url,
        data=data,
        method="PUT",
        headers={
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
            "Content-Range": content_range,
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read()
        # 308 Resume Incomplete is a normal resumable-upload response.
        if exc.code == 308:
            return 308, {k.lower(): v for k, v in exc.headers.items()}, body
        detail = body.decode("utf-8", "replace")
        raise RuntimeError(f"Drive upload HTTP {exc.code}: {detail[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Drive upload network error: {exc.reason}") from exc


def _drive_query_offset(session_url: str, total_size: int, *, timeout: int) -> tuple[int, dict[str, Any] | None]:
    status, headers, body = _drive_put(
        session_url,
        b"",
        content_type="application/octet-stream",
        content_range=f"bytes */{total_size}",
        timeout=timeout,
    )
    if status in (200, 201):
        return total_size, json.loads(body) if body else {}
    if status != 308:
        raise RuntimeError(f"Unexpected Drive resumable status response: {status}")
    range_header = headers.get("range")
    if not range_header:
        return 0, None
    # Google returns Range: bytes=0-N.
    try:
        last = int(range_header.split("-", 1)[1])
    except (IndexError, ValueError) as exc:
        raise RuntimeError(f"Invalid Drive resumable Range header: {range_header!r}") from exc
    return last + 1, None


def upload_drive_resumable(
    session_url: str,
    artifact_path: Path,
    *,
    expected_sha256: str,
    expected_size: int,
    mime_type: str = "application/octet-stream",
    timeout: int = 300,
    chunk_size: int = 8 * 1024 * 1024,
    max_resume_attempts: int = 4,
) -> DriveUploadReceipt:
    path = artifact_path.resolve()
    actual_size = path.stat().st_size
    if actual_size != int(expected_size):
        raise RuntimeError(f"Artifact size changed before upload: {actual_size} != {expected_size}")
    actual_hash = sha256_file(path)
    if actual_hash.lower() != expected_sha256.lower():
        raise RuntimeError("Artifact SHA-256 changed before upload")
    if actual_size <= 0:
        raise RuntimeError("Refusing to upload an empty scientific artifact")
    if chunk_size < 256 * 1024 or chunk_size % (256 * 1024):
        raise ValueError("chunk_size must be a positive multiple of 256 KiB")

    offset = 0
    final_meta: dict[str, Any] | None = None
    resume_attempts = 0
    with path.open("rb") as fh:
        while offset < actual_size:
            fh.seek(offset)
            data = fh.read(min(chunk_size, actual_size - offset))
            if not data:
                raise RuntimeError("Unexpected EOF while reading scientific artifact")
            end = offset + len(data) - 1
            try:
                status, headers, body = _drive_put(
                    session_url,
                    data,
                    content_type=mime_type,
                    content_range=f"bytes {offset}-{end}/{actual_size}",
                    timeout=timeout,
                )
            except RuntimeError:
                if resume_attempts >= max_resume_attempts:
                    raise
                resume_attempts += 1
                offset, completed = _drive_query_offset(session_url, actual_size, timeout=timeout)
                if completed is not None:
                    final_meta = completed
                    break
                continue

            if status == 308:
                range_header = headers.get("range")
                if range_header:
                    try:
                        offset = int(range_header.split("-", 1)[1]) + 1
                    except (IndexError, ValueError) as exc:
                        raise RuntimeError(f"Invalid Drive resumable Range header: {range_header!r}") from exc
                else:
                    offset = end + 1
                resume_attempts = 0
                continue
            if status in (200, 201):
                final_meta = json.loads(body) if body else {}
                offset = actual_size
                break
            raise RuntimeError(f"Unexpected Drive upload response: {status}")

    if final_meta is None:
        offset, completed = _drive_query_offset(session_url, actual_size, timeout=timeout)
        if offset != actual_size or completed is None:
            raise RuntimeError("Drive upload did not reach a completed state")
        final_meta = completed

    meta = final_meta
    file_id = str(meta.get("id") or "").strip()
    drive_hash = str(meta.get("sha256Checksum") or "").strip().lower()
    drive_md5 = str(meta.get("md5Checksum") or "").strip().lower() or None
    size = int(meta.get("size") or 0)
    if not file_id:
        raise RuntimeError("Drive upload response did not include file id")
    if drive_hash != actual_hash.lower():
        raise RuntimeError(f"Drive SHA-256 mismatch: {drive_hash or '<missing>'} != {actual_hash}")
    if size != actual_size:
        raise RuntimeError(f"Drive size mismatch: {size} != {actual_size}")
    return DriveUploadReceipt(
        file_id=file_id,
        name=str(meta.get("name") or path.name),
        mime_type=str(meta.get("mimeType") or mime_type),
        size=size,
        sha256=drive_hash,
        md5=drive_md5,
        web_view_link=str(meta.get("webViewLink")) if meta.get("webViewLink") else None,
    )


def store_artifact_via_capability(
    capability: TransportCapability,
    job: ComputeJob,
    artifact_path: Path,
    *,
    artifact_sha256: str | None = None,
    mime_type: str | None = None,
) -> DriveUploadReceipt:
    digest = artifact_sha256 or sha256_file(artifact_path)
    lease = request_drive_upload_lease(
        capability,
        job,
        artifact_path,
        artifact_sha256=digest,
        mime_type=mime_type,
    )
    return upload_drive_resumable(
        str(lease["session_url"]),
        artifact_path,
        expected_sha256=str(lease["expected_sha256"]),
        expected_size=int(lease["expected_size"]),
        mime_type=str(lease["mime_type"]),
    )


def submit_compute_result(
    capability: SubmissionCapability,
    result: dict[str, Any],
    *,
    timeout: int = 60,
) -> dict[str, Any]:
    payload = {k: v for k, v in result.items() if not str(k).startswith("_")}
    req = urllib.request.Request(
        capability.url,
        data=json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "X-Deadworlds-Capability": capability.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    response = _request_json(req, timeout=timeout)
    if response.get("ok") is not True or response.get("status") != "COMPLETE":
        raise RuntimeError(f"Forge rejected compute result: {response}")
    return response
