from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .errors import FigureSpecError


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


def _norm(key: str) -> str:
    # Preserve semantic word boundaries for both snake_case and camelCase
    # FigureSpec bindings before applying firewall key checks.
    key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


_M09 = {
    "m09_recovered_site_map",
    "m09_pairwise_distance_matrix",
    "m09_sampling_and_recovery_context",
    "m09_spatial_inference_prerequisite_matrix",
}
_M11 = {
    "m11a_proxy_concordance_matrix",
    "m11a_population_inference_prerequisites",
    "m11a_demographic_inference_ladder",
}
_M13 = {
    "m13a_corpus_readiness",
    "m13a_alternative_explanation_matrix",
    "m13a_direction_identifiability",
    "m13a_comparison_provenance",
}
_M14 = {
    "m14a_mark_inventory",
    "m14a_sequence_reading_order",
    "m14a_decipherment_prerequisite_ladder",
    "m14a_model_handoff",
}


def _validate_m09(spec: dict[str, Any]) -> None:
    b = spec["data"]["bindings"]
    forbidden = re.compile(
        r"^(?:cluster_result|ripley_result|viewshed_result|least_cost_path_result|"
        r"network_result|interaction_result|exchange_network|social_network|route_result|"
        r"ancient_settlement_density|settlement_hierarchy_result)$"
    )
    for path, key, value in _walk(b):
        if forbidden.match(_norm(key)) and value is not None:
            raise FigureSpecError(f"MODULE9_UNLICENSED_SPATIAL_INFERENCE: {path}")

    if spec["recipe_id"] == "m09_recovered_site_map":
        sites = b.get("georeferencedSites") or []
        if not sites:
            raise FigureSpecError("Module 9 recovered-site map has no georeferenced sites")
        for i, site in enumerate(sites):
            frame = site.get("frame")
            if frame == "LOCAL_SURVEY_GRID":
                if site.get("latitudeDeg") is not None or site.get("longitudeDeg") is not None:
                    raise FigureSpecError(f"MODULE9_FAKE_PLANET_COORDINATES: georeferencedSites[{i}]")
            elif frame == "PLANETOCENTRIC_LAT_LON":
                if site.get("xM") is not None or site.get("yM") is not None or site.get("zM") is not None:
                    raise FigureSpecError(f"MODULE9_MIXED_COORDINATE_FRAME: georeferencedSites[{i}]")
            else:
                raise FigureSpecError(f"MODULE9_UNSUPPORTED_COORDINATE_FRAME: georeferencedSites[{i}]")

    if spec["recipe_id"] == "m09_sampling_and_recovery_context":
        density = b.get("observedSiteDensityPerKm2")
        if density is not None and (isinstance(density, bool) or not isinstance(density, (int, float)) or density < 0):
            raise FigureSpecError("Module 9 recovered-site density must be nonnegative when present")


def _validate_m11(spec: dict[str, Any]) -> None:
    b = spec["data"]["bindings"]
    if b.get("populationResult") is not None:
        raise FigureSpecError("Module 11 hosted figures may not contain a numeric population result")
    if spec["recipe_id"] == "m11a_settlement_proxy_by_phase":
        raise FigureSpecError("Module 11 settlement-proxy posterior remains blocked until chronology/sampling uncertainty is propagated")
    for path, key, value in _walk(b):
        normalized = _norm(key)
        if normalized in {
            "hiddenpopulation", "hidden_population", "household_size_assumption",
            "human_density_constant", "earth_radiocarbon_calibration",
            "population_estimate", "population_posterior", "growth_rate_result",
        } and value is not None:
            raise FigureSpecError(f"MODULE11_UNLICENSED_POPULATION_INFERENCE: {path}")
    for i, proxy in enumerate(b.get("proxyLedger") or []):
        if proxy.get("populationConversionLicensed") is True:
            raise FigureSpecError(f"MODULE11_PROXY_TO_POPULATION_FORBIDDEN: proxyLedger[{i}]")


def _validate_m13(spec: dict[str, Any]) -> None:
    b = spec["data"]["bindings"]
    if b.get("modelComparisonResult") is not None:
        raise FigureSpecError("Module 13 may not contain a model-comparison result")
    if b.get("directionResult") is not None:
        raise FigureSpecError("Module 13 may not contain a donor/recipient direction result")
    forbidden = re.compile(
        r"^(?:borrowing_probability|contact_probability|donor_assignment|recipient_assignment|"
        r"contact_edge|social_network_edge|bilingualism_rate|semantic_meaning|preferred_model|winner_model)$"
    )
    for path, key, value in _walk(b):
        if forbidden.match(_norm(key)) and value is not None:
            raise FigureSpecError(f"MODULE13_UNLICENSED_CONTACT_RESULT: {path}")


def _validate_m14(spec: dict[str, Any]) -> None:
    b = spec["data"]["bindings"]
    forbidden = re.compile(
        r"^(?:decoded_mapping|deciphered_mapping|translation|gloss|phonetic_value|semantic_value|"
        r"sign_value|preferred_model|winner_model|reading_result|script_classification_result)$"
    )
    for path, key, value in _walk(b):
        if forbidden.match(_norm(key)) and value is not None:
            raise FigureSpecError(f"MODULE14_PREMATURE_DECIPHERMENT_RESULT: {path}")


def validate_module_09_11_13_14(spec: dict[str, Any]) -> None:
    recipe = spec.get("recipe_id")
    if recipe in _M09:
        _validate_m09(spec)
    elif recipe in _M11:
        _validate_m11(spec)
    elif recipe in _M13:
        _validate_m13(spec)
    elif recipe in _M14:
        _validate_m14(spec)
