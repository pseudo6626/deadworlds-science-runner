from __future__ import annotations

import copy
import pytest

from deadworlds_figures.adapters import plans_for_spec, supported_recipes
from deadworlds_figures.errors import FigureSpecError
from deadworlds_figures.validate import validate_figure_spec


def base(recipe: str, module: str, version: str, style: str) -> dict:
    return {
        'spec_version': 'deadworlds-figure-spec-v1',
        'figure_id': f'{module}:{recipe}:fixture',
        'module_id': module,
        'module_version': version,
        'recipe_id': recipe,
        'title': recipe,
        'purpose': 'v0.8 renderer regression fixture',
        'dimensionality': '2d',
        'renderer': {'preferred': 'matplotlib', 'fallbacks': ['plotly'], 'style_profile': style},
        'data': {'source_kind': 'derived_evidence', 'bindings': {}, 'units_policy': 'explicit_si_or_domain_standard'},
        'axes': {'units_policy': 'explicit_si_or_domain_standard'},
        'uncertainty': {'representation': 'categorical_status', 'meaning': 'status only'},
        'epistemics': {'method_ids': ['fixture'], 'assumptions': [], 'blocked_if': [], 'precision_policy': 'never_exceed_source_precision'},
        'outputs': ['svg', 'png', 'csv', 'json'],
        'provenance': {'renderer_version_required': True, 'module_run_id_required': True, 'source_refs_required': True, 'module_run_id': '80000000-0000-4000-8000-000000000001', 'source_refs': ['fixture:v08:public-evidence']},
    }


def m7(recipe: str) -> dict:
    s = base(recipe, '07_extinction_selectivity', 'deadworlds-extinction-selectivity-v1.0.0', 'extinction_selectivity_publication_v1')
    if recipe == 'm07_driver_trait_identifiability':
        s['data']['bindings'] = {
            'driverTraitReadiness': [
                {'candidateDriverClass': 'temperature_shift', 'publicEnvironmentalEvidenceStatus': 'RECOVERED_HISTORY_PROXY_PRESENT_CAUSAL_ROLE_UNRESOLVED', 'evidenceRefs': ['forge:atmosphere:A1'], 'requiredTraitClasses': ['thermal_tolerance'], 'vulnerabilityTraitStatus': 'RECOVERED_BODY_EVIDENCE_PRESENT_NO_CALIBRATED_VULNERABILITY_TRAITS', 'causalRole': 'UNASSIGNED_FROM_PUBLIC_EVIDENCE', 'riskDirection': 'UNASSIGNED', 'selectivityMagnitude': None},
                {'candidateDriverClass': 'resource_base_collapse', 'publicEnvironmentalEvidenceStatus': 'NO_PUBLIC_DRIVER_EVIDENCE', 'evidenceRefs': [], 'requiredTraitClasses': ['resource_dependency'], 'vulnerabilityTraitStatus': 'RECOVERED_BODY_EVIDENCE_PRESENT_NO_CALIBRATED_VULNERABILITY_TRAITS', 'causalRole': 'UNASSIGNED_FROM_PUBLIC_EVIDENCE', 'riskDirection': 'UNASSIGNED', 'selectivityMagnitude': None},
            ],
            'recoveredContext': {'biofossilRecordCount': 1, 'samplingLimitCount': 1},
            'eventDriverResult': None,
            'extinctionRiskResult': None,
        }
    elif recipe == 'm07_primary_secondary_dependency':
        s['data']['bindings'] = {
            'dependencyReadiness': [
                {'pathway': 'primary_environmental_selectivity', 'status': 'PREREQUISITES_PARTIAL_CAUSAL_ATTRIBUTION_UNRESOLVED', 'prerequisites': ['environmental history', 'body evidence', 'chronology'], 'evidenceRefs': ['forge:biofossil:BF-1'], 'causalResult': None, 'magnitude': None},
                {'pathway': 'secondary_network_mediated_extinction', 'status': 'BLOCKED_WITHOUT_EXPLICIT_INTERACTION_NETWORK', 'prerequisites': ['recovered interaction network'], 'evidenceRefs': [], 'causalResult': None, 'magnitude': None},
            ],
            'interactionNetworkResult': None,
            'causalAttributionResult': None,
        }
    else:
        raise ValueError(recipe)
    return s


