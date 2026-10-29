from __future__ import annotations

import json
from pathlib import Path

from deadworlds_compute.contracts import ComputeJob, JOB_SOURCE_RULE, JOB_VERSION, sha256_json, validate_job_package
from deadworlds_compute.runner import execute


def make_job(tmp_path: Path):
    manifest = {
        "job_version": JOB_VERSION,
        "analysis_id": "smoke-gaussian-001",
        "comparison_group_id": "smoke:gaussian",
        "candidate_model_id": "normal-location",
        "source_module": "test_fixture",
        "source_version": "v1",
        "random_seed": 20261028,
        "model": {"plugin": "gaussian_location_exact", "parameters": {"prior_mean": 0.0, "prior_sd": 2.0, "known_sigma": 1.0, "chains": 4, "draws": 500}},
        "input_data": {"y": [0.8, 1.0, 1.2, 0.9, 1.1]},
        "evaluation_plan": {"validation_unit_status": "DEFINED_AND_JUSTIFIED", "dependence_structure_status": "MODELED_OR_RESPECTED", "predeclared_discrepancies": ["sample_mean"], "heldout_or_cv_partition_status": "AVAILABLE", "sbc_status": "NOT_RUN", "prior_predictive_status": "NOT_RUN", "abc_summary_discrimination_status": "UNRESOLVED", "predictive_validation_method": "PSIS_LOO", "observed_variable": "y", "partition_sha256": None},
        "artifact_format": "ARVIZ_INFERENCE_DATA_NETCDF",
    }
    expected = {"job_manifest_sha256": sha256_json(manifest), "input_sha256": sha256_json(manifest["input_data"]), "model_spec_sha256": sha256_json(manifest["model"]), "evaluation_plan_sha256": sha256_json(manifest["evaluation_plan"])}
    raw = {"package_version": JOB_VERSION, "sourceRule": JOB_SOURCE_RULE, "manifest": manifest, "expected_hashes": expected}
    return raw


def test_job_and_exact_runner(tmp_path):
    raw = make_job(tmp_path)
    validate_job_package(raw)
    result = execute(ComputeJob(raw), tmp_path / "out")
    assert result["analysis_id"] == "smoke-gaussian-001"
    assert result["artifact_format"] == "JSON_SUMMARY_WITH_EXTERNAL_DRAW_ARTIFACT"
    assert len(result["artifact_sha256"]) == 64
    assert result["predictive_validation"]["method"] == "PSIS_LOO"
    assert result["predictive_validation"]["pareto_k_max"] is not None
    assert result["posterior_predictive_checks"][0]["discrepancy_id"] == "sample_mean"
    assert "winner_model" not in json.dumps(result)


def test_hash_tampering_rejected(tmp_path):
    raw = make_job(tmp_path)
    raw["manifest"]["input_data"]["y"][0] = 999
    try:
        validate_job_package(raw)
    except ValueError as exc:
        assert "hash mismatch" in str(exc).lower()
    else:
        raise AssertionError("tampered Worker package was accepted")
