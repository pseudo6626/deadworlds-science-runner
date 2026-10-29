# Deadworlds Science Runner

Scientific-compute runner for the Deadworlds Model Comparison/PPC layer.

Current reconstructed successor: **v0.9.0**.

The previously validated v0.8.9 package is recorded by Forge with SHA-256 `0cd24a1727c96d0101d67fb87288b3a95693e409b7879a6e62fde213427379d9`, but that exact archive was not retained in the chat runtime. v0.9.0 is therefore a new provenance line: it reconstructs the frozen v0.8.9 statistical behavior from the production contracts and verifies the reference fixture numerically rather than pretending to be the missing artifact.

## Safety boundary

The runner executes only Worker-issued immutable compute packages. It verifies the Worker hashes before computation. Raw compute may produce model-conditional parameter summaries, posterior predictive checks, and held-out predictive scores; it may **not** declare a historical mechanism true, choose a model as truth, or turn predictive preference into cognition/social-history evidence.

## Cultural Transmission backends

Production-registered plugins:

- `cultural_neutral_abc` — legacy simulator/ABC adequacy path.
- `cultural_frequency_dependent_abc` — legacy simulator/ABC adequacy path; ABC model choice remains blocked unless summary discrimination is independently validated.
- `cultural_neutral_copying_v1` — closed-state fixed-predictive neutral baseline.
- `cultural_frequency_dependent_grid_v1` — closed-state exact grid-Bayes frequency alternative; **default frequency backend**.
- `pymc_cultural_frequency_dependent_v1` — PyMC 6 equivalent backend, explicit opt-in only.

The closed-state model uses

`pi_i ∝ p_i^(1-b)`

for states already represented in the source phase. Under the frozen Deadworlds convention, `b=0` is neutral, `b<0` produces a common-variant/conformity-like aggregate weighting, and `b>0` produces a rare-variant/anti-conformity-like aggregate weighting. These labels describe model behavior only, not recovered cognition.

Zero-to-positive state appearances are blocked by Module 15 rather than assigned an invented innovation process.

### Frozen regression fixture

The six-phase reference fixture (`50/30/20 → 55/29/16 → 60/27/13 → 59/28/13 → 72/17/11 → 81/14/5`) must reproduce:

- neutral K-fold ELPD: `-30.058753607306258`
- frequency grid K-fold ELPD: `-26.951595127178244`
- full grid posterior mean `b`: `-0.2588764747792396`
- the stored pointwise K-fold predictive densities to numerical tolerance

The difference is still interpreted only as relative predictive performance; the stored reference comparison remains model-indistinguishable at its uncertainty resolution.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[pymc,dev]'
python -m pytest -q
```

## Run a Worker-issued bundle

```bash
deadworlds-compute run compute-bundle.json --out deadworlds-compute-output
```

When the bundle contains one-job transport/submission capabilities, the runner uploads the scientific artifact to Google Drive through Forge's private broker and submits the compact result automatically.

## GitHub-hosted compute

`.github/workflows/deadworlds-compute.yml` listens only for the `deadworlds-compute-v1` repository-dispatch event. The workflow requests a GitHub OIDC token with audience `deadworlds-compute`; sandbox Forge verifies the signed repository/workflow identity before returning the one-time compute bundle. No persistent Forge secret is stored in GitHub.

See `PRODUCTION_CONSTRAINTS.txt` for the frozen runtime and epistemic limits.
