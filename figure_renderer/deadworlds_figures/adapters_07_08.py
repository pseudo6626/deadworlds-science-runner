from __future__ import annotations

from typing import Any, Callable

from .errors import FigureSpecError
from .plans import PlotPlan


def _text(value: Any) -> str:
    return str(value if value is not None else "UNRESOLVED")


def _join(values: Any) -> str:
    if not isinstance(values, list):
        return "UNRESOLVED"
    return ", ".join(str(x) for x in values) or "NONE"


def _table(
    title: str,
    suffix: str,
    columns: list[str],
    rows: list[list[str]],
    csv_rows: list[dict[str, Any]],
    *,
    note: str,
) -> PlotPlan:
    return PlotPlan(
        suffix=suffix,
        kind="table",
        title=title,
        table_columns=columns,
        table_rows=rows,
        csv_rows=csv_rows,
        note=note,
    )


def _status_table(title: str, suffix: str, rows: list[tuple[str, str]], *, note: str) -> PlotPlan:
    return PlotPlan(
        suffix=suffix,
        kind="status_table",
        title=title,
        table_columns=["Diagnostic", "Status"],
        table_rows=[[a, b] for a, b in rows],
        csv_rows=[{"diagnostic": a, "status": b} for a, b in rows],
        note=note,
    )


# ---------------- Module 7: Extinction Selectivity (public evidence only) ----------------


