from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from deadworlds_compute.contracts import ComputeJob, JOB_SOURCE_RULE, JOB_VERSION, sha256_json
from deadworlds_compute.plugins.cultural_kandler import kandler_replacement_probabilities
from deadworlds_compute.runner import execute


def make_job(plugin: str, model_id: str, *, seed: int = 12345) -> ComputeJob:
    params = {
        "population_size": 200,
        "innovation_rate": 0.02,
        "replacement_fraction_low": 0.1,
        "replacement_fraction_high": 0.3,
        "dirichlet_alpha_observed": 1.0,
        "dirichlet_alpha_unobserved": 1.0,
        "simulations": 400,
        "retain": 50,
        "posterior_predictive_draws": 100,
        "time_averaging_mode": "UNIFORM_WITHIN_INTERVAL",
        "require_survivor_count_match": True,
    }
    if plugin == "cultural_frequency_dependent_abc":
        params.update(b_freq_low=-0.02, b_freq_high=0.02)
    manifest = {
        "job_version": JOB_VERSION,
        "analysis_id": f"ct-test-{model_id}",
        "comparison_group_id": "cultural_transmission:fixture:P1:P2",
        "candidate_model_id": model_id,
        "source_module": "cultural_transmission",
        "source_version": "deadworlds-cultural-transmission-v1.0.0",
        "random_seed": seed,
        "model": {"plugin": plugin, "parameters": params},
        "input_data": {
            "trait_family": "rim-shape",
            "phase_from": "P1",
            "phase_to": "P2",
            "steps": 10,
            "counts_t1": {"A": 30, "B": 20, "C": 10},
            "counts_t2": {"A": 25, "B": 20, "C": 12, "D": 3},
        },
        "evaluation_plan": {
            "validation_unit_status": "DEFINED_AND_JUSTIFIED",
            "dependence_structure_status": "MODELED_OR_RESPECTED",
            "predeclared_discrepancies": [
                "phase_transition_total_variation",
                "initial_variant_survival_count",
                "max_initial_variant_frequency_t2",
            ],
            "heldout_or_cv_partition_status": "UNRESOLVED",
            "sbc_status": "NOT_RUN",
            "prior_predictive_status": "PLANNED",
            "abc_summary_discrimination_status": "UNRESOLVED",
            "predictive_validation_method": "NONE",
            "observed_variable": "trait_count",
            "partition_sha256": None,
        },
        "artifact_format": "ARVIZ_INFERENCE_DATA_NETCDF",
    }
    raw = {
        "package_version": JOB_VERSION,
        "sourceRule": JOB_SOURCE_RULE,
        "manifest": manifest,
        "expected_hashes": {
            "job_manifest_sha256": sha256_json(manifest),
            "input_sha256": sha256_json(manifest["input_data"]),
            "model_spec_sha256": sha256_json(manifest["model"]),
            "evaluation_plan_sha256": sha256_json(manifest["evaluation_plan"]),
        },
    }
    return ComputeJob(raw)


def test_frequency_rule_direction():
    survivors = np.asarray([70, 20, 10, 0], dtype=np.int64)
    neutral = kandler_replacement_probabilities(survivors, b_freq=0.0, innovation_rate=0.0)
    conformist = kandler_replacement_probabilities(survivors, b_freq=0.02, innovation_rate=0.0)
    anticonformist = kandler_replacement_probabilities(survivors, b_freq=-0.02, innovation_rate=0.0)
    assert np.allclose(neutral, survivors / survivors.sum())
    assert conformist[0] > neutral[0]
    assert conformist[2] < neutral[2]
    assert anticonformist[0] < neutral[0]
    assert anticonformist[2] > neutral[2]
    assert np.isclose(conformist.sum(), 1.0)
    assert np.isclose(anticonformist.sum(), 1.0)


def test_neutral_cultural_abc_is_noninterpretive(tmp_path: Path):
    result = execute(make_job("cultural_neutral_abc", "neutral_unbiased_copying"), tmp_path / "neutral")
    abc = result["abc_diagnostics"]
    assert abc["method"] == "ABC_REJECTION"
    assert abc["summary_discrimination_status"] == "UNRESOLVED"
    ids = {x["parameter_id"] for x in result["parameter_summaries"]}
    assert "replacement_fraction" in ids
    assert "frequency_bias_b" not in ids
    assert result["predictive_validation"] is None
    assert {x["discrepancy_id"] for x in result["posterior_predictive_checks"]} == {
        "phase_transition_total_variation",
        "initial_variant_survival_count",
        "max_initial_variant_frequency_t2",
    }
    text = json.dumps(result)
    assert "winner_model" not in text
    assert "preferred_model" not in text
    assert "truth_probability" not in text


def test_frequency_dependent_abc_keeps_zero_eligible(tmp_path: Path):
    result = execute(make_job("cultural_frequency_dependent_abc", "frequency_dependent_alternative"), tmp_path / "freq")
    q = next(x for x in result["parameter_summaries"] if x["parameter_id"] == "frequency_bias_b")
    # This deliberately sparse fixture should not falsely force a directional bias.
    assert q["q05"] < 0 < q["q95"]
    assert result["sampler_diagnostics"]["inference_class"] == "ABC"
    assert result["predictive_validation"] is None


def test_cultural_job_requires_explicit_population_assumption(tmp_path: Path):
    job = make_job("cultural_neutral_abc", "neutral_unbiased_copying")
    del job.raw["manifest"]["model"]["parameters"]["population_size"]
    # Re-hash to ensure the failure comes from the scientific plugin, not tamper detection.
    manifest = job.raw["manifest"]
    job.raw["expected_hashes"] = {
        "job_manifest_sha256": sha256_json(manifest),
        "input_sha256": sha256_json(manifest["input_data"]),
        "model_spec_sha256": sha256_json(manifest["model"]),
        "evaluation_plan_sha256": sha256_json(manifest["evaluation_plan"]),
    }
    try:
        execute(job, tmp_path / "bad")
    except ValueError as exc:
        assert "population_size" in str(exc)
    else:
        raise AssertionError("cultural model silently invented a population-size assumption")
