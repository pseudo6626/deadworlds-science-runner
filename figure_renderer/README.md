# Deadworlds Figure Renderer v0.2.0

Deterministic static scientific renderer for the production Deadworlds `deadworlds-figure-spec-v1` contract.

The renderer never invents numeric plot data. Plotting values come only from `FigureSpec.data.bindings`; provenance and epistemic limits are preserved in the render manifest and, where needed, printed directly on detached static figures.

## Implemented live recipes

Production Forge currently emits concrete FigureSpecs for Module 10 and Modules 12–15. v0.2 implements every currently emitted Matplotlib-compatible recipe in Modules 1–11 (the five Module 10 recipes), plus the Module 12 and Module 15 adapters first implemented in v0.1:

- `m10_energy_lower_bound_ledger`
- `m10_energy_power_identifiability`
- `m10_process_trace_prerequisite_matrix`
- `m10_radiative_ceiling_vs_capture`
- `m10_measurement_formula_provenance` (licensed Matplotlib fallback)
- `m12a_trait_frequency_by_phase`
- `m12a_diversity_distance_by_phase`
- `m12a_transmission_model_identifiability`
- `m15a_evaluation_method_eligibility`
- `m15a_validation_diagnostics`
- `m15a_adequacy_vs_preference_contract`

Modules 1–9 and 11 already have recipe contracts in Forge but do not yet emit concrete FigureSpecs. The renderer intentionally fails closed for those recipes until Forge supplies deterministic binding objects.

## Determinism

v0.2 fixes Matplotlib SVG hash salt and export metadata. Regression tests require repeat renders of the same FigureSpec to produce identical output hashes.

## Local use

```bash
python -m pip install -c RENDERER_CONSTRAINTS.txt .
deadworlds-render-figure examples/m10_energy_lower_bound_ledger.json --out rendered/
```

Strict mode requires a persisted `module_run_id` and at least one `source_ref`.

## Hosted rendering

The package also contains the runner-side claim/execution scripts used by the GitHub Actions rendering workflow. The hosted protocol uses:

1. immutable Worker-issued FigureSpec package;
2. GitHub OIDC bound to the exact repository/workflow;
3. separate one-job lease and submit capabilities;
4. deterministic rendering on GitHub-hosted Python 3.13;
5. a deterministic ZIP render bundle;
6. resumable upload to Google Drive through a private render-storage Worker;
7. Drive SHA-256/size/MIME/appProperty verification before Forge marks the job complete.

No Google credential or long-lived render capability is sent to GitHub.
