from __future__ import annotations

from pathlib import Path

from ..contracts import ComputeJob
from .base import PluginRun


class PyMCGaussianLocationPlugin:
    """PyMC 6 implementation of the Gaussian-location smoke model.

    Kept separate from the exact plugin so contract tests do not depend on a compiled
    probabilistic-programming stack. Production scientific runners should install the
    `pymc` optional dependency from pyproject.toml.
    """

    name = "pymc_gaussian_location"

    def run(self, job: ComputeJob, output_dir: Path) -> PluginRun:
        import numpy as np
        import arviz as az
        import pymc as pm

        major = int(str(pm.__version__).split(".")[0])
        if major < 6:
            raise RuntimeError(
                f"{self.name} requires PyMC >=6 with ArviZ 1.x; found PyMC {pm.__version__}. "
                "Use a clean runner environment created from this package's pyproject.toml."
            )

        p = job.parameters
        y = np.asarray(job.input_data.get("y"), dtype=float)
        prior_mean = float(p.get("prior_mean", 0.0))
        prior_sd = float(p.get("prior_sd", 5.0))
        sigma = float(p.get("known_sigma", 1.0))
        chains = int(p.get("chains", 4))
        draws = int(p.get("draws", 1000))
        tune = int(p.get("tune", 1000))

        if y.ndim != 1 or y.size < 2 or not np.all(np.isfinite(y)):
            raise ValueError("pymc_gaussian_location requires finite 1-D input_data.y")

        with pm.Model() as model:
            mu = pm.Normal("mu", mu=prior_mean, sigma=prior_sd)
            pm.Normal("y", mu=mu, sigma=sigma, observed=y)
            idata = pm.sample(
                draws=draws,
                tune=tune,
                chains=chains,
                random_seed=job.random_seed,
                nuts_sampler="pymc",
                progressbar=False,
            )
            idata = pm.sample_posterior_predictive(idata, model=model, random_seed=job.random_seed, extend_inferencedata=True, progressbar=False)
            idata = pm.compute_log_likelihood(idata, model=model, extend_inferencedata=True)

        output_dir.mkdir(parents=True, exist_ok=True)
        draw_path = output_dir / f"{job.analysis_id}__{job.model_id}__idata.nc"
        idata.to_netcdf(draw_path)

        rhat_tree = az.rhat(idata, var_names=["mu"])
        ess_bulk_tree = az.ess(idata, var_names=["mu"], method="bulk")
        ess_tail_tree = az.ess(idata, var_names=["mu"], method="tail")
        def scalar(tree):
            return float(tree["posterior"].dataset["mu"].values)
        divergences = int(np.asarray(idata["sample_stats"].dataset["diverging"]).sum()) if "sample_stats" in idata.children else 0
        bfmi = az.bfmi(idata)
        bfmi_min = float(np.min(np.asarray(bfmi))) if bfmi is not None else None

        ppc = []
        allowed = set(job.evaluation_plan.get("predeclared_discrepancies") or [])
        if "sample_mean" in allowed:
            rep = np.asarray(idata["posterior_predictive"].dataset["y"]).mean(axis=-1).reshape(-1)
            obs = float(y.mean())
            ppc.append({
                "discrepancy_id": "sample_mean",
                "observed_value": obs,
                "replicate_quantiles": {"q05": float(np.quantile(rep,.05)), "q50": float(np.quantile(rep,.5)), "q95": float(np.quantile(rep,.95))},
                "tail_area": float(min(1.0, 2*min(np.mean(rep <= obs), np.mean(rep >= obs))))
            })

        validation = None
        method = str(job.evaluation_plan.get("predictive_validation_method") or "NONE").upper()
        if method == "PSIS_LOO":
            loo = az.loo(idata, var_name="y", pointwise=True)
            ks = np.asarray(loo.pareto_k, dtype=float)
            validation = {"method":"PSIS_LOO","elpd":float(loo.elpd),"se":float(loo.se),"pointwise_log_likelihood_available":True,"pareto_k_max":float(np.max(ks)),"pareto_k_bad_count":int(np.sum(ks > 0.7))}

        return PluginRun(
            draw_artifact=draw_path,
            artifact_format="ARVIZ_INFERENCE_DATA_NETCDF",
            sampler_diagnostics={"inference_class":"MCMC","chains":chains,"draws_per_chain":draws,"divergences":divergences,"rhat_max":scalar(rhat_tree),"ess_bulk_min":scalar(ess_bulk_tree),"ess_tail_min":scalar(ess_tail_tree),"bfmi_min":bfmi_min},
            posterior_predictive_checks=ppc,
            predictive_validation=validation,
            sbc={"status":"NOT_RUN","simulations":0,"rank_diagnostics":[]},
        )
