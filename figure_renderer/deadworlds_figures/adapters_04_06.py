from __future__ import annotations

from collections import defaultdict
import math
from typing import Any, Callable

from .errors import FigureSpecError
from .plans import LineSeries, PlotPlan


def _text(value: Any) -> str:
    return str(value if value is not None else "UNRESOLVED")


def _num(value: Any, *, positive: bool = False, nonnegative: bool = False, label: str = "value") -> float:
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


def _table(
    title: str,
    suffix: str,
    columns: list[str],
    rows: list[list[str]],
    csv_rows: list[dict[str, Any]],
    *,
    note: str,
) -> PlotPlan:
    if not rows:
        raise FigureSpecError(f"{suffix} has no renderable rows")
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
    return _table(
        title,
        suffix,
        ["Diagnostic", "Status"],
        [[a, b] for a, b in rows],
        [{"diagnostic": a, "status": b} for a, b in rows],
        note=note,
    )


def _present_scope(bindings: dict[str, Any]) -> tuple[float, str]:
    rho = _num(bindings.get("presentAtmosphereDensityKgM3"), positive=True, label="present-atmosphere density")
    scope = _text(bindings.get("presentAtmosphereScope"))
    if scope != "PRESENT_STATE_ONLY":
        raise FigureSpecError("present-atmosphere mechanics must be explicitly scoped to PRESENT_STATE_ONLY")
    if bindings.get("biosphereEraGasDensityKgM3") is not None:
        raise FigureSpecError("present-atmosphere mechanics may not substitute a biosphere-era gas density")
    return rho, scope


# ---------------- Module 4: Biomechanics Scaling ----------------

