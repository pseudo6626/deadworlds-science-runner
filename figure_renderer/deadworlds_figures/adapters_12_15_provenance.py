from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from .errors import FigureSpecError
from .plans import PlotPlan


def _text(value: Any) -> str:
    return str(value if value is not None else "UNRESOLVED")


def _join(values: Any) -> str:
    if not isinstance(values, list):
        return "UNRESOLVED"
    return "; ".join(str(x) for x in values) or "NONE"


def trait_coding_provenance(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    assignments = b.get("traitAssignments") or []
    rules = b.get("codingRules") or []
    if not assignments or not rules:
        raise FigureSpecError("trait-coding provenance requires nonempty traitAssignments and codingRules")

    by_family: dict[str, dict[str, Any]] = {}
    rule_rows: list[list[str]] = []
    rule_csv: list[dict[str, Any]] = []
    for raw in rules:
        row = dict(raw)
        family = _text(row.get("trait_family")).strip()
        dimension = _text(row.get("observation_dimension")).strip()
        states = [str(x) for x in (row.get("state_labels") or [])]
        basis = _text(row.get("coding_basis")).strip()
        if not family or family == "UNRESOLVED" or family in by_family:
            raise FigureSpecError("trait-coding provenance has missing or duplicate trait family")
        if not dimension or dimension == "UNRESOLVED" or len(states) < 2 or len(set(states)) != len(states) or not basis or basis == "UNRESOLVED":
            raise FigureSpecError("trait-coding provenance contains an invalid coding rule")
        by_family[family] = row
        rule_rows.append([
            family,
            dimension,
            "; ".join(states),
            basis,
            _text(row.get("functional_constraint_status")),
        ])
        rule_csv.append(row)

    assignment_rows: list[list[str]] = []
    assignment_csv: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for raw in assignments:
        row = dict(raw)
        family = _text(row.get("trait_family")).strip()
        state = _text(row.get("trait_state")).strip()
        ref = _text(row.get("evidence_ref")).strip()
        phase = _text(row.get("phase_id")).strip()
        basis = _text(row.get("observation_basis")).strip()
        rule = by_family.get(family)
        if rule is None:
            raise FigureSpecError(f"trait assignment references unknown coding family: {family}")
        if state not in {str(x) for x in (rule.get("state_labels") or [])}:
            raise FigureSpecError(f"trait assignment state is not licensed by coding rule: {family}/{state}")
        if not ref or ref == "UNRESOLVED" or not phase or not basis or basis == "UNRESOLVED":
            raise FigureSpecError("trait assignment is missing recovered evidence, phase, or observable basis")
        key = (ref, family, phase, state)
        if key in seen:
            raise FigureSpecError("duplicate trait assignment in provenance figure")
        seen.add(key)
        assignment_rows.append([
            ref,
            family,
            state,
            phase,
            _text(row.get("observation_unit")),
            basis,
            _text(rule.get("observation_dimension")),
        ])
        assignment_csv.append({
            **row,
            "rule_observation_dimension": rule.get("observation_dimension"),
            "rule_coding_basis": rule.get("coding_basis"),
        })

    return [
        PlotPlan(
            suffix="trait_coding_rules",
            kind="table",
            title=f"{spec['title']} — coding rules",
            table_columns=[
                "Trait family",
                "Observable dimension",
                "Allowed states",
                "Coding basis",
                "Functional-constraint status",
            ],
            table_rows=rule_rows,
            csv_rows=rule_csv,
            note=(
                "Analytical coding rules for recovered observable variation only. "
                "They do not encode function, meaning, social identity, copying, contact, ancestry, or transmission edges."
            ),
        ),
        PlotPlan(
            suffix="trait_assignment_provenance",
            kind="table",
            title=f"{spec['title']} — recovered assignments",
            table_columns=[
                "Recovered evidence",
                "Trait family",
                "Coded state",
                "Phase",
                "Observation unit",
                "Observable basis",
                "Rule dimension",
            ],
            table_rows=assignment_rows,
            csv_rows=assignment_csv,
            note=(
                "Each row links one recovered observation to an explicit analytical coding rule. "
                "The links are coding provenance only, never social or transmission relationships."
            ),
        ),
    ]


def model_provenance(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    models = b.get("candidateModels") or []
    sources = b.get("candidateSources") or []
    if not models or not sources:
        raise FigureSpecError("model provenance requires nonempty candidateModels and candidateSources")

    source_by_group: dict[str, dict[str, Any]] = {}
    for raw in sources:
        src = dict(raw)
        gid = _text(src.get("comparison_group_id")).strip()
        if not gid or gid == "UNRESOLVED" or gid in source_by_group:
            raise FigureSpecError("model provenance has missing or duplicate comparison group source")
        if not _text(src.get("source_module")).strip() or not _text(src.get("source_version")).strip() or not _text(src.get("source_rule")).strip():
            raise FigureSpecError("model provenance source row is incomplete")
        source_by_group[gid] = src

    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for raw in models:
        row = dict(raw)
        gid = _text(row.get("comparison_group_id")).strip()
        mid = _text(row.get("model_id")).strip()
        src = source_by_group.get(gid)
        if src is None:
            raise FigureSpecError(f"candidate model references unknown comparison group: {gid}")
        if not mid or mid == "UNRESOLVED" or (gid, mid) in seen:
            raise FigureSpecError("candidate model id is missing or duplicated within a comparison group")
        seen.add((gid, mid))
        if _text(row.get("source_module")) != _text(src.get("source_module")) or _text(row.get("source_version")) != _text(src.get("source_version")):
            raise FigureSpecError("candidate model source module/version does not match comparison-group provenance")
        by_group[gid].append(row)

    if set(by_group) != set(source_by_group):
        raise FigureSpecError("candidate sources and candidate-model comparison groups must match exactly")

    plans: list[PlotPlan] = []
    for gid in sorted(by_group):
        group_models = sorted(by_group[gid], key=lambda x: _text(x.get("model_id")))
        if len(group_models) < 2:
            raise FigureSpecError("model provenance comparison group requires at least two explicit candidate models")
        src = source_by_group[gid]
        rows: list[list[str]] = []
        csv_rows: list[dict[str, Any]] = []
        for row in group_models:
            rows.append([
                _text(row.get("model_id")),
                _text(src.get("source_module")),
                _text(src.get("source_version")),
                _text(src.get("source_rule")),
                _join(row.get("assumptions")),
                _join(row.get("observed_data_refs")),
                _text(row.get("simulator_status")),
                _text(row.get("pointwise_log_likelihood_status")),
                _text(row.get("likelihood_status")),
            ])
            csv_rows.append({
                **row,
                "source_rule": src.get("source_rule"),
            })
        plans.append(
            PlotPlan(
                suffix=f"model_provenance__{''.join(c.lower() if c.isalnum() else '_' for c in gid).strip('_')[:80] or 'group'}",
                kind="table",
                title=f"{spec['title']} — {gid}",
                table_columns=[
                    "Candidate model",
                    "Source module",
                    "Source version",
                    "Source rule",
                    "Assumptions",
                    "Observed-data refs",
                    "Simulator",
                    "Pointwise log-likelihood",
                    "Likelihood",
                ],
                table_rows=rows,
                csv_rows=csv_rows,
                note=(
                    "Candidate provenance is displayed within this comparison group only. "
                    "Rows are not ranked, no candidate is preferred, and capability/status fields are not fit scores or truth probabilities."
                ),
            )
        )
    return plans


ADAPTERS_12_15_PROVENANCE: dict[str, Callable[[dict[str, Any]], list[PlotPlan]]] = {
    "m12a_trait_coding_provenance": trait_coding_provenance,
    "m15a_model_provenance": model_provenance,
}
