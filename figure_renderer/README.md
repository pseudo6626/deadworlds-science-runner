# Deadworlds Figure Renderer v0.4.0

Deterministic static scientific renderer for the Deadworlds `deadworlds-figure-spec-v1` contract.

The renderer does not invent numeric plot data. Numeric values come only from `FigureSpec.data.bindings`. Provenance, assumptions, unresolved quantities, and epistemic limits remain explicit in the render manifest and, where appropriate, on the detached static figure itself.

## Hosted recipe coverage

Renderer v0.4.0 currently supports 17 hosted recipes across Modules 1, 2, 10, 12, and 15.

### Module 1 — Atmospheric Evolution

- `m01_equilibrium_temperature_albedo_sensitivity`
- `m01_escape_retention_sensitivity`
- `m01_multistar_forcing_contributors`

These adapters preserve the distinction between deterministic sensitivity calculations and inferred atmospheric history. They do not infer greenhouse warming, exobase structure, escape rate, atmospheric-loss history, or unresolved stellar forcing.

### Module 2 — Geochemical Cycling

- `m02_atmospheric_element_budget`
- `m02_redox_ratio_diagnostics`
- `m02_rock_metal_ice_composition`

These adapters remain deliberately conservative. They do not convert broad DSS composition into mineralogy, measured atmospheric gas ratios into mantle oxygen fugacity, or incomplete atmospheric measurements into whole-planet inventories or aqueous pH.

### Module 10 — Technological Energetics

- `m10_energy_lower_bound_ledger`
- `m10_energy_power_identifiability`
- `m10_process_trace_prerequisite_matrix`
- `m10_radiative_ceiling_vs_capture`
- `m10_measurement_formula_provenance`

### Module 12 — Cultural Transmission

- `m12a_trait_frequency_by_phase`
- `m12a_diversity_distance_by_phase`
- `m12a_transmission_model_identifiability`

### Module 15 — Model Comparison / PPC

- `m15a_evaluation_method_eligibility`
- `m15a_validation_diagnostics`
- `m15a_adequacy_vs_preference_contract`

Any recipe without a registered deterministic adapter fails closed with `UnsupportedRecipeError`. Contract presence alone is not treated as renderer support.

## Determinism and validation

The validated renderer stack is pinned in `RENDERER_CONSTRAINTS.txt`:

- Python 3.13 hosted runtime
- Matplotlib 3.10.8
- NumPy 2.3.5
- jsonschema 4.26.0
- pytest 9.0.2

SVG hash salt and export metadata are fixed. Regression tests require repeat renders of the same FigureSpec to produce identical output hashes.

Renderer v0.4.0 has also been validated through the hosted path: Worker-issued immutable FigureSpec package, repository/workflow-bound GitHub OIDC, deterministic render, private Google Drive upload and verification, and idempotent Forge result submission. Final submission uses bounded retry for transient network/server failures so a lost response after a successful idempotent POST does not unnecessarily fail the hosted render.

## Local use

```bash
cd figure_renderer
python -m pip install -c RENDERER_CONSTRAINTS.txt '.[dev]'
deadworlds-render-figure examples/m10_energy_lower_bound_ledger.json --out rendered/
```

Strict mode requires a persisted `module_run_id` and at least one `source_ref`.

## Hosted rendering protocol

The package includes the runner-side claim and execution scripts used by the GitHub Actions rendering workflow. The hosted protocol uses:

1. an immutable Worker-issued FigureSpec package;
2. GitHub OIDC bound to the exact repository and workflow;
3. separate one-job lease and submit capabilities;
4. deterministic rendering on GitHub-hosted Python 3.13;
5. a deterministic ZIP render bundle;
6. resumable upload to Google Drive through a private render-storage Worker;
7. Drive SHA-256, size, MIME, and app-property verification;
8. bounded retry of the final idempotent Forge result submission.

No Google credential or long-lived render capability is sent to GitHub.
