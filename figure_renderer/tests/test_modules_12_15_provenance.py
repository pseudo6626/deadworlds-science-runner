from __future__ import annotations

import copy

import pytest

from deadworlds_figures.adapters import plans_for_spec, supported_recipes
from deadworlds_figures.errors import FigureSpecError
from deadworlds_figures.validate import validate_figure_spec


def _base(recipe: str, module_id: str, module_version: str, style: str, bindings: dict) -> dict:
    return {
        "spec_version": "deadworlds-figure-spec-v1",
        "figure_id": f"{module_id}:{recipe}:fixture",
        "module_id": module_id,
        "module_version": module_version,
        "recipe_id": recipe,
        "title": recipe,
        "purpose": "Renderer v0.9 provenance firewall regression fixture.",
        "dimensionality": "2d",
        "renderer": {
            "preferred": "plotly",
            "fallbacks": ["matplotlib"],
            "style_profile": style,
        },
        "data": {
            "source_kind": "derived_evidence",
            "bindings": bindings,
            "units_policy": "explicit_si_or_domain_standard",
        },
        "axes": {"units_policy": "explicit_si_or_domain_standard"},
        "uncertainty": {
            "representation": "categorical_status",
            "meaning": "Provenance/comparability status only.",
        },
        "epistemics": {
            "method_ids": ["fixture"],
            "assumptions": ["Fixture only."],
            "blocked_if": [],
            "precision_policy": "never_exceed_source_precision",
        },
        "outputs": ["svg", "png", "json", "interactive_html"],
        "provenance": {
            "renderer_version_required": True,
            "module_run_id_required": True,
            "source_refs_required": True,
            "module_run_id": "90000000-0000-4000-8000-000000000001",
            "source_refs": ["fixture:v09:public-provenance"],
        },
    }


def _m12() -> dict:
    return _base(
        "m12a_trait_coding_provenance",
        "12_cultural_transmission",
        "deadworlds-cultural-transmission-v1.0.0",
        "cultural_transmission_publication_v1",
        {
            "traitAssignments": [
                {
                    "evidence_ref": "forge:find:F1",
                    "trait_family": "ridge",
                    "trait_state": "parallel",
                    "phase_id": "A",
                    "observation_basis": "parallel ridges visible",
                    "observation_unit": "find",
                    "functional_constraint_status": "FUNCTIONAL_CONSTRAINT_EXCLUDED",
                    "cultural_origin_status": "ESTABLISHED_BY_INDEPENDENT_EVIDENCE",
                },
                {
                    "evidence_ref": "forge:find:F2",
                    "trait_family": "ridge",
                    "trait_state": "crossed",
                    "phase_id": "A",
                    "observation_basis": "crossed ridges visible",
                    "observation_unit": "find",
                    "functional_constraint_status": "FUNCTIONAL_CONSTRAINT_EXCLUDED",
                    "cultural_origin_status": "ESTABLISHED_BY_INDEPENDENT_EVIDENCE",
                },
            ],
            "codingRules": [
                {
                    "trait_family": "ridge",
                    "observation_dimension": "visible ridge orientation",
                    "state_labels": ["parallel", "crossed"],
                    "coding_basis": "direct visible orientation",
                    "functional_constraint_status": "UNRESOLVED",
                }
            ],
        },
    )


def _m15(two_groups: bool = False) -> dict:
    src1 = {
        "comparison_group_id": "cultural_transmission:v1:1",
        "source_module": "cultural_transmission",
        "source_version": "deadworlds-cultural-transmission-v1.0.0",
        "source_rule": "RECOVERED_OBSERVABLE_TRAITS_ONLY",
    }
    models = [
        {
            "comparison_group_id": src1["comparison_group_id"],
            "model_id": "neutral_unbiased_copying",
            "source_module": src1["source_module"],
            "source_version": src1["source_version"],
            "assumptions": ["candidate model from source module"],
            "observed_data_refs": ["derived:cultural_transmission:trait_frequencies"],
            "simulator_status": "AVAILABLE",
            "pointwise_log_likelihood_status": "UNRESOLVED",
            "likelihood_status": "SIMULATOR_ONLY",
        },
        {
            "comparison_group_id": src1["comparison_group_id"],
            "model_id": "frequency_dependent_alternative",
            "source_module": src1["source_module"],
            "source_version": src1["source_version"],
            "assumptions": ["candidate model from source module"],
            "observed_data_refs": ["derived:cultural_transmission:trait_frequencies"],
            "simulator_status": "AVAILABLE",
            "pointwise_log_likelihood_status": "UNRESOLVED",
            "likelihood_status": "SIMULATOR_ONLY",
        },
    ]
    sources = [src1]
    if two_groups:
        src2 = {
            "comparison_group_id": "language_contact:v1:1",
            "source_module": "language_contact",
            "source_version": "deadworlds-language-contact-v1.0.0",
            "source_rule": "RECOVERED_CORPORA_PLUS_INDEPENDENT_PREREQUISITES",
        }
        sources.append(src2)
        models.extend([
            {
                "comparison_group_id": src2["comparison_group_id"],
                "model_id": "common_inheritance",
                "source_module": src2["source_module"],
                "source_version": src2["source_version"],
                "assumptions": ["candidate explanation"],
                "observed_data_refs": ["derived:language_contact:comparison_ledger"],
                "simulator_status": "UNRESOLVED",
                "pointwise_log_likelihood_status": "UNRESOLVED",
                "likelihood_status": "UNRESOLVED",
            },
            {
                "comparison_group_id": src2["comparison_group_id"],
                "model_id": "independent_convergence",
                "source_module": src2["source_module"],
                "source_version": src2["source_version"],
                "assumptions": ["candidate explanation"],
                "observed_data_refs": ["derived:language_contact:comparison_ledger"],
                "simulator_status": "UNRESOLVED",
                "pointwise_log_likelihood_status": "UNRESOLVED",
                "likelihood_status": "UNRESOLVED",
            },
        ])
    return _base(
        "m15a_model_provenance",
        "15_model_comparison_ppc",
        "deadworlds-model-comparison-ppc-v1.0.0",
        "model_comparison_ppc_publication_v1",
        {"candidateModels": models, "candidateSources": sources},
    )