def m8(recipe: str) -> dict:
    s = base(recipe, '08_trace_fossils_ichnology', 'deadworlds-trace-fossils-v1.0.0', 'ichnology_publication_v1')
    trace = {'evidenceRef': 'forge:ichno:TR-1', 'traceId': 'TR-1', 'licenseId': 'ichno:trace_1', 'traceClass': 'locomotion_surface_or_subsurface_trace', 'morphologyObservation': 'paired impressions', 'preservationMode': 'epichnia_or_epirelief', 'substrateContext': 'fine substrate', 'crosscuttingRelationships': [], 'behavioralHypotheses': ['repichnia'], 'tracemakerAffinity': 'UNRESOLVED_WITHOUT_INDEPENDENT_BODY_TRACE_ASSOCIATION', 'preservationBias': 'partial exposure', 'reliability': 0.7}
    lic = {'licenseId': 'ichno:trace_1', 'allowedObservationClass': 'locomotion_surface_or_subsurface_trace', 'allowedBehaviorClasses': ['repichnia'], 'specificity': 'GENERIC_BEHAVIORAL_MORPHOLOGY_ONLY'}
    if recipe == 'm08_behavior_trace_license_matrix':
        s['data']['bindings'] = {'recoveredTraceLedger': [trace], 'usedLicenseLedger': [lic], 'tracemakerResult': None, 'exactBehaviorResult': None}
    elif recipe == 'm08_preservation_gate_matrix':
        s['data']['bindings'] = {'preservationGates': [{'gate': 'recovered_trace_observation', 'status': 'RECOVERED_TRACE_PRESENT'}, {'gate': 'exposure_and_sampling', 'status': 'QUALITATIVE_SAMPLING_CONTEXT_PRESENT'}], 'samplingContext': {'samplingLimits': ['partial exposure'], 'surveyContext': {'survey_design': 'TARGETED', 'coverage_completeness': 'PARTIAL', 'detection_model_status': 'QUALITATIVE_ONLY'}}, 'fossilizationProbability': None}
    elif recipe == 'm08_ethological_ambiguity_graph':
        s['data']['bindings'] = {'ambiguityLedger': [{'evidenceRef': trace['evidenceRef'], 'traceId': 'TR-1', 'traceClass': trace['traceClass'], 'allowedBehaviorHypotheses': ['repichnia'], 'ambiguityStatus': 'HYPOTHESIS_SET_NOT_IDENTITY', 'exactBehaviorResult': None, 'tracemakerResult': None}], 'exactBehaviorResult': None, 'tracemakerResult': None}
    elif recipe == 'm08_ichnological_inference_ladder':
        s['data']['bindings'] = {'inferenceLadder': [{'level': 'recovered_morphology', 'status': 'OBSERVED'}, {'level': 'generic_trace_class', 'status': 'LICENSED_FOR_RECOVERED_TRACE'}, {'level': 'behavioral_interpretation', 'status': 'HYPOTHESIS_ONLY'}, {'level': 'tracemaker_identity', 'status': 'BLOCKED_WITHOUT_INDEPENDENT_BODY_TRACE_ASSOCIATION'}, {'level': 'ichnofacies', 'status': 'BLOCKED_WITHOUT_RECOVERED_ASSEMBLAGE_AND_INDEPENDENT_SEDIMENTOLOGY'}, {'level': 'behavior_absence_from_non_detection', 'status': 'PROHIBITED'}], 'ichnofaciesResult': None, 'tracemakerResult': None}
    else:
        raise ValueError(recipe)
    return s


@pytest.mark.parametrize('recipe', ['m07_driver_trait_identifiability', 'm07_primary_secondary_dependency'])
def test_m7_safe_recipes(recipe):
    s=m7(recipe); validate_figure_spec(s); assert plans_for_spec(s)

@pytest.mark.parametrize('recipe', ['m08_behavior_trace_license_matrix','m08_preservation_gate_matrix','m08_ethological_ambiguity_graph','m08_ichnological_inference_ladder'])
def test_m8_safe_recipes(recipe):
    s=m8(recipe); validate_figure_spec(s); assert plans_for_spec(s)


def test_m7_hidden_clade_camelcase_rejected():
    s=m7('m07_driver_trait_identifiability'); s['data']['bindings']['cladeId']='hidden'
    with pytest.raises(FigureSpecError, match='HIDDEN_TRUTH'): validate_figure_spec(s)


def test_m7_risk_direction_rejected():
    s=m7('m07_driver_trait_identifiability'); s['data']['bindings']['driverTraitReadiness'][0]['riskDirection']='HIGHER_RISK'
    with pytest.raises(FigureSpecError, match='RISK_DIRECTION'): validate_figure_spec(s)


def test_m7_secondary_network_must_stay_blocked():
    s=m7('m07_primary_secondary_dependency'); s['data']['bindings']['dependencyReadiness'][1]['status']='SUPPORTED'
    with pytest.raises(FigureSpecError, match='SECONDARY_NETWORK'): validate_figure_spec(s)


def test_m7_unsafe_recipes_not_registered():
    assert 'm07_clade_constraint_matrix' not in supported_recipes()
    assert 'm07_lineage_continuity_status' not in supported_recipes()


def test_m8_unused_license_rejected():
    s=m8('m08_behavior_trace_license_matrix'); s['data']['bindings']['usedLicenseLedger'].append({'licenseId':'unused','allowedObservationClass':'x','allowedBehaviorClasses':[]})
    with pytest.raises(FigureSpecError, match='UNUSED_LICENSE'): validate_figure_spec(s)


def test_m8_resolved_tracemaker_rejected():
    s=m8('m08_behavior_trace_license_matrix'); s['data']['bindings']['recoveredTraceLedger'][0]['tracemakerAffinity']='walker'
    with pytest.raises(FigureSpecError, match='TRACEMAKER'): validate_figure_spec(s)


def test_m8_hidden_candidate_trace_classes_rejected():
    s=m8('m08_preservation_gate_matrix'); s['data']['bindings']['candidateTraceClasses']=[{'cladeId':'walker'}]
    with pytest.raises(FigureSpecError, match='HIDDEN_TRUTH'): validate_figure_spec(s)


def test_m8_ichnotaxon_rejected():
    s=m8('m08_ethological_ambiguity_graph'); s['data']['bindings']['ambiguityLedger'][0]['traceClass']='Cruziana'
    with pytest.raises(FigureSpecError, match='ICHNOTAXON'): validate_figure_spec(s)


def test_m8_non_detection_cannot_be_absence():
    s=m8('m08_ichnological_inference_ladder'); s['data']['bindings']['inferenceLadder'][-1]['status']='ABSENT'
    with pytest.raises(FigureSpecError, match='NONDETECTION'): validate_figure_spec(s)


def test_m8_ambiguity_static_fallback_is_edge_table_not_graph_geometry():
    s=m8('m08_ethological_ambiguity_graph'); p=plans_for_spec(s)[0]
    assert p.kind=='table'
    assert 'compatibility edge' in p.note
    assert all('x' not in row and 'y' not in row for row in p.csv_rows)
