from __future__ import annotations

import hashlib
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
        "m01_equilibrium_temperature_albedo_sensitivity",
        "m01_escape_retention_sensitivity",
        "m01_multistar_forcing_contributors",
        "m02_atmospheric_element_budget",
        "m02_redox_ratio_diagnostics",
        "m02_rock_metal_ice_composition",
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



def _m01_fixture(recipe_id: str) -> dict:
    common = {
        "spec_version": "deadworlds-figure-spec-v1", "figure_id": f"atmospheric_evolution:{recipe_id}:fixture",
        "module_id": "01_atmospheric_evolution", "module_version": "deadworlds-atmospheric-evolution-v1.1.2", "recipe_id": recipe_id,
        "title": recipe_id, "purpose": "Module 1 deterministic renderer regression fixture.", "dimensionality": "2d",
        "renderer": {"preferred": "matplotlib", "fallbacks": ["plotly"], "style_profile": "planetary_science_publication_v1"},
        "data": {"source_kind": "deterministic_diagnostic", "bindings": {}, "units_policy": "explicit_si_or_domain_standard"},
        "axes": {"units_policy": "explicit_si_or_domain_standard"},
        "uncertainty": {"representation": "sensitivity_grid", "meaning": "Explicit deterministic sensitivity fixture."},
        "epistemics": {"method_ids": ["atmospheric-energy-balance"], "assumptions": ["Fixture only."], "blocked_if": [], "precision_policy": "never_exceed_source_precision"},
        "outputs": ["svg", "png", "csv", "json"],
        "provenance": {"renderer_version_required": True, "module_run_id_required": True, "source_refs_required": True, "module_run_id": "10000000-0000-4000-8000-000000000001", "source_refs": ["fixture:atmosphere:m01"]},
    }
    if recipe_id == "m01_equilibrium_temperature_albedo_sensitivity":
        common["data"]["bindings"] = {"orbitMeanBolometricFluxSearth": 1.0, "equilibriumTemperatureSensitivity": [{"bondAlbedo": 0.0, "equilibriumTemperatureK": 278.3},{"bondAlbedo": 0.3, "equilibriumTemperatureK": 254.55856631},{"bondAlbedo": 0.6, "equilibriumTemperatureK": 221.32384382}]}
    elif recipe_id == "m01_escape_retention_sensitivity":
        rows = []
        for species, values in {"H2": [44.0,22.0,11.0,5.5], "He": [88.0,44.0,22.0,11.0], "mean_atmosphere": [620.0,310.0,155.0,77.5]}.items():
            for texo, value in zip([500.0,1000.0,2000.0,4000.0], values): rows.append({"species": species, "assumedExobaseTemperatureK": texo, "referenceJeansLambda": value})
        common["data"]["bindings"] = {"referenceJeansSensitivity": rows, "escapeRateResult": None, "historyResult": None}
    elif recipe_id == "m01_multistar_forcing_contributors":
        common["uncertainty"] = {"representation": "envelope", "meaning": "Resolved contributor geometry."}
        common["data"]["bindings"] = {"forcingCompleteness": "resolved", "combinedResolvedMeanBolometricFluxSearth": 0.93, "radiativeContributors": [{"starBodyId":0,"relation":"immediate_host","starClass":"G","resolved":True,"orbitMeanBolometricFluxSearth":0.75},{"starBodyId":2,"relation":"ancestral_star","starClass":"K","resolved":True,"orbitMeanBolometricFluxSearth":0.18},{"starBodyId":5,"relation":"unresolved_context","starClass":"M","resolved":False,"orbitMeanBolometricFluxSearth":None}]}
    else: raise ValueError(recipe_id)
    return common


def test_module1_albedo_adapter_uses_existing_diagnostic_rows():
    plan = plans_for_spec(_m01_fixture("m01_equilibrium_temperature_albedo_sensitivity"))[0]
    assert plan.kind == "line" and plan.series[0].x == [0.0,0.3,0.6]
    assert plan.series[0].y == [278.3,254.55856631,221.32384382]
    assert "not measured surface temperature" in plan.note


