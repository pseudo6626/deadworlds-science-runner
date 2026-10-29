from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

JOB_VERSION = "deadworlds-model-comparison-compute-job-v0.1.0"
RESULT_VERSION = "deadworlds-model-comparison-compute-result-v0.3.0-design"
JOB_SOURCE_RULE = "WORKER_ISSUED_IMMUTABLE_COMPUTE_JOB"
RESULT_SOURCE_RULE = "EXTERNAL_SCIENTIFIC_COMPUTE_ARTIFACT_ONLY"


def js_json_bytes(value: Any) -> bytes:
    """Closest Python equivalent to JSON.stringify for Worker-issued JSON.

    The runner preserves object insertion order from the parsed Worker package.
    Worker job payloads intentionally avoid NaN/Infinity and exotic numeric forms.
    """
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(js_json_bytes(value))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class ComputeJob:
    raw: dict[str, Any]

    @property
    def manifest(self) -> dict[str, Any]:
        return self.raw["manifest"]

    @property
    def expected_hashes(self) -> dict[str, str]:
        return self.raw["expected_hashes"]

    @property
    def analysis_id(self) -> str:
        return str(self.manifest["analysis_id"])

    @property
    def group_id(self) -> str:
        return str(self.manifest["comparison_group_id"])

    @property
    def model_id(self) -> str:
        return str(self.manifest["candidate_model_id"])

    @property
    def random_seed(self) -> int:
        return int(self.manifest["random_seed"])

    @property
    def plugin(self) -> str:
        return str(self.manifest["model"]["plugin"])

    @property
    def parameters(self) -> dict[str, Any]:
        return dict(self.manifest["model"].get("parameters") or {})

    @property
    def input_data(self) -> dict[str, Any]:
        return dict(self.manifest["input_data"])

    @property
    def evaluation_plan(self) -> dict[str, Any]:
        return dict(self.manifest["evaluation_plan"])


def load_job(path: str | Path) -> ComputeJob:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_job_package(raw)
    return ComputeJob(raw)


def validate_job_package(raw: dict[str, Any]) -> None:
    if raw.get("package_version") != JOB_VERSION:
        raise ValueError(f"Unsupported package_version: {raw.get('package_version')!r}")
    if raw.get("sourceRule") != JOB_SOURCE_RULE:
        raise ValueError("Job sourceRule mismatch")
    manifest = raw.get("manifest")
    expected = raw.get("expected_hashes")
    if not isinstance(manifest, dict) or not isinstance(expected, dict):
        raise ValueError("Job must contain manifest and expected_hashes objects")

    required = ["analysis_id", "comparison_group_id", "candidate_model_id", "random_seed", "model", "input_data", "evaluation_plan", "artifact_format"]
    missing = [k for k in required if k not in manifest]
    if missing:
        raise ValueError(f"Job manifest missing fields: {missing}")

    recomputed = {
        "job_manifest_sha256": sha256_json(manifest),
        "input_sha256": sha256_json(manifest["input_data"]),
        "model_spec_sha256": sha256_json(manifest["model"]),
        "evaluation_plan_sha256": sha256_json(manifest["evaluation_plan"]),
    }
    for key, value in recomputed.items():
        if expected.get(key) != value:
            raise ValueError(f"Worker-issued hash mismatch for {key}: expected {expected.get(key)}, recomputed {value}")

    seed = manifest["random_seed"]
    if not isinstance(seed, int) or not (0 <= seed <= 0xFFFFFFFF):
        raise ValueError("random_seed must be a uint32 integer")

    forbidden = ("hiddenCulture", "HIDDEN_AND_FORBIDDEN", "hidden_truth", "winner_model", "preferred_model", "truth_probability")
    compact = json.dumps(manifest, ensure_ascii=False)
    if any(token in compact for token in forbidden):
        raise ValueError("Job manifest contains forbidden hidden/winner semantics")
