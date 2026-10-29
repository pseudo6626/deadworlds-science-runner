from __future__ import annotations

from collections import defaultdict
import math
from typing import Any, Callable

from .errors import FigureSpecError, UnsupportedRecipeError
from .plans import LineSeries, PlotPlan


def _text(value: Any) -> str:
    return str(value if value is not None else "UNRESOLVED")


def _slug(value: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "_" for c in str(value)).strip("_")
    return out[:80] or "item"


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


def _value_bar(title: str, suffix: str, labels: list[str], values: list[float], *, x_label: str, csv_rows: list[dict[str, Any]], note: str) -> PlotPlan:
    if not labels or len(labels) != len(values):
        raise FigureSpecError(f"{suffix} has no renderable values")
    positives = [v for v in values if v > 0]
    x_scale = "log" if len(positives) == len(values) and max(positives) / min(positives) >= 1000 else "linear"
    return PlotPlan(
        suffix=suffix,
        kind="barh",
        title=title,
        x_label=x_label,
        series=[LineSeries(label="value", x=labels, y=values)],
        csv_rows=csv_rows,
        note=note,
        x_scale=x_scale,
    )


# ---------------- Module 1: Atmospheric Evolution ----------------

def equilibrium_temperature_albedo_sensitivity(spec: dict[str, Any]) -> list[PlotPlan]:
    rows = spec["data"]["bindings"].get("equilibriumTemperatureSensitivity") or []
    if len(rows) < 2:
        raise FigureSpecError("equilibriumTemperatureSensitivity requires at least two albedo rows")
    points = []
    for row in rows:
        albedo = row.get("bondAlbedo")
        temp = row.get("equilibriumTemperatureK")
        if isinstance(albedo, bool) or not isinstance(albedo, (int, float)) or not 0 <= float(albedo) <= 1:
            raise FigureSpecError("equilibrium-temperature sensitivity has invalid Bond albedo")
        if isinstance(temp, bool) or not isinstance(temp, (int, float)) or float(temp) <= 0:
            raise FigureSpecError("equilibrium-temperature sensitivity has invalid temperature")
        points.append((float(albedo), float(temp), dict(row)))
    points.sort(key=lambda x: x[0])
    return [PlotPlan(
        suffix="equilibrium_temperature_albedo_sensitivity",
        kind="line",
        title=spec["title"],
        x_label="Assumed Bond albedo",
        y_label="Equilibrium temperature (K)",
        series=[LineSeries("Irradiation equilibrium", [x[0] for x in points], [x[1] for x in points])],
        csv_rows=[x[2] for x in points],
        note="Deterministic irradiation sensitivity only. Bond albedo is an explicit assumption; equilibrium temperature is not measured surface temperature and excludes greenhouse and internal heating.",
    )]


def escape_retention_sensitivity(spec: dict[str, Any]) -> list[PlotPlan]:
    rows = spec["data"]["bindings"].get("referenceJeansSensitivity") or []
    if not rows:
        raise FigureSpecError("referenceJeansSensitivity is empty")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        species = _text(row.get("species"))
        texo = row.get("assumedExobaseTemperatureK")
        lam = row.get("referenceJeansLambda")
        if species == "UNRESOLVED":
            raise FigureSpecError("reference Jeans sensitivity row lacks species")
        if isinstance(texo, bool) or not isinstance(texo, (int, float)) or float(texo) <= 0:
            raise FigureSpecError("reference Jeans sensitivity has invalid assumed exobase temperature")
        if isinstance(lam, bool) or not isinstance(lam, (int, float)) or float(lam) < 0:
            raise FigureSpecError("reference Jeans sensitivity has invalid lambda")
        grouped[species].append(dict(row))
    series = []
    csv_rows = []
    for species in sorted(grouped):
        species_rows = sorted(grouped[species], key=lambda x: float(x["assumedExobaseTemperatureK"]))
        if len(species_rows) < 2:
            raise FigureSpecError("reference Jeans sensitivity requires at least two temperatures per species")
        series.append(LineSeries(species,[float(x["assumedExobaseTemperatureK"]) for x in species_rows],[float(x["referenceJeansLambda"]) for x in species_rows]))
        csv_rows.extend(species_rows)
    return [PlotPlan(
        suffix="escape_retention_sensitivity",kind="line",title=spec["title"],
        x_label="Assumed exobase temperature (K)",y_label="Reference Jeans λ (dimensionless)",series=series,csv_rows=csv_rows,
        note="Reference sensitivity only: r_exo = R_p and assumed exobase temperatures. These curves are not an inferred Jeans parameter, escape regime, escape rate, or atmospheric-loss history.",
    )]