def test_v09_recipes_are_registered():
    recipes = set(supported_recipes())
    assert "m12a_trait_coding_provenance" in recipes
    assert "m15a_model_provenance" in recipes


def test_m12_validates_and_renders_two_static_tables():
    spec = _m12()
    validate_figure_spec(spec)
    plans = plans_for_spec(spec)
    assert len(plans) == 2
    assert all(plan.kind == "table" for plan in plans)
    assert plans[1].table_rows[0][0] == "forge:find:F1"
    assert "never social or transmission relationships" in plans[1].note


def test_m12_unknown_state_rejected():
    spec = _m12()
    spec["data"]["bindings"]["traitAssignments"][0]["trait_state"] = "spiral"
    with pytest.raises(FigureSpecError, match="UNLICENSED_STATE"):
        validate_figure_spec(spec)


def test_m12_orphan_family_rejected():
    spec = _m12()
    spec["data"]["bindings"]["traitAssignments"][0]["trait_family"] = "other"
    with pytest.raises(FigureSpecError, match="ORPHAN_ASSIGNMENT"):
        validate_figure_spec(spec)


def test_m12_interpretive_text_rejected():
    spec = _m12()
    spec["data"]["bindings"]["codingRules"][0]["coding_basis"] = "ritual prestige marker"
    with pytest.raises(FigureSpecError, match="INTERPRETIVE_TEXT"):
        validate_figure_spec(spec)


def test_m12_unreviewed_nested_field_rejected():
    spec = _m12()
    spec["data"]["bindings"]["traitAssignments"][0]["confidence"] = 0.8
    with pytest.raises(FigureSpecError, match="unreviewed"):
        validate_figure_spec(spec)


def test_m12_unused_rule_rejected():
    spec = _m12()
    spec["data"]["bindings"]["codingRules"].append({
        "trait_family": "groove",
        "observation_dimension": "visible groove count",
        "state_labels": ["single", "multiple"],
        "coding_basis": "direct visible count",
        "functional_constraint_status": "UNRESOLVED",
    })
    with pytest.raises(FigureSpecError, match="UNUSED_OR_MISSING_CODING_RULE"):
        validate_figure_spec(spec)


def test_m15_validates_and_renders_one_table_per_group():
    spec = _m15(two_groups=True)
    validate_figure_spec(spec)
    plans = plans_for_spec(spec)
    assert len(plans) == 2
    assert all(plan.kind == "table" for plan in plans)
    assert all("not ranked" in plan.note for plan in plans)
    assert all(len({row[1] for row in plan.table_rows}) == 1 for plan in plans)


def test_m15_cross_group_model_rejected():
    spec = _m15()
    spec["data"]["bindings"]["candidateModels"][0]["comparison_group_id"] = "other"
    with pytest.raises(FigureSpecError, match="ORPHAN_MODEL"):
        validate_figure_spec(spec)


def test_m15_source_mismatch_rejected():
    spec = _m15()
    spec["data"]["bindings"]["candidateModels"][0]["source_module"] = "language_contact"
    with pytest.raises(FigureSpecError, match="SOURCE_MISMATCH"):
        validate_figure_spec(spec)


def test_m15_winner_semantic_rejected():
    spec = _m15()
    spec["data"]["bindings"]["candidateModels"][0]["assumptions"] = ["preferred winner"]
    with pytest.raises(FigureSpecError, match="RESULT_SEMANTIC"):
        validate_figure_spec(spec)


def test_m15_truth_probability_field_rejected():
    spec = _m15()
    spec["data"]["bindings"]["candidateModels"][0]["truth_probability"] = 0.9
    with pytest.raises(FigureSpecError, match="unlicensed/hidden|unreviewed"):
        validate_figure_spec(spec)


def test_m15_group_requires_two_candidates():
    spec = _m15()
    spec["data"]["bindings"]["candidateModels"] = spec["data"]["bindings"]["candidateModels"][:1]
    with pytest.raises(FigureSpecError, match="TWO_CANDIDATES"):
        validate_figure_spec(spec)


def test_m15_unreviewed_rank_field_rejected():
    spec = _m15()
    spec["data"]["bindings"]["candidateModels"][0]["rank"] = 1
    with pytest.raises(FigureSpecError, match="unreviewed"):
        validate_figure_spec(spec)


def test_m15_source_without_models_rejected():
    spec = _m15()
    spec["data"]["bindings"]["candidateSources"].append({
        "comparison_group_id": "language_contact:v1:1",
        "source_module": "language_contact",
        "source_version": "deadworlds-language-contact-v1.0.0",
        "source_rule": "RECOVERED_CORPORA_PLUS_INDEPENDENT_PREREQUISITES",
    })
    with pytest.raises(FigureSpecError, match="GROUP_SET_MISMATCH"):
        validate_figure_spec(spec)
