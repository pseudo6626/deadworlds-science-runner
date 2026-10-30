from __future__ import annotations

import math
from pathlib import Path

import pytest

from deadworlds_figures.adapters import plans_for_spec, supported_recipes
from deadworlds_figures.errors import FigureSpecError
from deadworlds_figures.render import render_figure_spec
from deadworlds_figures.validate import validate_figure_spec

M4 = {
    "m04_gravity_jump_sensitivity",
    "m04_froude_similarity_grid",
    "m04_dynamic_pressure_grid",
    "m04_terminal_velocity_grid",
    "m04_lift_loading_grid",
    "m04_self_weight_support_scaling",
}
M5 = {
    "m05_stellar_emission_peak_context",
    "m05_acoustic_sound_speed_sensitivity",
    "m05_diffraction_resolution_sensitivity",
    "m05_channel_identifiability",
}
M6 = {
    "m06_channel_identifiability_matrix",
    "m06_visual_angular_geometry_sensitivity",
    "m06_sender_medium_receiver_prerequisites",
    "m06_multimodal_constraint_map",
}
ALL_M456 = M4 | M5 | M6


def _spec(recipe: str, bindings: dict) -> dict:
    if recipe in M4:
        module_id = "04_biomechanics_scaling"
        module_version = "deadworlds-biomechanics-scaling-v1.0.0"
        style = "biomechanics_publication_v1"
        source_kind = "deterministic_diagnostic"
        method_ids = ["dynamic-similarity-alexander-jayes-1983"]
        uncertainty = "sensitivity_grid"
    elif recipe in M5:
        module_id = "05_sensory_ecology"
        module_version = "deadworlds-sensory-ecology-v1.0.0"
        style = "sensory_ecology_publication_v1"
        source_kind = "derived_evidence" if recipe == "m05_channel_identifiability" else "deterministic_diagnostic"
        method_ids = ["sensory-drive-endler-1992"]
        uncertainty = "categorical_status" if recipe in {"m05_stellar_emission_peak_context", "m05_channel_identifiability"} else "sensitivity_grid"
    else:
        module_id = "06_non_acoustic_communication"
        module_version = "deadworlds-nonacoustic-communication-v1.0.1"
        style = "communication_ecology_publication_v1"
        source_kind = "derived_evidence" if recipe == "m06_multimodal_constraint_map" else "deterministic_diagnostic"
        method_ids = ["vibrational-communication-cocroft-rodriguez-2005"]
        uncertainty = "sensitivity_grid" if recipe == "m06_visual_angular_geometry_sensitivity" else "categorical_status"
    return {
        "spec_version": "deadworlds-figure-spec-v1",
        "figure_id": f"{module_id}:{recipe}:fixture",
        "module_id": module_id,
        "module_version": module_version,
        "recipe_id": recipe,
        "title": recipe,
        "purpose": "Module 4-6 deterministic hosted-renderer regression fixture.",
        "dimensionality": "2d",
        "renderer": {"preferred": "matplotlib", "fallbacks": ["plotly"], "style_profile": style},
        "data": {"source_kind": source_kind, "bindings": bindings, "units_policy": "explicit_si_or_domain_standard"},
        "axes": {"units_policy": "explicit_si_or_domain_standard"},
        "uncertainty": {"representation": uncertainty, "meaning": "Regression fixture preserving live Forge epistemic semantics."},
        "epistemics": {"method_ids": method_ids, "assumptions": ["Regression fixture only."], "blocked_if": [], "precision_policy": "never_exceed_source_precision"},
        "outputs": ["json"],
        "provenance": {
            "renderer_version_required": True,
            "module_run_id_required": True,
            "source_refs_required": True,
            "module_run_id": "60000000-0000-4000-8000-000000000456",
            "source_refs": [f"fixture:{module_id}:{recipe}"],
        },
    }