def extinction_driver_trait_identifiability(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("eventDriverResult") is not None or b.get("extinctionRiskResult") is not None:
        raise FigureSpecError("Module 7 public figure may not contain a driver or extinction-risk result")
    ledger = b.get("driverTraitReadiness") or []
    if not ledger:
        raise FigureSpecError("driverTraitReadiness is empty")
    rows: list[list[str]] = []
    csv_rows: list[dict[str, Any]] = []
    for raw in ledger:
        row = dict(raw)
        if row.get("causalRole") != "UNASSIGNED_FROM_PUBLIC_EVIDENCE":
            raise FigureSpecError("Module 7 public figure assigned a causal driver role")
        if row.get("riskDirection") != "UNASSIGNED" or row.get("selectivityMagnitude") is not None:
            raise FigureSpecError("Module 7 public figure assigned a risk direction or selectivity magnitude")
        rows.append([
            _text(row.get("candidateDriverClass")),
            _text(row.get("publicEnvironmentalEvidenceStatus")),
            _join(row.get("requiredTraitClasses")),
            _text(row.get("vulnerabilityTraitStatus")),
            _text(row.get("causalRole")),
            _text(row.get("riskDirection")),
        ])
        csv_rows.append({
            "candidateDriverClass": row.get("candidateDriverClass"),
            "publicEnvironmentalEvidenceStatus": row.get("publicEnvironmentalEvidenceStatus"),
            "requiredTraitClasses": row.get("requiredTraitClasses") or [],
            "vulnerabilityTraitStatus": row.get("vulnerabilityTraitStatus"),
            "causalRole": row.get("causalRole"),
            "riskDirection": row.get("riskDirection"),
            "evidenceRefs": row.get("evidenceRefs") or [],
        })
    return [_table(
        spec["title"],
        "driver_trait_identifiability",
        ["Candidate driver class", "Public environmental evidence", "Required trait classes", "Vulnerability-trait evidence", "Causal role", "Risk direction"],
        rows,
        csv_rows,
        note=(
            "Public evidence readiness only. Candidate driver classes are analytical categories, not historical "
            "extinction drivers; no selectivity magnitude, survival probability, or generic risk direction is inferred."
        ),
    )]


def extinction_primary_secondary_dependency(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("interactionNetworkResult") is not None or b.get("causalAttributionResult") is not None:
        raise FigureSpecError("Module 7 dependency figure may not contain network or causal-attribution results")
    ledger = b.get("dependencyReadiness") or []
    if not ledger:
        raise FigureSpecError("dependencyReadiness is empty")
    rows: list[list[str]] = []
    csv_rows: list[dict[str, Any]] = []
    for raw in ledger:
        row = dict(raw)
        if row.get("causalResult") is not None or row.get("magnitude") is not None:
            raise FigureSpecError("Module 7 dependency row contains a causal result or extinction magnitude")
        rows.append([
            _text(row.get("pathway")),
            _text(row.get("status")),
            _join(row.get("prerequisites")),
            str(len(row.get("evidenceRefs") or [])),
        ])
        csv_rows.append({
            "pathway": row.get("pathway"),
            "status": row.get("status"),
            "prerequisites": row.get("prerequisites") or [],
            "evidenceRefs": row.get("evidenceRefs") or [],
        })
    return [_table(
        spec["title"],
        "primary_secondary_dependency",
        ["Pathway", "Evidence status", "Prerequisites", "Public evidence refs"],
        rows,
        csv_rows,
        note=(
            "Direct environmental selectivity and network-mediated secondary extinction remain separate hypotheses. "
            "Evidence-reference count is descriptive only; it is not effect strength, probability, or model support."
        ),
    )]


# ---------------- Module 8: Trace Fossils / Ichnology (recovered evidence only) ----------------


def ichnology_trace_license_matrix(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("tracemakerResult") is not None or b.get("exactBehaviorResult") is not None:
        raise FigureSpecError("Module 8 trace-license figure may not contain tracemaker/exact-behavior results")
    traces = b.get("recoveredTraceLedger") or []
    licenses = b.get("usedLicenseLedger") or []
    if not traces:
        raise FigureSpecError("recoveredTraceLedger is empty")
    lic_by_id = {str(x.get("licenseId")): dict(x) for x in licenses}
    used = {str(x.get("licenseId")) for x in traces}
    if set(lic_by_id) != used:
        raise FigureSpecError("usedLicenseLedger must contain exactly the licenses exercised by recovered traces")
    rows: list[list[str]] = []
    csv_rows: list[dict[str, Any]] = []
    for raw in traces:
        row = dict(raw)
        license_id = str(row.get("licenseId"))
        lic = lic_by_id.get(license_id)
        if lic is None or str(row.get("traceClass")) != str(lic.get("allowedObservationClass")):
            raise FigureSpecError("recovered trace does not match its exercised public license")
        if row.get("tracemakerAffinity") != "UNRESOLVED_WITHOUT_INDEPENDENT_BODY_TRACE_ASSOCIATION":
            raise FigureSpecError("recovered trace contains a resolved tracemaker affinity")
        allowed = {str(x) for x in (lic.get("allowedBehaviorClasses") or [])}
        hypotheses = [str(x) for x in (row.get("behavioralHypotheses") or [])]
        if any(x not in allowed for x in hypotheses):
            raise FigureSpecError("recovered trace contains an unlicensed behavioral hypothesis")
        rows.append([
            _text(row.get("traceId")),
            _text(row.get("traceClass")),
            _join(hypotheses),
            _text(row.get("tracemakerAffinity")),
        ])
        csv_rows.append({
            "traceId": row.get("traceId"),
            "evidenceRef": row.get("evidenceRef"),
            "licenseId": license_id,
            "traceClass": row.get("traceClass"),
            "behavioralHypotheses": hypotheses,
            "tracemakerAffinity": row.get("tracemakerAffinity"),
        })
    return [_table(
        spec["title"],
        "trace_license_matrix",
        ["Recovered trace", "Generic trace class", "Licensed behavioral hypotheses", "Tracemaker affinity"],
        rows,
        csv_rows,
        note=(
            "Only licenses actually exercised by recovered trace evidence are shown. Behavioral classes remain "
            "hypotheses; producer identity and exact behavior are unresolved."
        ),
    )]


def ichnology_preservation_gate_matrix(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("fossilizationProbability") is not None:
        raise FigureSpecError("Module 8 preservation figure may not contain fossilization probability")
    gates = b.get("preservationGates") or []
    if not gates:
        raise FigureSpecError("preservationGates is empty")
    rows = [(_text(x.get("gate")), _text(x.get("status"))) for x in gates]
    sampling = b.get("samplingContext") or {}
    for item in sampling.get("samplingLimits") or []:
        rows.append(("Sampling limit", _text(item)))
    survey = sampling.get("surveyContext") or {}
    for key in ("survey_design", "coverage_completeness", "detection_model_status"):
        if key in survey:
            rows.append((f"Survey · {key}", _text(survey.get(key))))
    return [_status_table(
        spec["title"],
        "preservation_gate_matrix",
        rows,
        note=(
            "Recovered preservation/recovery context only. These statuses are not a fossilization probability, and "
            "non-detection is not evidence that a behavior was absent."
        ),
    )]


def ichnology_ethological_ambiguity(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("exactBehaviorResult") is not None or b.get("tracemakerResult") is not None:
        raise FigureSpecError("Module 8 ambiguity figure may not contain exact behavior/tracemaker results")
    ledger = b.get("ambiguityLedger") or []
    if not ledger:
        raise FigureSpecError("ambiguityLedger is empty")
    rows: list[list[str]] = []
    csv_rows: list[dict[str, Any]] = []
    for raw in ledger:
        row = dict(raw)
        if row.get("exactBehaviorResult") is not None or row.get("tracemakerResult") is not None:
            raise FigureSpecError("ambiguity row contains exact behavior/tracemaker result")
        hypotheses = [str(x) for x in (row.get("allowedBehaviorHypotheses") or [])]
        if not hypotheses:
            rows.append([_text(row.get("traceId")), _text(row.get("traceClass")), "UNRESOLVED", _text(row.get("ambiguityStatus"))])
            csv_rows.append({"traceId": row.get("traceId"), "traceClass": row.get("traceClass"), "behavioralHypothesis": None, "ambiguityStatus": row.get("ambiguityStatus")})
        else:
            for hypothesis in hypotheses:
                rows.append([_text(row.get("traceId")), _text(row.get("traceClass")), hypothesis, _text(row.get("ambiguityStatus"))])
                csv_rows.append({"traceId": row.get("traceId"), "traceClass": row.get("traceClass"), "behavioralHypothesis": hypothesis, "ambiguityStatus": row.get("ambiguityStatus")})
    return [_table(
        spec["title"],
        "ethological_ambiguity",
        ["Recovered trace", "Generic trace class", "Compatible behavioral hypothesis", "Interpretation status"],
        rows,
        csv_rows,
        note=(
            "Static edge-list fallback for the ambiguity graph. Each row is a compatibility edge only; edges are "
            "not probabilities, and neither exact behavior nor tracemaker identity is assigned."
        ),
    )]


def ichnology_inference_ladder(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("ichnofaciesResult") is not None or b.get("tracemakerResult") is not None:
        raise FigureSpecError("Module 8 inference ladder may not contain ichnofacies/tracemaker results")
    ladder = b.get("inferenceLadder") or []
    if not ladder:
        raise FigureSpecError("inferenceLadder is empty")
    rows = [(_text(x.get("level")), _text(x.get("status"))) for x in ladder]
    return [_status_table(
        spec["title"],
        "ichnological_inference_ladder",
        rows,
        note=(
            "Morphology, generic trace class, behavioral hypothesis, tracemaker identity, and ichnofacies remain "
            "distinct epistemic levels. Higher-level interpretations require independent evidence."
        ),
    )]


ADAPTERS_07_08: dict[str, Callable[[dict[str, Any]], list[PlotPlan]]] = {
    "m07_driver_trait_identifiability": extinction_driver_trait_identifiability,
    "m07_primary_secondary_dependency": extinction_primary_secondary_dependency,
    "m08_behavior_trace_license_matrix": ichnology_trace_license_matrix,
    "m08_preservation_gate_matrix": ichnology_preservation_gate_matrix,
    "m08_ethological_ambiguity_graph": ichnology_ethological_ambiguity,
    "m08_ichnological_inference_ladder": ichnology_inference_ladder,
}
