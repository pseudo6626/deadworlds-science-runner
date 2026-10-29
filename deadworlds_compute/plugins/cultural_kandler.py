from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import arviz as az
import numpy as np

from ..contracts import ComputeJob
from .base import PluginRun

OTHER_LABEL = "__UNOBSERVED_OR_NEW__"


@dataclass(frozen=True)
class CulturalTransitionData:
    trait_family: str
    phase_from: str
    phase_to: str
    steps: int
    labels: tuple[str, ...]
    counts_t1: np.ndarray
    counts_t2: np.ndarray

    @property
    def n1(self) -> int:
        return int(self.counts_t1.sum())

    @property
    def n2(self) -> int:
        return int(self.counts_t2.sum())


@dataclass(frozen=True)
class CulturalModelConfig:
    population_size: int
    innovation_rate: float
    replacement_low: float
    replacement_high: float
    b_low: float
    b_high: float
    dirichlet_alpha_observed: float
    dirichlet_alpha_unobserved: float
    simulations: int
    retain: int
    posterior_predictive_draws: int
    time_averaging_mode: str
    require_survivor_count_match: bool


def _validate_counts(value: Any, name: str) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{name} must be a non-empty object of variant -> non-negative integer count")
    out: dict[str, int] = {}
    for raw_key, raw_count in value.items():
        key = str(raw_key).strip()
        if not key or key == OTHER_LABEL:
            raise ValueError(f"{name} contains an invalid/reserved variant label: {raw_key!r}")
        if isinstance(raw_count, bool) or not isinstance(raw_count, (int, np.integer)) or int(raw_count) < 0:
            raise ValueError(f"{name}[{key!r}] must be a non-negative integer")
        if int(raw_count) > 0:
            out[key] = int(raw_count)
    if not out:
        raise ValueError(f"{name} must contain at least one positive count")
    return out


def parse_transition(job: ComputeJob) -> CulturalTransitionData:
    data = job.input_data
    trait_family = str(data.get("trait_family") or "").strip()
    phase_from = str(data.get("phase_from") or "").strip()
    phase_to = str(data.get("phase_to") or "").strip()
    steps = data.get("steps")
    if not trait_family or not phase_from or not phase_to or phase_from == phase_to:
        raise ValueError("cultural transmission input requires trait_family and distinct phase_from/phase_to")
    if isinstance(steps, bool) or not isinstance(steps, (int, np.integer)) or not (1 <= int(steps) <= 10000):
        raise ValueError("input_data.steps must be an independently justified integer in [1, 10000]")

    c1 = _validate_counts(data.get("counts_t1"), "counts_t1")
    c2 = _validate_counts(data.get("counts_t2"), "counts_t2")
    labels = tuple(sorted(c1)) + (OTHER_LABEL,)
    initial = np.asarray([c1[k] for k in labels[:-1]] + [0], dtype=np.int64)
    later_other = sum(v for k, v in c2.items() if k not in c1)
    later = np.asarray([c2.get(k, 0) for k in labels[:-1]] + [later_other], dtype=np.int64)
    if initial.sum() < 2 or later.sum() < 2:
        raise ValueError("both phases require at least two recovered observations")
    return CulturalTransitionData(
        trait_family=trait_family,
        phase_from=phase_from,
        phase_to=phase_to,
        steps=int(steps),
        labels=labels,
        counts_t1=initial,
        counts_t2=later,
    )


