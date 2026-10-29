from __future__ import annotations

import importlib.metadata
import json
import platform
from pathlib import Path
from typing import Any

from . import __version__
from .contracts import ComputeJob, RESULT_SOURCE_RULE, RESULT_VERSION, sha256_file
from .plugins.gaussian_exact import GaussianLocationExactPlugin
from .plugins.pymc_gaussian import PyMCGaussianLocationPlugin
from .plugins.cultural_kandler import CulturalNeutralKandlerABCPlugin, CulturalFrequencyKandlerABCPlugin
from .plugins.cultural_closed_state import CulturalNeutralCopyingPlugin, CulturalFrequencyDependentGridPlugin
from .plugins.pymc_cultural import PyMCCulturalFrequencyDependentPlugin
from .transport import TransportCapability, store_artifact_via_capability

PLUGINS = {
    GaussianLocationExactPlugin.name: GaussianLocationExactPlugin(),
    PyMCGaussianLocationPlugin.name: PyMCGaussianLocationPlugin(),
    CulturalNeutralKandlerABCPlugin.name: CulturalNeutralKandlerABCPlugin(),
    CulturalFrequencyKandlerABCPlugin.name: CulturalFrequencyKandlerABCPlugin(),
    CulturalNeutralCopyingPlugin.name: CulturalNeutralCopyingPlugin(),
    CulturalFrequencyDependentGridPlugin.name: CulturalFrequencyDependentGridPlugin(),
    PyMCCulturalFrequencyDependentPlugin.name: PyMCCulturalFrequencyDependentPlugin(),
}


def _version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def execute(
    job: ComputeJob,
    output_dir: str | Path,
    *,
    transport: TransportCapability | None = None,
) -> dict[str, Any]:
    plugin = PLUGINS.get(job.plugin)
    if plugin is None:
        raise ValueError(f"Unsupported model plugin: {job.plugin}. Available: {sorted(PLUGINS)}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run = plugin.run(job, out_dir)
    artifact_hash = sha256_file(run.draw_artifact)
    artifact_ref = run.draw_artifact.resolve().as_uri()
    storage_receipt = None

    if transport is not None:
        artifact_mime = {
            ".nc": "application/x-netcdf",
            ".npz": "application/octet-stream",
            ".zip": "application/zip",
        }.get(run.draw_artifact.suffix.lower(), "application/octet-stream")
        receipt = store_artifact_via_capability(
            transport,
            job,
            run.draw_artifact,
            artifact_sha256=artifact_hash,
            mime_type=artifact_mime,
        )
        artifact_ref = receipt.artifact_ref
        storage_receipt = {
            "provider": "google_drive",
            "file_id": receipt.file_id,
            "name": receipt.name,
            "mime_type": receipt.mime_type,
            "size": receipt.size,
            "sha256": receipt.sha256,
            "md5": receipt.md5,
            "web_view_link": receipt.web_view_link,
        }

    expected = job.expected_hashes
    result = {
        "artifactVersion": RESULT_VERSION,
        "sourceRule": RESULT_SOURCE_RULE,
        "analysis_id": job.analysis_id,
        "comparison_group_id": job.group_id,
        "candidate_model_id": job.model_id,
        "job_manifest_sha256": expected["job_manifest_sha256"],
        "input_sha256": expected["input_sha256"],
        "model_spec_sha256": expected["model_spec_sha256"],
        "evaluation_plan_sha256": expected["evaluation_plan_sha256"],
        "random_seed": job.random_seed,
        "runner": {
            "name": "deadworlds-science-runner",
            "version": __version__,
            "libraries": {
                "python": platform.python_version(),
                "numpy": _version("numpy") or "unknown",
                "arviz": _version("arviz") or "unknown",
                "xarray": _version("xarray") or "unknown",
                **({"pymc": _version("pymc")} if job.plugin.startswith("pymc_") and _version("pymc") else {}),
            },
        },
        "artifact_ref": artifact_ref,
        "artifact_sha256": artifact_hash,
        "artifact_format": run.artifact_format,
        "sampler_diagnostics": run.sampler_diagnostics,
        "posterior_predictive_checks": run.posterior_predictive_checks,
        "predictive_validation": run.predictive_validation,
        "sbc": run.sbc,
    }
    if run.abc_diagnostics is not None:
        result["abc_diagnostics"] = run.abc_diagnostics
    if run.parameter_summaries is not None:
        result["parameter_summaries"] = run.parameter_summaries
    if storage_receipt is not None:
        result["storage_receipt"] = storage_receipt
        result["transport"] = {
            "provider": "GOOGLE_DRIVE_RESUMABLE",
            "file_id": storage_receipt["file_id"],
            "size_bytes": storage_receipt["size"],
            "md5_checksum": storage_receipt["md5"],
            "sha256_checksum": storage_receipt["sha256"],
            "mime_type": storage_receipt["mime_type"],
            "file_name": storage_receipt["name"],
        }

    result_path = out_dir / f"{job.analysis_id}__{job.model_id}__result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["_result_path"] = str(result_path)
    return result
