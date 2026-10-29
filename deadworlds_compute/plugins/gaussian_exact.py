from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import arviz as az
import numpy as np

from ..contracts import ComputeJob
from .base import PluginRun


class GaussianLocationExactPlugin:
    """Exact conjugate Normal-location posterior.

    This is a smoke-test scientific plugin, not a replacement for PyMC. It is useful
    for validating the Deadworlds compute contract in environments where PyMC is not
    available or where its binary dependency stack is intentionally absent.
    """

    name = "gaussian_location_exact"

    def run(self, job: ComputeJob, output_dir: Path) -> PluginRun:
        p = job.parameters
        y = np.asarray(job.input_data.get("y"), dtype=float)
        if y.ndim != 1 or y.size < 2 or not np.all(np.isfinite(y)):
            raise ValueError("gaussian_location_exact requires finite 1-D input_data.y with at least 2 observations")

        prior_mean = float(p.get("prior_mean", 0.0))
        prior_sd = float(p.get("prior_sd", 5.0))
        sigma = float(p.get("known_sigma", 1.0))
        chains = int(p.get("chains", 4))
        draws = int(p.get("draws", 1000))
        if prior_sd <= 0 or sigma <= 0 or chains < 2 or draws < 100:
            raise ValueError("Invalid prior/sigma/chains/draws")

        prior_prec = 1.0 / prior_sd**2
        like_prec = y.size / sigma**2
        post_var = 1.0 / (prior_prec + like_prec)
        post_mean = post_var * (prior_mean * prior_prec + y.sum() / sigma**2)
        post_sd = math.sqrt(post_var)

        rng = np.random.default_rng(job.random_seed)
        mu = rng.normal(post_mean, post_sd, size=(chains, draws))
        y_rep = rng.normal(mu[:, :, None], sigma, size=(chains, draws, y.size))
        log_lik = -0.5 * math.log(2 * math.pi * sigma**2) - 0.5 * ((y[None, None, :] - mu[:, :, None]) / sigma) ** 2

        dt = az.from_dict(
            {
                "posterior": {"mu": mu},
                "posterior_predictive": {"y": y_rep},
                "log_likelihood": {"y": log_lik},
                "observed_data": {"y": y},
            },
            sample_dims=["chain", "draw"],
        )

        rhat = float(dt_rscalar(az.rhat(dt, var_names=["mu"]), "mu"))
        ess_bulk = float(dt_rscalar(az.ess(dt, var_names=["mu"], method="bulk"), "mu"))
        ess_tail = float(dt_rscalar(az.ess(dt, var_names=["mu"], method="tail"), "mu"))

        ppc = []
        allowed = set(job.evaluation_plan.get("predeclared_discrepancies") or [])
        if "sample_mean" in allowed:
            rep = y_rep.mean(axis=-1).reshape(-1)
            obs = float(y.mean())
            ppc.append(
                {
                    "discrepancy_id": "sample_mean",
                    "observed_value": obs,
                    "replicate_quantiles": {
                        "q05": float(np.quantile(rep, 0.05)),
                        "q50": float(np.quantile(rep, 0.50)),
                        "q95": float(np.quantile(rep, 0.95)),
                    },
                    "tail_area": float(min(1.0, 2 * min(np.mean(rep <= obs), np.mean(rep >= obs)))),
                }
            )

        validation = None
        method = str(job.evaluation_plan.get("predictive_validation_method") or "NONE").upper()
        if method == "PSIS_LOO":
            loo = az.loo(dt, var_name="y", pointwise=True)
            ks = np.asarray(loo.pareto_k, dtype=float)
            validation = {
                "method": "PSIS_LOO",
                "elpd": float(loo.elpd),
                "se": float(loo.se),
                "pointwise_log_likelihood_available": True,
                "pareto_k_max": float(np.max(ks)),
                "pareto_k_bad_count": int(np.sum(ks > 0.7)),
            }
        elif method not in {"NONE", ""}:
            raise ValueError(f"Exact smoke plugin currently supports predictive_validation_method NONE or PSIS_LOO, not {method}")

        output_dir.mkdir(parents=True, exist_ok=True)
        draw_path = output_dir / f"{job.analysis_id}__{job.model_id}__draws.npz"
        np.savez_compressed(
            draw_path,
            posterior_mu=mu,
            posterior_predictive_y=y_rep,
            log_likelihood_y=log_lik,
            observed_y=y,
            posterior_mean=np.asarray(post_mean),
            posterior_sd=np.asarray(post_sd),
        )

        return PluginRun(
            draw_artifact=draw_path,
            artifact_format="JSON_SUMMARY_WITH_EXTERNAL_DRAW_ARTIFACT",
            sampler_diagnostics={
                "inference_class": "SIMULATION_ONLY",
                "chains": chains,
                "draws_per_chain": draws,
                "divergences": 0,
                "rhat_max": rhat,
                "ess_bulk_min": ess_bulk,
                "ess_tail_min": ess_tail,
                "bfmi_min": None,
            },
            posterior_predictive_checks=ppc,
            predictive_validation=validation,
            sbc={"status": "NOT_RUN", "simulations": 0, "rank_diagnostics": []},
        )


def dt_rscalar(tree: Any, variable: str) -> float:
    # ArviZ 1.x returns an xarray.DataTree whose posterior child holds scalar diagnostics.
    if hasattr(tree, "children") and "posterior" in tree.children:
        return float(tree["posterior"].dataset[variable].values)
    # Defensive compatibility with older return types.
    if hasattr(tree, "data_vars"):
        return float(tree[variable].values)
    raise TypeError(f"Unsupported ArviZ diagnostic return type: {type(tree)!r}")
