from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from jsonschema import Draft202012Validator

from .errors import FigureSpecError
from .schema import FIGURE_SPEC_SCHEMA
from .validate_04_06 import validate_module_04_06
from .validate_09_11_13_14 import validate_module_09_11_13_14
from .validate_07_08 import validate_module_07_08
from .validate_12_15_provenance import validate_module_12_15_provenance

_VALIDATOR = Draft202012Validator(FIGURE_SPEC_SCHEMA)
_FORBIDDEN_KEY = re.compile(
    r"^(?:hiddenCulture|hidden_culture|hidden_truth|generator_truth|"
    r"modelTruthProbabilit(?:y|ies)|truth_probability|winner_model|preferred_model|"
    r"transmission_edges?|social_network_edges?|direct_contact_edges?|population_prevalence|"
    r"prestige_score|ethnic_identity|semantic_meaning)$",
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


def _finite_numbers(value: Any, path: str = "data.bindings") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise FigureSpecError(f"non-finite numeric value at {path}")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _finite_numbers(item, f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for i, item in enumerate(value):
            _finite_numbers(item, f"{path}[{i}]")


def validate_figure_spec(spec: dict[str, Any], *, strict_provenance: bool = True) -> dict[str, Any]:
    errors = sorted(_VALIDATOR.iter_errors(spec), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        location = ".".join(map(str, first.path)) or "<root>"
        raise FigureSpecError(f"FigureSpec schema violation at {location}: {first.message}")

    if spec["dimensionality"] != "2d":
        raise FigureSpecError("renderer v0.9.0 accepts only 2d FigureSpecs")
    renderer = spec["renderer"]
    if renderer["preferred"] != "matplotlib" and "matplotlib" not in renderer.get("fallbacks", []):
        raise FigureSpecError("FigureSpec has no licensed matplotlib renderer path")
    if not spec["outputs"]:
        raise FigureSpecError("FigureSpec outputs must not be empty")
    if "interactive_html" in spec["outputs"] and renderer["preferred"] != "plotly":
        # We can render the static fallback, but never silently pretend to have emitted interactivity.
        pass

    provenance = spec["provenance"]
    if strict_provenance:
        module_run_id = str(provenance.get("module_run_id", "")).strip()
        source_refs = provenance.get("source_refs")
        if not module_run_id or module_run_id == "UNPERSISTED":
            raise FigureSpecError("rendering requires a persisted module_run_id")
        if not isinstance(source_refs, list) or not source_refs:
            raise FigureSpecError("rendering requires at least one source_ref")

    bindings = spec["data"]["bindings"]
    for path, key, _ in _walk(bindings):
        if _FORBIDDEN_KEY.match(key):
            raise FigureSpecError(f"unlicensed/hidden inference field in figure bindings: {path}")
    if re.search(r"HIDDEN_AND_FORBIDDEN", str(bindings), re.IGNORECASE):
        raise FigureSpecError("hidden truth marker leaked into figure bindings")

    if spec["recipe_id"] == "m12a_transmission_model_identifiability":
        if bindings.get("modelComparisonResult", None) is not None:
            raise FigureSpecError("Module 12 identifiability figure may not contain model-comparison results")

    if spec["recipe_id"] == "m01_escape_retention_sensitivity":
        if bindings.get("escapeRateResult", None) is not None or bindings.get("historyResult", None) is not None:
            raise FigureSpecError("Module 1 retention sensitivity may not contain an escape rate/history result")
        forbidden = re.compile(r"(?:^|_)(?:escape_rate|mass_loss_rate|historical_loss|atmospheric_loss_history)(?:_|$)", re.IGNORECASE)
        for path, key, _ in _walk(bindings):
            normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
            if forbidden.search(normalized):
                raise FigureSpecError(f"MODULE1_ESCAPE_RATE_HISTORY_FORBIDDEN: {path}")

    if spec["recipe_id"] == "m02_redox_ratio_diagnostics":
        if (
            bindings.get("mantleOxygenFugacity", None) is not None
            or bindings.get("redoxBufferOffset", None) is not None
            or bindings.get("aqueousPh", None) is not None
        ):
            raise FigureSpecError("Module 2 atmospheric gas-ratio figure may not contain mantle fO2, redox-buffer, or aqueous-pH results")
        forbidden = re.compile(
            r"(?:mantle_(?:oxygen_fugacity|fo2)|(?:delta_)?(?:fmq|iw)(?:_offset)?|oxygen_fugacity)",
            re.IGNORECASE,
        )
        for path, key, _ in _walk(bindings):
            normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
            if forbidden.search(normalized):
                raise FigureSpecError(f"MODULE2_MANTLE_REDOX_FORBIDDEN: {path}")


    if spec["recipe_id"] == "m03_capture_efficiency_sensitivity":
        if (
            bindings.get("actualCaptureEfficiency", None) is not None
            or bindings.get("productivityResult", None) is not None
            or bindings.get("biomassResult", None) is not None
        ):
            raise FigureSpecError("Module 3 capture sensitivity may not contain inferred capture efficiency, productivity, or biomass results")

    if spec["recipe_id"] == "m03_trophic_transfer_sensitivity":
        if bindings.get("actualTrophicTransferEfficiency", None) is not None:
            raise FigureSpecError("Module 3 trophic sensitivity may not contain an inferred actual trophic-transfer efficiency")

    if spec["recipe_id"] == "m03_energy_channel_identifiability":
        forbidden = re.compile(
            r"(?:power_w|energy_magnitude|fractional_contribution|relative_importance|actual_channel_power|"
            r"primary_productivity|biomass_(?:inventory|density))",
            re.IGNORECASE,
        )
        for path, key, _ in _walk(bindings.get("channelAssessment") or []):
            normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
            if forbidden.search(normalized):
                raise FigureSpecError(f"MODULE3_CHANNEL_MAGNITUDE_FORBIDDEN: {path}")

    validate_module_04_06(spec)
    validate_module_09_11_13_14(spec)
    validate_module_07_08(spec)
    validate_module_12_15_provenance(spec)
    _finite_numbers(bindings)
    return spec
