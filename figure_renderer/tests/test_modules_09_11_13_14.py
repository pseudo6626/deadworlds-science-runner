from __future__ import annotations

import copy

import pytest

from deadworlds_figures.adapters import plans_for_spec
from deadworlds_figures.errors import FigureSpecError
from deadworlds_figures.validate import validate_figure_spec


def _base(module_id: str, module_version: str, recipe_id: str, style: str, source_kind: str = "deterministic_diagnostic") -> dict:
    return {
        "spec_version": "deadworlds-figure-spec-v1",
        "figure_id": f"{module_id}:{recipe_id}:fixture",
        "module_id": module_id,
        "module_version": module_version,
        "recipe_id": recipe_id,
        "title": recipe_id,
        "purpose": "v0.7 renderer regression fixture",
        "dimensionality": "2d",
        "renderer": {"preferred": "matplotlib", "fallbacks": ["plotly"], "style_profile": style},
        "data": {"source_kind": source_kind, "bindings": {}, "units_policy": "explicit_si_or_domain_standard"},
        "axes": {"units_policy": "explicit_si_or_domain_standard"},
        "uncertainty": {"representation": "categorical_status", "meaning": "Regression fixture status only."},
        "epistemics": {
            "method_ids": ["fixture-method"],
            "assumptions": ["Regression fixture only."],
            "blocked_if": [],
            "precision_policy": "never_exceed_source_precision",
        },
        "outputs": ["svg", "png", "csv", "json"],
        "provenance": {
            "renderer_version_required": True,
            "module_run_id_required": True,
            "source_refs_required": True,
            "module_run_id": "70000000-0000-4000-8000-000000000001",
            "source_refs": ["fixture:v07"],
        },
    }


def _m09(recipe: str) -> dict:
    spec = _base("09_spatial_archaeology", "deadworlds-spatial-archaeology-v1.0.0", recipe, "spatial_archaeology_publication_v1", "derived_evidence")
    if recipe == "m09_recovered_site_map":
        spec["data"]["bindings"] = {
            "georeferencedSites": [
                {"siteId": "A", "frame": "LOCAL_SURVEY_GRID", "surveyAreaId": "grid-1", "xM": 0.0, "yM": 0.0, "zM": None, "latitudeDeg": None, "longitudeDeg": None, "horizontalUncertaintyM": 2.0, "positionBasis": "RECOVERED_SURVEY_GRID"},
                {"siteId": "B", "frame": "LOCAL_SURVEY_GRID", "surveyAreaId": "grid-1", "xM": 300.0, "yM": 400.0, "zM": None, "latitudeDeg": None, "longitudeDeg": None, "horizontalUncertaintyM": 3.0, "positionBasis": "RECOVERED_SURVEY_GRID"},
            ],
            "surveyContext": {"survey_design": "TARGETED", "coverage_completeness": "PARTIAL", "detection_model_status": "QUALITATIVE_ONLY"},
        }
    elif recipe == "m09_pairwise_distance_matrix":
        spec["data"]["bindings"] = {"pairwiseDistances": [{"groupId": "LOCAL_SURVEY_GRID|grid-1", "siteA": "A", "siteB": "B", "distanceM": 500.0, "coordinateUncertaintyBoundM": 5.0, "semantics": "descriptive only"}]}
    elif recipe == "m09_sampling_and_recovery_context":
        spec["data"]["bindings"] = {
            "surveyContext": {"survey_design": "TARGETED", "coverage_completeness": "PARTIAL", "detection_model_status": "QUALITATIVE_ONLY"},
            "samplingFirewall": {"coverageCorrected": False, "absenceLicensed": False},
            "chronologyStatus": "UNRESOLVED_PALIMPSEST_RISK",
            "observedSiteDensityPerKm2": 3.0,
            "observedDensitySemantics": "recovered sites/km2 only",
        }
    elif recipe == "m09_spatial_inference_prerequisite_matrix":
        spec["data"]["bindings"] = {"blockedAnalyses": [{"analysis": "cluster_or_dispersion_significance", "status": "BLOCKED", "reason": "sampling design unresolved", "missingInputs": ["quantitative detection model"]}]}
    else:
        raise ValueError(recipe)
    return spec