def parse_config(job: ComputeJob, *, frequency_dependent: bool) -> CulturalModelConfig:
    p = job.parameters

    def finite(name: str) -> float:
        v = p.get(name)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
            raise ValueError(f"model parameter {name} must be explicitly supplied and finite")
        return float(v)

    population_size = p.get("population_size")
    simulations = p.get("simulations", 5000)
    retain = p.get("retain", 500)
    ppc_draws = p.get("posterior_predictive_draws", 1000)
    for name, value, low, high in [
        ("population_size", population_size, 2, 2_000_000),
        ("simulations", simulations, 200, 2_000_000),
        ("retain", retain, 50, 200_000),
        ("posterior_predictive_draws", ppc_draws, 100, 100_000),
    ]:
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or not (low <= int(value) <= high):
            raise ValueError(f"model parameter {name} must be an integer in [{low}, {high}]")

    innovation = finite("innovation_rate")
    r_low = finite("replacement_fraction_low")
    r_high = finite("replacement_fraction_high")
    alpha_obs = finite("dirichlet_alpha_observed")
    alpha_other = finite("dirichlet_alpha_unobserved")
    if not (0 <= innovation < 1):
        raise ValueError("innovation_rate must be in [0, 1)")
    if not (0 < r_low <= r_high <= 1):
        raise ValueError("replacement fraction prior must satisfy 0 < low <= high <= 1")
    if alpha_obs <= 0 or alpha_other <= 0:
        raise ValueError("Dirichlet alpha values must be positive")
    if int(retain) >= int(simulations):
        raise ValueError("retain must be smaller than simulations")

    if frequency_dependent:
        b_low = finite("b_freq_low")
        b_high = finite("b_freq_high")
        if not (-1 <= b_low <= b_high <= 1):
            raise ValueError("b_freq prior bounds must satisfy -1 <= low <= high <= 1")
    else:
        b_low = b_high = 0.0

    mode = str(p.get("time_averaging_mode") or "").strip().upper()
    if mode not in {"UNIFORM_WITHIN_INTERVAL", "TERMINAL_ONLY"}:
        raise ValueError("time_averaging_mode must be explicitly UNIFORM_WITHIN_INTERVAL or TERMINAL_ONLY")

    return CulturalModelConfig(
        population_size=int(population_size),
        innovation_rate=innovation,
        replacement_low=r_low,
        replacement_high=r_high,
        b_low=b_low,
        b_high=b_high,
        dirichlet_alpha_observed=alpha_obs,
        dirichlet_alpha_unobserved=alpha_other,
        simulations=int(simulations),
        retain=int(retain),
        posterior_predictive_draws=int(ppc_draws),
        time_averaging_mode=mode,
        require_survivor_count_match=bool(p.get("require_survivor_count_match", True)),
    )


def kandler_replacement_probabilities(
    survivors: np.ndarray,
    *,
    b_freq: float,
    innovation_rate: float,
) -> np.ndarray:
    """Replacement probabilities for the Kandler/Shennan frequency model.

    For each currently represented type, the unnormalized preference is

        max(0, f_i + b_freq * (k * f_i - 1)) * (1 - mu)

    where k is the number of non-zero types and f_i is the post-removal relative
    frequency. The final aggregate bucket represents unobserved/new variants and
    receives the innovation mass mu before normalization.

    This is the published frequency-dependent rule specialized to the fixed-size,
    aggregate-innovation case used by this plugin. b_freq=0 is the neutral model.
    """
    counts = np.asarray(survivors, dtype=np.int64)
    total = int(counts.sum())
    if total <= 0:
        raise ValueError("all cultural variants were removed; replacement probabilities undefined")
    freq = counts.astype(float) / total
    k = max(1, int(np.count_nonzero(counts)))
    raw = np.maximum(0.0, freq + float(b_freq) * (k * freq - 1.0))
    raw *= 1.0 - float(innovation_rate)
    raw[-1] += float(innovation_rate)
    z = float(raw.sum())
    if not math.isfinite(z) or z <= 0:
        raise ValueError("frequency-dependent replacement rule produced no valid probability mass")
    return raw / z


def _remove_multivariate_hypergeometric(rng: np.random.Generator, counts: np.ndarray, draws: int) -> np.ndarray:
    if draws <= 0:
        return np.zeros_like(counts)
    if draws >= int(counts.sum()):
        return counts.copy()
    method = getattr(rng, "multivariate_hypergeometric", None)
    if method is not None:
        return np.asarray(method(counts, draws), dtype=np.int64)
    # Exact sequential fallback.
    remaining_total = int(counts.sum())
    remaining_draws = int(draws)
    out = np.zeros_like(counts)
    for i in range(len(counts) - 1):
        take = int(rng.hypergeometric(int(counts[i]), remaining_total - int(counts[i]), remaining_draws))
        out[i] = take
        remaining_draws -= take
        remaining_total -= int(counts[i])
    out[-1] = remaining_draws
    return out


