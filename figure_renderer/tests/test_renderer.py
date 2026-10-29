from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from deadworlds_figures.adapters import plans_for_spec, supported_recipes
from deadworlds_figures.errors import FigureSpecError, UnsupportedRecipeError
from deadworlds_figures.render import render_figure_spec
from deadworlds_figures.validate import validate_figure_spec

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


def test_supported_recipe_set_is_explicit():
    assert supported_recipes() == (
        "m10_energy_lower_bound_ledger",
        "m10_energy_power_identifiability",
        "m10_measurement_formula_provenance",
        "m10_process_trace_prerequisite_matrix",
        "m10_radiative_ceiling_vs_capture",
        "m12a_diversity_distance_by_phase",
        "m12a_trait_frequency_by_phase",
        "m12a_transmission_model_identifiability",
        "m15a_adequacy_vs_preference_contract",
        "m15a_evaluation_method_eligibility",
        "m15a_validation_diagnostics",
    )


def test_live_contract_fixture_validates():
    spec = load("m12_trait_frequency.json")
    assert validate_figure_spec(spec)["spec_version"] == "deadworlds-figure-spec-v1"


def test_unpersisted_provenance_rejected():
    spec = load("m12_trait_frequency.json")
    spec["provenance"]["module_run_id"] = "UNPERSISTED"
    with pytest.raises(FigureSpecError, match="persisted module_run_id"):
        validate_figure_spec(spec)


def test_missing_source_ref_rejected():
    spec = load("m12_trait_frequency.json")
    spec["provenance"]["source_refs"] = []
    with pytest.raises(FigureSpecError, match="source_ref"):
        validate_figure_spec(spec)


def test_hidden_truth_binding_rejected():
    spec = load("m12_trait_frequency.json")
    spec["data"]["bindings"]["hidden_truth"] = {"answer": "forbidden"}
    with pytest.raises(FigureSpecError, match="unlicensed/hidden"):
        validate_figure_spec(spec)


def test_nonfinite_plot_value_rejected():
    spec = load("m12_trait_frequency.json")
    spec["data"]["bindings"]["traitFrequencyLedger"][0]["frequencies"]["A"] = math.nan
    with pytest.raises(FigureSpecError, match="non-finite"):
        validate_figure_spec(spec)


def test_module12_fake_model_fit_rejected():
    spec = load("m12_identifiability.json")
    spec["data"]["bindings"]["modelComparisonResult"] = {"preferred": "neutral"}
    with pytest.raises(FigureSpecError, match="model-comparison"):
        validate_figure_spec(spec)


def test_trait_frequency_adapter_uses_source_frequencies():
    spec = load("m12_trait_frequency.json")
    plans = plans_for_spec(spec)
    assert len(plans) == 1
    assert plans[0].kind == "line"
    series = {s.label: s.y for s in plans[0].series}
    assert series["A"] == [0.5, 0.55, 0.6, 0.59, 0.72, 0.81]
    assert plans[0].y_label == "Recovered-sample frequency"


def test_diversity_distance_emits_separate_single_panel_components():
    plans = plans_for_spec(load("m12_diversity_distance.json"))
    assert len(plans) == 2
    assert {p.suffix.split("__")[0] for p in plans} == {"diversity", "phase_distance"}


def test_model15_validation_adapter_preserves_status_text():
    plans = plans_for_spec(load("m15_validation_diagnostics.json"))
    assert len(plans) == 1
    cells = {r[0]: r[1] for r in plans[0].table_rows}
    assert cells["SBC"] == "PASSED_IMPLEMENTATION_VALIDATION"
    assert cells["ABC summary discrimination"] == "UNRESOLVED"


def test_module10_energy_ledger_uses_joule_values():
    plans = plans_for_spec(load("m10_energy_lower_bound_ledger.json"))
    assert len(plans) == 1
    assert plans[0].kind == "barh"
    assert plans[0].x_label == "Energy (J)"
    assert plans[0].series[0].y == [9806.65, 720.0]


def test_module10_energy_power_never_combines_joules_and_watts():
    plans = plans_for_spec(load("m10_energy_power_identifiability.json"))
    kinds = {p.suffix: p.x_label for p in plans}
    assert kinds["identified_energy"] == "Energy (J)"
    assert kinds["identified_power"] == "Average power (W)"
    assert "blocked_quantities" in kinds


def test_module10_radiative_capture_null_is_not_plotted_as_zero():
    plans = plans_for_spec(load("m10_radiative_ceiling_vs_capture.json"))
    assert len(plans) == 2
    assert all(len(p.series) == 1 for p in plans)
    assert all(p.series[0].label == "Incident ceiling" for p in plans)


def test_module10_provenance_preserves_formula_and_inputs():
    plan = plans_for_spec(load("m10_measurement_formula_provenance.json"))[0]
    assert plan.kind == "table"
    assert "E_min = m g |Δh|" in plan.table_rows[0]
    assert any("mass_kg=250.0 kg" in cell for cell in plan.table_rows[0])


def test_render_bundle_emits_requested_static_files_and_manifest(tmp_path):
    spec = load("m12_trait_frequency.json")
    manifest = render_figure_spec(spec, tmp_path)
    component = manifest["components"][0]
    names = {f["name"] for f in component["files"]}
    assert any(n.endswith(".png") for n in names)
    assert any(n.endswith(".svg") for n in names)
    assert any(n.endswith(".csv") for n in names)
    assert any(n.endswith(".json") for n in names)
    assert (tmp_path / "figure_spec.json").exists()
    assert (tmp_path / "render_manifest.json").exists()
    assert manifest["scientific_rendering_policy"]["llm_numeric_plot_data_allowed"] is False
    assert all(f["sha256"] for f in component["files"])


def test_module10_static_fallback_warns_when_interactive_requested(tmp_path):
    manifest = render_figure_spec(load("m10_measurement_formula_provenance.json"), tmp_path)
    assert any("interactive_html" in x for x in manifest["warnings"])
    assert any(x["name"].endswith(".png") for x in manifest["components"][0]["files"])


def test_model15_status_table_renders(tmp_path):
    manifest = render_figure_spec(load("m15_method_eligibility.json"), tmp_path)
    assert manifest["components"][0]["kind"] == "status_table"
    assert any(x["name"].endswith(".png") for x in manifest["components"][0]["files"])


def test_unsupported_recipe_fails_closed():
    spec = load("m12_trait_frequency.json")
    spec["recipe_id"] = "m01_equilibrium_temperature_albedo_sensitivity"
    with pytest.raises(UnsupportedRecipeError):
        plans_for_spec(spec)


def test_schema_precision_policy_cannot_be_relaxed():
    spec = load("m15_method_eligibility.json")
    spec["epistemics"]["precision_policy"] = "round_more_precisely"
    with pytest.raises(FigureSpecError, match="schema violation"):
        validate_figure_spec(spec)


def test_repeat_render_is_byte_deterministic(tmp_path):
    spec = load("m10_energy_lower_bound_ledger.json")
    a = tmp_path / "a"
    b = tmp_path / "b"
    ma = render_figure_spec(spec, a)
    mb = render_figure_spec(spec, b)
    files_a = {f["name"]: f["sha256"] for c in ma["components"] for f in c["files"]}
    files_b = {f["name"]: f["sha256"] for c in mb["components"] for f in c["files"]}
    assert files_a == files_b
    assert ma["spec_sha256"] == mb["spec_sha256"]