def _m11(recipe: str) -> dict:
    spec = _base("11_demography", "deadworlds-demography-v1.0.0", recipe, "demography_publication_v1", "derived_evidence")
    if recipe == "m11a_proxy_concordance_matrix":
        spec["data"]["bindings"] = {
            "proxyLedger": [
                {"proxy_id": "sites", "proxyClass": "site_activity", "status": "ADEQUATE", "direction": "INCREASE", "populationConversionLicensed": False, "phase_ids": ["early", "late"], "phase_values": [3.0, 5.0]},
                {"proxy_id": "finds", "proxyClass": "material_discard", "status": "ADEQUATE", "direction": "INCREASE", "populationConversionLicensed": False, "phase_ids": ["early", "late"], "phase_values": [4.0, 7.0]},
            ],
            "relativeTrend": {"status": "SUPPORTED_RELATIVE_DIRECTION", "direction": "INCREASE", "supportingProxyIds": ["sites", "finds"]},
            "prerequisites": {"detectionAdequate": True, "chronologyAdequate": True},
            "populationResult": None,
        }
    elif recipe == "m11a_population_inference_prerequisites":
        spec["data"]["bindings"] = {
            "prerequisites": {"detectionAdequate": True, "chronologyAdequate": True, "independentProxyClasses": 2},
            "blockedCalculations": [{"quantity": "absolute_population", "status": "BLOCKED", "reason": "alien-specific calibration missing", "missingInputs": ["ALIEN_EMPIRICAL_OCCUPANCY calibration"]}],
            "relativeTrendStatus": "SUPPORTED_RELATIVE_DIRECTION",
            "minimumIndividualsStatus": "UNRESOLVED",
            "absolutePopulationStatus": "UNRESOLVED",
            "populationResult": None,
        }
    elif recipe == "m11a_demographic_inference_ladder":
        spec["data"]["bindings"] = {
            "moduleStatus": "RELATIVE_DEMOGRAPHIC_TREND_SUPPORTED",
            "descriptiveProxyStatus": "RECOVERED_PROXIES_AVAILABLE",
            "relativeTrendStatus": "SUPPORTED_RELATIVE_DIRECTION",
            "minimumIndividualsStatus": "UNRESOLVED",
            "absolutePopulationStatus": "UNRESOLVED",
            "populationResult": None,
        }
    else:
        raise ValueError(recipe)
    return spec


def _m13(recipe: str) -> dict:
    spec = _base("13_language_contact", "deadworlds-language-contact-v1.0.0", recipe, "language_contact_publication_v1", "derived_evidence")
    corp = [{"corpus_id": "A", "modality": "mark_sequence", "pattern_unit_coding_status": "RESOLVED", "independence_status": "SUPPORTED", "communication_status": "UNRESOLVED", "language_status": "UNRESOLVED", "observation_model_status": "ADEQUATE", "representation_status": "RECOVERED_FORM_ONLY", "comparative_readiness": "ELIGIBLE"}]
    cmp = [{"comparison_id": "AB", "corpus_a": "A", "corpus_b": "B", "comparison_kind": "formal_pattern", "observed_similarity_status": "OBSERVED", "semantic_equivalence_status": "UNRESOLVED", "genealogical_baseline_status": "ELIGIBLE", "convergence_baseline_status": "ELIGIBLE", "chance_baseline_status": "ELIGIBLE", "chronology_status": "RESOLVED", "correspondence_model_status": "AVAILABLE", "contact_feasibility_status": "UNRESOLVED", "borrowing_model_eligibility": "ELIGIBLE_FOR_EXPLICIT_MODEL_COMPARISON", "directionality_eligibility": "BLOCKED", "phonetic_method_eligibility": "BLOCKED"}]
    if recipe == "m13a_corpus_readiness":
        spec["data"]["bindings"] = {"corpusReadiness": corp}
    elif recipe == "m13a_alternative_explanation_matrix":
        spec["data"]["bindings"] = {"comparisonLedger": cmp, "candidateModels": [{"model_id": "common_inheritance", "status": "CANDIDATE_FOR_LATER_COMPARISON"}, {"model_id": "horizontal_transfer", "status": "CANDIDATE_FOR_LATER_COMPARISON"}], "modelComparisonResult": None}
    elif recipe == "m13a_direction_identifiability":
        spec["data"]["bindings"] = {"comparisons": [{"comparison_id": "AB", "borrowing_model_eligibility": "ELIGIBLE_FOR_EXPLICIT_MODEL_COMPARISON", "directionality_eligibility": "BLOCKED", "chronology_status": "RESOLVED", "correspondence_model_status": "AVAILABLE"}], "directionResult": None}
    elif recipe == "m13a_comparison_provenance":
        spec["data"]["bindings"] = {"corpora": [{"corpus_id": "A", "independence_status": "SUPPORTED", "representation_status": "RECOVERED_FORM_ONLY"}], "comparisons": [{"comparison_id": "AB", "corpus_a": "A", "corpus_b": "B", "comparison_kind": "formal_pattern"}], "prerequisiteEvidence": [{"target_type": "comparison", "target_id": "AB", "kind": "chronology", "evidence_ref": "forge:chron:C1", "source_module": "09_spatial_archaeology", "status": "SUPPORTED"}]}
    else:
        raise ValueError(recipe)
    return spec


