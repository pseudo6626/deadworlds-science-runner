from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from ..contracts import ComputeJob
from .base import PluginRun
from .cultural_closed_state import (
    ClosedStateData,
    _elpd_summary,
    _observed_discrepancies,
    _ppc_record,
    _replicate_discrepancies,
    biased_probabilities,
    parse_closed_state,
    transition_log_likelihoods,
)


def _require_pymc6():
    try:
        import pymc as pm
        import arviz as az
    except Exception as exc:  # pragma: no cover - environment-specific
        raise RuntimeError("pymc_cultural_frequency_dependent_v1 requires PyMC 6.x and ArviZ 1.x") from exc
    major = int(str(pm.__version__).split(".")[0])
    if major < 6:
        raise RuntimeError(f"PyMC 6.x is required; found {pm.__version__}")
    return pm, az


def _logmeanexp(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    m = float(np.max(x))
    return float(m + math.log(float(np.exp(x - m).mean())))


def _fit_beta(
    data: ClosedStateData,
    indices: Iterable[int],
    *,
    bmin: float,
    bmax: float,
    chains: int,
    draws: int,
    tune: int,
    seed: int,
):
    pm, _ = _require_pymc6()
    idx = list(indices)
    if not idx:
        raise ValueError("PyMC fit requires at least one training transition")
    with pm.Model() as model:
        beta = pm.Uniform("frequency_bias_b", lower=bmin, upper=bmax)
        for i in idx:
            src = np.asarray(data.counts[i], dtype=float)
            dst = np.asarray(data.counts[i + 1], dtype=np.int64)
            pos = src > 0
            if np.any((~pos) & (dst > 0)):
                raise ValueError("closed-state PyMC model encountered forbidden zero-to-positive appearance")
            p = src[pos] / src[pos].sum()
            # q_i proportional to p_i ** (1-beta). Work in log space.
            logp = np.log(p)
            logits = (1.0 - beta) * logp
            q = pm.math.softmax(logits)
            pm.Multinomial(f"transition_{i}", n=int(dst.sum()), p=q, observed=dst[pos])
        idata = pm.sample(
            draws=draws,
            tune=tune,
            chains=chains,
            cores=1,
            random_seed=seed,
            target_accept=0.9,
            progressbar=False,
            return_inferencedata=True,
            compute_convergence_checks=True,
        )
    return idata


def _beta_draws(idata: Any) -> np.ndarray:
    return np.asarray(idata.posterior["frequency_bias_b"].values, dtype=float).reshape(-1)


def _mcmc_diagnostics(idata: Any, chains: int, draws: int) -> dict[str, Any]:
    _, az = _require_pymc6()
    rhat = np.asarray(az.rhat(idata, var_names=["frequency_bias_b"])["frequency_bias_b"].values, dtype=float)
    ess_bulk = np.asarray(az.ess(idata, var_names=["frequency_bias_b"], method="bulk")["frequency_bias_b"].values, dtype=float)
    ess_tail = np.asarray(az.ess(idata, var_names=["frequency_bias_b"], method="tail")["frequency_bias_b"].values, dtype=float)
    div = 0
    if hasattr(idata, "sample_stats") and "diverging" in idata.sample_stats:
        div = int(np.asarray(idata.sample_stats["diverging"].values).sum())
    bfmi = None
    try:
        vals = np.asarray(az.bfmi(idata), dtype=float)
        if vals.size:
            bfmi = float(np.nanmin(vals))
    except Exception:
        pass
    return {
        "inference_class": "MCMC",
        "chains": int(chains),
        "draws_per_chain": int(draws),
        "divergences": div,
        # Split-Rhat estimators may numerically dip a hair below one; the contract
        # treats 1 as the theoretical floor rather than evidence of super-convergence.
        "rhat_max": max(1.0, float(np.nanmax(rhat))),
        "ess_bulk_min": float(np.nanmin(ess_bulk)),
        "ess_tail_min": float(np.nanmin(ess_tail)),
        "bfmi_min": bfmi,
    }


def _parameter_summary(samples: np.ndarray) -> dict[str, Any]:
    x = np.asarray(samples, dtype=float)
    return {
        "parameter_id": "frequency_bias_b",
        "mean": float(np.mean(x)),
        "sd": float(np.std(x, ddof=1)),
        "q05": float(np.quantile(x, 0.05)),
        "q50": float(np.quantile(x, 0.50)),
        "q95": float(np.quantile(x, 0.95)),
        "unit": "dimensionless",
        "semantics": "MODEL_CONDITIONAL_PARAMETER_SUMMARY_ONLY",
    }


class PyMCCulturalFrequencyDependentPlugin:
    """PyMC 6 equivalent backend for the frozen closed-state frequency model.

    It intentionally uses the same q_i ∝ p_i^(1-b) likelihood as the exact-grid
    implementation. K-fold held-out predictive densities are computed by fitting
    only the training transitions in each frozen fold and integrating the held-out
    multinomial likelihood over posterior beta draws.
    """

    name = "pymc_cultural_frequency_dependent_v1"

    def run(self, job: ComputeJob, output_dir: Path) -> PluginRun:
        if str(job.evaluation_plan.get("inference_method") or "") not in {"MCMC", "AUTO"}:
            raise ValueError("PyMC cultural plugin requires MCMC inference")
        data = parse_closed_state(job)
        p = job.parameters
        chains = int(p.get("chains", 4))
        draws = int(p.get("draws", 1000))
        tune = int(p.get("tune", 1000))
        bmin = float(p.get("b_prior_min", -0.5))
        bmax = float(p.get("b_prior_max", 0.5))
        if chains < 2 or draws < 100 or tune < 0 or not (-2 <= bmin < bmax <= 2):
            raise ValueError("invalid PyMC cultural parameter policy")
        partition_hash = str(job.evaluation_plan.get("partition_sha256") or "")
        if len(partition_hash) != 64:
            raise ValueError("K-fold compute requires Worker-issued partition_sha256")

        assignments = np.asarray(data.partition_assignments, dtype=int)
        pointwise: list[dict[str, Any]] = []
        fold_samples: dict[int, np.ndarray] = {}
        for fold in sorted(set(assignments.tolist())):
            train = np.flatnonzero(assignments != fold).tolist()
            idata_fold = _fit_beta(
                data,
                train,
                bmin=bmin,
                bmax=bmax,
                chains=chains,
                draws=draws,
                tune=tune,
                seed=(job.random_seed + 1009 * (fold + 1)) & 0xFFFFFFFF,
            )
            fold_samples[fold] = _beta_draws(idata_fold)
        for i, unit_id in enumerate(data.transition_ids):
            beta_draw = fold_samples[int(assignments[i])]
            vals = np.asarray([transition_log_likelihoods(data, float(b))[i] for b in beta_draw], dtype=float)
            pointwise.append({"unit_id": unit_id, "log_predictive_density": _logmeanexp(vals)})
        predictive = _elpd_summary(pointwise, partition_hash)

        full = _fit_beta(
            data,
            range(len(data.counts) - 1),
            bmin=bmin,
            bmax=bmax,
            chains=chains,
            draws=draws,
            tune=tune,
            seed=job.random_seed,
        )
        beta = _beta_draws(full)
        summary = _parameter_summary(beta)
        diagnostics = _mcmc_diagnostics(full, chains, draws)

        rng = np.random.default_rng(job.random_seed ^ 0xD34DB33F)
        allowed = set(job.evaluation_plan.get("predeclared_discrepancies") or [])
        observed = _observed_discrepancies(data)
        reps = {k: [] for k in observed if k in allowed}
        n_ppc = min(max(draws, 500), 4000)
        chosen = rng.choice(beta, size=n_ppc, replace=True)
        for b in chosen:
            r = _replicate_discrepancies(data, rng, float(b))
            for k in reps:
                reps[k].append(r[k])
        ppc = [_ppc_record(k, observed[k], np.asarray(v)) for k, v in reps.items()]

        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{job.analysis_id}__{job.model_id}__pymc_idata.nc"
        try:
            full.to_netcdf(path, engine="h5netcdf")
        except Exception as exc:  # pragma: no cover - runtime environment contract
            raise RuntimeError("PyMC backend must emit ARVIZ_INFERENCE_DATA_NETCDF using h5netcdf") from exc

        return PluginRun(
            draw_artifact=path,
            artifact_format="ARVIZ_INFERENCE_DATA_NETCDF",
            sampler_diagnostics=diagnostics,
            posterior_predictive_checks=ppc,
            predictive_validation=predictive,
            sbc={"status": "NOT_RUN", "simulations": 0, "rank_diagnostics": [], "purpose": "INFERENCE_IMPLEMENTATION_VALIDATION_ONLY"},
            parameter_summaries=[summary],
        )