def _m4() -> dict[str, dict]:
    g, rho = 3.28226386, 0.02346794
    jump = [{"launchSpeedMS": v, "verticalHeightM": v*v/(2*g), "hangTimeS": 2*v/g, "vacuumRange45degM": v*v/g} for v in [0.5,1,2,5,10]]
    froude = [{"characteristicLengthM": L, "speedMS": v, "froude": v*v/(g*L)} for L in [0.01,0.1,1,10,100] for v in [0.1,0.5,1,2,5,10]]
    dp = [{"speedMS": v, "dynamicPressurePa": 0.5*rho*v*v} for v in [0.25,0.5,1,2,5,10,20,50]]
    terminal = [{"ballisticCoefficientKgM2": beta, "terminalVelocityMS": math.sqrt(2*beta*g/rho)} for beta in [0.1,1,10,100,1000]]
    lift = [{"speedMS": v, "assumedLiftCoefficient": cl, "weightPerAreaPa": 0.5*rho*v*v*cl} for v in [1,2,5,10,20,50] for cl in [0.5,1,1.5,2]]
    self_weight = [{"assumedBulkDensityKgM3": rb, "characteristicHeightM": L, "axialSelfWeightStressPa": rb*g*L} for rb in [100,1000,10000] for L in [0.01,0.1,1,10,100]]
    return {
        "m04_gravity_jump_sensitivity": {"gravityMS2": g, "jumpSensitivity": jump, "actualLaunchSpeedMS": None, "actualLocomotorPowerW": None},
        "m04_froude_similarity_grid": {"gravityMS2": g, "froudeSensitivity": froude, "actualCharacteristicLengthM": None, "actualSpeedMS": None, "gaitTransitionResult": None},
        "m04_dynamic_pressure_grid": {"presentAtmosphereDensityKgM3": rho, "presentAtmosphereScope": "PRESENT_STATE_ONLY", "biosphereEraGasDensityKgM3": None, "dynamicPressureSensitivity": dp},
        "m04_terminal_velocity_grid": {"gravityMS2": g, "presentAtmosphereDensityKgM3": rho, "presentAtmosphereScope": "PRESENT_STATE_ONLY", "biosphereEraGasDensityKgM3": None, "actualBallisticCoefficientKgM2": None, "terminalVelocitySensitivity": terminal},
        "m04_lift_loading_grid": {"presentAtmosphereDensityKgM3": rho, "presentAtmosphereScope": "PRESENT_STATE_ONLY", "biosphereEraGasDensityKgM3": None, "flightFeasibilityResult": None, "organismWingLoadingResult": None, "liftLoadingSensitivity": lift},
        "m04_self_weight_support_scaling": {"gravityMS2": g, "materialStrengthPa": None, "failureSizeLimitM": None, "selfWeightStressSensitivity": self_weight},
    }


def _m5() -> dict[str, dict]:
    peaks = [
        {"starBodyId": 0, "relation": "ancestral_star", "temperatureK": 7993, "peakWavelengthNm": 2897771.955/7993, "bolometricContributionSearth": 0.38},
        {"starBodyId": 27, "relation": "immediate_host", "temperatureK": 279, "peakWavelengthNm": 2897771.955/279, "bolometricContributionSearth": 0.0003},
    ]
    k = 8.314462618*200/0.028
    sound = [{"assumedHeatCapacityRatio": gamma, "soundSpeedMS": math.sqrt(gamma*k)} for gamma in [1.1,1.2,1.3,1.4,1.67]]
    diffraction = []
    for wavelength in [0.3,0.5,1,5,10,20]:
        for aperture in [0.001,0.01,0.1,1]:
            rad = 1.22*(wavelength*1e-6)/aperture
            diffraction.append({"wavelengthUm": wavelength, "apertureM": aperture, "angularResolutionRad": rad, "angularResolutionDeg": rad*180/math.pi})
    channels = [{"channel": c, "presentStatus": "CONTEXT_ONLY", "constraint": "Quantitative performance unresolved."} for c in ["photic","gas_pressure_acoustic","substrate_vibration","chemical","mechanoflow","thermal_radiation","electric","magnetic"]]
    blocked = [{"quantity": "actual_visual_acuity", "reason": "Required receptor and scene data unresolved."}]
    return {
        "m05_stellar_emission_peak_context": {"stellarSpectralPeaks": peaks, "surfaceSpectralIrradiance": None, "receptorOptimumWavelength": None},
        "m05_acoustic_sound_speed_sensitivity": {"presentEnvironment": {"surfaceTemperatureK": 200}, "acousticSoundSpeedSensitivity": sound, "biosphereEraSoundSpeed": None, "attenuationResult": None, "activeSpaceResult": None},
        "m05_diffraction_resolution_sensitivity": {"diffractionSensitivity": diffraction, "actualApertureM": None, "actualReceptorBand": None, "actualVisualAcuity": None},
        "m05_channel_identifiability": {"channelConstraints": channels, "blockedCalculations": blocked, "evolvedSensoryModalityPrevalence": None, "channelImportanceRanking": None},
    }