def multistar_forcing_contributors(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    rows = b.get("radiativeContributors") or []
    resolved = []
    for row in rows:
        value = row.get("orbitMeanBolometricFluxSearth")
        if row.get("resolved") is True and isinstance(value, (int, float)) and not isinstance(value, bool):
            resolved.append(dict(row))
    if len(resolved) < 2:
        raise FigureSpecError("multi-star forcing requires at least two resolved radiative contributors")
    labels, values = [], []
    for row in resolved:
        labels.append(f"body {_text(row.get('starBodyId'))} · {_text(row.get('starClass'))} · {_text(row.get('relation'))}")
        values.append(float(row["orbitMeanBolometricFluxSearth"]))
    completeness = _text(b.get("forcingCompleteness"))
    return [_value_bar(spec["title"],"multistar_forcing_contributors",labels,values,x_label="Orbit-mean bolometric flux contribution (S_earth)",csv_rows=resolved,note=f"Resolved stellar contributions are shown separately before summation. Forcing completeness: {completeness}. Unresolved contributors are omitted, never plotted as zero.")]


# ---------------- Module 2: Geochemical Cycling ----------------

def rock_metal_ice_composition(spec: dict[str, Any]) -> list[PlotPlan]:
    rows = spec["data"]["bindings"].get("solidComposition") or []
    if not rows:
        raise FigureSpecError("solidComposition is empty")
    labels, values, csv_rows = [], [], []
    for row in rows:
        name = _text(row.get("name"))
        value = row.get("fraction")
        if name == "UNRESOLVED":
            raise FigureSpecError("solid composition row lacks a broad class name")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
            raise FigureSpecError("solid composition has invalid normalized fraction")
        labels.append(name)
        values.append(float(value))
        csv_rows.append(dict(row))
    total = sum(values)
    if total <= 0 or abs(total - 1.0) > 1e-4:
        raise FigureSpecError("solidComposition normalized fractions must sum to one")
    return [_value_bar(
        spec["title"], "rock_metal_ice_composition", labels, values,
        x_label="Normalized broad composition fraction", csv_rows=csv_rows,
        note="DSS broad rock/metal/ice composition only. These fractions are not a mineral assemblage, modal mineralogy, or mantle/crust assay.",
    )]


def atmospheric_element_budget(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    rows = b.get("elements") or []
    if not rows:
        raise FigureSpecError("atmospheric element budget is empty")
    coverage = b.get("recognizedMoleFraction")
    if isinstance(coverage, bool) or not isinstance(coverage, (int, float)) or not 0 <= float(coverage) <= 1:
        raise FigureSpecError("recognizedMoleFraction is invalid")
    labels, values, csv_rows = [], [], []
    for row in rows:
        element = _text(row.get("element"))
        value = row.get("moles_per_mole_atmosphere")
        if element == "UNRESOLVED":
            raise FigureSpecError("atmospheric element row lacks element identity")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) < 0:
            raise FigureSpecError("atmospheric element row has invalid stoichiometric amount")
        labels.append(element)
        values.append(float(value))
        csv_rows.append(dict(row))
    if not any(v > 0 for v in values):
        raise FigureSpecError("atmospheric element budget has no positive stoichiometric amounts")
    return [_value_bar(
        spec["title"], "atmospheric_element_budget", labels, values,
        x_label="Stoichiometric amount (mol element / mol measured atmosphere)", csv_rows=csv_rows,
        note=(
            f"Bookkeeping from recognized measured gas formulas only; recognized-gas coverage = "
            f"{float(coverage):.4g} of measured atmosphere. Unrecognized gases are omitted, not "
            "treated as zero elemental content. This is not a whole-planet elemental inventory."
        ),
    )]


def redox_ratio_diagnostics(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if (
        b.get("mantleOxygenFugacity") is not None
        or b.get("redoxBufferOffset") is not None
        or b.get("aqueousPh") is not None
    ):
        raise FigureSpecError("atmospheric gas-ratio figure may not contain mantle fO2, redox-buffer, or aqueous-pH results")
    rows = b.get("gasRedoxRatios") or []
    if not rows:
        raise FigureSpecError("gasRedoxRatios is empty")
    labels, values, csv_rows = [], [], []
    for row in rows:
        label = _text(row.get("label"))
        ratio = row.get("ratio")
        logged = row.get("log10_ratio")
        if label == "UNRESOLVED":
            raise FigureSpecError("gas redox-ratio row lacks label")
        if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or float(ratio) <= 0:
            raise FigureSpecError("gas redox-ratio row has invalid ratio")
        if isinstance(logged, bool) or not isinstance(logged, (int, float)):
            raise FigureSpecError("gas redox-ratio row lacks numeric log10_ratio")
        if abs(float(logged) - math.log10(float(ratio))) > 2e-5:
            raise FigureSpecError("gas redox-ratio log10 value is inconsistent with ratio")
        labels.append(label)
        values.append(float(logged))
        csv_rows.append(dict(row))
    return [_value_bar(
        spec["title"], "redox_ratio_diagnostics", labels, values,
        x_label="log10 measured atmospheric gas ratio", csv_rows=csv_rows,
        note="Ratios describe the measured present atmosphere only. They are not mantle oxygen fugacity, an FMQ/IW buffer offset, aqueous pH, or a unique geochemical history.",
    )]



# ---------------- Module 3: Ecological Energy Budgets ----------------

def capture_efficiency_sensitivity(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    intercepted = b.get("interceptedPowerW")
    rows = b.get("captureEfficiencySensitivity") or []

    if isinstance(intercepted, bool) or not isinstance(intercepted, (int, float)) or float(intercepted) <= 0:
        raise FigureSpecError("capture-efficiency sensitivity requires positive interceptedPowerW")
    if len(rows) < 2:
        raise FigureSpecError("captureEfficiencySensitivity requires at least two explicit assumption rows")

    points = []
    for row in rows:
        eff = row.get("assumedCaptureEfficiency")
        power = row.get("capturedPowerW")
        if isinstance(eff, bool) or not isinstance(eff, (int, float)) or not 0 < float(eff) <= 1:
            raise FigureSpecError("capture-efficiency sensitivity contains an invalid assumed efficiency")
        if isinstance(power, bool) or not isinstance(power, (int, float)) or float(power) < 0:
            raise FigureSpecError("capture-efficiency sensitivity contains invalid captured power")
        expected = float(intercepted) * float(eff)
        tolerance = max(abs(expected) * 1e-9, 1e-9)
        if abs(float(power) - expected) > tolerance:
            raise FigureSpecError("captured-power sensitivity is inconsistent with intercepted power × assumed efficiency")
        points.append((float(eff), float(power), dict(row)))

    points.sort(key=lambda x: x[0])
    return [PlotPlan(
        suffix="capture_efficiency_sensitivity",
        kind="line",
        title=spec["title"],
        x_label="Assumed biological capture efficiency (%)",
        y_label="Captured stellar power (W)",
        series=[LineSeries(
            "Deterministic assumption sensitivity",
            [100.0 * x[0] for x in points],
            [x[1] for x in points],
        )],
        csv_rows=[x[2] for x in points],
        note=(
            "Each point is an explicit efficiency assumption applied to the measured/derived intercepted "
            "bolometric stellar-power boundary. The curve is not an inferred capture efficiency, primary "
            "productivity, biomass estimate, or probability distribution."
        ),
        x_scale="log",
        y_scale="log" if all(x[1] > 0 for x in points) else "linear",
    )]


def trophic_transfer_sensitivity(spec: dict[str, Any]) -> list[PlotPlan]:
    rows = spec["data"]["bindings"].get("trophicTransferSensitivity") or []
    if not rows:
        raise FigureSpecError("trophicTransferSensitivity is empty")

    grouped: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        eff = row.get("transferEfficiency")
        transfers = row.get("trophicTransfers")
        remaining = row.get("remainingFraction")
        if isinstance(eff, bool) or not isinstance(eff, (int, float)) or not 0 < float(eff) < 1:
            raise FigureSpecError("trophic sensitivity contains invalid transfer efficiency")
        if isinstance(transfers, bool) or not isinstance(transfers, int) or transfers < 1:
            raise FigureSpecError("trophic sensitivity contains invalid transfer count")
        if isinstance(remaining, bool) or not isinstance(remaining, (int, float)) or not 0 <= float(remaining) <= 1:
            raise FigureSpecError("trophic sensitivity contains invalid remaining fraction")
        expected = float(eff) ** int(transfers)
        if abs(float(remaining) - expected) > max(2e-10, abs(expected) * 2e-8):
            raise FigureSpecError("trophic sensitivity remaining fraction is inconsistent with efficiency^transfers")
        grouped[float(eff)].append(dict(row))

    series = []
    csv_rows = []
    for eff in sorted(grouped):
        group = sorted(grouped[eff], key=lambda x: int(x["trophicTransfers"]))
        series.append(LineSeries(
            f"{eff * 100:g}% reference case",
            [int(x["trophicTransfers"]) for x in group],
            [float(x["remainingFraction"]) for x in group],
        ))
        csv_rows.extend(group)

    return [PlotPlan(
        suffix="trophic_transfer_sensitivity",
        kind="line",
        title=spec["title"],
        x_label="Number of trophic transfers",
        y_label="Remaining fraction of basal captured energy",
        series=series,
        csv_rows=csv_rows,
        note=(
            "Reference transfer-efficiency cases are sensitivity calculations only. They are not a universal "
            "ecological law, an inferred food-web efficiency, or evidence for the number of trophic levels."
        ),
        y_scale="log",
    )]


def energy_channel_identifiability(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    channels = b.get("channelAssessment") or []
    blocked = b.get("blockedCalculations") or []
    plans: list[PlotPlan] = []

    if channels:
        columns = ["Energy channel", "Evidence status", "Evidence refs", "Reasoning", "Uncertainty"]
        rows = []
        csv_rows = []
        for item in channels:
            channel = _text(item.get("channel"))
            status = _text(item.get("support_class"))
            if channel == "UNRESOLVED" or status == "UNRESOLVED":
                raise FigureSpecError("energy-channel assessment row lacks channel or support_class")
            refs = [str(x) for x in (item.get("evidence_refs") or [])]
            reasoning = _text(item.get("reasoning"))
            uncertainty = _text(item.get("uncertainty"))
            rows.append([channel, status, "; ".join(refs) or "NONE", reasoning, uncertainty])
            csv_rows.append({
                "channel": channel,
                "support_class": status,
                "evidence_refs": refs,
                "reasoning": reasoning,
                "uncertainty": uncertainty,
            })
        plans.append(_table(
            "Basal energy-channel evidence status",
            "energy_channel_status",
            columns,
            rows,
            csv_rows,
            note=(
                "Support class is an evidence/identifiability status only. It is not a measured energy magnitude, "
                "fractional contribution, productivity estimate, or ranking of ecological importance."
            ),
        ))

    if blocked:
        rows = []
        for item in blocked:
            quantity = _text(item.get("quantity"))
            reason = _text(item.get("reason"))
            if quantity == "UNRESOLVED":
                raise FigureSpecError("blocked ecological calculation lacks quantity")
            rows.append((quantity, f"BLOCKED: {reason}"))
        plans.append(_status_table(
            "Blocked ecological-energy quantities",
            "blocked_ecological_energy_quantities",
            rows,
            note="BLOCKED means required evidence is absent or unresolved. It never means zero energy, zero biomass, or zero productivity.",
        ))

    if not plans:
        raise FigureSpecError("energy-channel identifiability contains no channel statuses or blocked calculations")
    return plans


# ---------------- Module 10: Technological Energetics ----------------

def energy_lower_bound_ledger(spec: dict[str, Any]) -> list[PlotPlan]:
    rows = spec["data"]["bindings"].get("energyRelations") or []
    if not rows:
        raise FigureSpecError("energyRelations is empty")
    labels, values, csv_rows = [], [], []
    for row in rows:
        value = row.get("valueJ")
        if not isinstance(value, (int, float)):
            raise FigureSpecError("energy relation lacks numeric valueJ")
        label = f"{_text(row.get('findId'))}: {_text(row.get('key'))}"
        labels.append(label)
        values.append(float(value))
        csv_rows.append(dict(row))
    return [_value_bar(
        spec["title"], "energy_lower_bound_ledger", labels, values,
        x_label="Energy (J)", csv_rows=csv_rows,
        note="Values retain lower-bound/state-energy/environmental-ceiling semantics; they are not total societal energy demand.",
    )]


def energy_power_identifiability(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    energy = b.get("energyRelations") or []
    power = b.get("powerRelations") or []
    blocked = b.get("blockedCalculations") or []
    plans: list[PlotPlan] = []
    if energy:
        labels = [f"{_text(x.get('findId'))}: {_text(x.get('key'))}" for x in energy]
        values = [float(x["valueJ"]) for x in energy]
        plans.append(_value_bar(
            "Recovered energy relations", "identified_energy", labels, values,
            x_label="Energy (J)", csv_rows=[dict(x) for x in energy],
            note="Recovered energetic relations only; not system-wide energy use.",
        ))
    if power:
        labels = [f"{_text(x.get('findId'))}: {_text(x.get('key'))}" for x in power]
        values = [float(x["valueW"]) for x in power]
        plans.append(_value_bar(
            "Recovered average-power relations", "identified_power", labels, values,
            x_label="Average power (W)", csv_rows=[dict(x) for x in power],
            note="Average power appears only where an independent duration is available.",
        ))
    if blocked:
        rows = [
            (_text(x.get("quantity")), f"{_text(x.get('status'))}: {_text(x.get('reason'))}")
            for x in blocked
        ]
        plans.append(_status_table(
            "Blocked energetic quantities", "blocked_quantities", rows,
            note="Blocked means required evidence is unresolved; it does not mean zero energy or zero power.",
        ))
    if not plans:
        raise FigureSpecError("energy/power identifiability bindings contain no renderable rows")
    return plans


def process_trace_prerequisite_matrix(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    candidates = b.get("processTraceCandidates") or []
    blocked = b.get("blockedCalculations") or []
    if not candidates:
        raise FigureSpecError("processTraceCandidates is empty")
    columns = ["Recovered find", "Physical process class", "Status", "Basis"]
    rows: list[list[str]] = []
    csv_rows: list[dict[str, Any]] = []
    for c in candidates:
        rows.append([
            _text(c.get("findId")), _text(c.get("processClass")),
            _text(c.get("status")), _text(c.get("basis")),
        ])
        csv_rows.append(dict(c))
    plans = [_table(
        spec["title"], "process_trace_candidates", columns, rows, csv_rows,
        note="Compatibility classes only; technological causation and exact process conditions remain unresolved unless independently established.",
    )]
    if blocked:
        plans.append(_table(
            "Missing energetic prerequisites", "process_trace_blocked_prerequisites",
            ["Quantity", "Status", "Reason", "Missing inputs"],
            [[_text(x.get("quantity")), _text(x.get("status")), _text(x.get("reason")), ", ".join(map(str, x.get("missingInputs") or [])) or "UNRESOLVED"] for x in blocked],
            [dict(x) for x in blocked],
            note="Missing prerequisites identify evidence gaps; they are not evidence against a process.",
        ))
    return plans


def radiative_ceiling_vs_capture(spec: dict[str, Any]) -> list[PlotPlan]:
    rows = spec["data"]["bindings"].get("incidentCeilings") or []
    if not rows:
        raise FigureSpecError("incidentCeilings is empty")
    plans: list[PlotPlan] = []
    for unit in ("J", "W"):
        subset = [x for x in rows if _text(x.get("unit")) == unit]
        if not subset:
            continue
        labels = [f"{_text(x.get('findId'))}: {_text(x.get('key'))}" for x in subset]
        incident = [float(x["value"]) for x in subset]
        # Captured values are only plotted when the source explicitly supplies a numeric value.
        captured_rows = [x for x in subset if isinstance(x.get("captured"), (int, float)) and not isinstance(x.get("captured"), bool)]
        series = [LineSeries("Incident ceiling", labels, incident)]
        if len(captured_rows) == len(subset):
            series.append(LineSeries("Measured captured", labels, [float(x["captured"]) for x in subset]))
        plan = PlotPlan(
            suffix=f"radiative_ceiling__{unit.lower()}",
            kind="barh",
            title=f"{spec['title']} — {'energy' if unit == 'J' else 'power'}",
            x_label=f"{'Energy' if unit == 'J' else 'Power'} ({unit})",
            series=series,
            csv_rows=[dict(x) for x in subset],
            note="Incident radiation is an environmental ceiling. Captured technological energy/power remains unresolved unless directly supplied by evidence.",
        )
        positives = [v for s in series for v in s.y if v > 0]
        if positives and len(positives) == sum(len(s.y) for s in series) and max(positives) / min(positives) >= 1000:
            plan.x_scale = "log"
        plans.append(plan)
    if not plans:
        raise FigureSpecError("incidentCeilings contains no J or W rows")
    return plans


def measurement_formula_provenance(spec: dict[str, Any]) -> list[PlotPlan]:
    rows = spec["data"]["bindings"].get("relations") or []
    if not rows:
        raise FigureSpecError("relations is empty")
    table_rows, csv_rows = [], []
    for row in rows:
        prov = row.get("provenance") or {}
        inputs = prov.get("inputs") or []
        input_text = ", ".join(
            f"{_text(x.get('kind'))}={_text(x.get('value'))} {_text(x.get('unit'))}"
            for x in inputs
        ) or "UNRESOLVED"
        table_rows.append([
            f"{_text(row.get('findId'))}: {_text(row.get('key'))}",
            f"{_text(row.get('value'))} {_text(row.get('unit'))}",
            _text(prov.get("formula")),
            input_text,
        ])
        csv_rows.append({
            **dict(row),
            "formula": prov.get("formula"),
            "inputs": inputs,
            "assumptions": prov.get("assumptions") or [],
            "calculationBasis": prov.get("calculationBasis"),
            "sourceRule": prov.get("sourceRule"),
        })
    return [_table(
        spec["title"], "measurement_formula_provenance",
        ["Relation", "Reported value", "Formula", "Measured inputs"],
        table_rows, csv_rows,
        note="Links are deterministic calculation dependencies only; they do not establish technological organization or causation.",
    )]


# ---------------- Module 12: Cultural Transmission ----------------

def trait_frequency(spec: dict[str, Any]) -> list[PlotPlan]:
    rows = spec["data"]["bindings"].get("traitFrequencyLedger") or []
    if not rows:
        raise FigureSpecError("traitFrequencyLedger is empty")
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        family = _text(row.get("trait_family"))
        phase = _text(row.get("phase_id"))
        n = int(row.get("sample_size", 0))
        frequencies = row.get("frequencies") or {}
        if not phase or n <= 0 or not isinstance(frequencies, dict):
            raise FigureSpecError("invalid traitFrequencyLedger row")
        by_family[family].append(row)

    plans: list[PlotPlan] = []
    for family, fam_rows in by_family.items():
        phases = [f"{_text(r.get('phase_id'))}\nn={int(r.get('sample_size', 0))}" for r in fam_rows]
        states = sorted({s for r in fam_rows for s in (r.get("frequencies") or {}).keys()})
        series = []
        csv_rows = []
        for state in states:
            ys = [float((r.get("frequencies") or {}).get(state, 0.0)) for r in fam_rows]
            series.append(LineSeries(label=state, x=phases, y=ys))
        for r in fam_rows:
            base = {
                "trait_family": family,
                "phase_id": _text(r.get("phase_id")),
                "sample_size": int(r.get("sample_size", 0)),
                "observation_unit": _text(r.get("observation_unit")),
            }
            for state in states:
                csv_rows.append({**base, "trait_state": state, "frequency": float((r.get("frequencies") or {}).get(state, 0.0)), "count": int((r.get("counts") or {}).get(state, 0))})
        plans.append(PlotPlan(
            suffix=f"trait_frequency__{_slug(family)}",
            kind="line",
            title=f"{spec['title']} — {family}",
            x_label="Modeled phase",
            y_label="Recovered-sample frequency",
            series=series,
            csv_rows=csv_rows,
            note="Sample frequency only; not source-population prevalence.",
        ))
    return plans


def diversity_distance(spec: dict[str, Any]) -> list[PlotPlan]:
    bindings = spec["data"]["bindings"]
    diversity = bindings.get("diversityLedger") or []
    distances = bindings.get("phaseDistances") or []
    if not diversity and not distances:
        raise FigureSpecError("diversityLedger and phaseDistances are both empty")
    families = sorted({str(x.get("trait_family")) for x in [*diversity, *distances] if x.get("trait_family") is not None})
    plans: list[PlotPlan] = []
    for family in families:
        drows = [x for x in diversity if str(x.get("trait_family")) == family]
        if drows:
            phases = [_text(x.get("phase_id")) for x in drows]
            plans.append(PlotPlan(
                suffix=f"diversity__{_slug(family)}",
                kind="line",
                title=f"Recovered trait diversity — {family}",
                x_label="Modeled phase",
                y_label="Descriptive diversity",
                series=[
                    LineSeries("Shannon entropy", phases, [float(x.get("shannon_entropy", 0.0)) for x in drows]),
                    LineSeries("Gini-Simpson", phases, [float(x.get("gini_simpson", 0.0)) for x in drows]),
                ],
                csv_rows=[dict(x) for x in drows],
                note="Descriptive recovered-assemblage statistics only.",
            ))
        prows = [x for x in distances if str(x.get("trait_family")) == family]
        if prows:
            transitions = [f"{_text(x.get('phase_a'))}→{_text(x.get('phase_b'))}" for x in prows]
            plans.append(PlotPlan(
                suffix=f"phase_distance__{_slug(family)}",
                kind="line",
                title=f"Inter-phase total-variation distance — {family}",
                x_label="Phase transition",
                y_label="Total-variation distance",
                series=[LineSeries("TV distance", transitions, [float(x.get("total_variation_distance", 0.0)) for x in prows])],
                csv_rows=[dict(x) for x in prows],
                note="Distributional distance only; not a transmission probability.",
            ))
    return plans


def transmission_identifiability(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("modelComparisonResult", None) is not None:
        raise FigureSpecError("Module 12 modelComparisonResult must remain null")
    eligibility = b.get("modelEligibility") or {}
    rows = [(str(k), _text(v)) for k, v in eligibility.items() if not isinstance(v, (dict, list))]
    candidates = b.get("candidateModelSpecifications") or []
    for c in candidates:
        model_id = _text(c.get("model_id") or c.get("id"))
        status = _text(c.get("status") or c.get("eligibility") or "CANDIDATE_SPECIFICATION")
        rows.append((f"candidate:{model_id}", status))
    if not rows:
        raise FigureSpecError("modelEligibility contains no renderable statuses")
    return [_status_table(
        spec["title"], "transmission_model_identifiability", rows,
        note="Eligibility for later explicit model comparison; not model fit, copying, contact, or ancestry.",
    )]


# ---------------- Module 15: Model Comparison / PPC ----------------

_METHOD_KEYS = [
    ("priorPredictive", "Prior predictive"),
    ("simulationBasedCalibration", "SBC"),
    ("posteriorPredictiveChecks", "Posterior predictive checks"),
    ("psisLoo", "PSIS-LOO"),
    ("exactOrKfoldCv", "Exact/K-fold CV"),
    ("abcModelChoice", "ABC model choice"),
    ("predictiveStacking", "Predictive stacking"),
]


def evaluation_method_eligibility(spec: dict[str, Any]) -> list[PlotPlan]:
    groups = spec["data"]["bindings"].get("evaluationGroups") or []
    if not groups:
        raise FigureSpecError("evaluationGroups is empty")
    plans = []
    for group in groups:
        gid = _text(group.get("comparison_group_id"))
        eligibility = group.get("evaluationEligibility") or {}
        rows = [(label, _text(eligibility.get(key, "UNRESOLVED"))) for key, label in _METHOD_KEYS]
        rows.insert(0, ("Comparison group", gid))
        rows.insert(1, ("Plan status", _text(group.get("status"))))
        plans.append(_status_table(
            f"{spec['title']} — {gid}", f"method_eligibility__{_slug(gid)}", rows,
            note="Method eligibility only; no candidate model is evaluated by this figure.",
        ))
    return plans


def validation_diagnostics(spec: dict[str, Any]) -> list[PlotPlan]:
    groups = spec["data"]["bindings"].get("evaluationGroups") or []
    if not groups:
        raise FigureSpecError("evaluationGroups is empty")
    plans = []
    for group in groups:
        gid = _text(group.get("comparison_group_id"))
        plan = group.get("evaluationPlan") or {}
        rows = [
            ("Validation unit", _text(plan.get("validation_unit_status"))),
            ("Dependence structure", _text(plan.get("dependence_structure_status"))),
            ("Held-out/CV partition", _text(plan.get("heldout_or_cv_partition_status"))),
            ("SBC", _text(plan.get("sbc_status"))),
            ("Prior predictive", _text(plan.get("prior_predictive_status"))),
            ("ABC summary discrimination", _text(plan.get("abc_summary_discrimination_status"))),
            ("Predeclared discrepancies", ", ".join(map(str, plan.get("predeclared_discrepancies") or [])) or "NONE"),
        ]
        plans.append(_status_table(
            f"{spec['title']} — {gid}", f"validation_diagnostics__{_slug(gid)}", rows,
            note="Workflow validation status; not empirical model adequacy or causal truth.",
        ))
    return plans


def adequacy_preference_contract(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    rows = [
        ("Result status", _text(b.get("resultStatus"))),
        ("NONE_ADEQUATE allowed", _text(b.get("noneAdequateAllowed"))),
        ("MODEL_INDISTINGUISHABLE allowed", _text(b.get("modelIndistinguishableAllowed"))),
        ("Comparison groups remain separate", _text(b.get("comparisonGroupsSeparate"))),
        ("Absolute adequacy separate from preference", _text(b.get("absoluteAdequacyAndRelativePreferenceSeparate"))),
    ]
    return [_status_table(
        spec["title"], "adequacy_vs_preference_contract", rows,
        note="Epistemic/result contract only; no quantitative comparison result is implied.",
    )]


_ADAPTERS: dict[str, Callable[[dict[str, Any]], list[PlotPlan]]] = {
    "m01_equilibrium_temperature_albedo_sensitivity": equilibrium_temperature_albedo_sensitivity,
    "m01_escape_retention_sensitivity": escape_retention_sensitivity,
    "m01_multistar_forcing_contributors": multistar_forcing_contributors,
    "m02_atmospheric_element_budget": atmospheric_element_budget,
    "m02_redox_ratio_diagnostics": redox_ratio_diagnostics,
    "m02_rock_metal_ice_composition": rock_metal_ice_composition,
    "m03_capture_efficiency_sensitivity": capture_efficiency_sensitivity,
    "m03_energy_channel_identifiability": energy_channel_identifiability,
    "m03_trophic_transfer_sensitivity": trophic_transfer_sensitivity,
    "m10_energy_lower_bound_ledger": energy_lower_bound_ledger,
    "m10_energy_power_identifiability": energy_power_identifiability,
    "m10_process_trace_prerequisite_matrix": process_trace_prerequisite_matrix,
    "m10_radiative_ceiling_vs_capture": radiative_ceiling_vs_capture,
    "m10_measurement_formula_provenance": measurement_formula_provenance,
    "m12a_trait_frequency_by_phase": trait_frequency,
    "m12a_diversity_distance_by_phase": diversity_distance,
    "m12a_transmission_model_identifiability": transmission_identifiability,
    "m15a_evaluation_method_eligibility": evaluation_method_eligibility,
    "m15a_validation_diagnostics": validation_diagnostics,
    "m15a_adequacy_vs_preference_contract": adequacy_preference_contract,
}


def plans_for_spec(spec: dict[str, Any]) -> list[PlotPlan]:
    adapter = _ADAPTERS.get(spec["recipe_id"])
    if adapter is None:
        raise UnsupportedRecipeError(f"recipe not implemented in renderer v0.5.0: {spec['recipe_id']}")
    return adapter(spec)


def supported_recipes() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTERS))
