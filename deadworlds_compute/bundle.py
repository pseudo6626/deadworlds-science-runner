from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import ComputeJob, validate_job_package
from .transport import SubmissionCapability, TransportCapability


@dataclass(frozen=True)
class ComputeBundle:
    job: ComputeJob
    transport: TransportCapability | None = None
    submission: SubmissionCapability | None = None


def _capability(raw: Any, *, kind: str):
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{kind} must be an object")
    if kind == "transport":
        provider = str(raw.get("provider") or "").strip()
        lease_request_url = str(raw.get("lease_request_url") or "").strip()
        lease_token = str(raw.get("lease_token") or "").strip()
        if not provider or not lease_request_url or not lease_token:
            raise ValueError("transport capability is incomplete")
        return TransportCapability(provider, lease_request_url, lease_token)
    url = str(raw.get("url") or "").strip()
    token = str(raw.get("token") or "").strip()
    if not url or not token:
        raise ValueError("submission capability is incomplete")
    return SubmissionCapability(url, token)


def load_bundle(path: str | Path) -> ComputeBundle:
    raw: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    package = raw.get("package") if isinstance(raw.get("package"), dict) else raw
    validate_job_package(package)
    if package is raw:
        return ComputeBundle(ComputeJob(package))
    return ComputeBundle(
        ComputeJob(package),
        _capability(raw.get("transport"), kind="transport"),
        _capability(raw.get("submission"), kind="submission"),
    )