def _m14(recipe: str) -> dict:
    spec = _base("14_inscription_decipherment", "deadworlds-inscription-decipherment-v1.0.0", recipe, "inscription_decipherment_publication_v1", "derived_evidence")
    marks = [{"mark_id": "M1", "formal_description": "three parallel strokes", "variant_status": "DISTINCT_CLASS"}, {"mark_id": "M2", "formal_description": "crossed pair", "variant_status": "DISTINCT_CLASS"}]
    if recipe == "m14a_mark_inventory":
        spec["data"]["bindings"] = {"documents": [{"document_id": "D1", "mark_classes": marks, "preservation_status": "GOOD"}]}
    elif recipe == "m14a_sequence_reading_order":
        spec["data"]["bindings"] = {"documents": [{"document_id": "D1", "sequences": [{"sequence_id": "Q1", "mark_ids": ["M1", "M2", "M1"], "physical_order_status": "OBSERVED_SPATIAL_ORDER", "unknown_positions": 0}]}], "readiness": {"readingOrder": "UNRESOLVED", "segmentation": "UNRESOLVED"}}
    elif recipe == "m14a_decipherment_prerequisite_ladder":
        spec["data"]["bindings"] = {"readiness": {"formalInventory": "AVAILABLE", "writingSystem": "UNRESOLVED", "linguisticAnalysis": "BLOCKED"}, "blockedInferences": [{"quantity": "sign_value_from_shape_similarity", "reason": "independent value evidence missing"}]}
    elif recipe == "m14a_model_handoff":
        spec["data"]["bindings"] = {"modelHandoff": {"contractVersion": "deadworlds-inscription-model-handoff-v1", "status": "BLOCKED_PENDING_PREREQUISITES", "candidateFamilies": [{"family_id": "structural_sequence_model", "status": "CANDIDATE_ONLY"}]}}
    else:
        raise ValueError(recipe)
    return spec


@pytest.mark.parametrize("recipe", [
    "m09_recovered_site_map",
    "m09_pairwise_distance_matrix",
    "m09_sampling_and_recovery_context",
    "m09_spatial_inference_prerequisite_matrix",
])
def test_module9_recipes_validate_and_render_plans(recipe):
    spec = _m09(recipe)
    validate_figure_spec(spec)
    assert plans_for_spec(spec)


def test_module9_map_uses_single_point_series_no_routes():
    plan = plans_for_spec(_m09("m09_recovered_site_map"))[0]
    assert all(len(series.x) == len(series.y) == 1 for series in plan.series)
    assert "no connecting route" in plan.note


def test_module9_local_grid_rejects_fake_planet_coords():
    spec = _m09("m09_recovered_site_map")
    spec["data"]["bindings"]["georeferencedSites"][0]["latitudeDeg"] = 1.0
    with pytest.raises(FigureSpecError, match="MODULE9_FAKE_PLANET_COORDINATES"):
        validate_figure_spec(spec)