def test_module1_escape_adapter_is_sensitivity_not_rate_or_history():
    plan = plans_for_spec(_m01_fixture("m01_escape_retention_sensitivity"))[0]
    assert plan.x_label == "Assumed exobase temperature (K)" and plan.y_label == "Reference Jeans λ (dimensionless)"
    assert {s.label for s in plan.series} == {"H2","He","mean_atmosphere"}
    assert all(s.x == [500.0,1000.0,2000.0,4000.0] for s in plan.series)
    assert "not an inferred Jeans parameter" in plan.note and "escape rate" in plan.note and "atmospheric-loss history" in plan.note


def test_module1_multistar_keeps_contributors_separate_and_never_zero_fills():
    plan = plans_for_spec(_m01_fixture("m01_multistar_forcing_contributors"))[0]
    assert plan.kind == "barh" and plan.series[0].y == [0.75,0.18]
    assert "Unresolved contributors are omitted, never plotted as zero" in plan.note


def test_module1_3d_geometry_remains_unsupported():
    spec = _m01_fixture("m01_multistar_forcing_contributors"); spec["recipe_id"] = "m01_orbital_irradiation_geometry_3d"; spec["dimensionality"] = "3d"
    with pytest.raises(UnsupportedRecipeError): plans_for_spec(spec)


def test_module1_escape_rejects_actual_rate_or_history_results():
    spec = _m01_fixture("m01_escape_retention_sensitivity"); spec["data"]["bindings"]["escapeRateResult"] = {"kg_s": 1.0}
    with pytest.raises(FigureSpecError, match="rate/history"): validate_figure_spec(spec)



def _m02_fixture(recipe_id: str) -> dict:
    source_kind = "measured_evidence" if recipe_id == "m02_rock_metal_ice_composition" else "deterministic_diagnostic"
    spec = {
        "spec_version": "deadworlds-figure-spec-v1",
        "figure_id": f"geochemical_cycling:{recipe_id}:fixture",
        "module_id": "02_geochemical_cycling",
        "module_version": "deadworlds-geochemical-cycling-v1.0.1",
        "recipe_id": recipe_id,
        "title": recipe_id,
        "purpose": "Module 2 deterministic renderer regression fixture.",
        "dimensionality": "2d",
        "renderer": {"preferred": "matplotlib", "fallbacks": ["plotly"], "style_profile": "geochemistry_publication_v1"},
        "data": {"source_kind": source_kind, "bindings": {}, "units_policy": "explicit_si_or_domain_standard"},
        "axes": {"units_policy": "explicit_si_or_domain_standard"},
        "uncertainty": {"representation": "none", "meaning": "Measured or deterministic bookkeeping fixture."},
        "epistemics": {"method_ids": ["mantle-redox-2025"], "assumptions": ["Fixture only."], "blocked_if": [], "precision_policy": "never_exceed_source_precision"},
        "outputs": ["svg", "png", "csv", "json"],
        "provenance": {"renderer_version_required": True, "module_run_id_required": True, "source_refs_required": True, "module_run_id": "10000000-0000-4000-8000-000000000002", "source_refs": ["fixture:geochemistry:m02"]},
    }
    if recipe_id == "m02_rock_metal_ice_composition":
        spec["data"]["bindings"] = {"solidComposition": [
            {"name": "Rock", "fraction": 0.62, "reported": 62.0, "basis": "explicit_percent_or_share"},
            {"name": "Metal", "fraction": 0.28, "reported": 28.0, "basis": "explicit_percent_or_share"},
            {"name": "Ice", "fraction": 0.10, "reported": 10.0, "basis": "explicit_percent_or_share"},
        ]}
    elif recipe_id == "m02_atmospheric_element_budget":
        spec["data"]["bindings"] = {"recognizedMoleFraction": 0.99, "elements": [
            {"element": "C", "moles_per_mole_atmosphere": 0.50, "mass_kg_per_mole_atmosphere": 0.00600535},
            {"element": "O", "moles_per_mole_atmosphere": 1.00, "mass_kg_per_mole_atmosphere": 0.0159994},
            {"element": "N", "moles_per_mole_atmosphere": 0.98, "mass_kg_per_mole_atmosphere": 0.013726566},
        ]}
    elif recipe_id == "m02_redox_ratio_diagnostics":
        spec["data"]["bindings"] = {"gasRedoxRatios": [
            {"label": "CO2/CO", "numerator": "carbon dioxide", "denominator": "carbon monoxide", "ratio": 100.0, "log10_ratio": 2.0, "basis": "measured present atmospheric mole/volume fractions"},
            {"label": "H2O/H2", "numerator": "water", "denominator": "hydrogen", "ratio": 0.1, "log10_ratio": -1.0, "basis": "measured present atmospheric mole/volume fractions"},
        ], "mantleOxygenFugacity": None, "redoxBufferOffset": None, "aqueousPh": None}
    else:
        raise ValueError(recipe_id)
    return spec