def _initial_population(
    rng: np.random.Generator,
    transition: CulturalTransitionData,
    config: CulturalModelConfig,
) -> np.ndarray:
    if config.population_size < max(transition.n1, transition.n2):
        raise ValueError("population_size must be at least as large as both recovered sample sizes")
    alpha = np.asarray(
        [
            *(transition.counts_t1[:-1].astype(float) + config.dirichlet_alpha_observed),
            config.dirichlet_alpha_unobserved,
        ],
        dtype=float,
    )
    proportions = rng.dirichlet(alpha)
    return rng.multinomial(config.population_size, proportions).astype(np.int64)


def simulate_transition(
    rng: np.random.Generator,
    transition: CulturalTransitionData,
    config: CulturalModelConfig,
    *,
    replacement_fraction: float,
    b_freq: float,
) -> np.ndarray:
    """Generate one theoretical recovered t2 sample for a fixed-size population."""
    population = _initial_population(rng, transition, config)
    snapshots: list[np.ndarray] = []
    u = int(math.floor(float(replacement_fraction) * config.population_size))
    if not (0 <= u <= config.population_size):
        raise ValueError("replacement fraction generated invalid replacement count")

    for _ in range(transition.steps):
        removed = _remove_multivariate_hypergeometric(rng, population, u)
        survivors = population - removed
        probs = kandler_replacement_probabilities(
            survivors,
            b_freq=b_freq,
            innovation_rate=config.innovation_rate,
        )
        additions = rng.multinomial(u, probs).astype(np.int64)
        population = survivors + additions
        snapshots.append(population.astype(float) / float(config.population_size))

    if config.time_averaging_mode == "UNIFORM_WITHIN_INTERVAL":
        sample_probs = np.mean(np.stack(snapshots, axis=0), axis=0)
    else:
        sample_probs = population.astype(float) / float(config.population_size)
    sample_probs = np.maximum(sample_probs, 0.0)
    sample_probs /= sample_probs.sum()
    return rng.multinomial(transition.n2, sample_probs).astype(np.int64)


def _surviving_initial(counts: np.ndarray) -> int:
    return int(np.count_nonzero(np.asarray(counts)[:-1]))


def _frequency_distance(simulated: np.ndarray, observed: np.ndarray, require_survival_match: bool) -> float:
    if require_survival_match and _surviving_initial(simulated) != _surviving_initial(observed):
        return math.inf
    s = simulated.astype(float) / simulated.sum()
    o = observed.astype(float) / observed.sum()
    return float(np.abs(s - o).sum())


def _tail_area(samples: np.ndarray, observed: float) -> float:
    a = float(np.mean(samples <= observed))
    b = float(np.mean(samples >= observed))
    return float(min(1.0, 2.0 * min(a, b)))


def _quantile_record(samples: np.ndarray, observed: float) -> dict[str, Any]:
    x = np.asarray(samples, dtype=float)
    return {
        "observed_value": float(observed),
        "replicate_quantiles": {
            "q05": float(np.quantile(x, 0.05)),
            "q50": float(np.quantile(x, 0.50)),
            "q95": float(np.quantile(x, 0.95)),
        },
        "tail_area": _tail_area(x, float(observed)),
    }


def _tv(a: np.ndarray, b: np.ndarray) -> float:
    aa = a.astype(float) / a.sum()
    bb = b.astype(float) / b.sum()
    return float(0.5 * np.abs(aa - bb).sum())


def _max_initial_frequency(x: np.ndarray) -> float:
    return float(np.max(x[:-1].astype(float) / x.sum())) if len(x) > 1 else 0.0


def _posterior_quantiles(values: np.ndarray) -> dict[str, float]:
    x = np.asarray(values, dtype=float)
    return {
        "q025": float(np.quantile(x, 0.025)),
        "q50": float(np.quantile(x, 0.50)),
        "q975": float(np.quantile(x, 0.975)),
    }