def _public_ledger() -> list[dict]:
    channels = ["visual_reflective_or_gesture","active_optical","chemical","substrate_vibration","tactile_contact","fluid_motion","thermal_pattern","electric","active_magnetic"]
    return [{
        "channel": c,
        "carrierStatus": "PHYSICAL_CONTEXT_ONLY",
        "senderPrerequisiteStatus": "UNRESOLVED_FROM_PUBLIC_EVIDENCE",
        "receiverPrerequisiteStatus": "UNRESOLVED_FROM_PUBLIC_EVIDENCE",
        "quantitativeRangeStatus": "BLOCKED_WITHOUT_CHANNEL_SPECIFIC_TRANSMISSION_AND_THRESHOLD_DATA",
        "informationCapacityStatus": "BLOCKED_WITHOUT_SIGNAL_NOISE_AND_RECEIVER_DATA",
        "constraint": "Carrier context only; biological prerequisites unresolved.",
        "status": "BLOCKED_BY_MODULE_V1_POLICY" if c == "active_magnetic" else "PHYSICAL_CARRIER_CONTEXT_ONLY_BIOLOGICAL_PREREQUISITES_UNRESOLVED",
    } for c in channels]


def _m6() -> dict[str, dict]:
    ledger = _public_ledger()
    visual = []
    for size in [0.01,0.1,1,10]:
        for distance in [0.1,1,10,100,1000]:
            rad = 2*math.atan(size/(2*distance))
            visual.append({"assumedDisplaySizeM": size, "assumedDistanceM": distance, "angularSizeRad": rad, "angularSizeDeg": rad*180/math.pi})
    blocked = [{"quantity": "visual_signal_active_space", "reason": "Surface spectrum and receptor performance unresolved."}]
    return {
        "m06_channel_identifiability_matrix": {"channelLedger": ledger},
        "m06_visual_angular_geometry_sensitivity": {"visualAngularSizeSensitivity": visual, "visibilityResult": None, "acuityResult": None, "communicationRangeResult": None},
        "m06_sender_medium_receiver_prerequisites": {"channelLedger": ledger},
        "m06_multimodal_constraint_map": {"channelLedger": ledger, "blockedCalculations": blocked, "channelRanking": None, "evolvedPreference": None},
    }


FIXTURES = {**_m4(), **_m5(), **_m6()}


def test_modules_04_06_all_registered():
    assert ALL_M456.issubset(set(supported_recipes()))
    assert len(ALL_M456) == 14


@pytest.mark.parametrize("recipe", sorted(FIXTURES))
def test_modules_04_06_validate_plan_and_render(recipe: str, tmp_path: Path):
    spec = _spec(recipe, FIXTURES[recipe])
    assert validate_figure_spec(spec)["recipe_id"] == recipe
    plans = plans_for_spec(spec)
    assert plans and all(plan.note for plan in plans)
    manifest = render_figure_spec(spec, tmp_path / recipe)
    assert manifest["renderer_version"] == "deadworlds-figure-renderer-v0.9.0"
    assert manifest["recipe_id"] == recipe
    assert manifest["components"]
    assert manifest["warnings"] == []
    assert manifest["scientific_rendering_policy"]["llm_numeric_plot_data_allowed"] is False


def test_module4_present_atmosphere_cannot_be_paleo_substitute():
    bindings = dict(FIXTURES["m04_dynamic_pressure_grid"])
    bindings["biosphereEraGasDensityKgM3"] = bindings["presentAtmosphereDensityKgM3"]
    with pytest.raises(FigureSpecError, match="BIOSPHERE_ERA|biosphere-era"):
        validate_figure_spec(_spec("m04_dynamic_pressure_grid", bindings))


def test_module4_lift_grid_cannot_become_flight_feasibility():
    bindings = dict(FIXTURES["m04_lift_loading_grid"])
    bindings["flightFeasibilityResult"] = "possible"
    with pytest.raises(FigureSpecError, match="FLIGHT"):
        validate_figure_spec(_spec("m04_lift_loading_grid", bindings))


def test_module5_diffraction_cannot_become_actual_acuity():
    bindings = dict(FIXTURES["m05_diffraction_resolution_sensitivity"])
    bindings["actualVisualAcuity"] = 0.01
    with pytest.raises(FigureSpecError, match="ACUITY"):
        validate_figure_spec(_spec("m05_diffraction_resolution_sensitivity", bindings))


def test_module6_hidden_raw_ledger_is_rejected():
    bad = dict(_public_ledger()[0])
    bad["receiverStatus"] = "RECEPTOR_HYPOTHESIS_PRESENT"
    with pytest.raises(FigureSpecError, match="HIDDEN|RAW_HIDDEN"):
        validate_figure_spec(_spec("m06_channel_identifiability_matrix", {"channelLedger": [bad]}))


def test_module6_public_sender_receiver_prerequisites_remain_unresolved():
    bad = dict(_public_ledger()[0])
    bad["receiverPrerequisiteStatus"] = "RECEPTOR_PRESENT"
    with pytest.raises(FigureSpecError, match="RECEIVER_PREREQUISITE"):
        validate_figure_spec(_spec("m06_channel_identifiability_matrix", {"channelLedger": [bad]}))
