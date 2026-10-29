from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from deadworlds_compute.contracts import ComputeJob, JOB_SOURCE_RULE, JOB_VERSION, sha256_json
from deadworlds_compute.plugins.cultural_closed_state import biased_probabilities
from deadworlds_compute.runner import execute


ROWS = [
    ("P0", {"A": 50, "B": 30, "C": 20}),
    ("P1", {"A": 55, "B": 29, "C": 16}),
    ("P2", {"A": 60, "B": 27, "C": 13}),
    ("P3", {"A": 59, "B": 28, "C": 13}),
    ("P4", {"A": 72, "B": 17, "C": 11}),
    ("P5", {"A": 81, "B": 14, "C": 5}),
]


def make_job(plugin: str, model_id: str, params: dict, artifact_format="JSON_SUMMARY_WITH_EXTERNAL_DRAW_ARTIFACT") -> ComputeJob:
    phase_order = [p for p, _ in ROWS]
    input_data = {
        "trait_family": "synthetic_motif_class",
        "observation_unit": "find",
        "phase_order": phase_order,
        "phase_counts": [
            {"phase_id": p, "counts": c, "sample_size": sum(c.values())} for p, c in ROWS
        ],
        "validation_partition": {
            "scheme": "K_FOLD_TRANSITIONS_V1",
            "fold_count": 3,
            "assignments": {f"P{i}->P{i+1}": i % 3 for i in range(5)},
        },
        "source_semantics": "coded recovered-record frequency; not population prevalence",
    }
    plan = {
        "validation_unit_status": "DEFINED_AND_JUSTIFIED",
        "dependence_structure_status": "MODELED_OR_RESPECTED",
        "predeclared_discrepancies": ["mean_interphase_tv_distance", "mean_destination_shannon_entropy"],
        "heldout_or_cv_partition_status": "AVAILABLE",
        "sbc_status": "NOT_RUN",
        "prior_predictive_status": "NOT_RUN",
        "abc_summary_discrimination_status": "UNRESOLVED",
        "predictive_validation_method": "K_FOLD",
        "inference_method": "FIXED_PREDICTIVE" if model_id == "neutral_unbiased_copying" else "GRID_BAYES",
        "evaluation_scope": "MODEL_ADEQUACY_AND_VALIDATED_RELATIVE_COMPARISON",
        "observed_variable": "phase_counts",
        "partition_sha256": sha256_json(input_data["validation_partition"]),
    }
    manifest = {
        "job_version": JOB_VERSION,
        "analysis_id": f"ct-synthetic-001-{model_id}",
        "comparison_group_id": "ct:synthetic_motif_class",
        "candidate_model_id": model_id,
        "source_module": "cultural_transmission",
        "source_version": "deadworlds-cultural-transmission-v1.0.0",
        "random_seed": 20261028,
        "model": {"plugin": plugin, "parameters": params},
        "input_data": input_data,
        "evaluation_plan": plan,
        "artifact_format": artifact_format,
    }
    return ComputeJob({
        "package_version": JOB_VERSION,
        "sourceRule": JOB_SOURCE_RULE,
        "manifest": manifest,
        "expected_hashes": {
            "job_manifest_sha256": sha256_json(manifest),
            "input_sha256": sha256_json(input_data),
            "model_spec_sha256": sha256_json(manifest["model"]),
            "evaluation_plan_sha256": sha256_json(plan),
        },
    })


def test_frequency_bias_direction_contract():
    x = np.asarray([50, 30, 20])
    neutral = biased_probabilities(x, 0.0)
    common = biased_probabilities(x, -0.3)
    rare = biased_probabilities(x, 0.3)
    assert np.allclose(neutral, [0.5, 0.3, 0.2])
    assert common[0] > neutral[0] and common[-1] < neutral[-1]
    assert rare[0] < neutral[0] and rare[-1] > neutral[-1]


def test_neutral_fixture_reproduces_frozen_v089_numbers(tmp_path: Path):
    job = make_job("cultural_neutral_copying_v1", "neutral_unbiased_copying", {"chains": 4, "draws": 1000})
    r = execute(job, tmp_path / "neutral")
    pv = r["predictive_validation"]
    assert pv["method"] == "K_FOLD"
    assert math.isclose(pv["elpd"], -30.058753607306258, rel_tol=0, abs_tol=1e-10)
    expected = [-5.306281821307621, -5.114887034346822, -4.559275828774986, -8.318798334823626, -6.759510588053203]
    assert np.allclose([x["log_predictive_density"] for x in pv["pointwise"]], expected, atol=1e-10, rtol=0)
    assert r["sampler_diagnostics"]["inference_class"] == "FIXED_PREDICTIVE"
    assert "preferredModel" not in r and "modelTruthProbability" not in r


def test_grid_fixture_reproduces_frozen_v089_numbers(tmp_path: Path):
    job = make_job(
        "cultural_frequency_dependent_grid_v1",
        "frequency_dependent_alternative",
        {"chains": 4, "draws": 1000, "b_prior_min": -0.6, "b_prior_max": 0.6, "grid_points": 1201},
    )
    r = execute(job, tmp_path / "grid")
    pv = r["predictive_validation"]
    assert math.isclose(pv["elpd"], -26.951595127178244, rel_tol=0, abs_tol=1e-10)
    expected = [-4.783394954338751, -4.660451258352586, -6.192741545044889, -6.599398441653179, -4.715608927788838]
    assert np.allclose([x["log_predictive_density"] for x in pv["pointwise"]], expected, atol=1e-10, rtol=0)
    s = r["parameter_summaries"][0]
    assert math.isclose(s["mean"], -0.2588764747792396, abs_tol=1e-12)
    assert math.isclose(s["q05"], -0.40732080106531254, abs_tol=1e-12)
    assert math.isclose(s["q50"], -0.2585178468863979, abs_tol=1e-12)
    assert math.isclose(s["q95"], -0.11443666893163834, abs_tol=1e-12)
    assert s["semantics"] == "MODEL_CONDITIONAL_PARAMETER_SUMMARY_ONLY"


def test_closed_state_blocks_unmodeled_state_appearance(tmp_path: Path):
    job = make_job("cultural_neutral_copying_v1", "neutral_unbiased_copying", {"chains": 4, "draws": 1000})
    job.raw["manifest"]["input_data"]["phase_counts"][0]["counts"] = {"A": 70, "B": 30}
    job.raw["manifest"]["input_data"]["phase_counts"][0]["sample_size"] = 100
    try:
        execute(job, tmp_path / "bad")
    except ValueError as exc:
        assert "zero-to-positive" in str(exc)
    else:
        raise AssertionError("unmodeled state appearance was accepted")
