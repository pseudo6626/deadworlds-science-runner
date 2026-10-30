from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .errors import FigureSpecError

_M12 = "m12a_trait_coding_provenance"
_M15 = "m15a_model_provenance"

_M12_ASSIGN_KEYS = {
    "evidence_ref",
    "trait_family",
    "trait_state",
    "phase_id",
    "observation_basis",
    "observation_unit",
    "functional_constraint_status",
    "cultural_origin_status",
}
_M12_RULE_KEYS = {
    "trait_family",
    "observation_dimension",
    "state_labels",
    "coding_basis",
    "functional_constraint_status",
}
_M15_MODEL_KEYS = {
    "comparison_group_id",
    "model_id",
    "source_module",
    "source_version",
    "assumptions",
    "observed_data_refs",
    "simulator_status",
    "pointwise_log_likelihood_status",
    "likelihood_status",
}
_M15_SOURCE_KEYS = {
    "comparison_group_id",
    "source_module",
    "source_version",
    "source_rule",
}

_INTERPRETIVE = re.compile(
    r"\b(?:means?|meaning|symboli[sz](?:e|es|ed|ing)?|used\s+for|function(?:ed)?\s+as|"
    r"prestige|elite|religio\w*|ritual|ethnic|language|phoneme|teacher|learner|kinship|clan|"
    r"copy(?:ing|ied)?|direct\s+contact|common\s+descent|social\s+identity)\b",
    re.IGNORECASE,
)
_RESULTISH = re.compile(
    r"(?:winner|preferred|truth[_ ]?probab|posterior[_ ]?model[_ ]?probab|"
    r"stacking[_ ]?weight|model[_ ]?score|rank|elpd|loo[_ ]?result|bayes[_ ]?factor)",
    re.IGNORECASE,
)


def _forbid_unreviewed_keys(row: Mapping[str, Any], allowed: set[str], label: str) -> None:
    extra = sorted(str(k) for k in row if str(k) not in allowed)
    if extra:
        raise FigureSpecError(f"{label} contains unreviewed fields: {extra}")


def _as_text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _validate_m12(bindings: dict[str, Any]) -> None:
    if set(bindings) != {"traitAssignments", "codingRules"}:
        raise FigureSpecError("MODULE12_PROVENANCE_BINDINGS_MUST_BE_EXACT")
    assignments = bindings.get("traitAssignments")
    rules = bindings.get("codingRules")
    if not isinstance(assignments, list) or not assignments or not isinstance(rules, list) or not rules:
        raise FigureSpecError("MODULE12_PROVENANCE_ASSIGNMENTS_AND_RULES_REQUIRED")

    by_family: dict[str, dict[str, Any]] = {}
    for raw in rules:
        if not isinstance(raw, Mapping):
            raise FigureSpecError("MODULE12_PROVENANCE_RULE_INVALID")
        _forbid_unreviewed_keys(raw, _M12_RULE_KEYS, "Module 12 coding rule")
        family = _as_text(raw.get("trait_family"))
        dimension = _as_text(raw.get("observation_dimension"))
        basis = _as_text(raw.get("coding_basis"))
        states = raw.get("state_labels")
        if not family or family in by_family or not dimension or not basis:
            raise FigureSpecError("MODULE12_PROVENANCE_RULE_INVALID")
        if not isinstance(states, list) or len(states) < 2 or any(not _as_text(x) for x in states) or len({_as_text(x) for x in states}) != len(states):
            raise FigureSpecError("MODULE12_PROVENANCE_RULE_STATES_INVALID")
        if _INTERPRETIVE.search(" ".join([family, dimension, basis, *map(str, states)])):
            raise FigureSpecError("MODULE12_PROVENANCE_INTERPRETIVE_TEXT_FORBIDDEN")
        by_family[family] = dict(raw)

    seen: set[tuple[str, str, str, str]] = set()
    used_families: set[str] = set()
    for raw in assignments:
        if not isinstance(raw, Mapping):
            raise FigureSpecError("MODULE12_PROVENANCE_ASSIGNMENT_INVALID")
        _forbid_unreviewed_keys(raw, _M12_ASSIGN_KEYS, "Module 12 trait assignment")
        ref = _as_text(raw.get("evidence_ref"))
        family = _as_text(raw.get("trait_family"))
        state = _as_text(raw.get("trait_state"))
        phase = _as_text(raw.get("phase_id"))
        basis = _as_text(raw.get("observation_basis"))
        unit = _as_text(raw.get("observation_unit"))
        if not ref or not family or not state or not phase or not basis or unit not in {"find", "signal", "site"}:
            raise FigureSpecError("MODULE12_PROVENANCE_ASSIGNMENT_INVALID")
        rule = by_family.get(family)
        if rule is None:
            raise FigureSpecError("MODULE12_PROVENANCE_ORPHAN_ASSIGNMENT")
        if state not in {_as_text(x) for x in rule.get("state_labels", [])}:
            raise FigureSpecError("MODULE12_PROVENANCE_UNLICENSED_STATE")
        if _INTERPRETIVE.search(basis):
            raise FigureSpecError("MODULE12_PROVENANCE_INTERPRETIVE_TEXT_FORBIDDEN")
        key = (ref, family, phase, state)
        if key in seen:
            raise FigureSpecError("MODULE12_PROVENANCE_DUPLICATE_ASSIGNMENT")
        seen.add(key)
        used_families.add(family)

    if used_families != set(by_family):
        raise FigureSpecError("MODULE12_PROVENANCE_UNUSED_OR_MISSING_CODING_RULE")


