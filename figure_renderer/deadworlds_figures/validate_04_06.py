from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .errors import FigureSpecError


MODULE_04_RECIPES = {
    "m04_gravity_jump_sensitivity",
    "m04_froude_similarity_grid",
    "m04_dynamic_pressure_grid",
    "m04_terminal_velocity_grid",
    "m04_lift_loading_grid",
    "m04_self_weight_support_scaling",
}
MODULE_05_RECIPES = {
    "m05_stellar_emission_peak_context",
    "m05_acoustic_sound_speed_sensitivity",
    "m05_diffraction_resolution_sensitivity",
    "m05_channel_identifiability",
}
MODULE_06_RECIPES = {
    "m06_channel_identifiability_matrix",
    "m06_visual_angular_geometry_sensitivity",
    "m06_sender_medium_receiver_prerequisites",
    "m06_multimodal_constraint_map",
}

_HIDDEN_M6 = re.compile(
    r"RECEPTOR_HYPOTHESIS_PRESENT|LIGHT_PRODUCTION_HYPOTHESIS_PRESENT|"
    r"ELECTRIC_SIGNAL_PRODUCTION_HYPOTHESIS_PRESENT|HIDDEN_BIOLOGY",
    re.IGNORECASE,
)


def _walk(value: Any, path: str = ""):
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            yield child, str(key), item
            yield from _walk(item, child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            child = f"{path}[{index}]"
            yield from _walk(item, child)


def _numeric(value: Any, label: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FigureSpecError(f"{label} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise FigureSpecError(f"{label} must be finite")
    if positive and out <= 0:
        raise FigureSpecError(f"{label} must be positive")
    if nonnegative and out < 0:
        raise FigureSpecError(f"{label} must be nonnegative")
    return out


def _present_scope(bindings: dict[str, Any]) -> float:
    rho = _numeric(bindings.get("presentAtmosphereDensityKgM3"), "presentAtmosphereDensityKgM3", positive=True)
    if bindings.get("presentAtmosphereScope") != "PRESENT_STATE_ONLY":
        raise FigureSpecError("MODULE4_PRESENT_ATMOSPHERE_SCOPE_REQUIRED")
    if bindings.get("biosphereEraGasDensityKgM3") is not None:
        raise FigureSpecError("MODULE4_BIOSPHERE_ERA_DENSITY_SUBSTITUTION_FORBIDDEN")
    return rho


def _validate_m04(recipe: str, b: dict[str, Any]) -> None:
    if recipe == "m04_gravity_jump_sensitivity":
        g = _numeric(b.get("gravityMS2"), "gravityMS2", positive=True)
        if b.get("actualLaunchSpeedMS") is not None or b.get("actualLocomotorPowerW") is not None:
            raise FigureSpecError("MODULE4_JUMP_ORGANISM_PERFORMANCE_FORBIDDEN")
        rows = b.get("jumpSensitivity") or []
        if len(rows) < 2:
            raise FigureSpecError("MODULE4_JUMP_GRID_EMPTY")
        for row in rows:
            v = _numeric(row.get("launchSpeedMS"), "launchSpeedMS", positive=True)
            h = _numeric(row.get("verticalHeightM"), "verticalHeightM", nonnegative=True)
            t = _numeric(row.get("hangTimeS"), "hangTimeS", nonnegative=True)
            r = _numeric(row.get("vacuumRange45degM"), "vacuumRange45degM", nonnegative=True)
            if abs(h - v * v / (2 * g)) > max(1e-8, abs(h) * 2e-8):
                raise FigureSpecError("MODULE4_JUMP_FORMULA_MISMATCH")
            if abs(t - 2 * v / g) > max(1e-8, abs(t) * 2e-8):
                raise FigureSpecError("MODULE4_JUMP_FORMULA_MISMATCH")
            if abs(r - v * v / g) > max(1e-8, abs(r) * 2e-8):
                raise FigureSpecError("MODULE4_JUMP_FORMULA_MISMATCH")
        return

    if recipe == "m04_froude_similarity_grid":
        g = _numeric(b.get("gravityMS2"), "gravityMS2", positive=True)
        if b.get("actualCharacteristicLengthM") is not None or b.get("actualSpeedMS") is not None or b.get("gaitTransitionResult") is not None:
            raise FigureSpecError("MODULE4_FROUDE_ORGANISM_INFERENCE_FORBIDDEN")
        rows = b.get("froudeSensitivity") or []
        if not rows:
            raise FigureSpecError("MODULE4_FROUDE_GRID_EMPTY")
        for row in rows:
            length = _numeric(row.get("characteristicLengthM"), "characteristicLengthM", positive=True)
            speed = _numeric(row.get("speedMS"), "speedMS", positive=True)
            fr = _numeric(row.get("froude"), "froude", nonnegative=True)
            expected = speed * speed / (g * length)
            if abs(fr - expected) > max(1e-8, abs(expected) * 2e-8):
                raise FigureSpecError("MODULE4_FROUDE_FORMULA_MISMATCH")
        return

    if recipe == "m04_dynamic_pressure_grid":
        rho = _present_scope(b)
        rows = b.get("dynamicPressureSensitivity") or []
        if not rows:
            raise FigureSpecError("MODULE4_DYNAMIC_PRESSURE_GRID_EMPTY")
        for row in rows:
            speed = _numeric(row.get("speedMS"), "speedMS", positive=True)
            q = _numeric(row.get("dynamicPressurePa"), "dynamicPressurePa", nonnegative=True)
            expected = 0.5 * rho * speed * speed
            if abs(q - expected) > max(1e-8, abs(expected) * 2e-8):
                raise FigureSpecError("MODULE4_DYNAMIC_PRESSURE_FORMULA_MISMATCH")
        return

    if recipe == "m04_terminal_velocity_grid":
        rho = _present_scope(b)
        g = _numeric(b.get("gravityMS2"), "gravityMS2", positive=True)
        if b.get("actualBallisticCoefficientKgM2") is not None:
            raise FigureSpecError("MODULE4_ACTUAL_BALLISTIC_COEFFICIENT_FORBIDDEN")
        rows = b.get("terminalVelocitySensitivity") or []
        if not rows:
            raise FigureSpecError("MODULE4_TERMINAL_GRID_EMPTY")
        for row in rows:
            beta = _numeric(row.get("ballisticCoefficientKgM2"), "ballisticCoefficientKgM2", positive=True)
            vt = _numeric(row.get("terminalVelocityMS"), "terminalVelocityMS", positive=True)
            expected = math.sqrt(2 * beta * g / rho)
            if abs(vt - expected) > max(1e-8, abs(expected) * 2e-8):
                raise FigureSpecError("MODULE4_TERMINAL_FORMULA_MISMATCH")
        return

    if recipe == "m04_lift_loading_grid":
        rho = _present_scope(b)
        if b.get("flightFeasibilityResult") is not None or b.get("organismWingLoadingResult") is not None:
            raise FigureSpecError("MODULE4_FLIGHT_FEASIBILITY_FORBIDDEN")
        rows = b.get("liftLoadingSensitivity") or []
        if not rows:
            raise FigureSpecError("MODULE4_LIFT_GRID_EMPTY")
        for row in rows:
            speed = _numeric(row.get("speedMS"), "speedMS", positive=True)
            cl = _numeric(row.get("assumedLiftCoefficient"), "assumedLiftCoefficient", positive=True)
            loading = _numeric(row.get("weightPerAreaPa"), "weightPerAreaPa", nonnegative=True)
            expected = 0.5 * rho * speed * speed * cl
            if abs(loading - expected) > max(1e-8, abs(expected) * 2e-8):
                raise FigureSpecError("MODULE4_LIFT_FORMULA_MISMATCH")
        return

    if recipe == "m04_self_weight_support_scaling":
        g = _numeric(b.get("gravityMS2"), "gravityMS2", positive=True)
        if b.get("materialStrengthPa") is not None or b.get("failureSizeLimitM") is not None:
            raise FigureSpecError("MODULE4_MATERIAL_STRENGTH_OR_SIZE_LIMIT_FORBIDDEN")
        rows = b.get("selfWeightStressSensitivity") or []
        if not rows:
            raise FigureSpecError("MODULE4_SELF_WEIGHT_GRID_EMPTY")
        for row in rows:
            rho_body = _numeric(row.get("assumedBulkDensityKgM3"), "assumedBulkDensityKgM3", positive=True)
            length = _numeric(row.get("characteristicHeightM"), "characteristicHeightM", positive=True)
            stress = _numeric(row.get("axialSelfWeightStressPa"), "axialSelfWeightStressPa", nonnegative=True)
            expected = rho_body * g * length
            if abs(stress - expected) > max(1e-7, abs(expected) * 2e-8):
                raise FigureSpecError("MODULE4_SELF_WEIGHT_FORMULA_MISMATCH")


def _validate_m05(recipe: str, b: dict[str, Any]) -> None:
    if recipe == "m05_stellar_emission_peak_context":
        if b.get("surfaceSpectralIrradiance") is not None or b.get("receptorOptimumWavelength") is not None:
            raise FigureSpecError("MODULE5_SURFACE_SPECTRUM_OR_RECEPTOR_OPTIMUM_FORBIDDEN")
        rows = b.get("stellarSpectralPeaks") or []
        if not rows:
            raise FigureSpecError("MODULE5_STELLAR_PEAKS_EMPTY")
        for row in rows:
            temp = _numeric(row.get("temperatureK"), "temperatureK", positive=True)
            peak = _numeric(row.get("peakWavelengthNm"), "peakWavelengthNm", positive=True)
            expected = 2897771.955 / temp
            if abs(peak - expected) > max(1e-4, expected * 2e-7):
                raise FigureSpecError("MODULE5_WIEN_FORMULA_MISMATCH")
        return

    if recipe == "m05_acoustic_sound_speed_sensitivity":
        if b.get("biosphereEraSoundSpeed") is not None or b.get("attenuationResult") is not None or b.get("activeSpaceResult") is not None:
            raise FigureSpecError("MODULE5_ACOUSTIC_OVERCLAIM_FORBIDDEN")
        rows = b.get("acousticSoundSpeedSensitivity") or []
        if len(rows) < 2:
            raise FigureSpecError("MODULE5_SOUND_SPEED_GRID_EMPTY")
        invariant = None
        for row in rows:
            gamma = _numeric(row.get("assumedHeatCapacityRatio"), "assumedHeatCapacityRatio", positive=True)
            speed = _numeric(row.get("soundSpeedMS"), "soundSpeedMS", positive=True)
            k = speed * speed / gamma
            invariant = k if invariant is None else invariant
            if abs(k - invariant) > max(1e-5, abs(invariant) * 2e-7):
                raise FigureSpecError("MODULE5_SOUND_SPEED_GRID_INCONSISTENT")
        return

    if recipe == "m05_diffraction_resolution_sensitivity":
        if b.get("actualApertureM") is not None or b.get("actualReceptorBand") is not None or b.get("actualVisualAcuity") is not None:
            raise FigureSpecError("MODULE5_ACUITY_OR_RECEPTOR_INFERENCE_FORBIDDEN")
        rows = b.get("diffractionSensitivity") or []
        if not rows:
            raise FigureSpecError("MODULE5_DIFFRACTION_GRID_EMPTY")
        for row in rows:
            wavelength = _numeric(row.get("wavelengthUm"), "wavelengthUm", positive=True)
            aperture = _numeric(row.get("apertureM"), "apertureM", positive=True)
            rad = _numeric(row.get("angularResolutionRad"), "angularResolutionRad", positive=True)
            deg = _numeric(row.get("angularResolutionDeg"), "angularResolutionDeg", positive=True)
            expected = 1.22 * (wavelength * 1e-6) / aperture
            if abs(rad - expected) > max(2e-12, expected * 2e-7):
                raise FigureSpecError("MODULE5_DIFFRACTION_FORMULA_MISMATCH")
            if abs(deg - expected * 180 / math.pi) > max(2e-10, abs(deg) * 2e-7):
                raise FigureSpecError("MODULE5_DIFFRACTION_FORMULA_MISMATCH")
        return

    if recipe == "m05_channel_identifiability":
        if b.get("evolvedSensoryModalityPrevalence") is not None or b.get("channelImportanceRanking") is not None:
            raise FigureSpecError("MODULE5_SENSORY_PREVALENCE_OR_RANKING_FORBIDDEN")
        rows = b.get("channelConstraints") or []
        if not rows or any(not x.get("channel") or not x.get("presentStatus") for x in rows):
            raise FigureSpecError("MODULE5_CHANNEL_STATUS_INVALID")


def _validate_public_m6_ledger(b: dict[str, Any]) -> list[dict[str, Any]]:
    rows = b.get("channelLedger") or []
    if not rows:
        raise FigureSpecError("MODULE6_PUBLIC_LEDGER_EMPTY")
    if _HIDDEN_M6.search(str(rows)):
        raise FigureSpecError("MODULE6_HIDDEN_BIOLOGY_LEAK")
    for path, key, _ in _walk(rows):
        if key in {"receiverStatus", "senderStatus", "blocked"}:
            raise FigureSpecError(f"MODULE6_RAW_HIDDEN_LEDGER_FIELD_FORBIDDEN: {path}")
    for row in rows:
        if row.get("senderPrerequisiteStatus") != "UNRESOLVED_FROM_PUBLIC_EVIDENCE":
            raise FigureSpecError("MODULE6_SENDER_PREREQUISITE_MUST_REMAIN_UNRESOLVED")
        if row.get("receiverPrerequisiteStatus") != "UNRESOLVED_FROM_PUBLIC_EVIDENCE":
            raise FigureSpecError("MODULE6_RECEIVER_PREREQUISITE_MUST_REMAIN_UNRESOLVED")
        if not row.get("channel") or not row.get("carrierStatus") or not row.get("status"):
            raise FigureSpecError("MODULE6_PUBLIC_LEDGER_STATUS_INVALID")
    return rows


def _validate_m06(recipe: str, b: dict[str, Any]) -> None:
    if recipe == "m06_visual_angular_geometry_sensitivity":
        if b.get("visibilityResult") is not None or b.get("acuityResult") is not None or b.get("communicationRangeResult") is not None:
            raise FigureSpecError("MODULE6_VISIBILITY_ACUITY_RANGE_FORBIDDEN")
        rows = b.get("visualAngularSizeSensitivity") or []
        if not rows:
            raise FigureSpecError("MODULE6_VISUAL_GEOMETRY_GRID_EMPTY")
        for row in rows:
            size = _numeric(row.get("assumedDisplaySizeM"), "assumedDisplaySizeM", positive=True)
            distance = _numeric(row.get("assumedDistanceM"), "assumedDistanceM", positive=True)
            rad = _numeric(row.get("angularSizeRad"), "angularSizeRad", positive=True)
            deg = _numeric(row.get("angularSizeDeg"), "angularSizeDeg", positive=True)
            expected = 2 * math.atan(size / (2 * distance))
            if abs(rad - expected) > max(2e-12, expected * 2e-7):
                raise FigureSpecError("MODULE6_VISUAL_GEOMETRY_FORMULA_MISMATCH")
            if abs(deg - expected * 180 / math.pi) > max(2e-10, abs(deg) * 2e-7):
                raise FigureSpecError("MODULE6_VISUAL_GEOMETRY_FORMULA_MISMATCH")
        return

    rows = _validate_public_m6_ledger(b)
    if recipe == "m06_multimodal_constraint_map":
        if b.get("channelRanking") is not None or b.get("evolvedPreference") is not None:
            raise FigureSpecError("MODULE6_CHANNEL_RANKING_OR_PREFERENCE_FORBIDDEN")
        if not isinstance(b.get("blockedCalculations"), list):
            raise FigureSpecError("MODULE6_BLOCKED_LEDGER_REQUIRED")
    if recipe in {"m06_channel_identifiability_matrix", "m06_sender_medium_receiver_prerequisites"} and not rows:
        raise FigureSpecError("MODULE6_PUBLIC_LEDGER_EMPTY")


def validate_module_04_06(spec: dict[str, Any]) -> None:
    recipe = str(spec.get("recipe_id") or "")
    bindings = spec.get("data", {}).get("bindings", {})
    if recipe in MODULE_04_RECIPES:
        _validate_m04(recipe, bindings)
    elif recipe in MODULE_05_RECIPES:
        _validate_m05(recipe, bindings)
    elif recipe in MODULE_06_RECIPES:
        _validate_m06(recipe, bindings)