def test_module9_rejects_invented_network_result():
    spec = _m09("m09_pairwise_distance_matrix")
    spec["data"]["bindings"]["networkResult"] = {"A": ["B"]}
    with pytest.raises(FigureSpecError, match="MODULE9_UNLICENSED_SPATIAL_INFERENCE"):
        validate_figure_spec(spec)


@pytest.mark.parametrize("recipe", [
    "m11a_proxy_concordance_matrix",
    "m11a_population_inference_prerequisites",
    "m11a_demographic_inference_ladder",
])
def test_module11_recipes_validate_and_render_plans(recipe):
    spec = _m11(recipe)
    validate_figure_spec(spec)
    assert plans_for_spec(spec)


def test_module11_proxy_cannot_be_population():
    spec = _m11("m11a_proxy_concordance_matrix")
    spec["data"]["bindings"]["proxyLedger"][0]["populationConversionLicensed"] = True
    with pytest.raises(FigureSpecError, match="MODULE11_PROXY_TO_POPULATION_FORBIDDEN"):
        validate_figure_spec(spec)


def test_module11_numeric_population_result_rejected():
    spec = _m11("m11a_demographic_inference_ladder")
    spec["data"]["bindings"]["populationResult"] = 9000
    with pytest.raises(FigureSpecError, match="numeric population"):
        validate_figure_spec(spec)


def test_module11_settlement_posterior_recipe_remains_unregistered():
    assert "m11a_settlement_proxy_by_phase" not in {
        "m11a_proxy_concordance_matrix",
        "m11a_population_inference_prerequisites",
        "m11a_demographic_inference_ladder",
    }


@pytest.mark.parametrize("recipe", [
    "m13a_corpus_readiness",
    "m13a_alternative_explanation_matrix",
    "m13a_direction_identifiability",
    "m13a_comparison_provenance",
])
def test_module13_recipes_validate_and_render_plans(recipe):
    spec = _m13(recipe)
    validate_figure_spec(spec)
    assert plans_for_spec(spec)


def test_module13_rejects_model_result():
    spec = _m13("m13a_alternative_explanation_matrix")
    spec["data"]["bindings"]["modelComparisonResult"] = {"preferred": "horizontal_transfer"}
    with pytest.raises(FigureSpecError, match="model-comparison"):
        validate_figure_spec(spec)


def test_module13_rejects_donor_assignment():
    spec = _m13("m13a_direction_identifiability")
    spec["data"]["bindings"]["donor_assignment"] = "A"
    with pytest.raises(FigureSpecError, match="MODULE13_UNLICENSED_CONTACT_RESULT"):
        validate_figure_spec(spec)


def test_module13_rejects_camelcase_donor_assignment():
    spec = _m13("m13a_direction_identifiability")
    spec["data"]["bindings"]["donorAssignment"] = "A"
    with pytest.raises(FigureSpecError, match="MODULE13_UNLICENSED_CONTACT_RESULT"):
        validate_figure_spec(spec)


@pytest.mark.parametrize("recipe", [
    "m14a_mark_inventory",
    "m14a_sequence_reading_order",
    "m14a_decipherment_prerequisite_ladder",
    "m14a_model_handoff",
])
def test_module14_recipes_validate_and_render_plans(recipe):
    spec = _m14(recipe)
    validate_figure_spec(spec)
    assert plans_for_spec(spec)


def test_module14_rejects_translation_result():
    spec = _m14("m14a_mark_inventory")
    spec["data"]["bindings"]["translation"] = "royal grain tax"
    with pytest.raises(FigureSpecError, match="MODULE14_PREMATURE_DECIPHERMENT_RESULT"):
        validate_figure_spec(spec)


def test_module14_mark_inventory_preserves_form_without_meaning():
    plan = plans_for_spec(_m14("m14a_mark_inventory"))[0]
    assert plan.table_rows[0][2] == "three parallel strokes"
    assert "No sound" in plan.note