class _CulturalKandlerABCBase:
    frequency_dependent = False
    name = "cultural_kandler_abc_base"

    def run(self, job: ComputeJob, output_dir: Path) -> PluginRun:
        transition = parse_transition(job)
        config = parse_config(job, frequency_dependent=self.frequency_dependent)
        rng = np.random.default_rng(job.random_seed)

        r_draws = rng.uniform(config.replacement_low, config.replacement_high, size=config.simulations)
        if self.frequency_dependent:
            b_draws = rng.uniform(config.b_low, config.b_high, size=config.simulations)
        else:
            b_draws = np.zeros(config.simulations, dtype=float)

        distances = np.full(config.simulations, np.inf, dtype=float)
        for i in range(config.simulations):
            simulated = simulate_transition(
                rng,
                transition,
                config,
                replacement_fraction=float(r_draws[i]),
                b_freq=float(b_draws[i]),
            )
            distances[i] = _frequency_distance(
                simulated,
                transition.counts_t2,
                config.require_survivor_count_match,
            )

        finite_idx = np.flatnonzero(np.isfinite(distances))
        if finite_idx.size < config.retain:
            raise ValueError(
                "ABC could not retain the requested number of draws after the initial-variant survival constraint; "
                f"finite={finite_idx.size}, retain={config.retain}. The data/model may be poorly matched or the request too strict."
            )
        order = finite_idx[np.argsort(distances[finite_idx], kind="stable")[: config.retain]]
        post_r = r_draws[order]
        post_b = b_draws[order]
        post_d = distances[order]
        epsilon = float(post_d.max())

        ppc_counts = np.empty((config.posterior_predictive_draws, len(transition.labels)), dtype=np.int64)
        chosen = rng.integers(0, config.retain, size=config.posterior_predictive_draws)
        for j, idx in enumerate(chosen):
            ppc_counts[j] = simulate_transition(
                rng,
                transition,
                config,
                replacement_fraction=float(post_r[idx]),
                b_freq=float(post_b[idx]),
            )

        allowed = set(job.evaluation_plan.get("predeclared_discrepancies") or [])
        ppc: list[dict[str, Any]] = []
        if "phase_transition_total_variation" in allowed:
            reps = np.asarray([_tv(transition.counts_t1, x) for x in ppc_counts])
            rec = _quantile_record(reps, _tv(transition.counts_t1, transition.counts_t2))
            ppc.append({"discrepancy_id": "phase_transition_total_variation", **rec})
        if "initial_variant_survival_count" in allowed:
            reps = np.asarray([_surviving_initial(x) for x in ppc_counts], dtype=float)
            rec = _quantile_record(reps, float(_surviving_initial(transition.counts_t2)))
            ppc.append({"discrepancy_id": "initial_variant_survival_count", **rec})
        if "max_initial_variant_frequency_t2" in allowed:
            reps = np.asarray([_max_initial_frequency(x) for x in ppc_counts])
            rec = _quantile_record(reps, _max_initial_frequency(transition.counts_t2))
            ppc.append({"discrepancy_id": "max_initial_variant_frequency_t2", **rec})

        # Store accepted ABC draws and posterior predictive samples in an ArviZ-compatible
        # artifact. A single 'chain' dimension is merely an interchange representation;
        # these are retained ABC particles, not MCMC draws, so no R-hat/ESS is reported.
        posterior: dict[str, np.ndarray] = {
            "replacement_fraction": post_r[None, :],
            "abc_distance": post_d[None, :],
        }
        if self.frequency_dependent:
            posterior["b_freq"] = post_b[None, :]
        idata = az.from_dict(
            {
                "posterior": posterior,
                "posterior_predictive": {"t2_count": ppc_counts[None, :, :]},
                "observed_data": {
                    "t1_count": transition.counts_t1,
                    "t2_count": transition.counts_t2,
                },
            },
            coords={"variant": list(transition.labels)},
            dims={"t1_count": ["variant"], "t2_count": ["variant"]},
            sample_dims=["chain", "draw"],
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            import h5netcdf  # noqa: F401
        except ImportError:
            draw_path = output_dir / f"{job.analysis_id}__{job.model_id}__abc_draws.npz"
            payload = {
                "replacement_fraction": post_r,
                "abc_distance": post_d,
                "posterior_predictive_t2_count": ppc_counts,
                "observed_t1_count": transition.counts_t1,
                "observed_t2_count": transition.counts_t2,
                "variant_labels": np.asarray(transition.labels, dtype=str),
            }
            if self.frequency_dependent:
                payload["b_freq"] = post_b
            np.savez_compressed(draw_path, **payload)
            artifact_format = "JSON_SUMMARY_WITH_EXTERNAL_DRAW_ARTIFACT"
        else:
            draw_path = output_dir / f"{job.analysis_id}__{job.model_id}__abc_idata.nc"
            idata.to_netcdf(draw_path, engine="h5netcdf")
            artifact_format = "ARVIZ_INFERENCE_DATA_NETCDF"

        posterior_summary = {"replacement_fraction": _posterior_quantiles(post_r)}
        if self.frequency_dependent:
            posterior_summary["b_freq"] = _posterior_quantiles(post_b)
        abc_diagnostics = {
            "method": "ABC_REJECTION",
            "prior_simulations": config.simulations,
            "accepted_particles": config.retain,
            "epsilon_final": epsilon,
            "acceptance_fraction": float(config.retain / config.simulations),
            "distance_metric": "L1_FREQUENCY_WITH_OPTIONAL_EXACT_INITIAL_VARIANT_SURVIVAL",
            "summary_statistic_ids": ["phase2_identity_frequencies"],
            "summary_discrimination_status": str(
                job.evaluation_plan.get("abc_summary_discrimination_status") or "UNRESOLVED"
            ),
            "interpretation": "APPROXIMATE_PARAMETER_INFERENCE_ONLY",
        }
        parameter_summaries = [{
            "parameter_id": "replacement_fraction",
            "mean": float(np.mean(post_r)),
            "sd": float(np.std(post_r, ddof=1)),
            "q05": float(np.quantile(post_r, 0.05)),
            "q50": float(np.quantile(post_r, 0.50)),
            "q95": float(np.quantile(post_r, 0.95)),
            "unit": "dimensionless",
            "semantics": "MODEL_CONDITIONAL_PARAMETER_SUMMARY_ONLY",
        }]
        if self.frequency_dependent:
            parameter_summaries.append({
                "parameter_id": "frequency_bias_b",
                "mean": float(np.mean(post_b)),
                "sd": float(np.std(post_b, ddof=1)),
                "q05": float(np.quantile(post_b, 0.05)),
                "q50": float(np.quantile(post_b, 0.50)),
                "q95": float(np.quantile(post_b, 0.95)),
                "unit": "dimensionless",
                "semantics": "MODEL_CONDITIONAL_PARAMETER_SUMMARY_ONLY",
            })

        return PluginRun(
            draw_artifact=draw_path,
            artifact_format=artifact_format,
            sampler_diagnostics={
                "inference_class": "ABC",
                "chains": 1,
                "draws_per_chain": config.retain,
                "divergences": 0,
                "rhat_max": None,
                "ess_bulk_min": None,
                "ess_tail_min": None,
                "bfmi_min": None,
            },
            posterior_predictive_checks=ppc,
            predictive_validation=None,
            sbc={"status": "NOT_RUN", "simulations": 0, "rank_diagnostics": []},
            abc_diagnostics=abc_diagnostics,
            parameter_summaries=parameter_summaries,
        )


class CulturalNeutralKandlerABCPlugin(_CulturalKandlerABCBase):
    """Neutral/unbiased cultural copying as a Kandler-style generative ABC model."""

    name = "cultural_neutral_abc"
    frequency_dependent = False


class CulturalFrequencyKandlerABCPlugin(_CulturalKandlerABCBase):
    """Frequency-dependent alternative with b_freq inferred jointly with replacement r."""

    name = "cultural_frequency_dependent_abc"
    frequency_dependent = True
