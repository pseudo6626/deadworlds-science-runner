from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from ..contracts import ComputeJob
from .base import PluginRun


@dataclass(frozen=True)
class ClosedStateData:
    trait_family: str
    phase_order: tuple[str, ...]
    labels: tuple[str, ...]
    counts: tuple[np.ndarray, ...]
    partition_assignments: tuple[int, ...]
    fold_count: int

    @property
    def transition_ids(self) -> tuple[str, ...]:
        return tuple(f"{self.phase_order[i]}->{self.phase_order[i+1]}" for i in range(len(self.phase_order)-1))


def _require_int(v: Any, name: str, low: int = 1, high: int = 10_000_000) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, np.integer)) or not (low <= int(v) <= high):
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return int(v)


def parse_closed_state(job: ComputeJob) -> ClosedStateData:
    d = job.input_data
    family = str(d.get("trait_family") or "").strip()
    phase_order = tuple(str(x).strip() for x in (d.get("phase_order") or []))
    rows = d.get("phase_counts")
    partition = d.get("validation_partition")
    if not family or len(phase_order) < 4 or len(set(phase_order)) != len(phase_order):
        raise ValueError("closed-state cultural input requires one trait family and >=4 unique ordered phases")
    if not isinstance(rows, list) or len(rows) != len(phase_order):
        raise ValueError("phase_counts must contain exactly one row per phase_order entry")
    if not isinstance(partition, dict) or partition.get("scheme") != "K_FOLD_TRANSITIONS_V1":
        raise ValueError("validation_partition must use K_FOLD_TRANSITIONS_V1")
    fold_count = _require_int(partition.get("fold_count"), "validation_partition.fold_count", 2, 32)
    assignments_obj = partition.get("assignments")
    if not isinstance(assignments_obj, dict):
        raise ValueError("validation_partition.assignments must be an object")

    # Canonical state ordering is lexical across the frozen observed state set.
    states: set[str] = set()
    normalized_rows: list[dict[str, int]] = []
    for expected_phase, row in zip(phase_order, rows):
        if not isinstance(row, dict) or str(row.get("phase_id") or "") != expected_phase:
            raise ValueError("phase_counts phase_id order must match phase_order")
        raw_counts = row.get("counts")
        if not isinstance(raw_counts, dict) or not raw_counts:
            raise ValueError(f"phase {expected_phase} counts must be a non-empty object")
        c: dict[str, int] = {}
        for k, v in raw_counts.items():
            label = str(k).strip()
            if not label:
                raise ValueError("trait state labels may not be empty")
            c[label] = _require_int(v, f"count[{expected_phase}:{label}]", 0, 10_000_000)
            if c[label] > 0:
                states.add(label)
        n = _require_int(row.get("sample_size"), f"sample_size[{expected_phase}]", 1, 10_000_000)
        if sum(c.values()) != n:
            raise ValueError(f"phase {expected_phase} counts do not sum to sample_size")
        normalized_rows.append(c)
    if len(states) < 2:
        raise ValueError("closed-state model requires at least two observed trait states")
    labels = tuple(sorted(states))
    counts = tuple(np.asarray([r.get(s, 0) for s in labels], dtype=np.int64) for r in normalized_rows)

    assignments: list[int] = []
    for i, key in enumerate(f"{phase_order[j]}->{phase_order[j+1]}" for j in range(len(phase_order)-1)):
        if key not in assignments_obj:
            raise ValueError(f"validation partition is missing transition {key}")
        f = _require_int(assignments_obj[key], f"fold[{key}]", 0, fold_count - 1)
        assignments.append(f)
        # Frozen Module 15 blocks innovation rather than assigning a hidden pseudocount.
        src, dst = counts[i], counts[i + 1]
        appeared = [labels[j] for j in range(len(labels)) if src[j] == 0 and dst[j] > 0]
        if appeared:
            raise ValueError(
                f"closed-state model forbids zero-to-positive state appearance without explicit innovation model: {key}: {appeared}"
            )
    if len(set(assignments)) < 2:
        raise ValueError("K-fold partition must use at least two folds")
    return ClosedStateData(
        trait_family=family,
        phase_order=phase_order,
        labels=labels,
        counts=counts,
        partition_assignments=tuple(assignments),
        fold_count=fold_count,
    )