def _validate_m15(bindings: dict[str, Any]) -> None:
    if set(bindings) != {"candidateModels", "candidateSources"}:
        raise FigureSpecError("MODULE15_PROVENANCE_BINDINGS_MUST_BE_EXACT")
    models = bindings.get("candidateModels")
    sources = bindings.get("candidateSources")
    if not isinstance(models, list) or not models or not isinstance(sources, list) or not sources:
        raise FigureSpecError("MODULE15_PROVENANCE_MODELS_AND_SOURCES_REQUIRED")

    source_by_group: dict[str, dict[str, Any]] = {}
    for raw in sources:
        if not isinstance(raw, Mapping):
            raise FigureSpecError("MODULE15_PROVENANCE_SOURCE_INVALID")
        _forbid_unreviewed_keys(raw, _M15_SOURCE_KEYS, "Module 15 candidate source")
        gid = _as_text(raw.get("comparison_group_id"))
        sm = _as_text(raw.get("source_module"))
        sv = _as_text(raw.get("source_version"))
        sr = _as_text(raw.get("source_rule"))
        if not gid or gid in source_by_group or not sm or not sv or not sr:
            raise FigureSpecError("MODULE15_PROVENANCE_SOURCE_INVALID")
        if re.search(r"model_comparison_ppc", sm, re.IGNORECASE):
            raise FigureSpecError("MODULE15_PROVENANCE_SELF_SOURCE_FORBIDDEN")
        if _RESULTISH.search(" ".join([gid, sm, sv, sr])):
            raise FigureSpecError("MODULE15_PROVENANCE_RESULT_SEMANTIC_FORBIDDEN")
        source_by_group[gid] = dict(raw)

    group_models: dict[str, set[str]] = {}
    for raw in models:
        if not isinstance(raw, Mapping):
            raise FigureSpecError("MODULE15_PROVENANCE_MODEL_INVALID")
        _forbid_unreviewed_keys(raw, _M15_MODEL_KEYS, "Module 15 candidate model")
        gid = _as_text(raw.get("comparison_group_id"))
        mid = _as_text(raw.get("model_id"))
        src = source_by_group.get(gid)
        if src is None or not mid:
            raise FigureSpecError("MODULE15_PROVENANCE_ORPHAN_MODEL")
        if _as_text(raw.get("source_module")) != _as_text(src.get("source_module")) or _as_text(raw.get("source_version")) != _as_text(src.get("source_version")):
            raise FigureSpecError("MODULE15_PROVENANCE_SOURCE_MISMATCH")
        assumptions = raw.get("assumptions")
        refs = raw.get("observed_data_refs")
        if not isinstance(assumptions, list) or not isinstance(refs, list):
            raise FigureSpecError("MODULE15_PROVENANCE_LIST_FIELDS_REQUIRED")
        text = " ".join([mid, *map(str, assumptions), *map(str, refs)])
        if _RESULTISH.search(text):
            raise FigureSpecError("MODULE15_PROVENANCE_RESULT_SEMANTIC_FORBIDDEN")
        ids = group_models.setdefault(gid, set())
        if mid in ids:
            raise FigureSpecError("MODULE15_PROVENANCE_DUPLICATE_MODEL")
        ids.add(mid)

    if set(group_models) != set(source_by_group):
        raise FigureSpecError("MODULE15_PROVENANCE_GROUP_SET_MISMATCH")
    if any(len(ids) < 2 for ids in group_models.values()):
        raise FigureSpecError("MODULE15_PROVENANCE_GROUP_REQUIRES_TWO_CANDIDATES")


def validate_module_12_15_provenance(spec: dict[str, Any]) -> None:
    recipe = spec.get("recipe_id")
    if recipe not in {_M12, _M15}:
        return
    if spec.get("data", {}).get("source_kind") != "derived_evidence":
        raise FigureSpecError("PROVENANCE_RECIPE_DERIVED_EVIDENCE_REQUIRED")
    bindings = spec.get("data", {}).get("bindings")
    if not isinstance(bindings, dict):
        raise FigureSpecError("PROVENANCE_RECIPE_BINDINGS_REQUIRED")
    if recipe == _M12:
        _validate_m12(bindings)
    else:
        _validate_m15(bindings)
