from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .errors import FigureSpecError

_M7 = {
    "m07_driver_trait_identifiability",
    "m07_primary_secondary_dependency",
}
_M8 = {
    "m08_behavior_trace_license_matrix",
    "m08_preservation_gate_matrix",
    "m08_ethological_ambiguity_graph",
    "m08_ichnological_inference_ladder",
}


def _walk(value: Any, path: str = "data.bindings"):
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            yield child, str(key), item
            yield from _walk(item, child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")


def _norm(key: str) -> str:
    key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def _forbid_hidden(bindings: dict[str, Any], *, module: str) -> None:
    forbidden = re.compile(
        r"^(?:clade_id|clade_label|relict_links?|lineage_continuity|candidate_trace_classes?|"
        r"primary_drivers?|hidden_biology|hidden_truth|generator_truth|confirmed_extinct(?:ion)?|"
        r"reconstructed_scale|driver_ledger|clade_selectivity_ledger)$",
        re.IGNORECASE,
    )
    for path, key, _ in _walk(bindings):
        if forbidden.match(_norm(key)):
            raise FigureSpecError(f"{module}_HIDDEN_TRUTH_FORBIDDEN: {path}")
    text = str(bindings)
    if re.search(r"HIDDEN_(?:BIOLOGY|PROCESS|AND_FORBIDDEN)|CONFIRMED_EXTINCT", text, re.IGNORECASE):
        raise FigureSpecError(f"{module}_HIDDEN_TRUTH_MARKER_FORBIDDEN")


def _validate_m7(spec: dict[str, Any]) -> None:
    b = spec["data"]["bindings"]
    if spec["data"].get("source_kind") != "derived_evidence":
        raise FigureSpecError("MODULE7_PUBLIC_SOURCE_KIND_REQUIRED")
    _forbid_hidden(b, module="MODULE7")

    if spec["recipe_id"] == "m07_driver_trait_identifiability":
        if b.get("eventDriverResult") is not None or b.get("extinctionRiskResult") is not None:
            raise FigureSpecError("MODULE7_CAUSAL_RESULT_FORBIDDEN")
        rows = b.get("driverTraitReadiness") or []
        if not rows:
            raise FigureSpecError("MODULE7_DRIVER_TRAIT_READINESS_REQUIRED")
        for row in rows:
            if row.get("causalRole") != "UNASSIGNED_FROM_PUBLIC_EVIDENCE":
                raise FigureSpecError("MODULE7_CAUSAL_ROLE_FORBIDDEN")
            if row.get("riskDirection") != "UNASSIGNED":
                raise FigureSpecError("MODULE7_RISK_DIRECTION_FORBIDDEN")
            if row.get("selectivityMagnitude") is not None:
                raise FigureSpecError("MODULE7_SELECTIVITY_MAGNITUDE_FORBIDDEN")

    elif spec["recipe_id"] == "m07_primary_secondary_dependency":
        if b.get("interactionNetworkResult") is not None or b.get("causalAttributionResult") is not None:
            raise FigureSpecError("MODULE7_NETWORK_CAUSAL_RESULT_FORBIDDEN")
        rows = b.get("dependencyReadiness") or []
        if not rows:
            raise FigureSpecError("MODULE7_DEPENDENCY_READINESS_REQUIRED")
        for row in rows:
            if row.get("causalResult") is not None or row.get("magnitude") is not None:
                raise FigureSpecError("MODULE7_DEPENDENCY_RESULT_FORBIDDEN")
        secondary = [x for x in rows if x.get("pathway") == "secondary_network_mediated_extinction"]
        if not secondary or any(x.get("status") != "BLOCKED_WITHOUT_EXPLICIT_INTERACTION_NETWORK" for x in secondary):
            raise FigureSpecError("MODULE7_SECONDARY_NETWORK_MUST_REMAIN_BLOCKED")


def _validate_m8(spec: dict[str, Any]) -> None:
    b = spec["data"]["bindings"]
    if spec["data"].get("source_kind") != "derived_evidence":
        raise FigureSpecError("MODULE8_PUBLIC_SOURCE_KIND_REQUIRED")
    _forbid_hidden(b, module="MODULE8")
    text = str(b)
    if re.search(r"\b(?:skolithos|cruziana|thallasinoides|thalassinoides|ophiomorpha|rusophycus|paleodictyon)\b", text, re.IGNORECASE):
        raise FigureSpecError("MODULE8_UNLICENSED_ICHNOTAXON_FORBIDDEN")

    if spec["recipe_id"] == "m08_behavior_trace_license_matrix":
        if b.get("tracemakerResult") is not None or b.get("exactBehaviorResult") is not None:
            raise FigureSpecError("MODULE8_IDENTITY_RESULT_FORBIDDEN")
        traces = b.get("recoveredTraceLedger") or []
        licenses = b.get("usedLicenseLedger") or []
        if not traces:
            raise FigureSpecError("MODULE8_RECOVERED_TRACE_REQUIRED")
        used = {str(x.get("licenseId")) for x in traces}
        if {str(x.get("licenseId")) for x in licenses} != used:
            raise FigureSpecError("MODULE8_UNUSED_LICENSE_FORBIDDEN")
        lic_by_id = {str(x.get("licenseId")): x for x in licenses}
        for trace in traces:
            lic = lic_by_id.get(str(trace.get("licenseId")))
            if lic is None or str(trace.get("traceClass")) != str(lic.get("allowedObservationClass")):
                raise FigureSpecError("MODULE8_LICENSE_MISMATCH")
            if trace.get("tracemakerAffinity") != "UNRESOLVED_WITHOUT_INDEPENDENT_BODY_TRACE_ASSOCIATION":
                raise FigureSpecError("MODULE8_TRACEMAKER_IDENTITY_FORBIDDEN")
            allowed = {str(x) for x in (lic.get("allowedBehaviorClasses") or [])}
            if any(str(h) not in allowed for h in (trace.get("behavioralHypotheses") or [])):
                raise FigureSpecError("MODULE8_BEHAVIOR_HYPOTHESIS_UNLICENSED")

    elif spec["recipe_id"] == "m08_preservation_gate_matrix":
        if b.get("fossilizationProbability") is not None:
            raise FigureSpecError("MODULE8_FOSSILIZATION_PROBABILITY_FORBIDDEN")
        if not (b.get("preservationGates") or []):
            raise FigureSpecError("MODULE8_PRESERVATION_GATES_REQUIRED")

    elif spec["recipe_id"] == "m08_ethological_ambiguity_graph":
        if b.get("exactBehaviorResult") is not None or b.get("tracemakerResult") is not None:
            raise FigureSpecError("MODULE8_IDENTITY_RESULT_FORBIDDEN")
        rows = b.get("ambiguityLedger") or []
        if not rows:
            raise FigureSpecError("MODULE8_AMBIGUITY_LEDGER_REQUIRED")
        for row in rows:
            if row.get("exactBehaviorResult") is not None or row.get("tracemakerResult") is not None:
                raise FigureSpecError("MODULE8_AMBIGUITY_IDENTITY_RESULT_FORBIDDEN")

    elif spec["recipe_id"] == "m08_ichnological_inference_ladder":
        if b.get("ichnofaciesResult") is not None or b.get("tracemakerResult") is not None:
            raise FigureSpecError("MODULE8_HIGHER_INFERENCE_RESULT_FORBIDDEN")
        ladder = b.get("inferenceLadder") or []
        if not ladder:
            raise FigureSpecError("MODULE8_INFERENCE_LADDER_REQUIRED")
        statuses = {str(x.get("level")): str(x.get("status")) for x in ladder}
        if statuses.get("tracemaker_identity") != "BLOCKED_WITHOUT_INDEPENDENT_BODY_TRACE_ASSOCIATION":
            raise FigureSpecError("MODULE8_TRACEMAKER_LEVEL_MUST_REMAIN_BLOCKED")
        if statuses.get("behavior_absence_from_non_detection") != "PROHIBITED":
            raise FigureSpecError("MODULE8_NONDETECTION_ABSENCE_INFERENCE_FORBIDDEN")


def validate_module_07_08(spec: dict[str, Any]) -> None:
    recipe = spec.get("recipe_id")
    if recipe in _M7:
        _validate_m7(spec)
    elif recipe in _M8:
        _validate_m8(spec)