def biased_probabilities(source_counts: np.ndarray, b: float) -> np.ndarray:
    """Closed-state frequency-bias transform frozen by Module 15.

    pi_i ∝ p_i ** (1 - b)

    b = 0: neutral/unbiased copying
    b < 0: common variants receive greater weight (conformity-like aggregate pattern)
    b > 0: rarer variants receive greater weight (anti-conformity-like aggregate pattern)

    This is a model-conditional aggregate frequency transformation; b is not a
    direct observation of cognition or historical transmission mechanism.
    """
    x = np.asarray(source_counts, dtype=float)
    if np.any(x < 0) or x.sum() <= 0:
        raise ValueError("source counts must contain non-negative positive total")
    p = x / x.sum()
    positive = p > 0
    q = np.zeros_like(p)
    q[positive] = np.power(p[positive], 1.0 - float(b))
    z = q.sum()
    if not np.isfinite(z) or z <= 0:
        raise ValueError("frequency transform produced invalid probability mass")
    return q / z


def _log_multinomial(counts: np.ndarray, probs: np.ndarray) -> float:
    y = np.asarray(counts, dtype=np.int64)
    q = np.asarray(probs, dtype=float)
    if y.sum() <= 0 or np.any(y < 0) or len(y) != len(q):
        raise ValueError("invalid multinomial observation")
    if np.any((q <= 0) & (y > 0)):
        return -math.inf
    n = int(y.sum())
    out = math.lgamma(n + 1) - sum(math.lgamma(int(v) + 1) for v in y)
    out += float(np.sum(np.where(y > 0, y * np.log(np.where(q > 0, q, 1.0)), 0.0)))
    return float(out)


def transition_log_likelihoods(data: ClosedStateData, b: float) -> np.ndarray:
    return np.asarray(
        [
            _log_multinomial(data.counts[i + 1], biased_probabilities(data.counts[i], b))
            for i in range(len(data.counts) - 1)
        ],
        dtype=float,
    )


