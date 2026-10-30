# Deadworlds Figure Renderer v0.8.0

Deterministic static scientific renderer for the Deadworlds `deadworlds-figure-spec-v1` contract.

The renderer does not invent numeric plot data. Numeric values come only from `FigureSpec.data.bindings`. Provenance, assumptions, unresolved quantities, and epistemic limits remain explicit in the render manifest and, where appropriate, on the detached static figure itself.

## Hosted recipe coverage

Renderer v0.8.0 currently supports 49 hosted recipes across Modules 1-6, 9-15 except Modules 7-8 and the blocked M11 settlement-posterior recipe.

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

### Module 3 — Ecological Energy Budgets

- `m03_capture_efficiency_sensitivity`
- `m03_trophic_transfer_sensitivity`
- `m03_energy_channel_identifiability`

Module 3 renders only deterministic assumption sensitivities and evidence-status/identifiability information. Capture efficiency, actual trophic-transfer efficiency, productivity, biomass, and channel energy magnitudes remain unresolved unless independently measured or modeled by a later licensed analysis. The 3D spatial-productivity recipe remains unsupported until spatially resolved productivity evidence exists.

### Module 4 — Biomechanics Scaling

- `m04_gravity_jump_sensitivity`
- `m04_froude_similarity_grid`
- `m04_dynamic_pressure_grid`
- `m04_terminal_velocity_grid`
- `m04_lift_loading_grid`
- `m04_self_weight_support_scaling`

Module 4 renders explicit mechanics sensitivity grids only. Present-atmosphere aerodynamic calculations remain labeled `PRESENT_STATE_ONLY` and are never substituted for the unresolved biosphere-era medium. Launch speed, organism scale, gait transitions, ballistic coefficient, flight feasibility, wing loading, material strength, failure size, and locomotor power are not inferred.

### Module 5 — Sensory Ecology

- `m05_stellar_emission_peak_context`
- `m05_acoustic_sound_speed_sensitivity`
- `m05_diffraction_resolution_sensitivity`
- `m05_channel_identifiability`

Module 5 separates physical carrier context from evolved sensory biology. Wien-law stellar peaks are not surface spectra or receptor optima; present-medium sound-speed cases are not paleo acoustic active space; diffraction grids are not actual visual acuity. Carrier availability never becomes sensory prevalence or importance.

### Module 6 — Non-acoustic Communication

- `m06_channel_identifiability_matrix`
- `m06_visual_angular_geometry_sensitivity`
- `m06_sender_medium_receiver_prerequisites`
- `m06_multimodal_constraint_map`

Module 6 figures use only the public physical-carrier/prerequisite ledger. Hidden reconstructed sender or receiver biology is forbidden from FigureSpec bindings and public derived evidence. Sender and receiver prerequisites remain unresolved from public evidence; angular geometry does not become visibility or range, and the constraint map does not rank channels or infer evolved preference. Active magnetic signaling remains blocked by the v1 module policy.


### Module 9 — Spatial Archaeology

- `m09_recovered_site_map`
- `m09_pairwise_distance_matrix`
- `m09_sampling_and_recovery_context`
- `m09_spatial_inference_prerequisite_matrix`

Module 9 renders recovered-site geometry, descriptive distances, survey context, and blocked-analysis prerequisites only. Single-point site markers never become routes or networks; recovered-site density never becomes ancient settlement density; local survey grids are never promoted to planetary coordinates.

### Module 11 — Demography

- `m11a_proxy_concordance_matrix`
- `m11a_population_inference_prerequisites`
- `m11a_demographic_inference_ladder`

Module 11 keeps recovered proxies, relative trends, minimum-individual evidence, and calibrated population at distinct epistemic levels. Hosted figures expose readiness/status only and never convert a proxy directly into population. `m11a_settlement_proxy_by_phase` remains blocked until chronology and sampling uncertainty are actually propagated.

### Module 13 — Language Contact

- `m13a_corpus_readiness`
- `m13a_alternative_explanation_matrix`
- `m13a_direction_identifiability`
- `m13a_comparison_provenance`

Module 13 renders recovered-corpus readiness and later-model eligibility only. It does not emit borrowing/contact probabilities, donor-recipient assignments, contact edges, social networks, or preferred models.

### Module 14 — Inscription Decipherment

- `m14a_mark_inventory`
- `m14a_sequence_reading_order`
- `m14a_decipherment_prerequisite_ladder`
- `m14a_model_handoff`

Module 14 renders formal recovered mark structure and analysis prerequisites only. It never emits sign values, phonetic or semantic assignments, translations, script classifications, or model winners.

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

The hosted renderer path has been validated end to end: Worker-issued immutable FigureSpec package, repository/workflow-bound GitHub OIDC, deterministic render, private Google Drive upload and verification, and idempotent Forge result submission. Final submission uses bounded retry for transient network/server failures so a lost response after a successful idempotent POST does not unnecessarily fail the hosted render.

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