def gravity_jump_sensitivity(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    g = _num(b.get("gravityMS2"), positive=True, label="gravityMS2")
    if b.get("actualLaunchSpeedMS") is not None or b.get("actualLocomotorPowerW") is not None:
        raise FigureSpecError("jump sensitivity may not contain inferred launch speed or locomotor power")
    rows = b.get("jumpSensitivity") or []
    if len(rows) < 2:
        raise FigureSpecError("jumpSensitivity requires at least two explicit launch-speed rows")

    cleaned = []
    for row in rows:
        v = _num(row.get("launchSpeedMS"), positive=True, label="launchSpeedMS")
        height = _num(row.get("verticalHeightM"), nonnegative=True, label="verticalHeightM")
        hang = _num(row.get("hangTimeS"), nonnegative=True, label="hangTimeS")
        rng = _num(row.get("vacuumRange45degM"), nonnegative=True, label="vacuumRange45degM")
        tol_h = max(1e-8, (v * v / (2 * g)) * 2e-8)
        tol_t = max(1e-8, (2 * v / g) * 2e-8)
        tol_r = max(1e-8, (v * v / g) * 2e-8)
        if abs(height - v * v / (2 * g)) > tol_h or abs(hang - 2 * v / g) > tol_t or abs(rng - v * v / g) > tol_r:
            raise FigureSpecError("jump sensitivity is inconsistent with the stated ballistic equations")
        cleaned.append((v, height, hang, rng, dict(row)))
    cleaned.sort(key=lambda x: x[0])

    xs = [x[0] for x in cleaned]
    note = (
        "Ballistic mechanics sensitivity only. Launch speed is an explicit parameter; "
        "drag, morphology, muscle/actuator power, and organism performance are not inferred."
    )
    length_plan = PlotPlan(
        suffix="jump_distance_sensitivity",
        kind="line",
        title=f"{spec['title']} — distance envelope",
        x_label="Assumed launch speed (m/s)",
        y_label="Ballistic distance (m)",
        series=[
            LineSeries("Vertical height", xs, [x[1] for x in cleaned]),
            LineSeries("45° vacuum range", xs, [x[3] for x in cleaned]),
        ],
        csv_rows=[x[4] for x in cleaned],
        note=note,
        x_scale="log",
        y_scale="log",
    )
    time_plan = PlotPlan(
        suffix="jump_hang_time_sensitivity",
        kind="line",
        title=f"{spec['title']} — hang-time envelope",
        x_label="Assumed launch speed (m/s)",
        y_label="Ballistic hang time (s)",
        series=[LineSeries("Hang time", xs, [x[2] for x in cleaned])],
        csv_rows=[x[4] for x in cleaned],
        note=note,
        x_scale="log",
        y_scale="log",
    )
    return [length_plan, time_plan]


def froude_similarity_grid(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    g = _num(b.get("gravityMS2"), positive=True, label="gravityMS2")
    if b.get("actualCharacteristicLengthM") is not None or b.get("actualSpeedMS") is not None or b.get("gaitTransitionResult") is not None:
        raise FigureSpecError("Froude sensitivity may not contain inferred organism scale, speed, or gait transition")
    rows = b.get("froudeSensitivity") or []
    if not rows:
        raise FigureSpecError("froudeSensitivity is empty")
    grouped: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        length = _num(row.get("characteristicLengthM"), positive=True, label="characteristicLengthM")
        speed = _num(row.get("speedMS"), positive=True, label="speedMS")
        fr = _num(row.get("froude"), nonnegative=True, label="froude")
        expected = speed * speed / (g * length)
        if abs(fr - expected) > max(1e-8, abs(expected) * 2e-8):
            raise FigureSpecError("Froude sensitivity is inconsistent with v^2/(gL)")
        grouped[length].append(dict(row))
    series, csv_rows = [], []
    for length in sorted(grouped):
        group = sorted(grouped[length], key=lambda x: float(x["speedMS"]))
        series.append(LineSeries(
            f"L = {length:g} m",
            [float(x["speedMS"]) for x in group],
            [float(x["froude"]) for x in group],
        ))
        csv_rows.extend(group)
    return [PlotPlan(
        suffix="froude_similarity_grid",
        kind="line",
        title=spec["title"],
        x_label="Assumed speed (m/s)",
        y_label="Froude number, v²/(gL)",
        series=series,
        csv_rows=csv_rows,
        note=(
            "Dimensionless dynamic-similarity sensitivity only. Characteristic length and speed are explicit "
            "parameters; no Earth gait threshold, alien anatomy, or actual locomotor state is inferred."
        ),
        x_scale="log",
        y_scale="log",
    )]


def dynamic_pressure_grid(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    rho, _ = _present_scope(b)
    rows = b.get("dynamicPressureSensitivity") or []
    if not rows:
        raise FigureSpecError("dynamicPressureSensitivity is empty")
    points = []
    for row in rows:
        speed = _num(row.get("speedMS"), positive=True, label="speedMS")
        q = _num(row.get("dynamicPressurePa"), nonnegative=True, label="dynamicPressurePa")
        expected = 0.5 * rho * speed * speed
        if abs(q - expected) > max(1e-8, abs(expected) * 2e-8):
            raise FigureSpecError("dynamic pressure is inconsistent with q=0.5 rho v^2")
        points.append((speed, q, dict(row)))
    points.sort(key=lambda x: x[0])
    return [PlotPlan(
        suffix="dynamic_pressure_grid",
        kind="line",
        title=spec["title"],
        x_label="Speed in measured present atmosphere (m/s)",
        y_label="Dynamic pressure (Pa)",
        series=[LineSeries("Present-state q", [x[0] for x in points], [x[1] for x in points])],
        csv_rows=[x[2] for x in points],
        note=(
            "Uses measured present-atmosphere density only. It must not be substituted for an unresolved "
            "biosphere-era atmosphere or treated as organism-specific aerodynamic loading."
        ),
        x_scale="log",
        y_scale="log",
    )]


def terminal_velocity_grid(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    rho, _ = _present_scope(b)
    g = _num(b.get("gravityMS2"), positive=True, label="gravityMS2")
    if b.get("actualBallisticCoefficientKgM2") is not None:
        raise FigureSpecError("terminal-velocity sensitivity may not contain an inferred ballistic coefficient")
    rows = b.get("terminalVelocitySensitivity") or []
    if not rows:
        raise FigureSpecError("terminalVelocitySensitivity is empty")
    points = []
    for row in rows:
        beta = _num(row.get("ballisticCoefficientKgM2"), positive=True, label="ballisticCoefficientKgM2")
        vt = _num(row.get("terminalVelocityMS"), positive=True, label="terminalVelocityMS")
        expected = math.sqrt(2 * beta * g / rho)
        if abs(vt - expected) > max(1e-8, abs(expected) * 2e-8):
            raise FigureSpecError("terminal velocity is inconsistent with the stated ballistic-coefficient sensitivity")
        points.append((beta, vt, dict(row)))
    points.sort(key=lambda x: x[0])
    return [PlotPlan(
        suffix="terminal_velocity_grid",
        kind="line",
        title=spec["title"],
        x_label="Assumed ballistic coefficient β (kg/m²)",
        y_label="Terminal velocity (m/s)",
        series=[LineSeries("Constant-density sensitivity", [x[0] for x in points], [x[1] for x in points])],
        csv_rows=[x[2] for x in points],
        note=(
            "Ballistic coefficient is an explicit sensitivity parameter. Constant-density quadratic drag does "
            "not establish organism mass, drag coefficient, projected area, or biosphere-era terminal velocity."
        ),
        x_scale="log",
        y_scale="log",
    )]


def lift_loading_grid(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    rho, _ = _present_scope(b)
    if b.get("flightFeasibilityResult") is not None or b.get("organismWingLoadingResult") is not None:
        raise FigureSpecError("lift-loading sensitivity may not contain organism-specific flight results")
    rows = b.get("liftLoadingSensitivity") or []
    if not rows:
        raise FigureSpecError("liftLoadingSensitivity is empty")
    grouped: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        speed = _num(row.get("speedMS"), positive=True, label="speedMS")
        cl = _num(row.get("assumedLiftCoefficient"), positive=True, label="assumedLiftCoefficient")
        loading = _num(row.get("weightPerAreaPa"), nonnegative=True, label="weightPerAreaPa")
        expected = 0.5 * rho * speed * speed * cl
        if abs(loading - expected) > max(1e-8, abs(expected) * 2e-8):
            raise FigureSpecError("lift loading is inconsistent with W/S=q C_L")
        grouped[cl].append(dict(row))
    series, csv_rows = [], []
    for cl in sorted(grouped):
        group = sorted(grouped[cl], key=lambda x: float(x["speedMS"]))
        series.append(LineSeries(
            f"C_L = {cl:g}",
            [float(x["speedMS"]) for x in group],
            [float(x["weightPerAreaPa"]) for x in group],
        ))
        csv_rows.extend(group)
    return [PlotPlan(
        suffix="lift_loading_grid",
        kind="line",
        title=spec["title"],
        x_label="Assumed speed in present atmosphere (m/s)",
        y_label="Conditional W/S = q C_L (Pa)",
        series=series,
        csv_rows=csv_rows,
        note=(
            "Conditional lift balance in the measured present atmosphere only. Speed and C_L are explicit "
            "parameters; this is not evidence that flight evolved or that a specific organism can fly."
        ),
        x_scale="log",
        y_scale="log",
    )]


def self_weight_support_scaling(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    g = _num(b.get("gravityMS2"), positive=True, label="gravityMS2")
    if b.get("materialStrengthPa") is not None or b.get("failureSizeLimitM") is not None:
        raise FigureSpecError("self-weight sensitivity may not contain material strength or a failure-size result")
    rows = b.get("selfWeightStressSensitivity") or []
    if not rows:
        raise FigureSpecError("selfWeightStressSensitivity is empty")
    grouped: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rho_body = _num(row.get("assumedBulkDensityKgM3"), positive=True, label="assumedBulkDensityKgM3")
        height = _num(row.get("characteristicHeightM"), positive=True, label="characteristicHeightM")
        stress = _num(row.get("axialSelfWeightStressPa"), nonnegative=True, label="axialSelfWeightStressPa")
        expected = rho_body * g * height
        if abs(stress - expected) > max(1e-7, abs(expected) * 2e-8):
            raise FigureSpecError("self-weight stress is inconsistent with rho_body g L")
        grouped[rho_body].append(dict(row))
    series, csv_rows = [], []
    for rho_body in sorted(grouped):
        group = sorted(grouped[rho_body], key=lambda x: float(x["characteristicHeightM"]))
        series.append(LineSeries(
            f"ρ_body = {rho_body:g} kg/m³",
            [float(x["characteristicHeightM"]) for x in group],
            [float(x["axialSelfWeightStressPa"]) for x in group],
        ))
        csv_rows.extend(group)
    return [PlotPlan(
        suffix="self_weight_support_scaling",
        kind="line",
        title=spec["title"],
        x_label="Assumed characteristic height (m)",
        y_label="Axial self-weight stress ρgL (Pa)",
        series=series,
        csv_rows=csv_rows,
        note=(
            "Self-weight stress sensitivity only. Body density and height are explicit parameters; material "
            "strength, shape, buckling, tissue failure, safety factor, and maximum organism size remain unresolved."
        ),
        x_scale="log",
        y_scale="log",
    )]


# ---------------- Module 5: Sensory Ecology ----------------

def stellar_emission_peak_context(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("surfaceSpectralIrradiance") is not None or b.get("receptorOptimumWavelength") is not None:
        raise FigureSpecError("stellar context may not contain a surface spectrum or receptor optimum")
    rows = b.get("stellarSpectralPeaks") or []
    if not rows:
        raise FigureSpecError("stellarSpectralPeaks is empty")
    labels, values, csv_rows = [], [], []
    for row in rows:
        temp = _num(row.get("temperatureK"), positive=True, label="temperatureK")
        peak = _num(row.get("peakWavelengthNm"), positive=True, label="peakWavelengthNm")
        expected = 2897771.955 / temp
        if abs(peak - expected) > max(1e-4, expected * 2e-7):
            raise FigureSpecError("stellar peak wavelength is inconsistent with Wien's law")
        labels.append(f"body {_text(row.get('starBodyId'))} · {_text(row.get('relation'))}")
        values.append(peak)
        csv_rows.append(dict(row))
    positives = [x for x in values if x > 0]
    scale = "log" if positives and max(positives) / min(positives) >= 100 else "linear"
    return [PlotPlan(
        suffix="stellar_emission_peak_context",
        kind="barh",
        title=spec["title"],
        x_label="Wien-law characteristic emission peak (nm)",
        series=[LineSeries("Characteristic peak", labels, values)],
        csv_rows=csv_rows,
        note=(
            "Blackbody characteristic emission peaks are stellar irradiation context only. They are not "
            "surface spectral irradiance, receptor sensitivity, or an evolved sensory optimum."
        ),
        x_scale=scale,
    )]


def acoustic_sound_speed_sensitivity(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("biosphereEraSoundSpeed") is not None or b.get("attenuationResult") is not None or b.get("activeSpaceResult") is not None:
        raise FigureSpecError("acoustic sensitivity may not contain paleo sound speed, attenuation, or active-space results")
    rows = b.get("acousticSoundSpeedSensitivity") or []
    if len(rows) < 2:
        raise FigureSpecError("acousticSoundSpeedSensitivity requires at least two gamma cases")
    points = []
    invariant = None
    for row in rows:
        gamma = _num(row.get("assumedHeatCapacityRatio"), positive=True, label="assumedHeatCapacityRatio")
        speed = _num(row.get("soundSpeedMS"), positive=True, label="soundSpeedMS")
        k = speed * speed / gamma
        invariant = k if invariant is None else invariant
        if abs(k - invariant) > max(1e-5, abs(invariant) * 2e-7):
            raise FigureSpecError("sound-speed sensitivity is internally inconsistent across gamma assumptions")
        points.append((gamma, speed, dict(row)))
    points.sort(key=lambda x: x[0])
    return [PlotPlan(
        suffix="acoustic_sound_speed_sensitivity",
        kind="line",
        title=spec["title"],
        x_label="Assumed heat-capacity ratio γ",
        y_label="Ideal-gas sound speed (m/s)",
        series=[LineSeries("Present-medium sensitivity", [x[0] for x in points], [x[1] for x in points])],
        csv_rows=[x[2] for x in points],
        note=(
            "Present-atmosphere ideal-gas sensitivity only. Gamma is parameterized; biosphere-era medium, "
            "attenuation, humidity, turbulence, source spectrum, noise, and receptor threshold remain unresolved."
        ),
    )]


def diffraction_resolution_sensitivity(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("actualApertureM") is not None or b.get("actualReceptorBand") is not None or b.get("actualVisualAcuity") is not None:
        raise FigureSpecError("diffraction sensitivity may not contain inferred aperture, receptor band, or acuity")
    rows = b.get("diffractionSensitivity") or []
    if not rows:
        raise FigureSpecError("diffractionSensitivity is empty")
    grouped: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        wavelength = _num(row.get("wavelengthUm"), positive=True, label="wavelengthUm")
        aperture = _num(row.get("apertureM"), positive=True, label="apertureM")
        rad = _num(row.get("angularResolutionRad"), positive=True, label="angularResolutionRad")
        deg = _num(row.get("angularResolutionDeg"), positive=True, label="angularResolutionDeg")
        expected = 1.22 * (wavelength * 1e-6) / aperture
        if abs(rad - expected) > max(2e-12, expected * 2e-7) or abs(deg - expected * 180 / math.pi) > max(2e-10, deg * 2e-7):
            raise FigureSpecError("diffraction sensitivity is inconsistent with the Rayleigh lambda/D relation")
        grouped[aperture].append(dict(row))
    series, csv_rows = [], []
    for aperture in sorted(grouped):
        group = sorted(grouped[aperture], key=lambda x: float(x["wavelengthUm"]))
        series.append(LineSeries(
            f"D = {aperture:g} m",
            [float(x["wavelengthUm"]) for x in group],
            [float(x["angularResolutionDeg"]) for x in group],
        ))
        csv_rows.extend(group)
    return [PlotPlan(
        suffix="diffraction_resolution_sensitivity",
        kind="line",
        title=spec["title"],
        x_label="Assumed wavelength (µm)",
        y_label="Diffraction-limited angular resolution (deg)",
        series=series,
        csv_rows=csv_rows,
        note=(
            "Rayleigh diffraction sensitivity only. Wavelength and aperture are explicit parameters; receptor "
            "sampling, contrast, noise, neural processing, and any alien eye or sensory band remain unresolved."
        ),
        x_scale="log",
        y_scale="log",
    )]


def sensory_channel_identifiability(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("evolvedSensoryModalityPrevalence") is not None or b.get("channelImportanceRanking") is not None:
        raise FigureSpecError("sensory carrier figure may not contain prevalence or importance rankings")
    channels = b.get("channelConstraints") or []
    blocked = b.get("blockedCalculations") or []
    plans: list[PlotPlan] = []
    if channels:
        rows = []
        csv_rows = []
        for row in channels:
            channel = _text(row.get("channel"))
            status = _text(row.get("presentStatus"))
            if channel == "UNRESOLVED" or status == "UNRESOLVED":
                raise FigureSpecError("sensory channel row lacks channel or presentStatus")
            rows.append([channel, status, _text(row.get("constraint"))])
            csv_rows.append(dict(row))
        plans.append(_table(
            spec["title"],
            "sensory_channel_identifiability",
            ["Carrier/channel", "Present-state status", "Constraint"],
            rows,
            csv_rows,
            note=(
                "Physical carrier state and identifiability only. Present conditions do not establish which "
                "sensory modalities evolved, their importance, prevalence, active space, or historical availability."
            ),
        ))
    if blocked:
        plans.append(_status_table(
            "Blocked sensory quantities",
            "blocked_sensory_quantities",
            [(_text(x.get("quantity")), f"BLOCKED: {_text(x.get('reason'))}") for x in blocked],
            note="BLOCKED identifies missing evidence or model inputs; it does not mean zero sensory capability.",
        ))
    if not plans:
        raise FigureSpecError("sensory channel identifiability has no renderable rows")
    return plans


# ---------------- Module 6: Non-acoustic Communication ----------------

_HIDDEN_M6 = (
    "RECEPTOR_HYPOTHESIS_PRESENT",
    "LIGHT_PRODUCTION_HYPOTHESIS_PRESENT",
    "ELECTRIC_SIGNAL_PRODUCTION_HYPOTHESIS_PRESENT",
    "HIDDEN_BIOLOGY",
)


def _public_channel_ledger(bindings: dict[str, Any]) -> list[dict[str, Any]]:
    rows = bindings.get("channelLedger") or []
    if not rows:
        raise FigureSpecError("public channelLedger is empty")
    cleaned = []
    for row in rows:
        if "receiverStatus" in row or "senderStatus" in row or "blocked" in row:
            raise FigureSpecError("raw hidden-biological channel-ledger fields are forbidden")
        text = str(row)
        if any(marker.lower() in text.lower() for marker in _HIDDEN_M6):
            raise FigureSpecError("hidden biological sender/receiver reconstruction leaked into public channel ledger")
        channel = _text(row.get("channel"))
        carrier = _text(row.get("carrierStatus"))
        sender = _text(row.get("senderPrerequisiteStatus"))
        receiver = _text(row.get("receiverPrerequisiteStatus"))
        status = _text(row.get("status"))
        if "UNRESOLVED" in {channel, carrier, sender, receiver, status}:
            raise FigureSpecError("public communication channel row lacks required status fields")
        if sender != "UNRESOLVED_FROM_PUBLIC_EVIDENCE" or receiver != "UNRESOLVED_FROM_PUBLIC_EVIDENCE":
            raise FigureSpecError("public sender/receiver prerequisites must remain unresolved without evidence")
        cleaned.append(dict(row))
    return cleaned


def communication_channel_identifiability_matrix(spec: dict[str, Any]) -> list[PlotPlan]:
    ledger = _public_channel_ledger(spec["data"]["bindings"])
    rows, csv_rows = [], []
    for row in ledger:
        rows.append([
            _text(row.get("channel")),
            _text(row.get("status")),
            _text(row.get("carrierStatus")),
            _text(row.get("quantitativeRangeStatus")),
            _text(row.get("informationCapacityStatus")),
        ])
        csv_rows.append(dict(row))
    return [_table(
        spec["title"],
        "communication_channel_identifiability_matrix",
        ["Channel", "Public status", "Carrier context", "Range status", "Information-capacity status"],
        rows,
        csv_rows,
        note=(
            "Public physical-carrier identifiability only. Hidden biological sender/receiver reconstruction is "
            "excluded; feasibility is not evidence that a communication system evolved."
        ),
    )]


def visual_angular_geometry_sensitivity(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("visibilityResult") is not None or b.get("acuityResult") is not None or b.get("communicationRangeResult") is not None:
        raise FigureSpecError("visual geometry may not contain visibility, acuity, or communication-range results")
    rows = b.get("visualAngularSizeSensitivity") or []
    if not rows:
        raise FigureSpecError("visualAngularSizeSensitivity is empty")
    grouped: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        size = _num(row.get("assumedDisplaySizeM"), positive=True, label="assumedDisplaySizeM")
        distance = _num(row.get("assumedDistanceM"), positive=True, label="assumedDistanceM")
        rad = _num(row.get("angularSizeRad"), positive=True, label="angularSizeRad")
        deg = _num(row.get("angularSizeDeg"), positive=True, label="angularSizeDeg")
        expected = 2 * math.atan(size / (2 * distance))
        if abs(rad - expected) > max(2e-12, expected * 2e-7) or abs(deg - expected * 180 / math.pi) > max(2e-10, deg * 2e-7):
            raise FigureSpecError("visual angular-size sensitivity is inconsistent with pure geometry")
        grouped[size].append(dict(row))
    series, csv_rows = [], []
    for size in sorted(grouped):
        group = sorted(grouped[size], key=lambda x: float(x["assumedDistanceM"]))
        series.append(LineSeries(
            f"display = {size:g} m",
            [float(x["assumedDistanceM"]) for x in group],
            [float(x["angularSizeDeg"]) for x in group],
        ))
        csv_rows.extend(group)
    return [PlotPlan(
        suffix="visual_angular_geometry_sensitivity",
        kind="line",
        title=spec["title"],
        x_label="Assumed distance (m)",
        y_label="Angular size (deg)",
        series=series,
        csv_rows=csv_rows,
        note=(
            "Pure angular-size geometry only. Display size and distance are explicit assumptions; angular size "
            "does not establish visibility, contrast, receptor acuity, detectability, or communication range."
        ),
        x_scale="log",
        y_scale="log",
    )]


def sender_medium_receiver_prerequisites(spec: dict[str, Any]) -> list[PlotPlan]:
    ledger = _public_channel_ledger(spec["data"]["bindings"])
    rows, csv_rows = [], []
    for row in ledger:
        rows.append([
            _text(row.get("channel")),
            _text(row.get("senderPrerequisiteStatus")),
            _text(row.get("carrierStatus")),
            _text(row.get("receiverPrerequisiteStatus")),
            _text(row.get("status")),
        ])
        csv_rows.append(dict(row))
    return [_table(
        spec["title"],
        "sender_medium_receiver_prerequisites",
        ["Channel", "Sender prerequisite", "Medium/carrier", "Receiver prerequisite", "Public status"],
        rows,
        csv_rows,
        note=(
            "Sender and receiver prerequisites remain unresolved from public evidence. Physical carrier context "
            "alone cannot license an evolved communication system or quantitative performance."
        ),
    )]


def multimodal_constraint_map(spec: dict[str, Any]) -> list[PlotPlan]:
    b = spec["data"]["bindings"]
    if b.get("channelRanking") is not None or b.get("evolvedPreference") is not None:
        raise FigureSpecError("multimodal constraint map may not contain channel ranking or evolved preference")
    ledger = _public_channel_ledger(b)
    blocked = b.get("blockedCalculations") or []
    plans = [_table(
        spec["title"],
        "multimodal_constraint_map",
        ["Channel", "Public status", "Carrier context", "Constraint"],
        [[
            _text(x.get("channel")),
            _text(x.get("status")),
            _text(x.get("carrierStatus")),
            _text(x.get("constraint")),
        ] for x in ledger],
        [dict(x) for x in ledger],
        note=(
            "Cross-channel constraint map only. It does not rank modalities, infer evolutionary adoption, "
            "or quantify range, bandwidth, energetic cost, or information capacity."
        ),
    )]
    if blocked:
        plans.append(_status_table(
            "Blocked non-acoustic communication quantities",
            "blocked_non_acoustic_quantities",
            [(_text(x.get("quantity")), f"BLOCKED: {_text(x.get('reason'))}") for x in blocked],
            note="BLOCKED identifies missing channel-specific evidence; it never means zero capability or zero signal.",
        ))
    return plans


ADAPTERS_04_06: dict[str, Callable[[dict[str, Any]], list[PlotPlan]]] = {
    "m04_gravity_jump_sensitivity": gravity_jump_sensitivity,
    "m04_froude_similarity_grid": froude_similarity_grid,
    "m04_dynamic_pressure_grid": dynamic_pressure_grid,
    "m04_terminal_velocity_grid": terminal_velocity_grid,
    "m04_lift_loading_grid": lift_loading_grid,
    "m04_self_weight_support_scaling": self_weight_support_scaling,
    "m05_stellar_emission_peak_context": stellar_emission_peak_context,
    "m05_acoustic_sound_speed_sensitivity": acoustic_sound_speed_sensitivity,
    "m05_diffraction_resolution_sensitivity": diffraction_resolution_sensitivity,
    "m05_channel_identifiability": sensory_channel_identifiability,
    "m06_channel_identifiability_matrix": communication_channel_identifiability_matrix,
    "m06_visual_angular_geometry_sensitivity": visual_angular_geometry_sensitivity,
    "m06_sender_medium_receiver_prerequisites": sender_medium_receiver_prerequisites,
    "m06_multimodal_constraint_map": multimodal_constraint_map,
}