def _logsumexp(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    m = float(np.max(x))
    if not math.isfinite(m):
        return m
    return float(m + math.log(float(np.exp(x - m).sum())))


def _weighted_quantile(grid: np.ndarray, weights: np.ndarray, p: float) -> float:
    c = np.cumsum(weights)
    return float(np.interp(float(p), c, grid))


def _grid_posterior(data: ClosedStateData, grid: np.ndarray, train_indices: Iterable[int]) -> tuple[np.ndarray, np.ndarray]:
    idx = list(train_indices)
    log_like = np.asarray([sum(transition_log_likelihoods(data, float(b))[i] for i in idx) for b in grid])
    logw = log_like - _logsumexp(log_like)
    w = np.exp(logw)
    w /= w.sum()
    return log_like, w


def _kfold_pointwise_grid(data: ClosedStateData, grid: np.ndarray) -> list[dict[str, Any]]:
    # Precompute ll[transition, grid].
    ll = np.asarray([transition_log_likelihoods(data, float(b)) for b in grid], dtype=float).T
    pointwise: list[dict[str, Any]] = []
    assignments = np.asarray(data.partition_assignments, dtype=int)
    for i, unit_id in enumerate(data.transition_ids):
        held_fold = assignments[i]
        train = np.flatnonzero(assignments != held_fold)
        train_log = ll[train].sum(axis=0)
        pred = _logsumexp(train_log + ll[i]) - _logsumexp(train_log)
        pointwise.append({"unit_id": unit_id, "log_predictive_density": float(pred)})
    return pointwise


def _kfold_pointwise_fixed(data: ClosedStateData, b: float = 0.0) -> list[dict[str, Any]]:
    ll = transition_log_likelihoods(data, b)
    return [
        {"unit_id": unit_id, "log_predictive_density": float(value)}
        for unit_id, value in zip(data.transition_ids, ll)
    ]


def _elpd_summary(pointwise: list[dict[str, Any]], partition_sha256: str) -> dict[str, Any]:
    vals = np.asarray([float(x["log_predictive_density"]) for x in pointwise])
    elpd = float(vals.sum())
    se = float(np.std(vals, ddof=1) * math.sqrt(len(vals))) if len(vals) > 1 else 0.0
    return {
        "method": "K_FOLD",
        "elpd": elpd,
        "se": se,
        "pointwise_log_likelihood_available": False,
        "pareto_k_max": None,
        "pareto_k_bad_count": None,
        "partition_sha256": partition_sha256,
        "pointwise": pointwise,
    }


def _tv(a: np.ndarray, b: np.ndarray) -> float:
    pa = a / a.sum()
    pb = b / b.sum()
    return float(0.5 * np.abs(pa - pb).sum())


def _shannon(x: np.ndarray) -> float:
    p = np.asarray(x, dtype=float)
    p = p[p > 0]
    p /= p.sum()
    return float(-np.sum(p * np.log(p)))


def _observed_discrepancies(data: ClosedStateData) -> dict[str, float]:
    return {
        "mean_interphase_tv_distance": float(np.mean([_tv(data.counts[i], data.counts[i+1]) for i in range(len(data.counts)-1)])),
        "mean_destination_shannon_entropy": float(np.mean([_shannon(data.counts[i+1]) for i in range(len(data.counts)-1)])),
    }


def _replicate_discrepancies(data: ClosedStateData, rng: np.random.Generator, b: float) -> dict[str, float]:
    tvs: list[float] = []
    hs: list[float] = []
    for i in range(len(data.counts) - 1):
        q = biased_probabilities(data.counts[i], b)
        y = rng.multinomial(int(data.counts[i+1].sum()), q)
        tvs.append(_tv(data.counts[i], y))
        hs.append(_shannon(y))
    return {
        "mean_interphase_tv_distance": float(np.mean(tvs)),
        "mean_destination_shannon_entropy": float(np.mean(hs)),
    }


def _ppc_record(discrepancy_id: str, observed: float, reps: np.ndarray) -> dict[str, Any]:
    reps = np.asarray(reps, dtype=float)
    left = float(np.mean(reps <= observed))
    right = float(np.mean(reps >= observed))
    return {
        "discrepancy_id": discrepancy_id,
        "observed_value": float(observed),
        "replicate_quantiles": {
            "q05": float(np.quantile(reps, 0.05)),
            "q50": float(np.quantile(reps, 0.50)),
            "q95": float(np.quantile(reps, 0.95)),
        },
        "tail_area": float(min(1.0, 2.0 * min(left, right))),
    }


def _posterior_summary(grid: np.ndarray, weights: np.ndarray) -> dict[str, Any]:
    mean = float(np.sum(grid * weights))
    sd = float(math.sqrt(float(np.sum(weights * (grid - mean) ** 2))))
    return {
        "parameter_id": "frequency_bias_b",
        "mean": mean,
        "sd": sd,
        "q05": _weighted_quantile(grid, weights, 0.05),
        "q50": _weighted_quantile(grid, weights, 0.50),
        "q95": _weighted_quantile(grid, weights, 0.95),
        "unit": "dimensionless",
        "semantics": "MODEL_CONDITIONAL_PARAMETER_SUMMARY_ONLY",
    }


def _write_npz(path: Path, **arrays: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)


class CulturalNeutralCopyingPlugin:
    name = "cultural_neutral_copying_v1"

    def run(self, job: ComputeJob, output_dir: Path) -> PluginRun:
        if str(job.evaluation_plan.get("inference_method") or "") not in {"FIXED_PREDICTIVE", "AUTO"}:
            raise ValueError("neutral closed-state plugin requires FIXED_PREDICTIVE inference")
        data = parse_closed_state(job)
        draws = _require_int(job.parameters.get("draws", 1000), "draws", 100, 100_000)
        partition_hash = str(job.evaluation_plan.get("partition_sha256") or "")
        if len(partition_hash) != 64:
            raise ValueError("K-fold compute requires Worker-issued partition_sha256")
        rng = np.random.default_rng(job.random_seed)
        pointwise = _kfold_pointwise_fixed(data, 0.0)
        predictive = _elpd_summary(pointwise, partition_hash)
        allowed = set(job.evaluation_plan.get("predeclared_discrepancies") or [])
        observed = _observed_discrepancies(data)
        reps = {k: [] for k in observed if k in allowed}
        for _ in range(draws):
            r = _replicate_discrepancies(data, rng, 0.0)
            for k in reps:
                reps[k].append(r[k])
        ppc = [_ppc_record(k, observed[k], np.asarray(v)) for k, v in reps.items()]
        path = output_dir / f"{job.analysis_id}__{job.model_id}__fixed_predictive.npz"
        _write_npz(
            path,
            phase_order=np.asarray(data.phase_order),
            state_labels=np.asarray(data.labels),
            pointwise_log_predictive_density=np.asarray([x["log_predictive_density"] for x in pointwise]),
        )
        return PluginRun(
            draw_artifact=path,
            artifact_format="JSON_SUMMARY_WITH_EXTERNAL_DRAW_ARTIFACT",
            sampler_diagnostics={"inference_class": "FIXED_PREDICTIVE", "chains": None, "draws_per_chain": draws, "divergences": None, "rhat_max": None, "ess_bulk_min": None, "ess_tail_min": None, "bfmi_min": None},
            posterior_predictive_checks=ppc,
            predictive_validation=predictive,
            sbc={"status": "NOT_RUN", "simulations": 0, "rank_diagnostics": []},
            parameter_summaries=[],
        )


class CulturalFrequencyDependentGridPlugin:
    name = "cultural_frequency_dependent_grid_v1"

    def run(self, job: ComputeJob, output_dir: Path) -> PluginRun:
        if str(job.evaluation_plan.get("inference_method") or "") not in {"GRID_BAYES", "AUTO"}:
            raise ValueError("frequency-dependent grid plugin requires GRID_BAYES inference")
        data = parse_closed_state(job)
        bmin = float(job.parameters.get("b_prior_min", -0.5))
        bmax = float(job.parameters.get("b_prior_max", 0.5))
        grid_points = _require_int(job.parameters.get("grid_points", 1001), "grid_points", 101, 100_001)
        draws = _require_int(job.parameters.get("draws", 1000), "draws", 100, 100_000)
        if not (math.isfinite(bmin) and math.isfinite(bmax) and -2 <= bmin < bmax <= 2):
            raise ValueError("b prior bounds must be finite, ordered, and inside [-2, 2]")
        partition_hash = str(job.evaluation_plan.get("partition_sha256") or "")
        if len(partition_hash) != 64:
            raise ValueError("K-fold compute requires Worker-issued partition_sha256")
        grid = np.linspace(bmin, bmax, grid_points)
        _, weights = _grid_posterior(data, grid, range(len(data.counts)-1))
        pointwise = _kfold_pointwise_grid(data, grid)
        predictive = _elpd_summary(pointwise, partition_hash)
        summary = _posterior_summary(grid, weights)
        rng = np.random.default_rng(job.random_seed)
        allowed = set(job.evaluation_plan.get("predeclared_discrepancies") or [])
        observed = _observed_discrepancies(data)
        reps = {k: [] for k in observed if k in allowed}
        draw_b = rng.choice(grid, size=draws, p=weights)
        for b in draw_b:
            r = _replicate_discrepancies(data, rng, float(b))
            for k in reps:
                reps[k].append(r[k])
        ppc = [_ppc_record(k, observed[k], np.asarray(v)) for k, v in reps.items()]
        path = output_dir / f"{job.analysis_id}__{job.model_id}__grid_bayes.npz"
        _write_npz(
            path,
            b_grid=grid,
            posterior_weight=weights,
            posterior_draw_b=draw_b,
            pointwise_log_predictive_density=np.asarray([x["log_predictive_density"] for x in pointwise]),
            phase_order=np.asarray(data.phase_order),
            state_labels=np.asarray(data.labels),
        )
        return PluginRun(
            draw_artifact=path,
            artifact_format="JSON_SUMMARY_WITH_EXTERNAL_DRAW_ARTIFACT",
            sampler_diagnostics={"inference_class": "GRID_BAYES", "chains": None, "draws_per_chain": draws, "divergences": None, "rhat_max": None, "ess_bulk_min": None, "ess_tail_min": None, "bfmi_min": None},
            posterior_predictive_checks=ppc,
            predictive_validation=predictive,
            sbc={"status": "NOT_RUN", "simulations": 0, "rank_diagnostics": []},
            parameter_summaries=[summary],
        )
