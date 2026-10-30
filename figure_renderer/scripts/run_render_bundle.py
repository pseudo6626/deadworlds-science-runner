from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from deadworlds_figures import __version__ as renderer_version
from deadworlds_figures.render import render_figure_spec

USER_AGENT = f"deadworlds-figure-renderer/{renderer_version}"
PACKAGE_VERSION = "deadworlds-figure-render-job-v0.2.0"
BUNDLE_VERSION = "deadworlds-figure-render-bundle-v0.2.0"
EXPECTED_RENDERER = "deadworlds-figure-renderer-v0.7.0"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(raw)


def post_json(
    url: str,
    payload: dict,
    capability: str,
    *,
    retry_transient: bool = False,
) -> dict:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    attempts = 3 if retry_transient else 1
    for attempt in range(attempts):
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
                "X-Deadworlds-Capability": capability,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if retry_transient and exc.code in {500, 502, 503, 504} and attempt + 1 < attempts:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"HTTP {exc.code} from {url}: {detail[:3000]}") from exc
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            if retry_transient and attempt + 1 < attempts:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Transport failure submitting to {url}: {exc}") from exc
    raise RuntimeError(f"Transient submission retries exhausted for {url}")


def deterministic_zip(source_dir: Path, output_path: Path) -> None:
    files = sorted(p for p in source_dir.rglob("*") if p.is_file())
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            rel = path.relative_to(source_dir).as_posix()
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 3
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def upload_drive(session_url: str, bundle_path: Path) -> dict:
    data = bundle_path.read_bytes()
    req = urllib.request.Request(
        session_url,
        data=data,
        method="PUT",
        headers={
            "Content-Type": "application/zip",
            "Content-Length": str(len(data)),
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Drive resumable upload failed: HTTP {exc.code}: {detail[:3000]}") from exc


def main() -> int:
    p = argparse.ArgumentParser(description="Execute one immutable Deadworlds figure-render bundle")
    p.add_argument("bundle", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    if bundle.get("bundle_version") != BUNDLE_VERSION:
        raise SystemExit("Render bundle version mismatch")
    job_id = str(bundle.get("render_job_id") or "")
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", job_id):
        raise SystemExit("Invalid render_job_id in bundle")
    package = bundle.get("package") or {}
    if package.get("package_version") != PACKAGE_VERSION or package.get("sourceRule") != "WORKER_ISSUED_IMMUTABLE_FIGURE_RENDER_JOB":
        raise SystemExit("Render package contract mismatch")
    policy = package.get("renderer_policy") or {}
    if policy.get("renderer_version") != EXPECTED_RENDERER or f"deadworlds-figure-renderer-v{renderer_version}" != EXPECTED_RENDERER:
        raise SystemExit("Renderer version does not match Worker-issued policy")
    spec = package.get("figure_spec")
    if not isinstance(spec, dict):
        raise SystemExit("Render package is missing FigureSpec")
    canonical_spec_json = package.get("figure_spec_canonical_json")
    if not isinstance(canonical_spec_json, str) or not canonical_spec_json:
        raise SystemExit("Render package is missing authoritative canonical FigureSpec JSON")
    expected_spec_sha = str(package.get("expected_hashes", {}).get("figure_spec_sha256") or "").lower()
    got_spec_sha = sha256_bytes(canonical_spec_json.encode("utf-8"))
    if got_spec_sha != expected_spec_sha:
        raise SystemExit("Canonical FigureSpec SHA-256 does not match immutable package")
    try:
        canonical_spec = json.loads(canonical_spec_json)
    except json.JSONDecodeError as exc:
        raise SystemExit("Canonical FigureSpec JSON is invalid") from exc
    if canonical_spec != spec:
        raise SystemExit("Canonical FigureSpec JSON does not match package FigureSpec")
    spec = canonical_spec

    work = args.out
    rendered = work / "rendered"
    if work.exists():
        shutil.rmtree(work)
    rendered.mkdir(parents=True)
    manifest = render_figure_spec(spec, rendered, strict_provenance=True, canonical_spec_json=canonical_spec_json)
    if manifest.get("renderer_version") != EXPECTED_RENDERER:
        raise SystemExit("Rendered manifest renderer version mismatch")
    if manifest.get("spec_sha256") != expected_spec_sha:
        raise SystemExit("Rendered manifest canonical FigureSpec hash mismatch")
    if manifest.get("spec_hash_basis") != "worker_canonical_json_v1":
        raise SystemExit("Rendered manifest FigureSpec hash basis mismatch")
    if manifest.get("figure_spec_file_sha256") != hashlib.sha256((rendered / "figure_spec.json").read_bytes()).hexdigest():
        raise SystemExit("Rendered manifest FigureSpec sidecar hash mismatch")

    bundle_path = work / f"deadworlds-render-{job_id}.zip"
    deterministic_zip(rendered, bundle_path)
    zip_bytes = bundle_path.read_bytes()
    bundle_sha = sha256_bytes(zip_bytes)
    bundle_size = len(zip_bytes)

    transport = bundle.get("transport") or {}
    lease = post_json(
        transport["lease_request_url"],
        {
            "render_job_id": job_id,
            "figure_spec_sha256": expected_spec_sha,
            "bundle_sha256": bundle_sha,
            "byte_size": bundle_size,
            "mime_type": "application/zip",
            "filename": bundle_path.name,
            "renderer_version": EXPECTED_RENDERER,
        },
        transport["lease_token"],
    )
    lease_data = lease.get("lease") or lease
    session_url = lease_data.get("upload_session_url") or lease_data.get("session_url")
    if not session_url:
        raise SystemExit("Forge lease did not return Drive resumable session URL")
    drive = upload_drive(session_url, bundle_path)
    file_id = str(drive.get("id") or "")
    if not file_id:
        raise SystemExit("Drive upload response did not include file id")

    submission = bundle.get("submission") or {}
    result = post_json(
        submission["url"],
        {
            "render_job_id": job_id,
            "figure_spec_sha256": expected_spec_sha,
            "renderer_version": EXPECTED_RENDERER,
            "bundle_sha256": bundle_sha,
            "bundle_size_bytes": bundle_size,
            "bundle_mime_type": "application/zip",
            "bundle_name": bundle_path.name,
            "render_manifest": manifest,
            "transport": {
                "provider": "GOOGLE_DRIVE_RESUMABLE",
                "file_id": file_id,
                "size_bytes": bundle_size,
                "mime_type": "application/zip",
                "file_name": bundle_path.name,
                "md5_checksum": drive.get("md5Checksum") or "",
            },
        },
        submission["token"],
        retry_transient=True,
    )
    if not result.get("ok") or result.get("status") != "COMPLETE":
        raise SystemExit(f"Forge rejected render result: {result}")
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