def test_module2_composition_uses_only_broad_dss_classes():
    plan = plans_for_spec(_m02_fixture("m02_rock_metal_ice_composition"))[0]
    assert plan.kind == "barh"
    assert plan.series[0].y == [0.62, 0.28, 0.10]
    assert "not a mineral assemblage" in plan.note


def test_module2_element_budget_uses_stoichiometric_atmospheric_bookkeeping():
    plan = plans_for_spec(_m02_fixture("m02_atmospheric_element_budget"))[0]
    assert plan.kind == "barh"
    assert plan.series[0].y == [0.50, 1.00, 0.98]
    assert "recognized-gas coverage" in plan.note
    assert "not a whole-planet elemental inventory" in plan.note


def test_module2_redox_ratio_uses_log10_present_atmosphere_only():
    plan = plans_for_spec(_m02_fixture("m02_redox_ratio_diagnostics"))[0]
    assert plan.series[0].y == [2.0, -1.0]
    assert "not mantle oxygen fugacity" in plan.note


def test_module2_redox_ratio_rejects_mantle_fo2_result():
    spec = _m02_fixture("m02_redox_ratio_diagnostics")
    spec["data"]["bindings"]["mantleOxygenFugacity"] = {"delta_fmq": 1.0}
    with pytest.raises(FigureSpecError, match="mantle"):
        validate_figure_spec(spec)


def test_module2_phase_space_remains_unsupported_without_thermodynamic_dataset():
    spec = _m02_fixture("m02_atmospheric_element_budget")
    spec["recipe_id"] = "m02_phase_space"
    with pytest.raises(UnsupportedRecipeError):
        plans_for_spec(spec)


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
    spec["recipe_id"] = "m99_not_implemented"
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


def test_worker_canonical_spec_bytes_are_authoritative(tmp_path):
    spec = load("m10_energy_lower_bound_ledger.json")
    canonical = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    manifest = render_figure_spec(spec, tmp_path, canonical_spec_json=canonical)
    assert manifest["spec_sha256"] == expected
    assert manifest["spec_hash_basis"] == "worker_canonical_json_v1"
    assert manifest["figure_spec_file_sha256"] == hashlib.sha256((tmp_path / "figure_spec.json").read_bytes()).hexdigest()

def test_worker_canonical_spec_object_mismatch_is_rejected(tmp_path):
    spec = load("m10_energy_lower_bound_ledger.json")
    wrong = dict(spec)
    wrong["title"] = "different immutable spec"
    canonical = json.dumps(wrong, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with pytest.raises(ValueError, match="does not match supplied FigureSpec"):
        render_figure_spec(spec, tmp_path, canonical_spec_json=canonical)
