from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from .errors import FigureSpecError
from .plans import LineSeries, PlotPlan


def _text(value: Any) -> str:
    return str(value if value is not None else "UNRESOLVED")


def _slug(value: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "_" for c in str(value)).strip("_")
    return out[:80] or "item"


def _table(title: str, suffix: str, columns: list[str], rows: list[list[str]], csv_rows: list[dict[str, Any]], *, note: str) -> PlotPlan:
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


# ---------------- Module 9: Spatial Archaeology ----------------

def recovered_site_map(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    sites = b.get("georeferencedSites") or []
    if not sites:
        raise FigureSpecError("georeferencedSites is empty")

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for raw in sites:
        row = dict(raw)
        site_id = _text(row.get("siteId"))
        frame = _text(row.get("frame"))
        area = _text(row.get("surveyAreaId"))
        if site_id == "UNRESOLVED":
            raise FigureSpecError("recovered-site map contains a site without siteId")
        if frame == "LOCAL_SURVEY_GRID":
            x, y = row.get("xM"), row.get("yM")
            if isinstance(x, bool) or not isinstance(x, (int, float)) or isinstance(y, bool) or not isinstance(y, (int, float)):
                raise FigureSpecError("local-grid site requires numeric xM/yM")
            if row.get("latitudeDeg") is not None or row.get("longitudeDeg") is not None:
                raise FigureSpecError("local-grid site may not contain planetocentric coordinates")
        elif frame == "PLANETOCENTRIC_LAT_LON":
            lat, lon = row.get("latitudeDeg"), row.get("longitudeDeg")
            if isinstance(lat, bool) or not isinstance(lat, (int, float)) or isinstance(lon, bool) or not isinstance(lon, (int, float)):
                raise FigureSpecError("planetocentric site requires numeric latitude/longitude")
            if row.get("xM") is not None or row.get("yM") is not None or row.get("zM") is not None:
                raise FigureSpecError("planetocentric site may not contain local-grid coordinates")
        else:
            raise FigureSpecError(f"unsupported spatial coordinate frame: {frame}")
        groups[(frame, area)].append(row)

    plans: list[PlotPlan] = []
    for (frame, area), rows in sorted(groups.items()):
        series: list[LineSeries] = []
        csv_rows: list[dict[str, Any]] = []
        if frame == "LOCAL_SURVEY_GRID":
            x_label, y_label = "Local survey x (m)", "Local survey y (m)"
            for row in rows:
                series.append(LineSeries(_text(row.get("siteId")), [float(row["xM"])], [float(row["yM"])]))
                csv_rows.append(dict(row))
        else:
            x_label, y_label = "Planetocentric longitude (°)", "Planetocentric latitude (°)"
            for row in rows:
                series.append(LineSeries(_text(row.get("siteId")), [float(row["longitudeDeg"])], [float(row["latitudeDeg"])]))
                csv_rows.append(dict(row))
        plans.append(PlotPlan(
            suffix=f"recovered_site_map__{_slug(frame)}__{_slug(area)}",
            kind="line",
            title=f"{spec['title']} — {area}",
            x_label=x_label,
            y_label=y_label,
            series=series,
            csv_rows=csv_rows,
            note=(
                "Recovered georeferenced sites only. Each site is a single-point marker: no connecting route, "
                "cluster, exchange network, settlement hierarchy, or common chronology is implied. "
                "Local survey grids remain local and are never promoted to planetary coordinates."
            ),
        ))
    return plans


def pairwise_distance_matrix(spec: dict[str, Any]) -> list[PlotPlan]:
    rows = spec["data"]["bindings"].get("pairwiseDistances") or []
    if not rows:
        raise FigureSpecError("pairwiseDistances is empty")
    table_rows: list[list[str]] = []
    csv_rows: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        distance = row.get("distanceM")
        if isinstance(distance, bool) or not isinstance(distance, (int, float)) or float(distance) < 0:
            raise FigureSpecError("pairwise distance must be finite and nonnegative")
        uncertainty = row.get("coordinateUncertaintyBoundM")
        if uncertainty is not None and (isinstance(uncertainty, bool) or not isinstance(uncertainty, (int, float)) or float(uncertainty) < 0):
            raise FigureSpecError("coordinate uncertainty bound must be nonnegative when present")
        table_rows.append([
            _text(row.get("groupId")),
            _text(row.get("siteA")),
            _text(row.get("siteB")),
            f"{float(distance):.6g}",
            "UNRESOLVED" if uncertainty is None else f"{float(uncertainty):.6g}",
        ])
        csv_rows.append(row)
    return [_table(
        spec["title"],
        "pairwise_distance_matrix",
        ["Comparable group", "Site A", "Site B", "Distance (m)", "Coordinate uncertainty bound (m)"],
        table_rows,
        csv_rows,
        note=(
            "Descriptive intersite distances only within comparable coordinate frames. Proximity is not "
            "interaction, exchange, route use, clustering significance, or common chronology."
        ),
    )]


def sampling_and_recovery_context(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    survey = b.get("surveyContext") or {}
    firewall = b.get("samplingFirewall") or {}
    rows: list[tuple[str, str]] = []
    for key in ("survey_design", "coverage_completeness", "detection_model_status"):
        if key in survey:
            rows.append((f"Survey · {key}", _text(survey.get(key))))
    for key, value in sorted(firewall.items()):
        if not isinstance(value, (dict, list)):
            rows.append((f"Sampling firewall · {key}", _text(value)))
    rows.append(("Chronology", _text(b.get("chronologyStatus"))))
    density = b.get("observedSiteDensityPerKm2")
    rows.append(("Recovered-site density (sites/km²)", "UNRESOLVED" if density is None else f"{float(density):.6g}"))
    if not rows:
        raise FigureSpecError("sampling/recovery context has no renderable statuses")
    return [_status_table(
        spec["title"],
        "sampling_and_recovery_context",
        rows,
        note=(
            "Survey-conditioned recovered-site context only. Recovered-site density is not ancient settlement "
            "density; unsurveyed or undetected space is not archaeological absence."
        ),
    )]


def spatial_inference_prerequisite_matrix(spec: dict[str, Any]) -> list[PlotPlan]:
    blocked = spec["data"]["bindings"].get("blockedAnalyses") or []
    if not blocked:
        raise FigureSpecError("blockedAnalyses is empty")
    rows: list[list[str]] = []
    csv_rows: list[dict[str, Any]] = []
    for raw in blocked:
        row = dict(raw)
        analysis = _text(row.get("analysis"))
        status = _text(row.get("status"))
        reason = _text(row.get("reason"))
        missing = ", ".join(map(str, row.get("missingInputs") or [])) or "UNRESOLVED"
        rows.append([analysis, status, reason, missing])
        csv_rows.append(row)
    return [_table(
        spec["title"],
        "spatial_inference_prerequisite_matrix",
        ["Analysis", "Status", "Reason", "Missing prerequisites"],
        rows,
        csv_rows,
        note="Blocked analyses remain blocked; recovered-site proximity is never substituted for missing models or chronology.",
    )]


# ---------------- Module 11: Demography ----------------

def proxy_concordance_matrix(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    proxies = b.get("proxyLedger") or []
    if not proxies:
        raise FigureSpecError("proxyLedger is empty")
    rows: list[list[str]] = []
    csv_rows: list[dict[str, Any]] = []
    for raw in proxies:
        row = dict(raw)
        if row.get("populationConversionLicensed") is True:
            raise FigureSpecError("proxy ledger may not license direct population conversion")
        rows.append([
            _text(row.get("proxy_id")),
            _text(row.get("proxyClass")),
            _text(row.get("status")),
            _text(row.get("direction")),
            "NO",
        ])
        csv_rows.append(row)
    trend = b.get("relativeTrend") or {}
    rows.append([
        "relative_trend",
        "multi-proxy concordance",
        _text(trend.get("status")),
        _text(trend.get("direction")),
        "NO",
    ])
    return [_table(
        spec["title"],
        "proxy_concordance_matrix",
        ["Proxy", "Proxy class", "Status", "Direction", "Direct population conversion"],
        rows,
        csv_rows,
        note=(
            "Recovered proxies remain proxies. Concordant direction can support only relative demographic change "
            "when chronology and observation prerequisites are satisfied; no proxy is automatically population."
        ),
    )]


def population_inference_prerequisites(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    rows: list[tuple[str, str]] = []
    for key, value in sorted((b.get("prerequisites") or {}).items()):
        rows.append((f"Prerequisite · {key}", _text(value)))
    rows.extend([
        ("Relative-trend status", _text(b.get("relativeTrendStatus"))),
        ("Minimum-individuals status", _text(b.get("minimumIndividualsStatus"))),
        ("Absolute-population status", _text(b.get("absolutePopulationStatus"))),
    ])
    for item in b.get("blockedCalculations") or []:
        rows.append((f"BLOCKED · {_text(item.get('quantity'))}", _text(item.get("reason"))))
    if not rows:
        raise FigureSpecError("population inference prerequisite matrix is empty")
    return [_status_table(
        spec["title"],
        "population_inference_prerequisites",
        rows,
        note=(
            "Identifiability/prerequisite status only. BLOCKED means unresolved, not zero population or demographic absence."
        ),
    )]


def demographic_inference_ladder(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("populationResult") is not None:
        raise FigureSpecError("demographic inference ladder may not contain a numeric population result")
    rows = [
        ("Module status", _text(b.get("moduleStatus"))),
        ("Recovered descriptive proxies", _text(b.get("descriptiveProxyStatus"))),
        ("Relative demographic trend", _text(b.get("relativeTrendStatus"))),
        ("Minimum individuals", _text(b.get("minimumIndividualsStatus"))),
        ("Calibrated absolute population", _text(b.get("absolutePopulationStatus"))),
    ]
    return [_status_table(
        spec["title"],
        "demographic_inference_ladder",
        rows,
        note=(
            "Epistemic levels remain separate. This figure reports readiness/status only and deliberately exposes no "
            "numeric population estimate."
        ),
    )]


# ---------------- Module 13: Language Contact ----------------

def corpus_readiness(spec: dict[str, Any]) -> list[PlotPlan]:
    corpora = spec["data"]["bindings"].get("corpusReadiness") or []
    if not corpora:
        raise FigureSpecError("corpusReadiness is empty")
    columns = [
        "Corpus", "Modality", "Pattern coding", "Independence", "Communication",
        "Language", "Observation model", "Representation", "Comparative readiness",
    ]
    rows, csv_rows = [], []
    for raw in corpora:
        row = dict(raw)
        rows.append([
            _text(row.get("corpus_id")), _text(row.get("modality")),
            _text(row.get("pattern_unit_coding_status")), _text(row.get("independence_status")),
            _text(row.get("communication_status")), _text(row.get("language_status")),
            _text(row.get("observation_model_status")), _text(row.get("representation_status")),
            _text(row.get("comparative_readiness")),
        ])
        csv_rows.append(row)
    return [_table(
        spec["title"], "corpus_readiness", columns, rows, csv_rows,
        note="Recovered-corpus readiness only. Readiness does not establish language, contact, borrowing, or historical linkage.",
    )]


def alternative_explanation_matrix(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("modelComparisonResult") is not None:
        raise FigureSpecError("Module 13 may not contain a model-comparison result")
    comparisons = b.get("comparisonLedger") or []
    if not comparisons:
        raise FigureSpecError("comparisonLedger is empty")
    rows, csv_rows = [], []
    for raw in comparisons:
        row = dict(raw)
        rows.append([
            _text(row.get("comparison_id")),
            _text(row.get("observed_similarity_status")),
            _text(row.get("genealogical_baseline_status")),
            _text(row.get("convergence_baseline_status")),
            _text(row.get("chance_baseline_status")),
            _text(row.get("contact_feasibility_status")),
            _text(row.get("borrowing_model_eligibility")),
        ])
        csv_rows.append(row)
    plans = [_table(
        spec["title"],
        "alternative_explanation_matrix",
        ["Comparison", "Observed similarity", "Inheritance baseline", "Convergence baseline", "Chance baseline", "Contact feasibility", "Transfer-model eligibility"],
        rows, csv_rows,
        note=(
            "Alternative explanations remain candidates for later explicit comparison. Eligibility is not model fit, "
            "borrowing probability, or evidence that contact occurred."
        ),
    )]
    candidates = b.get("candidateModels") or []
    if candidates:
        plans.append(_status_table(
            f"{spec['title']} — candidate models",
            "candidate_model_readiness",
            [(_text(x.get("model_id")), _text(x.get("status"))) for x in candidates],
            note="Candidate-model readiness only; no model has been evaluated or preferred.",
        ))
    return plans


def direction_identifiability(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("directionResult") is not None:
        raise FigureSpecError("Module 13 may not contain a donor/recipient direction result")
    comparisons = b.get("comparisons") or []
    if not comparisons:
        raise FigureSpecError("direction-identifiability comparisons are empty")
    rows, csv_rows = [], []
    for raw in comparisons:
        row = dict(raw)
        rows.append([
            _text(row.get("comparison_id")),
            _text(row.get("borrowing_model_eligibility")),
            _text(row.get("directionality_eligibility")),
            _text(row.get("chronology_status")),
            _text(row.get("correspondence_model_status")),
        ])
        csv_rows.append(row)
    return [_table(
        spec["title"], "direction_identifiability",
        ["Comparison", "Transfer-model eligibility", "Direction-test eligibility", "Chronology", "Correspondence model"],
        rows, csv_rows,
        note="Direction-test eligibility is not a donor/recipient assignment and does not establish transfer.",
    )]


def comparison_provenance(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    plans: list[PlotPlan] = []
    corpora = b.get("corpora") or []
    if corpora:
        plans.append(_table(
            f"{spec['title']} — corpora", "comparison_provenance_corpora",
            ["Corpus", "Independence", "Representation"],
            [[_text(x.get("corpus_id")), _text(x.get("independence_status")), _text(x.get("representation_status"))] for x in corpora],
            [dict(x) for x in corpora],
            note="Corpus provenance/readiness only; rows are not historical contact nodes.",
        ))
    comparisons = b.get("comparisons") or []
    if comparisons:
        plans.append(_table(
            f"{spec['title']} — comparisons", "comparison_provenance_comparisons",
            ["Comparison", "Corpus A", "Corpus B", "Comparison kind"],
            [[_text(x.get("comparison_id")), _text(x.get("corpus_a")), _text(x.get("corpus_b")), _text(x.get("comparison_kind"))] for x in comparisons],
            [dict(x) for x in comparisons],
            note="Analytical comparison dependencies only; table rows are not contact or social-network edges.",
        ))
    prereq = b.get("prerequisiteEvidence") or []
    if prereq:
        plans.append(_table(
            f"{spec['title']} — prerequisite evidence", "comparison_provenance_prerequisites",
            ["Target", "Kind", "Evidence ref", "Source module", "Status"],
            [[f"{_text(x.get('target_type'))}:{_text(x.get('target_id'))}", _text(x.get("kind")), _text(x.get("evidence_ref")), _text(x.get("source_module")), _text(x.get("status"))] for x in prereq],
            [dict(x) for x in prereq],
            note="Evidence dependency provenance only; no historical contact is inferred from these links.",
        ))
    if not plans:
        raise FigureSpecError("comparison provenance has no renderable evidence")
    return plans


# ---------------- Module 14: Inscription Decipherment ----------------

def mark_inventory(spec: dict[str, Any]) -> list[PlotPlan]:
    docs = spec["data"]["bindings"].get("documents") or []
    if not docs:
        raise FigureSpecError("mark inventory contains no documents")
    rows: list[list[str]] = []
    csv_rows: list[dict[str, Any]] = []
    for doc in docs:
        doc_id = _text(doc.get("document_id"))
        preservation = _text(doc.get("preservation_status"))
        for mark in doc.get("mark_classes") or []:
            row = dict(mark) if isinstance(mark, dict) else {"mark_id": str(mark)}
            rows.append([
                doc_id,
                _text(row.get("mark_id")),
                _text(row.get("formal_description")),
                _text(row.get("variant_status")),
                preservation,
            ])
            csv_rows.append({"document_id": doc_id, "preservation_status": preservation, **row})
    if not rows:
        raise FigureSpecError("mark inventory contains no formal mark classes")
    return [_table(
        spec["title"], "mark_inventory",
        ["Document", "Mark class", "Formal description", "Variant status", "Preservation"],
        rows, csv_rows,
        note="Formal recovered mark classes only. No sound, linguistic value, semantic meaning, script type, or translation is assigned.",
    )]


def sequence_reading_order(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    docs = b.get("documents") or []
    rows: list[list[str]] = []
    csv_rows: list[dict[str, Any]] = []
    for doc in docs:
        doc_id = _text(doc.get("document_id"))
        for seq in doc.get("sequences") or []:
            row = dict(seq)
            marks = " · ".join(map(str, row.get("mark_ids") or [])) or "UNRESOLVED"
            rows.append([
                doc_id,
                _text(row.get("sequence_id")),
                marks,
                _text(row.get("physical_order_status")),
                _text(row.get("unknown_positions")),
            ])
            csv_rows.append({"document_id": doc_id, **row})
    if not rows:
        raise FigureSpecError("sequence/read-order figure contains no observed physical sequences")
    plans = [_table(
        spec["title"], "physical_sequence_observations",
        ["Document", "Sequence", "Observed physical mark order", "Physical-order status", "Unknown positions"],
        rows, csv_rows,
        note="Observed spatial/physical order only. Physical order is not automatically reading order or segmentation.",
    )]
    readiness = b.get("readiness") or {}
    if readiness:
        plans.append(_status_table(
            f"{spec['title']} — readiness", "reading_order_readiness",
            [(str(k), _text(v)) for k, v in readiness.items() if not isinstance(v, (dict, list))],
            note="Readiness status only; no reading direction, word boundary, value, or translation is inferred.",
        ))
    return plans


def decipherment_prerequisite_ladder(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    rows = [(str(k), _text(v)) for k, v in (b.get("readiness") or {}).items() if not isinstance(v, (dict, list))]
    blocked = b.get("blockedInferences") or []
    for item in blocked:
        rows.append((f"BLOCKED · {_text(item.get('quantity'))}", _text(item.get("reason"))))
    if not rows:
        raise FigureSpecError("decipherment prerequisite ladder is empty")
    return [_status_table(
        spec["title"], "decipherment_prerequisite_ladder", rows,
        note="Analysis eligibility only. This figure is not a reading, translation, sign-value assignment, or writing-system classification.",
    )]


def decipherment_model_handoff(spec: dict[str, Any]) -> list[PlotPlan]:
    h = spec["data"]["bindings"].get("modelHandoff") or {}
    rows = [
        ("Contract", _text(h.get("contractVersion"))),
        ("Handoff status", _text(h.get("status"))),
    ]
    plans = [_status_table(
        spec["title"], "decipherment_model_handoff_status", rows,
        note="Model-comparison handoff only; no candidate has been fitted or preferred and no decipherment result exists.",
    )]
    families = h.get("candidateFamilies") or []
    if families:
        table_rows, csv_rows = [], []
        for raw in families:
            row = dict(raw) if isinstance(raw, dict) else {"family": str(raw)}
            ident = _text(row.get("family_id") or row.get("model_id") or row.get("family") or row.get("id"))
            status = _text(row.get("status"))
            table_rows.append([ident, status])
            csv_rows.append(row)
        plans.append(_table(
            f"{spec['title']} — candidate families", "decipherment_candidate_families",
            ["Candidate family", "Status"], table_rows, csv_rows,
            note="Candidate-family readiness only; no sign mapping, phonetic/semantic value, translation, or model fit.",
        ))
    return plans


ADAPTERS_09_11_13_14: dict[str, Callable[[dict[str, Any]], list[PlotPlan]]] = {
    "m09_recovered_site_map": recovered_site_map,
    "m09_pairwise_distance_matrix": pairwise_distance_matrix,
    "m09_sampling_and_recovery_context": sampling_and_recovery_context,
    "m09_spatial_inference_prerequisite_matrix": spatial_inference_prerequisite_matrix,
    "m11a_proxy_concordance_matrix": proxy_concordance_matrix,
    "m11a_population_inference_prerequisites": population_inference_prerequisites,
    "m11a_demographic_inference_ladder": demographic_inference_ladder,
    "m13a_corpus_readiness": corpus_readiness,
    "m13a_alternative_explanation_matrix": alternative_explanation_matrix,
    "m13a_direction_identifiability": direction_identifiability,
    "m13a_comparison_provenance": comparison_provenance,
    "m14a_mark_inventory": mark_inventory,
    "m14a_sequence_reading_order": sequence_reading_order,
    "m14a_decipherment_prerequisite_ladder": decipherment_prerequisite_ladder,
    "m14a_model_handoff": decipherment_model_handoff,
}
